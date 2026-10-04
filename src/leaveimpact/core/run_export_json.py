"""JSON for the run export: one canonical tree under the one byte rule, format version 2.

The export is written once by the agent and read by the evaluator, so its codec sits
here with the types, the only package both reach (the investigator milestone's second
build step, ruling 1). The bytes are canonical JSON in ``core``'s one sense, so the
digest the evaluation artifact cites is a property of the run and not of a serializer;
the format version is the first field, and a decoder refuses any version but its own,
since a reader that guessed at an older shape would be the compatibility branch the
design rules out. Within the version, the structural fields a replay cannot do without
are exactly the declared ones, and the extensible blocks (the usage counters, the
provenance names) are lists whose entries are the ones the run had, so an entry
appended later reads as absent from an older export and the codec learns nothing.

Strict in the sealed codecs' manner, through the domain constructors: exactly the
declared fields on every object, each of its declared shape, enum members by value,
dates and instants in the one canonical spelling, every tagged union by its ``kind``,
and every invariant the types enforce, so a tree that decodes is one the evaluator can
grade and anything else refuses naming the field. Absent is a different statement from
empty throughout: ``null`` where a run had no value (no usage reported, no cost, no
failure, no answer), an empty list where it had none of a thing.

Observed records travel through the entity codec, claims through the claim codec,
call configurations through their own codec, rates through the pricing codec, and the
parts format 2 added (model calls, usage, timing, the attempt's ending) through
``run_parts_json``, each the one encoding its type has in this project.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import assert_never, cast

from leaveimpact.core.call_settings import (
    CallConfiguration,
    decode_call_configuration,
    encode_call_configuration,
)
from leaveimpact.core.claims_json import decode_claim, encode_claim
from leaveimpact.core.entities_json import decode_observed, encode_observed
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, is_numbered_id
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.pricing import decode_rate, encode_rate
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport, RunTrace
from leaveimpact.core.run_parts_json import (
    decode_abandonment,
    decode_approval,
    decode_composition,
    decode_cost,
    decode_failure_site,
    decode_model_call,
    decode_reservation,
    decode_timing,
    encode_abandonment,
    encode_approval,
    encode_composition,
    encode_cost,
    encode_failure_site,
    encode_model_call,
    encode_reservation,
    encode_timing,
)
from leaveimpact.core.run_record import (
    Caps,
    Failure,
    FailureCategory,
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    PricingSelection,
    Retrieval,
    RetrievalKind,
    RunRecord,
    System,
    SystemKind,
    TerminalStatus,
    UsageAggregate,
)
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
    HarnessOrigin,
    ModelCallId,
    ModelOrigin,
    Operation,
    OperationId,
    Origin,
    Outcome,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    UnreachableOutcome,
    frozen_json,
    require_integer,
    thawed_json,
)
from leaveimpact.core.timeshape import decode_date, decode_instant, encode_date, encode_instant
from leaveimpact.core.worldtime import RunContext

# --- Encoding ---------------------------------------------------------------------------


def export_bytes(export: RunExport) -> bytes:
    """The canonical bytes of ``export``: what is written, hashed and cited."""
    return canonical_bytes(encode_run_export(export))


def encode_run_export(export: RunExport) -> JsonObject:
    """The JSON object of an export: version and identity first, then context, record, trace."""
    return {
        "format_version": export.format_version,
        "run_id": export.run_id,
        "attempt": export.attempt,
        "context": _encode_context(export.context),
        "record": encode_run_record(export.record),
        "trace": encode_run_trace(export.trace),
    }


def _encode_context(context: RunContext) -> JsonObject:
    return {
        "scenario_id": context.scenario_id,
        "world_version": context.world_version,
        "leave_id": context.leave_id,
        "now": encode_instant(context.now),
        "reference_timezone": context.reference_timezone,
    }


def encode_run_record(record: RunRecord) -> JsonObject:
    """The JSON object of the provenance block, every role-indexed collection in role order."""
    return {
        "observed_condition": {
            "reachable": sorted(source.value for source in record.observed_condition.reachable)
        },
        "outage": {
            "scheduled_unreachable": sorted(
                source.value for source in record.outage.scheduled_unreachable
            ),
            "schedule_digest": record.outage.schedule_digest,
        },
        "corpus_level": record.corpus_level,
        "preregistration_commit": record.preregistration_commit,
        "attribution_table": record.attribution_table,
        "model_configurations": [
            {"role": role, "configuration": encode_call_configuration(configured)}
            for role, configured in record.model_configurations
        ],
        "pricing_selections": [
            {
                "role": role,
                "pricing_key": selection.pricing_key,
                "region": selection.region,
                "billing_mode": selection.billing_mode,
            }
            for role, selection in record.pricing_selections
        ],
        "prompt_digests": [
            {"role": role, "name": name, "digest": digest}
            for role, name, digest in record.prompt_digests
        ],
        "tool_surface_digests": [
            {"role": role, "digest": digest} for role, digest in record.tool_surface_digests
        ],
        "system": {"kind": record.system.kind.value, "variant": record.system.variant},
        "retrieval": {
            "kind": record.retrieval.kind.value,
            "embedding_model": record.retrieval.embedding_model,
        },
        "prefetch_rule": {
            "identifier": record.prefetch_rule.identifier,
            "digest": record.prefetch_rule.digest,
        },
        "caps": {
            "call_cap": record.caps.call_cap,
            "token_cap": record.caps.token_cap,
            "finalization_call_reserve": record.caps.finalization_call_reserve,
            "finalization_token_reserve": record.caps.finalization_token_reserve,
            "counting_rule": record.caps.counting_rule,
        },
        "status": record.status.value,
        "failure": None if record.failure is None else _encode_failure(record.failure),
        "abandonment": encode_abandonment(record.abandonment),
        "timing": encode_timing(record.timing),
        "usage": {
            "counters": [
                {"name": name, "value": value, "reported": reported}
                for name, value, reported in record.usage.counters
            ],
            "model_calls": record.usage.model_calls,
            "dispatches": record.usage.dispatches,
        },
        "cost": encode_cost(record.cost),
        "reservation": encode_reservation(record.reservation),
        "approval": encode_approval(record.approval),
        "pricing": {
            "table_digest": record.pricing.table_digest,
            "currency": record.pricing.currency,
            "effective_from": encode_date(record.pricing.effective_from),
            "rows": [encode_rate(row) for row in record.pricing.rows],
        },
    }


def _encode_failure(failure: Failure) -> JsonObject:
    return {
        "category": failure.category.value,
        "site": encode_failure_site(failure.site),
        "reason": failure.reason,
    }


def encode_run_trace(trace: RunTrace) -> JsonObject:
    """The JSON object of the trace: model calls, operations and claims in the trace's order,
    then how the claims were composed."""
    return {
        "model_calls": [encode_model_call(call) for call in trace.model_calls],
        "operations": [_encode_operation(operation) for operation in trace.operations],
        "claims": [encode_claim(claim) for claim in trace.claims],
        "composition": encode_composition(trace.composition),
    }


def _encode_operation(operation: Operation) -> JsonObject:
    return {
        "id": operation.id,
        "origin": _encode_origin(operation.origin),
        "tool": operation.tool,
        "source": None if operation.source is None else operation.source.value,
        "arguments": thawed_json(operation.arguments),
        "outcome": _encode_outcome(operation.outcome),
        "position": operation.position,
    }


def _encode_origin(origin: Origin) -> JsonObject:
    match origin:
        case PrefetchOrigin():
            return {"kind": "prefetch"}
        case HarnessOrigin():
            return {"kind": "harness", "policy": origin.policy}
        case ModelOrigin():
            return {"kind": "model", "model_call": origin.model_call}
        case _:
            assert_never(origin)


def _encode_outcome(outcome: Outcome) -> JsonObject:
    match outcome:
        case RecordOutcome():
            return {"kind": "record", "record": encode_observed(outcome.record)}
        case AbsentOutcome():
            return {"kind": "absent"}
        case RecordsOutcome():
            return {"kind": "records", "records": [encode_observed(r) for r in outcome.records]}
        case UnreachableOutcome():
            return {"kind": "unreachable", "source": outcome.source.value, "reason": outcome.reason}
        case DefectOutcome():
            return {
                "kind": "defect",
                "source": outcome.source.value,
                "locator": outcome.locator,
                "reason": outcome.reason,
            }
        case RefusedCallOutcome():
            return {"kind": "refused_call", "reason": outcome.reason}
        case _:
            assert_never(outcome)


# --- Decoding ---------------------------------------------------------------------------


def decode_export_bytes(content: bytes | str) -> RunExport:
    """The export ``content`` holds, accepted only if its re-encoding is ``content`` byte for byte.

    The boundary a reader actually meets is bytes, and the digest it cites is of those
    bytes, so the decoder checks what the one byte rule promises: that the bytes are the
    canonical encoding of the tree they decode to. Input that decodes to a tree and then
    re-encodes differently (a pretty-printed spelling, a duplicate in a set-valued list,
    a role-indexed entry out of order) is refused as not canonical, since accepting it
    would let two byte sequences stand for one export and the cited digest name neither.

    >>> decode_export_bytes(b'{"format_version": 1}')
    Traceback (most recent call last):
    ...
    ValueError: this code reads export format 2, got 1
    """
    raw = content.encode("utf-8") if isinstance(content, str) else content
    export = decode_run_export(json.loads(raw))
    if export_bytes(export) != raw:
        raise ValueError(
            "the export's bytes are not its canonical encoding; a re-encoding of what they "
            "decode to differs, so they are not what the one byte rule writes"
        )
    return export


def decode_run_export(value: object) -> RunExport:
    """The export ``value`` encodes; a format other than this code's refuses before anything."""
    data = as_object(value, "a run export")
    version = require_integer(field_of(data, "format_version"), "format_version")
    if version != EXPORT_FORMAT_VERSION:
        raise ValueError(f"this code reads export format {EXPORT_FORMAT_VERSION}, got {version}")
    expect_fields(
        data, ("format_version", "run_id", "attempt", "context", "record", "trace"), "a run export"
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        string_field(data, "run_id"),
        integer_field(data, "attempt"),
        _decode_context(object_field(data, "context")),
        decode_run_record(object_field(data, "record")),
        decode_run_trace(object_field(data, "trace")),
    )


def _decode_context(data: Mapping[str, object]) -> RunContext:
    expect_fields(
        data,
        ("scenario_id", "world_version", "leave_id", "now", "reference_timezone"),
        "the context",
    )
    scenario = string_field(data, "scenario_id")
    if not is_numbered_id(scenario) or not scenario.startswith("scenario_"):
        raise ValueError(f"scenario_id has the form scenario_NNN, got {scenario!r}")
    return RunContext(
        ScenarioId(scenario),
        WorldVersion(string_field(data, "world_version")),
        LeaveId(string_field(data, "leave_id")),
        decode_instant(field_of(data, "now"), "now"),
        string_field(data, "reference_timezone"),
    )


def decode_run_record(data: Mapping[str, object]) -> RunRecord:
    """The provenance block ``data`` encodes, through every constructor invariant."""
    expect_fields(
        data,
        (
            "observed_condition",
            "outage",
            "corpus_level",
            "preregistration_commit",
            "attribution_table",
            "model_configurations",
            "pricing_selections",
            "prompt_digests",
            "tool_surface_digests",
            "system",
            "retrieval",
            "prefetch_rule",
            "caps",
            "status",
            "failure",
            "abandonment",
            "timing",
            "usage",
            "cost",
            "reservation",
            "approval",
            "pricing",
        ),
        "the record",
    )
    condition = object_field(data, "observed_condition")
    expect_fields(condition, ("reachable",), "the observed condition")
    outage = object_field(data, "outage")
    expect_fields(outage, ("scheduled_unreachable", "schedule_digest"), "the outage")
    system = object_field(data, "system")
    expect_fields(system, ("kind", "variant"), "the system")
    retrieval = object_field(data, "retrieval")
    expect_fields(retrieval, ("kind", "embedding_model"), "the retrieval")
    prefetch = object_field(data, "prefetch_rule")
    expect_fields(prefetch, ("identifier", "digest"), "the prefetch rule")
    caps = object_field(data, "caps")
    expect_fields(
        caps,
        (
            "call_cap",
            "token_cap",
            "finalization_call_reserve",
            "finalization_token_reserve",
            "counting_rule",
        ),
        "the caps",
    )
    usage = object_field(data, "usage")
    expect_fields(usage, ("counters", "model_calls", "dispatches"), "the usage")
    pricing = object_field(data, "pricing")
    expect_fields(pricing, ("table_digest", "currency", "effective_from", "rows"), "the pricing")
    failure = field_of(data, "failure")
    return RunRecord(
        observed_condition=RunCondition(_sources(condition, "reachable")),
        outage=OutageAssignment(
            _sources(outage, "scheduled_unreachable"), string_field(outage, "schedule_digest")
        ),
        corpus_level=string_field(data, "corpus_level"),
        preregistration_commit=string_field(data, "preregistration_commit"),
        attribution_table=optional_string_field(data, "attribution_table"),
        model_configurations=tuple(
            _decode_configured(item) for item in array_field(data, "model_configurations")
        ),
        pricing_selections=tuple(
            _decode_selection(item) for item in array_field(data, "pricing_selections")
        ),
        prompt_digests=tuple(_decode_prompt(item) for item in array_field(data, "prompt_digests")),
        tool_surface_digests=tuple(
            _decode_surface(item) for item in array_field(data, "tool_surface_digests")
        ),
        system=System(SystemKind(string_field(system, "kind")), string_field(system, "variant")),
        retrieval=Retrieval(
            RetrievalKind(string_field(retrieval, "kind")),
            optional_string_field(retrieval, "embedding_model"),
        ),
        prefetch_rule=PrefetchRule(
            string_field(prefetch, "identifier"), string_field(prefetch, "digest")
        ),
        caps=Caps(
            integer_field(caps, "call_cap"),
            integer_field(caps, "token_cap"),
            integer_field(caps, "finalization_call_reserve"),
            integer_field(caps, "finalization_token_reserve"),
            string_field(caps, "counting_rule"),
        ),
        status=TerminalStatus(string_field(data, "status")),
        failure=None if failure is None else _decode_failure(as_object(failure, "the failure")),
        abandonment=decode_abandonment(field_of(data, "abandonment")),
        timing=decode_timing(object_field(data, "timing")),
        usage=UsageAggregate(
            tuple(_decode_aggregate_counter(item) for item in array_field(usage, "counters")),
            integer_field(usage, "model_calls"),
            integer_field(usage, "dispatches"),
        ),
        cost=decode_cost(field_of(data, "cost")),
        reservation=decode_reservation(field_of(data, "reservation")),
        approval=decode_approval(object_field(data, "approval")),
        pricing=PricingBasis(
            string_field(pricing, "table_digest"),
            string_field(pricing, "currency"),
            decode_date(string_field(pricing, "effective_from"), "effective_from"),
            tuple(decode_rate(item) for item in array_field(pricing, "rows")),
        ),
    )


def _sources(data: Mapping[str, object], key: str) -> frozenset[Source]:
    return frozenset(Source(string_item(item, key)) for item in array_field(data, key))


def _decode_configured(item: object) -> tuple[str, CallConfiguration]:
    data = as_object(item, "a model configuration entry")
    expect_fields(data, ("role", "configuration"), "a model configuration entry")
    return string_field(data, "role"), decode_call_configuration(field_of(data, "configuration"))


def _decode_selection(item: object) -> tuple[str, PricingSelection]:
    data = as_object(item, "a pricing selection")
    expect_fields(data, ("role", "pricing_key", "region", "billing_mode"), "a pricing selection")
    return string_field(data, "role"), PricingSelection(
        string_field(data, "pricing_key"),
        string_field(data, "region"),
        string_field(data, "billing_mode"),
    )


def _decode_prompt(item: object) -> tuple[str, str, str]:
    data = as_object(item, "a prompt digest")
    expect_fields(data, ("role", "name", "digest"), "a prompt digest")
    return string_field(data, "role"), string_field(data, "name"), string_field(data, "digest")


def _decode_surface(item: object) -> tuple[str, str]:
    data = as_object(item, "a tool surface digest")
    expect_fields(data, ("role", "digest"), "a tool surface digest")
    return string_field(data, "role"), string_field(data, "digest")


def _decode_failure(data: Mapping[str, object]) -> Failure:
    expect_fields(data, ("category", "site", "reason"), "the failure")
    return Failure(
        FailureCategory(string_field(data, "category")),
        decode_failure_site(object_field(data, "site")),
        string_field(data, "reason"),
    )


def _decode_aggregate_counter(item: object) -> tuple[str, int, int]:
    data = as_object(item, "an aggregate counter")
    expect_fields(data, ("name", "value", "reported"), "an aggregate counter")
    return (
        string_field(data, "name"),
        integer_field(data, "value"),
        integer_field(data, "reported"),
    )


def decode_run_trace(data: Mapping[str, object]) -> RunTrace:
    """The trace ``data`` encodes, through every constructor invariant."""
    expect_fields(data, ("model_calls", "operations", "claims", "composition"), "the trace")
    return RunTrace(
        tuple(decode_model_call(item) for item in array_field(data, "model_calls")),
        tuple(_decode_operation(item) for item in array_field(data, "operations")),
        tuple(decode_claim(as_object(item, "a claim")) for item in array_field(data, "claims")),
        decode_composition(object_field(data, "composition")),
    )


def _decode_operation(item: object) -> Operation:
    data = as_object(item, "an operation")
    expect_fields(
        data,
        ("id", "origin", "tool", "source", "arguments", "outcome", "position"),
        "an operation",
    )
    position = field_of(data, "position")
    source = optional_string_field(data, "source")
    arguments = cast(
        "Mapping[str, object]", frozen_json(object_field(data, "arguments"), "arguments")
    )
    return Operation(
        OperationId(string_field(data, "id")),
        _decode_origin(object_field(data, "origin")),
        string_field(data, "tool"),
        None if source is None else Source(source),
        arguments,
        _decode_outcome(object_field(data, "outcome")),
        None if position is None else require_integer(position, "position"),
    )


def _decode_origin(data: Mapping[str, object]) -> Origin:
    kind = string_field(data, "kind")
    if kind == "prefetch":
        expect_fields(data, ("kind",), "a prefetch origin")
        return PrefetchOrigin()
    if kind == "harness":
        expect_fields(data, ("kind", "policy"), "a harness origin")
        return HarnessOrigin(string_field(data, "policy"))
    if kind == "model":
        expect_fields(data, ("kind", "model_call"), "a model origin")
        return ModelOrigin(ModelCallId(string_field(data, "model_call")))
    raise ValueError(f"an origin is prefetch, harness or model, got {kind!r}")


def _decode_outcome(data: Mapping[str, object]) -> Outcome:
    kind = string_field(data, "kind")
    if kind == "record":
        expect_fields(data, ("kind", "record"), "a record outcome")
        return RecordOutcome(decode_observed(field_of(data, "record")))
    if kind == "absent":
        expect_fields(data, ("kind",), "an absent outcome")
        return AbsentOutcome()
    if kind == "records":
        expect_fields(data, ("kind", "records"), "a records outcome")
        return RecordsOutcome(tuple(decode_observed(item) for item in array_field(data, "records")))
    if kind == "unreachable":
        expect_fields(data, ("kind", "source", "reason"), "an unreachable outcome")
        return UnreachableOutcome(
            Source(string_field(data, "source")), string_field(data, "reason")
        )
    if kind == "defect":
        expect_fields(data, ("kind", "source", "locator", "reason"), "a defect outcome")
        return DefectOutcome(
            Source(string_field(data, "source")),
            string_field(data, "locator"),
            string_field(data, "reason"),
        )
    if kind == "refused_call":
        expect_fields(data, ("kind", "reason"), "a refused call outcome")
        return RefusedCallOutcome(string_field(data, "reason"))
    raise ValueError(
        f"an outcome is record, absent, records, unreachable, defect or refused_call, got {kind!r}"
    )
