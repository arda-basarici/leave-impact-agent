"""One process of the crash check: it opens a segment on a run attempt, drives the attempt to
its end, and dies at a seam if the injector told it to.

The parent starts this script once per segment, in a schema it names, with the world it
prepared once: the run's context, the script's turns and the in-memory systems, serialized
to a file whose digest the child verifies before using it, so every child of an execution
runs the same world. The injector's record and the kill target arrive in the environment
(``seams``). The run goes through the seamed saver and the counted ports.

On a normal exit it prints one JSON line: the steps the driver took, the appends that
repeated a held event, and its segment number. A child killed at its target prints nothing
and exits with the injector's code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
from pathlib import Path

from eventlog import RUN_STARTED, EventLog, connect
from graph import Harness, build, saver_on
from recovery import drive
from run_uninterrupted import ATTEMPT, RUN_ID, THREAD, provenance
from scripted import ScriptedChatModel, reported_usage
from seamed import SeamedSaver, counted

from leaveimpact.core.run_export_json import (
    _encode_context,  # pyright: ignore[reportPrivateUsage]
)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--schema", required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--world-sha256", required=True)
    parser.add_argument("--count-file", required=True)
    arguments = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")

    serialized = arguments.world.read_bytes()
    if hashlib.sha256(serialized).hexdigest() != arguments.world_sha256:
        raise SystemExit(f"{arguments.world} is not the world this execution prepared")
    # The file is this execution's own, written by the parent and verified above.
    world = pickle.loads(serialized)  # noqa: S301

    log = EventLog.open(connect(url, arguments.schema, arguments.application), RUN_ID, ATTEMPT)
    if log.find(RUN_STARTED, "1") is None:
        revision = log.events()[0].data
        log.append(
            RUN_STARTED,
            "1",
            {
                "run_id": RUN_ID,
                "attempt": ATTEMPT,
                "context": _encode_context(world["context"]),
                "provenance": provenance(revision["commit"]),
            },
        )
    saver = saver_on(url, arguments.schema, SeamedSaver, arguments.application)
    model = ScriptedChatModel(turns=world["turns"], count_file=arguments.count_file)
    ports = counted(world["systems"].ports)
    graph = build(Harness(log, ports, model, world["context"], reported_usage), saver)
    taken = drive(graph, log, saver, THREAD)
    print(json.dumps({"taken": taken, "held_again": log.held_again, "segment": log.segment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
