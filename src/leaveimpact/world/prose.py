"""The prose vocabulary of the benchmark: what a text may claim, what a brief may name, and the
record of how a model's text was accepted.

Materialized prose is gated by semantic containment — every required planted fact present,
no benchmark-relevant fact added — and this module holds the pure types the gate and its
record are stated in (the step 14 rulings in DESIGN, "Materialization"). A *proposition* is
what an independent checker reads out of a text: a subject, a predicate from the registry,
a value of the predicate's declared shape, its polarity and its assertion mode. Polarity and
mode are properties of the text, never of the checker's confidence: "Deniz might know Kafka"
is affirmed and hedged whatever the checker believes, and the gate refuses it because a
hedged planted fact is a weakened one. A proposition whose subject the checker could not
resolve to a world entity carries no subject at all; it is an invented person until proven
otherwise, and the gate refuses it too.

The *namespace* is the finite set of surface forms a text may use — the display names of the
entities its brief's facts mention, the dates and the numbers those facts carry — derived
from the facts through the closed vocabulary rather than authored by a scenario class, so a
class cannot forget a name or leak one. The *lexical anchors* are the cheap presence check a
required fact affords before a checker is paid: per predicate, the surface forms a text
stating that fact cannot avoid. The registry stays the authority on what a predicate is;
this table is the world's authority on how one of its facts can surface, which is why it
lives here and not in ``core``. A predicate with no row here cannot be carried by prose, and
a brief that requires one is refused at construction rather than at the first live run.

The *materialization record* is the provenance of every accepted text: the writer and the
checker with their inference settings serialized whole, the digests of the prompt assets,
the attempt cap, and per target the attempts, each refusal by guard, the rendered request's
digest, the accepted body's digest and the accepted attempt's extracted propositions —
which the hand audit of the first golden set is measured against. It carries what truth
expects of the prose, so it seals beside the keys in the evaluator-only truth manifest, and
the types are ``world``'s because that file is. Rejected text is nowhere in it on purpose: a
discarded artifact needs nothing, and a public job log is not a place for one.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from re import fullmatch

from leaveimpact.core.enums import EmploymentType, EntityKind
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import SkillId, skill_id
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import (
    EmploymentTypeCriterion,
    FactValue,
    Requirement,
    SkillCriterion,
    ValueKind,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan

# --- Propositions -------------------------------------------------------------------------


class Polarity(StrEnum):
    """Whether the text affirms the proposition or denies it."""

    AFFIRMED = "affirmed"
    NEGATED = "negated"


class AssertionMode(StrEnum):
    """The text's modality: stated as a fact, or hedged ("might", "probably", "some")."""

    ASSERTED = "asserted"
    HEDGED = "hedged"


@dataclass(frozen=True, slots=True)
class Proposition:
    """One claim a text makes, in the registry's terms, with the text's polarity and modality.

    ``subject`` is ``None`` when the checker could not resolve the text's subject to an
    entity of the world — the shape an invented person takes. The value is checked
    against the predicate's spec here, the way a fact's is, so a malformed value from a
    checker is refused where it is built and never compared.

    >>> from leaveimpact.core.ids import employee_id
    >>> from leaveimpact.core.refs import employee_ref
    >>> Proposition(employee_ref(employee_id(23)), PredicateName.HAS_SKILL, "Kafka",
    ...             Polarity.AFFIRMED, AssertionMode.ASSERTED)
    Traceback (most recent call last):
    ...
    ValueError: has_skill: expected a skill, got 'Kafka': a skill id is a lower-case vocabulary key
    """

    subject: EntityRef | None
    predicate: PredicateName
    value: FactValue
    polarity: Polarity
    assertion_mode: AssertionMode

    def __post_init__(self) -> None:
        row = predicate(self.predicate)
        if self.subject is not None and self.subject.kind is not row.subject:
            raise ValueError(
                f"{row.name.value} is a fact about {row.subject.value}, got a proposition "
                f"about {self.subject.kind.value}"
            )
        try:
            row.value_spec.check(self.value)
        except ValueError as problem:
            raise ValueError(f"{row.name.value}: {problem}") from None

    @property
    def statement(self) -> Statement | None:
        """What the proposition says, without polarity or mode; ``None`` for an unknown subject."""
        if self.subject is None:
            return None
        return (self.subject, self.predicate, self.value)


Statement = tuple[EntityRef, PredicateName, FactValue]
"""The comparable content of a fact or a proposition: subject, predicate, value."""


def statement_of(fact: Fact) -> Statement:
    """``fact`` as the statement containment compares — evidence and date deliberately dropped."""
    return (fact.subject, fact.predicate, fact.value)


# --- Roles and surface forms ----------------------------------------------------------------


class FactRole(StrEnum):
    """Whether a required fact changes the scenario's answer or only colours its text.

    Derived, never tagged: the rules run once with the fact removed from the base, and a
    changed verdict, reason, open question or outcome makes it answer-changing. The hand
    audit reads every artifact carrying one.
    """

    ANSWER_CHANGING = "answer_changing"
    CONTEXT = "context"


@dataclass(frozen=True, slots=True)
class SurfaceForm:
    """One thing a text may name and the spelling it names it by: a person, a skill, a title."""

    kind: str
    id: str
    form: str

    def __post_init__(self) -> None:
        if not self.form.strip():
            raise ValueError(f"a surface form for {self.kind} {self.id} is not blank")


@dataclass(frozen=True, slots=True)
class Namespace:
    """The finite set of surface forms, dates and numbers a text under one brief may use.

    Derived from the brief's facts by ``derive_namespace``; the guard that scans a text
    against it needs a closed set, and a closed set derived from facts is one a class author
    cannot get wrong. Forms are unique per (kind, id); dates and numbers are sorted sets.
    """

    forms: tuple[SurfaceForm, ...]
    dates: tuple[date, ...]
    numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        keys = [(form.kind, form.id) for form in self.forms]
        if len(set(keys)) != len(keys):
            raise ValueError(f"a namespace names each entity once, got {keys}")
        if list(self.dates) != sorted(set(self.dates)):
            raise ValueError(f"a namespace's dates are sorted and unique, got {self.dates}")
        if list(self.numbers) != sorted(set(self.numbers)):
            raise ValueError(f"a namespace's numbers are sorted and unique, got {self.numbers}")

    def form_of(self, kind: str, id: str) -> str:
        """The spelling of one named thing; a thing outside the namespace is a ``ValueError``."""
        for form in self.forms:
            if (form.kind, form.id) == (kind, id):
                return form.form
        raise ValueError(f"{kind} {id} is outside the namespace")


SKILL_KIND = "skill"
"""The surface-form kind of a skill, which is a vocabulary term and not an entity."""

GIVEN_NAME_KIND = "given_name"
"""The surface-form kind of an employee's given name alone, keyed by the employee's id: a text
names a colleague by first name, and a guard that knew only full names would not see it."""

CARRIER_KINDS: frozenset[EntityKind] = frozenset({EntityKind.COMMENT, EntityKind.CLAUSE})
"""The kinds of thing prose is written into; they have no display form and name nothing."""


class Lexicon:
    """Every display form a world affords, by kind and id — what a namespace is derived through.

    Built by the world from its organization and plantings (``briefs.lexicon_of``); held
    here as the pure lookup the anchors and the namespace derivation read.
    """

    def __init__(self, forms: Iterable[SurfaceForm]) -> None:
        self._forms: dict[tuple[str, str], str] = {}
        for form in forms:
            key = (form.kind, form.id)
            if key in self._forms and self._forms[key] != form.form:
                raise ValueError(f"{form.kind} {form.id} has two display forms")
            self._forms[key] = form.form

    def forms(self) -> tuple[SurfaceForm, ...]:
        """Every form held, in (kind, id) order — the scanner's list of what a world can name."""
        return tuple(
            SurfaceForm(kind, id, form) for (kind, id), form in sorted(self._forms.items())
        )

    def form_of(self, ref: EntityRef) -> SurfaceForm:
        return self._surface(ref.kind.value, ref.id)

    def alias(self, kind: str, id: str) -> SurfaceForm | None:
        """The form of ``kind`` for ``id`` when the world has one (a given name); else ``None``."""
        form = self._forms.get((kind, id))
        return None if form is None else SurfaceForm(kind, id, form)

    def skill(self, skill: SkillId) -> SurfaceForm:
        return self._surface(SKILL_KIND, skill_id(skill))

    def _surface(self, kind: str, id: str) -> SurfaceForm:
        try:
            return SurfaceForm(kind, id, self._forms[(kind, id)])
        except KeyError:
            raise ValueError(f"{kind} {id} has no display form in this world") from None


def derive_namespace(
    facts: Iterable[Fact], lexicon: Lexicon, extra: Iterable[SurfaceForm] = ()
) -> Namespace:
    """The namespace texts stating ``facts`` may use: every named thing, date and number in them.

    ``extra`` adds forms the target itself affords — its parent's title, its author — which
    no fact mentions and a text naturally does.
    """
    forms: dict[tuple[str, str], SurfaceForm] = {}
    dates: set[date] = set()
    numbers: set[int] = set()

    def add(form: SurfaceForm) -> None:
        forms.setdefault((form.kind, form.id), form)
        if form.kind == EntityKind.EMPLOYEE.value:
            given = lexicon.alias(GIVEN_NAME_KIND, form.id)
            if given is not None:
                forms.setdefault((given.kind, given.id), given)

    for form in extra:
        add(form)
    for fact in facts:
        # A clause or a comment as subject is the carrier itself, which a text never names.
        if fact.subject.kind not in CARRIER_KINDS:
            add(lexicon.form_of(fact.subject))
        _collect(fact, lexicon, add, dates, numbers)
    ordered = sorted(forms.values(), key=lambda form: (form.kind, form.id))
    return Namespace(tuple(ordered), tuple(sorted(dates)), tuple(sorted(numbers)))


def _collect(
    fact: Fact,
    lexicon: Lexicon,
    add: Callable[[SurfaceForm], None],
    dates: set[date],
    numbers: set[int],
) -> None:
    """Every surface form, date and number ``fact``'s value exposes, by its declared kind.

    The kind comes from the registry row and not from the Python type: a skill and an
    enum member are both strings, and only the skill has a display form.
    """
    value = fact.value
    match predicate(fact.predicate).value_spec.kind:
        case ValueKind.ENTITY_REF:
            assert isinstance(value, EntityRef)
            add(lexicon.form_of(value))
        case ValueKind.SKILL:
            assert isinstance(value, str)
            add(lexicon.skill(SkillId(value)))
        case ValueKind.REQUIREMENT:
            assert isinstance(value, Requirement)
            numbers.add(value.count)
            for criterion in value.criteria:
                if isinstance(criterion, SkillCriterion):
                    add(lexicon.skill(criterion.skill))
        case ValueKind.DATE:
            assert isinstance(value, date)
            dates.add(value)
        case ValueKind.DATE_SPAN:
            assert isinstance(value, DateSpan)
            dates.update((value.start, value.end))
        case ValueKind.INSTANT_SPAN:
            assert isinstance(value, InstantSpan)
            dates.update((value.start.date(), value.end.date()))
        case ValueKind.TEXT | ValueKind.ENUM:
            pass


# --- Lexical anchors ------------------------------------------------------------------------

Anchor = tuple[str, ...]
"""One thing a text stating a fact cannot avoid, as its alternative spellings; one must appear."""

NUMBER_WORDS: Mapping[int, str] = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}
"""A count may be written as a digit or a word; a text is not refused for choosing either."""

EMPLOYMENT_FORMS: Mapping[EmploymentType, Anchor] = {
    EmploymentType.EMPLOYEE: ("employee", "employees"),
    EmploymentType.CONTRACTOR: ("contractor", "contractors"),
}


def lexical_anchors(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    """The anchors a text carrying ``fact`` must contain, one alternative group per named thing.

    Lexical only: presence proves no relation ("Deniz has never worked with Kafka" carries
    both anchors), which is the extraction check's job; absence proves the fact vanished
    in the writing, which is worth catching before a checker is paid.

    >>> from datetime import date
    >>> from leaveimpact.core.enums import Source
    >>> from leaveimpact.core.ids import comment_id, employee_id
    >>> from leaveimpact.core.refs import EvidenceRef, comment_ref, employee_ref
    >>> deniz = employee_ref(employee_id(23))
    >>> lexicon = Lexicon([SurfaceForm("employee", "emp_023", "Deniz Kaya"),
    ...                    SurfaceForm(SKILL_KIND, "kafka", "Kafka")])
    >>> fact = Fact(deniz, PredicateName.HAS_SKILL, "kafka",
    ...             EvidenceRef(Source.JIRA, comment_ref(comment_id(5))), date(2026, 3, 1))
    >>> lexical_anchors(fact, lexicon)
    (('Deniz Kaya',), ('Kafka',))
    """
    row = _ANCHOR_ROWS.get(fact.predicate)
    if row is None:
        raise ValueError(f"{fact.predicate.value} cannot be carried by prose: no anchor row")
    return row(fact, lexicon)


def _subject_and_entity(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    assert isinstance(fact.value, EntityRef)
    return ((lexicon.form_of(fact.subject).form,), (lexicon.form_of(fact.value).form,))


def _subject_and_skill(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    assert isinstance(fact.value, str)
    return ((lexicon.form_of(fact.subject).form,), (lexicon.skill(SkillId(fact.value)).form,))


def _requirement(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    """A clause's requirement: its count in either spelling and every criterion's form."""
    assert isinstance(fact.value, Requirement)
    count = fact.value.count
    spellings = (str(count), NUMBER_WORDS[count]) if count in NUMBER_WORDS else (str(count),)
    anchors: list[Anchor] = [spellings]
    for criterion in fact.value.criteria:
        match criterion:
            case SkillCriterion():
                anchors.append((lexicon.skill(criterion.skill).form,))
            case EmploymentTypeCriterion():
                anchors.append(EMPLOYMENT_FORMS[criterion.employment_type])
    return tuple(anchors)


_ANCHOR_ROWS: Mapping[PredicateName, Callable[[Fact, Lexicon], tuple[Anchor, ...]]] = {
    PredicateName.HAS_SKILL: _subject_and_skill,
    PredicateName.MEMBER_OF_COMPONENT: _subject_and_entity,
    PredicateName.OWNS_WORK_ITEM: _subject_and_entity,
    PredicateName.REQUIRES: _requirement,
}

PROSE_CAPABLE: frozenset[PredicateName] = frozenset(_ANCHOR_ROWS)
"""The predicates a brief may require: exactly those with an anchor row."""


# --- The materialization record -------------------------------------------------------------


class GuardName(StrEnum):
    """The three code guards, in the order they run; the human pass is not one of them."""

    NAMESPACE = "namespace"
    REQUIRED_FACT = "required_fact"
    EXTRACTION = "extraction"


@dataclass(frozen=True, slots=True)
class Refusal:
    """One attempt refused by one guard: which attempt, which guard, how many findings.

    A count and never the finding itself: the record is sealed, but the same value is
    what a log line may carry, and a log is public.
    """

    attempt: int
    guard: GuardName
    count: int

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError(f"attempts are numbered from one, got {self.attempt}")
        if self.count < 1:
            raise ValueError(f"a refusal counts at least one finding, got {self.count}")


@dataclass(frozen=True, slots=True)
class Setting:
    """One inference parameter by name, as the model was called with it."""

    name: str
    value: int | float | str


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    """A model and every explicit inference setting it ran under, settings in name order.

    Serialized whole so a parameter added later joins the record unasked (the step 14
    ruling on provenance); ordered here so equal configurations are equal in bytes.
    """

    model_id: str
    settings: tuple[Setting, ...]

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("a model configuration names its model")
        names = [setting.name for setting in self.settings]
        if len(set(names)) != len(names):
            raise ValueError(f"a setting is given once, got {names}")
        object.__setattr__(self, "settings", tuple(sorted(self.settings, key=lambda s: s.name)))


SHA256_HEX = r"[0-9a-f]{64}"


@dataclass(frozen=True, slots=True)
class TargetRecord:
    """How one target's text was accepted: the attempts, the refusals, the digests, the reading.

    ``attempts`` counts every attempt including the accepted last one, and the refusals
    are a possible history: exactly one for each attempt before it, in order, since the
    first guard that refuses ends an attempt (a namespace refusal means the checker never
    ran on that draft). ``request_digest`` is of the rendered model request and
    ``accepted_body_digest`` of the body the model wrote — the composed text, prefix and
    all, has its own place in the world's digests. ``propositions`` are the checker's
    reading of the accepted body, kept because the hand audit is measured against them.
    """

    target_id: str
    attempts: int
    refusals: tuple[Refusal, ...]
    request_digest: str
    accepted_body_digest: str
    propositions: tuple[Proposition, ...]

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError(f"{self.target_id}: an accepted target took at least one attempt")
        refused = [refusal.attempt for refusal in self.refusals]
        if refused != list(range(1, self.attempts)):
            raise ValueError(
                f"{self.target_id}: accepted on attempt {self.attempts}, so attempts "
                f"1..{self.attempts - 1} were each refused once in order, got refusals on "
                f"{refused}"
            )
        for name, value in (
            ("request_digest", self.request_digest),
            ("accepted_body_digest", self.accepted_body_digest),
        ):
            if not fullmatch(SHA256_HEX, value):
                raise ValueError(f"{self.target_id}: {name} is a SHA-256 hex, got {value!r}")


@dataclass(frozen=True, slots=True)
class MaterializationRecord:
    """The provenance of every model-written text in a world, sealed with the truth.

    ``prompt_digests`` name each prompt asset and its digest, held in name order so equal
    provenance is equal in bytes; the rendered per-target request is digested on its
    target's record instead, since it varies by design. ``targets`` are in the order the
    materializer ran them, which is execution provenance and not a collection: the stage
    runs targets sequentially, so the order is a fact of the run, and the realized
    identity includes it on purpose.
    """

    writer: ModelConfiguration
    checker: ModelConfiguration
    prompt_digests: tuple[tuple[str, str], ...]
    attempt_cap: int
    targets: tuple[TargetRecord, ...]

    def __post_init__(self) -> None:
        if self.attempt_cap < 1:
            raise ValueError(f"the attempt cap is at least one, got {self.attempt_cap}")
        names = [name for name, _ in self.prompt_digests]
        if len(set(names)) != len(names):
            raise ValueError(f"a prompt asset is digested once, got {names}")
        object.__setattr__(self, "prompt_digests", tuple(sorted(self.prompt_digests)))
        for name, value in self.prompt_digests:
            if not fullmatch(SHA256_HEX, value):
                raise ValueError(f"prompt {name}: a SHA-256 hex, got {value!r}")
        ids = [target.target_id for target in self.targets]
        if len(set(ids)) != len(ids):
            raise ValueError(f"a target is recorded once, got {ids}")
        for target in self.targets:
            if target.attempts > self.attempt_cap:
                raise ValueError(
                    f"{target.target_id}: {target.attempts} attempts over a cap of "
                    f"{self.attempt_cap}"
                )

    @property
    def target_ids(self) -> frozenset[str]:
        return frozenset(target.target_id for target in self.targets)


__all__ = [
    "EMPLOYMENT_FORMS",
    "GIVEN_NAME_KIND",
    "NUMBER_WORDS",
    "PROSE_CAPABLE",
    "SKILL_KIND",
    "Anchor",
    "AssertionMode",
    "FactRole",
    "GuardName",
    "Lexicon",
    "MaterializationRecord",
    "ModelConfiguration",
    "Namespace",
    "Polarity",
    "Proposition",
    "Refusal",
    "Setting",
    "Statement",
    "SurfaceForm",
    "TargetRecord",
    "derive_namespace",
    "lexical_anchors",
    "statement_of",
]
