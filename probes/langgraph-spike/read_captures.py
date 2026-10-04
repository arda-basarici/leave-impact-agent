"""The numbers the spike's findings cite, read back from the private captures.

The captures stay outside the repository, so a findings entry cannot point at them. What it
can do is cite numbers that anyone holding the captures regenerates with this file: the send
and outcome counts, the usage fields each family returned streamed and not, the state of the
cache counters call by call, the known usage per family beside the sends whose usage is
unknown, and a digest per execution that says which captures were read.

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> python probes/langgraph-spike/read_captures.py

It reads the record and the capture files and nothing else: no client, no send. Sends an
offline execution answered itself never reached a provider; they are counted once, at the
top, and left out of every table.

Absent is kept apart from zero throughout. A counter a response did not carry is not summed
as zero: each sum is printed with the number of sends that reported that counter.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from capture import USAGE_COUNTERS, capture_root

Line = dict[str, Any]


def family_of(send: Line) -> str:
    """The model family a send addressed, from the profile in its URL."""
    model = send["requested_model"]
    if "anthropic" in model:
        return "haiku"
    return "nova" if "nova" in model else f"other ({model})"


def mode_of(send: Line) -> str:
    return "streamed" if send["operation"] == "ConverseStream" else "whole"


def execution_digest(folder: Path, record_lines: list[str]) -> str:
    """SHA-256 over everything an execution's numbers are read from: its lines of the shared
    record, then each capture file's name and content digest in name order.

    The record's lines are covered because the usage, the counter states and the outcomes are
    read from them, not from the files. The findings rows written beside the captures are
    left out, since they are derived. Every part is length-prefixed, so no two different
    sets of parts share a digest by concatenation.
    """
    whole = hashlib.sha256()

    def take(part: bytes) -> None:
        whole.update(len(part).to_bytes(8, "big"))
        whole.update(part)

    for line in record_lines:
        take(line.encode("utf-8"))
    files = sorted(folder.iterdir()) if folder.is_dir() else []
    for file in files:
        if file.name == "findings.jsonl":
            continue
        take(file.name.encode("utf-8"))
        take(hashlib.sha256(file.read_bytes()).digest())
    return whole.hexdigest()


def usage_fields(sends: dict[str, Line], outcomes: dict[str, Line]) -> dict[str, list[str]]:
    """Every usage field name seen, per family and per mode (``whole`` or ``streamed``)."""
    seen: dict[str, set[str]] = defaultdict(set)
    for identifier, outcome in outcomes.items():
        if isinstance(outcome["usage"], dict):
            send = sends[identifier]
            seen[f"{family_of(send)} {mode_of(send)}"] |= set(outcome["usage"])
    return {key: sorted(names) for key, names in sorted(seen.items())}


def counter_table(sends: dict[str, Line], outcomes: dict[str, Line]) -> Counter[tuple[str, ...]]:
    """How often each (family, mode, cache-read state, cache-write state) occurred among the
    sends that returned usage."""
    table: Counter[tuple[str, ...]] = Counter()
    for identifier, outcome in outcomes.items():
        if not isinstance(outcome["usage"], dict):
            continue
        send = sends[identifier]
        states = outcome["counters"]
        key = (
            family_of(send),
            mode_of(send),
            states["cacheReadInputTokens"],
            states["cacheWriteInputTokens"],
        )
        table[key] += 1
    return table


def known_usage(sends: dict[str, Line], outcomes: dict[str, Line]) -> dict[str, dict[str, Any]]:
    """Per family: how many sends returned usage and how many returned none, and each counter
    as ``(sum, sends that reported it)``. A counter no send reported has no entry, and a sum
    beside ``sends_usage_unknown`` above zero is not a total."""
    sums: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for identifier, send in sends.items():
        family = family_of(send)
        outcome = outcomes.get(identifier)
        usage = outcome["usage"] if outcome else None
        if not isinstance(usage, dict):
            counts[family]["sends_usage_unknown"] += 1
            continue
        counts[family]["sends_with_usage"] += 1
        for name in USAGE_COUNTERS:
            if name in usage:
                sums[family][name][0] += int(usage[name])
                sums[family][name][1] += 1
    return {
        family: dict(counts[family])
        | {name: (pair[0], pair[1]) for name, pair in sums[family].items()}
        for family in sorted(counts)
    }


def main() -> int:
    root = capture_root()
    with (root / "sends.jsonl").open(encoding="utf-8") as record:
        raw = [line.rstrip("\n") for line in record if line.strip()]
    lines: list[Line] = [json.loads(line) for line in raw]
    every = {line["send"]: line for line in lines if line["event"] == "send"}
    sends = {identifier: send for identifier, send in every.items() if not send.get("offline")}
    outcomes = {
        line["send"]: line for line in lines if line["event"] == "outcome" and line["send"] in sends
    }
    print(f"offline sends left out: {len(every) - len(sends)}")

    print("executions")
    for execution in sorted({send["execution"] for send in sends.values()}):
        count = sum(1 for send in sends.values() if send["execution"] == execution)
        own = [
            text
            for text, line in zip(raw, lines, strict=True)
            if every.get(line["send"], {}).get("execution") == execution
        ]
        print(f"  {execution}  sends {count:3}  digest {execution_digest(root / execution, own)}")

    print(f"sends {len(sends)}")
    kinds = Counter(outcome["outcome"] for outcome in outcomes.values())
    kinds["unresolved"] = len(sends) - len(outcomes)
    for kind, count in sorted(kinds.items()):
        print(f"  {kind:15} {count}")
    print("  by family      ", dict(sorted(Counter(map(family_of, sends.values())).items())))
    invocations = Counter(send["invocation"] for send in sends.values())
    retried = sum(1 for n in invocations.values() if n > 1)
    print(f"  invocations with a send {len(invocations)}, with more than one send {retried}")

    print("usage fields seen")
    for key, names in usage_fields(sends, outcomes).items():
        print(f"  {key:15} {', '.join(names)}")

    print("cache counter states (family, mode, read, write): sends")
    for key, count in sorted(counter_table(sends, outcomes).items()):
        print(f"  {' '.join(f'{part:8}' for part in key)} {count}")

    print("caching, call by call (a counter the response did not carry is shown as absent)")
    for identifier, send in sends.items():
        if send["probe"] != "caching":
            continue
        outcome = outcomes.get(identifier)
        usage = outcome["usage"] if outcome else None
        label = f"{send['execution'][-6:]} {send['label']}"
        if not isinstance(usage, dict):
            print(f"  {label:26} no usage ({outcome['outcome'] if outcome else 'unresolved'})")
            continue
        parts = {name: usage.get(name, "absent") for name in USAGE_COUNTERS}
        reported = sum(value for value in parts.values() if isinstance(value, int))
        print(f"  {label:26} {parts}  total {usage.get('totalTokens')} sum of reported {reported}")

    print("one request streamed and whole, per execution: input tokens")
    pairs: dict[str, dict[str, Any]] = defaultdict(dict)
    for identifier, send in sends.items():
        if send["probe"] != "forced-choice":
            continue
        family, choice, mode = send["label"].split()
        outcome = outcomes.get(identifier)
        usage = outcome["usage"] if outcome else None
        tokens = usage.get("inputTokens", "absent") if isinstance(usage, dict) else "no usage"
        pairs[f"{send['execution'][-6:]} {family} {choice}"][mode] = tokens
    for key, modes in sorted(pairs.items()):
        print(f"  {key:22} {modes}")

    print("known usage per family: counter (sum, sends that reported it)")
    for family, values in known_usage(sends, outcomes).items():
        print(f"  {family:6} {values}")

    print("response header names seen (outcomes that kept them)")
    header_names: Counter[str] = Counter()
    kept = 0
    for outcome in outcomes.values():
        if "response_headers" in outcome:
            kept += 1
            header_names.update(list(outcome["response_headers"]))
    print(f"  outcomes with headers {kept}: {dict(sorted(header_names.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
