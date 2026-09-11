"""World assembly: the organization, the plan, every scenario, and the whole-world re-verification.

A scenario is correct locally against its key; a world is correct globally over the
history observable at each scenario's ``now`` (the assembled-world ruling at step 8). The
fact base is world-level and time-filtered, so a record one scenario plants can change a
verdict in another slice months later, which the per-scenario verification inside
``construct`` cannot see. Assembly therefore builds every scenario, derives one fact base
over the union of every planted record, and re-runs the verification for each scenario
at every day of its stable interval — today included, since the interval contains it.
A disagreement is ``WorldContamination``: the scenario, the day, the impact, the verdict
or outcome that changed, expected against actual, and the foreign record responsible with
its owning scenario and observable-from date. Never a repair or a redraw — a world that
needs re-draws is a class whose affordance is under-specified.

Attribution costs nothing because planted records are only ever added: a verdict can only
flip toward more established facts, and the flipped verdict's own evidence names the
record. Any evidence entity that is neither the organization's nor this scenario's own
is foreign, and the owner is read off the scenarios' owned entities.

One seed identifies a world: the organization is generated from it, one ``Random`` from
it deals the slices and the plan and hands each scenario its own generator, and one id
book numbers every record world-wide. The result is a ``WorldSpec``, the pure composed
bundle the artifact step serializes and hashes.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from leaveimpact.core.claims import CoverageActionKind, Verdict
from leaveimpact.core.facts import Fact, FactBase, RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.plans import expected_action
from leaveimpact.core.viability import assess_impact
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.world.construction import (
    ConstructionError,
    Minting,
    construct,
    required_count_for,
)
from leaveimpact.world.modifiers import MODIFIERS
from leaveimpact.world.org import OrgParams, OrgSpec, generate_org
from leaveimpact.world.plan import TIER_ONE_RULES, PlanRow, PlanRules, plan_world
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
    """One disagreement between a scenario's key and the rules over the assembled world."""

    scenario_id: ScenarioId
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
            f"{self.scenario_id} on {self.day}, {self.artifact_id}: {self.subject} expected "
            f"{self.expected}, the assembled world says {self.actual}; {culprits}"
        )


class WorldContamination(ConstructionError):
    """Local construction passed; the assembled world disagrees with at least one key."""

    def __init__(self, findings: Sequence[Contamination]) -> None:
        super().__init__("; ".join(str(finding) for finding in findings))
        self.findings = tuple(findings)


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """The pure composed bundle: organization, plan, scenarios, world-level fact base, provenance.

    ``interpreter`` is the minor version the world was generated under and
    ``vocabulary_digest`` the tables' fingerprint; with the seed, the organization's
    parameters and the generator version they are the provenance the manifest records.
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


def assemble_world(
    seed: int,
    params: OrgParams,
    world_start: date,
    rules: PlanRules = TIER_ONE_RULES,
) -> WorldSpec:
    """The world ``seed`` produces under ``params`` and ``rules``, re-verified as a whole.

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
    return WorldSpec(
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
    """Every disagreement between a key and the rules over ``facts``, across each stable interval.

    The same check ``construct`` ran locally — authored verdicts per candidate, the
    outcome over the whole organization — now against the assembled world, at every day
    of the scenario's stable interval. Empty means the world is valid.
    """
    owner_of = _owners(scenarios)
    universe = [employee.id for employee in org.employees]
    findings: list[Contamination] = []
    for scenario in scenarios:
        leave = scenario.investigated_leave.span
        timezone = scenario.spec.reference_timezone
        for day in _days(scenario.key.stable_interval):
            view = facts.at(day, RunCondition.all_reachable())
            for expected in scenario.key.impacts:
                assessments = assess_impact(
                    view, expected.key, universe, scenario.key.constraints, leave, timezone
                )
                by_employee = {a.employee_id: a for a in assessments}
                for authored in expected.must_assess:
                    actual = by_employee[authored.employee_id]
                    if (actual.verdict, actual.reasons) == (authored.verdict, authored.reasons):
                        continue
                    findings.append(
                        Contamination(
                            scenario.key.scenario_id,
                            day,
                            expected.key.artifact.id,
                            authored.employee_id,
                            _verdict_text(authored.verdict, authored.reasons),
                            _verdict_text(actual.verdict, actual.reasons),
                            _foreign(actual.evidence, scenario, owner_of),
                        )
                    )
                required = required_count_for(
                    view, expected.key, scenario.key.constraints, leave, timezone
                )
                outcome = expected_action((a.verdict for a in assessments), required)
                if outcome is not expected.outcome:
                    evidence = [fact for a in assessments for fact in a.evidence]
                    findings.append(
                        Contamination(
                            scenario.key.scenario_id,
                            day,
                            expected.key.artifact.id,
                            "outcome",
                            expected.outcome.value,
                            outcome.value,
                            _foreign(evidence, scenario, owner_of),
                        )
                    )
    return tuple(findings)


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
    "CoverageActionKind",
    "ForeignRecord",
    "WorldContamination",
    "WorldSpec",
    "assemble_world",
    "verify_world",
    "world_fact_base",
]
