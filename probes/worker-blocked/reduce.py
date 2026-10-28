"""The blocked-work probe's capture read into its findings table: one row per case and
mode from `runs.jsonl`, the criteria's measurements beside each other (when the block
was seen, how long the exit or the wall took, whether the next closure followed, what the
child left and what the replacement did), and the threads the child reported at its exit,
since an executor thread left waiting is what would hold the interpreter's exit.

    python probes/worker-blocked/reduce.py probes/captures/worker-blocked/<date>/runs.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

COLUMNS = (
    "case",
    "mode",
    "blocked after (s)",
    "exit code",
    "exit after signal (s)",
    "within grace",
    "wall after start (s)",
    "next closure seen",
    "ready again (s)",
    "child left",
    "replacement",
    "threads left",
)


def records_of(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _left(summary: dict[str, Any]) -> str:
    closed = summary.get("closed")
    segment = "open" if summary.get("segment_open") else "ended"
    flight = len(summary.get("in_flight") or ())
    state = f"closed {summary.get('closing_reason')}" if closed else f"open, segment {segment}"
    return f"{state}, {flight} in flight, {summary.get('positions')} events"


def _replacement(record: dict[str, Any]) -> str:
    after: dict[str, Any] = record.get("after_tick") or {}
    closed: Any = after.get("closed")
    settlement: dict[str, Any] = after.get("settlement") or {}
    kept: Any = settlement.get("kept_reason")
    calls: list[Any] = record.get("replacement_work_calls") or []
    objects: list[Any] = record.get("objects_published") or []
    published = len(objects)
    parts = [
        f"closed {after.get('closing_reason')}" if closed else "left open",
        f"settlement {settlement.get('state')}" + (f" ({kept})" if kept else "")
        if settlement
        else "no settlement",
        f"{len(calls)} work call(s)",
        f"{published} object(s) published",
    ]
    return "; ".join(parts)


def _threads(record: dict[str, Any]) -> str:
    for line in reversed(record.get("child_lines") or []):
        if "threads left:" in line:
            return line.split("threads left:", 1)[1].strip()
    return "(no exit line)"


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def rows_of(records: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for record in records:
        rows.append(
            (
                record["case"],
                record["mode"],
                _cell(record.get("blocked_after_s")),
                _cell(record.get("exit_code")),
                _cell(record.get("exit_after_s")),
                _cell(record.get("exited_within_grace")),
                _cell(record.get("wall_after_s")),
                _cell(record.get("next_closure_seen")),
                _cell(record.get("ready_again_after_s")),
                _left(record.get("after_child") or {}),
                _replacement(record),
                _threads(record),
            )
        )
    return rows


def table_of(records: list[dict[str, Any]]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows_of(records))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(table_of(records_of(Path(argv[1]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
