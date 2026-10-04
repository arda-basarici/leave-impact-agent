"""Export format 2's acceptance: each of the hand-built cases encodes to bytes that decode to
an equal export, and each states what it means, read back from the decoded export so that a
meaning the codec dropped would fail here. The cases are the ones format 1 had no value for
(``format2_fixtures``)."""

import json
from dataclasses import replace
from typing import cast

import pytest

from leaveimpact.core import (
    Approval,
    ApprovalState,
    Approver,
    AsOperation,
    AttributionKind,
    CallState,
    Cost,
    DefectOutcome,
    FactRefusal,
    HandledAsBatch,
    HarnessSite,
    HarnessSiteName,
    KeptReason,
    MalformedBatch,
    ModelCallId,
    ModelOrigin,
    OperationId,
    OperationSite,
    ParsedBatch,
    PlacementState,
    Refused,
    RefusedInput,
    ReservationState,
    RunExport,
    Sends,
    ServiceError,
    TerminalStatus,
    Undispatched,
    UndispatchedReason,
    UnresolvedToolCall,
    decode_export_bytes,
    elapsed_ms,
    event_ref,
    evidenced_active_ms,
    export_bytes,
    review_payload,
    review_payload_digest,
    timing_complete,
)
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.model_calls import Answer, ModelCall
from tests.unit import format2_fixtures as cases
from tests.unit import stated_fixture as f

CALL = ModelCallId("call-1")


def decoded(export: RunExport) -> RunExport:
    """``export`` after a trip through its canonical bytes."""
    return decode_export_bytes(export_bytes(export))


def the_call(export: RunExport, id: ModelCallId = CALL) -> ModelCall:
    return export.trace.model_call(id)


def the_answer(export: RunExport) -> Answer:
    answer = the_call(export).answer
    assert answer is not None
    return answer


@pytest.mark.parametrize("name", list(cases.FIXTURES))
def test_every_case_round_trips_through_its_bytes_without_loss(name: str) -> None:
    export = cases.FIXTURES[name]()
    data = export_bytes(export)
    assert decode_export_bytes(data) == export
    assert export_bytes(decode_export_bytes(data)) == data


def test_a_paused_attempt_has_no_export() -> None:
    """The eighth case's third history: an attempt waiting for its approval is a state of the
    log. The nearest export, a completed attempt whose approval is still only requested, does
    not construct, and no approval state names a wait."""
    assert len(cases.FIXTURES) == 13
    assert "pending" not in {state.value for state in ApprovalState}
    record = cases.recovered_attempt().record
    waiting = Approval(ApprovalState.REQUESTED_UNAPPROVED, None, record.approval.payload_digest)
    with pytest.raises(ValueError, match="status completed, approval requested_unapproved"):
        replace(record, approval=waiting)


def test_facts_beside_tools_are_one_answer_with_both() -> None:
    export = decoded(cases.facts_beside_tools())
    answer = the_answer(export)
    assert answer.text_present
    (tool_call,) = answer.tool_calls
    (batch,) = answer.fact_batches
    assert tool_call.disposition == AsOperation(OperationId("op-2"))
    read = export.trace.operation(OperationId("op-2"))
    assert read is not None and read.origin == ModelOrigin(CALL)
    assert isinstance(batch, ParsedBatch)
    assert [type(entry).__name__ for entry in batch.entries] == ["Admitted"]
    # The batch arrived in the answer's own content: no tool call names it.
    assert not any(isinstance(call.disposition, HandledAsBatch) for call in answer.tool_calls)
    dispatch = the_call(export).dispatches[0]
    assert dispatch.input_reads == (OperationId("op-1"),)
    assert read.position is not None and dispatch.outcome_position is not None
    assert read.position > dispatch.outcome_position


def test_a_malformed_batch_keeps_its_payload_and_who_refused_it() -> None:
    (batch,) = the_answer(decoded(cases.malformed_batch())).fact_batches
    assert isinstance(batch, MalformedBatch)
    assert batch.raw.endswith('"subject": "emp_023", "va')
    assert batch.refused_by == cases.PARSER
    raw = cast(JsonObject, json.loads(export_bytes(cases.malformed_batch())))
    trace = cast(JsonObject, raw["trace"])
    stored = cast(list[JsonObject], trace["model_calls"])[0]["answer"]
    assert cast(JsonObject, stored)["fact_batches"] == [
        {
            "kind": "malformed",
            "raw": batch.raw,
            "refused_by": {"parser": "fact-batch-parser-v1", "schema_digest": "c" * 64},
        }
    ]


def test_a_refused_fact_is_never_stored_as_the_fact_that_refused_it() -> None:
    (batch,) = the_answer(decoded(cases.refused_fact())).fact_batches
    assert isinstance(batch, ParsedBatch)
    unreadable, refused, admitted = batch.entries
    assert isinstance(unreadable, RefusedInput)
    assert unreadable.reason is FactRefusal.UNDECODABLE
    assert '"value":7' in unreadable.raw
    assert isinstance(refused, Refused)
    assert refused.reason is FactRefusal.QUOTE_NOT_IN_CARRIER
    assert refused.fact.quote == "I led the Kafka migration"
    assert type(admitted).__name__ == "Admitted"


def test_a_cut_call_is_answered_and_its_tool_call_was_never_dispatched() -> None:
    export = decoded(cases.cut_call())
    call = the_call(export)
    assert (call.state, call.stop_reason) == (CallState.ANSWERED, "max_tokens")
    (tool_call,) = the_answer(export).tool_calls
    assert tool_call.disposition == Undispatched(UndispatchedReason.STOP_REASON_NOT_TOOL_USE)
    assert not any(isinstance(op.origin, ModelOrigin) for op in export.trace.operations)


def test_a_handled_fact_tool_links_to_its_batch_and_asks_no_source() -> None:
    export = decoded(cases.handled_fact_tool())
    answer = the_answer(export)
    (tool_call,) = answer.tool_calls
    assert tool_call.disposition == HandledAsBatch(0)
    assert isinstance(answer.fact_batches[0], ParsedBatch)
    assert [op.id for op in export.trace.operations] == ["op-1"]


def test_an_unresolved_dispatch_leaves_the_cost_a_floor_and_the_reservation_kept() -> None:
    export = decoded(cases.unresolved_then_answered())
    lost, again = the_call(export).dispatches
    assert (lost.sends, again.sends) == (Sends.UNRESOLVED, Sends.ONE)
    assert (lost.number, again.number, lost.segment, again.segment) == (1, 2, 1, 2)
    assert lost.attribution.kind is AttributionKind.UNRESOLVED and lost.outcome_position is None
    assert (lost.usage, lost.cost) == (None, None) and lost.allocation == cases.ALLOCATION
    # The token cap is auditable from the export: what the answered dispatch reported, plus
    # the worst case the unresolved one was counted for, against the cap the run ran under.
    assert again.usage is not None
    known = sum(value for _, value in again.usage.counters.counters)
    assert (known, lost.allocation_tokens) == (150, cases.ALLOCATION_TOKENS)
    assert known + lost.allocation_tokens <= export.record.caps.token_cap
    assert the_call(export).state is CallState.ANSWERED
    record = export.record
    assert (record.usage.model_calls, record.usage.dispatches) == (1, 2)
    assert record.cost == Cost(cases.PRICED.pico_usd, complete=False)
    assert record.reservation is not None
    assert record.reservation.state is ReservationState.KEPT
    assert record.reservation.kept_reason is KeptReason.UNRESOLVED_DISPATCH
    assert record.reservation.pico_usd == 2 * cases.ALLOCATION
    assert not timing_complete(record.timing)
    # No export of this history can state a settled cost.
    reconciled = replace(record.reservation, state=ReservationState.RECONCILED, kept_reason=None)
    with pytest.raises(ValueError, match="incomplete cumulative cost never carries a reconciled"):
        replace(export, record=replace(record, reservation=reconciled))


def test_the_nova_signature_is_behaviour_and_another_model_error_is_infrastructure() -> None:
    export = decoded(cases.nova_signature_beside_another())
    cut, other = export.trace.model_calls
    first, second = cut.dispatches[0], other.dispatches[0]
    assert isinstance(first.observation, ServiceError)
    assert isinstance(second.observation, ServiceError)
    assert first.observation.code == second.observation.code == "ModelErrorException"
    assert first.observation.message_signature == cases.NOVA_CUT
    # Neither error was retried beneath its dispatch, and each names its own send.
    assert (first.observation.sdk_retries, second.observation.sdk_retries) == (0, 0)
    assert (first.observation.provider_request_id, second.observation.provider_request_id) == (
        "req-nova-1",
        "req-nova-2",
    )
    assert (first.attribution.kind, first.attribution.rule) == (
        AttributionKind.BEHAVIOUR,
        "nova-cut-tool-use",
    )
    assert (second.attribution.kind, second.attribution.rule) == (
        AttributionKind.INFRASTRUCTURE,
        "unmatched",
    )
    # The cut call failed and the attempt went on; the other was asked again and answered.
    assert (cut.state, other.state) == (CallState.FAILED, CallState.ANSWERED)
    assert export.record.status is TerminalStatus.COMPLETED
    # An error is not free because it returned no usage: both leave the cost a floor.
    assert export.record.cost == Cost(cases.PRICED.pico_usd, complete=False)
    assert (export.record.usage.model_calls, export.record.usage.dispatches) == (2, 3)


def test_a_recovered_attempt_has_two_segments_and_an_incomplete_timing() -> None:
    export = decoded(cases.recovered_attempt())
    timing = export.record.timing
    assert [segment.end_recorded for segment in timing.segments] == [False, True]
    assert evidenced_active_ms(timing) == 1_200 + 6_000
    assert elapsed_ms(timing) == 600_000
    assert not timing_complete(timing)
    assert the_call(export).dispatches[0].segment == 2
    assert len(timing.harness_revisions) == 1
    assert export.record.approval.approver is Approver.AUTOMATIC


def test_an_abandoned_attempt_records_the_decision_and_an_unapproved_request() -> None:
    export = decoded(cases.abandoned_attempt())
    record = export.record
    assert record.status is TerminalStatus.FAILED
    assert record.failure is not None
    assert record.failure.site == HarnessSite(HarnessSiteName.ABANDONED)
    assert record.abandonment is not None
    assert (record.abandonment.authority, record.abandonment.ownership_generation) == (
        "operator",
        3,
    )
    assert record.approval.state is ApprovalState.REQUESTED_UNAPPROVED
    assert record.approval.approver is None
    assert record.approval.payload_digest == review_payload_digest((), cases.RULES)
    # The wait from the request to the segment's last durable offset is not active time.
    assert evidenced_active_ms(record.timing) == 4_800
    assert not timing_complete(record.timing)


def test_an_approval_wait_across_a_restart_is_left_out_of_the_active_time() -> None:
    export = decoded(cases.approval_wait_across_restart())
    timing = export.record.timing
    assert timing.approval_requested is not None and timing.approval_resumed is not None
    assert (timing.approval_requested.segment, timing.approval_resumed.segment) == (1, 3)
    # 7,900 + 600 + 2,050 evidenced, less waits of 900, 600 and 50.
    assert evidenced_active_ms(timing) == 7_000 + 0 + 2_000
    assert elapsed_ms(timing) == 7_200_000
    assert not timing_complete(timing)
    assert export.record.approval.state is ApprovalState.APPROVED


def test_a_wrong_scope_is_a_placement_and_an_unplaced_one_is_a_diagnostic() -> None:
    export = decoded(cases.wrong_scope_beside_unplaced())
    placed, unplaced = export.trace.composition.placements
    assert placed.fact.statement == unplaced.fact.statement
    assert (placed.fact.target_span, unplaced.fact.target_span) == (
        f.MEETING.title,
        "Ledger cutover",
    )
    assert placed.placement.state is PlacementState.PLACED
    assert placed.placement.artifact == event_ref(f.MEETING.id)
    assert unplaced.placement.state is PlacementState.UNPLACED
    # Both statements were admitted: a wrong binding is not an invention.
    (batch,) = the_answer(export).fact_batches
    assert isinstance(batch, ParsedBatch)
    assert [type(entry).__name__ for entry in batch.entries] == ["Admitted", "Admitted"]
    # The approval is over the payload a reviewer sees: the unbound requirement is in it.
    payload = review_payload(export.trace.claims, export.trace.composition)
    unbound = cast(list[JsonObject], payload["unbound"])
    assert [cast(JsonObject, entry["placement"])["state"] for entry in unbound] == ["unplaced"]
    assert export.record.approval.payload_digest == review_payload_digest(
        export.trace.claims, export.trace.composition
    )
    assert export.record.approval.payload_digest != review_payload_digest((), cases.RULES)


def test_the_first_tool_call_ends_the_attempt_and_the_second_was_never_reached() -> None:
    export = decoded(cases.first_tool_call_ends_the_attempt())
    first, second = the_answer(export).tool_calls
    assert first.disposition == AsOperation(OperationId("op-2"))
    assert second.disposition == Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)
    failed_at = export.trace.operation(OperationId("op-2"))
    assert failed_at is not None and isinstance(failed_at.outcome, DefectOutcome)
    assert export.record.failure is not None
    assert export.record.failure.site == OperationSite(OperationId("op-2"))
    assert export.record.approval.state is ApprovalState.NOT_REQUESTED


def test_a_tool_call_whose_result_was_lost_is_unresolved_and_not_undispatched() -> None:
    export = decoded(cases.tool_result_lost())
    (tool_call,) = the_answer(export).tool_calls
    assert isinstance(tool_call.disposition, UnresolvedToolCall)
    assert not any(isinstance(op.origin, ModelOrigin) for op in export.trace.operations)
    assert export.record.abandonment is not None
    assert export.record.abandonment.authority == "recovery"
    assert not timing_complete(export.record.timing)
