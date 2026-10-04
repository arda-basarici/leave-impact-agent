"""JSON for the parts export format 2 adds: model calls, usage, timing, the attempt's ending.

The export's codec composes these, as it composes the entity, claim and pricing codecs:
each type has one encoding in this project and it lives beside the one byte rule. Strict
in the sealed codecs' manner, through the domain constructors: exactly the declared fields
on every object, enum members by value, every tagged union by its ``kind``, and every
invariant the types hold, so a tree that decodes is one the evaluator can read. Absent is
kept apart from empty throughout: ``null`` where an attempt had no value (no usage, no
cost, no answer, no outcome position), an empty list where it had none of a thing.

Two encodings carry something a reader can check against itself. A usage object is
written with its raw form and the counters read from it, and the decoder refuses counters
that are not the raw object's reading, so the convenient copy can never be the one that
is wrong. And the review payload, the thing an approval's digest is over, is defined here
once: the claims, the composing policy and its author, the requirements whose span did not
bind, and the statements the view left out.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import assert_never

from leaveimpact.core.claims import Claim
from leaveimpact.core.claims_json import encode_claim
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
from leaveimpact.core.model_calls import (
    Answer,
    AsOperation,
    Attribution,
    AttributionKind,
    BatchEntry,
    BrokenStream,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    Dispatch,
    Disposition,
    FactBatch,
    HandledAsBatch,
    MalformedBatch,
    ModelCall,
    NoRecordedOutcome,
    Observation,
    ParsedBatch,
    RefusedBeforeSend,
    RefusedBy,
    RequestIdentity,
    ServiceError,
    ToolCall,
    Undispatched,
    UndispatchedReason,
    Unparsed,
    UnresolvedToolCall,
)
from leaveimpact.core.run_ending import (
    Abandonment,
    Approval,
    ApprovalState,
    Approver,
    ClaimAuthor,
    ComposingPolicy,
    Composition,
    DispatchPhase,
    DispatchSite,
    FailureSite,
    HarnessSite,
    HarnessSiteName,
    KeptReason,
    OperationSite,
    RequirementPlacement,
    Reservation,
    ReservationState,
)
from leaveimpact.core.run_timing import HarnessRevision, Segment, Stamp, Timing, TreeState
from leaveimpact.core.run_trace import Cost, ModelCallId, OperationId, thawed_json
from leaveimpact.core.stated import PlacementState, RefusedInput
from leaveimpact.core.stated_json import (
    decode_admission,
    decode_emission,
    decode_excluded,
    decode_placement,
    decode_stated_fact,
    encode_admission,
    encode_emission,
    encode_excluded,
    encode_placement,
    encode_stated_fact,
)
from leaveimpact.core.timeshape import decode_instant, encode_instant
from leaveimpact.core.usage import ReportedUsage


def _optional_integer(data: Mapping[str, object], key: str) -> int | None:
    return None if field_of(data, key) is None else integer_field(data, key)


def _boolean(data: Mapping[str, object], key: str) -> bool:
    value = field_of(data, key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} is a boolean, got {value!r}")
    return value


# --- Usage and cost --------------------------------------------------------------------


def encode_usage(usage: ReportedUsage) -> JsonObject:
    """A reported usage: the raw object verbatim, and the counters read from it."""
    return {
        "raw": thawed_json(usage.raw),
        "counters": [{"name": name, "value": value} for name, value in usage.counters.counters],
    }


def decode_usage(data: Mapping[str, object]) -> ReportedUsage:
    """The usage ``data`` encodes; counters that are not the raw object's reading refuse."""
    expect_fields(data, ("raw", "counters"), "a usage")
    usage = ReportedUsage(object_field(data, "raw"))
    stated: list[tuple[str, int]] = []
    for item in array_field(data, "counters"):
        counter = as_object(item, "a usage counter")
        expect_fields(counter, ("name", "value"), "a usage counter")
        stated.append((string_field(counter, "name"), integer_field(counter, "value")))
    if tuple(stated) != usage.counters.counters:
        raise ValueError(
            "a usage's counters are the reading of its raw object: stated "
            f"{stated}, read {list(usage.counters.counters)}"
        )
    return usage


def encode_cost(cost: Cost | None) -> JsonObject | None:
    """A cost in pico-dollars with its completeness, or ``null`` for none."""
    return None if cost is None else {"pico_usd": cost.pico_usd, "complete": cost.complete}


def decode_cost(value: object) -> Cost | None:
    if value is None:
        return None
    data = as_object(value, "a cost")
    expect_fields(data, ("pico_usd", "complete"), "a cost")
    return Cost(integer_field(data, "pico_usd"), _boolean(data, "complete"))


# --- Model calls -----------------------------------------------------------------------


def encode_model_call(call: ModelCall) -> JsonObject:
    """One logical call: identity, role, dispatches in order, what its answer carried."""
    return {
        "id": call.id,
        "role": call.role,
        "dispatches": [_encode_dispatch(dispatch) for dispatch in call.dispatches],
        "answer": None if call.answer is None else _encode_answer(call.answer),
    }


def decode_model_call(item: object) -> ModelCall:
    data = as_object(item, "a model call")
    expect_fields(data, ("id", "role", "dispatches", "answer"), "a model call")
    answer = field_of(data, "answer")
    return ModelCall(
        ModelCallId(string_field(data, "id")),
        string_field(data, "role"),
        tuple(_decode_dispatch(entry) for entry in array_field(data, "dispatches")),
        None if answer is None else _decode_answer(as_object(answer, "an answer")),
    )


_DISPATCH_FIELDS = (
    "number",
    "segment",
    "intent_position",
    "outcome_position",
    "request",
    "input_reads",
    "observation",
    "attribution",
    "usage",
    "cost",
    "zero_cost_rule",
    "allocation_pico_usd",
    "allocation_tokens",
)


def _encode_dispatch(dispatch: Dispatch) -> JsonObject:
    request = dispatch.request
    return {
        "number": dispatch.number,
        "segment": dispatch.segment,
        "intent_position": dispatch.intent_position,
        "outcome_position": dispatch.outcome_position,
        "request": {
            "request_digest": request.request_digest,
            "operation": request.operation,
            "requested_profile": request.requested_profile,
            "client_region": request.client_region,
            "sent_body_digest": request.sent_body_digest,
        },
        "input_reads": list(dispatch.input_reads),
        "observation": _encode_observation(dispatch.observation),
        "attribution": {
            "kind": dispatch.attribution.kind.value,
            "rule": dispatch.attribution.rule,
        },
        "usage": None if dispatch.usage is None else encode_usage(dispatch.usage),
        "cost": encode_cost(dispatch.cost),
        "zero_cost_rule": dispatch.zero_cost_rule,
        "allocation_pico_usd": dispatch.allocation,
        "allocation_tokens": dispatch.allocation_tokens,
    }


def _decode_dispatch(item: object) -> Dispatch:
    data = as_object(item, "a dispatch")
    expect_fields(data, _DISPATCH_FIELDS, "a dispatch")
    request = object_field(data, "request")
    expect_fields(
        request,
        ("request_digest", "operation", "requested_profile", "client_region", "sent_body_digest"),
        "a request identity",
    )
    attribution = object_field(data, "attribution")
    expect_fields(attribution, ("kind", "rule"), "an attribution")
    usage = field_of(data, "usage")
    return Dispatch(
        number=integer_field(data, "number"),
        segment=integer_field(data, "segment"),
        intent_position=integer_field(data, "intent_position"),
        outcome_position=_optional_integer(data, "outcome_position"),
        request=RequestIdentity(
            string_field(request, "request_digest"),
            string_field(request, "operation"),
            string_field(request, "requested_profile"),
            string_field(request, "client_region"),
            optional_string_field(request, "sent_body_digest"),
        ),
        input_reads=tuple(
            OperationId(string_item(entry, "input_reads"))
            for entry in array_field(data, "input_reads")
        ),
        observation=_decode_observation(object_field(data, "observation")),
        attribution=Attribution(
            AttributionKind(string_field(attribution, "kind")), string_field(attribution, "rule")
        ),
        usage=None if usage is None else decode_usage(as_object(usage, "a usage")),
        cost=decode_cost(field_of(data, "cost")),
        zero_cost_rule=optional_string_field(data, "zero_cost_rule"),
        allocation=integer_field(data, "allocation_pico_usd"),
        allocation_tokens=integer_field(data, "allocation_tokens"),
    )


def _encode_observation(observation: Observation) -> JsonObject:
    match observation:
        case CompleteResponse():
            return {
                "kind": "complete_response",
                "stop_reason": observation.stop_reason,
                "provider_latency_ms": observation.provider_latency_ms,
                "sdk_retries": observation.sdk_retries,
                "provider_request_id": observation.provider_request_id,
            }
        case BrokenStream():
            return {
                "kind": "broken_stream",
                "reason": observation.reason,
                "sdk_retries": observation.sdk_retries,
                "provider_request_id": observation.provider_request_id,
            }
        case ServiceError():
            return {
                "kind": "service_error",
                "http_status": observation.http_status,
                "code": observation.code,
                "original_status": observation.original_status,
                "message_signature": observation.message_signature,
                "sdk_retries": observation.sdk_retries,
                "provider_request_id": observation.provider_request_id,
            }
        case ClientError():
            return {
                "kind": "client_error",
                "error": observation.kind.value,
                "reason": observation.reason,
            }
        case RefusedBeforeSend():
            return {"kind": "refused_before_send", "reason": observation.reason}
        case NoRecordedOutcome():
            return {"kind": "no_recorded_outcome"}
        case _:
            assert_never(observation)


def _decode_observation(data: Mapping[str, object]) -> Observation:
    kind = string_field(data, "kind")
    if kind == "complete_response":
        expect_fields(
            data,
            ("kind", "stop_reason", "provider_latency_ms", "sdk_retries", "provider_request_id"),
            "a complete response",
        )
        return CompleteResponse(
            string_field(data, "stop_reason"),
            integer_field(data, "provider_latency_ms"),
            _optional_integer(data, "sdk_retries"),
            optional_string_field(data, "provider_request_id"),
        )
    if kind == "broken_stream":
        expect_fields(
            data, ("kind", "reason", "sdk_retries", "provider_request_id"), "a broken stream"
        )
        return BrokenStream(
            string_field(data, "reason"),
            _optional_integer(data, "sdk_retries"),
            optional_string_field(data, "provider_request_id"),
        )
    if kind == "service_error":
        expect_fields(
            data,
            (
                "kind",
                "http_status",
                "code",
                "original_status",
                "message_signature",
                "sdk_retries",
                "provider_request_id",
            ),
            "a service error",
        )
        return ServiceError(
            integer_field(data, "http_status"),
            string_field(data, "code"),
            _optional_integer(data, "original_status"),
            string_field(data, "message_signature"),
            _optional_integer(data, "sdk_retries"),
            optional_string_field(data, "provider_request_id"),
        )
    if kind == "client_error":
        expect_fields(data, ("kind", "error", "reason"), "a client error")
        return ClientError(
            ClientErrorKind(string_field(data, "error")), string_field(data, "reason")
        )
    if kind == "refused_before_send":
        expect_fields(data, ("kind", "reason"), "a refusal before sending")
        return RefusedBeforeSend(string_field(data, "reason"))
    if kind == "no_recorded_outcome":
        expect_fields(data, ("kind",), "no recorded outcome")
        return NoRecordedOutcome()
    raise ValueError(
        "an observation is complete_response, broken_stream, service_error, client_error, "
        f"refused_before_send or no_recorded_outcome, got {kind!r}"
    )


def _encode_answer(answer: Answer) -> JsonObject:
    return {
        "text_present": answer.text_present,
        "tool_calls": [
            {"id": call.id, "name": call.name, "disposition": _encode_disposition(call.disposition)}
            for call in answer.tool_calls
        ],
        "fact_batches": [_encode_batch(batch) for batch in answer.fact_batches],
    }


def _decode_answer(data: Mapping[str, object]) -> Answer:
    expect_fields(data, ("text_present", "tool_calls", "fact_batches"), "an answer")
    return Answer(
        _boolean(data, "text_present"),
        tuple(_decode_tool_call(item) for item in array_field(data, "tool_calls")),
        tuple(
            _decode_batch(as_object(item, "a fact batch"))
            for item in array_field(data, "fact_batches")
        ),
    )


def _decode_tool_call(item: object) -> ToolCall:
    data = as_object(item, "a tool call")
    expect_fields(data, ("id", "name", "disposition"), "a tool call")
    return ToolCall(
        string_field(data, "id"),
        string_field(data, "name"),
        _decode_disposition(object_field(data, "disposition")),
    )


def _encode_refused_by(refused_by: RefusedBy) -> JsonObject:
    return {"parser": refused_by.parser, "schema_digest": refused_by.schema_digest}


def _decode_refused_by(data: Mapping[str, object]) -> RefusedBy:
    expect_fields(data, ("parser", "schema_digest"), "a refusing parser")
    return RefusedBy(string_field(data, "parser"), string_field(data, "schema_digest"))


def _encode_disposition(disposition: Disposition) -> JsonObject:
    match disposition:
        case AsOperation():
            return {"kind": "operation", "operation": disposition.operation}
        case HandledAsBatch():
            return {"kind": "handled", "batch": disposition.batch}
        case Unparsed():
            return {
                "kind": "unparsed",
                "raw_arguments": disposition.raw_arguments,
                "refused_by": _encode_refused_by(disposition.refused_by),
            }
        case Undispatched():
            return {"kind": "undispatched", "reason": disposition.reason.value}
        case UnresolvedToolCall():
            return {"kind": "unresolved"}
        case _:
            assert_never(disposition)


def _decode_disposition(data: Mapping[str, object]) -> Disposition:
    kind = string_field(data, "kind")
    if kind == "operation":
        expect_fields(data, ("kind", "operation"), "an operation disposition")
        return AsOperation(OperationId(string_field(data, "operation")))
    if kind == "handled":
        expect_fields(data, ("kind", "batch"), "a handled disposition")
        return HandledAsBatch(integer_field(data, "batch"))
    if kind == "unparsed":
        expect_fields(data, ("kind", "raw_arguments", "refused_by"), "an unparsed disposition")
        return Unparsed(
            string_field(data, "raw_arguments"),
            _decode_refused_by(object_field(data, "refused_by")),
        )
    if kind == "undispatched":
        expect_fields(data, ("kind", "reason"), "an undispatched disposition")
        return Undispatched(UndispatchedReason(string_field(data, "reason")))
    if kind == "unresolved":
        expect_fields(data, ("kind",), "an unresolved disposition")
        return UnresolvedToolCall()
    raise ValueError(
        f"a disposition is operation, handled, unparsed, undispatched or unresolved, got {kind!r}"
    )


def _encode_batch(batch: FactBatch) -> JsonObject:
    match batch:
        case ParsedBatch():
            return {"kind": "parsed", "entries": [_encode_entry(entry) for entry in batch.entries]}
        case MalformedBatch():
            return {
                "kind": "malformed",
                "raw": batch.raw,
                "refused_by": _encode_refused_by(batch.refused_by),
            }
        case _:
            assert_never(batch)


def _decode_batch(data: Mapping[str, object]) -> FactBatch:
    kind = string_field(data, "kind")
    if kind == "parsed":
        expect_fields(data, ("kind", "entries"), "a parsed batch")
        return ParsedBatch(
            tuple(
                _decode_entry(as_object(item, "a batch entry"))
                for item in array_field(data, "entries")
            )
        )
    if kind == "malformed":
        expect_fields(data, ("kind", "raw", "refused_by"), "a malformed batch")
        return MalformedBatch(
            string_field(data, "raw"), _decode_refused_by(object_field(data, "refused_by"))
        )
    raise ValueError(f"a fact batch is parsed or malformed, got {kind!r}")


def _encode_entry(entry: BatchEntry) -> JsonObject:
    # A refused input is the emission codec's and an admission the admission codec's, each
    # under its own tag, so an entry is told apart by which tag it carries.
    if isinstance(entry, RefusedInput):
        return encode_emission(entry)
    return encode_admission(entry)


def _decode_entry(data: Mapping[str, object]) -> BatchEntry:
    if "admission" in data:
        return decode_admission(data)
    emission = decode_emission(data)
    if not isinstance(emission, RefusedInput):
        raise ValueError(
            "a batch entry is a refused input or an admission; a stated fact is held "
            "inside its admission"
        )
    return emission


# --- Timing ----------------------------------------------------------------------------


def encode_timing(timing: Timing) -> JsonObject:
    """The timing's inputs: segments, the two instants, the approval's two stamps."""
    return {
        "segments": [
            {
                "number": segment.number,
                "harness": {"commit": segment.harness.commit, "tree": segment.harness.tree.value},
                "last_offset_ms": segment.last_offset_ms,
                "end_recorded": segment.end_recorded,
            }
            for segment in timing.segments
        ],
        "admitted_at": encode_instant(timing.admitted_at),
        "terminal_at": encode_instant(timing.terminal_at),
        "approval_requested": _encode_stamp(timing.approval_requested),
        "approval_resumed": _encode_stamp(timing.approval_resumed),
    }


def decode_timing(data: Mapping[str, object]) -> Timing:
    expect_fields(
        data,
        ("segments", "admitted_at", "terminal_at", "approval_requested", "approval_resumed"),
        "the timing",
    )
    return Timing(
        tuple(_decode_segment(item) for item in array_field(data, "segments")),
        decode_instant(field_of(data, "admitted_at"), "admitted_at"),
        decode_instant(field_of(data, "terminal_at"), "terminal_at"),
        _decode_stamp(field_of(data, "approval_requested")),
        _decode_stamp(field_of(data, "approval_resumed")),
    )


def _decode_segment(item: object) -> Segment:
    data = as_object(item, "a segment")
    expect_fields(data, ("number", "harness", "last_offset_ms", "end_recorded"), "a segment")
    harness = object_field(data, "harness")
    expect_fields(harness, ("commit", "tree"), "the harness")
    return Segment(
        integer_field(data, "number"),
        HarnessRevision(string_field(harness, "commit"), TreeState(string_field(harness, "tree"))),
        integer_field(data, "last_offset_ms"),
        _boolean(data, "end_recorded"),
    )


def _encode_stamp(stamp: Stamp | None) -> JsonObject | None:
    if stamp is None:
        return None
    return {"segment": stamp.segment, "offset_ms": stamp.offset_ms, "position": stamp.position}


def _decode_stamp(value: object) -> Stamp | None:
    if value is None:
        return None
    data = as_object(value, "a stamp")
    expect_fields(data, ("segment", "offset_ms", "position"), "a stamp")
    return Stamp(
        integer_field(data, "segment"),
        integer_field(data, "offset_ms"),
        integer_field(data, "position"),
    )


# --- The attempt's ending --------------------------------------------------------------


def encode_failure_site(site: FailureSite) -> JsonObject:
    """Where a failure was found: an operation, a model dispatch, or a harness site."""
    match site:
        case OperationSite():
            return {"kind": "operation", "operation": site.operation}
        case DispatchSite():
            return {
                "kind": "dispatch",
                "model_call": site.model_call,
                "dispatch": site.dispatch,
                "phase": site.phase.value,
            }
        case HarnessSite():
            return {"kind": "harness", "site": site.site.value}
        case _:
            assert_never(site)


def decode_failure_site(data: Mapping[str, object]) -> FailureSite:
    kind = string_field(data, "kind")
    if kind == "operation":
        expect_fields(data, ("kind", "operation"), "an operation site")
        return OperationSite(OperationId(string_field(data, "operation")))
    if kind == "dispatch":
        expect_fields(data, ("kind", "model_call", "dispatch", "phase"), "a dispatch site")
        return DispatchSite(
            ModelCallId(string_field(data, "model_call")),
            integer_field(data, "dispatch"),
            DispatchPhase(string_field(data, "phase")),
        )
    if kind == "harness":
        expect_fields(data, ("kind", "site"), "a harness site")
        return HarnessSite(HarnessSiteName(string_field(data, "site")))
    raise ValueError(f"a failure site is operation, dispatch or harness, got {kind!r}")


def encode_abandonment(abandonment: Abandonment | None) -> JsonObject | None:
    if abandonment is None:
        return None
    return {
        "authority": abandonment.authority,
        "ownership_generation": abandonment.ownership_generation,
    }


def decode_abandonment(value: object) -> Abandonment | None:
    if value is None:
        return None
    data = as_object(value, "an abandonment")
    expect_fields(data, ("authority", "ownership_generation"), "an abandonment")
    return Abandonment(string_field(data, "authority"), integer_field(data, "ownership_generation"))


def encode_reservation(reservation: Reservation | None) -> JsonObject | None:
    if reservation is None:
        return None
    return {
        "pico_usd": reservation.pico_usd,
        "state": reservation.state.value,
        "kept_reason": None if reservation.kept_reason is None else reservation.kept_reason.value,
        "ledger_revision": reservation.ledger_revision,
    }


def decode_reservation(value: object) -> Reservation | None:
    if value is None:
        return None
    data = as_object(value, "a reservation")
    expect_fields(data, ("pico_usd", "state", "kept_reason", "ledger_revision"), "a reservation")
    reason = optional_string_field(data, "kept_reason")
    return Reservation(
        integer_field(data, "pico_usd"),
        ReservationState(string_field(data, "state")),
        None if reason is None else KeptReason(reason),
        integer_field(data, "ledger_revision"),
    )


def encode_approval(approval: Approval) -> JsonObject:
    return {
        "state": approval.state.value,
        "approver": None if approval.approver is None else approval.approver.value,
        "payload_digest": approval.payload_digest,
    }


def decode_approval(data: Mapping[str, object]) -> Approval:
    expect_fields(data, ("state", "approver", "payload_digest"), "an approval")
    approver = optional_string_field(data, "approver")
    return Approval(
        ApprovalState(string_field(data, "state")),
        None if approver is None else Approver(approver),
        optional_string_field(data, "payload_digest"),
    )


def encode_composition(composition: Composition) -> JsonObject:
    """Who composed the claims, under which policy, with the placements and the exclusions."""
    return {
        "author": composition.author.value,
        "policy": {
            "identifier": composition.policy.identifier,
            "digest": composition.policy.digest,
        },
        "placements": [_encode_requirement(entry) for entry in composition.placements],
        "exclusions": [encode_excluded(excluded) for excluded in composition.exclusions],
    }


def decode_composition(data: Mapping[str, object]) -> Composition:
    expect_fields(data, ("author", "policy", "placements", "exclusions"), "the composition")
    policy = object_field(data, "policy")
    expect_fields(policy, ("identifier", "digest"), "a composing policy")
    return Composition(
        ClaimAuthor(string_field(data, "author")),
        ComposingPolicy(string_field(policy, "identifier"), string_field(policy, "digest")),
        tuple(
            _decode_requirement(as_object(item, "a placement"))
            for item in array_field(data, "placements")
        ),
        tuple(
            decode_excluded(as_object(item, "an exclusion"))
            for item in array_field(data, "exclusions")
        ),
    )


def _encode_requirement(entry: RequirementPlacement) -> JsonObject:
    return {
        "fact": encode_stated_fact(entry.fact),
        "placement": encode_placement(entry.placement),
    }


def _decode_requirement(data: Mapping[str, object]) -> RequirementPlacement:
    expect_fields(data, ("fact", "placement"), "a placement")
    return RequirementPlacement(
        decode_stated_fact(object_field(data, "fact")),
        decode_placement(object_field(data, "placement")),
    )


# --- The review payload ----------------------------------------------------------------


def review_payload(claims: Sequence[Claim], composition: Composition) -> JsonObject:
    """What an approval is asked over, frozen: the claims in claim-id order, who composed
    them under which policy, the requirements whose span did not bind, and the statements
    the view left out, a requirement withheld for its scope among them. A placed
    requirement is not repeated: it is in the constraint claim it composed, or it was
    bound to something the leave does not touch and composed none, which is no diagnostic.
    An abstention's payload holds no claim and is a payload all the same."""
    return {
        "claims": [
            encode_claim(claim) for claim in sorted(claims, key=lambda claim: claim.claim_id)
        ],
        "author": composition.author.value,
        "policy": {
            "identifier": composition.policy.identifier,
            "digest": composition.policy.digest,
        },
        "unbound": [
            _encode_requirement(entry)
            for entry in composition.placements
            if entry.placement.state is not PlacementState.PLACED
        ],
        "exclusions": [encode_excluded(excluded) for excluded in composition.exclusions],
    }


def review_payload_digest(claims: Sequence[Claim], composition: Composition) -> str:
    """SHA-256 of the review payload's canonical bytes: what an approval's digest holds."""
    return hashlib.sha256(canonical_bytes(review_payload(claims, composition))).hexdigest()


__all__ = [
    "decode_abandonment",
    "decode_approval",
    "decode_composition",
    "decode_cost",
    "decode_failure_site",
    "decode_model_call",
    "decode_reservation",
    "decode_timing",
    "decode_usage",
    "encode_abandonment",
    "encode_approval",
    "encode_composition",
    "encode_cost",
    "encode_failure_site",
    "encode_model_call",
    "encode_reservation",
    "encode_timing",
    "encode_usage",
    "review_payload",
    "review_payload_digest",
]
