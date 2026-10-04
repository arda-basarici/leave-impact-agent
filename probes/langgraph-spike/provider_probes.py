"""The acceptance spike's live provider probes: the pinned chat client against both families.

The criteria are in ``probes/README.md``, written before any of this ran. Three of its
must-pass checks are decided here (the capture, the forced-choice matrix, the tool-result
string); the rest of this file measures, and any result of a measurement is a finding.

Run from the repository root, with an AWS profile that may invoke both inference profiles and
a private capture directory outside the tree:

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> AWS_PROFILE=<profile> \
        uv run --group harness python probes/langgraph-spike/provider_probes.py

``--only <probe>`` runs a subset, ``--offline`` runs against a canned answer with no send.
Every probe needs each family's effective surface, so the schema acceptance runs first in
every execution. A full execution makes about fifty sends against a guard of 150.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from bench import PROFILES, REGION, SYSTEM, Asked, Bench, Row, open_bench
from capture import USAGE_COUNTERS, Recorder, capture_root, require_tracing_off
from faults import provoked_faults
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from surface import LADDER, tool_choice, tools_under

from leaveimpact.core import Observed, Source, encode_observed
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.tools import specification_named, validate_arguments

FAMILIES = tuple(PROFILES)
CACHE_REPEATS = 3
VIOLATION_TRIES = 3


def _opening(text: str) -> list[Any]:
    return [SystemMessage(SYSTEM), HumanMessage(text)]


def _refusals(message: AIMessage) -> list[str]:
    """Why each tool call of ``message`` fails the tool's own validation; empty when all pass."""
    reasons: list[str] = []
    for call in message.tool_calls:
        specification = specification_named(call["name"])
        if specification is None:
            reasons.append(f"no tool named {call['name']!r}")
            continue
        try:
            validate_arguments(specification, call["args"])
        except ValueError as refused:
            reasons.append(str(refused))
    return reasons


def _usage(bench: Bench, asked: Asked) -> dict[str, Any]:
    """The raw usage and counter states of the last send of ``asked``, as captured."""
    outcome = bench.recorder.outcome_of(asked.sends[-1]) if asked.sends else None
    if outcome is None:
        return {"outcome": "unresolved"}
    return {
        "outcome": outcome["outcome"],
        "usage": outcome["usage"],
        "counters": outcome["counters"],
    }


# --- The effective surface ------------------------------------------------------------------


def schema_acceptance(bench: Bench, employee: str) -> None:
    """Measured: which rung of the ladder each family's endpoint accepts, unchanged first."""
    for family in FAMILIES:
        for translation in LADDER:
            bench.surfaces[family] = translation
            asked = bench.ask(
                "schema-acceptance",
                f"{family} {translation.name}",
                bench.bound(family, "any"),
                _opening(f"Look up the employee {employee}."),
            )
            accepted = asked.error is None
            bench.add(
                Row(
                    "schema-acceptance",
                    family,
                    translation.name,
                    "measured",
                    "finding",
                    {
                        "accepted": accepted,
                        "translation_version": translation.version,
                        "error": asked.error_code,
                        "message": str(asked.error)[:300] if asked.error else "",
                    },
                    asked.sends,
                )
            )
            if accepted:
                break
            if asked.error_code != "ValidationException":
                raise SystemExit(
                    f"{family}: {asked.error_code} is not a schema rejection; stopping"
                )
        else:
            raise SystemExit(f"{family} accepts no rung of the ladder; the matrix cannot run")


# --- Must pass ------------------------------------------------------------------------------


def forced_choice(bench: Bench, employee: str) -> None:
    """Must pass, eight cells: forced by ``any`` and by name, streamed and not, per family.

    A cell passes when the definitions and the choice in the captured request equal the
    effective surface bound, the answer carries at least one tool call, a named choice is
    answered with that tool, and every call's arguments pass the original validation.
    """
    for family in FAMILIES:
        translation = bench.surfaces[family]
        for choice in ("any", "employee"):
            for streamed in (False, True):
                cell = (
                    f"{'named' if choice != 'any' else 'any'} {'streamed' if streamed else 'whole'}"
                )
                if streamed and bench.offline:
                    bench.add(Row("forced-choice", family, cell, "must-pass", "skipped", {}))
                    continue
                asked = bench.ask(
                    "forced-choice",
                    f"{family} {cell}",
                    bench.bound(family, choice),
                    _opening(f"Look up the employee {employee}."),
                    streamed=streamed,
                )
                detail: dict[str, Any] = {"surface": translation.name, "error": asked.error_code}
                passed = False
                if asked.message is not None and asked.sends:
                    sent = bench.recorder.request_of(asked.sends[-1])["toolConfig"]
                    calls = asked.message.tool_calls
                    refusals = _refusals(asked.message)
                    detail |= {
                        "definitions_equal": sent["tools"] == tools_under(translation),
                        "choice_equal": sent["toolChoice"] == tool_choice(choice),
                        "calls": [call["name"] for call in calls],
                        "invalid_tool_calls": len(asked.message.invalid_tool_calls),
                        "refusals": refusals,
                    }
                    passed = (
                        detail["definitions_equal"]
                        and detail["choice_equal"]
                        and len(calls) >= 1
                        and not refusals
                        and (choice == "any" or all(call["name"] == choice for call in calls))
                    )
                verdict = "pass" if passed else "fail"
                bench.add(
                    Row("forced-choice", family, cell, "must-pass", verdict, detail, asked.sends)
                )


def tool_result(bench: Bench, employee: str, rendered: str) -> None:
    """Must pass: the canonical result string, sent back in one exchange, is in the captured
    request exactly, as the one text block of the tool result."""
    for family in FAMILIES:
        opening = _opening(f"Look up the employee {employee}.")
        first = bench.ask("tool-result", f"{family} call", bench.bound(family, "employee"), opening)
        if first.message is None or not first.message.tool_calls:
            bench.add(
                Row(
                    "tool-result",
                    family,
                    "round trip",
                    "must-pass",
                    "fail",
                    {"stage": "no forced call to answer", "error": first.error_code},
                    first.sends,
                )
            )
            continue
        call = first.message.tool_calls[0]
        second = bench.ask(
            "tool-result",
            f"{family} result",
            bench.bound(family, "auto"),
            [*opening, first.message, ToolMessage(rendered, tool_call_id=call["id"])],
        )
        held: list[Any] = []
        if second.sends:
            for message in bench.recorder.request_of(second.sends[-1])["messages"]:
                held += [b["toolResult"] for b in message["content"] if "toolResult" in b]
        exact = len(held) == 1 and held[0]["content"] == [{"text": rendered}]
        bench.add(
            Row(
                "tool-result",
                family,
                "round trip",
                "must-pass",
                "pass" if exact and second.error is None else "fail",
                {
                    "exact": exact,
                    "tool_results_in_request": len(held),
                    "rendered_bytes": len(rendered.encode("utf-8")),
                    "error": second.error_code,
                },
                first.sends + second.sends,
            )
        )


def capture_check(bench: Bench) -> None:
    """Must pass: every send of this execution left a request body as sent, and every send
    that was answered left the response body or the parsed events of its stream."""
    missing: list[str] = []
    unresolved: list[str] = []
    for invocation in bench.recorder.finished:
        for send in invocation.sends:
            folder = bench.recorder.directory
            if not (folder / f"{send}.request.json").exists():
                missing.append(f"{send} request")
            outcome = bench.recorder.outcome_of(send)
            if outcome is None:
                unresolved.append(send)
            elif not any(
                (folder / f"{send}.{kind}.json").exists() for kind in ("response", "stream")
            ):
                missing.append(f"{send} response")
    bench.add(
        Row(
            "capture",
            "both",
            "every send",
            "must-pass",
            "fail" if missing else "pass",
            {
                "sends": bench.recorder.sends_made,
                "missing": missing,
                "unresolved": unresolved,
                "cumulative_sends": bench.recorder.cumulative_sends(),
            },
        )
    )


# --- Measured -------------------------------------------------------------------------------


def digest_pair(bench: Bench, employee: str) -> None:
    """Measured: whether one logical request sent twice has one body digest."""
    for family in FAMILIES:
        pair = [
            bench.ask(
                "digest-pair",
                f"{family} {n}",
                bench.bound(family, "any"),
                _opening(f"Look up the employee {employee}."),
            )
            for n in (1, 2)
        ]
        digests = [
            bench.recorder.lines_of(asked.sends[-1])[0]["body_sha256"] if asked.sends else None
            for asked in pair
        ]
        bench.add(
            Row(
                "digest-pair",
                family,
                "two sends",
                "measured",
                "finding",
                {"equal": digests[0] is not None and digests[0] == digests[1], "digests": digests},
                pair[0].sends + pair[1].sends,
            )
        )


def _prefix(nonce: str) -> str:
    """Roughly eight thousand tokens of deterministic filler: over Haiku 4.5's documented 4,096
    minimum, under Nova's documented 20K maximum. The nonce leads, so no earlier execution's
    cache entry can be this one's prefix."""
    clauses = (
        f"Policy clause {n}: employees on approved leave hand over open work to a named "
        f"substitute before the first day of absence and record the handover."
        for n in range(1, 251)
    )
    return f"Reference {nonce}. " + " ".join(clauses)


def caching(bench: Bench) -> None:
    """Measured: the cache counters of each call, implicit and with an explicit checkpoint.

    The same request is repeated; a hit is never assumed. Each row holds the counters as the
    raw response carried them (present, zero or absent) and whether the reported total equals
    the sum of the four.
    """
    from langchain_aws import ChatBedrockConverse

    for family in FAMILIES:
        for kind in ("implicit", "explicit"):
            prefix = _prefix(f"{bench.recorder.execution}-{family}-{kind}")
            system: Any = prefix
            if kind == "explicit":
                system = [
                    {"type": "text", "text": prefix},
                    ChatBedrockConverse.create_cache_point(),
                ]
            messages = [SystemMessage(system), HumanMessage("Reply with the single word: ok")]
            for repeat in range(1, CACHE_REPEATS + 1):
                asked = bench.ask(
                    "caching",
                    f"{family} {kind} {repeat}",
                    bench.chat(family, max_tokens=16),
                    messages,
                )
                detail = _usage(bench, asked) | {"error": asked.error_code}
                usage = detail.get("usage")
                if isinstance(usage, dict):
                    parts = sum(int(usage.get(name, 0)) for name in USAGE_COUNTERS)
                    detail["total_equals_sum"] = usage.get("totalTokens") == parts
                bench.add(
                    Row(
                        "caching",
                        family,
                        f"{kind} {repeat}",
                        "measured",
                        "finding",
                        detail,
                        asked.sends,
                    )
                )


def truncated_call(bench: Bench) -> None:
    """Measured: a forced call cut by a very small output limit, the shape a run at its cap
    would produce, streamed and not."""
    text = "List the calendar events from 2026-09-14 09:00 to 2026-09-18 18:00, Istanbul time."
    for family in FAMILIES:
        for streamed in (False, True):
            if streamed and bench.offline:
                continue
            asked = bench.ask(
                "truncated-call",
                f"{family} {'streamed' if streamed else 'whole'}",
                bench.bound(family, "events_within", max_tokens=8),
                _opening(text),
                streamed=streamed,
            )
            detail: dict[str, Any] = {"error": asked.error_code}
            if asked.error is not None:
                detail["message"] = str(asked.error)[:300]
            if asked.message is not None:
                detail |= {
                    "stop_reason": asked.message.response_metadata.get("stopReason"),
                    "tool_calls": [dict(call) for call in asked.message.tool_calls],
                    "invalid_tool_calls": [dict(c) for c in asked.message.invalid_tool_calls],
                }
            bench.add(
                Row(
                    "truncated-call",
                    family,
                    "streamed" if streamed else "whole",
                    "measured",
                    "finding",
                    detail,
                    asked.sends,
                )
            )


def schema_violation(bench: Bench) -> None:
    """Measured: whether a model can be brought to call a tool against its schema in a fixed
    number of tries. Not elicited is a result."""
    prompts = (
        'Call the employee tool with the id "LIA-42", exactly as written.',
        'The id to look up is "LIA-42". Do not correct it; pass it to the employee tool as is.',
        "Look up the employee whose id is the number 42, passed as an integer, not a string.",
    )
    for family in FAMILIES:
        elicited: list[dict[str, Any]] = []
        sends: tuple[str, ...] = ()
        for prompt in prompts[:VIOLATION_TRIES]:
            asked = bench.ask(
                "schema-violation", f"{family}", bench.bound(family, "employee"), _opening(prompt)
            )
            sends += asked.sends
            if asked.message is not None and (reasons := _refusals(asked.message)):
                elicited.append({"refusals": reasons, "calls": asked.message.tool_calls})
            elif asked.error is not None:
                elicited.append({"error": asked.error_code})
        bench.add(
            Row(
                "schema-violation",
                family,
                f"{VIOLATION_TRIES} tries",
                "measured",
                "finding",
                {"elicited": len(elicited), "cases": elicited},
                sends,
            )
        )


def response_shapes(bench: Bench, employee: str, second_employee: str) -> None:
    """Measured: text beside a tool call, and several tool calls in one response."""
    text = (
        f"First say in one short sentence what you are about to do. Then look up both "
        f"{employee} and {second_employee} with the employee tool, both calls in this one reply."
    )
    for family in FAMILIES:
        asked = bench.ask("response-shapes", family, bench.bound(family, "auto"), _opening(text))
        detail: dict[str, Any] = {"error": asked.error_code}
        if asked.message is not None:
            content = asked.message.content
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            detail |= {
                "text_blocks": sum(
                    1
                    for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                ),
                "tool_calls": len(asked.message.tool_calls),
                "stop_reason": asked.message.response_metadata.get("stopReason"),
            }
        bench.add(
            Row(
                "response-shapes",
                family,
                "text and calls",
                "measured",
                "finding",
                detail,
                asked.sends,
            )
        )
    bench.add(
        Row(
            "response-shapes",
            "both",
            "parallel calls off",
            "measured",
            "finding",
            {
                "sent": False,
                "reason": "the Converse tool choice documents no switch for parallel calls "
                "(auto, any and tool only); a model-specific request field was not tried",
            },
        )
    )


# --- The command ----------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="The acceptance spike's live provider probes.")
    parser.add_argument("--only", action="append", default=[], help="a probe to run; repeatable")
    parser.add_argument("--offline", action="store_true", help="a canned answer, no send")
    parser.add_argument("--region", default=REGION)
    arguments = parser.parse_args()

    require_tracing_off()
    root = capture_root()

    from tests.unit.throwaway_world import loaded_world

    employees = loaded_world().org.employees
    employee, second = employees[0].id, employees[1].id
    rendered = canonical_json(encode_observed(Observed(employees[0], Source.FRAPPE)))

    recorder = Recorder(root, arguments.region)
    bench = open_bench(recorder, offline=arguments.offline, employee=employee)
    print(f"execution {recorder.execution}; {recorder.cumulative_sends()} sends recorded before it")

    probes: dict[str, Callable[[], None]] = {
        "forced-choice": lambda: forced_choice(bench, employee),
        "tool-result": lambda: tool_result(bench, employee, rendered),
        "digest-pair": lambda: digest_pair(bench, employee),
        "caching": lambda: caching(bench),
        "truncated-call": lambda: truncated_call(bench),
        "schema-violation": lambda: schema_violation(bench),
        "response-shapes": lambda: response_shapes(bench, employee, second),
        "faults": lambda: provoked_faults(bench, employee),
    }
    unknown = [name for name in arguments.only if name not in probes]
    if unknown:
        parser.error(f"no probe named {', '.join(unknown)}; the probes are {', '.join(probes)}")

    schema_acceptance(bench, employee)
    for name, probe in probes.items():
        if not arguments.only or name in arguments.only:
            probe()
    capture_check(bench)

    failed = [row for row in bench.rows if row.verdict == "fail"]
    print(
        f"{recorder.sends_made} sends this execution, {recorder.cumulative_sends()} in all; "
        f"{len(failed)} must-pass rows failed; rows in {recorder.execution}/findings.jsonl"
    )
    print(json.dumps({"surfaces": {f: t.name for f, t in bench.surfaces.items()}}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
