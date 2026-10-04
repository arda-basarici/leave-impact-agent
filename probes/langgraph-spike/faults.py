"""Provider faults provoked on purpose, each kept with its exception, service code and stage.

All four are measurements. The configured attempt count is a ceiling, never an expectation:
a request refused before sending makes no send, a rejection makes one, and whether a read
timeout is sent again is what the timeout probe observes. The one assertion is that the
observed sends never exceed the ceiling, and a row that breaks it is a failed row.

A row states what was provoked (``provoked``) apart from what happened (``observed``, derived
from the sends and their outcomes), so a fault that did not occur reads as one that did not.

The permission denial is not provoked here. These probes run under a principal that is
allowed to invoke both profiles, so a denial is not tested under this principal; the row says
so, and it is owed from the deployed role's own network.
"""

from __future__ import annotations

from typing import Any

from bench import Asked, Bench, Row
from capture import clients
from langchain_core.messages import HumanMessage, SystemMessage
from surface import tool_config

TIMEOUT_ATTEMPTS = 2
TIMEOUT_SECONDS = 0.2
FAMILY = "haiku"


def observed_stage(error: BaseException | None, outcomes: list[dict[str, Any] | None]) -> str:
    """What the sends and their outcomes show happened, in words.

    >>> observed_stage(ValueError("x"), [])
    'raised with no send'
    >>> observed_stage(TimeoutError(), [None, None])
    '2 sends, none answered'
    >>> observed_stage(None, [{"outcome": "response", "http_status": 200}])
    'answered, HTTP 200'
    """
    if not outcomes:
        return "raised with no send" if error is not None else "no send, nothing raised"
    last = outcomes[-1]
    if last is None:
        answered = sum(1 for outcome in outcomes if outcome is not None)
        return f"{len(outcomes)} sends, {answered if answered else 'none'} answered"
    if last["outcome"] == "service_error":
        return f"rejected by the service, HTTP {last['http_status']}"
    return f"answered, HTTP {last['http_status']}"


def _row(bench: Bench, cell: str, ceiling: int, asked: Asked, provoked: str) -> None:
    outcomes = [bench.recorder.outcome_of(send) for send in asked.sends]
    within = len(asked.sends) <= ceiling
    detail = {
        "provoked": provoked,
        "observed": observed_stage(asked.error, outcomes),
        "exception": type(asked.error).__name__ if asked.error else None,
        "service_code": asked.error_code,
        "message": str(asked.error)[:300] if asked.error else "",
        "sends": len(asked.sends),
        "ceiling": ceiling,
        "within_ceiling": within,
        "outcomes": [o["outcome"] if o else "unresolved" for o in outcomes],
        "http_status": [o["http_status"] if o else None for o in outcomes],
    }
    verdict = "finding" if within else "fail"
    bench.add(Row("faults", FAMILY, cell, "measured", verdict, detail, asked.sends))


def provoked_faults(bench: Bench, employee: str) -> None:
    """The read timeout, the request refused before sending, the request AWS rejects, and the
    denial's row."""
    opening = [SystemMessage("You answer at length."), HumanMessage(f"Describe {employee}'s week.")]

    if bench.offline:
        bench.add(Row("faults", FAMILY, "read timeout", "measured", "skipped", {}))
    else:
        # Its own client: the short timeout and the second attempt belong to this probe only.
        slow, _ = clients(
            bench.recorder, total_max_attempts=TIMEOUT_ATTEMPTS, read_timeout=TIMEOUT_SECONDS
        )
        asked = bench.ask(
            "faults", "read timeout", bench.chat(FAMILY, max_tokens=512, runtime=slow), opening
        )
        _row(
            bench,
            "read timeout",
            TIMEOUT_ATTEMPTS,
            asked,
            f"a read timeout of {TIMEOUT_SECONDS} s; whether the model ran or usage was "
            "incurred cannot be known from the client",
        )

    refused = bench.chat(FAMILY).bind(toolConfig={"tools": "not a list", "toolChoice": {"any": {}}})
    asked = bench.ask("faults", "refused before sending", refused, opening)
    _row(bench, "refused before sending", 1, asked, "a request the SDK's own validation refuses")

    missing = tool_config(bench.surfaces[FAMILY], "no_such_tool")
    asked = bench.ask(
        "faults", "rejected by the service", bench.chat(FAMILY).bind(toolConfig=missing), opening
    )
    _row(bench, "rejected by the service", 1, asked, "a tool choice naming a tool not defined")

    bench.add(
        Row(
            "faults",
            FAMILY,
            "permission denial",
            "measured",
            "not-run",
            {"reason": "permission denial not tested under this principal"},
        )
    )
