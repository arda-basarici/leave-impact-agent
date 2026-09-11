"""The retry rule as behaviour: what is replayed, what is not, and what the caller sees after.

Every case runs against a scripted httpx mock transport — a fixed sequence of responses
and faults per test — with the pause recorded instead of slept, so the rule is proven
without a network and without waiting. The claims: a replayable request survives a
transient status or fault and returns; a non-replayable one replays only a fault the
client names as connect-phase and stops at once on anything after bytes went out; the
pause follows Retry-After's integer form under the cap and the backoff otherwise; the
budget's end and an undeclared status both surface as ``SourceUnreachable`` with the
cause chained where there is one.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from leaveimpact.adapters.transport import DEFAULT_POLICY, Transport, TransportPolicy
from leaveimpact.core.enums import Source
from leaveimpact.core.ports.errors import SourceUnreachable

Outcome = httpx.Response | Exception


class Scripted:
    """A mock transport that answers each request with the next scripted outcome."""

    def __init__(self, *outcomes: Outcome) -> None:
        self.seen: list[httpx.Request] = []
        self._outcomes: Iterator[Outcome] = iter(outcomes)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def transport(
    script: Scripted, pauses: list[float], policy: TransportPolicy = DEFAULT_POLICY
) -> Transport:
    return Transport(
        base_url="https://vendor.invalid",
        source=Source.JIRA,
        headers={"Authorization": "token sample"},
        policy=policy,
        sleep=pauses.append,
        httpx_transport=httpx.MockTransport(script.handler),
    )


def response(status: int, body: str = "", **headers: str) -> httpx.Response:
    return httpx.Response(status, text=body, headers=headers)


def test_replayable_read_survives_a_transient_status() -> None:
    script = Scripted(response(503), response(200, '{"ok": true}'))
    pauses: list[float] = []
    got = transport(script, pauses).request("GET", "/thing", replayable=True)
    assert got.status_code == 200
    assert len(script.seen) == 2
    assert pauses == [2.0]


def test_replayable_read_survives_a_fault_after_bytes_were_sent() -> None:
    script = Scripted(httpx.ReadTimeout("stalled"), httpx.ReadTimeout("stalled"), response(200))
    pauses: list[float] = []
    assert transport(script, pauses).request("GET", "/thing", replayable=True).status_code == 200
    assert pauses == [2.0, 4.0]


def test_non_replayable_write_replays_a_connect_phase_fault() -> None:
    script = Scripted(httpx.ConnectError("refused"), response(201))
    pauses: list[float] = []
    got = transport(script, pauses).request("POST", "/things", replayable=False, ok=(201,))
    assert got.status_code == 201
    assert len(script.seen) == 2


def test_non_replayable_write_replays_a_pool_timeout() -> None:
    script = Scripted(httpx.PoolTimeout("no connection free"), response(201))
    pauses: list[float] = []
    got = transport(script, pauses).request("POST", "/things", replayable=False, ok=(201,))
    assert got.status_code == 201, "a pool timeout happens before anything is sent"
    assert len(script.seen) == 2


def test_non_replayable_write_stops_at_once_after_bytes_were_sent() -> None:
    script = Scripted(httpx.ReadTimeout("stalled"), response(201))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable) as caught:
        transport(script, pauses).request("POST", "/things", replayable=False, ok=(201,))
    assert len(script.seen) == 1, "the create must not be replayed: it may have been applied"
    assert pauses == []
    assert "outcome unknown" in caught.value.reason
    assert isinstance(caught.value.__cause__, httpx.ReadTimeout)


def test_non_replayable_write_stops_at_once_on_a_gateway_status() -> None:
    script = Scripted(response(504), response(201))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable) as caught:
        transport(script, pauses).request("POST", "/things", replayable=False, ok=(201,))
    assert len(script.seen) == 1
    assert "504" in caught.value.reason


def test_non_replayable_write_retries_a_rate_limit() -> None:
    script = Scripted(response(429, **{"Retry-After": "7"}), response(201))
    pauses: list[float] = []
    got = transport(script, pauses).request("POST", "/things", replayable=False, ok=(201,))
    assert got.status_code == 201
    assert pauses == [7.0]


def test_retry_after_is_capped() -> None:
    script = Scripted(response(429, **{"Retry-After": "600"}), response(200))
    pauses: list[float] = []
    policy = TransportPolicy(max_pause_s=30.0)
    transport(script, pauses, policy).request("GET", "/thing", replayable=True)
    assert pauses == [30.0]


def test_retry_after_in_date_form_falls_back_to_the_backoff() -> None:
    dated = response(503, **{"Retry-After": "Fri, 11 Sep 2026 20:00:00 GMT"})
    script = Scripted(dated, response(200))
    pauses: list[float] = []
    transport(script, pauses).request("GET", "/thing", replayable=True)
    assert pauses == [2.0]


def test_the_budget_ends_with_the_last_status_in_the_reason() -> None:
    script = Scripted(response(503, "down"), response(503, "down"), response(503, "still down"))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable) as caught:
        transport(script, pauses).request("GET", "/thing", replayable=True)
    assert len(script.seen) == 3
    assert pauses == [2.0, 4.0]
    assert "503 on all 3 attempts" in caught.value.reason
    assert "still down" in caught.value.reason
    assert caught.value.source is Source.JIRA


def test_the_budget_ends_with_the_fault_chained() -> None:
    script = Scripted(*(httpx.ConnectError("refused") for _ in range(3)))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable) as caught:
        transport(script, pauses).request("GET", "/thing", replayable=True)
    assert "ConnectError on all 3 attempts" in caught.value.reason
    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_an_undeclared_status_is_unreachable_without_a_retry() -> None:
    script = Scripted(response(400, '{"error": "bad filter"}\n  second line'), response(200))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable) as caught:
        transport(script, pauses).request("GET", "/thing", replayable=True)
    assert len(script.seen) == 1
    assert caught.value.reason == 'GET /thing -> 400: {"error": "bad filter"} second line'


def test_a_declared_status_is_returned_for_the_caller_to_map() -> None:
    script = Scripted(response(404))
    pauses: list[float] = []
    got = transport(script, pauses).request("GET", "/thing/1", replayable=True, ok=(200, 404))
    assert got.status_code == 404


def test_the_session_carries_base_url_and_headers() -> None:
    script = Scripted(response(200))
    pauses: list[float] = []
    transport(script, pauses).request("GET", "/api/x", replayable=True, params={"q": "1"})
    (sent,) = script.seen
    assert str(sent.url) == "https://vendor.invalid/api/x?q=1"
    assert sent.headers["Authorization"] == "token sample"


def test_a_client_side_defect_propagates_untouched() -> None:
    script = Scripted(response(200))
    pauses: list[float] = []
    with pytest.raises(TypeError):
        transport(script, pauses).request("POST", "/x", replayable=True, json={"a": object()})
    assert script.seen == [], "the defect is ours and never reaches the wire"


@pytest.mark.parametrize(
    "defect", [httpx.LocalProtocolError("ours"), httpx.UnsupportedProtocol("ours")]
)
@pytest.mark.parametrize("replayable", [True, False])
def test_a_transport_level_defect_is_never_retried_into_a_run_condition(
    defect: Exception, replayable: bool
) -> None:
    script = Scripted(defect, response(200))
    pauses: list[float] = []
    with pytest.raises(type(defect)):
        transport(script, pauses).request("POST", "/x", replayable=replayable, ok=(200, 201))
    assert len(script.seen) == 1 and pauses == []


def test_a_single_attempt_policy_never_pauses() -> None:
    script = Scripted(response(503))
    pauses: list[float] = []
    with pytest.raises(SourceUnreachable):
        transport(script, pauses, TransportPolicy(attempts=1)).request(
            "GET", "/thing", replayable=True
        )
    assert pauses == []
