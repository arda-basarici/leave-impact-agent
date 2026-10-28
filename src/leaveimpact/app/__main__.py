"""The demo surface's operator commands, one command per execution: ``bootstrap`` applies
the app schema, which the deploy runs after the log's bootstrap and before the service
starts; ``publish`` writes a replay's row in the table of publishable attempts;
``verify-restore`` is the restore drill's verification over a restored scratch database,
the capture the backup recorded on stdin (the backup step; the checks in ``restore``);
``worker`` is the worker service (``app.worker``) and ``work-one`` the child it spawns per
attempt, which composes the same work order the service would and performs it once, the
ending as one JSON line on stdout (the worker service's step: the work runs in a process
the service can terminate, wait on, kill and reap, since the blocked-work probe showed the
in-process shape losing the first stop signal behind the checkpointer's executor).

``verify-restore`` runs the recovery procedure first, the log's bootstrap and the app's,
both idempotent, since a dump older than the code's layout is recovered that way and the
drill verifies the procedure, not the archive alone; then the checks, one printed line
each, and exit 0 only when every check passed. The capture arrives on stdin from a file
the platform's unit writes from the object's metadata, never pasted (the publish list's
lesson: a pasted stdin is read by the first container and the rest runs as shell lines).

Apart from the package root's ``python -m leaveimpact``, which is the image's command
(serve with no argument, the identity line, the smoke) and answers to nothing else, so an
operator step cannot be mistaken for the service and the root's exact-argument contract
stays as the deploy test holds it. Both commands read the database from the environment the
compose file composes; ``publish`` also reads the registration the image ships, at the path
its environment names, and refuses one whose digest is not the committed configuration's
(the read model's rule), since the attempt it verifies is folded under those rules. Each
prints one line of what it established and exits 1 on a refusal the stores name (another
schema version, a store that does not answer, an attempt that is not a closed run of the
served world, a name or an attempt already published) and 2 on a command line that is not
a command or an environment that lacks what the command needs.

``main`` takes the two stores' constructors, the configuration, the registration's bytes
and the registration's reading as seams, so the unit level drives it over fakes and the
integration level over the real database with a fixture history folded under the fixtures'
rules; the real reading, ``read_model.rules_under``, is the default and has its own tests.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TextIO, cast

from leaveimpact.adapters.corpus.adapter import served_versions
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    inventory_publisher,
    run_export_publisher,
    world_store_from_env,
)
from leaveimpact.agent.commands import WorkRequest, publish, write_inventory
from leaveimpact.agent.log_store import LogStore, LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import RoleFilling, registered_filling
from leaveimpact.agent.work_order import WorkOrder, perform
from leaveimpact.agent.worker import HumanApproval, WorkerEnding
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.heartbeat import heartbeat_path, worker_healthy
from leaveimpact.app.main import CODE_VERSION, DATABASE, REGISTRATION_FILE
from leaveimpact.app.public import public_id_of
from leaveimpact.app.publication_check import PublicationReads, verify_publications
from leaveimpact.app.publishing import PublishRefused, PublishRequest, draft_of
from leaveimpact.app.read_model import LogSession, rules_under
from leaveimpact.app.restore import RestoreReads, verify
from leaveimpact.app.store import (
    SCHEMA_VERSION,
    AlreadyPublished,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
    AttemptPublished,
    PublicationConflict,
    Published,
    SlugTaken,
    connect_bounded,
)
from leaveimpact.app.sweeper import (
    PublishExport,
    SweepComposition,
    WriteInventoryCommand,
    action_line,
    sweep,
)
from leaveimpact.app.worker import (
    ServiceComposition,
    ending_line,
    install_stop_handlers,
    serve,
    service_identity,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.pricing import PriceTable, decode_price_table
from leaveimpact.core.registration import NORMAL_CONDITION, Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import HarnessRevision, TreeState, require_commit

BOOTSTRAP = "bootstrap"
PUBLISH = "publish"
VERIFY_RESTORE = "verify-restore"
VERIFY_PUBLICATIONS = "verify-publications"
SWEEP = "sweep"
WORKER = "worker"
WORKER_HEALTH = "worker-health"
WORK_ONE = "work-one"

REGISTRATION_COMMIT = "LEAVEIMPACT_REGISTRATION_COMMIT"
PRICES_FILE = "LEAVEIMPACT_PRICES_FILE"
"""The two names the image bakes beside the registration file (the Dockerfile is the
contract; the launcher reads the same names for the surface's planning)."""

MakeStore = Callable[[str], AppStore]
MakeLog = Callable[[str], LogSession]
MakeRestoreLog = Callable[[str], LogStore]
CacheVersions = Callable[[str], frozenset[WorldVersion]]
SweepCommands = Callable[
    [Mapping[str, str], LogStore, Rules], tuple[PublishExport, WriteInventoryCommand]
]
"""The two publication commands of a sweep, bound to the world store the environment names,
the log and the rules; a test binds fakes."""
ServeWorker = Callable[[LogStore, AppStore, ServiceComposition], int]
"""The worker service's life over the two stores; a test serves a fake."""


class PerformWork(Protocol):
    """``work_order.perform``'s shape, the seam the child's command performs through; a
    test records the order and answers an ending."""

    def __call__(
        self,
        order: WorkOrder,
        registration: Registration,
        prices: PriceTable,
        *,
        store: LogStore,
        rules: Rules,
        env: Mapping[str, str],
    ) -> WorkerEnding: ...


def _sweep_commands_from_env(
    env: Mapping[str, str], log: LogStore, rules: Rules
) -> tuple[PublishExport, WriteInventoryCommand]:
    world_store = world_store_from_env(env)
    exporter, inventorier = run_export_publisher(world_store), inventory_publisher(world_store)
    return (
        lambda request: publish(request, log, exporter, rules=rules),
        lambda request: write_inventory(request, log, inventorier, rules=rules),
    )


def _store_over(dsn: str) -> AppStore:
    return AppStore(dsn=dsn)


def _log_store_over(dsn: str) -> LogStore:
    # The log store under the app's bounds, one command's lifetime, closed by the command.
    return LogStore(dsn=dsn, connect=connect_bounded)


def _log_over(dsn: str) -> LogSession:
    return _log_store_over(dsn)


def _registration_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: MakeStore = _store_over,
    log: MakeLog = _log_over,
    configuration: Callable[[], DemoConfiguration] = committed_configuration,
    registration: Callable[[str], bytes] = _registration_bytes,
    rules: Callable[[DemoConfiguration, bytes], Rules] = rules_under,
    restore_log: MakeRestoreLog = _log_store_over,
    cache: CacheVersions = served_versions,
    stdin: TextIO | None = None,
    sweep_commands: SweepCommands = _sweep_commands_from_env,
    serve_worker: ServeWorker = serve,
    perform_work: PerformWork = perform,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """``bootstrap`` applies the app schema to the database the environment names;
    ``publish --run <id> --attempt <n> --as <public-id> --by <who> [--title <t>]`` writes
    a replay's row after verifying the attempt against the log; ``verify-restore`` runs
    both bootstraps on the restored database the environment names and every check of the
    restore drill against the capture on ``stdin``, one line per check;
    ``verify-publications`` regenerates every published replay's log and export digests
    from its log under this code and holds them to its publication record, one line per
    replay; ``sweep`` runs one pass of the sweeper over the demo's public attempts (the
    reconciliations and the fifteen-minute close, the publications through the world
    store the environment names), one line per action; ``worker`` runs the worker service
    (``app.worker``: the start pass, then the sweeper's pass and one visitor's attempt per
    tick, each attempt worked in a child running ``work-one``, until the stop signal
    drains it); ``work-one --run <id> --attempt <n> --nonce <hex> --launch <identity>``
    is that child: the agent's work order over the demo's cell under the human approval,
    performed once, the ending printed as one JSON line; ``worker-health`` reads the
    worker's heartbeat. 0 with the printed lines (a drained worker included), 1 when a
    store refuses or does not answer, the attempt is not publishable, a check failed, an
    action was not carried, the work refused or the heartbeat is absent or stale, 2 on any
    other command line, an environment that lacks the database, the registration or (for
    a sweep, the worker or its child) the commit this code runs as, the registration's
    commit or the price table, or a stdin that is not a JSON list."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    environment = os.environ if env is None else env
    try:
        parsed = _parser().parse_args(arguments)
    except SystemExit:
        return 2
    dsn = environment.get(DATABASE, "").strip()
    if not dsn:
        print(f"leaveimpact.app: {DATABASE} is not set and the command needs it", file=sys.stderr)
        return 2
    if parsed.command == BOOTSTRAP:
        return _bootstrap(store(dsn))
    if parsed.command == VERIFY_RESTORE:
        return _verify_restore(
            dsn,
            environment,
            sys.stdin if stdin is None else stdin,
            store,
            restore_log,
            cache,
            configuration,
            registration,
            rules,
        )
    if parsed.command == VERIFY_PUBLICATIONS:
        return _verify_publications(
            dsn, environment, store, restore_log, configuration, registration, rules
        )
    if parsed.command == SWEEP:
        return _sweep(
            dsn, environment, store, restore_log, sweep_commands, configuration, registration, rules
        )
    if parsed.command == WORKER:
        return _worker(
            dsn,
            environment,
            store,
            restore_log,
            sweep_commands,
            configuration,
            registration,
            rules,
            serve_worker,
            now,
        )
    if parsed.command == WORK_ONE:
        return _work_one(
            parsed, dsn, environment, restore_log, configuration, registration, rules, perform_work
        )
    if parsed.command == WORKER_HEALTH:
        return 0 if worker_healthy(heartbeat_path(environment), now()) else 1
    return _publish(parsed, dsn, environment, store, log, configuration, registration, rules)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.app",
        description="The demo surface's operator commands, one per execution.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        BOOTSTRAP,
        description=(
            "Create the app's tables where missing and check their version; the deploy runs it."
        ),
    )
    publishing = commands.add_parser(
        PUBLISH, description="Publish a closed run of the served world as a replay."
    )
    publishing.add_argument("--run", required=True, help="the run id the log holds")
    publishing.add_argument("--attempt", required=True, type=int, help="the attempt number")
    publishing.add_argument(
        "--as", dest="public_id", required=True, help="the public name the URL carries"
    )
    publishing.add_argument("--by", required=True, help="who publishes")
    publishing.add_argument("--title", default=None, help="an introduced example's title")
    commands.add_parser(
        VERIFY_RESTORE,
        description=(
            "The restore drill: both bootstraps on the restored database, then every check "
            "against the backup's capture read from stdin."
        ),
    )
    commands.add_parser(
        VERIFY_PUBLICATIONS,
        description=(
            "Every published replay's log and export digests regenerated from its log under "
            "this code and held to its publication record; one line per replay."
        ),
    )
    commands.add_parser(
        SWEEP,
        description=(
            "One pass of the sweeper over the demo's public attempts: the reconciliations, "
            "the fifteen-minute close and the publications; one line per action."
        ),
    )
    commands.add_parser(
        WORKER,
        description=(
            "The worker service: the sweeper's pass and one visitor's attempt per tick, "
            "single flight, until the stop signal drains it."
        ),
    )
    commands.add_parser(
        WORKER_HEALTH,
        description="The worker's healthcheck: 0 while its heartbeat's deadline is ahead.",
    )
    one = commands.add_parser(
        WORK_ONE,
        description=(
            "The worker service's child: one attempt worked once under the demo's cell, the "
            "ending printed as one JSON line."
        ),
    )
    one.add_argument("--run", required=True, help="the run id the log holds")
    one.add_argument("--attempt", required=True, type=int, help="the attempt number")
    one.add_argument("--nonce", required=True, help="the process nonce of this claim")
    one.add_argument("--launch", required=True, help="the service's launch identity")
    return parser


def _verify_restore(
    dsn: str,
    environment: Mapping[str, str],
    stdin: TextIO,
    store: MakeStore,
    restore_log: MakeRestoreLog,
    cache: CacheVersions,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> int:
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        print(
            f"leaveimpact.app: {REGISTRATION_FILE} is not set and the drill folds attempts "
            "under the registration's rules",
            file=sys.stderr,
        )
        return 2
    try:
        loaded: object = json.loads(stdin.read())
    except ValueError as error:
        print(f"leaveimpact.app: stdin is not the backup's capture: {error}", file=sys.stderr)
        return 2
    rows = cast(list[object], loaded) if isinstance(loaded, list) else None
    if rows is None or not all(isinstance(row, dict) for row in rows):
        print("leaveimpact.app: the capture is a JSON list of ledger rows", file=sys.stderr)
        return 2
    capture = cast(list[JsonObject], rows)
    try:
        demo = configuration()
        folding = rules(demo, registration(registration_file))
    except (OSError, ValueError) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    log = restore_log(dsn)
    try:
        log.ensure_schema()
        app = store(dsn)
        app.ensure_schema()
        print("verify-restore: recovery procedure: both bootstraps applied")
        reads = RestoreReads(
            app_schema=app.schema_supported,
            ledger_capture=app.ledger_capture,
            cache_versions=lambda: cache(dsn),
            rows=app,
            log=log,
            configuration=demo,
            rules=folding,
        )
        checks = verify(capture, reads)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
        SourceUnreachable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        log.close()
    for check in checks:
        print(f"verify-restore: {check.name}: {'ok' if check.passed else 'FAILED'}: {check.detail}")
    passed = sum(check.passed for check in checks)
    print(f"verify-restore: {passed} of {len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def _verify_publications(
    dsn: str,
    environment: Mapping[str, str],
    store: MakeStore,
    restore_log: MakeRestoreLog,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> int:
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        print(
            f"leaveimpact.app: {REGISTRATION_FILE} is not set and the check folds attempts "
            "under the registration's rules",
            file=sys.stderr,
        )
        return 2
    try:
        demo = configuration()
        folding = rules(demo, registration(registration_file))
    except (OSError, ValueError) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    log = restore_log(dsn)
    try:
        reads = PublicationReads(
            rows=store(dsn),
            log=log,
            publication_of=log.publication_of,
            configuration=demo,
            rules=folding,
        )
        checks = verify_publications(reads)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        log.close()
    for check in checks:
        print(
            f"verify-publications: {check.name}: {'ok' if check.passed else 'FAILED'}: "
            f"{check.detail}"
        )
    passed = sum(check.passed for check in checks)
    print(f"verify-publications: {passed} of {len(checks)} replays reproduce")
    return 0 if checks and passed == len(checks) else 1


def _sweep(
    dsn: str,
    environment: Mapping[str, str],
    store: MakeStore,
    restore_log: MakeRestoreLog,
    sweep_commands: SweepCommands,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> int:
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        print(
            f"leaveimpact.app: {REGISTRATION_FILE} is not set and the pass folds attempts "
            "under the registration's rules",
            file=sys.stderr,
        )
        return 2
    code_version = environment.get(CODE_VERSION, "").strip()
    try:
        require_commit(code_version, "the commit this code runs as")
    except ValueError as error:
        print(
            f"leaveimpact.app: {CODE_VERSION} names the commit the exports and inventories "
            f"are built as: {error}",
            file=sys.stderr,
        )
        return 2
    try:
        demo = configuration()
        folding = rules(demo, registration(registration_file))
    except (OSError, ValueError) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    log = restore_log(dsn)
    try:
        publish_export, write_inventory_command = sweep_commands(environment, log, folding)
        composition = SweepComposition(
            demo,
            folding,
            HarnessRevision(code_version, TreeState.CLEAN),
            code_version,
            publish_export,
            write_inventory_command,
            lambda: secrets.token_hex(16),
        )
        report = sweep(log, store(dsn), composition)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        ConfigurationError,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        log.close()
    for outcome in report:
        print(
            f"sweep: {action_line(outcome.action)}: "
            f"{'ok' if outcome.carried else 'NOT CARRIED'}: {outcome.detail}"
        )
    carried = sum(outcome.carried for outcome in report)
    print(f"sweep: {carried} of {len(report)} actions carried")
    return 0 if carried == len(report) else 1


class _Refused(Exception):
    """What a command's composition refuses before any store is opened: the exit code the
    command line answers with and the line it prints."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class _WorkMaterials:
    """What one worker execution is composed from, read once from the environment the
    image bakes: the demo's configuration, its rules, the registration and the price table
    the image ships, the registered role's filling (none for rules only), the harness
    revision this code claims and the registration's commit. The service reads them for
    its sweep composition and the child for its order, from one reading, so the two cannot
    drift."""

    demo: DemoConfiguration
    rules: Rules
    registered: Registration
    prices: PriceTable
    role: RoleFilling | None
    harness: HarnessRevision
    registration_commit: str

    def perform(
        self,
        request: WorkRequest,
        log: LogStore,
        environment: Mapping[str, str],
        performing: PerformWork = perform,
    ) -> WorkerEnding:
        """The work order over ``request`` under the demo's cell, the normal condition and
        the human approval, performed through ``work_order.perform`` (``performing`` is
        the seam)."""
        order = WorkOrder(
            request,
            self.demo.system,
            NORMAL_CONDITION,
            self.demo.level,
            self.registration_commit,
            self.role,
            self.demo.region,
            self.harness,
            HumanApproval(),
        )
        return performing(
            order, self.registered, self.prices, store=log, rules=self.rules, env=environment
        )


def _work_materials(
    environment: Mapping[str, str],
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> _WorkMaterials:
    """The materials from the environment, or ``_Refused``: 2 for a name unset or a commit
    that is not one, 1 for a file or a registration that does not read."""
    missing = [
        name
        for name in (REGISTRATION_FILE, CODE_VERSION, REGISTRATION_COMMIT, PRICES_FILE)
        if not environment.get(name, "").strip()
    ]
    if missing:
        raise _Refused(2, f"{', '.join(missing)} not set and the worker composes from them")
    code_version = environment[CODE_VERSION].strip()
    try:
        require_commit(code_version, "the commit this code runs as")
        registration_commit = require_commit(
            environment[REGISTRATION_COMMIT].strip(), "the commit the registration was changed at"
        )
    except ValueError as error:
        raise _Refused(2, str(error)) from None
    try:
        demo = configuration()
        registration_bytes = registration(environment[REGISTRATION_FILE].strip())
        folding = rules(demo, registration_bytes)
        registered = decode_registration_bytes(registration_bytes)
        prices = decode_price_table(
            json.loads(Path(environment[PRICES_FILE].strip()).read_bytes())
        )
        role = (
            None
            if demo.system is SystemKind.RULES_ONLY
            else registered_filling(registered, demo.system, demo.region, "on_demand")
        )
    except (OSError, ValueError) as error:
        raise _Refused(1, f"refused: {error}") from None
    return _WorkMaterials(
        demo,
        folding,
        registered,
        prices,
        role,
        HarnessRevision(code_version, TreeState.CLEAN),
        registration_commit,
    )


def work_one_command(request: WorkRequest) -> list[str]:
    """The child's command line for ``request``: this interpreter running this package's
    ``work-one`` with the request's four fields; the environment is inherited whole.

    >>> line = work_one_command(WorkRequest("run-a", 1, "ab" * 16, "worker-20261028T090500Z-x"))
    >>> line[1:8]
    ['-m', 'leaveimpact.app', 'work-one', '--run', 'run-a', '--attempt', '1']
    >>> line[8:]
    ['--nonce', 'abababababababababababababababab', '--launch', 'worker-20261028T090500Z-x']
    """
    return [
        sys.executable,
        "-m",
        "leaveimpact.app",
        WORK_ONE,
        "--run",
        request.run_id,
        "--attempt",
        str(request.attempt),
        "--nonce",
        request.nonce,
        "--launch",
        request.launch,
    ]


def _worker(
    dsn: str,
    environment: Mapping[str, str],
    store: MakeStore,
    restore_log: MakeRestoreLog,
    sweep_commands: SweepCommands,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
    serve_worker: ServeWorker,
    now: Callable[[], datetime],
) -> int:
    """The service composed (``app.worker``): the sweep composition as ``sweep`` builds it
    under the service's identity over the work materials, the child's command line the
    ``work-one`` of this interpreter, the stop handlers installed, the service served
    until drained. The materials are read here too, before any store is opened, so a
    service whose child could not compose refuses at its start and not per attempt."""
    try:
        materials = _work_materials(environment, configuration, registration, rules)
    except _Refused as refused:
        print(f"leaveimpact.app: {refused}", file=sys.stderr)
        return refused.code
    identity = service_identity(now(), secrets.token_hex(16))
    log = restore_log(dsn)
    try:
        publish_export, write_inventory_command = sweep_commands(environment, log, materials.rules)
        composition = ServiceComposition(
            SweepComposition(
                materials.demo,
                materials.rules,
                materials.harness,
                materials.harness.commit,
                publish_export,
                write_inventory_command,
                lambda: secrets.token_hex(16),
                launch=identity,
            ),
            work_one_command,
            now,
            heartbeat=heartbeat_path(environment),
        )
        install_stop_handlers()
        return serve_worker(log, store(dsn), composition)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        ConfigurationError,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        log.close()


def _work_one(
    parsed: argparse.Namespace,
    dsn: str,
    environment: Mapping[str, str],
    restore_log: MakeRestoreLog,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
    perform_work: PerformWork,
) -> int:
    """The service's child: the work materials, the request from the line, the stop
    handlers installed so the supervisor's terminate ends the segment where the store
    answers (the worker's stop branch re-raises and this process exits through it, with
    no ending line, which the supervisor reads as the loss it caused), the order performed
    once and the ending printed as one JSON line on stdout. A refusal the stores, a codec,
    the registration or the corpus name is printed to stderr and answered with 1; a stdout
    with no ending line is the supervisor's signal either way."""
    try:
        materials = _work_materials(environment, configuration, registration, rules)
    except _Refused as refused:
        print(f"leaveimpact.app: {refused}", file=sys.stderr)
        return refused.code
    try:
        request = WorkRequest(parsed.run, parsed.attempt, parsed.nonce, parsed.launch)
    except ValueError as error:
        print(f"leaveimpact.app: {error}", file=sys.stderr)
        return 2
    log = restore_log(dsn)
    try:
        install_stop_handlers()
        ending = materials.perform(request, log, environment, perform_work)
    except (
        ConfigurationError,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
        OSError,
        SourceUnreachable,
        ValueError,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        log.close()
    print(ending_line(ending), flush=True)
    return 0

def _bootstrap(app: AppStore) -> int:
    try:
        app.ensure_schema()
    except (AppStoreInvariantBroken, AppStoreUnavailable) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    print(f"app schema version {SCHEMA_VERSION} established")
    return 0


def _publish(
    parsed: argparse.Namespace,
    dsn: str,
    environment: Mapping[str, str],
    store: MakeStore,
    log: MakeLog,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> int:
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        print(
            f"leaveimpact.app: {REGISTRATION_FILE} is not set and publishing folds the "
            "attempt under the registration's rules",
            file=sys.stderr,
        )
        return 2
    try:
        public_id = public_id_of(parsed.public_id)
        demo = configuration()
        folding = rules(demo, registration(registration_file))
    except (OSError, ValueError) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    request = PublishRequest(parsed.run, parsed.attempt, public_id, parsed.title, parsed.by)
    reads = log(dsn)
    try:
        draft = draft_of(request, demo, reads, folding)
        if isinstance(draft, PublishRefused):
            print(f"leaveimpact.app: refused: {draft.reason}", file=sys.stderr)
            return 1
        outcome = store(dsn).publish(draft)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        reads.close()
    match outcome:
        case Published(row):
            print(
                f"published {row.public_id}: run {row.run_id} attempt {row.attempt}, world "
                f"{row.world_version} scenario {row.scenario_id}, at "
                f"{row.published_at.isoformat()} by {row.published_by}"
            )
            return 0
        case AlreadyPublished(row):
            print(
                f"already published {row.public_id} at {row.published_at.isoformat()} by "
                f"{row.published_by}; nothing changed"
            )
            return 0
        case SlugTaken(existing):
            reason = (
                f"{existing.public_id} already names run {existing.run_id} attempt "
                f"{existing.attempt}"
            )
        case AttemptPublished(existing):
            reason = (
                f"run {existing.run_id} attempt {existing.attempt} is already published as "
                f"{existing.public_id}"
            )
        case PublicationConflict(existing):
            reason = (
                f"{existing.public_id} is published with title {existing.title!r} by "
                f"{existing.published_by!r}; a repeat states other content and changes nothing"
            )
    print(f"leaveimpact.app: refused: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
