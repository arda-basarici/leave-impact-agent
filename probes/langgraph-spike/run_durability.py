"""The crash check's first question: does a row the saver wrote survive the process being
killed the moment the write returned?

The saver has no commit of its own; on the pipeline branch its writes are committed because
its connection is autocommit (the pinned source read, group A). The whole crash matrix stands
on that, so it is asked first and on its own: one child is killed right after the first
``put`` returns and one right after the first ``put_writes`` returns, and the parent, once the
child's sessions have ended, reads the checkpoint store for exactly what that call wrote.

What runs: a discovery child with no kill target, which must complete and gives the crossing
list; then one kill child per target, each in a schema of its own. A row passes when the
child exited with the injector's code at exactly its target and the store holds the write:
for ``put``, a checkpoint with the target's step; for ``put_writes``, a pending write of the
result positions, or the control channel, the target names.

    uv run --group harness python probes/langgraph-spike/run_durability.py

It prints one JSON summary and exits non-zero unless both rows pass.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psycopg
from eventlog import harness_revision
from parent import (
    checkpointed,
    create_schema,
    drop_schema,
    prepare_world,
    sessions_ended,
    start_child,
)
from run_uninterrupted import PINNED
from seamed import written
from seams import parts


def first_with(crossings: list[str], phase: str) -> str:
    """The first crossing whose phase is ``phase``."""
    for crossing in crossings:
        if parts(crossing)[1] == phase:
            return crossing
    raise SystemExit(f"the discovery run crossed no {phase} seam")


def holds(store: list[dict[str, Any]], target: str) -> bool:
    """Whether the checkpoint store holds what the call ``target`` names wrote."""
    kind, _, name = parts(target)[0].partition("/")
    if kind == "checkpoint":
        return any(f"step={checkpoint['step']}" == name for checkpoint in store)
    return any(written(task) == name for checkpoint in store for task in checkpoint["pending"])


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    execution = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    prefix = "spike_" + execution.lower().replace("-", "_")
    directory = Path(tempfile.mkdtemp(prefix="spike-durability-"))
    world = prepare_world(directory)
    admin = psycopg.connect(url, autocommit=True)
    schemas: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        discovery = f"{prefix}_d"
        schemas.append(discovery)
        create_schema(admin, discovery)
        found = start_child(
            discovery, world, directory / "discovery.jsonl", directory / "discovery-count.jsonl"
        )
        if found.code != 0:
            print(found.stderr, file=sys.stderr)
            raise SystemExit(f"the discovery child exited {found.code}")
        crossings = found.crossings()
        for index, phase in enumerate(("put:after", "put_writes:after")):
            target = first_with(crossings, phase)
            schema = f"{prefix}_k{index}"
            schemas.append(schema)
            create_schema(admin, schema)
            ended = start_child(
                schema,
                world,
                directory / f"kill-{index}.jsonl",
                directory / f"kill-{index}-count.jsonl",
                kill_at=target,
            )
            died = ended.died_at(target)
            quiet = sessions_ended(admin, schema)
            store = checkpointed(url, schema) if died and quiet else []
            rows.append(
                {
                    "target": target,
                    "exit_code": ended.code,
                    "died_at_target": died,
                    "sessions_ended_before_the_read": quiet,
                    "checkpoints_held": [checkpoint["step"] for checkpoint in store],
                    "pending_writes_held": sorted(
                        {written(task) for checkpoint in store for task in checkpoint["pending"]}
                    ),
                    "the_write_survived": holds(store, target),
                    "verdict": "pass" if died and quiet and holds(store, target) else "fail",
                    "stderr": "" if died else ended.stderr,
                }
            )
    finally:
        for schema in schemas:
            drop_schema(admin, schema)
        admin.close()
    summary = {
        "probe": "saver durability under a kill",
        "verdict": "pass" if all(row["verdict"] == "pass" for row in rows) else "fail",
        "execution": execution,
        "harness": harness_revision(),
        "versions": {name: version(name) for name in PINNED},
        "world_sha256": world.sha256,
        "discovery": {
            "crossings": len(crossings),
            "steps": found.report["taken"] if found.report else None,
            "list": crossings,
        },
        "rows": rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
