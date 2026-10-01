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
    Caps,
    Cost,
    DefectOutcome,
    Document,
    DocumentKind,
    DocumentSection,
    Entity,
    Failure,
    FailureCategory,
    HarnessRevision,
    Leave,
    LeaveKind,
    LeaveStatus,
    ModelCallId,
    ModelCallOutcome,
    ModelCallRecord,
    ModelConfiguration,
    ModelOrigin,
    Observed,
    Operation,
    OperationId,
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
    Retrieval,
    RetrievalKind,
    RunCondition,
    RunContext,
    RunExport,
    RunRecord,
    RunTrace,
    Setting,
    Source,
    System,
    SystemKind,
    TerminalStatus,
    TreeState,
    Unknown,
    UnknownReason,
    UnreachableOutcome,
    Usage,
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
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500),
        PricingRow(
            "model-a",
            "eu-central-1",
            "on_demand",
            "cache_read_input_tokens",
            110,
            AbsentMeaning.ZERO,
        ),
    ),
)


def _calls() -> tuple[ModelCallRecord, ...]:
    return (
        ModelCallRecord(
            ModelCallId("call-1"),
            "investigator",
            ModelCallOutcome.TOOL_CALLS,
            "tool_use",
            840,
            DIGEST,
            Usage((("input_tokens", 120), ("output_tokens", 30))),
            Cost(297_000, True),
            None,
        ),
        ModelCallRecord(
            ModelCallId("call-2"),
            "investigator",
            ModelCallOutcome.PROVIDER_FAULT,
            None,
            None,
            DIGEST,
            None,
            None,
            "timeout after retries",
        ),
        ModelCallRecord(
            ModelCallId("call-3"),
            "investigator",
            ModelCallOutcome.CLAIMS,
            "end_turn",
            12,
            DIGEST,
            Usage(()),
            Cost(0, False),
            None,
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
        ),
        Operation(
            OperationId("op-2"),
            ModelOrigin(ModelCallId("call-1")),
            "leaves_within",
            Source.FRAPPE,
            {"span": span},
            RecordsOutcome(()),
        ),
        Operation(
            OperationId("op-3"),
            ModelOrigin(ModelCallId("call-1")),
            "search",
            Source.CORPUS,
            {"query": "kafka owner", "limit": 5},
            RecordsOutcome((RUNBOOK,)),
        ),
        Operation(
            OperationId("op-4"),
            PrefetchOrigin(),
            "employee",
            Source.FRAPPE,
            {"id": "emp_099"},
            AbsentOutcome(),
        ),
        Operation(
            OperationId("op-5"),
            PrefetchOrigin(),
            "work_items",
            Source.JIRA,
            {},
            UnreachableOutcome(Source.JIRA, "refused after 3 attempts"),
        ),
        Operation(
            OperationId("op-6"),
            ModelOrigin(ModelCallId("call-1")),
            "work_item",
            Source.JIRA,
            {"id": "ticket_042"},
            DefectOutcome(Source.JIRA, "LIA-42", "no world id"),
        ),
        Operation(
            OperationId("op-7"),
            ModelOrigin(ModelCallId("call-1")),
            "search",
            None,
            {"query": "", "limit": 500},
            RefusedCallOutcome("query is non-blank; limit above 20"),
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
        harness=HarnessRevision(COMMIT, TreeState.DIRTY),
        preregistration_commit=COMMIT,
        model_configurations=(
            ("investigator", ModelConfiguration("eu.model", (Setting("temperature", 0),))),
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
        usage=UsageAggregate((("input_tokens", 120, 1), ("output_tokens", 30, 1)), 3, 12_000),
        cost=Cost(297_000, False),
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
        RunTrace(_calls(), _operations(), _claims()),
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
    failed = _export(
        TerminalStatus.FAILED,
        Failure(FailureCategory.INFRASTRUCTURE, "call-2", "timeout after retries"),
    )
    assert decode_run_export(_reparsed(failed)) == failed
    defect = _export(TerminalStatus.FAILED, Failure(FailureCategory.DEFECT, "op-6", "no world id"))
    assert decode_run_export(_reparsed(defect)) == defect


def test_absent_and_empty_stay_distinct_in_the_bytes() -> None:
    data = _nested(_reparsed(_export()), "trace")
    calls = cast(list[JsonObject], data["model_calls"])
    assert (
        calls[1]["usage"] is None and calls[1]["cost"] is None and calls[1]["stop_reason"] is None
    )
    assert calls[2]["usage"] == {"counters": []}
    assert calls[2]["cost"] == {"nano_usd": 0, "complete": False}
    operations = cast(list[JsonObject], data["operations"])
    assert operations[1]["outcome"] == {"kind": "records", "records": []}
    assert operations[3]["outcome"] == {"kind": "absent"}
    assert operations[6]["source"] is None
    assert cast(JsonObject, operations[1]["arguments"])["span"] == {
        "start": "2026-09-10",
        "end": "2026-09-19",
    }


def test_the_tree_opens_with_the_format_version_and_the_identity() -> None:
    encoded = encode_run_export(_export())
    assert list(encoded)[:3] == ["format_version", "run_id", "attempt"]
    assert canonical_json(encoded).startswith('{"format_version":1,"run_id":"run-7","attempt":2,')


def test_another_format_refuses_before_anything_else() -> None:
    data = cast(JsonObject, _reparsed(_export()))
    data["format_version"] = 2
    del data["trace"]
    with pytest.raises(ValueError, match="this code reads export format 1, got 2"):
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
    del _nested(data, "trace", "model_calls", 0)["fault"]
    with pytest.raises(ValueError, match=r"a model call has fields .*missing \['fault'\]"):
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
    with pytest.raises(ValueError, match="an origin is prefetch or model, got 'human'"):
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
    with pytest.raises(ValueError, match="which emitted claims, not tool calls"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "model_calls", 1)["usage"] = {"counters": []}
    with pytest.raises(ValueError, match="a provider fault reports no usage"):
        decode_run_export(data)
    data = _reparsed(_export())
    _nested(data, "trace", "operations", 0)["source"] = "jira"
    with pytest.raises(ValueError, match="a record read from frappe in an operation on jira"):
        decode_run_export(data)


def test_a_non_canonical_instant_in_the_context_is_refused_rather_than_normalized() -> None:
    data = _reparsed(_export())
    _nested(data, "context", "now")["at"] = "2026-09-14T22:30:00Z"
    with pytest.raises(ValueError, match="now is spelled '2026-09-14T22:30:00Z'"):
        decode_run_export(data)


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
    )
    backward = Operation(
        OperationId("op-9"),
        PrefetchOrigin(),
        "leaves_within",
        Source.FRAPPE,
        {"limit": 5, "span": {"end": "2026-09-19", "start": "2026-09-10"}},
        AbsentOutcome(),
    )
    assert forward == backward
    base = _export()
    one = replace(base, trace=RunTrace(base.trace.model_calls, (forward,), base.trace.claims))
    other = replace(base, trace=RunTrace(base.trace.model_calls, (backward,), base.trace.claims))
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


def test_arguments_decode_frozen_and_equal_to_what_was_encoded() -> None:
    decoded = decode_run_export(_reparsed(_export()))
    assert decoded.trace.operations[1].arguments == _operations()[1].arguments
    with pytest.raises(TypeError):
        cast(dict[str, object], decoded.trace.operations[1].arguments)["span"] = {}
    assert replace(decoded, attempt=3) != decoded
