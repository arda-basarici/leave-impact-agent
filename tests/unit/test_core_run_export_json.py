"""The export codec: a full export with every outcome kind and every optional in both states
round-trips to an equal tree and to the same bytes, absent and empty stay distinct, and an
unknown format, a surplus field deep in the tree, an unknown outcome or origin kind and a
malformed nested record all refuse at decode naming what was wrong."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import cast

import pytest

from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    AbsentMeaning,
    AbsentOutcome,
    Answer,
    Approval,
    ApprovalState,
    Approver,
    AsOperation,
    Attribution,
    AttributionKind,
    CallConfiguration,
    CallSetting,
    Caps,
    ClaimAuthor,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    ComposingPolicy,
    Composition,
    Cost,
    DefectOutcome,
    Dispatch,
    DispatchPhase,
    DispatchSite,
    Document,
    DocumentKind,
    DocumentSection,
    Entity,
    Failure,
    FailureCategory,
    HarnessRevision,
    KeptReason,
    Leave,
    LeaveKind,
    LeaveStatus,
    ModelCall,
    ModelCallId,
    ModelOrigin,
    Observed,
    Operation,
    OperationId,
    OperationSite,
    OutageAssignment,
    PredicateName,
    PrefetchOrigin,
    PrefetchRule,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    ReportedUsage,
    RequestIdentity,
    Reservation,
    ReservationState,
    Retrieval,
    RetrievalKind,
    RunCondition,
    RunContext,
    RunExport,
    RunRecord,
    RunTrace,
    Segment,
    Source,
    System,
    SystemKind,
    TerminalStatus,
    Timing,
    ToolCall,
    TreeState,
    Unknown,
    UnknownReason,
    UnreachableOutcome,
    UsageAggregate,
    decode_export_bytes,
    decode_run_export,
    employee_ref,
    encode_run_export,
    export_bytes,
)
from leaveimpact.core.ids import (
    LeaveId,
    ScenarioId,
    WorldVersion,
    claim_id,
    clause_id,
    document_id,
    employee_id,
    leave_id,
)
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.model_calls import Observation

DIGEST = "a" * 64
COMMIT = "b" * 40
LEAVE: Observed[Entity] = Observed(
    Leave(
        leave_id(5),
        employee_id(17),
        date(2026, 9, 15),
        date(2026, 9, 19),
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    ),
    Source.FRAPPE,
)
RUNBOOK: Observed[Entity] = Observed(
    Document(
        document_id(4),
        "Payments runbook",
        DocumentKind.RUNBOOK,
        date(2026, 3, 1),
        (DocumentSection(clause_id(11), "Kafka is owned by Alice."),),
    ),
    Source.CORPUS,
)
CONTEXT = RunContext(
    ScenarioId("scenario_003"),
    WorldVersion("7b806ed6"),
    LeaveId("leave_005"),
    datetime(2026, 9, 14, 22, 30, tzinfo=UTC),
    "Europe/Istanbul",
)
SELECTION = PricingSelection("model-a", "eu-central-1", "on_demand")
PRICING = PricingBasis(
    DIGEST,
    "USD",
    date(2026, 9, 1),
    (
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500_000),
        PricingRow(
            "model-a",
            "eu-central-1",
            "on_demand",
            "cache_read_input_tokens",
            110_000,
            AbsentMeaning.ZERO,
        ),
    ),
)
COMPOSITION = Composition(ClaimAuthor.RULES, ComposingPolicy("a-policy", DIGEST), (), ())
REQUEST = RequestIdentity(DIGEST, "Converse", "eu.model", "eu-central-1", None)
ADMITTED = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _dispatch(
    intent: int,
    observation: Observation,
    read_as: AttributionKind,
    usage: dict[str, object] | None,
    cost: Cost | None,
    shown: tuple[str, ...] = (),
) -> Dispatch:
    return Dispatch(
        number=1,
        segment=1,
        intent_position=intent,
        outcome_position=intent + 1,
        request=REQUEST,
        input_reads=tuple(OperationId(read) for read in shown),
        observation=observation,
        attribution=Attribution(read_as, "a-rule"),
        usage=None if usage is None else ReportedUsage(usage),
        cost=cost,
        zero_cost_rule=None,
        allocation=5_000_000_000,
        allocation_tokens=4_608,
    )


def _calls() -> tuple[ModelCall, ...]:
    """Three calls: one that asked for four reads, one whose send timed out, and one that
    answered with an empty usage object, so a usage is present, empty and absent in turn."""
    asked = Answer(
        True,
        tuple(
            ToolCall(f"tu_{number}", tool, AsOperation(OperationId(operation)))
            for number, (tool, operation) in enumerate(
                (
                    ("leaves_within", "op-2"),
                    ("search", "op-3"),
                    ("work_item", "op-6"),
                    ("search", "op-7"),
                ),
                start=1,
            )
        ),
        (),
    )
    return (
        ModelCall(
            ModelCallId("call-1"),
            "investigator",
            (
                _dispatch(
                    2,
                    CompleteResponse("tool_use", 840, 0),
                    AttributionKind.BEHAVIOUR,
                    {"inputTokens": 120, "outputTokens": 30},
                    Cost(297_000_000, True),
                    shown=("op-1",),
                ),
            ),
            asked,
        ),
        ModelCall(
            ModelCallId("call-2"),
            "investigator",
            (
                _dispatch(
                    10,
                    ClientError(ClientErrorKind.TIMEOUT, "timeout after retries"),
                    AttributionKind.INFRASTRUCTURE,
                    None,
                    None,
                ),
            ),
            None,
        ),
        ModelCall(
            ModelCallId("call-3"),
            "investigator",
            (
                _dispatch(
                    12,
                    CompleteResponse("end_turn", 12, None),
                    AttributionKind.BEHAVIOUR,
                    {},
                    Cost(0, False),
                ),
            ),
            Answer(False, (), ()),
        ),
    )


def _operations() -> tuple[Operation, ...]:
    span = {"start": "2026-09-10", "end": "2026-09-19"}
    return (
        Operation(
            OperationId("op-1"),
            PrefetchOrigin(),
            "leave",
            Source.FRAPPE,
            {"id": "leave_005"},
            RecordOutcome(LEAVE),
            1,
        ),
        Operation(
            OperationId("op-2"),
            ModelOrigin(ModelCallId("call-1")),
            "leaves_within",
            Source.FRAPPE,
            {"span": span},
            RecordsOutcome(()),
            4,
        ),
        Operation(
            OperationId("op-3"),
            ModelOrigin(ModelCallId("call-1")),
            "search",
            Source.CORPUS,
            {"query": "kafka owner", "limit": 5},
            RecordsOutcome((RUNBOOK,)),
            5,
        ),
        Operation(
            OperationId("op-4"),
            PrefetchOrigin(),
            "employee",
            Source.FRAPPE,
            {"id": "emp_099"},
            AbsentOutcome(),
            6,
        ),
        Operation(
            OperationId("op-5"),
            PrefetchOrigin(),
            "work_items",
            Source.JIRA,
            {},
            UnreachableOutcome(Source.JIRA, "refused after 3 attempts"),
            7,
        ),
        Operation(
            OperationId("op-6"),
            ModelOrigin(ModelCallId("call-1")),
            "work_item",
            Source.JIRA,
            {"id": "ticket_042"},
            DefectOutcome(Source.JIRA, "LIA-42", "no world id"),
            8,
        ),
        Operation(
            OperationId("op-7"),
            ModelOrigin(ModelCallId("call-1")),
            "search",
            None,
            {"query": "", "limit": 500},
            RefusedCallOutcome("query is non-blank; limit above 20"),
            9,
        ),
    )


def _claims() -> tuple[Unknown, ...]:
    return (
        Unknown(
            claim_id=claim_id(2),
            evidence_refs=(),
            subject=employee_ref(employee_id(3)),
            required_fact=PredicateName.HAS_SKILL,
            reason=UnknownReason.INACCESSIBLE,
        ),
        Unknown(
            claim_id=claim_id(1),
            evidence_refs=(),
            subject=employee_ref(employee_id(17)),
            required_fact=PredicateName.HAS_SKILL,
            reason=UnknownReason.ABSENT,
        ),
    )


def _record(status: TerminalStatus, failure: Failure | None) -> RunRecord:
    return RunRecord(
        observed_condition=RunCondition.all_reachable().without(Source.JIRA),
        outage=OutageAssignment(frozenset({Source.JIRA}), DIGEST),
        corpus_level="base",
        preregistration_commit=COMMIT,
        attribution_table=DIGEST,
        model_configurations=(
            ("investigator", CallConfiguration("eu.model", (CallSetting("temperature", 0),))),
        ),
        pricing_selections=(("investigator", SELECTION),),
        prompt_digests=(("investigator", "system", DIGEST), ("investigator", "finalize", DIGEST)),
        tool_surface_digests=(("investigator", DIGEST),),
        system=System(SystemKind.AGENT, "reference"),
        retrieval=Retrieval(RetrievalKind.FULL_TEXT, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_output"),
        status=status,
        failure=failure,
        abandonment=None,
        timing=Timing(
            (Segment(1, HarnessRevision(COMMIT, TreeState.DIRTY), 12_000, True),),
            ADMITTED,
            ADMITTED,
            None,
            None,
        ),
        usage=UsageAggregate((("input_tokens", 120, 1), ("output_tokens", 30, 1)), 3, 3),
        cost=Cost(297_000_000, False),
        reservation=Reservation(
            15_000_000_000, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 4
        ),
        approval=(
            Approval(ApprovalState.NOT_REQUESTED, None, None)
            if failure is not None
            else Approval(ApprovalState.APPROVED, Approver.AUTOMATIC, DIGEST)
        ),
        pricing=PRICING,
    )


def _export(
    status: TerminalStatus = TerminalStatus.COMPLETED, failure: Failure | None = None
) -> RunExport:
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-7",
        2,
        CONTEXT,
        _record(status, failure),
        RunTrace(_calls(), _operations(), _claims(), COMPOSITION),
    )


def _reparsed(export: RunExport) -> object:
    return json.loads(export_bytes(export))


def _nested(data: object, *path: str | int) -> JsonObject:
    found = data
    for step in path:
        found = (
            cast(list[object], found)[step]
            if isinstance(step, int)
            else cast(JsonObject, found)[step]
        )
    return cast(JsonObject, found)


def test_a_full_export_round_trips_to_an_equal_tree_and_the_same_bytes() -> None:
    export = _export()
    decoded = decode_run_export(_reparsed(export))
    assert decoded == export
    assert export_bytes(decoded) == export_bytes(export)
    assert [claim.claim_id for claim in decoded.trace.claims] == ["claim_001", "claim_002"]


def test_a_failed_export_round_trips_with_its_failure_at_the_fault() -> None:
    at_send = DispatchSite(ModelCallId("call-2"), 1, DispatchPhase.SEND)
    failed = _export(
        TerminalStatus.FAILED,
        Failure(FailureCategory.INFRASTRUCTURE, at_send, "timeout after retries"),
    )
    assert decode_run_export(_reparsed(failed)) == failed
    assert _nested(_reparsed(failed), "record", "failure")["site"] == {
        "kind": "dispatch",
        "model_call": "call-2",
        "dispatch": 1,
        "phase": "send",
    }
    defect = _export(
        TerminalStatus.FAILED,
        Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-6")), "no world id"),
    )
    assert decode_run_export(_reparsed(defect)) == defect


def test_absent_and_empty_stay_distinct_in_the_bytes() -> None:
    data = _nested(_reparsed(_export()), "trace")
    calls = cast(list[JsonObject], data["model_calls"])
    timed_out = _nested(calls, 1, "dispatches", 0)
    assert timed_out["usage"] is None and timed_out["cost"] is None
    assert calls[1]["answer"] is None
    empty = _nested(calls, 2, "dispatches", 0)
    assert empty["usage"] == {"raw": {}, "counters": []}
    assert empty["cost"] == {"pico_usd": 0, "complete": False}
    assert calls[2]["answer"] == {"text_present": False, "tool_calls": [], "fact_batches": []}
    assert _nested(calls, 2, "dispatches", 0, "observation")["sdk_retries"] is None
    assert _nested(calls, 0, "dispatches", 0, "observation")["sdk_retries"] == 0
    assert _nested(calls, 0, "dispatches", 0)["input_reads"] == ["op-1"]
    assert _nested(calls, 0, "dispatches", 0, "request")["sent_body_digest"] is None
    assert _nested(calls, 0, "dispatches", 0, "observation")["provider_request_id"] is None
    assert _nested(calls, 0, "dispatches", 0)["allocation_tokens"] == 4_608
    operations = cast(list[JsonObject], data["operations"])
    assert operations[1]["outcome"] == {"kind": "records", "records": []}
    assert operations[3]["outcome"] == {"kind": "absent"}
    assert operations[6]["source"] is None
    assert cast(JsonObject, operations[1]["arguments"])["span"] == {
        "start": "2026-09-10",
        "end": "2026-09-19",
    }
    record = _nested(_reparsed(_export()), "record")
    assert record["failure"] is None and record["abandonment"] is None
    assert _nested(record, "timing")["approval_requested"] is None


def test_the_tree_opens_with_the_format_version_and_the_identity() -> None:
    encoded = encode_run_export(_export())
    assert list(encoded)[:3] == ["format_version", "run_id", "attempt"]
    assert canonical_json(encoded).startswith('{"format_version":2,"run_id":"run-7","attempt":2,')


def test_another_format_refuses_before_anything_else() -> None:
    data = cast(JsonObject, _reparsed(_export()))
    data["format_version"] = 1
    del data["trace"]
    with pytest.raises(ValueError, match="this code reads export format 2, got 1"):
        decode_run_export(data)
    data["format_version"] = True
    with pytest.raises(ValueError, match="format_version is an integer, got True"):
        decode_run_export(data)


def test_a_surplus_or_missing_field_deep_in_the_tree_refuses_naming_the_object() -> None:
    data = _reparsed(_export())
    _nested(data, "record", "caps")["burst"] = 1
    with pytest.raises(ValueError, match=r"the caps has fields .*surplus \['burst'\]"):
        decode_run_export(data)
    data = _reparsed(_export())
    del _nested(data, "trace", "model_calls", 0)["answer"]
    with pytest.raises(ValueError, match=r"a model call has fields .*missing \['answer'\]"):
        decode_run_export(data)
    data = _reparsed(_export())
    del _nested(data, "trace", "model_calls", 0, "dispatches", 0)["allocation_tokens"]
    with pytest.raises(
        ValueError, match=r"a dispatch has fields .*missing \['allocation_tokens'\]"
    ):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "model_calls", 0, "dispatches", 0)["retries"] = 2
    with pytest.raises(ValueError, match=r"a dispatch has fields .*surplus \['retries'\]"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 0, "outcome", "record")["read_at"] = "x"
    with pytest.raises(ValueError, match=r"an observed record has fields .*surplus \['read_at'\]"):
        decode_run_export(data)


def test_an_unknown_kind_or_value_refuses_by_name() -> None:
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 0, "outcome")["kind"] = "partial"
    with pytest.raises(ValueError, match="an outcome is record, absent, records, .*got 'partial'"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 0, "origin")["kind"] = "human"
    with pytest.raises(ValueError, match="an origin is prefetch, harness or model, got 'human'"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "model_calls", 0, "dispatches", 0, "observation")["kind"] = "echo"
    with pytest.raises(ValueError, match="an observation is complete_response, .*got 'echo'"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "model_calls", 0, "answer", "tool_calls", 0, "disposition")[
        "kind"
    ] = "dropped"
    with pytest.raises(ValueError, match="a disposition is operation, handled, .*got 'dropped'"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "record")["status"] = "done"
    with pytest.raises(ValueError, match="done"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "context")["scenario_id"] = "SC-3"
    with pytest.raises(ValueError, match="scenario_id has the form scenario_NNN, got 'SC-3'"):
        decode_run_export(data)


def test_the_constructors_invariants_hold_on_decode_too() -> None:
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 1, "origin")["model_call"] = "call-3"
    with pytest.raises(ValueError, match="whose answer holds no tool call that became it"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "model_calls", 1, "dispatches", 0)["observation"] = {
        "kind": "no_recorded_outcome"
    }
    with pytest.raises(ValueError, match="an outcome position is held exactly when"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 0)["source"] = "jira"
    with pytest.raises(ValueError, match="a record read from frappe in an operation on jira"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "record", "approval")["state"] = "not_requested"
    with pytest.raises(ValueError, match="an approver is named exactly"):
        decode_run_export(data)


def test_a_usages_counters_are_the_reading_of_its_raw_object_or_the_tree_refuses() -> None:
    data = _reparsed(_export())
    usage = _nested(data, "trace", "model_calls", 0, "dispatches", 0, "usage")
    assert usage["raw"] == {"inputTokens": 120, "outputTokens": 30}
    assert usage["counters"] == [
        {"name": "input_tokens", "value": 120},
        {"name": "output_tokens", "value": 30},
    ]
    cast(list[JsonObject], usage["counters"])[0]["value"] = 121
    with pytest.raises(ValueError, match="a usage's counters are the reading of its raw object"):
        decode_run_export(data)


def test_a_non_canonical_instant_in_the_context_is_refused_rather_than_normalized() -> None:
    data = _reparsed(_export())
    _nested(data, "context", "now")["at"] = "2026-09-14T22:30:00Z"
    with pytest.raises(ValueError, match="now is spelled '2026-09-14T22:30:00Z'"):
        decode_run_export(data)


def _reading_only(operation: Operation) -> RunExport:
    """The full export's record around a trace of one read and no model call."""
    base = _export()
    record = replace(
        base.record,
        cost=None,
        reservation=Reservation(0, ReservationState.RECONCILED, None, 4),
        usage=UsageAggregate((), 0, 0),
    )
    return replace(base, record=record, trace=RunTrace((), (operation,), (), COMPOSITION))


def test_equal_arguments_spelled_in_another_key_order_are_the_same_bytes() -> None:
    """A key's position says nothing in JSON, so two exports whose arguments differ only
    in nested key order are one export and one byte sequence."""
    forward = Operation(
        OperationId("op-9"),
        PrefetchOrigin(),
        "leaves_within",
        Source.FRAPPE,
        {"span": {"start": "2026-09-10", "end": "2026-09-19"}, "limit": 5},
        AbsentOutcome(),
        1,
    )
    backward = Operation(
        OperationId("op-9"),
        PrefetchOrigin(),
        "leaves_within",
        Source.FRAPPE,
        {"limit": 5, "span": {"end": "2026-09-19", "start": "2026-09-10"}},
        AbsentOutcome(),
        1,
    )
    assert forward == backward
    one, other = _reading_only(forward), _reading_only(backward)
    assert export_bytes(one) == export_bytes(other)
    assert '"arguments":{"limit":5,"span":{"end":"2026-09-19","start":"2026-09-10"}}' in (
        export_bytes(one).decode("utf-8")
    )


def test_the_bytes_decoder_accepts_only_the_canonical_encoding() -> None:
    export = _export()
    assert decode_export_bytes(export_bytes(export)) == export
    assert decode_export_bytes(export_bytes(export).decode("utf-8")) == export
    pretty = json.dumps(json.loads(export_bytes(export)), indent=2)
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_export_bytes(pretty)
    data = _reparsed(export)
    reachable = cast(list[str], _nested(data, "record", "observed_condition")["reachable"])
    reachable.append(reachable[0])  # a duplicate the set would silently collapse
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_export_bytes(canonical_json(data))
    data = _reparsed(export)
    prompts = cast(list[object], _nested(data, "record")["prompt_digests"])
    prompts.reverse()  # an order the constructor would silently sort
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_export_bytes(canonical_json(data))


def test_a_setting_spelled_a_second_way_is_not_the_canonical_encoding() -> None:
    """``temperature`` 0 and 0.0 are one setting, so only one spelling is the export's."""
    data = _reparsed(_export())
    setting = _nested(data, "record", "model_configurations", 0, "configuration", "settings", 0)
    assert setting == {"name": "temperature", "value": 0}
    setting["value"] = 0.0
    assert decode_run_export(data) == _export()
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_export_bytes(canonical_json(data))


def test_arguments_decode_frozen_and_equal_to_what_was_encoded() -> None:
    decoded = decode_run_export(_reparsed(_export()))
    assert decoded.trace.operations[1].arguments == _operations()[1].arguments
    with pytest.raises(TypeError):
        cast(dict[str, object], decoded.trace.operations[1].arguments)["span"] = {}
    assert replace(decoded, attempt=3) != decoded
