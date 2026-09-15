"""Organization generation: seed and parameters in, the static organization out, equal every time.

The organization is the part of the world no scenario owns — people, teams, the
reporting line, skills records, work-domain components (DESIGN, "The world's shape";
"Org-level facts are static across the world; scenarios select, never mutate"). It is
generated first and alone, and a scenario later slices it: chooses a leaver, a need and
a window so that the static facts yield the class it intends. That is why the generator
guarantees *shapes* rather than outcomes. It makes sure the organization contains what
the golden set's classes must be able to select — a skill nobody holds (the
``uncovered`` class), a skill exactly one person holds, a skill held broadly, people
whose skills record is absent (``missing_information``), components whose membership
crosses team lines — and leaves coverage-as-a-search to the scenario's own invariant.
An organization that promised every skill two holders would have made three Tier 3
classes unplantable.

Randomness is one ``random.Random`` created from the seed and passed to every helper;
no helper builds its own and nothing here touches the module-level functions, so the
sequence of draws is a function of the seed alone. The same seed, the same parameters
and the same generator version produce an equal ``OrgSpec``, and a test says so. Ids
are minted after the seats are shuffled, so ``emp_001`` is no likelier to be a lead than
``emp_028`` — an id reveals nothing about the structure around it.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from random import Random
from typing import cast

from leaveimpact.core.entities import Component, Employee, Team
from leaveimpact.core.enums import EmploymentType, Grade
from leaveimpact.core.ids import (
    SkillId,
    TeamId,
    component_id,
    employee_id,
    team_id,
)
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    expect_fields,
    field_of,
    integer_field,
    string_field,
)
from leaveimpact.core.worldtime import zone
from leaveimpact.world.version import GENERATOR_VERSION, GeneratorVersion
from leaveimpact.world.vocabulary import (
    CITIES,
    COMPONENT_NAMES,
    FAMILY_NAMES,
    GIVEN_NAMES,
    SKILLS,
    TEAM_NAMES,
    City,
)
from leaveimpact.world.zones import gap_holds_all_year

# The three skills every organization sets aside before the popularity draw: one nobody
# holds, one exactly one person holds, one held by at least a third of the people who
# have a skills record. Which skill plays which part is the seed's to decide.
_ANCHOR_SKILLS = 4
_BROAD_HOLDER_SHARE = 1 / 3

# A component is a handful of people, enough to cross two teams and still be a group a
# clause can name ("someone from the payments component").
_COMPONENT_MEMBERS = (3, 6)

# After round-robin dealing, at most this many members change team, so sizes differ by
# a few rather than by the ten-against-three an independent draw produced.
_TEAM_SIZE_MOVES = 2

# Non-lead grades, weighted towards the middle of a typical engineering team.
_GRADE_WEIGHTS: tuple[tuple[Grade, int], ...] = (
    (Grade.JUNIOR, 3),
    (Grade.MID, 4),
    (Grade.SENIOR, 3),
)


@dataclass(frozen=True, slots=True)
class OrgParams:
    """Every input besides the seed that can change the organization ``generate_org`` produces.

    The rule this type exists for: a generation dial lives here or it does not exist, so
    provenance is complete by construction and a knob added later cannot escape the
    record. ``org_size`` and ``team_count`` are the vision's two parameters;
    ``blank_skill_records`` is the number of people whose HR record carries no skills
    field at all (the missing-information case, distinct from an empty list);
    ``skills_per_person`` bounds the popularity draw, anchors excluded;
    ``contractor_share`` and ``remote_share`` are the probabilities that a non-lead is a
    contractor and that a person sits in a city other than the team's home city, the
    two dimensions policy clauses and timezone distractors turn on; a share above zero
    also guarantees one contractor, so a contractor clause can always find its scope.
    ``reference_timezone`` is the zone the world's truth is read in, an org parameter
    because the organization guarantees one person at least ``timezone_gap_hours`` from
    it at every hour of the rules year (the timezone affordance ruling at step 8): a
    boundary event is only plausible working time for someone that far away, and the
    golden set plans the modifier on several scenarios, so the shape is guaranteed the
    way the contractor is rather than left to the city draw. Six hours is the least gap
    at which a late-afternoon meeting crosses midnight in the other zone.

    Validation here owns the generator's ranges and cross-field constraints, rejected at
    construction and by name rather than somewhere inside a draw; scalar types are the
    typed API's, checked where raw configuration enters the system (the generator entry
    point, when it exists), not defended again here. A count that must exclude ``bool``
    is a semantic value's concern, as with a requirement's count in ``core``; a
    generator parameter has no caller that produces one by accident.

    >>> OrgParams(org_size=3, team_count=2)
    Traceback (most recent call last):
    ...
    ValueError: org_size must be at least 6 and at least twice team_count, got 3 for 2 teams
    """

    org_size: int = 28
    team_count: int = 5
    component_count: int = 5
    blank_skill_records: int = 2
    skills_per_person: tuple[int, int] = (1, 4)
    contractor_share: float = 0.15
    remote_share: float = 0.25
    reference_timezone: str = "Europe/Istanbul"
    timezone_gap_hours: int = 6

    def __post_init__(self) -> None:
        zone(self.reference_timezone)
        if self.timezone_gap_hours < 1:
            raise ValueError(
                f"timezone_gap_hours must be at least 1, got {self.timezone_gap_hours}"
            )
        if not _far_cities(self):
            raise ValueError(
                f"no city in the vocabulary is {self.timezone_gap_hours} hours from "
                f"{self.reference_timezone} all year, so the timezone affordance cannot be "
                "guaranteed"
            )
        if not 2 <= self.team_count <= len(TEAM_NAMES):
            raise ValueError(
                f"team_count must be between 2 and {len(TEAM_NAMES)} (the team vocabulary), "
                f"got {self.team_count}"
            )
        if self.org_size < max(_COMPONENT_MEMBERS[1], 2 * self.team_count):
            raise ValueError(
                f"org_size must be at least {_COMPONENT_MEMBERS[1]} and at least twice "
                f"team_count, got {self.org_size} for {self.team_count} teams"
            )
        name_capacity = len(GIVEN_NAMES) * len(FAMILY_NAMES)
        if self.org_size > name_capacity:
            raise ValueError(
                f"org_size must be at most {name_capacity} (the distinct names the vocabulary "
                f"can form), got {self.org_size}"
            )
        if not 1 <= self.component_count <= len(COMPONENT_NAMES):
            raise ValueError(
                f"component_count must be between 1 and {len(COMPONENT_NAMES)} "
                f"(the component vocabulary), got {self.component_count}"
            )
        if not 0 <= self.blank_skill_records <= self.org_size - 5:
            raise ValueError(
                "blank_skill_records must leave at least five people with a skills record (the "
                "paired skill's cast: its three holders and two recorded employees lacking it), "
                f"got {self.blank_skill_records} of {self.org_size}"
            )
        low, high = self.skills_per_person
        if not 1 <= low <= high <= len(SKILLS) - _ANCHOR_SKILLS:
            raise ValueError(
                "skills_per_person must satisfy 1 <= low <= high <= "
                f"{len(SKILLS) - _ANCHOR_SKILLS} (the vocabulary minus the four anchors), "
                f"got {self.skills_per_person}"
            )
        shares = (("contractor_share", self.contractor_share), ("remote_share", self.remote_share))
        for name, share in shares:
            if not 0.0 <= share <= 1.0:
                raise ValueError(f"{name} is a probability, got {share}")


def _far_cities(params: OrgParams) -> tuple[City, ...]:
    """The vocabulary's cities at least the parameterized gap from the reference zone all year."""
    return tuple(
        city
        for city in CITIES
        if gap_holds_all_year(city.timezone, params.reference_timezone, params.timezone_gap_hours)
    )


DEFAULT_PARAMS = OrgParams()


def encode_org_params(params: OrgParams) -> JsonObject:
    """``params`` as a JSON object, one field per dial in declaration order.

    The sealed world spec and the world manifest both carry it, so the encoding lives with
    the type: a dial added to ``OrgParams`` reaches every artifact through this one function.

    >>> encode_org_params(OrgParams(org_size=8, team_count=2))["skills_per_person"]
    [1, 4]
    """
    return {**asdict(params), "skills_per_person": list(params.skills_per_person)}


def decode_org_params(data: Mapping[str, object]) -> OrgParams:
    """The ``OrgParams`` that ``data`` encodes; the semantic ranges are the constructor's.

    Exactly the declared fields, each of its declared scalar type — a JSON boolean is not a
    count and a number is not a zone name — with the skills bounds back to a pair. A dial
    added to the type reaches the encoder by itself and fails here until the decoder is
    taught it, which is the loud failure a sealed artifact's reader wants.

    >>> decode_org_params(encode_org_params(DEFAULT_PARAMS)) == DEFAULT_PARAMS
    True
    """
    expect_fields(data, tuple(field.name for field in fields(OrgParams)), "org params")
    return OrgParams(
        org_size=integer_field(data, "org_size"),
        team_count=integer_field(data, "team_count"),
        component_count=integer_field(data, "component_count"),
        blank_skill_records=integer_field(data, "blank_skill_records"),
        skills_per_person=_integer_pair(data, "skills_per_person"),
        contractor_share=_number_field(data, "contractor_share"),
        remote_share=_number_field(data, "remote_share"),
        reference_timezone=string_field(data, "reference_timezone"),
        timezone_gap_hours=integer_field(data, "timezone_gap_hours"),
    )


def _integer_pair(data: Mapping[str, object], key: str) -> tuple[int, int]:
    items = array_field(data, key)
    if len(items) != 2 or any(not _is_integer(item) for item in items):
        raise ValueError(f"{key} is a pair of integers, got {items!r}")
    low, high = items
    return int(cast(int, low)), int(cast(int, high))


def _number_field(data: Mapping[str, object], key: str) -> float:
    value = field_of(data, key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{key} is a number, got {type(value).__name__}")
    return float(value)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class OrgSpec:
    """A generated organization with the three inputs that produced it.

    ``seed`` is the stochastic realization, ``params`` the shape, ``generator_version`` the
    algorithm; holding the same params and version while varying the seed gives another
    organization of the same regime. ``skills`` is the whole closed vocabulary, held
    skills and unheld alike, so the consumer that needs "a skill nobody has" reads it here
    and never reconstructs the vocabulary from the people.
    """

    seed: int
    params: OrgParams
    generator_version: GeneratorVersion
    teams: tuple[Team, ...]
    employees: tuple[Employee, ...]
    components: tuple[Component, ...]
    skills: tuple[SkillId, ...]

    def members_of(self, team: TeamId) -> tuple[Employee, ...]:
        """The employees whose ``team_id`` is ``team``, in id order."""
        return tuple(employee for employee in self.employees if employee.team_id == team)

    def holders_of(self, skill: SkillId) -> tuple[Employee, ...]:
        """The employees whose skills record lists ``skill``; no record, never listed."""
        return tuple(
            employee
            for employee in self.employees
            if employee.skills is not None and skill in employee.skills
        )


@dataclass(frozen=True, slots=True)
class _Seat:
    """A position in the organization before a person fills it: which team, and whether its lead."""

    team_index: int
    lead: bool


def generate_org(seed: int, params: OrgParams) -> OrgSpec:
    """The organization ``seed`` and ``params`` describe, stamped with the generator version.

    Guaranteed by construction, and asserted by the tests: exactly ``org_size`` people in
    ``team_count`` teams of a few people each, never a lead alone; one root with no
    manager, who leads the first team; every other team led by a lead reporting to the
    root; every non-lead reporting to their own team's lead; leads are employees, never
    contractors, and at least one contractor exists when the share is above zero; a
    person's location, country and timezone belong to one city, and at least one person
    sits ``timezone_gap_hours`` or more from the reference zone all year; names unique; exactly
    ``blank_skill_records`` people with ``skills`` absent, none of them a contractor; among
    the vocabulary at least one skill with no holder, one with exactly one, one held by
    at least a third of the people with a record, one held by exactly two employees and
    by a contractor when one exists; every component's members drawn from at least two
    teams, the first component holding a blank-record member and the second being exactly
    the paired skill's cast: its holders and two recorded employees lacking it, so it
    holds no blank record.

    >>> generate_org(7, DEFAULT_PARAMS) == generate_org(7, DEFAULT_PARAMS)
    True
    >>> len(generate_org(7, DEFAULT_PARAMS).employees)
    28
    """
    rng = Random(seed)
    teams = _teams(rng, params)
    seats = _seats(rng, params)
    lead_seat_by_team = {seat.team_index: index for index, seat in enumerate(seats) if seat.lead}
    root_seat = lead_seat_by_team[0]
    names = _names(rng, params.org_size)
    cities = _cities(rng, seats, params)
    contractors = _contractors(rng, seats, params)
    skills, paired = _skills(rng, params, contractors)

    employees: list[Employee] = []
    for index, seat in enumerate(seats):
        if seat.lead:
            manager = None if index == root_seat else employee_id(root_seat + 1)
            grade, employment = Grade.LEAD, EmploymentType.EMPLOYEE
        else:
            manager = employee_id(lead_seat_by_team[seat.team_index] + 1)
            grade = _weighted_choice(rng, _GRADE_WEIGHTS)
            is_contractor = index in contractors
            employment = EmploymentType.CONTRACTOR if is_contractor else EmploymentType.EMPLOYEE
        employees.append(
            Employee(
                id=employee_id(index + 1),
                name=names[index],
                team_id=teams[seat.team_index].id,
                manager_id=manager,
                skills=skills[index],
                location=cities[index].name,
                country=cities[index].country,
                timezone=cities[index].timezone,
                grade=grade,
                employment_type=employment,
            )
        )

    return OrgSpec(
        seed=seed,
        params=params,
        generator_version=GENERATOR_VERSION,
        teams=teams,
        employees=tuple(employees),
        components=_components(rng, params, teams, tuple(employees), paired),
        skills=tuple(skill.id for skill in SKILLS),
    )


def _teams(rng: Random, params: OrgParams) -> tuple[Team, ...]:
    names = rng.sample(TEAM_NAMES, params.team_count)
    return tuple(Team(id=team_id(number), name=name) for number, name in enumerate(names, start=1))


def _seats(rng: Random, params: OrgParams) -> list[_Seat]:
    """One lead per team, members dealt round-robin, a few moved between teams, then shuffled.

    Independent random placement gave a ten-against-three split at twenty-eight people,
    and a three-person team leaves a scenario nothing to search inside it. Dealing keeps
    sizes within one of each other; the moves put back enough variance that teams are not
    interchangeable, at most ``_TEAM_SIZE_MOVES`` of them and never from a team that would
    be left with its lead alone. The final shuffle is what keeps ids structure-free: a
    seat's position in this list becomes the employee number.
    """
    team_indices = range(params.team_count)
    seats = [_Seat(team, lead=True) for team in team_indices]
    member_count = params.org_size - params.team_count
    members = [_Seat(index % params.team_count, lead=False) for index in range(member_count)]
    for _ in range(rng.randint(0, _TEAM_SIZE_MOVES)):
        size = Counter(seat.team_index for seat in members)
        donors = [team for team in team_indices if size[team] >= 2]
        source = rng.choice(donors)
        destination = rng.choice([team for team in team_indices if team != source])
        from_source = [index for index, seat in enumerate(members) if seat.team_index == source]
        members[rng.choice(from_source)] = _Seat(destination, lead=False)
    seats += members
    rng.shuffle(seats)
    return seats


def _contractors(rng: Random, seats: list[_Seat], params: OrgParams) -> set[int]:
    """The seat indices contractors hold: each non-lead with ``contractor_share``, one guaranteed.

    A contractor-scoped policy clause can only become relevant in a world that has a
    contractor, and a share of fifteen percent over twenty-odd people leaves that to
    chance — the same reasoning as the skill anchors. A share of zero means none, and
    then nothing is guaranteed: the parameter stays honest. The draw is capped so that
    the blank records and four employees with a record still fit among the employee
    seats, which the paired skill's cast needs (two holders, two recorded non-holders);
    the guaranteed contractor is never the one dropped.
    """
    candidates = [index for index, seat in enumerate(seats) if not seat.lead]
    if params.contractor_share == 0.0:
        return set()
    contractors = {index for index in candidates if rng.random() < params.contractor_share}
    guaranteed = rng.choice(candidates)
    contractors.add(guaranteed)
    room = params.org_size - params.blank_skill_records - 4
    while len(contractors) > room:
        contractors.remove(rng.choice(sorted(contractors - {guaranteed})))
    return contractors


def _names(rng: Random, count: int) -> list[str]:
    """``count`` distinct full names, drawn without replacement over every given–family pair."""
    pairs = rng.sample(range(len(GIVEN_NAMES) * len(FAMILY_NAMES)), count)
    return [
        f"{GIVEN_NAMES[pair // len(FAMILY_NAMES)]} {FAMILY_NAMES[pair % len(FAMILY_NAMES)]}"
        for pair in pairs
    ]


def _cities(rng: Random, seats: list[_Seat], params: OrgParams) -> list[City]:
    """Each team has a home city; a person sits there or, with ``remote_share``, elsewhere.

    One far seat is guaranteed the way the contractor is: when the draw leaves nobody at
    the parameterized gap from the reference zone, one random non-lead moves to a far
    city. Leads stay with their teams, so the guarantee never puts a lead alone abroad.
    """
    home = [rng.choice(CITIES) for _ in range(params.team_count)]
    cities: list[City] = []
    for seat in seats:
        if rng.random() < params.remote_share:
            cities.append(rng.choice([city for city in CITIES if city != home[seat.team_index]]))
        else:
            cities.append(home[seat.team_index])
    far = _far_cities(params)
    if not any(city in far for city in cities):
        movers = [index for index, seat in enumerate(seats) if not seat.lead]
        cities[rng.choice(movers)] = rng.choice(far)
    return cities


def _skills(
    rng: Random, params: OrgParams, contractors: set[int]
) -> tuple[list[tuple[SkillId, ...] | None], SkillId]:
    """A skills record per seat, ``None`` for the blank records and a sorted tuple for the rest,
    and the paired skill, which the component draw needs to seat its cast together.

    The vocabulary is shuffled into a seed-specific popularity order; the first four
    entries become the anchors (unheld, singleton, broad, paired) and the remainder the
    pool the popularity draw runs over, with a rank-based weight so a few skills are
    common and the tail is rare — the shape that makes one candidate obvious and another
    a search. The paired skill is held by exactly two employees and by a contractor (the
    cardinality class of the step 15 rulings: two viable, one failing the employment
    rule, the count visibly load-bearing), so blank records are drawn from the employee
    seats and a contractor always carries a record — a contractor is hired for a named
    skill, and the guarantee needs one to hold it.
    """
    order = rng.sample([skill.id for skill in SKILLS], len(SKILLS))
    unheld, singleton, broad, paired = order[:_ANCHOR_SKILLS]
    pool = order[_ANCHOR_SKILLS:]
    weights = [1.0 / (rank + 1) for rank in range(len(pool))]
    del unheld  # set aside on purpose: it is in the vocabulary and on nobody's record

    employee_seats = [index for index in range(params.org_size) if index not in contractors]
    blank = set(rng.sample(employee_seats, params.blank_skill_records))
    skilled = [index for index in range(params.org_size) if index not in blank]
    skilled_employees = [index for index in employee_seats if index not in blank]
    low, high = params.skills_per_person
    drawn = {
        index: _weighted_sample(rng, pool, weights, rng.randint(low, high)) for index in skilled
    }
    for index in rng.sample(skilled, math.ceil(len(skilled) * _BROAD_HOLDER_SHARE)):
        drawn[index].append(broad)
    drawn[rng.choice(skilled)].append(singleton)
    for index in rng.sample(skilled_employees, 2):
        drawn[index].append(paired)
    if contractors:
        drawn[rng.choice(sorted(contractors))].append(paired)
    records = [
        None if index in blank else tuple(sorted(drawn[index])) for index in range(params.org_size)
    ]
    return records, paired


def _components(
    rng: Random,
    params: OrgParams,
    teams: tuple[Team, ...],
    employees: tuple[Employee, ...],
    paired: SkillId,
) -> tuple[Component, ...]:
    """Components anchored on two people from two different teams, then filled from anyone —
    except that the first component holds a blank-record member and the second is exactly
    the paired skill's cast.

    The missing-information and uncovered classes differ in one placement (the step 15
    rulings): a blank-record member inside the impact's component is an unknown
    candidate, none inside makes the world complete about everyone. The cardinality class
    needs more than a blank-free component (the 15.3 ruling): the viability rule asks
    every candidate for a work item to belong to its component, so the two employees and
    the contractor holding the paired skill must sit in one component with the leaver
    and the skill-failing candidate, or the class's four verdicts are not the ones it
    authors. The second component is that cast and nothing else — the holders plus two
    recorded employees lacking the skill, five people with a contractor, four without —
    so a reader of the world spec can verify the universe of viable people by eye, and
    it holds no blank record by construction, which keeps the uncovered class's
    placement. All three are guaranteed the way the contractor is, since a component
    filled from anyone would leave each to the seed. With a single component only the
    first guarantee can hold.
    """
    by_team = {
        team.id: [employee for employee in employees if employee.team_id == team.id]
        for team in teams
    }
    blank = [employee for employee in employees if employee.skills is None]
    names = rng.sample(COMPONENT_NAMES, params.component_count)
    components: list[Component] = []
    for number, name in enumerate(names, start=1):
        if number == 2:
            members = _paired_cast(rng, employees, paired)
        else:
            size = rng.randint(*_COMPONENT_MEMBERS)
            first, second = rng.sample(teams, 2)
            anchors = [rng.choice(by_team[first.id]), rng.choice(by_team[second.id])]
            rest = [employee for employee in employees if employee not in anchors]
            members = anchors + rng.sample(rest, size - 2)
            if number == 1 and blank and not any(e.skills is None for e in members):
                # A blank-record person takes the last filler's seat.
                members[-1] = rng.choice(blank)
        components.append(
            Component(
                id=component_id(number), name=name, member_ids=tuple(sorted(e.id for e in members))
            )
        )
    return tuple(components)


def _paired_cast(rng: Random, employees: tuple[Employee, ...], paired: SkillId) -> list[Employee]:
    """The paired skill's holders and two recorded employees lacking it, spanning two teams.

    The holders were seated by the skill draw with no regard for teams, so when they share
    one team the first filler comes from another, which is what keeps the component
    crossing team lines like every other; the second filler is anyone recorded, employed
    and lacking the skill. Contractors never fill: the cast's contractor is the holder,
    and the class draws its leaver and its skill-failing candidate from the fillers.
    """
    holders = [e for e in employees if e.skills is not None and paired in e.skills]
    pool = [
        e
        for e in employees
        if e.skills is not None
        and paired not in e.skills
        and e.employment_type is EmploymentType.EMPLOYEE
    ]
    if len({holder.team_id for holder in holders}) >= 2:
        return holders + rng.sample(pool, 2)
    (team,) = {holder.team_id for holder in holders}
    outside = [e for e in pool if e.team_id != team]
    if not outside:
        raise ValueError(
            f"no recorded employee outside team {team} to seat with the paired skill's holders"
        )
    first = rng.choice(outside)
    second = rng.choice([e for e in pool if e.id != first.id])
    return holders + [first, second]


def _weighted_choice[T](rng: Random, weighted: tuple[tuple[T, int], ...]) -> T:
    return rng.choices([item for item, _ in weighted], [weight for _, weight in weighted])[0]


def _weighted_sample[T](rng: Random, items: list[T], weights: list[float], count: int) -> list[T]:
    """``count`` distinct items, each draw weighted over what remains — without replacement."""
    remaining = list(zip(items, weights, strict=True))
    chosen: list[T] = []
    for _ in range(count):
        population = [item for item, _ in remaining]
        picked = rng.choices(population, [weight for _, weight in remaining])[0]
        chosen.append(picked)
        remaining = [(item, weight) for item, weight in remaining if item != picked]
    return chosen
