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
``decline``, ``abandon``, ``publish``, ``inventory``, ``set-threshold`` and ``import-spend``
take their fields as flags. ``review-approval`` prints the frozen review payload a human approves
over, with the digest ``deliver-approval`` must carry (the first live run's step, fork 10):
the one command whose output is the run's content, so it is run in a Session Manager
session, which is account-private, and never in a workflow's log or an SSM invocation's
stored output.
``bootstrap-log`` creates the run log's tables where missing, writes the schema version
where absent and checks it, and never alters an existing table: the deploy script runs it
at every landing, as it runs the corpus cache's, so a fresh instance holds the log before
any lifecycle command reaches it (the first live dispatch of 2026-10-13 found one that
never had).
``work`` restates its line as a work order and performs it (``work_order.perform``, where
the composition of the investigator graph's real fillings over an admitted attempt lives
since the worker service's step, so the operator's command line and the demo's worker
compose one way): the role's model, settings, rate and counting model from flags, the
price table and the registration from files, the approval policy named, the rest from
the environment and the stores as that module says. A rules-only cell runs the same
command with no model flag (the first live run's step, fork 4), and the registration's
rules it is read under are not consulted by its fold. One command, one run, one attempt;
the worker compares the composed configuration with the admission's and claims nothing on
a difference, and an attempt whose log already holds its ending takes the terminal-only
path with nothing beyond the run log built.

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

from leaveimpact.adapters.corpus import UnservedCorpus
from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    inventory_publisher,
    run_export_publisher,
    world_store_from_env,
)
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    CommandRefused,
    DeclineDelivery,
    ImportRequest,
    InventoryRequest,
    PublishRequest,
    ReviewRequest,
    ThresholdRequest,
    WorkRequest,
    abandon,
    admit,
    decline,
    deliver_approval,
    import_spend,
    publish,
    review_approval,
    set_threshold,
    write_inventory,
)
from leaveimpact.agent.log_events import Admitted, Producer, decode_event
from leaveimpact.agent.log_store import (
    SCHEMA_VERSION,
    AdmissionReceipt,
    AdmissionRequest,
    LogStore,
    LogStoreConflict,
    LogStoreInvariantBroken,
    LogStoreUnavailable,
)
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import (
    MODEL_SYSTEM_ROLES,
    RoleFilling,
    effective_rules,
)
from leaveimpact.agent.work_order import DATABASE, WorkOrder, perform
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
from leaveimpact.core.pricing import PriceTable, decode_price_table
from leaveimpact.core.registration import Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_record import PricingSelection, SystemKind
from leaveimpact.core.run_timing import GIT_SHA_LENGTH, HarnessRevision, TreeState

PROGRAM = "python -m leaveimpact.agent"
CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"


class Command(StrEnum):
    """The commands the entry offers."""

    ADMIT = "admit"
    WORK = "work"
    REVIEW_APPROVAL = "review-approval"
    DELIVER_APPROVAL = "deliver-approval"
    DECLINE = "decline"
    ABANDON = "abandon"
    PUBLISH = "publish"
    INVENTORY = "inventory"
    SET_THRESHOLD = "set-threshold"
    IMPORT_SPEND = "import-spend"
    BOOTSTRAP_LOG = "bootstrap-log"


@dataclass(frozen=True, slots=True)
class BootstrapLog:
    """The run log's schema bootstrap; the command takes nothing."""


@dataclass(frozen=True, slots=True)
class AdmitFile:
    """The admission request's file, read when the command runs."""

    path: Path


@dataclass(frozen=True, slots=True)
class WorkLine:
    """The work command as the line states it: the attempt with its nonce and launch
    identity, the registered cell (its system kind, condition and level), the registration's
    commit, the filling of the one role the system runs (``None`` for rules only, which runs
    none), the price table's file, the region the clients call from, the harness revision
    this code claims, and who approves. The registration file is the shared flag's."""

    attempt: WorkRequest
    condition: str
    level: str
    system: SystemKind
    registration_commit: str
    role: RoleFilling | None
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
    | ReviewRequest
    | ApprovalDelivery
    | DeclineDelivery
    | AbandonRequest
    | PublishRequest
    | InventoryRequest
    | ThresholdRequest
    | ImportRequest
    | BootstrapLog
)


type Resolved = (
    AdmissionRequest
    | WorkResolved
    | ReviewRequest
    | ApprovalDelivery
    | DeclineDelivery
    | AbandonRequest
    | PublishRequest
    | InventoryRequest
    | ThresholdRequest
    | ImportRequest
    | BootstrapLog
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
    working.add_argument(
        "--system",
        required=True,
        choices=[kind.value for kind in SystemKind],
        help="the registered system the cell belongs to",
    )
    working.add_argument("--registration-commit", required=True, help="the registration's commit")
    # The model flags: required for a system that runs a role, refused for rules only, which
    # runs none; ``_role_filling`` holds both rules, since argparse cannot state them.
    working.add_argument("--model", help="the model id the role's calls run under")
    working.add_argument("--counting-model", help="the base model the requests are counted against")
    working.add_argument(
        "--context-allowance",
        type=int,
        help="the model's input window in tokens; a request over it is refused before any send",
    )
    working.add_argument("--max-tokens", type=int, help="the output maximum")
    working.add_argument("--temperature", type=float, default=None, help="the sampling temperature")
    working.add_argument("--top-p", type=float, default=None, help="the nucleus sampling share")
    working.add_argument("--pricing-key", help="the rate's key in the price table")
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
    commands.add_parser(
        Command.REVIEW_APPROVAL.value,
        parents=[registration, about],
        description="Print the frozen review payload: run only where the output is private.",
    )
    delivering = commands.add_parser(Command.DELIVER_APPROVAL.value, parents=[registration, about])
    delivering.add_argument("--approver", required=True, help="the approver's identity")
    delivering.add_argument("--payload-digest", required=True, help="the payload the approver saw")
    declining = commands.add_parser(Command.DECLINE.value, parents=[registration, about])
    declining.add_argument("--decider", required=True, help="the decider's identity")
    declining.add_argument("--payload-digest", required=True, help="the payload the decider saw")
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
    commands.add_parser(
        Command.BOOTSTRAP_LOG.value,
        description=(
            "Create the run log's tables where missing and check its version; the deploy runs it."
        ),
    )
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
            kind = SystemKind(parsed.system)
            return WorkLine(
                WorkRequest(parsed.run, parsed.attempt, parsed.nonce, parsed.launch),
                parsed.condition,
                parsed.level,
                kind,
                parsed.registration_commit,
                _role_filling(kind, parsed),
                parsed.prices,
                parsed.region,
                HarnessRevision(code_version(env), TreeState(parsed.tree_state)),
                APPROVALS[parsed.approval],
            )
        case Command.REVIEW_APPROVAL:
            return ReviewRequest(parsed.run, parsed.attempt)
        case Command.DELIVER_APPROVAL:
            return ApprovalDelivery(
                parsed.run, parsed.attempt, parsed.approver, parsed.payload_digest
            )
        case Command.DECLINE:
            return DeclineDelivery(
                parsed.run, parsed.attempt, parsed.decider, parsed.payload_digest
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
        case Command.BOOTSTRAP_LOG:
            return BootstrapLog()


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
    (``registered.effective_rules``); with no file, none. An attempt that calls no model is
    read under none whatever the file names (``log_transition.rules_differ``), so one choice
    serves every command, a mixed inventory included.
    """
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


_MODEL_FLAGS = (
    "--model",
    "--counting-model",
    "--context-allowance",
    "--max-tokens",
    "--temperature",
    "--top-p",
    "--pricing-key",
)
_REQUIRED_MODEL_FLAGS = (
    "--model",
    "--counting-model",
    "--context-allowance",
    "--max-tokens",
    "--pricing-key",
)


def _role_filling(kind: SystemKind, parsed: argparse.Namespace) -> RoleFilling | None:
    """The one role's filling from the model flags for a system that runs a role, ``None``
    for rules only; ``ValueError`` naming the flags a rules-only line gives or a model
    system's line lacks."""
    given = {flag: getattr(parsed, flag[2:].replace("-", "_")) for flag in _MODEL_FLAGS}
    if kind is SystemKind.RULES_ONLY:
        offered = [flag for flag, value in given.items() if value is not None]
        if offered:
            raise ValueError(f"rules only runs no model; {', '.join(offered)} refused")
        return None
    missing = [flag for flag in _REQUIRED_MODEL_FLAGS if given[flag] is None]
    if missing:
        raise ValueError(f"{kind.value} runs a model; {', '.join(missing)} required")
    settings = [CallSetting("max_tokens", parsed.max_tokens)]
    for name, value in (("temperature", parsed.temperature), ("top_p", parsed.top_p)):
        if value is not None:
            settings.append(CallSetting(name, value))
    return RoleFilling(
        MODEL_SYSTEM_ROLES[kind].value,
        CallConfiguration(parsed.model, tuple(settings)),
        PricingSelection(parsed.pricing_key, parsed.region, parsed.billing_mode),
        parsed.counting_model,
        parsed.context_allowance,
    )


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
                    f"ledger={request.ledger_id or 'none'}",
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
        case ReviewRequest():
            reviewed = review_approval(request, store, rules=rules)
            if isinstance(reviewed, CommandRefused):
                return _refused(reviewed)
            # The payload is the run's content, printed on purpose for the one reader of a
            # private session; the fields before it are what a delivery needs.
            return 0, [
                f"review={reviewed.run_id}/{reviewed.attempt}",
                f"position={reviewed.position}",
                f"approved={'yes' if reviewed.approved else 'no'}",
                f"payload_digest={reviewed.digest}",
                json.dumps(reviewed.payload, indent=2),
            ]
        case ApprovalDelivery():
            delivered = deliver_approval(request, store, rules=rules)
            if isinstance(delivered, CommandRefused):
                return _refused(delivered)
            return 0, [
                f"approved={delivered.run_id}/{delivered.attempt}",
                f"position={delivered.position}",
            ]
        case DeclineDelivery():
            declined = decline(request, store, rules=rules)
            if isinstance(declined, CommandRefused):
                return _refused(declined)
            return 0, [
                f"declined={declined.run_id}/{declined.attempt}",
                f"position={declined.position}",
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
            publisher = run_export_publisher(world_store_from_env(env))
            record = publish(request, store, publisher, rules=rules)
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
            publisher = inventory_publisher(world_store_from_env(env))
            written = write_inventory(request, store, publisher, rules=rules)
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
        case BootstrapLog():
            store.ensure_schema()
            return 0, ["bootstrapped=log_schema", f"version={SCHEMA_VERSION}"]


def _work(
    request: WorkResolved, store: LogStore, rules: Rules, env: Mapping[str, str]
) -> WorkerEnding:
    """The line's work order performed (``work_order.perform``, where the composition and
    its order live): the line restated as the order, its two decoded files beside it."""
    line = request.line
    order = WorkOrder(
        line.attempt,
        line.system,
        line.condition,
        line.level,
        line.registration_commit,
        line.role,
        line.region,
        line.harness,
        line.approval,
    )
    return perform(
        order, request.registration, request.prices, store=store, rules=rules, env=env
    )


def _refused(refused: CommandRefused) -> tuple[int, list[str]]:
    return 1, [f"refused={refused.subject}", f"reason={refused.reason}"]


if __name__ == "__main__":
    sys.exit(main())
