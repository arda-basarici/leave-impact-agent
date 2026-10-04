"""The acceptance spike's live provider probes: the pinned chat client against both families.

The criteria are in ``probes/README.md``, written before any of this ran. Three of its
must-pass checks are decided here (the capture, the forced-choice matrix, the tool-result
string); the rest of this file measures, and any result of a measurement is a finding.

Run from the repository root, with an AWS profile that may invoke both inference profiles and
a private capture directory outside the tree:

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> AWS_PROFILE=<profile> \
        uv run --group harness python probes/langgraph-spike/provider_probes.py

``--only <probe>`` runs a subset, ``--offline`` runs against a canned answer with no send.
A probe that binds tools needs each family's effective surface, so the schema acceptance
runs first in any execution that includes one. A full execution makes about fifty-five
sends against a guard of 150.
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
SURFACE_FREE = frozenset({"caching", "serving-identity"})
"""The probes that bind no tool, so an execution of only these skips the schema acceptance."""


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


def _wire_answer(bench: Bench, send: str) -> dict[str, Any]:
    """What the captured bytes of ``send`` hold: the operation, the stop reason, and each tool
    call with its arguments parsed strictly.

    The chat client assembles a streamed call's arguments with a parser that repairs cut JSON,
    so a call it reports can rest on arguments that never arrived whole. Here a streamed call's
    argument fragments are joined per content block and parsed by ``json.loads``; ``complete``
    is false for a call whose fragments do not parse, and its ``input`` is ``None``.
    """
    operation = bench.recorder.lines_of(send)[0]["operation"]
    calls: list[dict[str, Any]] = []
    stop: Any = None
    if (whole := bench.recorder.response_of(send)) is not None:
        stop = whole.get("stopReason")
        for block in whole.get("output", {}).get("message", {}).get("content", []):
            if "toolUse" in block:
                use = block["toolUse"]
                calls.append({"name": use.get("name"), "input": use.get("input"), "complete": True})
    elif (stream := bench.recorder.stream_of(send)) is not None:
        names: dict[int, Any] = {}
        fragments: dict[int, str] = {}
        for event in stream["events"]:
            if "contentBlockStart" in event and "toolUse" in event["contentBlockStart"]["start"]:
                index = event["contentBlockStart"]["contentBlockIndex"]
                names[index] = event["contentBlockStart"]["start"]["toolUse"].get("name")
                fragments[index] = ""
            elif "contentBlockDelta" in event and "toolUse" in event["contentBlockDelta"]["delta"]:
                index = event["contentBlockDelta"]["contentBlockIndex"]
                piece = event["contentBlockDelta"]["delta"]["toolUse"].get("input", "")
                fragments[index] = fragments.get(index, "") + piece
            elif "messageStop" in event:
                stop = event["messageStop"].get("stopReason")
        for index in sorted(names):
            try:
                calls.append(
                    {"name": names[index], "input": json.loads(fragments[index]), "complete": True}
                )
            except ValueError:
                calls.append({"name": names[index], "input": None, "complete": False})
    return {"operation": operation, "stop_reason": stop, "calls": calls}


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
    """Measured: which rung of the ladder each family's endpoint accepts, unchanged first.

    Each rung's captured request is compared with the definitions bound, the rejected ones
    too, so a rejection is the family's answer to exactly those definitions. A validation
    rejection is read as the surface's; its message is kept in the row, since the service
    uses the same code for any invalid request.
    """
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
            sent_as_bound = bool(asked.sends) and (
                bench.recorder.request_of(asked.sends[-1])["toolConfig"]["tools"]
                == tools_under(translation)
            )
            bench.add(
                Row(
                    "schema-acceptance",
                    family,
                    translation.name,
                    "measured",
                    "finding",
                    {
                        "accepted": accepted,
                        "sent_as_bound": sent_as_bound,
                        "translation_version": translation.version,
                        "error": asked.error_code,
                        "message": str(asked.error)[:300] if asked.error else "",
                    },
                    asked.sends,
                )
            )
            if not sent_as_bound:
                # An acceptance or a rejection of definitions the client altered on the way
                # says nothing about the family.
                raise SystemExit(f"{family}: the request did not carry the surface bound")
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

    A cell passes when all of these hold. The definitions and the choice in the captured
    request equal the effective surface bound. The send used the operation the cell names.
    The captured answer stopped on ``tool_use`` and every tool call in it has arguments that
    parse whole. The client's message carries at least one tool call and no invalid one, its
    calls are the captured ones, a named choice is answered with that tool, and every call's
    arguments pass the original validation.
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
                    wire = _wire_answer(bench, asked.sends[-1])
                    calls = asked.message.tool_calls
                    refusals = _refusals(asked.message)
                    detail |= {
                        "definitions_equal": sent["tools"] == tools_under(translation),
                        "choice_equal": sent["toolChoice"] == tool_choice(choice),
                        "operation": wire["operation"],
                        "stop_reason": wire["stop_reason"],
                        "wire_calls_complete": all(call["complete"] for call in wire["calls"]),
                        "message_equals_wire": [(c["name"], c["args"]) for c in calls]
                        == [(c["name"], c["input"]) for c in wire["calls"]],
                        "calls": [call["name"] for call in calls],
                        "invalid_tool_calls": len(asked.message.invalid_tool_calls),
                        "refusals": refusals,
                    }
                    passed = (
                        detail["definitions_equal"]
                        and detail["choice_equal"]
                        and wire["operation"] == ("ConverseStream" if streamed else "Converse")
                        and wire["stop_reason"] == "tool_use"
                        and detail["wire_calls_complete"]
                        and detail["message_equals_wire"]
                        and len(calls) >= 1
                        and not asked.message.invalid_tool_calls
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
    """Must pass: every send left its request body as sent, and every send has an outcome
    whose answer was recorded: a response body that parses, or a stream's parsed events in
    the order a stream has (it opens on ``messageStart``, and one recorded as complete holds
    ``messageStop`` once).

    A send with no outcome fails the check, with one exception named here: the read-timeout
    probe's sends, which are unresolved by design. An unresolved send anywhere else is a
    request whose answer the recorder lost or never saw.
    """
    missing: list[str] = []
    malformed: list[str] = []
    unresolved: list[str] = []
    unexpected: list[str] = []
    for invocation in bench.recorder.finished:
        timeout = (invocation.probe, invocation.label) == ("faults", "read timeout")
        for send in invocation.sends:
            try:
                bench.recorder.request_of(send)
            except (OSError, ValueError):
                missing.append(f"{send} request")
            outcome = bench.recorder.outcome_of(send)
            if outcome is None:
                (unresolved if timeout else unexpected).append(send)
                continue
            stream = bench.recorder.stream_of(send)
            if stream is not None:
                events = stream["events"]
                stops = sum(1 for event in events if "messageStop" in event)
                opened = bool(events) and "messageStart" in events[0]
                if outcome["outcome"] == "response" and not (opened and stops == 1):
                    malformed.append(f"{send} stream")
                continue
            try:
                if bench.recorder.response_of(send) is None:
                    missing.append(f"{send} response")
            except ValueError:
                malformed.append(f"{send} response")
    failed = bool(missing or malformed or unexpected)
    bench.add(
        Row(
            "capture",
            "both",
            "every send",
            "must-pass",
            "fail" if failed else "pass",
            {
                "sends": bench.recorder.sends_made,
                "missing": missing,
                "malformed": malformed,
                "unresolved_timeout_sends": unresolved,
                "unresolved_unexpected": unexpected,
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
                    "wire": _wire_answer(bench, asked.sends[-1]) if asked.sends else None,
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


def serving_identity(bench: Bench) -> None:
    """Measured: what a response says about where it was served, streamed and not.

    The request names an inference profile and a client region; the body of a response names
    neither. Whatever identifies the serving side is in the response headers, kept whole in
    the record's outcome line. The row lists the header names and the values of the ones the
    service adds, the request id left out.
    """
    for family in FAMILIES:
        for streamed in (False, True):
            if streamed and bench.offline:
                continue
            asked = bench.ask(
                "serving-identity",
                f"{family} {'streamed' if streamed else 'whole'}",
                bench.chat(family, max_tokens=16),
                [HumanMessage("Reply with the single word: ok")],
                streamed=streamed,
            )
            outcome = bench.recorder.outcome_of(asked.sends[-1]) if asked.sends else None
            headers: dict[str, str] = (outcome or {}).get("response_headers", {})
            bench.add(
                Row(
                    "serving-identity",
                    family,
                    "streamed" if streamed else "whole",
                    "measured",
                    "finding",
                    {
                        "requested_profile": PROFILES[family],
                        "client_region": bench.recorder.region,
                        "header_names": sorted(headers),
                        "service_headers": {
                            name: value
                            for name, value in sorted(headers.items())
                            if name.startswith("x-amz") and name != "x-amzn-requestid"
                        },
                        "error": asked.error_code,
                    },
                    asked.sends,
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

    recorder = Recorder(root, arguments.region, offline=arguments.offline)
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
        "serving-identity": lambda: serving_identity(bench),
    }
    unknown = [name for name in arguments.only if name not in probes]
    if unknown:
        parser.error(f"no probe named {', '.join(unknown)}; the probes are {', '.join(probes)}")

    if not arguments.only or any(name not in SURFACE_FREE for name in arguments.only):
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
