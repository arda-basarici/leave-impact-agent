"""Closed-world evaluation per declared evidence domain: known true, known false, or unknown with
the reason.

Zero facts mean false only after the evidence domain has been fully observed, and a
gap blocks that inference. That sentence is the whole rule (DESIGN, "The rules in
code"); the order below is its operational form, read over a ``FactView`` that already
holds only what this run can see:

1. a positive fact → known true, carrying the facts that established it, because the
   assessment's evidence references are built from them;
2. a source of the predicate's declared domain unreachable → unknown, *inaccessible*;
3. a gap → unknown, *absent*;
4. an open domain → unknown, *insufficient*;
5. otherwise → known false.

The precedence inside "unknown" runs inaccessible > absent > insufficient because the
run condition is the outermost cause of an incomplete observation set: a blank HR
field with the tracker unreachable reports inaccessible, since a reachable tracker
could have made the fact known true, and absent shows only when every source
answered. Closure derives these three reasons and no other; ``ambiguous`` and
``conflicting`` are the agent's to emit, never the rule's, and the result type says so
in its signature rather than in a second enum.

A single-valued predicate is read through the authority table (the step 15 rulings in
DESIGN, "The stale conflict sits on a real impact, and reads resolve"). The raw base
keeps every source's value, since the conflict derivation needs them all; a read
resolves them first, so a rule sees the system of record's value and the facts that
agree with it, and a lower-authority fact never answers "known true" for a value the
record contradicts. When the record itself is unreachable, a positive fact from
another source is not promoted to truth: the answer is unknown, *inaccessible*, ahead
of the positive-fact step. Multi-valued predicates keep the plain order — a skill
evidenced in a comment is evidence whether or not the HR record answered — which is
what the fragmented tier relies on. The record reachable and silent while another
source holds a value is known true: answered is the line, not answered positively.

Two entry points share the rule. ``establish`` asks about one subject — "does this
employee hold this skill" — and gaps apply. ``establish_any`` asks a subject-free
question over every visible fact of a predicate — "which events does this employee
attend" — keyed to the entity the question is about so an unresolved answer still
names a subject for the unknown claim; gaps are subject-bound and no planted class
puts one on an event's schedule or attendance, so they do not apply there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from leaveimpact.core.authority import resolve
from leaveimpact.core.claims import UnknownReason
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef, with_article
from leaveimpact.core.values import FactValue, Observation

DerivedUnknownReason = Literal[
    UnknownReason.INACCESSIBLE, UnknownReason.ABSENT, UnknownReason.INSUFFICIENT
]
"""The reasons closure itself derives — a narrowing of the claim vocabulary, not a second one."""


@dataclass(frozen=True, slots=True)
class KnownTrue:
    """Positive evidence exists; ``facts`` are what established it."""

    facts: tuple[Fact, ...]


@dataclass(frozen=True, slots=True)
class KnownFalse:
    """The domain was fully observed and holds no positive evidence."""


@dataclass(frozen=True, slots=True)
class Unresolved:
    """The question could not be settled; becomes an unknown claim keyed by subject and
    predicate."""

    subject: EntityRef
    predicate: PredicateName
    reason: DerivedUnknownReason


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
    standing = _standing(view, row, subject, view.facts_about(subject, name), registry=registry)
    if isinstance(standing, Unresolved):
        return standing
    facts = tuple(fact for fact in standing if value is None or fact.value == value)
    if facts:
        return KnownTrue(facts)
    if standing and not row.multi_valued:
        # The record answered with another value, and a single-valued predicate holds one.
        return KnownFalse()
    return _absence(view, row, subject, gapped=bool(view.gaps_about(subject, name)))


def establish_any(
    view: FactView,
    name: PredicateName,
    matches: Callable[[Fact], bool],
    about: EntityRef,
    *,
    registry: Mapping[PredicateName, Predicate] = REGISTRY,
) -> Closure:
    """Whether any visible fact of ``name`` satisfies ``matches``; ``about`` keys an unresolved
    answer and must be a subject the predicate accepts."""
    row = registry[name]
    _require_subject(row, about)
    if not row.multi_valued and row.system_of_record not in view.condition.reachable:
        return Unresolved(about, row.name, UnknownReason.INACCESSIBLE)
    by_subject: dict[EntityRef, list[Fact]] = {}
    for fact in view.facts_of(name):
        by_subject.setdefault(fact.subject, []).append(fact)
    facts: list[Fact] = []
    for subject, group in by_subject.items():
        standing = _standing(view, row, subject, tuple(group), registry=registry)
        assert not isinstance(standing, Unresolved)  # the record's reachability was checked above
        facts.extend(fact for fact in standing if matches(fact))
    if facts:
        return KnownTrue(tuple(facts))
    return _absence(view, row, about, gapped=False)


def any_true(closures: Iterable[Closure]) -> Closure:
    """The closure of "at least one of these": true if any is, else unresolved if any is, else
    false — an empty sequence is false, since nothing was asked."""
    unresolved: Unresolved | None = None
    established: list[Fact] = []
    for closure in closures:
        match closure:
            case KnownTrue():
                established.extend(closure.facts)
            case Unresolved():
                unresolved = unresolved or closure
            case KnownFalse():
                pass
    if established:
        return KnownTrue(tuple(established))
    return unresolved or KnownFalse()


def _standing(
    view: FactView,
    row: Predicate,
    subject: EntityRef,
    facts: tuple[Fact, ...],
    *,
    registry: Mapping[PredicateName, Predicate],
) -> tuple[Fact, ...] | Unresolved:
    """The facts of ``subject`` a rule may read: all of them for a multi-valued predicate; for
    a single-valued one, those agreeing with the authority table's value — or unresolved,
    *inaccessible*, when another source answered while the record could not."""
    if row.multi_valued or not facts:
        return facts
    if row.system_of_record not in view.condition.reachable:
        return Unresolved(subject, row.name, UnknownReason.INACCESSIBLE)
    if len({fact.value for fact in facts}) == 1:
        return facts
    # One observation per source: the base refuses a source holding two values.
    by_source = {fact.source: fact.value for fact in facts}
    observations = tuple(Observation(source, value) for source, value in by_source.items())
    resolution = resolve(row.name, observations, registry=registry)
    return tuple(fact for fact in facts if fact.value == resolution.value)


def _absence(view: FactView, row: Predicate, subject: EntityRef, *, gapped: bool) -> Closure:
    if not view.condition.reaches(row.evidence_domain):
        return Unresolved(subject, row.name, UnknownReason.INACCESSIBLE)
    if gapped:
        return Unresolved(subject, row.name, UnknownReason.ABSENT)
    if not row.closed:
        return Unresolved(subject, row.name, UnknownReason.INSUFFICIENT)
    return KnownFalse()


def _require_subject(row: Predicate, subject: EntityRef) -> None:
    if subject.kind is not row.subject:
        raise ValueError(
            f"{row.name.value} is a fact about {with_article(row.subject.value)}, "
            f"got {with_article(subject.kind.value)}"
        )
