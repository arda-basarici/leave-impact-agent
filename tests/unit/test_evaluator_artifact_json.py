"""The artifact's written form. Two evaluations of the same stored runs are the same bytes. A
run is written as its outcome and its findings and nothing recomputable; a condition as the
sources it cannot reach; an absent part as null beside an empty one as empty. A value the
walk has no rule for and a number that is not finite are refused. And every key path the
walk produces, over runs chosen to reach every type, is pinned in ``artifact_shape.txt``:
a path that appears or disappears is a change of format, made with the format version."""

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    Answer,
    AttributionKind,
    CandidateAssessment,
    CheckReading,
    Comparison,
    CompleteResponse,
    Component,
    CoverageAction,
    Document,
    HarnessRevision,
    MalformedRecord,
    ModelCall,
    ModelCallId,
    Observed,
    Operation,
    PrefetchRule,
    PricingBasis,
    RecordOutcome,
    ReportedUsage,
    RunExport,
    Segment,
    Source,
    StratumLevel,
    System,
    SystemKind,
    TreeState,
    attribution_table_digest,
    condition_id,
    cost_of_reported,
    employee_ref,
    export_bytes,
    registration_bytes,
)
from leaveimpact.core.contradictions import Contradiction, ContradictionKind
from leaveimpact.core.ids import WorldVersion, document_id
from leaveimpact.core.run_trace import OperationId
from leaveimpact.evaluator.analysis import analyse
from leaveimpact.evaluator.artifact import (
    ChangedPath,
    EvaluationArtifact,
    EvaluatorRevision,
    StoredRun,
    evaluation_artifact,
)
from leaveimpact.evaluator.artifact_json import artifact_bytes, encode_artifact
from leaveimpact.evaluator.fact_stages import FactStages
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import BASE, NORMAL, PADDED, evaluated, relabelled, truthful
from tests.unit.export_fixture import (
    BASIS,
    ROLE,
    SELECTION,
    agent_export,
    answered,
    answered_call,
    dispatch,
    export_baseline,
    reads,
    run_export,
)
from tests.unit.in_memory_ports import InMemoryWork
from tests.unit.reads_fixture import Systems, reads_of_everything, systems_holding
from tests.unit.registration_fixture import DRAFT as COMMITTED
from tests.unit.registration_fixture import TABLE, decided, light, named
from tests.unit.report_fixture import of_type, without
from tests.unit.stating_fixture import stating_export, truthful_stater_runs
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
COMMIT = "b" * 40
SHAPE = Path(__file__).with_name("artifact_shape.txt")
REVISION = EvaluatorRevision(
    COMMIT, "c" * 40, (ChangedPath("src/leaveimpact/evaluator/tables.py", "1" * 40, None),)
)

DRAFT = light(COMMITTED)
DRAFT_BYTES = registration_bytes(DRAFT)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@dataclass
class _WorkWithBrokenComponents(InMemoryWork):
    def components(self) -> tuple[Observed[Component], ...]:
        self._reach()
        raise MalformedRecord(self.source, "Component/all", "a member id of the wrong shape")


def exported(
    world: SealedWorld,
    scenario: Scenario,
    *down: Source,
    run_id: str,
    systems: Systems | None = None,
) -> RunExport:
    """The real baseline's export of ``scenario`` under the draft."""
    systems = systems_holding(world) if systems is None else systems
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        DRAFT,
        condition_id(down),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return export_baseline(
        investigate(context, systems.ports),
        context,
        provenance,
        run_id=run_id,
        attempt=1,
        duration_ms=1_200,
    )


def stored_runs(world: SealedWorld) -> list[StoredRun]:
    """Runs that end every way an inventory entry can: graded under the normal condition and
    under an outage, limited, excluded by a defect, with a prefetch finding, out of the
    tables for its settings, of another world, and no export at all."""
    one, two, three, four, five, six, seven, *_ = world.scenarios
    broken = systems_holding(world)
    broken.work = _WorkWithBrokenComponents(
        tickets=broken.work.tickets, components_by_id=broken.work.components_by_id
    )
    short = exported(world, five, run_id="run-5")
    short = replace(short, trace=replace(short.trace, operations=short.trace.operations[:5]))
    foreign = exported(world, six, run_id="run-6")
    foreign = replace(
        foreign, record=replace(foreign.record, prefetch_rule=PrefetchRule("another", DIGEST))
    )
    elsewhere = exported(world, seven, run_id="run-7")
    elsewhere = replace(
        elsewhere, context=replace(elsewhere.context, world_version=WorldVersion("f" * 64))
    )
    exports = {
        "runs/1": exported(world, one, run_id="run-1"),
        "runs/2": exported(world, two, Source.JIRA, run_id="run-2"),
        "runs/3": exported(world, three, Source.FRAPPE, run_id="run-3"),
        "runs/4": exported(world, four, run_id="run-4", systems=broken),
        "runs/5": short,
        "runs/6": foreign,
        "runs/7": elsewhere,
    }
    # The baseline on the scenarios whose key lives in prose: plan findings against the oracle.
    for scenario in world.scenarios[7:]:
        name = f"baseline/{scenario.spec.id}"
        exports[name] = exported(world, scenario, run_id=f"run-{scenario.spec.id}")
    exports |= findings_of_every_kind(world)
    runs = [StoredRun(key, f"v-{key}", export_bytes(export)) for key, export in exports.items()]
    return [*runs, StoredRun("runs/8", "v-runs/8", b"not json")]


def findings_of_every_kind(world: SealedWorld) -> dict[str, RunExport]:
    """Exports that reach the rows and the findings the baseline's own runs never produce.
    Their records are a fixture's, so each is out of the tables for its settings and is
    written all the same.

    A truthful report of every scenario gives every row type the world's keys hold; the
    same report without its assessments gives plan findings and coverage gaps; a read by a
    tool nobody declared gives an operation finding; an enumeration short of one employee
    an integrity finding; a model call priced and one left unpriced a cost and a cost
    finding; a stating run whose record lets in what the gates refuse a recheck finding;
    the same run shown a document the world does not seal a level finding; a response
    whose metadata shows an SDK retry a retried send; and an attempt recovered by a process
    on another commit a provenance incident.
    """
    found: dict[str, RunExport] = {}
    for scenario in world.scenarios:
        report = truthful(world, scenario, NORMAL)
        everything = reads_of_everything(world, scenario)
        found[f"truthful/{scenario.spec.id}"] = run_export(
            world, scenario, report, operations=everything
        )
        bare = without(report, *of_type(report, CandidateAssessment))
        found[f"bare/{scenario.spec.id}"] = run_export(world, scenario, bare, operations=everything)
    first = world.scenarios[0]
    found["undeclared"] = run_export(world, first, operations=reads(answered(Source.FRAPPE)))
    short = systems_holding(world)
    bystander = next(
        employee.id
        for employee in world.org.employees
        if employee.id != first.investigated_leave.employee_id
    )
    del short.people.people[bystander]
    found["short"] = exported(world, first, run_id="run-short", systems=short)
    reported: dict[str, object] = {"inputTokens": 300, "outputTokens": 40}
    priced = cost_of_reported(ReportedUsage(reported), SELECTION, BASIS)
    calls = tuple(
        answered_call(number, reported, cost, stop_reason="tool_use")
        for number, cost in ((1, priced), (2, None))
    )
    found["priced"] = agent_export(world, first, calls)
    twice = dispatch(1, CompleteResponse("end_turn", 840, 1), AttributionKind.BEHAVIOUR)
    retried = ModelCall(ModelCallId("call-1"), ROLE, (twice,), Answer(True, (), ()))
    found["retried"] = agent_export(world, first, (retried,))
    whole = run_export(world, first)
    (finished,) = whole.record.timing.segments
    killed = Segment(1, HarnessRevision("e" * 40, TreeState.CLEAN), 300, False)
    timing = replace(whole.record.timing, segments=(killed, replace(finished, number=2)))
    found["mixed"] = replace(whole, record=replace(whole.record, timing=timing))
    stated = stating_export(world, world.scenarios[10], gated=False)
    found["stated"] = stated
    found["strayed"] = replace(
        stated,
        trace=replace(
            stated.trace, operations=tuple(_strayed(op) for op in stated.trace.operations)
        ),
    )
    return found


def _strayed(operation: Operation) -> Operation:
    """``operation`` with any document it returned by id under an id no world seals."""
    outcome = operation.outcome
    if not isinstance(outcome, RecordOutcome) or not isinstance(outcome.record.value, Document):
        return operation
    unsealed = replace(outcome.record.value, id=document_id(999))
    return replace(operation, outcome=RecordOutcome(Observed(unsealed, outcome.record.source)))


def artifact_of(world: SealedWorld) -> EvaluationArtifact:
    return evaluation_artifact(
        world, DRAFT_BYTES, stored_runs(world), {COMMIT: DRAFT_BYTES}, REVISION
    )


@pytest.fixture(scope="module")
def artifact(world: SealedWorld) -> EvaluationArtifact:
    return artifact_of(world)


def named_systems(world: SealedWorld, repeats: int) -> EvaluationArtifact:
    """An artifact whose analysis compares named systems at two corpus levels, ``repeats``
    runs a scenario: one run gives the two-by-two counts and Wilson's interval, two the
    bootstrap's and the repeat-consistency diagnostic.

    Chosen to reach every type the analysis holds. The agent and full context are named
    and the conditional group decided, so the primary is computed; a secondary between the
    agent and the baseline stands in for the registered ones, which need the single-shot
    system this registration format cannot resolve. Each system's wrong reports fall on a
    different stride of scenarios, shifted by the run, so every pair of arms that is
    compared differs by scenario at either count, two systems or two levels of one: a
    difference that is the same in every scenario resamples to one value, and the walk
    would then never reach a comparison's interval. One of the agent's runs met a source
    that contradicted itself, so there is an incident with a run that met it and runs that
    did not.

    The model systems' runs carry a truthful stater's fact stages, grafted on: let in whole
    for one arm and through the gates for another, and the two alternating by scenario for
    the padded full-context arm, so that a stage's interval resolves in an arm, by
    predicate and in a contrast.
    """
    agent, full_context = (
        System(SystemKind.AGENT, "graph"),
        System(SystemKind.FULL_CONTEXT, "all-documents"),
    )
    registration = decided(
        named(DRAFT, agent=agent.variant, full_context=full_context.variant), True
    )
    against_rules = Comparison(
        "correct_whole",
        CheckReading.END_TO_END,
        "normal",
        BASE,
        (SystemKind.AGENT, SystemKind.RULES_ONLY),
        (StratumLevel.TIER,),
    )
    registration = replace(
        registration,
        run_accounting=replace(registration.run_accounting, repeats=repeats),
        statistics=replace(registration.statistics, secondary=(against_rules,)),
    )
    struck = world.scenarios[3]
    contradiction = Contradiction(
        ContradictionKind.RETURNS_DIFFER,
        employee_ref(struck.investigated_leave.employee_id),
        OperationId("op-2"),
        OperationId("op-9"),
        OperationId("op-9"),
    )
    runs: list[Evaluation] = []
    for position, scenario in enumerate(world.scenarios):
        right = evaluated(world, scenario)
        report = truthful(world, scenario, NORMAL)
        actions = of_type(report, CoverageAction)
        wrong = evaluated(world, scenario, claims=without(report, actions[0])) if actions else right
        for number in range(repeats):
            name = f"run-{number}"

            def run(
                missed: bool, system: System | None = None, level: str | None = None
            ) -> Evaluation:
                made = wrong if missed else right  # noqa: B023
                return relabelled(made, run_id=name, system=system, level=level)  # noqa: B023

            turn = position + number
            whole, gated = (
                truthful_stater_runs(gated=layer)[position].metrics.facts
                for layer in (False, True)
            )
            padded_agent = stating(run(turn % 4 == 0, system=agent, level=PADDED), whole)
            if scenario is struck and number == 0:
                padded_agent = replace(padded_agent, contradictions=(contradiction,))
            runs += [
                run(turn % 3 == 0),
                stating(run(False, system=agent), gated),
                padded_agent,
                stating(run(False, system=full_context), whole),
                stating(
                    run(turn % 3 == 1, system=full_context, level=PADDED),
                    gated if turn % 2 else whole,
                ),
            ]
    return replace(artifact_of_none(world), analysis=analyse(world, runs, registration))


def stating(evaluation: Evaluation, facts: FactStages | None) -> Evaluation:
    """``evaluation`` as a run that stated facts with the stages ``facts`` holds."""
    return replace(evaluation, metrics=replace(evaluation.metrics, facts=facts))


def artifact_of_none(world: SealedWorld) -> EvaluationArtifact:
    return evaluation_artifact(world, DRAFT_BYTES, (), {}, REVISION)


def held_to_a_table(world: SealedWorld) -> EvaluationArtifact:
    """An artifact under a registration whose attribution table is set, holding one agent
    run whose record names that table and whose dispatch names a rule it lacks: the one
    way a stored run reaches the attribution check and a finding of it, the committed
    draft's table being pending."""
    registration = registration_bytes(named(DRAFT))
    export = agent_export(world, world.scenarios[0], (answered_call(1, None, None),))
    tabled = replace(
        export, record=replace(export.record, attribution_table=attribution_table_digest(TABLE))
    )
    run = StoredRun("runs/tabled", "v-runs/tabled", export_bytes(tabled))
    return evaluation_artifact(world, registration, (run,), {COMMIT: registration}, REVISION)


def paths(value: object, at: str = "") -> set[str]:
    """Every key path of a JSON value, an array's members under ``[]``."""
    if isinstance(value, dict):
        found: set[str] = set()
        for key, item in cast("dict[str, object]", value).items():
            found |= {f"{at}.{key}".lstrip(".")} | paths(item, f"{at}.{key}".lstrip("."))
        return found
    if isinstance(value, list):
        found = set()
        for item in cast("list[object]", value):
            found |= paths(item, f"{at}[]")
        return found
    return set()


def entry(written: dict[str, object], key: str) -> dict[str, object]:
    inventory = cast("list[dict[str, object]]", written["inventory"])
    return next(item for item in inventory if item["key"] == key)


# --- The bytes ---------------------------------------------------------------------------------


def test_two_evaluations_of_the_same_stored_runs_are_the_same_bytes(
    world: SealedWorld, artifact: EvaluationArtifact
) -> None:
    written = artifact_bytes(artifact)
    assert artifact_bytes(artifact_of(world)) == written
    decoded = json.loads(written)
    assert list(decoded) == [
        "format_version",
        "label",
        "evaluated_by_changed_code",
        "world",
        "evaluator",
        "registration",
        "inventory",
        "analysis",
    ]
    assert (decoded["format_version"], decoded["label"]) == (6, "development")
    assert decoded["world"]["truth_manifest"] == {
        "key": world.truth_manifest.key,
        "version_id": world.truth_manifest.version_id,
        "digest": world.truth_manifest.digest,
    }
    assert decoded["evaluator"]["changed"] == [
        {"path": "src/leaveimpact/evaluator/tables.py", "before": "1" * 40, "after": None}
    ]
    assert decoded["registration"]["declared"] == {"amends": None, "prior_full_set_results": False}


# --- What is written differently from its type -------------------------------------------------


def test_a_run_is_written_as_its_outcome_and_findings_and_nothing_recomputable(
    world: SealedWorld, artifact: EvaluationArtifact
) -> None:
    written = encode_artifact(artifact)
    graded = entry(written, "runs/1")
    run = cast("dict[str, dict[str, object]]", graded["run"])
    assert list(run) == [
        "assigned",
        "level",
        "outcome",
        "operation_findings",
        "prefetch",
        "fact_recheck",
        "level_check",
        "contradiction_not_failed",
        "ending",
        "attribution",
        "retried_sends",
    ]
    assert run["ending"] == {
        "segments": 1,
        "timing_complete": True,
        "elapsed_ms": 1_200,
        "commits": [COMMIT],
        "findings": [],
    }
    # The draft's attribution table is pending: held to none, which is not an empty finding.
    assert run["attribution"] is None and run["retried_sends"] == []
    assert run["fact_recheck"] == {"admissions": 0, "composition_evaluated": True, "findings": []}
    assert run["level_check"] == {"level": "base", "documents": 0, "findings": []}
    assert run["contradiction_not_failed"] is False
    assert run["level"] == "base"
    outcome = run["outcome"]
    assert (outcome["kind"], outcome["condition"]) == ("graded", {"unreachable": []})
    held = artifact.inventory[0].evaluation
    assert held is not None
    standings = cast("list[dict[str, object]]", outcome["standings"])
    assert len(standings) > 0
    assert set(standings[0]) == {"claim_id", "claim_type", "standing", "reason"}
    assert {standing["standing"] for standing in standings} == {"reproduced"}
    assert run["prefetch"] == {"evaluated": True, "findings": []}
    assert graded["cost"] is not None and (graded["disposition"], graded["label"]) == (
        "eligible",
        "development",
    )
    # Nothing the stored export gives back is written a second time.
    for recomputable in ("proof", "premises", "citations", "retrieval", "contribution"):
        assert not any(recomputable in path.split(".") for path in paths(written))

    outage = cast("dict[str, dict[str, object]]", entry(written, "runs/2")["run"])
    assert outage["assigned"] == {"unreachable": ["jira"]}
    assert outage["outcome"]["condition"] == {"unreachable": ["jira"]}


def test_each_way_a_run_ended_is_written_with_its_reason(artifact: EvaluationArtifact) -> None:
    written = encode_artifact(artifact)

    def outcome(key: str) -> dict[str, object]:
        run = cast("dict[str, dict[str, object]]", entry(written, key)["run"])
        return run["outcome"]

    limited = outcome("runs/3")
    assert (limited["kind"], limited["reason"]) == ("limited", "unreadable_leave")
    # An abstention is an empty report that was replayed: an empty list, not null.
    assert (limited["standings"], limited["mixed"]) == ([], [])
    excluded = outcome("runs/4")
    assert (excluded["kind"], excluded["reason"]) == ("excluded", "failed_by_defect")
    assert set(excluded) == {"kind", "header", "reason"}

    short = cast("dict[str, dict[str, object]]", entry(written, "runs/5")["run"])
    assert short["prefetch"] == {
        "evaluated": True,
        "findings": [{"kind": "missing", "step": 5, "operation": None}],
    }
    foreign = entry(written, "runs/6")
    assert (foreign["disposition"], foreign["differing"]) == ("settings_differ", ["prefetch"])
    assert cast("dict[str, object]", foreign["run"])["prefetch"] == {
        "evaluated": False,
        "findings": [],
    }
    elsewhere = entry(written, "runs/7")
    assert elsewhere["disposition"] == "another_world"
    assert elsewhere["run"] is None and elsewhere["cost"] is not None
    nothing = entry(written, "runs/8")
    assert (nothing["disposition"], nothing["run"], nothing["cost"]) == (
        "not_an_export",
        None,
        None,
    )


# --- What the walk refuses ---------------------------------------------------------------------


def test_a_value_with_no_rule_and_a_number_that_is_not_finite_are_refused(
    artifact: EvaluationArtifact,
) -> None:
    stranger = replace(REVISION, changed=(cast("ChangedPath", object()),))
    with pytest.raises(TypeError, match="no rule for object"):
        artifact_bytes(replace(artifact, evaluator=stranger))
    endless = replace(REVISION, changed=(ChangedPath(cast("str", float("inf")), None, None),))
    with pytest.raises(ValueError, match="finite numbers"):
        artifact_bytes(replace(artifact, evaluator=endless))


# --- The pinned shape --------------------------------------------------------------------------


def test_every_key_path_the_walk_writes_is_the_pinned_one(
    world: SealedWorld, artifact: EvaluationArtifact
) -> None:
    written: set[str] = set()
    for held in (
        artifact,
        named_systems(world, 1),
        named_systems(world, 2),
        held_to_a_table(world),
    ):
        written |= paths(encode_artifact(held))
    pinned = set(SHAPE.read_text(encoding="utf-8").split())
    assert written == pinned, (
        "the artifact's written form changed: a path that appears or disappears is a change "
        "of format, made with ARTIFACT_FORMAT_VERSION and this pin together.\n"
        f"new: {sorted(written - pinned)}\ngone: {sorted(pinned - written)}"
    )
