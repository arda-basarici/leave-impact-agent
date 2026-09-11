"""Shared HTTP mechanics beneath the vendor adapters: timeouts, the retry rule, the fault seam.

Frappe and Jira ride this module; the calendar adapter rides the Google client's own
transport and maps the same fault classes onto the same two port exceptions; the
corpus is psycopg and has no HTTP at all. It sits at the ``adapters`` level rather than
inside one sibling because siblings never import one another (the import law), and a
retry rule copied into two adapters would drift apart at the first fix.

**The retry rule.** Every request declares whether it is *replayable*: a request whose
repetition cannot change the world — a read, or a write whose identity the caller fixed
so a second arrival answers "already exists". The transport needs only that property,
never the reason, so the declaration is a flag and the justification lives at the call
site. A replayable request retries on every wire fault and on 429, 502, 503 and
504. A non-replayable one retries only where the request provably never arrived — a
connect error, a connect timeout, or a timeout waiting for a pool connection, the three
faults httpx raises before anything is sent — and on 429,
which Jira and the Cloudflare edge in front of Frappe answer without acting (an adapter
contract from observed behaviour, not an HTTP guarantee). Everything else after bytes
went out is ambiguous and raises at once, because a Frappe or Jira create replayed after
a lost response mints a duplicate; the projector recovers that case by restarting
find-or-create, so the recovery loop stays above the wire. Ruled at step 9 of the world
milestone's build, correcting the seed spike's "every write is find-or-create, so a
retry is safe": the operation is safe to restart, the wire call is not safe to replay.

**The pause.** Retry-After is honoured in its integer-seconds form and capped; the
HTTP-date form falls back to the growing backoff, because turning it into a delay would
read the wall clock this package never reads. ``sleep`` is injected so a cassette replay
never waits.

**The fault seam.** After the last attempt the transport raises ``SourceUnreachable``
with the vendor error chained as the cause. A status the caller did not declare
acceptable raises the same, status and body excerpt in the reason: the run cannot get
an answer from that source, and whether the cause is their outage or our request is a
diagnosis for the log, not a third exception type — the port declares two. A 404 on a
select-by-id is not a fault: the caller lists 404 as acceptable and maps the response to
``None``. Client-side errors that are neither the vendor's nor the wire's are defects
and propagate untouched — including the two httpx failures under its transport errors, a
local protocol violation and an unsupported URL scheme, which are re-raised before the
operational branch so a defect is never retried into a run condition (a review finding).
A response whose body cannot be decoded (a content-encoding header the bytes do not
honour) is not a wire fault in httpx's taxonomy and not a defect of ours: the source
answered and the answer is unreadable, which is ``MalformedRecord`` with the request as
locator, the same class a body that is not JSON gets in the adapters.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

from leaveimpact.core.enums import Source
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable

_REPLAYABLE_STATUSES = frozenset({429, 502, 503, 504})
_NEVER_ACTED_STATUSES = frozenset({429})
_CONNECT_PHASE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
_DEFECTS = (httpx.LocalProtocolError, httpx.UnsupportedProtocol)
_EXCERPT_CHARS = 200


@dataclass(frozen=True, slots=True)
class TransportPolicy:
    """Timeouts and the retry budget as numbers; the rule that spends them is the transport's.

    ``attempts`` counts requests, so three means two retries. The pause before retry
    ``n`` is ``backoff_s * n`` unless a Retry-After header says otherwise, and either is
    capped at ``max_pause_s``. The defaults are the seed spike's: fail fast on a stalled
    connection, three attempts, a growing pause.

    >>> TransportPolicy(attempts=0)
    Traceback (most recent call last):
    ...
    ValueError: attempts must be at least 1, got 0
    """

    connect_timeout_s: float = 10.0
    read_timeout_s: float = 60.0
    attempts: int = 3
    backoff_s: float = 2.0
    max_pause_s: float = 30.0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError(f"attempts must be at least 1, got {self.attempts}")
        for name in ("connect_timeout_s", "read_timeout_s", "backoff_s", "max_pause_s"):
            value: float = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")


DEFAULT_POLICY = TransportPolicy()


class Transport:
    """One vendor's HTTP session under the retry rule; the adapter owns it and speaks through it.

    The adapter supplies the base URL and its authentication (a header set, or an httpx
    auth flow), and calls ``request`` with the path relative to the base. ``sleep`` and
    ``httpx_transport`` are seams for tests: a recorded list of pauses in place of
    ``time.sleep``, a mock transport in place of the network. Use as a context manager
    or call ``close``; the underlying connection pool is the adapter's lifecycle.
    """

    def __init__(
        self,
        *,
        base_url: str,
        source: Source,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | None = None,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] = time.sleep,
        httpx_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._source = source
        self._policy = policy
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            auth=auth,
            timeout=httpx.Timeout(policy.read_timeout_s, connect=policy.connect_timeout_s),
            transport=httpx_transport,
        )

    @property
    def source(self) -> Source:
        return self._source

    def request(
        self,
        method: str,
        path: str,
        *,
        replayable: bool,
        ok: Collection[int] = (200,),
        **kwargs: Any,
    ) -> httpx.Response:
        """Send under the retry rule; return the response when its status is in ``ok``.

        ``replayable`` is the caller's declaration that repeating this exact request
        cannot change the world (the module docstring says what that permits).
        ``kwargs`` pass through to httpx (``params``, ``json``, ``content``). Raises
        ``SourceUnreachable`` when the budget is spent, when a non-replayable request's
        outcome became unknown, or when the status is neither acceptable nor retriable.
        """
        retriable = _REPLAYABLE_STATUSES if replayable else _NEVER_ACTED_STATUSES
        attempt = 0
        while True:
            attempt += 1
            last = attempt == self._policy.attempts
            try:
                response = self._client.request(method, path, **kwargs)
            except _DEFECTS:
                raise
            except httpx.DecodingError as exc:
                raise MalformedRecord(
                    self._source, f"{method} {path}", f"response body could not be decoded: {exc}"
                ) from exc
            except httpx.TransportError as exc:
                fault = type(exc).__name__
                if not replayable and not isinstance(exc, _CONNECT_PHASE):
                    raise SourceUnreachable(
                        self._source,
                        f"{method} {path}: {fault} after the request was sent, outcome unknown",
                    ) from exc
                if last:
                    raise SourceUnreachable(
                        self._source, f"{method} {path}: {fault} on all {attempt} attempts"
                    ) from exc
                self._sleep(self._backoff(attempt))
                continue
            status = response.status_code
            if status in ok:
                return response
            if status not in retriable:
                raise SourceUnreachable(
                    self._source, f"{method} {path} -> {status}: {_excerpt(response)}"
                )
            if last:
                raise SourceUnreachable(
                    self._source,
                    f"{method} {path} -> {status} on all {attempt} attempts: {_excerpt(response)}",
                )
            self._sleep(self._pause(response, attempt))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _backoff(self, attempt: int) -> float:
        return min(self._policy.max_pause_s, self._policy.backoff_s * attempt)

    def _pause(self, response: httpx.Response, attempt: int) -> float:
        # Only the integer form is honoured: the HTTP-date form needs "now" to become a
        # delay, and this package reads no clock.
        header = response.headers.get("retry-after", "").strip()
        if header.isdigit():
            return min(self._policy.max_pause_s, float(header))
        return self._backoff(attempt)


def _excerpt(response: httpx.Response) -> str:
    """The start of the body on one line, for a reason string that has to be logged."""
    return " ".join(response.text[:_EXCERPT_CHARS].split())
