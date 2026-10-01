"""The run export's plain data holds the rulings' invariants at construction: usage counters in
the declared order and never synthesized, a cost only over a usage, a fault exactly on a
provider fault, an accepted read naming its source and every record read from it, ids unique
and a model-originated read naming a call the trace holds, a failure exactly on a failed
status and pointing into the trace, rules-only with no model and no retrieval, reserves inside
the caps, an embedding model exactly for vector retrieval, and role-indexed provenance
unique by role and held in role order."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    AbsentOutcome,
    Caps,
    Cost,
    DefectOutcome,
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
    employee_ref,
    is_completed_read,
    is_failed_read,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, claim_id, employee_id, leave_id

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
CALL = ModelCallId("call-1")
REPORTED = Usage((("input_tokens", 120), ("output_tokens", 30)))
PRICED = Cost(297_000, True)
PREFETCH = PrefetchOrigin()
AGENT = System(SystemKind.AGENT, "reference")
FULL_TEXT = Retrieval(RetrievalKind.FULL_TEXT, None)
CONTEXT = RunContext(
    ScenarioId("scenario_003"),
    WorldVersion("4f2c"),
    LeaveId("leave_005"),
    datetime(2026, 9, 14, 22, 30, tzinfo=UTC),
    "Europe/Istanbul",
)
PRICING = PricingBasis(
    DIGEST,
    "USD",
    date(2026, 9, 1),
    (
        PricingRow(
            "eu.anthropic.claude-haiku-4-5", "eu-central-1", "on_demand", "input_tokens", 1_100
        ),
        PricingRow(
            "eu.anthropic.claude-haiku-4-5", "eu-central-1", "on_demand", "output_tokens", 5_500
        ),
    ),
)


def _call(
    id: str = "call-1",
    outcome: ModelCallOutcome = ModelCallOutcome.CLAIMS,
    usage: Usage | None = REPORTED,
    cost: Cost | None = PRICED,
    fault: str | None = None,
) -> ModelCallRecord:
    return ModelCallRecord(
        ModelCallId(id), "investigator", outcome, "end_turn", 840, DIGEST, usage, cost, fault
    )


def _operation(
    id: str = "op-1",
    origin: PrefetchOrigin | ModelOrigin = PREFETCH,
    source: Source | None = Source.FRAPPE,
    outcome: object = RecordOutcome(LEAVE),
) -> Operation:
    return Operation(OperationId(id), origin, "leave", source, {"id": "leave_005"}, outcome)  # type: ignore[arg-type]


def _claim() -> Unknown:
    return Unknown(
        claim_id=claim_id(1),
        evidence_refs=(),
        subject=employee_ref(employee_id(17)),
        required_fact=PredicateName.HAS_SKILL,
        reason=UnknownReason.ABSENT,
    )


def _record(
    system: System = AGENT,
    retrieval: Retrieval = FULL_TEXT,
    status: TerminalStatus = TerminalStatus.COMPLETED,
    failure: Failure | None = None,
    configurations: tuple[tuple[str, ModelConfiguration], ...] = (
        ("investigator", ModelConfiguration("eu.model", (Setting("temperature", 0),))),
    ),
) -> RunRecord:
    return RunRecord(
        observed_condition=RunCondition.all_reachable(),
        outage=OutageAssignment(frozenset(), DIGEST),
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        model_configurations=configurations,
        prompt_digests=(("investigator", "system", DIGEST),),
        tool_surface_digests=(("investigator", DIGEST),),
        system=system,
        retrieval=retrieval,
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_output"),
        status=status,
        failure=failure,
        usage=UsageAggregate((("input_tokens", 120, 1), ("output_tokens", 30, 1)), 1, 12_000),
        cost=Cost(297_000, True),
        pricing=PRICING,
    )


def _export(record: RunRecord | None = None, trace: RunTrace | None = None) -> RunExport:
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
        CONTEXT,
        record if record is not None else _record(),
        trace if trace is not None else RunTrace((_call(),), (_operation(),), (_claim(),)),
    )


# --- Usage and cost ---------------------------------------------------------------------


def test_usage_counters_hold_the_declared_order_and_a_missing_one_reads_as_unknown() -> None:
    usage = Usage((("input_tokens", 120), ("cache_read_input_tokens", 40)))
    assert usage.value("output_tokens") is None
    assert usage.value("cache_read_input_tokens") == 40
    with pytest.raises(ValueError, match="declared order"):
        Usage((("output_tokens", 30), ("input_tokens", 120)))
    with pytest.raises(ValueError, match="not a usage counter"):
        Usage((("total_tokens", 150),))
    with pytest.raises(ValueError, match="reported once"):
        Usage((("input_tokens", 1), ("input_tokens", 2)))
    with pytest.raises(ValueError, match="non-negative integer"):
        Usage((("input_tokens", True),))


def test_an_aggregate_carries_its_coverage_and_a_sum_over_no_call_is_zero() -> None:
    aggregate = UsageAggregate((("input_tokens", 500, 3),), 4, 9_000)
    assert aggregate.value("input_tokens") == (500, 3)
    assert aggregate.value("output_tokens") is None
    with pytest.raises(ValueError, match="reported by 5 calls of 4"):
        UsageAggregate((("input_tokens", 500, 5),), 4, 9_000)
    with pytest.raises(ValueError, match="a sum over no reporting call is zero"):
        UsageAggregate((("input_tokens", 500, 0),), 4, 9_000)


def test_a_cost_prices_a_reported_usage_and_a_fault_is_recorded_exactly_on_a_provider_fault() -> (
    None
):
    with pytest.raises(ValueError, match="a cost prices a reported usage"):
        _call(usage=None, cost=Cost(1, False))
    assert _call(usage=None, cost=None).cost is None
    with pytest.raises(ValueError, match="exactly on a provider fault"):
        _call(fault="timeout")
    with pytest.raises(ValueError, match="exactly on a provider fault"):
        _call(outcome=ModelCallOutcome.PROVIDER_FAULT)
    faulted = _call(outcome=ModelCallOutcome.PROVIDER_FAULT, usage=None, cost=None, fault="timeout")
    assert faulted.fault == "timeout"
    with pytest.raises(ValueError, match="nano-dollars"):
        Cost(-1, True)


# --- Operations -------------------------------------------------------------------------


def test_the_six_outcomes_split_into_completed_failed_and_neither() -> None:
    completed = (RecordOutcome(LEAVE), AbsentOutcome(), RecordsOutcome(()))
    failed = (
        UnreachableOutcome(Source.JIRA, "refused"),
        DefectOutcome(Source.JIRA, "LIA-42", "no id"),
    )
    assert all(is_completed_read(o) and not is_failed_read(o) for o in completed)
    assert all(is_failed_read(o) and not is_completed_read(o) for o in failed)
    refused = RefusedCallOutcome("limit above the bound")
    assert not is_completed_read(refused) and not is_failed_read(refused)


def test_an_accepted_read_names_its_source_and_every_record_was_read_from_it() -> None:
    with pytest.raises(ValueError, match="only a refused call may name none"):
        _operation(source=None, outcome=AbsentOutcome())
    assert _operation(source=None, outcome=RefusedCallOutcome("unknown tool")).source is None
    with pytest.raises(ValueError, match="a record read from frappe in an operation on jira"):
        _operation(source=Source.JIRA, outcome=RecordsOutcome((LEAVE,)))
    with pytest.raises(ValueError, match="a failure of jira in an operation on frappe"):
        _operation(outcome=UnreachableOutcome(Source.JIRA, "refused"))
    assert _operation(outcome=RecordsOutcome(())).source is Source.FRAPPE


def test_arguments_are_frozen_as_accepted() -> None:
    operation = _operation()
    with pytest.raises(TypeError):
        operation.arguments["id"] = "leave_006"  # type: ignore[index]
    assert dict(operation.arguments) == {"id": "leave_005"}


# --- The trace --------------------------------------------------------------------------


def test_ids_are_unique_and_a_model_originated_read_names_a_call_the_trace_holds() -> None:
    with pytest.raises(ValueError, match="model call ids are unique"):
        RunTrace((_call(), _call()), (), ())
    with pytest.raises(ValueError, match="operation ids are unique"):
        RunTrace((), (_operation(), _operation()), ())
    with pytest.raises(
        ValueError, match="answers model call 'call-9', which the trace does not hold"
    ):
        RunTrace((_call(),), (_operation(origin=ModelOrigin(ModelCallId("call-9"))),), ())
    with pytest.raises(ValueError, match="claim ids are unique"):
        RunTrace((), (), (_claim(), _claim()))
    trace = RunTrace((_call(),), (_operation(origin=ModelOrigin(CALL)),), (_claim(),))
    assert trace.model_call(CALL).role == "investigator"
    assert trace.holds("op-1") and trace.holds("call-1") and not trace.holds("op-2")


# --- The record -------------------------------------------------------------------------


def test_a_failure_is_recorded_exactly_when_the_status_is_failed() -> None:
    failure = Failure(FailureCategory.DEFECT, "op-1", "no world id")
    with pytest.raises(ValueError, match="exactly when the status is failed"):
        _record(failure=failure)
    with pytest.raises(ValueError, match="exactly when the status is failed"):
        _record(status=TerminalStatus.FAILED)
    assert _record(status=TerminalStatus.FAILED, failure=failure).failure is failure


def test_rules_only_calls_no_model_and_retrieves_nothing() -> None:
    rules_only = System(SystemKind.RULES_ONLY, "frozen")
    with pytest.raises(ValueError, match="records no model configuration"):
        _record(system=rules_only, retrieval=Retrieval(RetrievalKind.NONE, None))
    with pytest.raises(ValueError, match="its retrieval is none"):
        _record(system=rules_only, configurations=())
    record = _record(
        system=rules_only, retrieval=Retrieval(RetrievalKind.NONE, None), configurations=()
    )
    assert record.model_configurations == ()


def test_role_indexed_provenance_is_unique_by_role_and_held_in_role_order() -> None:
    one = ModelConfiguration("eu.model", ())
    with pytest.raises(ValueError, match="a role calls one model configuration"):
        _record(configurations=(("investigator", one), ("investigator", one)))
    record = _record(configurations=(("synthesizer", one), ("investigator", one)))
    assert [role for role, _ in record.model_configurations] == ["investigator", "synthesizer"]
    with pytest.raises(ValueError, match="a role sees one tool surface"):
        replace(record, tool_surface_digests=(("a", DIGEST), ("a", DIGEST)))
    with pytest.raises(ValueError, match="a prompt is digested once per role and name"):
        replace(record, prompt_digests=(("a", "system", DIGEST), ("a", "system", DIGEST)))
    with pytest.raises(ValueError, match="the a system prompt digest is a SHA-256"):
        replace(record, prompt_digests=(("a", "system", "deadbeef"),))


def test_the_reserves_sit_inside_the_caps_and_an_embedding_model_names_vector_retrieval() -> None:
    with pytest.raises(ValueError, match="call reserve sits inside the call cap, got 20 of 20"):
        Caps(20, 100_000, 20, 5_000, "input_output")
    with pytest.raises(ValueError, match="token reserve sits inside the token cap"):
        Caps(20, 100_000, 2, 100_000, "input_output")
    with pytest.raises(ValueError, match="call_cap is positive"):
        Caps(0, 100_000, 0, 5_000, "input_output")
    with pytest.raises(ValueError, match="exactly for vector retrieval"):
        Retrieval(RetrievalKind.VECTOR, None)
    assert Retrieval(RetrievalKind.VECTOR, "eu.embedder").embedding_model == "eu.embedder"


def test_pricing_rows_are_unique_by_rate_and_the_commit_is_a_full_sha() -> None:
    row = PricingRow("key", "eu-central-1", "on_demand", "input_tokens", 1_100)
    with pytest.raises(ValueError, match="a rate is given once"):
        PricingBasis(DIGEST, "USD", date(2026, 9, 1), (row, row))
    assert (
        PRICING.rate("eu.anthropic.claude-haiku-4-5", "eu-central-1", "on_demand", "input_tokens")
        == 1_100
    )
    assert PRICING.rate("other", "eu-central-1", "on_demand", "input_tokens") is None
    with pytest.raises(ValueError, match="a token class is a usage counter name"):
        PricingRow("key", "eu-central-1", "on_demand", "total_tokens", 1)
    with pytest.raises(ValueError, match="forty-hex git commit"):
        HarnessRevision("abc123", TreeState.CLEAN)


# --- The export -------------------------------------------------------------------------


def test_the_export_is_this_formats_self_identifying_tree() -> None:
    export = _export()
    assert (export.format_version, export.run_id, export.attempt) == (
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
    )
    with pytest.raises(ValueError, match="builds export format 1, got 2"):
        replace(export, format_version=2)
    with pytest.raises(ValueError, match="attempts are numbered from one"):
        replace(export, attempt=0)
    with pytest.raises(ValueError, match="a run id is a non-empty identifier"):
        replace(export, run_id=" ")


def test_a_recorded_failure_points_into_the_trace() -> None:
    failed = _record(
        status=TerminalStatus.FAILED,
        failure=Failure(FailureCategory.INFRASTRUCTURE, "call-9", "timeout after retries"),
    )
    with pytest.raises(ValueError, match="names 'call-9', no operation or model call of the trace"):
        _export(record=failed)
    at_call = replace(failed, failure=Failure(FailureCategory.INFRASTRUCTURE, "call-1", "timeout"))
    assert _export(record=at_call).record.failure is not None


def test_a_rules_only_export_holds_no_model_call() -> None:
    record = _record(
        system=System(SystemKind.RULES_ONLY, "frozen"),
        retrieval=Retrieval(RetrievalKind.NONE, None),
        configurations=(),
    )
    with pytest.raises(ValueError, match="a rules-only export holds no model call"):
        _export(record=record)
    assert (
        _export(record=record, trace=RunTrace((), (_operation(),), (_claim(),))).trace.model_calls
        == ()
    )
