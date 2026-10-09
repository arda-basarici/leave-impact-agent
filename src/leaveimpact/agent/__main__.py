"""The job seam's command line: ``python -m leaveimpact.agent <command> ...``, one command
per execution and no queue (the event log step's ruling on the job seam, part 2).

The composition of one execution and none of its logic: the request from the command line,
the store from ``DATABASE_URL``, the object store from the ``LEAVE_IMPACT_*`` names, the
reader's or builder's commit from ``LEAVEIMPACT_CODE_VERSION`` (the image's identity), the
registered rules from ``--registration`` when given, and the command over them. Nothing
here reads a clock.

The commands: ``admit`` takes the request from a file (the request identity, the admitter,
the ledger, and the frozen inputs as the admission event encodes them), since the agent
decodes no scenario and the file is written by a launcher that may; ``deliver-approval``,
``abandon``, ``publish``, ``inventory``, ``set-threshold`` and ``import-spend`` take their
fields as flags.
``work`` composes the investigator graph's real fillings over an admitted attempt (the
graph step, fork 17): the configuration the registration and this code give the named cell
(``registered.agent_provenance``), the role's model, settings, rate and counting model from
flags, the price table from a file, the vendor hosts from the environment, the world
manifest from the world store at the admitted version, the corpus reader from the admitted
version and level before any read (the registry step's forward), the live clients from the
region, the turns over the shipped prompts, the checkpoint saver on the run log's database,
and the approval policy named. One command, one run, one attempt; the worker compares the
composed configuration with the admission's and claims nothing on a difference.

The job's log is public, which decides what this module prints: a result as the fields its
command returns, a refusal of a known kind as its message (files, keys, commits, counts
and reasons the store wrote to be printed, nothing sealed), and anything else as the name
of its type with no traceback. A file that does not decode is reported by its name and the
exception's type alone, since a codec's refusal quotes the value it refused and the value
may be anything the file held (the group's review, first finding). Exit status: 0 for a
result, 1 for a refusal or a publication recorded as failed (its fields still printed; a
workflow must not proceed past either), 2 for a configuration fault, 3 for anything
unexpected.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import DictRow, dict_row

from leaveimpact.adapters.corpus import UnservedCorpus
from leaveimpact.adapters.inference import ConverseClient, CountingClient, inference_client
from leaveimpact.adapters.manifest import ManifestStage, decode_manifest
from leaveimpact.adapters.object_store.layout import world_manifest_key
from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    build_readers,
    hosts_from_env,
    inventory_publisher,
    run_export_publisher,
    stores_from_env,
    world_store_from_env,
    world_store_reader,
)
from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    CommandRefused,
    ImportRequest,
    InventoryRequest,
    PublishRequest,
    ThresholdRequest,
    WorkerComposition,
    WorkRequest,
    abandon,
    admit,
    deliver_approval,
    import_spend,
    publish,
    set_threshold,
    work,
    write_inventory,
)
from leaveimpact.agent.corpus import corpus_reader_for
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.log_events import Admitted, Producer, decode_event
from leaveimpact.agent.log_store import (
    AdmissionReceipt,
    AdmissionRequest,
    LogStore,
    LogStoreConflict,
    LogStoreInvariantBroken,
    LogStoreUnavailable,
)
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import RoleFilling, agent_provenance, effective_rules
from leaveimpact.agent.turns import InvestigatorTurns
from leaveimpact.agent.worker import (
    ApprovalPolicy,
    AutomaticApproval,
    HumanApproval,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import InventoryScope, PublicationStatus
from leaveimpact.core.jsonshape import as_object, expect_fields, object_field, string_field
from leaveimpact.core.pricing import PriceTable, basis_for, decode_price_table
from leaveimpact.core.registration import Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_record import PricingSelection
from leaveimpact.core.run_timing import GIT_SHA_LENGTH, HarnessRevision, TreeState
from leaveimpact.core.tools import Role

PROGRAM = "python -m leaveimpact.agent"
DATABASE = "DATABASE_URL"
CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"


class Command(StrEnum):
    """The commands the entry offers."""

    ADMIT = "admit"
    WORK = "work"
    DELIVER_APPROVAL = "deliver-approval"
    ABANDON = "abandon"
    PUBLISH = "publish"
    INVENTORY = "inventory"
    SET_THRESHOLD = "set-threshold"
    IMPORT_SPEND = "import-spend"


@dataclass(frozen=True, slots=True)
class AdmitFile:
    """The admission request's file, read when the command runs."""

    path: Path


@dataclass(frozen=True, slots=True)
class WorkLine:
    """The work command as the line states it: the attempt with its nonce and launch
    identity, the registered cell, the registration's commit, the role's filling, the
    price table's file, the region the clients call from, the harness revision this code
    claims, and who approves. The registration file is the shared flag's."""

    attempt: WorkRequest
    condition: str
    level: str
    registration_commit: str
    role: RoleFilling
    prices: Path
    region: str
    harness: HarnessRevision
    approval: ApprovalPolicy


@dataclass(frozen=True, slots=True)
class WorkResolved:
    """The work command with its two files decoded: the registration and the price table."""

    line: WorkLine
    registration: Registration
    prices: PriceTable


type Request = (
    AdmitFile
    | WorkLine
    | ApprovalDelivery
    | AbandonRequest
    | PublishRequest
    | InventoryRequest
    | ThresholdRequest
    | ImportRequest
)


type Resolved = (
    AdmissionRequest
    | WorkResolved
    | ApprovalDelivery
    | AbandonRequest
    | PublishRequest
    | InventoryRequest
    | ThresholdRequest
    | ImportRequest
)


@dataclass(frozen=True, slots=True)
class Parsed:
    """One command's request and the registration file whose rules it folds under, if any."""

    command: Command
    request: Request
    registration: Path | None


_REFUSALS = (
    LogStoreUnavailable,
    LogStoreInvariantBroken,
    LogStoreConflict,
    AccessRefused,
    ObjectStoreUnreachable,
    ObjectStoreMisconfigured,
    UnservedCorpus,
    ValueError,
)
"""The failures whose message is written to be printed; a ``ValueError`` is the store's, a
codec's or the registration's refusal naming ids, positions, fields, counts and digests;
the corpus refusal names a version and a level."""

APPROVALS: Mapping[str, ApprovalPolicy] = {
    "automatic": AutomaticApproval(),
    "human": HumanApproval(),
}
"""Who approves at the pause, by the flag's word."""


# --- The request ---------------------------------------------------------------------------


def parse_request(argv: Sequence[str], env: Mapping[str, str]) -> Parsed:
    """The request from ``argv``; the commit of this code from ``env`` where a command needs
    one. ``ConfigurationError`` names what is missing or malformed."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="One command over the run log.", exit_on_error=False
    )
    commands = parser.add_subparsers(dest="command", required=True)
    registration = argparse.ArgumentParser(add_help=False)
    registration.add_argument(
        "--registration", type=Path, default=None, help="the registration whose rules apply"
    )
    about = argparse.ArgumentParser(add_help=False)
    about.add_argument("--run", required=True, help="the run id")
    about.add_argument("--attempt", required=True, type=int, help="the attempt number")

    admitting = commands.add_parser(Command.ADMIT.value, parents=[registration])
    admitting.add_argument("--request", required=True, type=Path, help="the request's file")
    working = commands.add_parser(Command.WORK.value, parents=[registration, about])
    working.add_argument("--nonce", required=True, help="this process's claim nonce")
    working.add_argument("--launch", required=True, help="the launch identity recorded")
    working.add_argument("--condition", required=True, help="the registered condition")
    working.add_argument("--level", required=True, help="the registered corpus level")
    working.add_argument("--registration-commit", required=True, help="the registration's commit")
    working.add_argument("--model", required=True, help="the model id the role's calls run under")
    working.add_argument(
        "--counting-model", required=True, help="the base model the requests are counted against"
    )
    working.add_argument("--max-tokens", required=True, type=int, help="the output maximum")
    working.add_argument("--temperature", type=float, default=None, help="the sampling temperature")
    working.add_argument("--top-p", type=float, default=None, help="the nucleus sampling share")
    working.add_argument("--pricing-key", required=True, help="the rate's key in the price table")
    working.add_argument("--billing-mode", default="on_demand", help="the rate's billing mode")
    working.add_argument("--region", required=True, help="the region the clients call from")
    working.add_argument("--prices", required=True, type=Path, help="the price table's file")
    working.add_argument(
        "--tree-state",
        choices=[state.value for state in TreeState],
        default=TreeState.CLEAN.value,
        help="whether this code runs from its commit or from changes over it",
    )
    working.add_argument(
        "--approval", choices=sorted(APPROVALS), default="automatic", help="who approves"
    )
    delivering = commands.add_parser(Command.DELIVER_APPROVAL.value, parents=[registration, about])
    delivering.add_argument("--approver", required=True, help="the approver's identity")
    delivering.add_argument("--payload-digest", required=True, help="the payload the approver saw")
    abandoning = commands.add_parser(Command.ABANDON.value, parents=[registration, about])
    abandoning.add_argument("--authority", required=True, help="who decides")
    abandoning.add_argument(
        "--reason", required=True, choices=[reason.value for reason in AbandonmentReason]
    )
    commands.add_parser(Command.PUBLISH.value, parents=[registration, about])
    listing = commands.add_parser(Command.INVENTORY.value, parents=[registration])
    listing.add_argument("--world-version", required=True, help="the world the inventory is for")
    listing.add_argument("--registration-commit", required=True, help="the registration's commit")
    listing.add_argument("--ledger", required=True, help="the ledger id")
    setting = commands.add_parser(Command.SET_THRESHOLD.value)
    setting.add_argument("--ledger", required=True, help="the ledger id")
    setting.add_argument("--amount", required=True, type=int, help="the threshold in pico-dollars")
    setting.add_argument("--authority", required=True, help="who sets it")
    setting.add_argument("--registration-commit", required=True, help="the registration's commit")
    setting.add_argument("--limit", required=True, type=int, help="the registered limit")
    importing = commands.add_parser(Command.IMPORT_SPEND.value)
    importing.add_argument(
        "--request", required=True, help="the request identity, held across retries"
    )
    importing.add_argument("--ledger", required=True, help="the ledger id")
    importing.add_argument(
        "--amount", required=True, type=int, help="the spend made outside the log, pico-dollars"
    )
    importing.add_argument(
        "--authority", required=True, help="who established the amount, and from what"
    )
    importing.add_argument("--registration-commit", required=True, help="the registration's commit")
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(f"the command line is not a command: {error}") from error
    command = Command(parsed.command)
    try:
        request = _request_of(command, parsed, env)
    except ValueError as error:
        raise ConfigurationError(f"{command.value}: {error}") from error
    return Parsed(command, request, getattr(parsed, "registration", None))


def _request_of(command: Command, parsed: argparse.Namespace, env: Mapping[str, str]) -> Request:
    match command:
        case Command.ADMIT:
            return AdmitFile(parsed.request)
        case Command.WORK:
            if parsed.registration is None:
                raise ConfigurationError("work runs under a registration: --registration")
            settings = [CallSetting("max_tokens", parsed.max_tokens)]
            for name, value in (("temperature", parsed.temperature), ("top_p", parsed.top_p)):
                if value is not None:
                    settings.append(CallSetting(name, value))
            return WorkLine(
                WorkRequest(parsed.run, parsed.attempt, parsed.nonce, parsed.launch),
                parsed.condition,
                parsed.level,
                parsed.registration_commit,
                RoleFilling(
                    Role.INVESTIGATOR.value,
                    CallConfiguration(parsed.model, tuple(settings)),
                    PricingSelection(parsed.pricing_key, parsed.region, parsed.billing_mode),
                    parsed.counting_model,
                ),
                parsed.prices,
                parsed.region,
                HarnessRevision(code_version(env), TreeState(parsed.tree_state)),
                APPROVALS[parsed.approval],
            )
        case Command.DELIVER_APPROVAL:
            return ApprovalDelivery(
                parsed.run, parsed.attempt, parsed.approver, parsed.payload_digest
            )
        case Command.ABANDON:
            return AbandonRequest(
                parsed.run, parsed.attempt, parsed.authority, AbandonmentReason(parsed.reason)
            )
        case Command.PUBLISH:
            return PublishRequest(parsed.run, parsed.attempt, code_version(env))
        case Command.INVENTORY:
            return InventoryRequest(
                InventoryScope(
                    WorldVersion(parsed.world_version), parsed.registration_commit, parsed.ledger
                ),
                code_version(env),
            )
        case Command.SET_THRESHOLD:
            return ThresholdRequest(
                parsed.ledger,
                parsed.amount,
                parsed.authority,
                parsed.registration_commit,
                parsed.limit,
            )
        case Command.IMPORT_SPEND:
            return ImportRequest(
                parsed.request,
                parsed.ledger,
                parsed.amount,
                parsed.authority,
                parsed.registration_commit,
            )


def code_version(env: Mapping[str, str]) -> str:
    """The commit this code runs as, from the image's identity variable."""
    version = env.get(CODE_VERSION, "").strip()
    if len(version) != GIT_SHA_LENGTH:
        raise ValueError(
            f"{CODE_VERSION} is the forty-hex commit this code runs as, got {version!r}"
        )
    return version


def rules_of(registration: Path | None) -> Rules:
    """The attribution table and re-dispatch policy a run under the registration file is read
    by: the registered ones, or the development values while a draft holds them pending
    (``registered.effective_rules``); with no file, the rules of a system that calls no
    model."""
    if registration is None:
        return Rules(None, None)
    return effective_rules(decode_registration_bytes(registration.read_bytes()))


def admission_request_of(content: bytes | str, rules: Rules) -> AdmissionRequest:
    """The admission request a file holds: the request identity, the admitter's identity,
    the ledger (``null`` when the inputs reserve nothing) and the frozen inputs under
    ``admitted``, as the admission event encodes them."""
    data = as_object(json.loads(content), "an admission request")
    expect_fields(data, ("request_id", "admitter", "ledger_id", "admitted"), "an admission request")
    ledger = data["ledger_id"]
    if ledger is not None and not isinstance(ledger, str):
        raise ValueError("ledger_id is a string or null")
    admitted = decode_event("admitted", object_field(data, "admitted"))
    assert isinstance(admitted, Admitted)
    return AdmissionRequest(
        string_field(data, "request_id"),
        admitted.inputs,
        Producer(string_field(data, "admitter")),
        ledger,
        rules,
    )


# --- The execution -------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: LogStore | None = None,
) -> int:
    """Run one command; ``env`` defaults to the process's environment and ``store`` to one
    over ``DATABASE_URL``."""
    environment = os.environ if env is None else env
    try:
        parsed = parse_request(sys.argv[1:] if argv is None else argv, environment)
        rules = (
            Rules(None, None)
            if parsed.registration is None
            else _decoded(parsed.registration, "the registration", rules_of)
        )
        request = _resolved(parsed, rules)
        if store is None:
            dsn = environment.get(DATABASE, "").strip()
            if not dsn:
                raise ConfigurationError(f"{DATABASE} names the run log's database")
            store = LogStore(dsn=dsn)
    except ConfigurationError as error:
        print(f"leaveimpact.agent: {error}", file=sys.stderr)
        return 2
    try:
        status, lines = _run(request, store, rules, environment)
    except ConfigurationError as error:
        print(f"leaveimpact.agent: {error}", file=sys.stderr)
        return 2
    except _REFUSALS as refusal:
        print(f"leaveimpact.agent: refused: {refusal}", file=sys.stderr)
        return 1
    except Exception as unexpected:
        print(
            f"leaveimpact.agent: failed with {type(unexpected).__name__}; the traceback is "
            "withheld because this log is public",
            file=sys.stderr,
        )
        return 3
    finally:
        store.close()
    for line in lines:
        print(line)
    return status


def _decoded[T](path: Path, what: str, decode: Callable[[Path], T]) -> T:
    """``decode(path)``, a failure to read or decode the file reported by its name and the
    exception's type and never its message, which quotes what the file held."""
    try:
        return decode(path)
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            f"{what} {path} does not read or decode ({type(error).__name__})"
        ) from None


def _resolved(parsed: Parsed, rules: Rules) -> Resolved:
    """The command's request with its files decoded: the admission's under ``rules``, the
    work command's registration and price table."""
    request = parsed.request
    if isinstance(request, AdmitFile):
        return _decoded(
            request.path,
            "the request file",
            lambda path: admission_request_of(path.read_bytes(), rules),
        )
    if isinstance(request, WorkLine):
        assert parsed.registration is not None, "the work line is parsed under a registration"
        return WorkResolved(
            request,
            _decoded(
                parsed.registration,
                "the registration",
                lambda path: decode_registration_bytes(path.read_bytes()),
            ),
            _decoded(
                request.prices,
                "the price table",
                lambda path: decode_price_table(json.loads(path.read_bytes())),
            ),
        )
    return request


def _run(
    request: Resolved, store: LogStore, rules: Rules, env: Mapping[str, str]
) -> tuple[int, list[str]]:
    match request:
        case AdmissionRequest():
            result = admit(request, store)
            if isinstance(result, AdmissionReceipt):
                return 0, [
                    f"admitted={result.run_id}/{result.attempt}",
                    f"recorded_at={result.recorded_at.isoformat()}",
                    f"ledger_revision={result.ledger_revision}",
                ]
            return 1, [f"refused={result.run_id}/{result.attempt}", f"reason={result.reason}"]
        case WorkResolved():
            ending = _work(request, store, rules, env)
            closed = ending.kind in (WorkerEndingKind.CLOSED, WorkerEndingKind.AWAITING_APPROVAL)
            return 0 if closed else 1, [
                f"worked={ending.run_id}/{ending.attempt}",
                f"ending={ending.kind.value}",
                f"detail={ending.detail}",
                f"generation={ending.generation}",
            ]
        case ApprovalDelivery():
            delivered = deliver_approval(request, store, rules=rules)
            if isinstance(delivered, CommandRefused):
                return _refused(delivered)
            return 0, [
                f"approved={delivered.run_id}/{delivered.attempt}",
                f"position={delivered.position}",
            ]
        case AbandonRequest():
            closed = abandon(request, store, rules=rules)
            if isinstance(closed, CommandRefused):
                return _refused(closed)
            return 0, [
                f"abandoned={closed.run_id}/{closed.attempt}",
                f"generation_fenced={closed.generation_fenced}",
                f"position={closed.position}",
            ]
        case PublishRequest():
            stores = stores_from_env(env)
            record = publish(request, store, run_export_publisher(stores), rules=rules)
            if isinstance(record, CommandRefused):
                return _refused(record)
            return 1 if record.state is PublicationStatus.FAILED else 0, [
                f"publication={record.run_id}/{record.attempt}",
                f"state={record.state.value}",
                f"object_identity={record.object_identity}",
                f"object_digest={record.object_digest}",
                f"incident={record.incident}",
            ]
        case InventoryRequest():
            stores = stores_from_env(env)
            written = write_inventory(request, store, inventory_publisher(stores), rules=rules)
            return 0, [
                f"inventory_digest={written.digest}",
                f"inventory_key={written.key}",
                f"outcome={written.outcome.value}",
                f"attempts={len(written.inventory.attempts)}",
                f"refused={len(written.inventory.refused)}",
            ]
        case ThresholdRequest():
            entry = set_threshold(request, store)
            if isinstance(entry, CommandRefused):
                return _refused(entry)
            return 0, [
                f"threshold={request.ledger_id}",
                f"revision={entry.revision}",
                f"amount_pico_usd={entry.amount_pico_usd}",
            ]
        case ImportRequest():
            entry = import_spend(request, store)
            if isinstance(entry, CommandRefused):
                return _refused(entry)
            return 0, [
                f"imported={request.ledger_id}",
                f"revision={entry.revision}",
                f"amount_pico_usd={entry.amount_pico_usd}",
                f"total_after_pico_usd={entry.total_after_pico_usd}",
            ]


def _work(
    request: WorkResolved, store: LogStore, rules: Rules, env: Mapping[str, str]
) -> WorkerEnding:
    """The investigator's composition over the admitted attempt, worked as far as one
    process can; every reader and connection opened here is closed before it returns.

    The admitted inputs are read first, since the manifest and the corpus reader are
    functions of the admitted world version and level; the corpus reader runs its serving
    check before any read port is built (``corpus_reader_for``). The composed configuration
    is the registration's and this code's for the cell named, and the worker refuses the
    claim where it differs from the admission's.
    """
    line = request.line
    configuration = agent_provenance(
        request.registration,
        line.condition,
        line.level,
        preregistration_commit=line.registration_commit,
        pricing=basis_for(request.prices, (line.role.pricing,)),
        role=line.role,
    )
    inputs = store.load(line.attempt.run_id, line.attempt.attempt, rules=rules).inputs
    if inputs is None:
        raise ValueError(
            f"run {line.attempt.run_id} attempt {line.attempt.attempt} holds no admission"
        )
    dsn = env[DATABASE]
    world_reader = world_store_reader(world_store_from_env(env))
    version = inputs.context.world_version
    stored = world_reader.get(world_manifest_key(version))
    if stored is None:
        raise ValueError(f"the world store holds no manifest for version {version}")
    manifest = decode_manifest(stored.content, stage=ManifestStage.PROJECTED)
    if manifest.world_version != version:
        raise ValueError(
            f"the manifest at the keys of {version} describes world {manifest.world_version}"
        )
    corpus = corpus_reader_for(inputs, dsn=dsn)
    try:
        readers = build_readers(hosts_from_env(env, jira_at_gateway=True), manifest, world_reader)
        try:
            runtime = inference_client(line.region)
            connection = _saver_connection(dsn)
            try:
                saver = PostgresSaver(connection)
                saver.setup()
                composition = WorkerComposition(
                    configuration,
                    line.harness,
                    rules,
                    InvestigatorTurns(load_prompt_assets()),
                    ConverseClient(runtime),
                    CountingClient(runtime),
                    ReadPorts(readers.people, readers.work, readers.calendar, corpus),
                    line.approval,
                    saver,
                )
                return work(line.attempt, store, composition)
            finally:
                connection.close()
        finally:
            readers.close()
    finally:
        corpus.close()


def _saver_connection(dsn: str) -> psycopg.Connection[DictRow]:
    """The checkpoint saver's own connection, in the configuration the acceptance spike
    settled: autocommit, no prepared statements, dictionary rows."""
    return psycopg.Connection[DictRow].connect(
        dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )


def _refused(refused: CommandRefused) -> tuple[int, list[str]]:
    return 1, [f"refused={refused.subject}", f"reason={refused.reason}"]


if __name__ == "__main__":
    sys.exit(main())
