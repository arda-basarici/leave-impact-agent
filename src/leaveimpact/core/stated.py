"""The stated fact: what a model says a text asserts, and the three statuses it then has.

The rules read facts, and some facts live only in prose: a qualification mentioned in a
ticket comment, what a procedure's clause requires. A model's part in an investigation is
to state those, each with the words it read them from, and the rules conclude from them
(the contract step's rulings). A ``StatedFact`` is one such statement: a predicate from a
closed list of five, the subject and the value in the registry's own shapes, the comment
or the section that carries it, a verbatim quote, and for a requirement the *target span*,
the words inside the quote that name what the requirement applies to. It holds no date and
no artifact id for a requirement's scope. The model states neither: the date is the run's,
and the scope is bound from the span by the harness, once, over what the run read.

Only positive assertions exist. The type has no polarity and no mode, so a hedged or a
negated sentence has nothing to be stated as, and a model that states one anyway has made
a wrong positive extraction that can be graded as one.

What construction holds is everything that needs no read of the run: the predicate is one
of the five; the subject's kind and the value's shape are the registry row's; the carrier
is a comment or a section and its source is inside the predicate's evidence domain; a
predicate about a clause is carried by that clause; the quote is not empty; the span is
there exactly for a requirement and is a substring of the quote. A value that breaks one
of these never becomes a stated fact. ``Unstatable`` says which, by a reason code, so that
whoever parsed the model's output can keep the raw input in a ``RefusedInput``: an input
that cannot construct a fact cannot be stored as one.

Three statuses are kept apart, because each answers a different question about a model:

- *Emission*: what the model put out. A stated fact, or a refused input with its raw text
  and a reason. Never confused with nothing having been stated.
- *Admission*: whether a stated fact entered the run's view. The provenance gates and the
  anchor guard decide it over the run's reads: ``Admitted``, or ``Refused`` with a reason.
  A refusal is per emission, and a later valid emission of the same statement is admitted.
- *Placement*: for an admitted requirement, what its span bound to. ``SpanPlacement`` is
  placed on one artifact, unplaced, or ambiguous, with the read artifacts that decided it.
  A correctly extracted requirement can be admitted and unplaced, and a wrong binding is
  not an invention.

The gates and the binding themselves are functions over a run's reads, each in its own
module here (``admission``, ``binding``, and ``scoping`` for what several placements of one
clause come to), since a harness runs them and the evaluator reruns them and the two may
not import each other; this module is the vocabulary they speak.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.core.enums import EntityKind, Source, require_member
from leaveimpact.core.facts import Fact, Statement
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND, EntityRef, EvidenceRef, with_article
from leaveimpact.core.values import FactValue

STATED_PREDICATES: tuple[PredicateName, ...] = (
    PredicateName.HAS_SKILL,
    PredicateName.MEMBER_OF_COMPONENT,
    PredicateName.OWNS_WORK_ITEM,
    PredicateName.REQUIRES,
    PredicateName.NAMES_RESPONSIBLE,
)
"""The predicates a model may state, closed: the ones the generator can require of prose. A
model-stated leave or reporting line would assert what a structured record owns."""

CARRIER_KINDS: frozenset[EntityKind] = frozenset({EntityKind.COMMENT, EntityKind.CLAUSE})
"""The kinds of record that carry prose: a ticket's comment and a document's section."""

TITLED_KINDS: frozenset[EntityKind] = frozenset(
    {EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.DOCUMENT}
)
"""The kinds of artifact prose names by title, and so the only ones a span can bind to."""


class FactRefusal(StrEnum):
    """Why a statement was refused, at construction or at admission; a member is the wire
    format, and refusals are counted by it."""

    UNDECODABLE = "undecodable"
    """The input has no reading as a statement: a missing field, a malformed id or value, a
    subject or a carrier of a kind the predicate does not take."""
    MALFORMED_CARRIER = "malformed_carrier"
    """The carrier is not a comment or a section."""
    SPAN_NOT_IN_QUOTE = "span_not_in_quote"
    """A requirement's target span is missing, or is not a substring of its quote."""
    CARRIER_NOT_READ = "carrier_not_read"
    """No operation of the run returned the carrier."""
    QUOTE_NOT_IN_CARRIER = "quote_not_in_carrier"
    """The quote is not an exact substring of the carrier's text as read."""
    SUBJECT_NOT_READ = "subject_not_read"
    """The run read no record of the entity the statement is about."""
    VALUE_NOT_READ = "value_not_read"
    """The statement's value names an entity or a skill the run has no form for."""
    MISSING_ANCHOR = "missing_anchor"
    """The quote does not name what the statement says it is about."""


CONSTRUCTION_REFUSALS: frozenset[FactRefusal] = frozenset(
    {FactRefusal.UNDECODABLE, FactRefusal.MALFORMED_CARRIER, FactRefusal.SPAN_NOT_IN_QUOTE}
)
"""The reasons a value never becomes a stated fact. Every other reason is an admission's: it
needs the run's reads."""


class Unstatable(ValueError):
    """A value that cannot be a stated fact, with the reason it is counted under."""

    def __init__(self, reason: FactRefusal, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def _unstatable(detail: str) -> Unstatable:
    return Unstatable(FactRefusal.UNDECODABLE, detail)


@dataclass(frozen=True, slots=True)
class StatedFact:
    """One statement a model made about a text: what it says, where, and in which words.

    >>> from leaveimpact.core.ids import comment_id, employee_id
    >>> from leaveimpact.core.refs import comment_ref, employee_ref
    >>> stated = StatedFact(PredicateName.HAS_SKILL, employee_ref(employee_id(23)), "kafka",
    ...                     comment_ref(comment_id(5)), "I ran the Kafka migration")
    >>> stated.source
    <Source.JIRA: 'jira'>
    >>> StatedFact(PredicateName.ON_LEAVE, employee_ref(employee_id(23)), "kafka",
    ...            comment_ref(comment_id(5)), "out next week")
    Traceback (most recent call last):
    ...
    leaveimpact.core.stated.Unstatable: on_leave is not a predicate a model states
    """

    predicate: PredicateName
    subject: EntityRef
    value: FactValue
    carrier: EntityRef
    quote: str
    target_span: str | None = None
    """For ``requires`` only: the title of what the requirement applies to, as the quote
    writes it. The one source of the requirement's scope."""

    def __post_init__(self) -> None:
        # Whoever parses a model's entry builds this type from untrusted values, so a wrong
        # Python type is refused under a reason like any other unreadable input, and never
        # surfaces as an AttributeError three lines further down.
        if type(self.predicate) is not PredicateName:
            raise _unstatable(f"a predicate is a member of PredicateName, got {self.predicate!r}")
        for what, ref in (("subject", self.subject), ("carrier", self.carrier)):
            if type(ref) is not EntityRef:
                raise _unstatable(f"a stated fact's {what} is an entity reference, got {ref!r}")
        if type(self.quote) is not str:
            raise _unstatable(f"a quote is text, got {type(self.quote).__name__}")
        if self.target_span is not None and type(self.target_span) is not str:
            raise _unstatable(f"a target span is text, got {type(self.target_span).__name__}")
        if self.predicate not in STATED_PREDICATES:
            raise _unstatable(f"{self.predicate.value} is not a predicate a model states")
        row = predicate(self.predicate)
        if self.subject.kind is not row.subject:
            raise _unstatable(
                f"{row.name.value} is a fact about {with_article(row.subject.value)}, "
                f"got {with_article(self.subject.kind.value)}"
            )
        try:
            row.value_spec.check(self.value)
        except ValueError as problem:
            raise _unstatable(f"{row.name.value}: {problem}") from None
        if self.carrier.kind not in CARRIER_KINDS:
            raise Unstatable(
                FactRefusal.MALFORMED_CARRIER,
                f"a carrier is a comment or a section, got {with_article(self.carrier.kind.value)}",
            )
        if self.source not in row.evidence_domain:
            raise _unstatable(
                f"{with_article(self.carrier.kind.value)} cannot carry {row.name.value}: "
                f"{self.source.value} is outside its evidence domain"
            )
        if row.subject is EntityKind.CLAUSE and self.subject != self.carrier:
            raise _unstatable(
                f"{row.name.value} is stated by the section it is about: the subject "
                f"{self.subject.id} is not the carrier {self.carrier.id}"
            )
        if not self.quote:
            raise _unstatable("a stated fact quotes the words it was read from")
        if self.predicate is PredicateName.REQUIRES:
            if not self.target_span or self.target_span not in self.quote:
                raise Unstatable(
                    FactRefusal.SPAN_NOT_IN_QUOTE,
                    "a requirement's target span is a substring of its quote",
                )
        elif self.target_span is not None:
            raise _unstatable(f"{row.name.value} has no target span; only a requirement has one")

    @property
    def source(self) -> Source:
        """The source the statement was read from: its carrier's."""
        return SOURCE_BY_TARGET_KIND[self.carrier.kind]

    @property
    def statement(self) -> Statement:
        """What is stated, without where: subject, predicate, value."""
        return (self.subject, self.predicate, self.value)

    def as_fact(self, today: date) -> Fact:
        """The statement as a fact of a run's view, read from its carrier, dated to the run's
        day like every fact a run derives (the contract step's ruling on a stated fact's
        date). The fact base cannot refuse the fact alone: construction already holds what
        a fact checks."""
        return Fact(
            self.subject,
            self.predicate,
            self.value,
            EvidenceRef(self.source, self.carrier),
            today,
        )


# --- Emission -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefusedInput:
    """One entry of a model's output that could not construct a stated fact.

    ``raw`` is the entry as canonical JSON text, kept whole so the classification can be
    checked from the export and never stored as the typed fact that refused it.
    """

    raw: str
    reason: FactRefusal
    detail: str

    def __post_init__(self) -> None:
        require_member(self.reason, FactRefusal, "a refused input's reason")
        if self.reason not in CONSTRUCTION_REFUSALS:
            raise ValueError(
                f"{self.reason.value} refuses a stated fact at admission, never an input"
            )


Emission = StatedFact | RefusedInput
"""What a model put out for one entry: a statement, or an input no statement could be made of."""


# --- Admission ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Admitted:
    """A stated fact that passed the gates and entered the run's view."""

    fact: StatedFact


@dataclass(frozen=True, slots=True)
class Refused:
    """A stated fact a gate refused, with the reason it is counted under. The fact stays whole:
    what the model read and what the guard made of it are exported side by side."""

    fact: StatedFact
    reason: FactRefusal
    detail: str

    def __post_init__(self) -> None:
        require_member(self.reason, FactRefusal, "a refusal's reason")
        if self.reason in CONSTRUCTION_REFUSALS:
            raise ValueError(f"{self.reason.value} is a reason no stated fact can exist under")


Admission = Admitted | Refused
"""Whether one stated fact entered the view."""


# --- Placement ------------------------------------------------------------------------------


class PlacementState(StrEnum):
    """What a requirement's target span bound to; a member is the wire format."""

    PLACED = "placed"
    UNPLACED = "unplaced"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class SpanPlacement:
    """The binding of one requirement's span over what the run read.

    Placed: ``artifact`` is the one read artifact whose title equals the span. Unplaced: no
    read title equals it, and nothing is named. Ambiguous: ``among`` holds the read
    artifacts that kept it from binding, the several with an equal title or the ones whose
    longer title contains the span and stands in the carrier's text. Only a placed
    requirement composes a constraint; the other two are shown as diagnostics.

    >>> SpanPlacement(PlacementState.UNPLACED)
    SpanPlacement(state=<PlacementState.UNPLACED: 'unplaced'>, artifact=None, among=())
    """

    state: PlacementState
    artifact: EntityRef | None = None
    among: tuple[EntityRef, ...] = ()

    def __post_init__(self) -> None:
        require_member(self.state, PlacementState, "a placement's state")
        match self.state:
            case PlacementState.PLACED:
                if self.artifact is None or self.among:
                    raise ValueError("a placed span names its one artifact and nothing else")
            case PlacementState.UNPLACED:
                if self.artifact is not None or self.among:
                    raise ValueError("an unplaced span names no artifact")
            case PlacementState.AMBIGUOUS:
                if self.artifact is not None or not self.among:
                    raise ValueError(
                        "an ambiguous span binds nothing and names the artifacts it lay among"
                    )
        if len(set(self.among)) != len(self.among):
            raise ValueError("an ambiguous span names each artifact once")
        for named in (*self.among, *(() if self.artifact is None else (self.artifact,))):
            if named.kind not in TITLED_KINDS:
                raise ValueError(
                    "a span binds a ticket, a meeting or a document, got "
                    f"{with_article(named.kind.value)}"
                )


__all__ = [
    "CARRIER_KINDS",
    "CONSTRUCTION_REFUSALS",
    "STATED_PREDICATES",
    "TITLED_KINDS",
    "Admission",
    "Admitted",
    "Emission",
    "FactRefusal",
    "SpanPlacement",
    "PlacementState",
    "Refused",
    "RefusedInput",
    "StatedFact",
    "Unstatable",
]
