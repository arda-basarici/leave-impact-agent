"""The model call of format 2: a dispatch permits zero or one send, the observation is kept
apart from its attribution, a call's state is derived from its last dispatch, and an answer
holds one disposition per tool call."""

from dataclasses import replace

import pytest

from leaveimpact.core.model_calls import (
    Answer,
    AsOperation,
    Attribution,
    AttributionKind,
    BrokenStream,
    CallState,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    Dispatch,
    HandledAsBatch,
    MalformedBatch,
    ModelCall,
    NoRecordedOutcome,
    Observation,
    ParsedBatch,
    RefusedBeforeSend,
    RefusedBy,
    RequestIdentity,
    Sends,
    ServiceError,
    ToolCall,
    Undispatched,
    UndispatchedReason,
    Unparsed,
    UnresolvedToolCall,
)
from leaveimpact.core.run_trace import Cost, ModelCallId, OperationId
from leaveimpact.core.usage import ReportedUsage

REQUEST = RequestIdentity("a" * 64, "Converse", "eu.model", "eu-central-1", None)
BEHAVIOUR = Attribution(AttributionKind.BEHAVIOUR, "registered-stop-reason")
INFRASTRUCTURE = Attribution(AttributionKind.INFRASTRUCTURE, "service-error")
UNRESOLVED = Attribution(AttributionKind.UNRESOLVED, "no-outcome")
USAGE = ReportedUsage({"inputTokens": 120, "outputTokens": 30, "totalTokens": 150})
REFUSED_BY = RefusedBy("fact-batch-parser-v1", "b" * 64)


def answered(number: int = 1, intent: int = 7, stop_reason: str = "tool_use") -> Dispatch:
    return Dispatch(
        number=number,
        segment=1,
        intent_position=intent,
        outcome_position=intent + 1,
        request=REQUEST,
        input_reads=(OperationId("op-1"),),
        observation=CompleteResponse(stop_reason, 840, 0),
        attribution=BEHAVIOUR,
        usage=USAGE,
        cost=Cost(297_000, True),
        zero_cost_rule=None,
        allocation=5_000_000,
    )


def observed(observation: Observation, attribution: Attribution, number: int = 1) -> Dispatch:
    unrecorded = isinstance(observation, NoRecordedOutcome)
    return Dispatch(
        number=number,
        segment=1,
        intent_position=3 * number,
        outcome_position=None if unrecorded else 3 * number + 1,
        request=REQUEST,
        input_reads=(),
        observation=observation,
        attribution=attribution,
        usage=None,
        cost=None,
        zero_cost_rule=None,
        allocation=5_000_000,
    )


def test_a_dispatch_stands_for_zero_one_or_an_unresolved_send() -> None:
    assert answered().sends is Sends.ONE
    refused = observed(
        RefusedBeforeSend("ParamValidationError"), Attribution(AttributionKind.DEFECT, "sdk")
    )
    assert refused.sends is Sends.NONE
    lost = observed(NoRecordedOutcome(), UNRESOLVED)
    assert lost.sends is Sends.UNRESOLVED
    assert lost.outcome_position is None


def test_no_recorded_outcome_is_unresolved_and_nothing_else_is() -> None:
    with pytest.raises(ValueError, match="unresolved exactly when no outcome was recorded"):
        observed(NoRecordedOutcome(), INFRASTRUCTURE)
    with pytest.raises(ValueError, match="unresolved exactly when no outcome was recorded"):
        replace(answered(), attribution=UNRESOLVED)
    with pytest.raises(ValueError, match="outcome position is held exactly when"):
        replace(answered(), outcome_position=None)
    with pytest.raises(ValueError, match="logged after its intent"):
        replace(answered(), outcome_position=7)


def test_a_service_error_stays_one_whichever_rule_reads_it() -> None:
    """The Nova cut call: the same observation read as behaviour under its evidenced
    signature and as infrastructure under any other, the record of what arrived unchanged."""
    cut = ServiceError(424, "ModelErrorException", None, "invalid sequence as part of ToolUse")
    as_behaviour = observed(cut, Attribution(AttributionKind.BEHAVIOUR, "nova-cut-tool-use"))
    as_fault = observed(cut, Attribution(AttributionKind.INFRASTRUCTURE, "unmatched"))
    # Reading it as behaviour does not make it a response: under either rule the dispatch
    # holds a service error, one send, no usage and no answer to carry.
    for read in (as_behaviour, as_fault):
        assert isinstance(read.observation, ServiceError)
        assert (read.sends, read.usage, read.cost) == (Sends.ONE, None, None)
    assert as_behaviour != as_fault
    call = ModelCall(ModelCallId("call-1"), "investigator", (as_behaviour,), None)
    assert call.state is CallState.FAILED
    assert call.dispatches[-1].attribution.kind is AttributionKind.BEHAVIOUR
    assert call.stop_reason is None


def test_usage_and_cost_belong_to_a_send_whose_outcome_arrived() -> None:
    with pytest.raises(ValueError, match="usage and cost are recorded for a send"):
        replace(observed(NoRecordedOutcome(), UNRESOLVED), usage=USAGE)
    with pytest.raises(ValueError, match="usage and cost are recorded for a send"):
        replace(
            observed(RefusedBeforeSend("x"), Attribution(AttributionKind.DEFECT, "sdk")),
            cost=Cost(0, True),
            zero_cost_rule="no-send",
        )
    timeout = observed(ClientError(ClientErrorKind.TIMEOUT, "ReadTimeoutError"), INFRASTRUCTURE)
    assert timeout.usage is None
    assert timeout.cost is None


def test_an_error_is_free_only_under_a_named_zero_cost_rule() -> None:
    rejected = ServiceError(400, "ValidationException", None, "undefined tool")
    with pytest.raises(ValueError, match="prices a reported usage or names its zero-cost rule"):
        replace(observed(rejected, INFRASTRUCTURE), cost=Cost(0, True))
    free = replace(
        observed(rejected, INFRASTRUCTURE), cost=Cost(0, True), zero_cost_rule="validation-400"
    )
    assert free.cost == Cost(0, True)
    with pytest.raises(ValueError, match="at a complete zero"):
        replace(
            observed(rejected, INFRASTRUCTURE), cost=Cost(5, True), zero_cost_rule="validation-400"
        )
    with pytest.raises(ValueError, match="at a complete zero"):
        replace(answered(), zero_cost_rule="validation-400")


def test_a_dispatch_names_each_input_read_once() -> None:
    with pytest.raises(ValueError, match="each input read once"):
        replace(answered(), input_reads=(OperationId("op-1"), OperationId("op-1")))


def test_a_call_numbers_its_dispatches_and_only_the_last_holds_a_response() -> None:
    lost = observed(NoRecordedOutcome(), UNRESOLVED, number=1)
    call = ModelCall(
        ModelCallId("call-1"), "investigator", (lost, answered(2, intent=9)), Answer(True, (), ())
    )
    assert call.state is CallState.ANSWERED
    assert call.stop_reason == "tool_use"
    assert [dispatch.sends for dispatch in call.dispatches] == [Sends.UNRESOLVED, Sends.ONE]
    assert ModelCall(ModelCallId("c"), "r", (lost,), None).state is CallState.UNRESOLVED
    with pytest.raises(ValueError, match="at least one dispatch"):
        ModelCall(ModelCallId("c"), "r", (), None)
    with pytest.raises(ValueError, match="numbered from one without a gap"):
        ModelCall(ModelCallId("c"), "r", (answered(2),), None)
    with pytest.raises(ValueError, match="only a call's last dispatch"):
        ModelCall(ModelCallId("c"), "r", (answered(1, intent=2), answered(2, intent=9)), None)
    with pytest.raises(ValueError, match="in position order"):
        ModelCall(ModelCallId("c"), "r", (lost, answered(2, intent=2)), None)


def test_a_call_is_asked_again_only_after_the_last_outcome_and_never_in_an_earlier_segment() -> (
    None
):
    timed_out = observed(
        ClientError(ClientErrorKind.TIMEOUT, "ReadTimeoutError"), INFRASTRUCTURE
    )  # intent 3, outcome 4
    assert ModelCall(ModelCallId("c"), "r", (timed_out, answered(2, intent=5)), None)
    late = replace(timed_out, outcome_position=10)
    with pytest.raises(ValueError, match="asked before the outcome of dispatch 1 was logged"):
        ModelCall(ModelCallId("c"), "r", (late, answered(2, intent=5)), None)
    in_a_later_segment = replace(timed_out, segment=2)
    with pytest.raises(ValueError, match="runs in the same segment or a later one"):
        ModelCall(ModelCallId("c"), "r", (in_a_later_segment, answered(2, intent=5)), None)


def test_an_answer_exists_only_over_a_complete_response() -> None:
    broken = observed(BrokenStream("modelStreamErrorException"), INFRASTRUCTURE)
    with pytest.raises(ValueError, match="an answer is what a complete response carried"):
        ModelCall(ModelCallId("c"), "r", (broken,), Answer(False, (), ()))
    preserved = ModelCall(ModelCallId("c"), "r", (answered(),), None)
    assert preserved.state is CallState.ANSWERED
    assert preserved.answer is None


def test_a_tool_call_is_dispatched_only_under_a_tool_use_stop() -> None:
    cut = ToolCall("tu_1", "employee", Undispatched(UndispatchedReason.STOP_REASON_NOT_TOOL_USE))
    read = ToolCall("tu_1", "employee", AsOperation(OperationId("op-7")))
    limit = answered(stop_reason="max_tokens")
    ModelCall(ModelCallId("c"), "r", (limit,), Answer(False, (cut,), ()))
    with pytest.raises(ValueError, match="dispatched only under 'tool_use'"):
        ModelCall(ModelCallId("c"), "r", (limit,), Answer(False, (read,), ()))
    with pytest.raises(ValueError, match="undispatched for its stop reason"):
        ModelCall(ModelCallId("c"), "r", (answered(),), Answer(False, (cut,), ()))


def test_an_answer_links_each_handled_call_to_one_batch_it_holds() -> None:
    malformed = MalformedBatch('{"facts": [', REFUSED_BY)
    handled = ToolCall("tu_1", "state_facts", HandledAsBatch(0))
    answer = Answer(True, (handled,), (malformed, ParsedBatch(())))
    assert answer.fact_batches[0] == malformed
    with pytest.raises(ValueError, match="names fact batch 2"):
        Answer(False, (ToolCall("tu_1", "state_facts", HandledAsBatch(2)),), (malformed,))
    with pytest.raises(ValueError, match="the handling of one tool call"):
        Answer(
            False,
            (handled, ToolCall("tu_2", "state_facts", HandledAsBatch(0))),
            (malformed,),
        )
    with pytest.raises(ValueError, match="tool call ids are unique"):
        Answer(False, (handled, ToolCall("tu_1", "team", UnresolvedToolCall())), (malformed,))
    with pytest.raises(ValueError, match="text_present is a boolean"):
        Answer(1, (), ())  # type: ignore[arg-type]


def test_an_unparsed_call_keeps_its_raw_arguments_and_who_refused_them() -> None:
    call = ToolCall("tu_3", "employee", Unparsed("emp_042", REFUSED_BY))
    assert isinstance(call.disposition, Unparsed)
    assert call.disposition.raw_arguments == "emp_042"
    with pytest.raises(ValueError, match="a schema digest is a SHA-256"):
        RefusedBy("parser", "short")
    with pytest.raises(ValueError, match="a batch entry is a refused input or an admission"):
        ParsedBatch(("a fact",))  # type: ignore[arg-type]


def test_a_request_identity_says_when_no_hook_captured_the_sent_body() -> None:
    assert REQUEST.sent_body_digest is None
    captured = replace(REQUEST, sent_body_digest="c" * 64)
    assert captured != REQUEST
    with pytest.raises(ValueError, match="sent_body_digest is a SHA-256"):
        replace(REQUEST, sent_body_digest="")
