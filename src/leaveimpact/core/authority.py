"""The authority table: which observation wins when sources disagree, and where they disagree.

"Live wins" is the design intent and ``system_of_record_wins`` is the rule (DESIGN,
"Four semantic rules travel with the vocabulary"): each predicate has exactly one
system of record, declared in the registry, and its observation is the resolved value
whenever observations conflict. A conflict is keyed by subject and predicate, never by
field names that happen to look alike — an office location and a calendar timezone
are not a contradiction — and only a single-valued predicate can conflict: two sources
each naming a skill are a set, not a disagreement. The rule is a table lookup so that
precedence is testable rather than intuited, and the conflict claim cites the rule id
for the same reason.

``conflicts_in`` is the truth side: the generator derives the conflicts a world plants
from the fact base itself, so a stale runbook naming an outdated owner is an expected
``source_conflict`` claim because the facts say so, not because someone remembered to
list it. ``resolve`` is the shared judgement: the same function tells the generator
what the resolved value is and tells the chain check whether an agent's conflict claim
resolved to the right one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import AuthorityRule
from leaveimpact.core.facts import Fact, FactKey, FactView
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import FactValue, Observation


@dataclass(frozen=True, slots=True)
class Resolution:
    """The outcome of the authority rule: the value that stands, the rule that chose it, the
    observation it came from."""

    value: FactValue
    rule: AuthorityRule
    winner: Observation


def resolve(
    name: PredicateName,
    observations: Sequence[Observation],
    *,
    registry: Mapping[PredicateName, Predicate] = REGISTRY,
) -> Resolution:
    """The value that stands among ``observations`` of ``name``: the system of record's.

    ``ValueError`` when the observations do not form a resolvable conflict — a
    multi-valued predicate, fewer than two observations, a source twice, a source
    outside the predicate's domain, no two different values, or no observation from
    the system of record, which the table cannot rank without.

    >>> from leaveimpact.core.enums import Source
    >>> from leaveimpact.core.ids import EmployeeId
    >>> from leaveimpact.core.refs import employee_ref
    >>> live = Observation(Source.JIRA, employee_ref(EmployeeId("emp_017")))
    >>> stale = Observation(Source.CORPUS, employee_ref(EmployeeId("emp_003")))
    >>> resolve(PredicateName.OWNS_WORK_ITEM, (stale, live)).value.id
    'emp_017'
    """
    row = registry[name]
    if row.multi_valued:
        raise ValueError(f"{name.value}: a multi-valued predicate holds sets, never conflicts")
    sources = [observation.source for observation in observations]
    if len(sources) < 2:
        raise ValueError(f"{name.value}: a conflict needs at least two observations")
    if len(set(sources)) != len(sources):
        raise ValueError(f"{name.value}: a conflict observes each source once")
    outside = sorted(source.value for source in set(sources) - row.evidence_domain)
    if outside:
        raise ValueError(
            f"{name.value}: {', '.join(outside)} is outside the evidence domain of {name.value}"
        )
    if len({observation.value for observation in observations}) < 2:
        raise ValueError(f"{name.value}: a conflict needs two different observed values")
    for observation in observations:
        if observation.source is row.system_of_record:
            return Resolution(observation.value, AuthorityRule.SYSTEM_OF_RECORD_WINS, observation)
    raise ValueError(
        f"{name.value}: no observation from the system of record "
        f"{row.system_of_record.value}; the authority table cannot resolve"
    )


@dataclass(frozen=True, slots=True)
class ConflictFinding:
    """A planted disagreement as the fact base states it: every fact involved, the observations
    one per source, and the resolution.

    A source may state its one value more than once — a runbook naming the owner in two
    paragraphs is corroboration, and the base admits it — so ``facts`` keeps every record
    for the evidence references while ``observations`` collapses each source to the one
    value it holds, which is what the authority rule ranks and the conflict claim carries.
    """

    subject: EntityRef
    predicate: PredicateName
    facts: tuple[Fact, ...]
    observations: tuple[Observation, ...]
    resolution: Resolution


def conflicts_in(
    view: FactView, *, registry: Mapping[PredicateName, Predicate] = REGISTRY
) -> tuple[ConflictFinding, ...]:
    """Every subject and single-valued predicate on which the visible sources disagree, with the
    resolution, in a stable order (subject kind, subject id, predicate)."""
    grouped: dict[FactKey, list[Fact]] = {}
    for fact in view.facts:
        if not registry[fact.predicate].multi_valued:
            grouped.setdefault(fact.key, []).append(fact)
    findings: list[ConflictFinding] = []
    for (subject, name), facts in grouped.items():
        if len({fact.value for fact in facts}) < 2:
            continue
        ordered = tuple(sorted(facts, key=lambda fact: fact.source.value))
        # One observation per source: the base guarantees a source's facts agree here.
        by_source = {fact.source: fact.value for fact in ordered}
        observations = tuple(Observation(source, value) for source, value in by_source.items())
        findings.append(
            ConflictFinding(
                subject, name, ordered, observations, resolve(name, observations, registry=registry)
            )
        )
    findings.sort(key=lambda finding: (finding.subject.kind, finding.subject.id, finding.predicate))
    return tuple(findings)
