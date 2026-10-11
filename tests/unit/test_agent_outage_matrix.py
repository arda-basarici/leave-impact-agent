"""The registered outage injected over the ports, every system under every registered condition,
model-free (the outage step, fork 5 as amended by the external read).

The agent runs under the scripted two-call turns; the two one-call baselines run their real
turns over the reader's assets with the forced call answered by a script, so their exports
have the registered shape, one logical call and no model-origin read (the external read of
group 1). Each case states its assignment, the condition the trace should show and the
exposure the evaluator should read, apart: under ``corpus_down`` rules only reads no document
and an agent that never searches observes the normal condition with unexercised exposure, so
assignment and observation are not asked to agree. What every case asserts is that the record
agrees with the trace (the harness's own derived condition is the one the evaluator derives,
no mixed source) and that the exposure reads as expected; the shape of the run (its
operations, its sends, its harness read) is asserted where the condition decides it. Two agent
cases request the failed source through scripted turns: a call against a stopped source is
skipped and never made, and a search under a corpus outage is recorded unreachable and stops
the source. A recovering worker injects the outage from the admission again and makes no
vendor call. The log refuses a harness read after the derived universe abstention, a history
the preparation node never writes and the append had accepted (group 2's external read).

The conditions are the registration's own, read from the committed draft, so a condition
added there is a case here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.conclusion import Abstention
from leaveimpact.agent.execution import ReadPorts, ports_under
from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.graph import NoPreparation, Preparation, ReviewPayload, TurnRequest
from leaveimpact.agent.log_events import (
    CountStarted,
    FrozenInputs,
    HarnessReadKey,
    LoggedEvent,
    OperationEvent,
    OperationResult,
    OperationSkip,
    PrefetchKey,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import (
    AttemptState,
    Refused,
    derived_abstention,
    fold,
    next_state,
)
from leaveimpact.agent.one_call import OneCallTurns
from leaveimpact.agent.preparations import FullContextPreparation, SingleShotPreparation
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.agent.worker import (
    AutomaticApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core import (
    HarnessOrigin,
    HarnessRevision,
    ModelOrigin,
    OutageAssignment,
    PrefetchOrigin,
    PricingBasis,
    Role,
    RunCondition,
    RunExport,
    Source,
    TreeState,
    UndispatchedReason,
    UnreachableOutcome,
    condition_id,
    decode_registration_bytes,
)
from leaveimpact.core.read_condition import observed_condition
from leaveimpact.core.run_record import System
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.source_discipline import Ended
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.export_fixture import export_baseline
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world
from tests.unit.worker_support import (
    ContentScriptedClient,
    ScriptedClient,
    ScriptedCounter,
    ScriptedTurns,
    settled,
)

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1
COMMIT = "b" * 40
REGISTRATION = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)
CONDITIONS: tuple[frozenset[Source], ...] = tuple(
    condition.unreachable for condition in REGISTRATION.outage.conditions
)
"""The five registered conditions, by the sources they schedule out."""


def condition_name(down: frozenset[Source]) -> str:
    return condition_id(down)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


# --- What a case expects, and how it is read off an evaluation -------------------------------


@dataclass(frozen=True, slots=True)
class Expected:
    """One cell's forecast: the condition the trace shows and whether the outage was met."""

    observed: RunCondition
    exercised: bool


def expected_for(down: frozenset[Source], *, reads_corpus: bool) -> Expected:
    """The forecast of a run assigned ``down``: every scheduled-out source the run reads is
    met and observed; the corpus is read only by a system that does (the one-call baselines'
    preparation, an agent that searches), never by the prefetch."""
    met = frozenset(source for source in down if source is not Source.CORPUS or reads_corpus)
    return Expected(RunCondition.all_reachable().without(*met), met == down)


def exposure_of(evaluation: Evaluation) -> bool:
    """Whether every scheduled-out source was met in the trace, as the degraded table reads
    it (``evaluator.diagnostics``): the unreachable rows of the discipline against the
    assignment."""
    met = {
        row.source
        for row in evaluation.metrics.discipline.operations
        if row.ended is Ended.UNREACHABLE
    }
    scheduled_out = frozenset(Source) - evaluation.assigned.reachable
    return scheduled_out <= met


def assert_record_agrees_with_trace(
    world: SealedWorld, export: RunExport, down: frozenset[Source], expected: Expected
) -> Evaluation:
    """The three assertions every cell makes: the assignment recorded is the one given, the
    record's observed condition is the trace's with no mixed source, and the exposure reads
    as forecast; the evaluation, for a case that asserts more."""
    assert export.record.outage.scheduled_unreachable == down
    observed = observed_condition(export.trace.operations)
    assert not observed.is_mixed
    assert export.record.observed_condition == observed.condition == expected.observed
    evaluation = evaluate_run(world, export)
    assert evaluation.assigned == RunCondition.all_reachable().without(*down)
    assert exposure_of(evaluation) is expected.exercised
    return evaluation


# --- Rules only, through the function the runner will call ----------------------------------


def provenance(down: frozenset[Source]) -> RunProvenance:
    return rules_only_provenance(
        REGISTRATION,
        condition_id(down),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis("a" * 64, "USD", date(2026, 9, 1), ()),
    )


@pytest.mark.parametrize("down", CONDITIONS, ids=condition_name)
def test_rules_only_under_each_registered_condition(
    world: SealedWorld, scenario: Scenario, down: frozenset[Source]
) -> None:
    context = world.context_of(scenario)
    result = investigate(context, ports_under(systems_holding(world).ports, down))
    export = export_baseline(result, context, provenance(down), run_id="run-1", attempt=1)
    expected = expected_for(down, reads_corpus=False)
    assert_record_agrees_with_trace(world, export, down, expected)
    if Source.FRAPPE in down:
        assert result.abstention is not None and len(result.operations) == 1
    else:
        assert result.abstention is None and result.failure is None
    assert all(isinstance(op.origin, PrefetchOrigin) for op in export.trace.operations)


# --- The three model systems, through the worker ----------------------------------------------


@dataclass
class Bench:
    """One worker over a fresh in-memory log holding an admission under the case's
    assignment, the system's turns and preparation, the scripted client and counter."""

    log: MemoryLog
    inputs: FrozenInputs
    turns: PreconditionedTurns | OneCallTurns
    preparation: Preparation
    client: ScriptedClient | ContentScriptedClient
    ports: Any
    counter: ScriptedCounter = field(default_factory=ScriptedCounter)

    def work(self) -> WorkerEnding:
        worker = Worker(
            self.log,
            WorkerConfiguration.of(self.inputs),
            cases.REVISION,
            "launch-1",
            RULES,
            self.turns,
            self.preparation,
            self.client,
            self.counter,
            self.ports,
            AutomaticApproval(),
            InMemorySaver(),
            sleep=lambda seconds: None,
        )
        return worker.work(RUN, ATTEMPT, nonce=f"nonce-{uuid4().hex[:8]}")

    def events(self) -> tuple[LoggedEvent, ...]:
        return self.log.events(RUN, ATTEMPT)

    def export(self) -> RunExport:
        return export_of(self.log.load(RUN, ATTEMPT, rules=RULES))


Script = Callable[[Any], tuple[ScriptedTurns, ScriptedClient]]


@dataclass(frozen=True, slots=True)
class PreconditionedTurns:
    """The scripted turns behind the preconditions the real turns apply: after an abstention
    the system asks no call (``agent.turns``, ``agent.one_call``), so the stand-in asks none
    either; otherwise the script's bodies as written."""

    inner: ScriptedTurns

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None:
        if derived_abstention(state) is not None:
            return None
        return self.inner.request_for(state, call)

    def payload_for(self, state: AttemptState) -> ReviewPayload:
        return self.inner.payload_for(state)


def one_call_script(world: SealedWorld) -> tuple[OneCallTurns, ContentScriptedClient]:
    """The real one-call turns over the reader's assets, the forced fact call answered with
    the planted requirement stated truthfully (the one-call tests' bench): one logical call,
    no model-origin read, the preconditions the turns apply themselves."""
    planted = support.a_planted_requirement(world)
    answer = support.answered(
        support.fact_tool("tu_final", histories.entry_of(planted.stated)), stop_reason="tool_use"
    )
    return OneCallTurns(load_prompt_assets(Role.READER)), ContentScriptedClient((answer,))


MODEL_SYSTEMS: dict[str, tuple[System, Callable[[], Preparation]]] = {
    "agent": (histories.AGENT, NoPreparation),
    "single_shot": (histories.SINGLE_SHOT, SingleShotPreparation),
    "full_context": (histories.FULL_CONTEXT, FullContextPreparation),
}


def bench(
    world: SealedWorld,
    system: str,
    down: frozenset[Source],
    *,
    script: Script = support.two_call_script,
    events: Sequence[LoggedEvent] | None = None,
    ports: ReadPorts | None = None,
) -> Bench:
    """The ``system``'s run of the golden world's first scenario admitted under ``down``,
    the ports injected as the composition root injects them, over ``events`` instead of a
    fresh admission when given. The agent runs ``script`` behind the preconditions; a
    one-call baseline runs its real turns under the reader's inputs."""
    admitted, preparation = MODEL_SYSTEMS[system]
    context = world.context_of(world.scenarios[0])
    assignment = OutageAssignment(down, cases.DIGEST)
    turns: PreconditionedTurns | OneCallTurns
    client: ScriptedClient | ContentScriptedClient
    if system == "agent":
        inputs = replace(support.admitted_inputs(context, system=admitted), outage=assignment)
        scripted, client = script(context)
        turns = PreconditionedTurns(scripted)
    else:
        inputs = replace(support.reader_inputs(context, admitted), outage=assignment)
        turns, client = one_call_script(world)
    log = MemoryLog()
    log.seed(tuple(events) if events is not None else support.admission(inputs))
    given = systems_holding(world).ports if ports is None else ports
    return Bench(log, inputs, turns, preparation(), client, ports_under(given, down))


def harness_reads(export: RunExport) -> list[Any]:
    return [op for op in export.trace.operations if isinstance(op.origin, HarnessOrigin)]


@pytest.mark.parametrize("down", CONDITIONS, ids=condition_name)
@pytest.mark.parametrize("system", list(MODEL_SYSTEMS))
def test_each_model_system_under_each_registered_condition(
    world: SealedWorld, system: str, down: frozenset[Source]
) -> None:
    """The two-call script asks the people system only, so the agent never reads the
    corpus; the one-call baselines read it in their preparation. Under the HR system's
    outage every system abstains at its opening read with no send and no call; under the
    others the agent completes with its two sends, and a one-call baseline with its one
    logical call and no model-origin read, its harness read made and, under the corpus's
    outage, recorded unreachable with the call still made (step 12, fork 7)."""
    made = bench(world, system, down)
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    export = made.export()
    reads_corpus = system != "agent" and Source.FRAPPE not in down
    expected = expected_for(down, reads_corpus=reads_corpus)
    evaluation = assert_record_agrees_with_trace(world, export, down, expected)
    assert evaluation.level == "base"
    reads = harness_reads(export)
    by_model = [op for op in export.trace.operations if isinstance(op.origin, ModelOrigin)]
    if Source.FRAPPE in down:
        assert len(made.client.sends) == 0 and export.trace.model_calls == ()
        assert reads == [] and by_model == []
        assert len(export.trace.operations) == 1
        assert isinstance(export.trace.operations[0].outcome, UnreachableOutcome)
        return
    if system == "agent":
        assert len(made.client.sends) == 2 and len(export.trace.model_calls) == 2
        assert reads == []
        return
    assert len(made.client.sends) == 1 and len(export.trace.model_calls) == 1
    assert by_model == [], "a one-call baseline makes no model-origin read"
    (read,) = reads
    assert read.tool == ("search" if system == "single_shot" else "documents")
    if Source.CORPUS in down:
        assert isinstance(read.outcome, UnreachableOutcome)
    else:
        assert not isinstance(read.outcome, UnreachableOutcome)


# --- The agent requesting the failed source ---------------------------------------------------


def script_asking(*reads: tuple[str, str, dict[str, object]]) -> Script:
    """The two-call script with the first answer's reads replaced by ``reads`` (an id, a tool,
    its arguments); the second answer reads nothing, as the reference does."""

    def script(context: Any) -> tuple[ScriptedTurns, ScriptedClient]:
        bodies = (support.body_for(1), support.body_for(2))
        answers = {
            support.request_digest(bodies[0]): (
                support.answered(
                    support.text("Reading what the scenario needs."),
                    *(
                        support.tool_use(identifier, tool, arguments)
                        for identifier, tool, arguments in reads
                    ),
                    stop_reason="tool_use",
                ),
            ),
            support.request_digest(bodies[1]): (
                support.answered(support.text("Nothing further.")),
            ),
        }
        return ScriptedTurns(bodies), ScriptedClient(answers)

    return script


def test_an_agents_call_against_the_stopped_tracker_is_skipped_and_never_made(
    world: SealedWorld, scenario: Scenario
) -> None:
    """Under ``jira_down`` the prefetch met the outage and stopped the source; the model's
    work-item read is a logged skip with the unreachable reason, no operation is made for
    it, and the exposure is exercised by the prefetch's reads alone."""
    item = next(i for s in world.scenarios for i in s.owned.work_items).entity.id
    down = frozenset({Source.JIRA})
    made = bench(
        world, "agent", down, script=script_asking(("tu_item", "work_item", {"id": str(item)}))
    )
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    skips = [
        e.event.resolution
        for e in made.events()
        if isinstance(e.event, OperationEvent) and isinstance(e.event.resolution, OperationSkip)
    ]
    assert skips == [OperationSkip(UndispatchedReason.SOURCE_UNREACHABLE)]
    export = made.export()
    assert [op.tool for op in export.trace.operations if isinstance(op.origin, ModelOrigin)] == []
    assert_record_agrees_with_trace(world, export, down, expected_for(down, reads_corpus=False))


def test_an_agents_search_under_the_corpus_outage_is_recorded_unreachable_and_exercises_it(
    world: SealedWorld,
) -> None:
    """Under ``corpus_down`` the prefetch meets nothing; the model's search is the read that
    meets the outage: recorded unreachable, the source stopped, the exposure exercised, and
    the observed condition is the assigned one."""
    down = frozenset({Source.CORPUS})
    made = bench(
        world,
        "agent",
        down,
        script=script_asking(("tu_search", "search", {"query": "handover", "limit": 5})),
    )
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    export = made.export()
    searched = [op for op in export.trace.operations if isinstance(op.origin, ModelOrigin)]
    assert [op.tool for op in searched] == ["search"]
    assert isinstance(searched[0].outcome, UnreachableOutcome)
    assert_record_agrees_with_trace(world, export, down, expected_for(down, reads_corpus=True))


# --- Recovery under an injected outage --------------------------------------------------------


class _Untouched:
    """A reader no call may reach: behind ``ScheduledOut`` on recovery, any attribute read is
    the vendor call the wrapper exists to prevent."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the vendor reader was asked for {name!r} under an injected outage")


def test_a_recovering_worker_injects_the_outage_from_the_admission_and_makes_no_vendor_call(
    world: SealedWorld,
) -> None:
    """Fork 2 and the amended fork 9: the reference run under ``jira_down`` is cut after its
    prefetch; the recovering worker composes its ports from the same admission with the
    work reader behind the wrapper a spy that fails on any call. The recovery completes in
    its second generation with every settled event the reference's."""
    down = frozenset({Source.JIRA})
    reference = bench(world, "agent", down)
    reference.work()
    whole = reference.events()
    first_count = next(i for i, e in enumerate(whole) if isinstance(e.event, CountStarted))
    prefix = whole[:first_count]
    spied = replace(systems_holding(world).ports, work=_Untouched())  # type: ignore[arg-type]
    recovering = bench(world, "agent", down, events=prefix, ports=spied)
    ending = recovering.work()
    assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2
    recovered = recovering.events()
    assert recovered[:first_count] == prefix
    assert settled(recovered) == settled(whole)
    assert recovering.export().record.observed_condition == RunCondition.all_reachable().without(
        Source.JIRA
    )


def test_a_harness_read_after_the_universe_abstention_is_refused_at_the_append(
    world: SealedWorld,
) -> None:
    """Group 2's external read: the preparation node asks the derived abstention before it
    issues a read and the log had not, so a worker reading past the abstention could record
    the read and an export would hold a count of one with no dispatch, which the membership
    check cannot tell from an ended run. Over the full-context run's own events with the
    employee enumeration made unreachable, the abstention is derived and the read the run then
    made is refused by name; the identical re-append of a held read is received as before."""
    reference = bench(world, "full_context", frozenset())
    reference.work()
    before: list[LoggedEvent] = []
    read: LoggedEvent | None = None
    for logged in reference.events():
        event = logged.event
        if isinstance(event, OperationEvent) and isinstance(event.key, HarnessReadKey):
            read = logged
            break
        if isinstance(event, OperationEvent) and isinstance(event.key, PrefetchKey):
            result = event.resolution
            assert isinstance(result, OperationResult)
            if result.tool == "employees":
                unreachable = UnreachableOutcome(Source.FRAPPE, "made unreachable by the test")
                resolution = replace(result, outcome=unreachable)
                logged = replace(logged, event=replace(event, resolution=resolution))
        before.append(logged)
    assert read is not None, "the full-context run issues its harness read"
    state = fold(before, RULES)
    assert derived_abstention(state) is Abstention.UNIVERSE_NOT_COVERED
    assert next_state(state, read, RULES) == Refused(
        "a harness read after the run's abstention: universe_not_covered"
    )
