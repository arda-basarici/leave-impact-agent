"""Closed-world evaluation per declared evidence domain: known true, known false, or unknown with
the reason.

Zero facts mean false only after the evidence domain has been fully observed, and a
gap blocks that inference. That sentence is the whole rule (DESIGN, "The rules in
code"); the order below is its operational form, read over a ``FactView`` that already
holds only what this run can see:

1. a positive fact → known true, carrying the facts that established it, because the
   assessment's evidence references are built from them;
2. a slice the negative needs could not be read → unknown, *inaccessible*;
3. a slice the negative needs was not read, or no read observes it whole and the
   placement does not waive it → unknown, *insufficient*;
4. a gap → unknown, *absent*;
5. an open domain → unknown, *insufficient*;
6. otherwise → known false.

Fully observed is asked of the view's coverage, slice by slice (the coverage module):
the question names where its answer lives, one slice per source of the predicate's
declared domain, and the view says whether each was observed whole. Reachability alone
is not that. Over a base cut by a run condition the two coincide, a slice being covered
exactly when its source is reachable, so step 3 never fires there and the order is the
one the truth has always been read by. Over what a run read they part: the source
answered, and the record that would have settled the question was never asked for. An
unread record is not a negative (the investigator milestone's fourth build step,
ruling 2).

The precedence inside "unknown" runs inaccessible > unread > absent > open, because the
outermost cause of an incomplete observation set wins: a blank HR field with the
tracker unreachable reports inaccessible, since a reachable tracker could have made the
fact known true; the same field with the tracker never asked reports insufficient, for
the same reason; and absent shows only when every slice was observed. Closure derives
these three reasons and no other; ``ambiguous`` and ``conflicting`` are the agent's to
emit, never the rule's, and the result type says so in its signature rather than in a
second enum.

A single-valued predicate is read through the authority table (the step 15 rulings in
DESIGN, "The stale conflict sits on a real impact, and reads resolve"). The raw base
keeps every source's value, since the conflict derivation needs them all; a read
resolves them first, so a rule sees the system of record's value and the facts that
agree with it, and a lower-authority fact never answers "known true" for a value the
record contradicts. When the record's own slice was not observed, a positive fact from
another source is not promoted to truth: the answer is unknown, ahead of the
positive-fact step, *inaccessible* when the record could not be read and *insufficient*
when it was not, so an unread tracker never lets a runbook's owner stand. Multi-valued
predicates keep the plain order — a skill evidenced in a comment is evidence whether or
not the HR record answered — which is what the fragmented tier relies on. The record
observed and silent while another source holds a value is known true: answered is the
line, not answered positively.

Two entry points share the rule. ``establish`` asks about one subject — "does this
employee hold this skill" — and gaps apply. ``establish_any`` asks a subject-free
question over every visible fact of a predicate — "is this employee on leave over
these days" — keyed to the entity the question is about so an unresolved answer still
names a subject for the unknown claim; gaps are subject-bound and no planted class
puts one on an event's schedule or attendance, so they do not apply there. The caller
states the question's scope, a window or ``None`` for every record there is, because
the matcher hides it and the negative is only as wide as what was observed: one event
read by its id settles nothing about the other events of that hour.

Every answer carries its *proof*: the witnesses it rests on. A witness is a fact, a gap,
or a slice the answer asked the view about with what the view said of it. A negative
has no fact to show and used to carry nothing, so the record whose return answered it
was lost (the employee's own record for a skill not held, the ticket for a due date not
set); now it is a covered record slice in the proof, the enumeration or the window that
closed the rest is a covered kind or window slice, and prose no read enumerates is an
unclosable one, which is how a result says a source was left unclosed. An unresolved
answer's proof holds the slices that stopped it. A proof names slices and never the
reads that supplied them, so one question has one proof over the truth and over a run
that read enough (ruling 4 of the same step). The proof is not part of an answer's
identity: two answers are equal when they say the same thing, whatever each rests on,
which keeps every comparison the rules and the world's verification make exactly what
it was.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from leaveimpact.core.authority import resolve
from leaveimpact.core.claims import UnknownReason
from leaveimpact.core.coverage import (
    Needed,
    Scope,
    Slice,
    SliceStatus,
    closing_slices,
    closing_slices_of_any,
)
from leaveimpact.core.facts import Fact, FactView, Gap
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef, with_article
from leaveimpact.core.values import FactValue, Observation

DerivedUnknownReason = Literal[
    UnknownReason.INACCESSIBLE, UnknownReason.ABSENT, UnknownReason.INSUFFICIENT
]
"""The reasons closure itself derives — a narrowing of the claim vocabulary, not a second one."""


@dataclass(frozen=True, slots=True)
class Consulted:
    """A slice an answer asked the view about, and what the view said of it.

    Covered, it is what settled a negative: the exact record when the slice is one
    record, which a claim can cite, and the enumeration or the window when it is a kind
    or a window, which no citation can name. Unread or failed, it is what stopped an
    answer. ``waived`` marks the slice no read observes whole that the answer stood
    without: the source left unclosed, which is what separates the operational reading of
    a negative from the strict one. An unclosable slice in an answer that something else
    stopped is not waived; the answer does not rest on it.
    """

    where: Slice
    status: SliceStatus
    waived: bool = False


Witness = Fact | Gap | Consulted
"""One thing an answer rests on."""

Proof = tuple[Witness, ...]
"""What an answer rests on, each witness once, in the order the rule came to them."""


def proof_of(*parts: Iterable[Witness]) -> Proof:
    """The witnesses of ``parts`` as one proof: in order, each once."""
    return tuple(dict.fromkeys(witness for part in parts for witness in part))


@dataclass(frozen=True, slots=True)
class KnownTrue:
    """Positive evidence exists; ``facts`` are what established it.

    ``proof`` holds the facts and whatever else the answer rested on, as the record a
    single-valued predicate was resolved through; it takes no part in equality.

    >>> from leaveimpact.core.coverage import KindSlice
    >>> from leaveimpact.core.enums import EntityKind
    >>> observed = Consulted(KindSlice(EntityKind.LEAVE), SliceStatus.COVERED)
    >>> KnownTrue(()) == KnownTrue((), (observed,))
    True
    """

    facts: tuple[Fact, ...]
    proof: Proof = field(default=(), compare=False)

    def __post_init__(self) -> None:
        # The one write a frozen dataclass allows itself: the facts are witnesses whatever
        # the caller listed, so a proof never has to be assembled from two fields.
        object.__setattr__(self, "proof", proof_of(self.facts, self.proof))


@dataclass(frozen=True, slots=True)
class KnownFalse:
    """The domain was fully observed and holds no positive evidence.

    ``proof`` holds what showed it: the slices observed, and the fact that decided it when
    one did (the record's other value, a status that is done). No part of equality.
    """

    proof: Proof = field(default=(), compare=False)


@dataclass(frozen=True, slots=True)
class Unresolved:
    """The question could not be settled; becomes an unknown claim keyed by subject and
    predicate.

    ``proof`` holds what was seen and what stopped the answer: a gap, the slices asked
    with their statuses, a lower-authority fact that was not promoted. No part of
    equality, so two unresolved answers about one subject and predicate for one reason
    are one unknown, as they always were.
    """

    subject: EntityRef
    predicate: PredicateName
    reason: DerivedUnknownReason
    proof: Proof = field(default=(), compare=False)


Closure = KnownTrue | KnownFalse | Unresolved


def establish(
    view: FactView,
    subject: EntityRef,
    name: PredicateName,
    value: FactValue | None = None,
    *,
    registry: Mapping[PredicateName, Predicate] = REGISTRY,
) -> Closure:
    """Whether ``name`` holds of ``subject`` — for the given ``value``, or for any value when
    ``value`` is None — in the world this view can see.

    A ``value`` the predicate's spec refuses is a programming error and raises, never a
    known false: a rule asking about ``"Kafka"`` where a skill slug is declared must fail
    in tests rather than declare a candidate non-viable. ``registry`` is the seam for a
    row the table does not declare (an open domain); production reads the registry as is.

    >>> from leaveimpact.core.facts import FactBase, RunCondition
    >>> from leaveimpact.core.refs import employee_ref
    >>> from leaveimpact.core.ids import EmployeeId
    >>> from datetime import date
    >>> empty = FactBase(()).at(date(2026, 9, 14), RunCondition.all_reachable())
    >>> establish(empty, employee_ref(EmployeeId("emp_017")), PredicateName.HAS_SKILL, "Kafka")
    Traceback (most recent call last):
    ...
    ValueError: has_skill: expected a skill, got 'Kafka': a skill id is a lower-case vocabulary key
    """
    row = registry[name]
    _require_subject(row, subject)
    if value is not None:
        try:
            row.value_spec.check(value)
        except ValueError as problem:
            raise ValueError(f"{row.name.value}: {problem}") from None
    needed = closing_slices(row, subject, value)
    standing = view.facts_about(subject, name)
    authority: Proof = ()
    if standing and not row.multi_valued:
        # Read through authority: the slice the system of record holds the fact in is asked
        # ahead of the facts, so another source's value is never promoted over a record
        # that was not observed.
        record = _consult(view, needed[0].where)
        reason = _why_unobserved(record.status)
        if reason is not None:
            return Unresolved(subject, row.name, reason, (*standing, record))
        standing = _agreeing_with_the_record(row, standing, registry=registry)
        authority = (record,)
    facts = tuple(fact for fact in standing if value is None or fact.value == value)
    if facts:
        return KnownTrue(facts, authority)
    if standing and not row.multi_valued:
        # The record answered with another value, and a single-valued predicate holds one.
        return KnownFalse((*standing, *authority))
    return _absence(view, row, subject, needed, view.gaps_about(subject, name))


def establish_any(
    view: FactView,
    name: PredicateName,
    matches: Callable[[Fact], bool],
    about: EntityRef,
    *,
    scope: Scope | None,
    registry: Mapping[PredicateName, Predicate] = REGISTRY,
) -> Closure:
    """Whether any visible fact of ``name`` satisfies ``matches``; ``about`` keys an unresolved
    answer and must be a subject the predicate accepts.

    ``scope`` is the window ``matches`` selects within, the leave's days or the meeting's
    span, and ``None`` when it selects among every record there is. A fact that matches
    is evidence wherever it was read; "none matches" is false only over a scope that was
    observed whole, so ``matches`` must not admit a fact outside the scope it states.
    """
    row = registry[name]
    _require_subject(row, about)
    needed = closing_slices_of_any(row, scope)
    authority: Proof = ()
    if not row.multi_valued:
        # Every subject's record is read through authority, so the records' slice is asked
        # once, ahead of the facts, as ``establish`` asks one record's.
        records = _consult(view, needed[0].where)
        reason = _why_unobserved(records.status)
        if reason is not None:
            return Unresolved(about, row.name, reason, (records,))
        authority = (records,)
    by_subject: dict[EntityRef, list[Fact]] = {}
    for fact in view.facts_of(name):
        by_subject.setdefault(fact.subject, []).append(fact)
    facts: list[Fact] = []
    for group in by_subject.values():
        standing = _agreeing_with_the_record(row, tuple(group), registry=registry)
        facts.extend(fact for fact in standing if matches(fact))
    if facts:
        return KnownTrue(tuple(facts), authority)
    return _absence(view, row, about, needed, ())


def any_true(closures: Iterable[Closure]) -> Closure:
    """The closure of "at least one of these": true if any is, else unresolved if any is, else
    false — an empty sequence is false, since nothing was asked.

    A true answer rests on the true ones, a false answer on every one of them, and the
    first unresolved one is returned as it is.
    """
    unresolved: Unresolved | None = None
    established: list[Fact] = []
    shown: list[Witness] = []
    refuted: list[Witness] = []
    for closure in closures:
        match closure:
            case KnownTrue():
                established.extend(closure.facts)
                shown.extend(closure.proof)
            case Unresolved():
                unresolved = unresolved or closure
            case KnownFalse():
                refuted.extend(closure.proof)
    if established:
        return KnownTrue(tuple(established), proof_of(shown))
    return unresolved or KnownFalse(proof_of(refuted))


def _agreeing_with_the_record(
    row: Predicate, facts: tuple[Fact, ...], *, registry: Mapping[PredicateName, Predicate]
) -> tuple[Fact, ...]:
    """The facts of one subject that state the value authority resolves to; all of them for a
    multi-valued predicate, which has no one value to resolve."""
    if row.multi_valued or len({fact.value for fact in facts}) <= 1:
        return facts
    # One observation per source: the base refuses a source holding two values.
    by_source = {fact.source: fact.value for fact in facts}
    observations = tuple(Observation(source, value) for source, value in by_source.items())
    resolution = resolve(row.name, observations, registry=registry)
    return tuple(fact for fact in facts if fact.value == resolution.value)


def _consult(view: FactView, where: Slice) -> Consulted:
    return Consulted(where, view.coverage.status(where))


def _why_unobserved(status: SliceStatus) -> DerivedUnknownReason | None:
    """Why a slice of that status cannot be read as observed whole, or ``None`` when it was:
    *inaccessible* when it could not be read, *insufficient* when it was not or cannot be."""
    match status:
        case SliceStatus.COVERED:
            return None
        case SliceStatus.FAILED:
            return UnknownReason.INACCESSIBLE
        case SliceStatus.UNREAD | SliceStatus.UNCLOSABLE:
            return UnknownReason.INSUFFICIENT


def _absence(
    view: FactView,
    row: Predicate,
    subject: EntityRef,
    needed: Sequence[Needed],
    gaps: tuple[Gap, ...],
) -> Closure:
    """What no fact means, once every slice in ``needed`` has been asked of the view.

    A waivable slice no read observes whole does not hold the negative back (the coverage
    module says why); one that failed does, like any other. Whatever the answer, its
    proof is the gaps and every slice asked.
    """
    asked = tuple(_consult(view, each.where) for each in needed)
    blocking = [
        consulted.status
        for each, consulted in zip(needed, asked, strict=True)
        if consulted.status is not SliceStatus.COVERED
        and not (each.waivable and consulted.status is SliceStatus.UNCLOSABLE)
    ]
    if SliceStatus.FAILED in blocking:
        return Unresolved(subject, row.name, UnknownReason.INACCESSIBLE, (*gaps, *asked))
    if blocking:
        return Unresolved(subject, row.name, UnknownReason.INSUFFICIENT, (*gaps, *asked))
    # Nothing stopped the answer, so whatever was not covered was waived: said in the proof.
    proof: Proof = (
        *gaps,
        *(
            consulted
            if consulted.status is SliceStatus.COVERED
            else Consulted(consulted.where, consulted.status, waived=True)
            for consulted in asked
        ),
    )
    if gaps:
        return Unresolved(subject, row.name, UnknownReason.ABSENT, proof)
    if not row.closed:
        return Unresolved(subject, row.name, UnknownReason.INSUFFICIENT, proof)
    return KnownFalse(proof)


def _require_subject(row: Predicate, subject: EntityRef) -> None:
    if subject.kind is not row.subject:
        raise ValueError(
            f"{row.name.value} is a fact about {with_article(row.subject.value)}, "
            f"got {with_article(subject.kind.value)}"
        )
