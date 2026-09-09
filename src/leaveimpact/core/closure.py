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

from leaveimpact.core.claims import UnknownReason
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef, with_article
from leaveimpact.core.values import FactValue

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

    ``registry`` is the seam for a row the table does not declare (an open domain);
    production reads the registry as is.
    """
    row = registry[name]
    _require_subject(row, subject)
    facts = tuple(
        fact for fact in view.facts_about(subject, name) if value is None or fact.value == value
    )
    if facts:
        return KnownTrue(facts)
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
    facts = tuple(fact for fact in view.facts_of(name) if matches(fact))
    if facts:
        return KnownTrue(facts)
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
