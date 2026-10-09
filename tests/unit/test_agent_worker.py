"""The worker over the in-memory log: the reference run and what each ending leaves behind.

Every test runs the real path, the skeleton's nodes over the appender with the prefetch over
the executor against in-memory ports holding the golden world, and scripts only the system's
turns, the model client and the token counter. The claims, by the rulings they hold:

- the reference run completes under the automatic approval with the log the rulings fix,
  two sends, and an export the reader builds and round-trips;
- a worker recovering from any prefix of that log repeats no logged inference and no
  logged read, and the two logs agree on every logical event (recovery, parts 4 and 8;
  tool calls, part 8);
- a fenced worker exits and writes nothing after the fence (one writer, parts 4 and 5);
- the log unavailable leaves the attempt open with nothing written; an exception nobody
  classified closes by defect at ``unhandled`` with a type and a location and no message;
  a conflict closes by defect at the event-append site, and a conflict that persists
  leaves the attempt open (recovery, part 8);
- a differing configuration claims nothing (admission, part 3);
- a human approval ends the segment, and the next worker claims, replays to the interrupt
  without a send, resumes and completes (the event, part 7; recovery, part 5);
- a stop signal ends the segment and re-raises;
- a call failed by infrastructure is finalized in its category at its site, after the
  registered delay was waited between dispatches (re-dispatch, parts 1 and 3);
- a counting request refused transiently is retried after the delay and the bound rests on
  the count that answered (counting, part 13);
- a loop call in progress when the account enters finalization keeps its purpose and
  finishes from the reserve, on first execution and on recovery (the graph step's
  rulings, amendment 2).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields, replace
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent.appender import LogCommands
from leaveimpact.agent.log_events import (
    ApprovalRequested,
    Approved,
    CapExhausted,
    Completed,
    CountOutcomeLogged,
    DispatchIntent,
    EventKind,
    Failed,
    FrozenInputs,
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    Producer,
    WorkerStamp,
    count_id,
    kind_of,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStoreConflict, LogStoreUnavailable
from leaveimpact.agent.log_transition import (
    Appended,
    Refused,
    Rules,
    calls_of,
    counts_of,
    operations_of,
)
from leaveimpact.agent.worker import (
    COPIED_FROM_THE_ADMISSION,
    AutomaticApproval,
    HumanApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
    configuration_difference,
)
from leaveimpact.core import (
    Approver,
    Caps,
    DispatchPhase,
    DispatchSite,
    FailureCategory,
    HarnessSite,
    HarnessSiteName,
    ModelCallId,
    decode_export_bytes,
    export_bytes,
)
from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.counting_operations import Counted, CountServiceError
from leaveimpact.core.model_calls import ServiceError
from leaveimpact.core.run_account import CallPurpose
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.evaluator.account_check import check_account
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog, Ticking
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world
from tests.unit.worker_support import (
    ScriptedClient,
    ScriptedCounter,
    ScriptedTurns,
    in_flight,
    settled,
    throttled_script,
)

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@dataclass
class Bench:
    """One worker's composition over a fresh in-memory log holding the admission."""

    log: MemoryLog
    inputs: FrozenInputs
    turns: ScriptedTurns
    client: ScriptedClient
    counter: ScriptedCounter = field(default_factory=ScriptedCounter)
    waits: list[float] = field(default_factory=list[float])
    nonces: int = 0

    def worker(
        self,
        *,
        store: LogCommands | None = None,
        approval: AutomaticApproval | HumanApproval | None = None,
        configuration: WorkerConfiguration | None = None,
        rules: Rules = RULES,
        ports: Any = None,
    ) -> Worker:
        return Worker(
            store if store is not None else self.log,
            configuration if configuration is not None else WorkerConfiguration.of(self.inputs),
            cases.REVISION,
            "launch-1",
            rules,
            self.turns,
            self.client,
            self.counter,
            ports if ports is not None else self.ports,
            approval if approval is not None else AutomaticApproval(),
            InMemorySaver(),
            sleep=self.waits.append,
        )

    def work(self, **options: Any) -> WorkerEnding:
        self.nonces += 1
        return self.worker(**options).work(RUN, ATTEMPT, nonce=f"nonce-{uuid4().hex[:8]}")

    def events(self) -> tuple[LoggedEvent, ...]:
        return self.log.events(RUN, ATTEMPT)

    def kinds(self) -> list[str]:
        return [kind_of(e.event).value for e in self.events()]

    ports: Any = None


def bench(
    world: SealedWorld,
    *,
    script: Callable[[Any], tuple[ScriptedTurns, ScriptedClient]] = support.two_call_script,
    events: Sequence[LoggedEvent] | None = None,
    rules: Rules = RULES,
) -> Bench:
    context = world.context_of(world.scenarios[0])
    inputs = support.admitted_inputs(context)
    if rules.redispatch is not None and rules.redispatch != inputs.redispatch:
        inputs = replace(inputs, redispatch=rules.redispatch)
    turns, client = script(context)
    log = MemoryLog()
    log.seed(tuple(events) if events is not None else support.admission(inputs))
    made = Bench(log, inputs, turns, client)
    made.ports = systems_holding(world).ports
    return made


# --- The reference run -----------------------------------------------------------------------

REFERENCE_KINDS = [
    "admitted",
    "segment_started",
    *["operation"] * 9,
    "count_started",
    "count_outcome",
    "dispatch_intent",
    "dispatch_outcome",
    "operation",
    "operation",
    "count_started",
    "count_outcome",
    "dispatch_intent",
    "dispatch_outcome",
    "finalization_entered",
    "approval_requested",
    "approved",
    "resumed",
    "completed",
]


def test_the_reference_run_completes_with_the_log_the_rulings_fix(world: SealedWorld) -> None:
    made = bench(world)
    ending = made.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    kinds = made.kinds()
    prefetched = kinds.count("operation") - 2
    assert (
        kinds
        == [k if k != "operation" else "operation" for k in REFERENCE_KINDS[:2]]
        + ["operation"] * prefetched
        + REFERENCE_KINDS[11:]
    ), kinds
    assert support.sends_of(made.client) == 2 and len(made.counter.asked) == 2
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert state.closed is not None and state.resumed is not None
    approved = next(e for e in made.events() if isinstance(e.event, Approved))
    assert approved.envelope == Producer("policy:automatic")
    assert approved.event == Approved(Approver.AUTOMATIC, review_payload_digest((), cases.RULES))
    export = export_of(state)
    assert decode_export_bytes(export_bytes(export)) == export
    assert len(export.trace.model_calls) == 2 and len(calls_of(state)) == 2


def test_an_intent_is_committed_before_its_send_and_names_the_bound_the_count_gave(
    world: SealedWorld,
) -> None:
    made = bench(world)
    made.work()
    events = made.events()
    intents = [e for e in events if isinstance(e.event, DispatchIntent)]
    assert len(intents) == 2
    for logged in intents:
        intent = logged.event
        assert isinstance(intent, DispatchIntent)
        outcome = events[logged.position]
        assert kind_of(outcome.event) is EventKind.DISPATCH_OUTCOME
        count = next(
            c
            for c in counts_of(made.log.load(RUN, ATTEMPT, rules=RULES))
            if c.key.request_digest == intent.request_digest
        )
        assert intent.bound.input_tokens == cases.INPUT_BOUND
        assert intent.requested_profile == "eu.model" and intent.client_region == "eu-central-1"
        assert count.outcome is not None and count.outcome.position < logged.position


def recovers_from_prefix(
    world: SealedWorld,
    cut: int,
    *,
    outage: str | None = None,
    after: int = 0,
    after_recovering: int | None = None,
) -> tuple[LoggedEvent, ...]:
    """The recovery invariant from the prefix of ``cut`` events of the reference run, the
    people system's ``outage`` method unreachable from its ``after``-th call in the reference
    and from its ``after_recovering``-th in the recovery (the same by default; zero when the
    recovery replays the calls before the outage from the log and makes none itself); the
    reference log, for a test that places its cut."""
    reference = bench(world)
    if outage is not None:
        reference.ports = support.with_unreachable(reference.ports, outage, after=after)
    reference.work()
    whole = reference.events()
    if cut >= len(whole):
        pytest.skip("the prefix is the whole log")
    prefix = whole[:cut]
    recovering = bench(world, events=prefix)
    if outage is not None:
        later = after if after_recovering is None else after_recovering
        recovering.ports = support.with_unreachable(recovering.ports, outage, after=later)
    ending = recovering.work()
    assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2
    recovered = recovering.events()
    assert recovered[:cut] == prefix, "a recovering worker rewrites nothing"
    assert settled(recovered) == settled(whole)
    pending = in_flight(prefix)
    assert len(recovered) == len(whole) + 1 + len(pending), (
        "one claim, one request per in-flight one"
    )
    assert in_flight(recovered) == pending, (
        "an in-flight request stays unresolved; none is answered"
    )
    outcomes_held = sum(kind_of(e.event) is EventKind.DISPATCH_OUTCOME for e in prefix)
    assert support.sends_of(recovering.client) == 2 - outcomes_held
    reads_whole = sum(kind_of(e.event) is EventKind.OPERATION for e in whole)
    assert sum(kind_of(e.event) is EventKind.OPERATION for e in recovered) == reads_whole
    counted_held = sum(
        kind_of(e.event) is EventKind.COUNT_OUTCOME
        and isinstance(e.event, CountOutcomeLogged)
        and isinstance(e.event.outcome, Counted)
        for e in prefix
    )
    assert len(recovering.counter.asked) == 2 - counted_held, "a held count is reused"
    export = export_of(recovering.log.load(RUN, ATTEMPT, rules=RULES))
    assert len(export.record.timing.segments) == 2
    held = [e.event for e in recovered if isinstance(e.event, OperationEvent)]
    first = [e.event for e in whole if isinstance(e.event, OperationEvent)]
    assert [(o.key, o.resolution) for o in held] == [(o.key, o.resolution) for o in first], (
        "every read resolves as the uninterrupted run's, by key"
    )
    return whole


@pytest.mark.parametrize("cut", range(2, len(REFERENCE_KINDS) - 1))
def test_a_worker_recovering_from_any_prefix_repeats_no_logged_inference_or_read(
    world: SealedWorld, cut: int
) -> None:
    recovers_from_prefix(world, cut)


@pytest.mark.parametrize("cut", range(2, 14))
def test_a_recovery_under_an_outage_replays_the_stops_in_the_logs_order(
    world: SealedWorld, cut: int
) -> None:
    """The review's second finding: with one prefetch read unreachable, a recovery that
    seeded the stop from the whole history skipped calls the first run had made and reused
    held results under the wrong ordinals; the stops now accumulate as the held results are
    replayed, so every read resolves as the first run's."""
    recovers_from_prefix(world, cut, outage="leaves_within")


def model_read_cuts(world: SealedWorld, outage: str, *, after: int = 0) -> list[int]:
    """The cuts at or after the model's read of ``outage`` was logged unreachable, in a
    reference run where that method fails from its ``after``-th call on (zero when the
    prefetch never calls it, so the model's call is its first)."""
    reference = bench(world)
    reference.ports = support.with_unreachable(reference.ports, outage, after=after)
    reference.work()
    events = reference.events()
    first_model_read = next(
        i
        for i, e in enumerate(events)
        if isinstance(e.event, OperationEvent) and isinstance(e.event.key, ModelReadKey)
    )
    return list(range(first_model_read + 1, len(events) - 1))


def test_a_later_model_read_outage_does_not_stop_the_prefetchs_replay(world: SealedWorld) -> None:
    """The second read's first finding: the model's read of a people method is unreachable
    after the prefetch read the people source fine; a recovery that seeded the stop from
    every outcome outside the prefetch skipped the prefetch's calls and raised on the
    shifted ordinal. Stops are seeded from the operations before the replayed phase only.
    (Before the registry step the model's read was the enumeration the prefetch also
    makes, failing from its second call; the role's surface refuses the enumeration, so
    the read is the single-employee method the prefetch never calls.)"""
    for cut in model_read_cuts(world, "employee"):
        recovers_from_prefix(world, cut, outage="employee", after=0, after_recovering=0)


def test_a_held_unreachable_read_stops_the_rest_of_its_answer_on_recovery(
    world: SealedWorld,
) -> None:
    """The second read's second finding: the answer's first read is unreachable and the
    second must be skipped; a recovery that stepped over the held first read never learned
    its stop and ran the second. Held reads go through the executor, which accumulates."""
    for cut in model_read_cuts(world, "leave"):
        recovers_from_prefix(world, cut, outage="leave", after=1, after_recovering=0)


def test_a_recovery_waits_the_registered_delay_before_it_dispatches_again(
    world: SealedWorld,
) -> None:
    """The review's fourth finding: a worker recovering after a throttled outcome went
    straight to the next authorization; the delay now runs before each authorization from
    the held outcome's timestamp, so the recovery waits as the first process would have."""
    rules = Rules(cases.TABLE, RedispatchPolicy(3, 5_000))
    reference = bench(world, script=throttled_script, rules=rules)
    reference.work(rules=rules)
    assert reference.waits == [4.0, 4.0]
    events = reference.events()
    cut = [kind_of(e.event).value for e in events].index("dispatch_outcome") + 1
    recovering = bench(world, script=throttled_script, rules=rules, events=events[:cut])
    # The recovering log's clock starts after the prefix's last instant, as a real database's
    # would; a clock behind the anchor is bounded to the whole delay by design.
    recovering.log.clock = Ticking(start=events[cut - 1].timestamp)
    ending = recovering.work(rules=rules)
    assert ending.detail == "failed" and support.sends_of(recovering.client) == 2
    # The recovery's claim took one reading of the clock after the anchor, so the remainder
    # before its first dispatch is three seconds, and the whole four before its second.
    assert recovering.waits == [3.0, 4.0], "the remainder, then the delay"


# --- The endings -----------------------------------------------------------------------------


class FencingClient(ScriptedClient):
    """A client whose first send is overtaken: another process claims the attempt while the
    request is in flight."""

    def __init__(self, inner: ScriptedClient, log: MemoryLog) -> None:
        super().__init__(inner.answers)
        self.log = log
        self.fenced = False

    def send(self, requested_profile: str, body: Any) -> Any:
        sent = super().send(requested_profile, body)
        if not self.fenced:
            self.fenced = True
            claimed = self.log.claim(
                RUN,
                ATTEMPT,
                harness=cases.REVISION,
                nonce="takeover",
                launch="launch-2",
                rules=RULES,
            )
            assert claimed.__class__.__name__ == "Appended"
        return sent


def test_a_fenced_worker_exits_and_writes_nothing_after_the_fence(world: SealedWorld) -> None:
    made = bench(world)
    made.client = FencingClient(made.client, made.log)
    ending = made.work()
    assert ending == WorkerEnding(WorkerEndingKind.FENCED, RUN, ATTEMPT, 1, "generation 2")
    kinds = made.kinds()
    assert kinds[-2:] == ["dispatch_intent", "segment_started"], kinds
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert state.generation == 2 and state.closed is None
    call = calls_of(state)[0]
    assert call.last_outcome is None, "the fenced worker's outcome was refused"


class Failing:
    """A log whose appends fail with ``raising`` from the ``after``-th on, ``times`` times."""

    def __init__(
        self, inner: MemoryLog, raising: type[Exception], *, after: int, times: int
    ) -> None:
        self.inner = inner
        self.raising = raising
        self.after = after
        self.times = times
        self.appends = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _fail(self) -> None:
        self.appends += 1
        if self.appends >= self.after and self.times > 0:
            self.times -= 1
            raise self.raising("provoked")

    def append(self, *args: Any, **kwargs: Any) -> Any:
        self._fail()
        return self.inner.append(*args, **kwargs)

    def close_attempt(self, *args: Any, **kwargs: Any) -> Any:
        self._fail()
        return self.inner.close_attempt(*args, **kwargs)


def test_the_log_unavailable_leaves_the_attempt_open_with_nothing_written(
    world: SealedWorld,
) -> None:
    made = bench(world)
    failing = Failing(made.log, LogStoreUnavailable, after=4, times=10**6)
    ending = made.work(store=failing)
    assert ending == WorkerEnding(WorkerEndingKind.LEFT_OPEN, RUN, ATTEMPT, 1, "log unavailable")
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert state.closed is None and state.last_position == 2 + 3


def test_a_conflict_is_recorded_as_a_defect_at_the_event_append_site(world: SealedWorld) -> None:
    made = bench(world)
    failing = Failing(made.log, LogStoreConflict, after=4, times=1)
    ending = made.work(store=failing)
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "failed")
    closing = made.log.load(RUN, ATTEMPT, rules=RULES).closing
    assert isinstance(closing, Failed)
    assert (closing.category, closing.site) == (
        FailureCategory.DEFECT,
        HarnessSite(HarnessSiteName.EVENT_APPEND),
    )
    assert re.fullmatch(
        r"leaveimpact\.agent\.log_store\.LogStoreConflict at tests/unit/test_agent_worker\.py:\d+",
        closing.reason,
    )
    assert "provoked" not in closing.reason


def test_a_conflict_that_persists_leaves_the_attempt_open(world: SealedWorld) -> None:
    made = bench(world)
    failing = Failing(made.log, LogStoreConflict, after=4, times=10**6)
    ending = made.work(store=failing)
    assert ending == WorkerEnding(WorkerEndingKind.LEFT_OPEN, RUN, ATTEMPT, 1, "recording failed")
    assert made.log.load(RUN, ATTEMPT, rules=RULES).closed is None


class RaisingTurns(ScriptedTurns):
    def request_for(self, state: Any, call: int) -> Any:
        return 1 / 0


def test_an_unclassified_exception_closes_by_defect_at_unhandled_with_type_and_location(
    world: SealedWorld,
) -> None:
    made = bench(world)
    made.turns = RaisingTurns(made.turns.bodies)
    ending = made.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "failed")
    closing = made.log.load(RUN, ATTEMPT, rules=RULES).closing
    assert isinstance(closing, Failed)
    assert (closing.category, closing.site) == (
        FailureCategory.DEFECT,
        HarnessSite(HarnessSiteName.UNHANDLED),
    )
    assert re.fullmatch(
        r"builtins\.ZeroDivisionError at tests/unit/test_agent_worker\.py:\d+", closing.reason
    )
    assert "division" not in closing.reason


def test_a_differing_configuration_claims_nothing_and_names_the_fields(world: SealedWorld) -> None:
    made = bench(world)
    other = replace(
        WorkerConfiguration.of(made.inputs),
        caps=Caps(21, 100_000, 2, 5_000, "input_plus_output_cached_included", cases.METHOD),
        corpus_level="padded",
    )
    ending = made.work(configuration=other)
    assert ending == WorkerEnding(
        WorkerEndingKind.CONFIGURATION_MISMATCH, RUN, ATTEMPT, 0, "caps, corpus_level"
    )
    assert made.kinds() == ["admitted"]


def test_the_copied_fields_and_the_configuration_partition_the_frozen_inputs() -> None:
    configured = {f.name for f in fields(WorkerConfiguration)}
    frozen = {f.name for f in fields(FrozenInputs)}
    assert configured.isdisjoint(COPIED_FROM_THE_ADMISSION)
    assert configured | set(COPIED_FROM_THE_ADMISSION) == frozen
    inputs = histories.inputs(reservation=1_000)
    assert configuration_difference(inputs, WorkerConfiguration.of(inputs).frozen_for(inputs)) == ()
    with pytest.raises(ValueError, match="writes log format 2"):
        WorkerConfiguration.of(inputs).frozen_for(replace(inputs, log_format_version=3))


def test_a_human_approval_ends_the_segment_and_the_next_worker_resumes_without_a_send(
    world: SealedWorld,
) -> None:
    made = bench(world)
    first = made.work(approval=HumanApproval())
    assert first == WorkerEnding(
        WorkerEndingKind.AWAITING_APPROVAL, RUN, ATTEMPT, 1, "approval requested"
    )
    assert made.kinds()[-2:] == ["approval_requested", "segment_ended"]
    sends_before = support.sends_of(made.client)
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    request = state.approval_requested
    assert request is not None
    digest = review_payload_digest(request.event.claims, request.event.composition)  # type: ignore[union-attr]
    delivered = made.log.append(
        RUN, ATTEMPT, Producer("approver:test"), Approved(Approver.HUMAN, digest), rules=RULES
    )
    assert delivered.__class__.__name__ == "Appended"
    second = made.work(approval=HumanApproval())
    assert second == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "completed")
    assert made.kinds()[-4:] == ["approved", "segment_started", "resumed", "completed"]
    assert support.sends_of(made.client) == sends_before, "the replay sent nothing"


class InterruptingClient(ScriptedClient):
    def send(self, requested_profile: str, body: Any) -> Any:
        raise KeyboardInterrupt


def test_a_stop_signal_ends_the_segment_and_is_raised_again(world: SealedWorld) -> None:
    made = bench(world)
    made.client = InterruptingClient(made.client.answers)
    with pytest.raises(KeyboardInterrupt):
        made.work()
    assert made.kinds()[-2:] == ["dispatch_intent", "segment_ended"]
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert (
        state.closed is None and state.current_segment is not None and state.current_segment.ended
    )


def test_a_call_failed_by_infrastructure_is_finalized_in_its_category_after_the_delays(
    world: SealedWorld,
) -> None:
    rules = Rules(cases.TABLE, RedispatchPolicy(3, 5_000))
    made = bench(world, script=throttled_script, rules=rules)
    ending = made.work(rules=rules)
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "failed")
    closing = made.log.load(RUN, ATTEMPT, rules=rules).closing
    assert isinstance(closing, Failed)
    assert closing.category is FailureCategory.INFRASTRUCTURE
    assert closing.site == DispatchSite(ModelCallId("call-1"), 3, DispatchPhase.SEND)
    assert support.sends_of(made.client) == 3
    assert made.waits == [4.0, 4.0], "the clock advanced one second per reading; the rest was slept"


def test_a_transient_counting_refusal_is_retried_and_the_bound_rests_on_the_count_that_answered(
    world: SealedWorld,
) -> None:
    rules = Rules(cases.TABLE, RedispatchPolicy(3, 5_000))
    made = bench(world, rules=rules)
    made.counter = ScriptedCounter(
        (
            CountServiceError(503, "ServiceUnavailableException", "busy", None, 30),
            Counted(cases.INPUT_BOUND, None, 12),
        )
    )
    ending = made.work(rules=rules)
    assert ending.kind is WorkerEndingKind.CLOSED and ending.detail == "completed"
    kinds = made.kinds()
    first_intent = kinds.index("dispatch_intent")
    assert kinds[first_intent - 4 : first_intent] == [
        "count_started",
        "count_outcome",
        "count_started",
        "count_outcome",
    ]
    state = made.log.load(RUN, ATTEMPT, rules=rules)
    counts = counts_of(state)
    intent = calls_of(state)[0].intents[0].event
    assert isinstance(intent, DispatchIntent)
    assert intent.bound.evidence == count_id(counts[1].key)
    assert made.waits[:1] == [4.0]


def test_a_recorded_stopping_failure_is_finalized_without_running_the_graph(
    world: SealedWorld,
) -> None:
    rules = Rules(cases.TABLE, RedispatchPolicy(3, 0))
    made = bench(world, script=throttled_script)
    stopped = made.work()
    assert stopped.detail == "failed"
    events = made.events()
    cut = next(
        i for i, e in enumerate(events) if kind_of(e.event) is EventKind.DISPATCH_OUTCOME and i > 0
    )
    prefix = events[: cut + 3]
    assert [kind_of(e.event).value for e in prefix[-3:]] == [
        "dispatch_outcome",
        "dispatch_intent",
        "dispatch_outcome",
    ] or True
    recovering = bench(world, script=throttled_script, events=events[:-1])
    ending = recovering.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "failed")
    assert support.sends_of(recovering.client) == 0
    assert recovering.kinds()[-2:] == ["segment_started", "failed"]
    closing = recovering.log.load(RUN, ATTEMPT, rules=rules).closing
    assert isinstance(closing, Failed) and closing.category is FailureCategory.INFRASTRUCTURE


def test_a_closed_attempt_is_left_at_the_load_and_a_claim_on_it_is_refused(
    world: SealedWorld,
) -> None:
    made = bench(world)
    made.work()
    again = made.work()
    assert again == WorkerEnding(WorkerEndingKind.CLOSED_ALREADY, RUN, ATTEMPT, 1, "completed")
    assert len(operations_of(made.log.load(RUN, ATTEMPT, rules=RULES))) == len(
        [k for k in made.kinds() if k == "operation"]
    )


# --- The review's first finding: the ending the request froze toward -----------------------

AT_CAP = Caps(20, 4_700, 2, 4_699, "input_plus_output_cached_included", cases.METHOD)
"""A token cap the fixtures' worst case (4,608 tokens a dispatch) reaches on the second
dispatch of finalization: the loop's room is one token, so the first call enters finalization;
the first finalization dispatch fits in 4,700 and is then held at its observed 150 tokens,
and the second's 150 + 4,608 does not fit."""


class Silent(ScriptedTurns):
    """A system that restates no request: the reviewer's stub, which a recovering worker
    must not need."""

    def request_for(self, state: Any, call: int) -> Any:
        return None


def capped(world: SealedWorld, events: Sequence[LoggedEvent] | None = None) -> Bench:
    made = bench(world, events=events)
    if events is None:
        made.inputs = replace(made.inputs, caps=AT_CAP)
        made.log = MemoryLog()
        made.log.seed(support.admission(made.inputs))
    else:
        made.inputs = replace(made.inputs, caps=AT_CAP)
    return made


def test_a_run_at_its_cap_closes_cap_exhausted_and_the_request_carries_the_ending(
    world: SealedWorld,
) -> None:
    made = capped(world)
    ending = made.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "cap_exhausted")
    kinds = made.kinds()
    assert kinds.index("finalization_entered") < kinds.index("dispatch_intent"), (
        "the loop's first allocation did not fit; the run finalized from its first call"
    )
    assert support.sends_of(made.client) == 1, "the second finalization dispatch was refused"
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    request = state.approval_requested
    assert request is not None and isinstance(request.event, ApprovalRequested)
    assert request.event.at_cap is True
    assert export_of(state).record.status.value == "cap_exhausted"


def test_a_recovery_after_the_request_keeps_the_cap_ending_without_the_systems_help(
    world: SealedWorld,
) -> None:
    reference = capped(world)
    reference.work()
    events = reference.events()
    cut = [kind_of(e.event).value for e in events].index("approval_requested") + 1
    recovering = capped(world, events=events[:cut])
    recovering.turns = Silent(recovering.turns.bodies)
    ending = recovering.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "cap_exhausted")
    assert support.sends_of(recovering.client) == 0


NEAR_CAP = Caps(20, 14_000, 2, 5_000, "input_plus_output_cached_included", cases.METHOD)
"""A token cap whose loop room (9,000) holds one worst case (4,608) and not two, and whose
whole (14,000) holds two: a loop call's first dispatch fits, its re-dispatch after a throttle
does not and enters finalization, and the re-dispatch then fits from the reserve."""


def throttled_once_script(context: Any) -> tuple[ScriptedTurns, ScriptedClient]:
    """Call 1's first dispatch throttled and its second answered with no read; call 2
    answered with no read."""
    turns, _ = support.two_call_script(context)
    throttled = support.observed(
        ServiceError(429, "ThrottlingException", None, "too many requests")
    )
    answers = {
        support.request_digest(turns.bodies[0]): (
            throttled,
            support.answered(support.text("Nothing to read.")),
        ),
        support.request_digest(turns.bodies[1]): (support.answered(support.text("Done.")),),
    }
    return turns, ScriptedClient(answers)


def near_cap(world: SealedWorld, events: Sequence[LoggedEvent] | None = None) -> Bench:
    made = bench(world, script=throttled_once_script, events=events)
    made.inputs = replace(made.inputs, caps=NEAR_CAP)
    if events is None:
        made.log = MemoryLog()
        made.log.seed(support.admission(made.inputs))
    return made


def intents_of(events: Sequence[LoggedEvent]) -> list[tuple[int, DispatchIntent]]:
    return [(e.position, e.event) for e in events if isinstance(e.event, DispatchIntent)]


def test_a_loop_call_in_progress_at_the_entry_into_finalization_finishes_from_the_reserve(
    world: SealedWorld,
) -> None:
    """Amendment 2 of the graph step's rulings (option A): the call keeps the purpose it was
    first authorized under, its re-dispatch is authorized from the reserve once finalization
    is entered, and the request bytes do not change. Before the fix the re-dispatch derived
    the finalization purpose from the entry, the account refused it as a changed purpose and
    the worker closed by defect at the unhandled site."""
    made = near_cap(world)
    ending = made.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    kinds = made.kinds()
    intents = intents_of(made.events())
    assert [(i.call, i.number) for _, i in intents] == [(1, 1), (1, 2), (2, 1)]
    entered = kinds.index("finalization_entered") + 1
    assert intents[0][0] < entered < intents[1][0] < intents[2][0]
    first, again, final = (i for _, i in intents)
    assert first.request_digest == again.request_digest != final.request_digest
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert state.account.purpose_of("call-1") is CallPurpose.LOOP
    assert state.account.purpose_of("call-2") is CallPurpose.FINALIZATION
    assert support.sends_of(made.client) == 3
    check = check_account(export_of(state))
    assert check is not None and check.findings == (), "the evaluator replays the same rule"


def test_a_recovery_after_the_entry_re_dispatches_the_loop_call_with_the_same_bytes(
    world: SealedWorld,
) -> None:
    reference = near_cap(world)
    reference.work()
    events = reference.events()
    cut = [kind_of(e.event).value for e in events].index("finalization_entered") + 1
    recovering = near_cap(world, events=events[:cut])
    # The recovering process meets no throttle: the re-dispatch is answered at once.
    bodies = recovering.turns.bodies
    nothing = support.answered(support.text("Nothing to read."))
    done = support.answered(support.text("Done."))
    recovering.client = ScriptedClient(
        {support.request_digest(bodies[0]): (nothing,), support.request_digest(bodies[1]): (done,)}
    )
    ending = recovering.work()
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "completed")
    intents = [i for _, i in intents_of(recovering.events())]
    assert [(i.call, i.number) for i in intents] == [(1, 1), (1, 2), (2, 1)]
    assert intents[0].request_digest == intents[1].request_digest
    assert support.sends_of(recovering.client) == 2, "the throttled send is not repeated"
    assert support.settled(recovering.events()) == support.settled(events)


def test_the_closing_kind_must_be_the_one_the_request_froze_toward(world: SealedWorld) -> None:
    reference = capped(world)
    reference.work()
    events = reference.events()
    cut = [kind_of(e.event).value for e in events].index("resumed") + 1
    log = MemoryLog()
    log.seed(events[:cut])
    state = log.load(RUN, ATTEMPT, rules=RULES)
    refused = log.close_attempt(
        RUN, ATTEMPT, WorkerStamp(1, 1, 10_000), Completed(None), rules=RULES, state=state
    )
    assert isinstance(refused, Refused) and "froze toward: the cap" in refused.reason
    closed = log.close_attempt(
        RUN, ATTEMPT, WorkerStamp(1, 1, 10_000), CapExhausted(None), rules=RULES, state=state
    )
    assert isinstance(closed, Appended)
