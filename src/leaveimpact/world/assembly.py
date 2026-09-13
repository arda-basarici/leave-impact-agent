"""World assembly: the organization, the plan, every scenario, and the whole-world re-verification.

A scenario is correct locally against its key; a world is correct globally over the
history observable at each scenario's ``now`` (the assembled-world ruling at step 8). The
fact base is world-level and time-filtered, so a record one scenario plants can change a
verdict in another slice months later, which the per-scenario verification inside
``construct`` cannot see. Assembly therefore builds every scenario, derives one fact base
over the union of every planted record, and re-runs the verification for each scenario
at every day of its stable interval — today included, since the interval contains it.
A disagreement is ``WorldContamination``: the scenario, the view, the day, the impact,
the verdict, outcome or required sources that changed, expected against actual, and the
foreign records in that day's evidence with their owning scenario and observable-from
date. Never a repair or a redraw — a world that needs re-draws is a class whose
affordance is under-specified.

The verification runs under two views because only one of them is real at run time
(the runtime-view ruling at the validator step). The dated view is the truth base as the
evaluator reads it, each fact from the day the world planted its record. The runtime
view is what a run actually obtains: the read ports return what the systems hold — the
whole organization, every scenario's work items, the leaves and events overlapping the
scenario's window — and the harness dates every returned record to the run's day,
knowing no planting date. A key that holds under the dated view because a later or a
foreign planting stays hidden, and fails once the ports return it, is a world that would
seal cleanly and grade the investigator wrong; it is refused here instead. The reference
world passed both views on the day the second was added, so the runtime rule is a
constraint construction already met, now enforced.

Required sources are re-checked too, through the same pure rule construction used,
because the stable interval promises the same *key* for any ``now`` inside it and the
key includes them: a foreign fact can change what a conclusion depends on without
moving the conclusion — a comment establishing a skill the HR record already showed —
and that is a stale key (the step 8 review ruling).

Attribution is cheap for a verdict because planted records are only ever added: a
verdict can only flip toward more established facts, and the flipped verdict's own
evidence names the record. Any evidence entity that is neither the organization's nor
this scenario's own is foreign, and the owner is read off the scenarios' owned entities.
For a dependence drift the cause is counterfactual and may be several facts together, so
the finding lists the foreign records visible in the scenario's evidence that day rather
than claiming one culprit; expected against actual is the authoritative part.

One seed identifies a world: the organization is generated from it, one ``Random`` from
it deals the slices and the plan and hands each scenario its own generator, and one id
book numbers every record world-wide. The result is a ``SemanticWorld``: everything the
seed determines, which since the prose step is not yet a world spec. The parts a model
writes — a comment on a ticket, a section of a runbook — are absent from it and stand as
briefs, typed pending targets with the facts each must carry; verification needs no text,
so it runs here, on the semantic world, before any model is paid. ``WorldSpec`` is the
semantic world with those parts composed in, plus the one thing only composition knows,
the record of how each text was accepted; the composition module builds it, and its own
invariant is that every brief's target is now present and every prose-authored fact
resolves to a part. A world with no pending prose composes into the same entities it was
assembled with and carries no record.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from leaveimpact.core.claims import Verdict
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.facts import Fact, FactBase, RunCondition
from leaveimpact.core.ids import EmployeeId, ScenarioId
from leaveimpact.core.plans import expected_action
from leaveimpact.core.viability import assess_impact
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.world.briefs import parts_of
from leaveimpact.world.construction import (
    ConstructionError,
    Minting,
    construct,
    required_count_for,
    required_sources_for,
)
from leaveimpact.world.modifiers import MODIFIERS
from leaveimpact.world.org import OrgParams, OrgSpec, generate_org
from leaveimpact.world.plan import TIER_ONE_RULES, PlanRow, PlanRules, plan_world
from leaveimpact.world.prose import MaterializationRecord
from leaveimpact.world.runtime_view import runtime_facts, runtime_records
from leaveimpact.world.scenario import Scenario
from leaveimpact.world.slices import allocate_slices
from leaveimpact.world.structured import SCENARIO_CLASSES
from leaveimpact.world.truth_facts import truth_fact_base
from leaveimpact.world.version import GENERATOR_VERSION, GeneratorVersion
from leaveimpact.world.vocabulary import vocabulary_digest


@dataclass(frozen=True, slots=True)
class ForeignRecord:
    """A record another scenario planted that entered this scenario's evidence."""

    entity_id: str
    owner: ScenarioId
    observable_from: date


@dataclass(frozen=True, slots=True)
class Contamination:
    """One disagreement between a scenario's key and the rules over the assembled world.

    ``view`` names which reading of the world disagreed: the dated truth base, or the
    runtime view in which every record the ports return is observable.
    """

    scenario_id: ScenarioId
    view: str
    day: date
    artifact_id: str
    subject: str
    expected: str
    actual: str
    foreign: tuple[ForeignRecord, ...]

    def __str__(self) -> str:
        culprits = ", ".join(
            f"{f.entity_id} (owned by {f.owner}, observable from {f.observable_from})"
            for f in self.foreign
        ) or "no foreign record in the evidence"
        return (
            f"{self.scenario_id} on {self.day} under the {self.view} view, {self.artifact_id}: "
            f"{self.subject} expected {self.expected}, the assembled world says {self.actual}; "
            f"{culprits}"
        )


class WorldContamination(ConstructionError):
    """Local construction passed; the assembled world disagrees with at least one key."""

    def __init__(self, findings: Sequence[Contamination]) -> None:
        super().__init__("; ".join(str(finding) for finding in findings))
        self.findings = tuple(findings)


@dataclass(frozen=True, slots=True)
class SemanticWorld:
    """Everything the seed determines: organization, plan, scenarios with their briefs, the
    world-level fact base, provenance — the parts a model writes still pending.

    ``interpreter`` is the minor version the world was generated under and
    ``vocabulary_digest`` the tables' fingerprint; with the seed, the organization's
    parameters and the generator version they are the provenance the manifest records.
    Two runs from one seed share this value whatever prose they go on to accept.
    """

    seed: int
    world_start: date
    org: OrgSpec
    slices: tuple[DateSpan, ...]
    plan: tuple[PlanRow, ...]
    scenarios: tuple[Scenario, ...]
    facts: FactBase
    generator_version: GeneratorVersion
    interpreter: tuple[int, int]
    vocabulary_digest: str

    def __post_init__(self) -> None:
        if not (len(self.slices) == len(self.plan) == len(self.scenarios)):
            raise ValueError(
                f"one slice, one plan row and one scenario each, got {len(self.slices)}, "
                f"{len(self.plan)} and {len(self.scenarios)}"
            )
        for row, scenario in zip(self.plan, self.scenarios, strict=True):
            if (row.scenario_id, row.scenario_class, row.modifiers) != (
                scenario.key.scenario_id,
                scenario.key.scenario_class,
                scenario.key.modifiers,
            ):
                raise ValueError(f"plan row {row.scenario_id} and its scenario disagree")
        ids = [brief.id for scenario in self.scenarios for brief in scenario.briefs]
        if len(set(ids)) != len(ids):
            raise ValueError(f"a prose target is briefed once world-wide, got {ids}")

    @property
    def pending_ids(self) -> frozenset[str]:
        """The ids of every part a model still owes this world."""
        return frozenset(brief.id for scenario in self.scenarios for brief in scenario.briefs)


@dataclass(frozen=True, slots=True)
class WorldSpec(SemanticWorld):
    """A semantic world with its model-written parts composed in, and the two things only
    composition knows: the semantic digest and the record of how each text was accepted.

    Built by the composition module and never by hand: ``semantic_digest`` is the hash of
    the semantic world this was composed from, computed there so no caller passes one, and
    ``materialization`` is the provenance of every accepted text, ``None`` exactly when
    the world had no pending prose. The invariant a composed world adds is that every
    brief's target is now a part of its parent and every prose-authored fact resolves to a
    part that exists.
    """

    semantic_digest: str
    materialization: MaterializationRecord | None

    def __post_init__(self) -> None:
        SemanticWorld.__post_init__(self)
        if not re.fullmatch(r"[0-9a-f]{64}", self.semantic_digest):
            raise ValueError(f"semantic_digest is a SHA-256 hex, got {self.semantic_digest!r}")
        pending = self.pending_ids
        recorded: frozenset[str] = (
            frozenset() if self.materialization is None else self.materialization.target_ids
        )
        if recorded != pending:
            raise ValueError(
                f"the materialization record covers {sorted(recorded)} and the briefs name "
                f"{sorted(pending)}"
            )
        for scenario in self.scenarios:
            present = parts_of(
                [p.entity for p in scenario.owned.work_items],
                [p.entity for p in scenario.owned.documents],
            )
            missing = sorted(brief.id for brief in scenario.briefs if brief.id not in present)
            if missing:
                raise ValueError(f"{scenario.spec.id}: briefed parts not composed: {missing}")
            unresolved = sorted(
                fact.evidence.target.id
                for fact in scenario.authored_facts
                if fact.evidence.target.kind in (EntityKind.COMMENT, EntityKind.CLAUSE)
                and fact.evidence.target.id not in present
            )
            if unresolved:
                raise ValueError(
                    f"{scenario.spec.id}: authored facts evidenced by parts that do not exist: "
                    f"{unresolved}"
                )


def assemble_semantic_world(
    seed: int,
    params: OrgParams,
    world_start: date,
    rules: PlanRules = TIER_ONE_RULES,
) -> SemanticWorld:
    """The semantic world ``seed`` produces under ``params`` and ``rules``, re-verified as a whole.

    Raises ``PlanInfeasible`` when the rule cannot be met, a construction error when a
    scenario cannot be built as planned, ``WorldContamination`` when the assembled world
    disagrees with a key. Same inputs, same world.
    """
    org = generate_org(seed, params)
    rng = Random(seed)
    plan = plan_world(rng, rules)
    slices = allocate_slices(rng, len(plan), world_start)
    ids = Minting()
    scenarios = tuple(
        construct(
            SCENARIO_CLASSES[row.scenario_class],
            [MODIFIERS[name] for name in row.modifiers],
            org,
            scenario_id=row.scenario_id,
            window=window,
            world_start=world_start,
            reference_timezone=params.reference_timezone,
            ids=ids,
            rng=Random(rng.getrandbits(64)),
        )
        for row, window in zip(plan, slices, strict=True)
    )
    facts = world_fact_base(org, world_start, scenarios)
    findings = verify_world(facts, scenarios, org)
    if findings:
        raise WorldContamination(findings)
    return SemanticWorld(
        seed=seed,
        world_start=world_start,
        org=org,
        slices=slices,
        plan=plan,
        scenarios=scenarios,
        facts=facts,
        generator_version=GENERATOR_VERSION,
        interpreter=(sys.version_info.major, sys.version_info.minor),
        vocabulary_digest=vocabulary_digest(),
    )


def world_fact_base(org: OrgSpec, world_start: date, scenarios: Sequence[Scenario]) -> FactBase:
    """The one fact base over the organization and every scenario's planted and authored facts."""
    return truth_fact_base(
        org,
        world_start,
        [scenario.owned for scenario in scenarios],
        [fact for scenario in scenarios for fact in scenario.authored_facts],
    )


def verify_world(
    facts: FactBase, scenarios: Sequence[Scenario], org: OrgSpec
) -> tuple[Contamination, ...]:
    """Every disagreement between a key and the rules under both views, across each stable interval.

    The same checks ``construct`` ran locally — authored verdicts per candidate, the
    outcome over the whole organization, the required sources — now against the
    assembled world, at every day of the scenario's stable interval, twice: under the
    dated truth base ``facts``, and under the runtime view, the records the read ports
    return for the scenario's window with every one of them observable that day. Empty
    means the world is valid and realizable.
    """
    owner_of = _owners(scenarios)
    universe = [employee.id for employee in org.employees]
    owned = [scenario.owned for scenario in scenarios]
    authored = [fact for scenario in scenarios for fact in scenario.authored_facts]
    findings: list[Contamination] = []
    for scenario in scenarios:
        records = runtime_records(org, owned, scenario.spec)
        for day in _days(scenario.key.stable_interval):
            findings.extend(_check_day(DATED_VIEW, facts, day, scenario, universe, org, owner_of))
            runtime = runtime_facts(records, day, authored)
            findings.extend(
                _check_day(RUNTIME_VIEW, runtime, day, scenario, universe, org, owner_of)
            )
    return tuple(findings)


DATED_VIEW = "dated"
"""The truth base at a day: every fact the world had made observable by then."""

RUNTIME_VIEW = "runtime"
"""What a run that day obtains through the read ports, every returned record observable."""


def _check_day(
    view_name: str,
    base: FactBase,
    day: date,
    scenario: Scenario,
    universe: Sequence[EmployeeId],
    org: OrgSpec,
    owner_of: dict[str, tuple[ScenarioId, date]],
) -> list[Contamination]:
    """The key's three checks against ``base`` as seen on ``day``: verdicts, outcome, sources."""
    leave = scenario.investigated_leave.span
    timezone = scenario.spec.reference_timezone
    view = base.at(day, RunCondition.all_reachable())
    findings: list[Contamination] = []
    evidence_today: list[Fact] = []
    for expected in scenario.key.impacts:
        assessments = assess_impact(
            view, expected.key, universe, scenario.key.constraints, leave, timezone
        )
        by_employee = {a.employee_id: a for a in assessments}
        evidence_today.extend(fact for a in assessments for fact in a.evidence)
        for authored in expected.must_assess:
            actual = by_employee[authored.employee_id]
            if (actual.verdict, actual.reasons) == (authored.verdict, authored.reasons):
                continue
            findings.append(
                Contamination(
                    scenario.key.scenario_id,
                    view_name,
                    day,
                    expected.key.artifact.id,
                    authored.employee_id,
                    _verdict_text(authored.verdict, authored.reasons),
                    _verdict_text(actual.verdict, actual.reasons),
                    _foreign(actual.evidence, scenario, owner_of),
                )
            )
        required = required_count_for(view, expected.key, scenario.key.constraints, leave, timezone)
        outcome = expected_action((a.verdict for a in assessments), required)
        if outcome is not expected.outcome:
            evidence = [fact for a in assessments for fact in a.evidence]
            findings.append(
                Contamination(
                    scenario.key.scenario_id,
                    view_name,
                    day,
                    expected.key.artifact.id,
                    "outcome",
                    expected.outcome.value,
                    outcome.value,
                    _foreign(evidence, scenario, owner_of),
                )
            )
    required = required_sources_for(
        base,
        day,
        scenario.key.impacts,
        scenario.key.constraints,
        leave,
        timezone,
        org,
        scenario.spec.leave_id,
    )
    if required != set(scenario.key.required_sources):
        findings.append(
            Contamination(
                scenario.key.scenario_id,
                view_name,
                day,
                "all impacts",
                "required_sources",
                _sources_text(scenario.key.required_sources),
                _sources_text(required),
                _foreign(evidence_today, scenario, owner_of),
            )
        )
    return findings


def _sources_text(sources: Iterable[Source]) -> str:
    return "[" + ", ".join(sorted(source.value for source in sources)) + "]"


def _days(span: DateSpan) -> list[date]:
    return [span.start + timedelta(days=offset) for offset in range(span.days)]


def _verdict_text(verdict: Verdict, reasons: tuple[object, ...]) -> str:
    named = [getattr(reason, "value", str(reason)) for reason in reasons]
    return f"{verdict.value} {named}" if named else verdict.value


def _owners(scenarios: Sequence[Scenario]) -> dict[str, tuple[ScenarioId, date]]:
    """Every planted entity id, the comments and sections inside them included, to its owner."""
    owners: dict[str, tuple[ScenarioId, date]] = {}
    for scenario in scenarios:
        who = scenario.key.scenario_id
        for planted in scenario.owned.leaves:
            owners[planted.entity.id] = (who, planted.observable_from)
        for planted in scenario.owned.work_items:
            owners[planted.entity.id] = (who, planted.observable_from)
            for comment in planted.entity.comments:
                owners[comment.id] = (who, comment.world_date)
        for planted in scenario.owned.events:
            owners[planted.entity.id] = (who, planted.observable_from)
        for planted in scenario.owned.documents:
            owners[planted.entity.id] = (who, planted.observable_from)
            for section in planted.entity.sections:
                owners[section.id] = (who, planted.observable_from)
    return owners


def _foreign(
    evidence: Sequence[Fact], scenario: Scenario, owner_of: dict[str, tuple[ScenarioId, date]]
) -> tuple[ForeignRecord, ...]:
    """The evidence records owned by another scenario, each once, in evidence order."""
    seen: set[str] = set()
    foreign: list[ForeignRecord] = []
    for fact in evidence:
        target = fact.evidence.target.id
        owned = owner_of.get(target)
        if owned is None or owned[0] == scenario.key.scenario_id or target in seen:
            continue
        seen.add(target)
        foreign.append(ForeignRecord(target, owned[0], owned[1]))
    return tuple(foreign)


__all__ = [
    "Contamination",
    "ForeignRecord",
    "SemanticWorld",
    "WorldContamination",
    "WorldSpec",
    "assemble_semantic_world",
    "verify_world",
    "world_fact_base",
]
