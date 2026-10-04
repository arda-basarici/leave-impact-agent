"""The persistence half's first gate: one uninterrupted scripted run, its export built from the
event log with the checkpoint tables dropped, round-tripped through the package's codec.

The criterion is the ``export from the log`` row of the committed acceptance section in
``probes/README.md``. What runs: one scenario of the throwaway world over the in-memory
ports, the scripted model, real PostgreSQL in a schema of this execution's own. The graph
runs to the approval interrupt, the approval is delivered (its event appended, then the
resume), the graph runs to its end. Then both connections are closed, every table of the
schema except the event log is dropped, and a new connection reads the events, builds the
export, encodes it, decodes the bytes and compares.

The export is built by the codec's decoder, so the round trip alone is a property of the
codec. What the export holds is therefore also compared with expectations that do not come
from the log: the prefetch's operations with the rules-only baseline's own run of the same
scenario, the model-origin reads with the outcomes the script must produce, the claims with
the script's final ones, the model requests with the scripted model's count file, the
duration with a clock bracket taken around the run.

The script: turn 1 asks for two reads, turn 2 carries one claim beside one read, turn 3
carries the final claims. The claims are the rules-only baseline's report for the scenario,
through the claims codec: real claims at no cost, and nothing about them is a result. Turn 2
carries the report's first claim and turn 3 the rest, so a claim of turn 2 reaching the
export would show. The scenario is the first in id order whose baseline run completes with
at least two claims.

The provenance the ``run_started`` event carries is the spike's own and says so in its
values: a scripted model, a placeholder pricing basis with zero rates and no call priced,
placeholder caps, the harness commit standing in for a preregistration commit. Only the
prefetch rule and the tool surface digest are the package's real ones.

Run with ``DATABASE_URL`` naming the local database::

    uv run --group harness python probes/langgraph-spike/run_uninterrupted.py

It prints one JSON summary and exits non-zero unless every check holds. ``--keep`` leaves the
schema in place; ``--out DIR`` also writes the summary and the export's bytes there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psycopg
from eventlog import RUN_STARTED, TABLE, EventLog, connect, digest_of, read_events
from graph import (
    DURABILITY,
    Harness,
    build,
    deliver_approval,
    retry_policies,
    run_to_interrupt,
    saver_on,
)
from log_export import export_from_log, unstated_by_format_1
from psycopg.sql import SQL, Identifier
from replay import ROLE, SYSTEM
from scripted import (
    MODEL_ID,
    ScriptedChatModel,
    ToolCall,
    Turn,
    reported_usage,
    requests_counted,
)

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    # The throwaway world and the in-memory ports are the tests' fixtures; the repository
    # root makes `tests` importable from this folder.
    sys.path.insert(0, str(REPOSITORY))

from leaveimpact.agent.rules_only import RulesOnlyRun, investigate  # noqa: E402
from leaveimpact.core.claims import Claim  # noqa: E402
from leaveimpact.core.claims_json import encode_claims  # noqa: E402
from leaveimpact.core.entities import Leave  # noqa: E402
from leaveimpact.core.prefetch import prefetch_rule  # noqa: E402
from leaveimpact.core.pricing import encode_rate  # noqa: E402
from leaveimpact.core.provenance import (  # noqa: E402
    ModelConfiguration,
    encode_model_configuration,
)
from leaveimpact.core.run_export_json import (  # noqa: E402
    _encode_context,  # pyright: ignore[reportPrivateUsage]
    _encode_operation,  # pyright: ignore[reportPrivateUsage]
    decode_export_bytes,
    export_bytes,
)
from leaveimpact.core.run_record import PricingRow  # noqa: E402
from leaveimpact.core.run_trace import Operation, RecordOutcome  # noqa: E402
from leaveimpact.core.tools import TOOL_SPECIFICATIONS, tool_surface_digest  # noqa: E402
from leaveimpact.core.worldtime import RunContext  # noqa: E402
from tests.unit.reads_fixture import systems_holding  # noqa: E402
from tests.unit.throwaway_world import loaded_world  # noqa: E402

RUN_ID = "spike-run"
ATTEMPT = 1
THREAD = f"{RUN_ID}/{ATTEMPT}"
PINNED = (
    "langgraph",
    "langgraph-checkpoint-postgres",
    "langchain-aws",
    "langchain-core",
    "botocore",
    "psycopg",
)
PLACEHOLDER = "spike-placeholder"
MODEL_READS = (
    ("mc-1-t1", "employee", "record"),
    ("mc-1-t2", "work_items", "records"),
    ("mc-2-t1", "components", "records"),
)
"""The reads the script's tool calls must produce: position, tool, outcome kind."""


def scenario_and_baseline() -> tuple[RunContext, RulesOnlyRun, str, Any]:
    """The run context of the first scenario whose rules-only run completes with at least two
    claims, that run, the leaver's employee id as the run's opening read returned it, and the
    loaded world."""
    world = loaded_world()
    for scenario in sorted(world.scenarios, key=lambda scenario: scenario.spec.id):
        spec = scenario.spec
        context = RunContext(
            spec.id, world.version, spec.leave_id, spec.now, spec.reference_timezone
        )
        run = investigate(context, systems_holding(world).ports)
        opening = run.operations[0].outcome
        if len(run.claims) < 2 or not isinstance(opening, RecordOutcome):
            continue
        leave = opening.record.value
        if isinstance(leave, Leave):
            return context, run, leave.employee_id, world
    raise SystemExit("no scenario of the throwaway world gives two claims under rules only")


def script(claims: tuple[Claim, ...], leaver: str) -> tuple[Turn, ...]:
    """The three turns: two reads; the first claim beside one read; the remaining claims."""
    return (
        Turn("", (ToolCall("employee", {"id": leaver}), ToolCall("work_items", {})), 1200, 40, 11),
        Turn(encode_claims(claims[:1]), (ToolCall("components", {}),), 2400, 90, 12),
        Turn(encode_claims(claims[1:]), (), 2600, 300, 13),
    )


def provenance(commit: str) -> dict[str, Any]:
    """The provenance block of ``run_started``, in the shapes the export codec reads."""
    rule = prefetch_rule()
    rates = [
        encode_rate(PricingRow(PLACEHOLDER, "none", "none", token_class, 0))
        for token_class in ("input_tokens", "output_tokens")
    ]
    configuration = encode_model_configuration(ModelConfiguration(MODEL_ID, ()))
    return {
        "outage": {
            "scheduled_unreachable": [],
            "schedule_digest": digest_of("the spike schedules no outage"),
        },
        "preregistration_commit": commit,
        "model_configurations": [{"role": ROLE, "configuration": configuration}],
        "pricing_selections": [
            {"role": ROLE, "pricing_key": PLACEHOLDER, "region": "none", "billing_mode": "none"}
        ],
        "prompt_digests": [{"role": ROLE, "name": "system", "digest": digest_of(SYSTEM)}],
        "tool_surface_digests": [
            {"role": ROLE, "digest": tool_surface_digest(TOOL_SPECIFICATIONS)}
        ],
        "system": {"kind": "agent", "variant": "langgraph-spike"},
        "retrieval": {"kind": "full_text", "embedding_model": None},
        "prefetch_rule": {"identifier": rule.identifier, "digest": rule.digest},
        "caps": {
            "call_cap": 8,
            "token_cap": 100_000,
            "finalization_call_reserve": 1,
            "finalization_token_reserve": 5_000,
            "counting_rule": PLACEHOLDER,
        },
        "pricing": {
            "table_digest": digest_of("the spike prices nothing"),
            "currency": "USD",
            "effective_from": date(2026, 10, 4).isoformat(),
            "rows": rates,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--keep", action="store_true", help="leave the execution's schema")
    parser.add_argument("--out", type=Path, help="also write the summary and the export here")
    arguments = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")

    execution = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    schema = "spike_" + execution.lower().replace("-", "_")
    context, baseline, leaver, world = scenario_and_baseline()
    claims = baseline.claims
    count_file = str(Path(tempfile.mkdtemp(prefix="spike-")) / "model-requests.jsonl")

    admin = psycopg.connect(url, autocommit=True)
    admin.execute(SQL("CREATE SCHEMA {}").format(Identifier(schema)))
    try:
        bracket_start = time.monotonic_ns()
        log = EventLog.open(connect(url, schema), RUN_ID, ATTEMPT)
        revision = log.events()[0].data
        log.append(
            RUN_STARTED,
            "1",
            {
                "run_id": RUN_ID,
                "attempt": ATTEMPT,
                "context": _encode_context(context),
                "provenance": provenance(revision["commit"]),
            },
        )
        saver = saver_on(url, schema)
        model = ScriptedChatModel(turns=script(claims, leaver), count_file=count_file)
        ports = systems_holding(world).ports
        graph = build(Harness(log, ports, model, context, reported_usage), saver)
        policies = retry_policies(graph)

        paused = run_to_interrupt(graph, THREAD)
        kinds_at_interrupt = [event.kind for event in log.events()]
        deliver_approval(graph, log, THREAD)
        bracket_ms = (time.monotonic_ns() - bracket_start) // 1_000_000
        events_at_completion = len(log.events())
        try:
            deliver_approval(graph, log, THREAD)
            second_delivery = "accepted"
        except RuntimeError:
            second_delivery = "refused"
        events_after_second_delivery = len(log.events())
        held_again = list(log.held_again)

        tables = _tables(admin, schema)
        checkpoint_rows = {table: _count(admin, schema, table) for table in tables}
        saver.conn.close()
        log.connection.close()
        for table in tables:
            admin.execute(SQL("DROP TABLE {}").format(Identifier(schema, table)))
        remaining = _tables(admin, schema, keep=())

        reader = connect(url, schema)
        events = read_events(reader, RUN_ID, ATTEMPT)
        reader.close()
        export = export_from_log(events)
        raw = export_bytes(export)
        decoded = decode_export_bytes(raw)
    finally:
        if not arguments.keep:
            admin.execute(SQL("DROP SCHEMA {} CASCADE").format(Identifier(schema)))
        admin.close()

    requests = requests_counted(count_file)
    unstated = unstated_by_format_1(events)
    operations = export.trace.operations
    prefetched = [operation for operation in operations if operation.id.startswith("pf-")]
    model_reads = tuple(
        (operation.id, operation.tool, _encode_operation(operation)["outcome"]["kind"])  # type: ignore[index]
        for operation in operations
        if not operation.id.startswith("pf-")
    )
    exported_ids = {claim.claim_id for claim in export.trace.claims}
    duration_ms = export.record.usage.duration_ms
    checks = {
        "the graph stopped at the approval interrupt": "__interrupt__" in paused,
        "no approval or terminal event before the approval was delivered": not (
            {"approval", "run_terminal"} & set(kinds_at_interrupt)
        ),
        "a second delivery after completion is refused and appends nothing": second_delivery
        == "refused"
        and events_after_second_delivery == events_at_completion,
        "no append of the run repeated an event the log already held": held_again == [],
        "the compiled graph holds no retry policy": not any(policies.values()),
        "the saver wrote checkpoints before they were dropped": checkpoint_rows.get(
            "checkpoints", 0
        )
        > 0,
        "only the event log remained when the export was built": remaining == [TABLE],
        "the decoded export equals the built one": decoded == export,
        "the decoded export re-encodes to the same bytes": export_bytes(decoded) == raw,
        "the prefetch's operations are the rules-only baseline's": _unidentified(prefetched)
        == _unidentified(baseline.operations),
        "the model's reads are the script's, each answered by its source": model_reads
        == MODEL_READS,
        "three model calls, each requested once": requests == [1, 2, 3]
        and [call.id for call in export.trace.model_calls] == ["mc-1", "mc-2", "mc-3"]
        and [intent["dispatch_attempt"] for intent in unstated.intents] == [1, 1, 1],
        "the export's claims are the script's final claims": export.trace.claims
        == tuple(sorted(claims[1:], key=lambda claim: claim.claim_id)),
        "turn 2's claim is recorded and not exported": unstated.claims_beside_tool_calls
        == ("mc-2",)
        and claims[0].claim_id not in exported_ids,
        "the duration is positive and inside the clock bracket around the run": 0
        < duration_ms
        <= bracket_ms,
    }
    summary: dict[str, Any] = {
        "probe": "export from the log",
        "verdict": "pass" if all(checks.values()) else "fail",
        "execution": execution,
        "harness": revision,
        "versions": {name: version(name) for name in PINNED},
        "configuration": {
            "saver": "PostgresSaver, own autocommit connection",
            "durability": DURABILITY,
            "retry_policies_read_from_the_compiled_graph": policies,
        },
        "scenario": context.scenario_id,
        "checks": checks,
        "events": _counted(event.kind for event in events),
        "operations": {"prefetch": len(prefetched), "model": len(model_reads)},
        "model_reads": [list(read) for read in model_reads],
        "model_calls": [
            {"id": call.id, "outcome": call.outcome.value} for call in export.trace.model_calls
        ],
        "claims": {"exported": len(export.trace.claims), "baseline": len(claims)},
        "model_requests_counted": requests,
        "appends_that_repeated_a_held_event": held_again,
        "checkpoint_rows_before_drop": checkpoint_rows,
        "tables_dropped": tables,
        "duration_ms": duration_ms,
        "clock_bracket_ms": bracket_ms,
        "export": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        "unstated_by_format_1": asdict(unstated),
    }
    rendered = json.dumps(summary, indent=2, ensure_ascii=False)
    print(rendered)
    if arguments.out is not None:
        arguments.out.mkdir(parents=True, exist_ok=True)
        (arguments.out / f"{execution}-summary.json").write_text(rendered, encoding="utf-8")
        (arguments.out / f"{execution}-export.json").write_bytes(raw)
    return 0 if summary["verdict"] == "pass" else 1


def _unidentified(operations: Any) -> list[dict[str, Any]]:
    """``operations`` as the codec writes them, without their ids: the baseline numbers its
    operations its own way, and what is compared is what was asked and what came back."""
    encoded: list[dict[str, Any]] = []
    for operation in operations:
        assert isinstance(operation, Operation)
        written = dict(_encode_operation(operation))
        del written["id"]
        encoded.append(written)
    return encoded


def _count(admin: psycopg.Connection[Any], schema: str, table: str) -> int:
    row = admin.execute(SQL("SELECT count(*) FROM {}").format(Identifier(schema, table))).fetchone()
    return 0 if row is None else row[0]


def _tables(
    admin: psycopg.Connection[Any], schema: str, keep: tuple[str, ...] = (TABLE,)
) -> list[str]:
    rows = admin.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename", (schema,)
    ).fetchall()
    return [row[0] for row in rows if row[0] not in keep]


def _counted(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
