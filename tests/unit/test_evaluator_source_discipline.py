"""Source discipline is read off the trace alone: every read counts for the source it was
recorded against by how it ended and who asked, a refused call for none; the model's refused
tool requests are counted over the operations it asked for and apart from the model calls,
which are counted by how each stands and how its last dispatch was read; the tool calls a
model made are counted by what became of each, the undispatched ones by reason; a completed
read with an earlier one's tool and arguments names it; an operation that a conforming
harness could not have recorded is a finding, and so is a response whose metadata shows the
SDK sent more than once. The reads of a full investigation of a sealed scenario carry no
finding."""

from collections.abc import Mapping

from leaveimpact.core import (
    AbsentOutcome,
    Answer,
    AsOperation,
    AttributionKind,
    BrokenStream,
    CallState,
    CompleteResponse,
    DefectOutcome,
    HandledAsBatch,
    HarnessOrigin,
    ModelCall,
    ModelCallId,
    ModelOrigin,
    Operation,
    OperationId,
    Origin,
    Outcome,
    ParsedBatch,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedBy,
    RefusedCallOutcome,
    RunTrace,
    ServiceError,
    Source,
    ToolCall,
    Undispatched,
    UndispatchedReason,
    Unparsed,
    UnreachableOutcome,
    UnresolvedToolCall,
)
from leaveimpact.evaluator.source_discipline import (
    Ended,
    OperationFinding,
    OperationFindingKind,
    OriginCount,
    RequiredSourceUse,
    RetriedSend,
    SourceDiscipline,
    ToolCallEnded,
    source_discipline,
)
from tests.unit.export_fixture import COMPOSITION, answered_call, dispatch, failed_call
from tests.unit.reads_fixture import Recorder, reads_of_everything, systems_holding
from tests.unit.throwaway_world import loaded_world

PREFETCH = PrefetchOrigin()
CALL = ModelCallId("call-1")
MODEL = ModelOrigin(CALL)
NOTHING = RecordsOutcome(())
REFUSED = RefusedCallOutcome("not an id of that kind")

Read = tuple[Origin, str, Source | None, Mapping[str, object], Outcome]


def asking(*operations: Operation) -> ModelCall:
    """The first model call, answered with one tool call for each of ``operations``."""
    asked = tuple(
        ToolCall(f"tu_{number}", operation.tool, AsOperation(operation.id))
        for number, operation in enumerate(operations, start=1)
    )
    return answered_call(1, None, None, stop_reason="tool_use", answer=Answer(False, asked, ()))


def discipline_of(*reads: Read, calls: tuple[ModelCall, ...] | None = None) -> SourceDiscipline:
    """The discipline of a trace holding ``reads`` in order, after one model call that asked
    for the reads of model origin; ``calls`` adds the calls that follow it."""
    operations = tuple(
        Operation(
            OperationId(f"op-{number}"), origin, tool, source, arguments, outcome, 10_000 + number
        )
        for number, (origin, tool, source, arguments, outcome) in enumerate(reads, start=1)
    )
    asked = tuple(op for op in operations if isinstance(op.origin, ModelOrigin))
    held = (asking(*asked), *(() if calls is None else calls)) if asked or calls else ()
    return source_discipline(RunTrace(held, operations, (), COMPOSITION))


def down(source: Source) -> UnreachableOutcome:
    return UnreachableOutcome(source, "no answer after the retries")


def test_a_read_counts_for_its_source_by_how_it_ended_and_who_asked() -> None:
    seen = discipline_of(
        (PREFETCH, "employees", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "employee", Source.FRAPPE, {"id": "emp_099"}, AbsentOutcome()),
        (MODEL, "employees", Source.FRAPPE, {}, down(Source.FRAPPE)),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, DefectOutcome(Source.JIRA, "issue 1", "no owner")),
        (MODEL, "components", Source.JIRA, {}, down(Source.JIRA)),
        (MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED),
    )
    hr, tracker = seen.tally(Source.FRAPPE), seen.tally(Source.JIRA)
    assert (hr.completed, hr.unreachable, hr.defect) == (
        OriginCount(2, 0, 0),
        OriginCount(0, 0, 1),
        OriginCount(0, 0, 0),
    )
    assert (tracker.completed, tracker.unreachable, tracker.defect) == (
        OriginCount(0, 0, 1),
        OriginCount(0, 0, 1),
        OriginCount(0, 0, 1),
    )
    # The refused call had a source resolved and counts for none: no source was asked.
    assert [row.ended for row in seen.operations][-1] is Ended.REFUSED
    counted = sum(
        tally.completed.total + tally.unreachable.total + tally.defect.total
        for tally in map(seen.tally, Source)
    )
    assert counted + 1 == len(seen.operations)


def test_a_source_is_attempted_when_it_was_asked_and_succeeded_when_it_answered() -> None:
    seen = discipline_of(
        (PREFETCH, "employees", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "work_items", Source.JIRA, {}, down(Source.JIRA)),
        (MODEL, "document", Source.CORPUS, {"id": "nope"}, REFUSED),
        (
            PREFETCH,
            "event",
            Source.CALENDAR,
            {"id": "event_001"},
            DefectOutcome(Source.CALENDAR, "e", "x"),
        ),
    )
    used = {
        source: (seen.tally(source).attempted, seen.tally(source).succeeded) for source in Source
    }
    assert used[Source.FRAPPE] == (True, True)
    assert used[Source.JIRA] == (True, False)
    assert used[Source.CALENDAR] == (True, False)  # a malformed record: asked, not answered
    assert used[Source.CORPUS] == (False, False)  # only a refused call named it
    # Joined with the sources a key says its answer depends on, in the key's order.
    assert seen.required_source_use((Source.JIRA, Source.FRAPPE, Source.CORPUS)) == (
        RequiredSourceUse(Source.JIRA, attempted=True, succeeded=False),
        RequiredSourceUse(Source.FRAPPE, attempted=True, succeeded=True),
        RequiredSourceUse(Source.CORPUS, attempted=False, succeeded=False),
    )


def test_refused_calls_are_the_models_and_a_refused_prefetch_is_a_harness_finding() -> None:
    seen = discipline_of(
        (MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED),
        (MODEL, "no_such_tool", None, {}, REFUSED),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (PREFETCH, "employee", Source.FRAPPE, {"id": "LIA-42"}, REFUSED),
    )
    assert (seen.refused_by_the_wrapper, seen.model_operations) == (2, 3)
    assert seen.findings == (
        OperationFinding(OperationId("op-4"), OperationFindingKind.REFUSED_PREFETCH),
    )


def test_a_read_the_harness_issued_is_counted_apart_from_the_prefetch_and_the_model() -> None:
    issued = HarnessOrigin("full-context-documents")
    seen = discipline_of(
        (PREFETCH, "employees", Source.FRAPPE, {}, NOTHING),
        (issued, "employees", Source.FRAPPE, {}, NOTHING),
        (MODEL, "employees", Source.FRAPPE, {}, NOTHING),
    )
    assert seen.tally(Source.FRAPPE).completed == OriginCount(1, 1, 1)
    # A refused read the harness issued is the harness's own, as a refused prefetch call is.
    refused = discipline_of((issued, "employee", Source.FRAPPE, {"id": "LIA-42"}, REFUSED))
    assert refused.findings == (
        OperationFinding(OperationId("op-1"), OperationFindingKind.REFUSED_PREFETCH),
    )
    assert refused.refused_by_the_wrapper == 0
    assert [row.origin.value for row in seen.operations] == ["prefetch", "harness", "model"]
    assert seen.model_operations == 1


def test_model_calls_are_counted_by_state_and_reading_apart_from_refused_operations() -> None:
    """Three answered calls, one of them under a refusal's stop reason, which is behaviour like
    any registered stop; a send that timed out; and a service error read as the model's
    behaviour, which is a failed call counted under behaviour."""
    cut = ServiceError(424, "ModelErrorException", None, "invalid sequence as part of ToolUse")
    calls = (
        answered_call(2, None, None, stop_reason="guardrail_intervened"),
        failed_call(3),
        answered_call(4, None, None),
        ModelCall(
            ModelCallId("call-5"),
            "investigator",
            (dispatch(5, cut, AttributionKind.BEHAVIOUR),),
            None,
        ),
    )
    seen = discipline_of((MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED), calls=calls)
    counted = {(state, read_as): count for state, read_as, count in seen.model_calls}
    assert len(seen.model_calls) == len(CallState) * len(AttributionKind) == 12
    assert {pair: count for pair, count in counted.items() if count} == {
        (CallState.ANSWERED, AttributionKind.BEHAVIOUR): 3,
        (CallState.FAILED, AttributionKind.BEHAVIOUR): 1,
        (CallState.FAILED, AttributionKind.INFRASTRUCTURE): 1,
    }
    assert [pair for pair in counted][:2] == [
        (CallState.ANSWERED, AttributionKind.BEHAVIOUR),
        (CallState.ANSWERED, AttributionKind.INFRASTRUCTURE),
    ]
    # No model call is a refused operation: one tool request was refused, a different thing.
    assert seen.refused_by_the_wrapper == 1
    # A rules-only trace calls no model and every pair is still there, at zero.
    assert all(count == 0 for _, _, count in discipline_of().model_calls)


def test_tool_calls_are_counted_by_what_became_of_each_and_the_undispatched_by_reason() -> None:
    """One answer asked for a read that became an operation. A second held five more calls:
    a fact submission the harness took as a batch, arguments that were no JSON object, two
    never dispatched (the cap, a source already unreachable) and one with no logged result."""
    unreadable = Unparsed("{", RefusedBy("tool-argument-parser-v1", "d" * 64))
    more = (
        ToolCall("tu_a", "state_facts", HandledAsBatch(0)),
        ToolCall("tu_b", "work_item", unreadable),
        ToolCall("tu_c", "work_item", Undispatched(UndispatchedReason.CAP)),
        ToolCall("tu_d", "events", Undispatched(UndispatchedReason.SOURCE_UNREACHABLE)),
        ToolCall("tu_e", "employee", UnresolvedToolCall()),
    )
    second = answered_call(
        2, None, None, stop_reason="tool_use", answer=Answer(False, more, (ParsedBatch(()),))
    )
    seen = discipline_of((MODEL, "work_items", Source.JIRA, {}, NOTHING), calls=(second,))
    assert seen.tool_calls == (
        (ToolCallEnded.OPERATION, 1),
        (ToolCallEnded.HANDLED, 1),
        (ToolCallEnded.UNPARSED, 1),
        (ToolCallEnded.UNDISPATCHED, 2),
        (ToolCallEnded.UNRESOLVED, 1),
    )
    assert dict(seen.undispatched) == {
        UndispatchedReason.STOP_REASON_NOT_TOOL_USE: 0,
        UndispatchedReason.CAP: 1,
        UndispatchedReason.SOURCE_UNREACHABLE: 1,
        UndispatchedReason.ATTEMPT_ENDED_FIRST: 0,
    }
    # Every tool call is counted once, and only an operation is also a row of the reads.
    assert sum(count for _, count in seen.tool_calls) == 6
    assert seen.model_operations == 1
    # A trace with no model call holds every disposition and every reason, at zero.
    quiet = discipline_of()
    assert all(count == 0 for _, count in (*quiet.tool_calls, *quiet.undispatched))
    assert len(quiet.tool_calls) == len(ToolCallEnded) == 5


def test_a_response_whose_metadata_shows_an_sdk_retry_is_a_harness_finding() -> None:
    """Nothing retries beneath a dispatch. A retry count above zero is found wherever a
    response carried one; a count of zero, a count the metadata did not show and a client
    error, which has no response, are not."""

    def call(number: int, *observations: BrokenStream | ServiceError) -> ModelCall:
        sent = tuple(
            dispatch(number, observation, AttributionKind.INFRASTRUCTURE, number=at)
            for at, observation in enumerate(observations, start=1)
        )
        return ModelCall(ModelCallId(f"call-{number}"), "investigator", sent, None)

    throttled = ServiceError(429, "ThrottlingException", None, "too many requests", sdk_retries=2)
    calls = (
        call(2, BrokenStream("reset"), throttled, BrokenStream("reset", sdk_retries=1)),
        call(3, ServiceError(500, "InternalServerException", None, "an error", sdk_retries=0)),
        ModelCall(
            ModelCallId("call-4"),
            "investigator",
            (dispatch(4, CompleteResponse("end_turn", 840, 1), AttributionKind.BEHAVIOUR),),
            Answer(True, (), ()),
        ),
        failed_call(5),
        answered_call(6, None, None),
    )
    seen = discipline_of(calls=calls)
    assert seen.retried_sends == (
        RetriedSend(ModelCallId("call-2"), 2),
        RetriedSend(ModelCallId("call-2"), 3),
        RetriedSend(ModelCallId("call-4"), 1),
    )
    assert discipline_of().retried_sends == ()


def test_a_completed_read_with_an_earlier_ones_tool_and_arguments_names_it() -> None:
    week = {"span": {"start": "2026-09-15", "end": "2026-09-19"}}
    reordered = {"span": {"end": "2026-09-19", "start": "2026-09-15"}}
    other_week = {"span": {"start": "2026-09-22", "end": "2026-09-26"}}
    seen = discipline_of(
        (PREFETCH, "work_items", Source.JIRA, {}, down(Source.JIRA)),
        (PREFETCH, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, week, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, other_week, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, reordered, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, down(Source.JIRA)),
    )
    assert [row.repeat_of for row in seen.operations] == [
        None,  # failed: not a completed read
        None,  # the first completed one; the failed attempt before it is not what it repeats
        "op-2",
        None,
        None,  # the same tool over another window
        "op-4",  # the order a caller spelled the keys in says nothing
        "op-2",  # the first such read, however many came between
        None,  # failed again: a failed read repeats nothing
    ]
    assert [row.operation for row in seen.repeats] == ["op-3", "op-6", "op-7"]


def test_an_operation_no_conforming_harness_records_is_a_finding_by_kind() -> None:
    world = loaded_world("golden")
    reads = Recorder(systems_holding(world))
    employees = reads.read("employees")
    documents = [
        planted.entity.id for owner in world.scenarios for planted in owner.owned.documents
    ]
    found = [reads.read("document", {"id": id}) for id in documents[:2]]
    two_documents = RecordsOutcome(
        tuple(outcome.record for outcome in found if isinstance(outcome, RecordOutcome))
    )
    assert len(two_documents.records) == 2
    seen = discipline_of(
        (PREFETCH, "everyone", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "employees", Source.JIRA, {}, down(Source.JIRA)),
        (PREFETCH, "work_items", Source.FRAPPE, {"id": "emp_001"}, employees),
        (MODEL, "employees", Source.FRAPPE, {}, AbsentOutcome()),
        (MODEL, "search", Source.CORPUS, {"query": "rotation", "limit": 1}, two_documents),
        (MODEL, "search", Source.CORPUS, {"query": "rotation", "limit": 2}, two_documents),
    )
    kinds = OperationFindingKind
    assert seen.findings == (
        OperationFinding(OperationId("op-1"), kinds.UNKNOWN_TOOL),
        # An unreachable outcome recorded against a source its tool does not read.
        OperationFinding(OperationId("op-2"), kinds.SOURCE_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.SOURCE_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.RECORD_KIND_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.ARGUMENTS_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-4"), kinds.CARDINALITY_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-5"), kinds.MORE_THAN_THE_LIMIT),
    )
    # The mismatched reads still count for the source they were recorded against.
    assert seen.tally(Source.JIRA).unreachable == OriginCount(1, 0, 0)


def test_the_reads_of_a_full_investigation_carry_no_finding_and_sum_to_the_trace() -> None:
    world = loaded_world("golden")
    for scenario in world.scenarios[:5]:
        for down_sources in ((), (Source.JIRA,), (Source.CALENDAR,)):
            operations = reads_of_everything(world, scenario, *down_sources)
            seen = source_discipline(RunTrace((), tuple(operations), (), COMPOSITION))
            assert seen.findings == ()
            assert seen.repeats == ()
            assert (seen.model_operations, seen.refused_by_the_wrapper) == (0, 0)
            counted = sum(
                tally.completed.total + tally.unreachable.total + tally.defect.total
                for tally in map(seen.tally, Source)
            )
            assert counted == len(operations)
            for source in Source:
                tally = seen.tally(source)
                assert tally.attempted
                assert tally.succeeded == (source not in down_sources)
