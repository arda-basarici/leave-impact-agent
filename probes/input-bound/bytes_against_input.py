"""Request bytes against reported input tokens, over the acceptance spike's captured sends.

The ledger authorizes a model call on a bound of its input tokens, established before the
request leaves. The cheapest candidate is the request body's length: a token covers at least
one byte of text, so bytes bound tokens unless the provider adds input the body does not
hold (a hidden tool preamble, message framing). This reads every captured send that reported
usage and prints how far the byte length sits above the reported total input, by model
family and by streamed or whole, and every send where it sits below.

A second candidate bounds a call by the previous call's reported input plus what was
appended since. The captures hold few such sequences; they are found by one request's
messages extending another's under the same system prompt and tools, and each is printed
with the bytes appended beside the tokens the reported input grew by.

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> python probes/input-bound/bytes_against_input.py

It reads the shared record and the request files and nothing else: no client, no send. The
captures hold model requests and live outside the repository. A send whose usage is unknown
is left out and counted, never read as zero. Total input is the input, cache-read and
cache-write counters summed; a counter a response did not carry is absent from the sum, and
the number of sends that lacked one is printed.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CAPTURES_VARIABLE = "LEAVE_IMPACT_SPIKE_CAPTURES"
INPUT_COUNTERS = ("inputTokens", "cacheReadInputTokens", "cacheWriteInputTokens")


@dataclass(frozen=True, slots=True)
class Measured:
    """One send that reported usage: its request's size and what the provider counted."""

    send: str
    execution: str
    family: str
    mode: str
    body_bytes: int
    total_input: int
    counters_absent: int

    @property
    def bytes_per_token(self) -> float:
        return self.body_bytes / self.total_input


def family_of(model: str) -> str:
    """The model family a profile id names.

    >>> family_of("eu.anthropic.claude-haiku-4-5-20251001-v1:0")
    'haiku'
    >>> family_of("eu.amazon.nova-pro-v1:0")
    'nova'
    """
    if "anthropic" in model:
        return "haiku"
    return "nova" if "nova" in model else f"other ({model})"


def total_input(usage: dict[str, Any]) -> tuple[int, int]:
    """The input-side counters summed, with how many of the three the usage did not carry.

    >>> total_input({"inputTokens": 10, "cacheReadInputTokens": 5})
    (15, 1)
    """
    held = [usage[name] for name in INPUT_COUNTERS if name in usage]
    return sum(held), len(INPUT_COUNTERS) - len(held)


def measured_sends(record: list[dict[str, Any]]) -> tuple[list[Measured], int]:
    """Every send with reported usage, and the number of sends left out for having none."""
    outcomes = {line["send"]: line for line in record if line["event"] == "outcome"}
    kept: list[Measured] = []
    unknown = 0
    for line in record:
        if line["event"] != "send" or line.get("offline"):
            continue
        usage = (outcomes.get(line["send"]) or {}).get("usage")
        if not isinstance(usage, dict) or "inputTokens" not in usage:
            unknown += 1
            continue
        tokens, absent = total_input(usage)
        kept.append(
            Measured(
                send=line["send"],
                execution=line["execution"],
                family=family_of(line["requested_model"]),
                mode="streamed" if line["operation"] == "ConverseStream" else "whole",
                body_bytes=line["body_bytes"],
                total_input=tokens,
                counters_absent=absent,
            )
        )
    return kept, unknown


def extensions(
    sends: list[Measured], bodies: dict[str, dict[str, Any]]
) -> list[tuple[Measured, Measured, int]]:
    """Pairs where a later request's messages extend an earlier one's, everything else in the
    two bodies equal; with the bytes of the appended messages as compact JSON.

    Each later request is paired with the longest earlier request it extends, so a three-call
    exchange gives two pairs and not three.
    """
    pairs: list[tuple[Measured, Measured, int]] = []
    for index, later in enumerate(sends):
        after = bodies[later.send]
        longest: Measured | None = None
        for earlier in sends[:index]:
            if (earlier.execution, earlier.family) != (later.execution, later.family):
                continue
            before = bodies[earlier.send]
            rest_equal = all(
                before.get(key) == after.get(key)
                for key in (before.keys() | after.keys()) - {"messages"}
            )
            held = before.get("messages", [])
            grown = after.get("messages", [])
            if not rest_equal or len(held) >= len(grown) or grown[: len(held)] != held:
                continue
            if longest is None or len(held) > len(bodies[longest.send]["messages"]):
                longest = earlier
        if longest is not None:
            appended = after["messages"][len(bodies[longest.send]["messages"]) :]
            size = len(json.dumps(appended, ensure_ascii=False, separators=(",", ":")).encode())
            pairs.append((longest, later, size))
    return pairs


def main() -> None:
    named = os.environ.get(CAPTURES_VARIABLE, "").strip()
    if not named:
        raise SystemExit(f"{CAPTURES_VARIABLE} names the private capture directory; it is unset")
    root = Path(named)
    raw = (root / "sends.jsonl").read_bytes()
    record = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    sends, unknown = measured_sends(record)
    print(f"record sha256 {hashlib.sha256(raw).hexdigest()}")
    print(f"{len(sends)} sends reported usage; {unknown} did not and are left out")
    print(f"{sum(s.counters_absent > 0 for s in sends)} of them lacked an input-side counter\n")

    groups: dict[tuple[str, str], list[Measured]] = defaultdict(list)
    for send in sends:
        groups[(send.family, send.mode)].append(send)
    print(
        "family mode      sends  bytes min..max      input min..max   "
        "bytes/token min  median     max  under"
    )
    for (family, mode), members in sorted(groups.items()):
        ratios = [m.bytes_per_token for m in members]
        sizes = [m.body_bytes for m in members]
        inputs = [m.total_input for m in members]
        under = sum(m.body_bytes < m.total_input for m in members)
        print(
            f"{family:<6} {mode:<9} {len(members):>5}  {min(sizes):>6}..{max(sizes):<6}  "
            f"{min(inputs):>6}..{max(inputs):<6}  {min(ratios):>14.2f}  "
            f"{statistics.median(ratios):>6.2f}  {max(ratios):>6.2f}  {under:>5}"
        )

    print("\nthe ten sends with the fewest bytes a token")
    print("family mode      bytes   input  bytes/token  send")
    for send in sorted(sends, key=lambda s: s.bytes_per_token)[:10]:
        print(
            f"{send.family:<6} {send.mode:<9} {send.body_bytes:>5}  {send.total_input:>6}  "
            f"{send.bytes_per_token:>11.2f}  {send.send}"
        )

    bodies = {
        s.send: json.loads((root / s.execution / f"{s.send}.request.json").read_bytes())
        for s in sends
    }
    pairs = extensions(sends, bodies)
    print(f"\n{len(pairs)} requests extend an earlier request's messages")
    print(
        "family  earlier input  later input  input grew  bytes appended  "
        "bytes/token grown  later send"
    )
    for earlier, later, size in pairs:
        grew = later.total_input - earlier.total_input
        ratio = f"{size / grew:>17.2f}" if grew > 0 else f"{'n/a':>17}"
        print(
            f"{later.family:<6}  {earlier.total_input:>13}  {later.total_input:>11}  {grew:>10}  "
            f"{size:>14}  {ratio}  {later.send}"
        )


if __name__ == "__main__":
    main()
