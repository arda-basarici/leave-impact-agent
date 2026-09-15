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
the attempt cap, and per target the attempts, each refusal by guard with its findings
counted by reason under a closed vocabulary (never the finding itself), the rendered
request's digest, the accepted body's digest and the accepted attempt's extracted
propositions —
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


PROSE_RECORD_KINDS: frozenset[EntityKind] = frozenset({EntityKind.COMMENT, EntityKind.CLAUSE})
"""The record kinds a prose target realizes. A fact evidenced by one is established by text
alone; every other evidence record is a structured field a reader checks without reading."""


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

CLIENT_KIND = "client"
"""A client is a name and nothing more: the responsibility class's note is titled by it and
its procedure clause names that title. Every client name is a world form, so a text naming
another client is refused by the namespace scanner rather than left to the checker (the
15.2 review); a section's brief admits the one client its own document's title names."""
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


def lexical_anchors(
    fact: Fact, lexicon: Lexicon, *, first_person: EntityRef | None = None
) -> tuple[Anchor, ...]:
    """The anchors a text carrying ``fact`` must contain, one alternative group per named thing.

    Lexical only: presence proves no relation ("Deniz has never worked with Kafka" carries
    both anchors), which is the extraction check's job; absence proves the fact vanished
    in the writing, which is worth catching before a checker is paid. ``first_person``
    is the text's author when it has one — a comment's. When a required fact's subject
    is that author, the target supplies the subject's identity and the anchors are the
    fact's value-side groups only, since the author writes "I" and never their own name:
    the first measurement world refused twelve of twelve attempts on exactly that anchor
    (2026-09-14). The exemption is that narrow on purpose: a fact about anyone else keeps
    its subject anchor, and a row whose subject is a clause or the carrier never matches
    an author. The drop is positional, so every row with an employee subject puts the
    subject's group first; a row that broke that order would drop a value anchor
    unnoticed.

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
    anchors = row(fact, lexicon)
    if first_person is not None and fact.subject == first_person:
        return anchors[1:]
    return anchors


def _subject_and_entity(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    assert isinstance(fact.value, EntityRef)
    return ((lexicon.form_of(fact.subject).form,), (lexicon.form_of(fact.value).form,))


def _subject_and_skill(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    assert isinstance(fact.value, str)
    return ((lexicon.form_of(fact.subject).form,), (lexicon.skill(SkillId(fact.value)).form,))


def _named_entity(fact: Fact, lexicon: Lexicon) -> tuple[Anchor, ...]:
    """A fact whose subject is the carrier itself: the named entity is the only anchor."""
    assert isinstance(fact.value, EntityRef)
    return ((lexicon.form_of(fact.value).form,),)


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
    PredicateName.NAMES_RESPONSIBLE: _named_entity,
}

PROSE_CAPABLE: frozenset[PredicateName] = frozenset(_ANCHOR_ROWS)
"""The predicates a brief may require: exactly those with an anchor row."""


# --- The materialization record -------------------------------------------------------------


class GuardName(StrEnum):
    """The three code guards, in the order they run; the human pass is not one of them."""

    NAMESPACE = "namespace"
    REQUIRED_FACT = "required_fact"
    EXTRACTION = "extraction"


class RefusalReason(StrEnum):
    """Why a guard refused, as a closed vocabulary — the one thing about a finding the sealed
    record and the public log may carry, since a reason names no entity, value or text.

    The reasons are the guards' failure paths, never a verdict on who was at fault: an
    untyped proposition may be the checker misreading a clean text or a confused text the
    checker could not type, and only the hand audit separates the two (the measurement
    world's review, 2026-09-15). The namespace guard's three, the required-fact guard's
    one, then the containment check's seven, in the order each guard reports them.
    """

    FOREIGN_NAME = "foreign_name"
    UNLISTED_DATE = "unlisted_date"
    UNLISTED_NUMBER = "unlisted_number"
    MISSING_ANCHOR = "missing_anchor"
    UNKNOWN_SUBJECT = "unknown_subject"
    NEGATED_PROPOSITION = "negated_proposition"
    DISALLOWED_HEDGE = "disallowed_hedge"
    NOT_PERMITTED_FACT = "not_permitted_fact"
    REQUIRED_NOT_ASSERTED = "required_not_asserted"
    OTHER_CLAIM = "other_claim"
    UNTYPED_PROPOSITION = "untyped_proposition"


ReasonCount = tuple[RefusalReason, int]
"""One reason and how many of a refusal's findings gave it."""


@dataclass(frozen=True, slots=True)
class Refusal:
    """One attempt refused by one guard: which attempt, which guard, how many findings, and
    the findings counted by reason.

    Counts and never the finding itself: the record is sealed, but the same values are
    what a log line may carry, and a log is public. ``reasons`` is ``None`` on a record
    sealed before reasons were recorded (the measurement world's), which is a different
    statement from an empty count and is kept distinct; present, the counts sum to
    ``count`` and are held in reason order so the sealed bytes are canonical.
    """

    attempt: int
    guard: GuardName
    count: int
    reasons: tuple[ReasonCount, ...] | None = None

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError(f"attempts are numbered from one, got {self.attempt}")
        if self.count < 1:
            raise ValueError(f"a refusal counts at least one finding, got {self.count}")
        if self.reasons is None:
            return
        names = [reason for reason, _ in self.reasons]
        if len(set(names)) != len(names):
            raise ValueError("a refusal counts each reason once")
        if any(n < 1 for _, n in self.reasons):
            raise ValueError("a reason counts at least one finding")
        if sum(n for _, n in self.reasons) != self.count:
            raise ValueError(
                f"the reasons account for every finding: {self.count} findings, "
                f"{sum(n for _, n in self.reasons)} by reason"
            )
        object.__setattr__(self, "reasons", tuple(sorted(self.reasons, key=lambda r: r[0].value)))


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


COUNTER_NAMES: tuple[str, ...] = (
    "writer_attempts",
    "targets_first_attempt_pass",
    "targets_eventual_pass",
    "targets_cap_exhausted",
    "namespace_refusals",
    "required_fact_refusals",
    "extraction_refusals",
    "checker_retries",
    "checker_unusable",
    "writer_retries",
    "writer_input_tokens",
    "writer_output_tokens",
    "checker_input_tokens",
    "checker_output_tokens",
    "writer_latency_ms",
    "checker_latency_ms",
    "canonicalized_pairs",
)
"""Every counter the stage has sealed, in the order it seals them: append-only, so a record
sealed with fewer holds a prefix of this order. A counter the loop gains is appended here,
a test holds the loop to this list, and no decoder or encoder learns of it — a record
sealed before it was counted is missing the name, which reads back as unavailable."""


@dataclass(frozen=True, slots=True)
class MaterializationMetrics:
    """The stage's aggregate counters, sealed as provenance of the run that wrote the texts.

    Attempts and passes by target, refusals by guard, retries and unusable checkers, tokens
    in and out and the summed latency per model, and the checker's canonicalized pairs.
    Run measurements, not world semantics: the semantic digest never covers them, and a
    resume neither needs nor checks them. They are sealed because the log used to be
    their only carrier and a run that sealed its truth and then failed in projection took
    them with it (the measurement world, 2026-09-15); the ruling that adopts or rejects a
    prose fix reads these numbers, so they travel with the world they measured.

    ``counters`` are exactly the names the record was sealed with, in the declared order,
    which is what makes a decoded record encode back to its sealed bytes: a counter added
    to the stage later is absent here, and ``value`` returns ``None`` for it, unavailable
    and never zero (the review of 2026-09-15, which found the decoder had required
    today's names of every record).

    >>> counted = MaterializationMetrics((("writer_attempts", 5), ("targets_eventual_pass", 3)))
    >>> counted.value("writer_attempts"), counted.value("canonicalized_pairs")
    (5, None)
    """

    counters: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        names = [name for name, _ in self.counters]
        unknown = [name for name in names if name not in COUNTER_NAMES]
        if unknown:
            raise ValueError(f"not a counter the stage seals: {', '.join(unknown)}")
        if len(set(names)) != len(names):
            raise ValueError("a counter is sealed once")
        declared = [name for name in COUNTER_NAMES if name in names]
        if names != declared:
            raise ValueError(f"counters are sealed in the declared order, got {names}")
        for name, value in self.counters:
            if value < 0:
                raise ValueError(f"{name}: a counter is never negative, got {value}")

    def value(self, name: str) -> int | None:
        """The counter's value, or ``None`` when the record was sealed without it."""
        if name not in COUNTER_NAMES:
            raise ValueError(f"not a counter the stage seals: {name}")
        return dict(self.counters).get(name)


@dataclass(frozen=True, slots=True)
class MaterializationRecord:
    """The provenance of every model-written text in a world, sealed with the truth.

    ``prompt_digests`` name each prompt asset and its digest, held in name order so equal
    provenance is equal in bytes; the rendered per-target request is digested on its
    target's record instead, since it varies by design. ``targets`` are in the order the
    materializer ran them, which is execution provenance and not a collection: the stage
    runs targets sequentially, so the order is a fact of the run, and the realized
    identity includes it on purpose. ``metrics`` are the stage's counters, ``None`` for
    a record sealed before they were carried (the measurement world's is one), and the
    sealed bytes of such a record hold no field for them; present, they are the counters
    the run had, so a counter added to the stage later is simply absent.
    """

    writer: ModelConfiguration
    checker: ModelConfiguration
    prompt_digests: tuple[tuple[str, str], ...]
    attempt_cap: int
    targets: tuple[TargetRecord, ...]
    metrics: MaterializationMetrics | None = None

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
    "CLIENT_KIND",
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
