"""The attribution table: the first row in order decides and the order is in the digest; a
kind of observation always ends in a row that takes all of it; a defect is read only with a
cause the harness supplied; only an infrastructure reading may be followed by another
dispatch or a new attempt; no recorded outcome is unresolved and no row's; and the codec
returns the bytes it was given only when they were canonical."""

import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from leaveimpact.core.attribution import (
    UNRESOLVED_RULE,
    AttributionRow,
    AttributionTable,
    Cause,
    Match,
    ObservationKind,
    RedispatchPolicy,
    attribute,
    attribution_table_digest,
    decode_attribution_table,
    decode_redispatch_policy,
    encode_attribution_table,
    encode_redispatch_policy,
    kind_of,
)
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.model_calls import (
    AttributionKind,
    BrokenStream,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    NoRecordedOutcome,
    Observation,
    RefusedBeforeSend,
    ServiceError,
)

BEHAVIOUR = AttributionKind.BEHAVIOUR
INFRASTRUCTURE = AttributionKind.INFRASTRUCTURE
DEFECT = AttributionKind.DEFECT
CUT_TOOL_CALL = "invalid-tool-use-sequence-at-output-limit"


def ruled_classes() -> AttributionTable:
    """A table holding the classes the ruling on dispatches names, with stand-in values: a
    registered stop reason is behaviour; a request the harness built against its own
    contract is a defect; a throttle, a denial, a server error and a timeout are
    infrastructure; the model error with the evidenced signature is behaviour and every
    other error is infrastructure, flagged unmatched."""
    service = ObservationKind.SERVICE_ERROR
    return AttributionTable(
        (
            AttributionRow(
                "registered_stop_reason",
                Match(
                    ObservationKind.COMPLETE_RESPONSE,
                    stop_reasons=frozenset({"end_turn", "tool_use", "max_tokens"}),
                ),
                BEHAVIOUR,
            ),
            AttributionRow(
                "unregistered_stop_reason",
                Match(ObservationKind.COMPLETE_RESPONSE),
                INFRASTRUCTURE,
                new_attempt=True,
                unmatched=True,
            ),
            AttributionRow(
                "broken_stream",
                Match(ObservationKind.BROKEN_STREAM),
                INFRASTRUCTURE,
                redispatch=True,
                new_attempt=True,
            ),
            AttributionRow(
                "request_contract_rejected",
                Match(service, cause=Cause.HARNESS_REQUEST_CONTRACT),
                DEFECT,
            ),
            AttributionRow(
                "cut_tool_call",
                Match(
                    service,
                    http_statuses=frozenset({424}),
                    codes=frozenset({"ModelErrorException"}),
                    message_signatures=frozenset({CUT_TOOL_CALL}),
                ),
                BEHAVIOUR,
            ),
            AttributionRow(
                "throttled",
                Match(service, codes=frozenset({"ThrottlingException"})),
                INFRASTRUCTURE,
                redispatch=True,
                new_attempt=True,
            ),
            AttributionRow(
                "denied",
                Match(service, codes=frozenset({"AccessDeniedException"})),
                INFRASTRUCTURE,
            ),
            AttributionRow(
                "server_error",
                Match(service, http_statuses=frozenset({500, 503})),
                INFRASTRUCTURE,
                redispatch=True,
                new_attempt=True,
            ),
            AttributionRow(
                "unmatched_service_error",
                Match(service),
                INFRASTRUCTURE,
                new_attempt=True,
                unmatched=True,
            ),
            AttributionRow(
                "timeout",
                Match(
                    ObservationKind.CLIENT_ERROR,
                    client_errors=frozenset({ClientErrorKind.TIMEOUT}),
                ),
                INFRASTRUCTURE,
                redispatch=True,
                new_attempt=True,
            ),
            AttributionRow(
                "client_error",
                Match(ObservationKind.CLIENT_ERROR),
                INFRASTRUCTURE,
                new_attempt=True,
            ),
            AttributionRow(
                "request_contract_refused",
                Match(ObservationKind.REFUSED_BEFORE_SEND, cause=Cause.HARNESS_REQUEST_CONTRACT),
                DEFECT,
            ),
            AttributionRow(
                "refused_before_send",
                Match(ObservationKind.REFUSED_BEFORE_SEND),
                INFRASTRUCTURE,
                unmatched=True,
            ),
        )
    )


def _service(status: int, code: str, signature: str = "other") -> ServiceError:
    return ServiceError(status, code, None, signature)


@pytest.mark.parametrize(
    ("observation", "cause", "rule", "reading"),
    [
        (CompleteResponse("tool_use", 900, 0), None, "registered_stop_reason", BEHAVIOUR),
        (
            CompleteResponse("content_filtered", 900, 0),
            None,
            "unregistered_stop_reason",
            INFRASTRUCTURE,
        ),
        (BrokenStream("connection reset"), None, "broken_stream", INFRASTRUCTURE),
        (
            _service(424, "ModelErrorException", CUT_TOOL_CALL),
            None,
            "cut_tool_call",
            BEHAVIOUR,
        ),
        (
            _service(424, "ModelErrorException"),
            None,
            "unmatched_service_error",
            INFRASTRUCTURE,
        ),
        (_service(429, "ThrottlingException"), None, "throttled", INFRASTRUCTURE),
        (_service(403, "AccessDeniedException"), None, "denied", INFRASTRUCTURE),
        (_service(503, "ServiceUnavailableException"), None, "server_error", INFRASTRUCTURE),
        (
            _service(400, "ValidationException"),
            Cause.HARNESS_REQUEST_CONTRACT,
            "request_contract_rejected",
            DEFECT,
        ),
        (_service(400, "ValidationException"), None, "unmatched_service_error", INFRASTRUCTURE),
        (ClientError(ClientErrorKind.TIMEOUT, "read timed out"), None, "timeout", INFRASTRUCTURE),
        (
            ClientError(ClientErrorKind.CONNECTION, "refused"),
            None,
            "client_error",
            INFRASTRUCTURE,
        ),
        (
            RefusedBeforeSend("a tool result with no tool use"),
            Cause.HARNESS_REQUEST_CONTRACT,
            "request_contract_refused",
            DEFECT,
        ),
        (RefusedBeforeSend("unknown parameter"), None, "refused_before_send", INFRASTRUCTURE),
    ],
)
def test_each_ruled_class_is_read_by_its_row(
    observation: Observation, cause: Cause | None, rule: str, reading: AttributionKind
) -> None:
    attribution, row = attribute(ruled_classes(), observation, cause)
    assert (attribution.rule, attribution.kind) == (rule, reading)
    assert row is not None and row.identifier == rule


def test_the_same_error_code_is_a_defect_only_with_the_cause() -> None:
    rejected = _service(400, "ValidationException")
    table = ruled_classes()
    assert attribute(table, rejected, Cause.HARNESS_REQUEST_CONTRACT)[0].kind is DEFECT
    assert attribute(table, rejected)[0].kind is INFRASTRUCTURE
    with pytest.raises(ValueError, match="requires a cause"):
        AttributionRow(
            "by_code", Match(ObservationKind.SERVICE_ERROR, codes=frozenset({"X"})), DEFECT
        )


def test_the_first_row_in_order_decides_and_the_digest_holds_the_order() -> None:
    table = ruled_classes()
    # A throttle answered with a 503 meets two rows; the earlier one reads it.
    both = _service(503, "ThrottlingException")
    assert attribute(table, both)[0].rule == "throttled"
    rows = list(table.rows)
    names = [row.identifier for row in rows]
    throttled, server = names.index("throttled"), names.index("server_error")
    rows[throttled], rows[server] = rows[server], rows[throttled]
    swapped = AttributionTable(tuple(rows))
    assert attribute(swapped, both)[0].rule == "server_error"
    assert attribution_table_digest(swapped) != attribution_table_digest(table)
    assert attribution_table_digest(ruled_classes()) == attribution_table_digest(table)


def test_a_service_error_that_relays_no_status_does_not_meet_a_relayed_status() -> None:
    relayed = Match(ObservationKind.SERVICE_ERROR, original_statuses=frozenset({400}))
    assert relayed.takes(ServiceError(424, "ModelErrorException", 400, "s"), None)
    assert not relayed.takes(ServiceError(424, "ModelErrorException", None, "s"), None)


def test_no_recorded_outcome_is_unresolved_and_no_row() -> None:
    attribution, row = attribute(ruled_classes(), NoRecordedOutcome())
    assert (attribution.kind, attribution.rule) == (AttributionKind.UNRESOLVED, UNRESOLVED_RULE)
    assert row is None and kind_of(NoRecordedOutcome()) is None
    with pytest.raises(ValueError, match="is no row"):
        AttributionRow(UNRESOLVED_RULE, Match(ObservationKind.BROKEN_STREAM), INFRASTRUCTURE)
    with pytest.raises(ValueError, match="unresolved is the reading of no recorded outcome"):
        AttributionRow("lost", Match(ObservationKind.BROKEN_STREAM), AttributionKind.UNRESOLVED)


def test_a_table_leaves_no_observation_without_a_reading_and_no_row_unreachable() -> None:
    rows = ruled_classes().rows
    without_fallback = tuple(row for row in rows if row.identifier != "client_error")
    with pytest.raises(ValueError, match="rows for a client_error end in one that takes every"):
        AttributionTable(without_fallback)
    no_kind = tuple(
        row for row in rows if row.match.observation is not ObservationKind.BROKEN_STREAM
    )
    with pytest.raises(ValueError, match="rows for a broken_stream"):
        AttributionTable(no_kind)
    late = AttributionRow(
        "late", Match(ObservationKind.BROKEN_STREAM), INFRASTRUCTURE, new_attempt=True
    )
    with pytest.raises(ValueError, match="broken_stream takes every broken_stream"):
        AttributionTable((*rows, late))
    with pytest.raises(ValueError, match="identified once"):
        AttributionTable((*rows, rows[0]))


def test_only_an_infrastructure_reading_may_be_followed_by_anything() -> None:
    stop = Match(ObservationKind.COMPLETE_RESPONSE, stop_reasons=frozenset({"end_turn"}))
    for followed in ({"redispatch": True}, {"new_attempt": True}):
        with pytest.raises(ValueError, match="only an infrastructure reading"):
            AttributionRow("stop", stop, BEHAVIOUR, **followed)
        with pytest.raises(ValueError, match="only an infrastructure reading"):
            AttributionRow(
                "built", replace(stop, cause=Cause.HARNESS_REQUEST_CONTRACT), DEFECT, **followed
            )


def test_the_unmatched_mark_is_only_on_a_row_that_takes_everything_of_its_kind() -> None:
    with pytest.raises(ValueError, match="marked unmatched and constrains its match"):
        AttributionRow(
            "narrow",
            Match(ObservationKind.SERVICE_ERROR, codes=frozenset({"X"})),
            INFRASTRUCTURE,
            unmatched=True,
        )
    assert [row.identifier for row in ruled_classes().rows if row.unmatched] == [
        "unregistered_stop_reason",
        "unmatched_service_error",
        "refused_before_send",
    ]


def test_a_constraint_belongs_to_its_kind_and_admits_something() -> None:
    with pytest.raises(ValueError, match="codes constrains a service_error"):
        Match(ObservationKind.BROKEN_STREAM, codes=frozenset({"X"}))
    with pytest.raises(ValueError, match="an empty set matches nothing"):
        Match(ObservationKind.SERVICE_ERROR, http_statuses=frozenset())


def _as_json(table: AttributionTable) -> list[dict[str, Any]]:
    """The table's encoding as a caller would hold it after parsing the bytes."""
    return json.loads(canonical_json(encode_attribution_table(table)))


def test_the_table_round_trips_and_a_reordered_constraint_is_not_its_written_form() -> None:
    table = ruled_classes()
    encoded = _as_json(table)
    assert decode_attribution_table(encoded) == table
    server = next(row for row in encoded if row["identifier"] == "server_error")
    assert server["match"]["http_statuses"] == [500, 503]
    server["match"]["http_statuses"] = [503, 500]
    reread = decode_attribution_table(encoded)
    assert reread == table
    assert canonical_json(encode_attribution_table(reread)) != canonical_json(encoded)


def _without(key: str) -> Callable[[dict[str, Any]], None]:
    return lambda held: held.__delitem__(key)


def _with(key: str, value: object) -> Callable[[dict[str, Any]], None]:
    return lambda held: held.__setitem__(key, value)


@pytest.mark.parametrize(
    ("part", "damage", "message"),
    [
        ("row", _without("unmatched"), "an attribution row"),
        ("row", _with("redispatch", 1), "redispatch is true or false"),
        ("match", _with("cause", "a hunch"), "is not a valid Cause"),
        ("match", _with("http_statuses", ["503"]), "http_statuses is an integer"),
        ("match", _without("codes"), "an attribution match"),
    ],
)
def test_a_malformed_row_is_refused(
    part: str, damage: Callable[[dict[str, Any]], None], message: str
) -> None:
    encoded = _as_json(ruled_classes())
    damage(encoded[0] if part == "row" else encoded[0]["match"])
    with pytest.raises(ValueError, match=message):
        decode_attribution_table(encoded)
    with pytest.raises(ValueError, match="is a JSON array"):
        decode_attribution_table({"rows": encoded})


def test_the_redispatch_policy_is_bounded_and_round_trips() -> None:
    policy = RedispatchPolicy(3, 2000)
    assert decode_redispatch_policy(encode_redispatch_policy(policy)) == policy
    with pytest.raises(ValueError, match="max_dispatches is at least 1"):
        RedispatchPolicy(0, 2000)
    with pytest.raises(ValueError, match="max_delay_ms is at least 0"):
        RedispatchPolicy(1, -1)
    with pytest.raises(ValueError, match="a re-dispatch policy"):
        decode_redispatch_policy({"max_dispatches": 3})
