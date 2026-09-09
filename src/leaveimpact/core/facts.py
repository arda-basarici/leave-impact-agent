"""The fact base: every planted atomic fact with its provenance, and the view of it a run can see.

The rules' only world is this base (DESIGN, "The rules in code"): a fact is a subject,
a predicate, a typed value, the evidence reference it was read from and the world date
at which it became observable, and a rule that has to reach back into an entity for a
field is not reading the fact base. Validation happens once, at construction, against
the predicate's registry row — the subject's kind, the value's spec, the evidence
source inside the declared domain — so a rule downstream never re-checks shape.

Absence is a record of its own. A ``Gap`` says the record was observed and this field
held no value; it is planted where a scenario class plants a missing fact, and it is
never a failed read. A failed read is the run condition: ``RunCondition`` names the
sources reachable in this execution, passed beside ``RunContext`` rather than inside
it because one scenario runs under several conditions and the tool-failure metric is
the difference between them. The distinction the entity types drew between a missing
skills field and an empty one maps to gap-versus-no-facts when the world builds the
base, a per-field table there: a ticket without a due date is an observed negative,
zero ``due_on`` facts and no gap.

A ``FactView`` is the base restricted to what a run at ``now`` under a condition can
observe — facts and gaps dated at or before ``now`` from reachable sources — so a
qualification evidenced in month three is admissible in month nine and not in month
one, and a skill visible only in a ticket comment is no evidence in a run where the
tracker is down. Every rule takes the view; the filtering happens once.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

from leaveimpact.core.enums import Source
from leaveimpact.core.predicates import Predicate, PredicateName, predicate
from leaveimpact.core.refs import EntityRef, EvidenceRef, with_article
from leaveimpact.core.values import FactValue

FactKey = tuple[EntityRef, PredicateName]
"""What a fact or a gap is about: the subject and the predicate."""


@dataclass(frozen=True, slots=True)
class RunCondition:
    """Which sources this execution can reach — the run's fault condition, not the world's state.

    >>> RunCondition.all_reachable().without(Source.JIRA).reaches({Source.FRAPPE, Source.JIRA})
    False
    """

    reachable: frozenset[Source]

    @classmethod
    def all_reachable(cls) -> RunCondition:
        """The normal run: every source answers."""
        return cls(frozenset(Source))

    def without(self, *sources: Source) -> RunCondition:
        """This condition with ``sources`` unreachable — a tool-failure run."""
        return RunCondition(self.reachable - frozenset(sources))

    def reaches(self, sources: Iterable[Source]) -> bool:
        """Whether every one of ``sources`` is reachable."""
        return frozenset(sources) <= self.reachable


def _require_subject(row: Predicate, subject: EntityRef) -> None:
    if subject.kind is not row.subject:
        raise ValueError(
            f"{row.name.value} is a fact about {with_article(row.subject.value)}, "
            f"got {with_article(subject.kind.value)}"
        )


def _require_in_domain(row: Predicate, evidence: EvidenceRef) -> None:
    if evidence.source not in row.evidence_domain:
        raise ValueError(
            f"{evidence.source.value} is outside the evidence domain of {row.name.value}: "
            f"{', '.join(sorted(source.value for source in row.evidence_domain))}"
        )


@dataclass(frozen=True, slots=True)
class Fact:
    """One atomic world fact: what is true of the subject, where that was read, since when.

    ``observable_from`` is the world date at which the provenance became observable —
    world start for static HR facts, the comment's date for a skill evidenced in a
    ticket comment — and the view admits the fact from that day on.

    >>> from leaveimpact.core.refs import employee_ref, team_ref
    >>> from leaveimpact.core.ids import EmployeeId, TeamId
    >>> who = employee_ref(EmployeeId("emp_017"))
    >>> Fact(who, PredicateName.MEMBER_OF_TEAM, "payments",
    ...      EvidenceRef(Source.FRAPPE, who, "team_id"), date(2026, 1, 1))
    Traceback (most recent call last):
    ...
    ValueError: member_of_team: expected an entity_ref to a team, got 'payments'
    """

    subject: EntityRef
    predicate: PredicateName
    value: FactValue
    evidence: EvidenceRef
    observable_from: date

    def __post_init__(self) -> None:
        row = predicate(self.predicate)
        _require_subject(row, self.subject)
        try:
            row.value_spec.check(self.value)
        except ValueError as problem:
            raise ValueError(f"{row.name.value}: {problem}") from None
        _require_in_domain(row, self.evidence)

    @property
    def source(self) -> Source:
        """The source the fact was read from — the evidence reference's."""
        return self.evidence.source

    @property
    def key(self) -> FactKey:
        return (self.subject, self.predicate)


@dataclass(frozen=True, slots=True)
class Gap:
    """The record was observed and this field held no value.

    Not a failed read — an unreachable source is the run condition — and not an observed
    negative: a gap is planted where missing information is the scenario's point, and
    it blocks the closed-world inference that zero facts mean false.
    """

    subject: EntityRef
    predicate: PredicateName
    evidence: EvidenceRef
    observable_from: date

    def __post_init__(self) -> None:
        row = predicate(self.predicate)
        _require_subject(row, self.subject)
        _require_in_domain(row, self.evidence)

    @property
    def source(self) -> Source:
        return self.evidence.source

    @property
    def key(self) -> FactKey:
        return (self.subject, self.predicate)


def _index[T: Fact | Gap](items: Iterable[T]) -> Mapping[FactKey, tuple[T, ...]]:
    grouped: dict[FactKey, list[T]] = {}
    for item in items:
        grouped.setdefault(item.key, []).append(item)
    return MappingProxyType({key: tuple(group) for key, group in grouped.items()})


@dataclass(frozen=True, slots=True)
class FactBase:
    """The world-level truth: every fact and gap with dated provenance, checked for coherence.

    Refused at construction: a fact or gap stated twice; a source that both holds a
    value and holds none for one subject and predicate; a single-valued predicate given
    two values by one source for one subject. Two *sources* disagreeing is not refused —
    that is a planted conflict, the authority table's to resolve.
    """

    facts: tuple[Fact, ...]
    gaps: tuple[Gap, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.facts)) != len(self.facts):
            raise ValueError("a fact is stated once")
        if len(set(self.gaps)) != len(self.gaps):
            raise ValueError("a gap is stated once")
        gapped = {(gap.key, gap.source) for gap in self.gaps}
        for fact in self.facts:
            if (fact.key, fact.source) in gapped:
                raise ValueError(
                    f"{fact.source.value} cannot both hold a value and hold none for "
                    f"{fact.predicate.value} of {fact.subject.id}"
                )
        seen: dict[tuple[FactKey, Source], FactValue] = {}
        for fact in self.facts:
            if predicate(fact.predicate).multi_valued:
                continue
            slot = (fact.key, fact.source)
            if slot in seen and seen[slot] != fact.value:
                raise ValueError(
                    f"{fact.source.value} holds two values for {fact.predicate.value} of "
                    f"{fact.subject.id}, a single-valued predicate"
                )
            seen.setdefault(slot, fact.value)

    def at(self, now: date, condition: RunCondition) -> FactView:
        """What a run at ``now`` under ``condition`` can observe."""
        return FactView(
            now,
            condition,
            tuple(
                fact
                for fact in self.facts
                if fact.observable_from <= now and fact.source in condition.reachable
            ),
            tuple(
                gap
                for gap in self.gaps
                if gap.observable_from <= now and gap.source in condition.reachable
            ),
        )


@dataclass(frozen=True, slots=True)
class FactView:
    """The base as one run sees it; built by ``FactBase.at``, read by every rule."""

    now: date
    condition: RunCondition
    facts: tuple[Fact, ...]
    gaps: tuple[Gap, ...]
    _facts_by_key: Mapping[FactKey, tuple[Fact, ...]] = field(init=False, repr=False, compare=False)
    _gaps_by_key: Mapping[FactKey, tuple[Gap, ...]] = field(init=False, repr=False, compare=False)
    _facts_by_predicate: Mapping[PredicateName, tuple[Fact, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        by_predicate: dict[PredicateName, list[Fact]] = {}
        for fact in self.facts:
            by_predicate.setdefault(fact.predicate, []).append(fact)
        # The indexes are the one write a frozen dataclass allows itself.
        object.__setattr__(self, "_facts_by_key", _index(self.facts))
        object.__setattr__(self, "_gaps_by_key", _index(self.gaps))
        object.__setattr__(
            self,
            "_facts_by_predicate",
            MappingProxyType({name: tuple(group) for name, group in by_predicate.items()}),
        )

    def facts_about(self, subject: EntityRef, name: PredicateName) -> tuple[Fact, ...]:
        """The visible facts stating ``name`` of ``subject``, in base order."""
        return self._facts_by_key.get((subject, name), ())

    def gaps_about(self, subject: EntityRef, name: PredicateName) -> tuple[Gap, ...]:
        """The visible gaps for ``name`` of ``subject``."""
        return self._gaps_by_key.get((subject, name), ())

    def facts_of(self, name: PredicateName) -> tuple[Fact, ...]:
        """Every visible fact stating ``name``, whatever its subject — for subject-free queries."""
        return self._facts_by_predicate.get(name, ())
