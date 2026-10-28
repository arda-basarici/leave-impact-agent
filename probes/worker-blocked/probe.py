"""The blocked-work probe of the worker service (the demo milestone's worker step; the
criteria in `probes/README.md`): does the loop stop blocked work at the wall and under the
stop signal, teardown included, under four ways a call can block? First run over the
in-process shape (the 2026-10-27 capture, which ruled the supervised child); rerun over the
service supervising the work in a child process it terminates, waits on, kills and reaps
(the 2026-10-28 capture).

The parent prepares the throwaway world once (the crash matrix's preparation), and per
case a scratch schema with the log's and the app's tables, the threshold, one public
attempt admitted as the demo's start admits it (the demo's admitter, the demo's ledger, a
live row) and the case's block applied from outside the child: a model client whose send
waits on an event never set; the saver's tables locked by another session so the first
checkpoint write waits; a local socket that accepts and never answers, behind the real SDK
client by endpoint URL, so botocore's own read blocks; the log's attempt table locked by
another session so the claim waits, or locked after the block so the segment's end waits.
The service process (`run`) runs the service's loop (`leaveimpact.app.worker.serve`) with
the real stop handlers and the real spawn, its child command this file's `work`
subcommand, which runs the real `Worker` composed as the crash harness composes it (the
scripted turns, the planted ports, the real saver) once, over the case's client, and
prints its ending as the one stdout line; the wall at fifteen seconds (the first rerun's
five met the signal at the wall, since the wall counts the work process's startup), the
terminate grace the service's ten. Every announcement of the service and the work goes to
stderr, which both inherit from the parent's pipe. Mode `term`: once the block is seen (the client's
line, or the session waiting on a lock in `pg_stat_activity`, or three seconds after the
work process's readiness line for the socket), SIGTERM to the service, its exit measured.
Mode `wall`: the wall's line waited for, then the supervisor's own closure of the lost
attempt, the readiness to claim again measured. Then the parent runs the replacement's
start pass and a tick in its own process over a child command that prints a refused
ending, and records the staged accounting: what the drain left, what the replacement
closed, what was published; and what the work process's threads did at its exit, since an
executor thread left waiting holds the interpreter's exit.

Runs under Linux (the signals are POSIX); from this machine, under WSL's Ubuntu with the
project's environment synced there, against the dev PostgreSQL. One JSON line per run goes
to the capture directory, and `reduce.py` reads them into the findings table.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402

from leaveimpact.adapters.wiring import (  # noqa: E402
    inventory_publisher_over,
    run_export_publisher_over,
)
from leaveimpact.agent.commands import (  # noqa: E402
    WorkRequest,
    publish,
    write_inventory,
)
from leaveimpact.agent.graph import NoPreparation  # noqa: E402
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRequest, LogStore  # noqa: E402
from leaveimpact.agent.worker import (  # noqa: E402
    HumanApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.app.live import LiveDraft, key_digest_of, public_id_for  # noqa: E402
from leaveimpact.app.public import PublicationDraft  # noqa: E402
from leaveimpact.app.start import DEMO_START  # noqa: E402
from leaveimpact.app.store import STATEMENT_TIMEOUT_MS, AppStore  # noqa: E402
from leaveimpact.app.sweeper import SweepComposition, SweepLog  # noqa: E402
from leaveimpact.app.worker import (  # noqa: E402
    ServiceComposition,
    ending_line,
    install_stop_handlers,
    serve,
    service_identity,
    start_pass,
    tick,
)
from tests.crash import matrix  # noqa: E402
from tests.crash.child import application_of, saver_in  # noqa: E402
from tests.unit import format_fixtures as cases  # noqa: E402
from tests.unit import log_histories as histories  # noqa: E402
from tests.unit import worker_support as support  # noqa: E402
from tests.unit.in_memory_object_store import InMemoryObjectStore  # noqa: E402
from tests.unit.publishable_fixture import CONFIGURATION  # noqa: E402
from tests.unit.test_app_start import key  # noqa: E402

CASES = ("send", "checkpoint", "http", "claim", "append")
MODES = ("term", "wall")
WALL_SECONDS = 15
"""Under the child the wall counts the work process's startup (about three and a half
seconds of imports under WSL), so a five-second wall met the signal mode's SIGTERM at the
wall itself in the first rerun; fifteen keeps the two modes apart."""
EXIT_WAIT_SECONDS = 15
"""How long the parent waits for the service's exit after its signal: past the
supervisor's ten-second grace, so a kill path's exit is measured and not cut off."""
CHILD_APPLICATION = "probe-child"
SERVICE_APPLICATION = "probe-service"
LIVE = replace(
    CONFIGURATION, ledger_id=matrix.LEDGER, live_runs=True, attempt_wall_seconds=WALL_SECONDS
)
SCRIPT_OF = {
    "send": "two-call",
    "checkpoint": "two-call",
    "http": "stating",
    "claim": "two-call",
    "append": "two-call",
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def say(line: str) -> None:
    """To stderr: the work process's stdout is the service's pipe for the ending line."""
    print(f"probe {time.monotonic():.3f}: {line}", file=sys.stderr, flush=True)


# --- connections into the scratch schema ---------------------------------------------------


def bounded_connect(schema: str, application: str) -> Any:
    """The production worker's log connection: the app's statement bound, into the schema."""

    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            make_conninfo(
                dsn,
                options=f"-c search_path={schema} -c statement_timeout={STATEMENT_TIMEOUT_MS}",
                application_name=application,
            ),
            connect_timeout=10,
            autocommit=True,
        )

    return connect


def app_store_in(url: str, schema: str, application: str) -> AppStore:
    return AppStore(dsn=url, connect=bounded_connect(schema, application))


# --- the child -----------------------------------------------------------------------------


class BlockingClient:
    """The scripted client whose first send announces itself and waits forever."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.operation = inner.operation
        self.client_region = getattr(inner, "client_region", "eu-central-1")
        self._blocked = threading.Event()

    def send(self, requested_profile: str, body: Any) -> Any:
        say("blocked at send")
        self._blocked.wait()
        return self._inner.send(requested_profile, body)


def stalled_server() -> int:
    """A socket that accepts and never answers, on a free port; its thread is a daemon."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    held: list[socket.socket] = []

    def accept_forever() -> None:
        while True:
            conn, _ = listener.accept()
            held.append(conn)

    threading.Thread(target=accept_forever, daemon=True).start()
    return listener.getsockname()[1]


def child_work(case: str, url: str, schema: str, context: Any, systems: Any, materials: Any):
    """The work callable: the real worker as the crash harness composes it, the case's
    client in place of the scripted one."""
    script = support.SCRIPTS[SCRIPT_OF[case]]
    built: tuple[Any, Any] = script.build(materials[SCRIPT_OF[case]], context)
    turns: Any = built[0]
    client: Any = built[1]
    model_client: Any = client
    if case == "send" or case == "append":
        model_client = BlockingClient(client)
    elif case == "http":
        import boto3
        from botocore.config import Config

        from leaveimpact.adapters.inference import ConverseClient

        port = stalled_server()
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "probe")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "probe")
        runtime = boto3.client(  # pyright: ignore[reportUnknownMemberType]
            "bedrock-runtime",
            region_name="eu-central-1",
            endpoint_url=f"http://127.0.0.1:{port}",
            config=Config(
                retries={"mode": "standard", "total_max_attempts": 1},
                connect_timeout=5,
                read_timeout=600,
            ),
        )
        model_client = ConverseClient(runtime)
        say(f"stalled server on port {port}")

    # The saver prepared once, at the child's start, so a lock the parent takes on its
    # tables after the claim is announced catches the first checkpoint write, not the setup.
    # PROBE_SAVER_TIMEOUT_MS bounds its statements as the remedy under test does; absent,
    # the connection is the crash harness's, unbounded as the first build's.
    saver = (
        bounded_saver(url, schema)
        if os.environ.get("PROBE_SAVER_TIMEOUT_MS")
        else saver_in(url, schema)
    )

    def work(request: WorkRequest, log: SweepLog) -> Any:
        inputs = log.load(request.run_id, request.attempt, rules=histories.RULES).inputs
        assert inputs is not None
        say("work ready")  # the saver set up; the parent's lock lands in the pause below
        if case in ("checkpoint", "claim"):
            time.sleep(1.0)
        worker = Worker(
            log,  # type: ignore[arg-type]
            WorkerConfiguration.of(inputs),
            cases.REVISION,
            request.launch,
            histories.RULES,
            turns,
            NoPreparation(),
            model_client,
            support.ScriptedCounter(),
            script.ports(systems.ports),
            HumanApproval(),
            saver,
        )
        return worker.work(request.run_id, request.attempt, nonce=request.nonce)

    return work


def bounded_saver(url: str, schema: str) -> PostgresSaver:
    """The real saver over a connection with a statement bound, the remedy under test."""
    bound = int(os.environ["PROBE_SAVER_TIMEOUT_MS"])
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(
            url,
            options=f"-c search_path={schema} -c statement_timeout={bound}",
            application_name=application_of(schema),
        ),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = PostgresSaver(connection)
    saver.setup()
    say(f"saver statements bounded at {bound} ms")
    return saver


def run_service(args: argparse.Namespace) -> int:
    """The service process: the real loop over the scratch schema, its child command this
    file's ``work`` for the case, the stop handlers installed."""
    url = os.environ["DATABASE_URL"]
    log = LogStore(dsn=url, connect=bounded_connect(args.schema, SERVICE_APPLICATION))
    rows = app_store_in(url, args.schema, SERVICE_APPLICATION)
    objects = InMemoryObjectStore()
    exporter, inventorier = run_export_publisher_over(objects), inventory_publisher_over(objects)

    def work_command(request: WorkRequest) -> list[str]:
        return [
            sys.executable,
            str(Path(__file__).resolve()),
            "work",
            "--case",
            args.case,
            "--schema",
            args.schema,
            "--world",
            args.world,
            "--run",
            request.run_id,
            "--attempt",
            str(request.attempt),
            "--nonce",
            request.nonce,
            "--launch",
            request.launch,
        ]

    composition = ServiceComposition(
        SweepComposition(
            LIVE,
            histories.RULES,
            cases.REVISION,
            cases.COMMIT,
            lambda request: publish(request, log, exporter, rules=histories.RULES),
            lambda request: write_inventory(request, log, inventorier, rules=histories.RULES),
            lambda: uuid4().hex,
            launch=args.identity,
        ),
        work_command,
        lambda: datetime.now(UTC),
        heartbeat=None,
        interval_seconds=0.5,
        report=say,
    )
    install_stop_handlers()
    say(f"service pid {os.getpid()} case {args.case}")
    status = serve(log, rows, composition)
    others = [t.name for t in threading.enumerate() if t is not threading.main_thread()]
    say(f"serve returned {status}; service threads left: {others}")
    return status


def run_work(args: argparse.Namespace) -> int:
    """The work process the service spawns: the case's work over the pickled world, once,
    the ending printed as the one stdout line, the stop handler installed as the demo's
    child installs it; its threads at the exit announced whatever ended it."""
    with Path(args.world).open("rb") as held:
        context, systems, materials = pickle.load(held)  # noqa: S301 - the parent wrote it
    url = os.environ["DATABASE_URL"]
    log = LogStore(dsn=url, connect=bounded_connect(args.schema, CHILD_APPLICATION))
    work = child_work(args.case, url, args.schema, context, systems, materials)
    install_stop_handlers()
    say(f"work pid {os.getpid()} case {args.case}")
    request = WorkRequest(args.run, args.attempt, args.nonce, args.launch)
    try:
        ending = work(request, log)
    finally:
        others = [t.name for t in threading.enumerate() if t is not threading.main_thread()]
        say(f"work returned; threads left: {others}")
    print(ending_line(ending), flush=True)
    return 0


# --- the parent ----------------------------------------------------------------------------


def admit_public(url: str, schema: str, prepared: matrix.Prepared, script: str) -> str:
    """The attempt as the demo's start admits it: the admitter, the ledger, the live row."""
    store = matrix.threshold_set(prepared, schema)
    inputs = prepared.inputs_for(script)
    receipt = store.admit(
        AdmissionRequest(
            f"req-{uuid4().hex[:12]}", inputs, DEMO_START, matrix.LEDGER, histories.RULES
        )
    )
    assert isinstance(receipt, AdmissionReceipt), receipt
    rows = app_store_in(url, schema, "probe-parent")
    rows.ensure_schema()
    digest = key_digest_of(key(1))
    with rows.start_section() as writer:
        writer.write(
            PublicationDraft(
                public_id_for(digest),
                inputs.run_id,
                1,
                inputs.context.world_version,
                inputs.context.scenario_id,
                None,
                "demo-start",
            ),
            LiveDraft(public_id_for(digest), inputs.run_id, 1, digest, datetime.now(UTC)),
        )
    store.close()
    return inputs.run_id


def lock_tables(
    url: str,
    schema: str,
    tables: tuple[str, ...],
    mode: Literal["ACCESS EXCLUSIVE", "EXCLUSIVE"] = "ACCESS EXCLUSIVE",
) -> psycopg.Connection[Any]:
    """A session holding a lock on the tables inside an open transaction: ACCESS EXCLUSIVE
    blocks every read and write (the claim's row lock, the segment end's insert);
    EXCLUSIVE lets reads through and blocks writes, so the checkpointer's read at the
    graph's start passes and its first write waits on the executor's thread."""
    conn = psycopg.connect(make_conninfo(url, options=f"-c search_path={schema}"), autocommit=False)
    for table in tables:
        conn.execute(
            sql.SQL("LOCK TABLE {} IN {} MODE").format(sql.Identifier(table), sql.SQL(mode))
        )
    return conn


def session_waiting_on_lock(url: str, application: str) -> bool:
    with psycopg.connect(url, autocommit=True) as admin:
        row = admin.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE application_name = %s AND wait_event_type = 'Lock'",
            (application,),
        ).fetchone()
    return bool(row and row[0])


def state_summary(log: LogStore, run_id: str) -> dict[str, Any]:
    state = log.load(run_id, 1, rules=histories.RULES)
    segment = state.current_segment
    return {
        "positions": state.last_position,
        "generation": state.generation,
        "closed": None if state.closed is None else type(state.closed.event).__name__,
        "closing_reason": _reason_of(None if state.closed is None else state.closed.event),
        "segment_open": segment is not None and not segment.ended,
        "in_flight": support.in_flight(state.events),
        "account": asdict(state.account),
        "settlement": _settlement_of(None if state.closed is None else state.closed.event),
    }


def _reason_of(event: object) -> str | None:
    reason: Any = getattr(event, "reason", None)
    return None if reason is None else str(reason.value)


def _settlement_of(event: object) -> dict[str, Any] | None:
    settlement: Any = getattr(event, "settlement", None)
    return None if settlement is None else asdict(settlement)


def run_case(prepared: matrix.Prepared, case: str, mode: str, out: Path) -> dict[str, Any]:
    url = prepared.url
    schema = matrix.new_schema(url)
    record: dict[str, Any] = {"case": case, "mode": mode, "schema": schema, "started": now()}
    held: psycopg.Connection[Any] | None = None
    child: subprocess.Popen[str] | None = None
    try:
        run_id = admit_public(url, schema, prepared, SCRIPT_OF[case])
        identity = service_identity(datetime.now(UTC), uuid4().hex)
        env = {**os.environ, "DATABASE_URL": url}
        started = time.monotonic()
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "run",
                "--case",
                case,
                "--schema",
                schema,
                "--world",
                str(prepared.world_file),
                "--identity",
                identity,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        lines: list[str] = []
        seen = threading.Event()
        ready = threading.Event()
        ready_instant: list[float] = []

        def ready_at() -> float:
            return ready_instant[0] if ready_instant else float("inf")

        wall_seen = threading.Event()
        closed_seen = threading.Event()

        def pump() -> None:
            assert child is not None and child.stdout is not None
            for line in child.stdout:
                lines.append(f"{time.monotonic() - started:7.3f} {line.rstrip()}")
                if "blocked at send" in line or "claiming" in line:
                    seen.set()
                if "work ready" in line:
                    ready_instant.append(time.monotonic())
                    ready.set()
                if "the wall of" in line and "passed" in line:
                    wall_seen.set()
                if "CloseUnrecovered" in line or "FenceAndClose" in line:
                    closed_seen.set()

        threading.Thread(target=pump, daemon=True).start()
        # The block: the client's own line, the session waiting on a lock, or three seconds
        # after the claim for the socket case.
        deadline = time.monotonic() + 30 + WALL_SECONDS
        while time.monotonic() < deadline:
            if case in ("checkpoint", "claim") and held is None and ready.is_set():
                # The work process pauses a second after announcing itself ready, its
                # saver set up; the lock lands in that window: on the saver's tables in
                # EXCLUSIVE mode so the first checkpoint write waits on the executor's
                # thread, or on the attempt table so the claim's row lock waits.
                if case == "checkpoint":
                    held = lock_tables(
                        url,
                        schema,
                        ("checkpoints", "checkpoint_writes", "checkpoint_blobs"),
                        "EXCLUSIVE",
                    )
                else:
                    held = lock_tables(url, schema, ("attempt",))
            if case in ("send", "append") and any("blocked at send" in line for line in lines):
                break
            # A wait counts only once the parent's lock is held: the second rerun's
            # detection fired on a session waiting during the work process's own setup,
            # before any lock of the probe's, and the signal landed on idle work.
            if (
                case == "checkpoint"
                and held is not None
                and session_waiting_on_lock(url, application_of(schema))
            ):
                break
            if (
                case == "claim"
                and held is not None
                and session_waiting_on_lock(url, CHILD_APPLICATION)
            ):
                break
            if case == "http" and ready.is_set() and time.monotonic() - ready_at() > 3:
                break
            time.sleep(0.1)
        blocked_at = time.monotonic() - started
        record["blocked_after_s"] = round(blocked_at, 3)
        record["block_observed"] = time.monotonic() < deadline
        if case == "append":
            held = lock_tables(url, schema, ("attempt",))
        if mode == "term":
            time.sleep(0.5)
            signalled = time.monotonic()
            child.send_signal(signal.SIGTERM)
            try:
                code = child.wait(timeout=EXIT_WAIT_SECONDS)
                record["exit_code"] = code
                record["exit_after_s"] = round(time.monotonic() - signalled, 3)
                record["exited_within_grace"] = True
            except subprocess.TimeoutExpired:
                record["exited_within_grace"] = False
                child.kill()
                child.wait()
        else:
            if wall_seen.wait(timeout=WALL_SECONDS + 15):
                record["wall_after_s"] = round(time.monotonic() - started, 3)
                record["next_closure_seen"] = closed_seen.wait(timeout=EXIT_WAIT_SECONDS)
                record["ready_again_after_s"] = round(time.monotonic() - started, 3)
            else:
                record["wall_after_s"] = None
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=EXIT_WAIT_SECONDS)
                record["exited_within_grace"] = True
            except subprocess.TimeoutExpired:
                record["exited_within_grace"] = False
                child.kill()
                child.wait()
        time.sleep(0.3)
        record["child_lines"] = lines
        if held is not None:
            held.rollback()
            held.close()
            held = None
        log = LogStore(dsn=url, connect=bounded_connect(schema, "probe-parent"))
        record["after_child"] = state_summary(log, run_id)
        # The replacement: a start pass and a tick over a work that must not be called.
        objects = InMemoryObjectStore()
        exporter, inventorier = (
            run_export_publisher_over(objects),
            inventory_publisher_over(objects),
        )
        calls: list[str] = []

        def no_work(request: WorkRequest) -> list[str]:
            # An attempt the replacement finds due is recorded, never worked: its child is
            # the interpreter printing a refused ending, so the record says whether the
            # replacement would have run inference.
            calls.append(request.run_id)
            refused = WorkerEnding(
                WorkerEndingKind.CLAIM_REFUSED, request.run_id, request.attempt, None, "probe"
            )
            return [sys.executable, "-c", f"print({ending_line(refused)!r})"]

        replacement = ServiceComposition(
            SweepComposition(
                LIVE,
                histories.RULES,
                cases.REVISION,
                cases.COMMIT,
                lambda request: publish(request, log, exporter, rules=histories.RULES),
                lambda request: write_inventory(request, log, inventorier, rules=histories.RULES),
                lambda: uuid4().hex,
                launch=service_identity(datetime.now(UTC), uuid4().hex),
            ),
            no_work,
            lambda: datetime.now(UTC),
            heartbeat=None,
            report=lambda line: lines.append(f"replacement {line}"),
        )
        first = start_pass(log, app_store_in(url, schema, "probe-parent"), replacement)
        record["replacement_start_pass"] = [
            f"{type(o.action).__name__} carried={o.carried} {o.detail}" for o in first
        ]
        record["after_start_pass"] = state_summary(log, run_id)
        second = tick(log, app_store_in(url, schema, "probe-parent"), replacement)
        record["replacement_tick"] = [
            f"{type(o.action).__name__} carried={o.carried} {o.detail}" for o in second.swept
        ]
        record["after_tick"] = state_summary(log, run_id)
        third = tick(log, app_store_in(url, schema, "probe-parent"), replacement)
        record["replacement_second_tick"] = [
            f"{type(o.action).__name__} carried={o.carried} {o.detail}" for o in third.swept
        ]
        record["replacement_work_calls"] = calls
        record["objects_published"] = sorted(objects.list_keys(""))
        log.close()
    finally:
        if held is not None:
            held.rollback()
            held.close()
        if child is not None and child.poll() is None:
            child.kill()
        matrix.drop_schema(url, schema)
    record["finished"] = now()
    with (out / "runs.jsonl").open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(record) + "\n")
    return record


def run_parent(args: argparse.Namespace) -> int:
    url = os.environ["DATABASE_URL"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # The pickled world is the golden world's: it stays in a temporary directory, never
    # beside the capture, which is committed.
    prepared = matrix.prepare(url, Path(tempfile.mkdtemp(prefix="worker-blocked-")))
    cases_to_run = CASES if args.case == "all" else (args.case,)
    modes = MODES if args.mode == "all" else (args.mode,)
    for case in cases_to_run:
        for mode in modes:
            print(f"=== {case} / {mode} ===", flush=True)
            record = run_case(prepared, case, mode, out)
            for name in (
                "blocked_after_s",
                "exit_code",
                "exit_after_s",
                "exited_within_grace",
                "wall_after_s",
                "next_closure_seen",
                "ready_again_after_s",
                "replacement_work_calls",
            ):
                if name in record:
                    print(f"  {name}: {record[name]}", flush=True)
            print(f"  after child: {record['after_child']}", flush=True)
            print(f"  after tick: {record['after_tick']}", flush=True)
            for line in record["child_lines"][-6:]:
                print(f"  | {line}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    service = commands.add_parser("run")
    service.add_argument("--case", choices=CASES, required=True)
    service.add_argument("--schema", required=True)
    service.add_argument("--world", required=True)
    service.add_argument("--identity", required=True)
    work = commands.add_parser("work")
    work.add_argument("--case", choices=CASES, required=True)
    work.add_argument("--schema", required=True)
    work.add_argument("--world", required=True)
    work.add_argument("--run", required=True)
    work.add_argument("--attempt", required=True, type=int)
    work.add_argument("--nonce", required=True)
    work.add_argument("--launch", required=True)
    parent = commands.add_parser("parent")
    parent.add_argument("--out", required=True)
    parent.add_argument("--case", default="all", choices=(*CASES, "all"))
    parent.add_argument("--mode", default="all", choices=(*MODES, "all"))
    args = parser.parse_args()
    if args.command == "run":
        return run_service(args)
    if args.command == "work":
        return run_work(args)
    return run_parent(args)


if __name__ == "__main__":
    sys.exit(main())
