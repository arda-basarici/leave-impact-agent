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
from dataclasses import dataclass
from random import Random

from leaveimpact.core.entities import Component, Employee, Team
from leaveimpact.core.enums import EmploymentType, Grade
from leaveimpact.core.ids import (
    EmployeeId,
    SkillId,
    TeamId,
    component_id,
    employee_id,
    team_id,
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
_ANCHOR_SKILLS = 3
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
        if not 0 <= self.blank_skill_records <= self.org_size - 2:
            raise ValueError(
                "blank_skill_records must leave at least two people with a skills record, "
                f"got {self.blank_skill_records} of {self.org_size}"
            )
        low, high = self.skills_per_person
        if not 1 <= low <= high <= len(SKILLS) - _ANCHOR_SKILLS:
            raise ValueError(
                "skills_per_person must satisfy 1 <= low <= high <= "
                f"{len(SKILLS) - _ANCHOR_SKILLS} (the vocabulary minus the three anchors), "
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
    ``blank_skill_records`` people with ``skills`` absent; among the vocabulary at least
    one skill with no holder, one with exactly one, one held by at least a third of the
    people with a record; every component's members drawn from at least two teams.

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
    skills = _skills(rng, params)
    contractors = _contractors(rng, seats, params)

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
        components=_components(rng, params, teams, tuple(employees)),
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
    then nothing is guaranteed: the parameter stays honest.
    """
    candidates = [index for index, seat in enumerate(seats) if not seat.lead]
    if params.contractor_share == 0.0:
        return set()
    contractors = {index for index in candidates if rng.random() < params.contractor_share}
    contractors.add(rng.choice(candidates))
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


def _skills(rng: Random, params: OrgParams) -> list[tuple[SkillId, ...] | None]:
    """A skills record per seat: ``None`` for the blank records, a sorted tuple for the rest.

    The vocabulary is shuffled into a seed-specific popularity order; the first three
    entries become the anchors (unheld, singleton, broad) and the remainder the pool the
    popularity draw runs over, with a rank-based weight so a few skills are common and
    the tail is rare — the shape that makes one candidate obvious and another a search.
    """
    order = rng.sample([skill.id for skill in SKILLS], len(SKILLS))
    unheld, singleton, broad = order[:_ANCHOR_SKILLS]
    pool = order[_ANCHOR_SKILLS:]
    weights = [1.0 / (rank + 1) for rank in range(len(pool))]
    del unheld  # set aside on purpose: it is in the vocabulary and on nobody's record

    blank = set(rng.sample(range(params.org_size), params.blank_skill_records))
    skilled = [index for index in range(params.org_size) if index not in blank]
    low, high = params.skills_per_person
    drawn = {
        index: _weighted_sample(rng, pool, weights, rng.randint(low, high)) for index in skilled
    }
    for index in rng.sample(skilled, math.ceil(len(skilled) * _BROAD_HOLDER_SHARE)):
        drawn[index].append(broad)
    drawn[rng.choice(skilled)].append(singleton)
    return [
        None if index in blank else tuple(sorted(drawn[index])) for index in range(params.org_size)
    ]


def _components(
    rng: Random, params: OrgParams, teams: tuple[Team, ...], employees: tuple[Employee, ...]
) -> tuple[Component, ...]:
    """Components anchored on two people from two different teams, then filled from anyone."""
    by_team = {
        team.id: [employee for employee in employees if employee.team_id == team.id]
        for team in teams
    }
    names = rng.sample(COMPONENT_NAMES, params.component_count)
    components: list[Component] = []
    for number, name in enumerate(names, start=1):
        first, second = rng.sample(teams, 2)
        anchors = [rng.choice(by_team[first.id]), rng.choice(by_team[second.id])]
        size = rng.randint(*_COMPONENT_MEMBERS)
        rest = [employee for employee in employees if employee not in anchors]
        members: list[EmployeeId] = [e.id for e in anchors + rng.sample(rest, size - 2)]
        components.append(
            Component(id=component_id(number), name=name, member_ids=tuple(sorted(members)))
        )
    return tuple(components)


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
