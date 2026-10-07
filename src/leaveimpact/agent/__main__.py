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
``abandon``, ``publish``, ``inventory`` and ``set-threshold`` take their fields as flags.
``work`` waits for the first composition it could run, the investigator graph's.

The job's log is public, which decides what this module prints: a result as the fields its
command returns, a refusal of a known kind as its message (files, keys, commits, counts
and reasons the store wrote to be printed, nothing sealed), and anything else as the name
of its type with no traceback. Exit status: 0 for a result, 1 for a refusal, 2 for a
configuration fault, 3 for anything unexpected.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    inventory_publisher,
    run_export_publisher,
    stores_from_env,
)
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    CommandRefused,
    InventoryRequest,
    PublishRequest,
    ThresholdRequest,
    abandon,
    admit,
    deliver_approval,
    publish,
    set_threshold,
    write_inventory,
)
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
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import InventoryScope
from leaveimpact.core.jsonshape import as_object, expect_fields, object_field, string_field
from leaveimpact.core.registration import Pending
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_timing import GIT_SHA_LENGTH

PROGRAM = "python -m leaveimpact.agent"
DATABASE = "DATABASE_URL"
CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"


class Command(StrEnum):
    """The commands the entry offers; ``work`` is the investigator graph step's."""

    ADMIT = "admit"
    DELIVER_APPROVAL = "deliver-approval"
    ABANDON = "abandon"
    PUBLISH = "publish"
    INVENTORY = "inventory"
    SET_THRESHOLD = "set-threshold"


@dataclass(frozen=True, slots=True)
class AdmitFile:
    """The admission request's file, read when the command runs."""

    path: Path


type Request = (
    AdmitFile
    | ApprovalDelivery
    | AbandonRequest
    | PublishRequest
    | InventoryRequest
    | ThresholdRequest
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
    ValueError,
)
"""The failures whose message is written to be printed; a ``ValueError`` is the store's or
a codec's refusal naming ids, positions, fields and counts."""


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


def code_version(env: Mapping[str, str]) -> str:
    """The commit this code runs as, from the image's identity variable."""
    version = env.get(CODE_VERSION, "").strip()
    if len(version) != GIT_SHA_LENGTH:
        raise ValueError(
            f"{CODE_VERSION} is the forty-hex commit this code runs as, got {version!r}"
        )
    return version


def rules_of(registration: Path | None) -> Rules:
    """The registered attribution table and re-dispatch policy from the registration file,
    each ``None`` while pending; with no file, the rules of a system that calls no model."""
    if registration is None:
        return Rules(None, None)
    decoded = decode_registration_bytes(registration.read_bytes())
    table = decoded.attribution
    policy = decoded.run_accounting.redispatch
    return Rules(
        None if isinstance(table, Pending) else table,
        None if isinstance(policy, Pending) else policy,
    )


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
        rules = rules_of(parsed.registration)
        if store is None:
            dsn = environment.get(DATABASE, "").strip()
            if not dsn:
                raise ConfigurationError(f"{DATABASE} names the run log's database")
            store = LogStore(dsn=dsn)
    except (ConfigurationError, OSError, ValueError) as error:
        print(f"leaveimpact.agent: {error}", file=sys.stderr)
        return 2
    try:
        lines = _run(parsed, store, rules, environment)
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
    return 0


def _run(parsed: Parsed, store: LogStore, rules: Rules, env: Mapping[str, str]) -> list[str]:
    request = parsed.request
    match request:
        case AdmitFile(path):
            result = admit(admission_request_of(path.read_bytes(), rules), store)
            if isinstance(result, AdmissionReceipt):
                return [
                    f"admitted={result.run_id}/{result.attempt}",
                    f"recorded_at={result.recorded_at.isoformat()}",
                    f"ledger_revision={result.ledger_revision}",
                ]
            return [f"refused={result.run_id}/{result.attempt}", f"reason={result.reason}"]
        case ApprovalDelivery():
            delivered = deliver_approval(request, store, rules=rules)
            if isinstance(delivered, CommandRefused):
                return _refused(delivered)
            return [
                f"approved={delivered.run_id}/{delivered.attempt}",
                f"position={delivered.position}",
            ]
        case AbandonRequest():
            closed = abandon(request, store, rules=rules)
            if isinstance(closed, CommandRefused):
                return _refused(closed)
            return [
                f"abandoned={closed.run_id}/{closed.attempt}",
                f"generation_fenced={closed.generation_fenced}",
                f"position={closed.position}",
            ]
        case PublishRequest():
            stores = stores_from_env(env)
            record = publish(request, store, run_export_publisher(stores), rules=rules)
            if isinstance(record, CommandRefused):
                return _refused(record)
            return [
                f"publication={record.run_id}/{record.attempt}",
                f"state={record.state.value}",
                f"object_identity={record.object_identity}",
                f"object_digest={record.object_digest}",
                f"incident={record.incident}",
            ]
        case InventoryRequest():
            stores = stores_from_env(env)
            written = write_inventory(request, store, inventory_publisher(stores), rules=rules)
            return [
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
            return [
                f"threshold={request.ledger_id}",
                f"revision={entry.revision}",
                f"amount_pico_usd={entry.amount_pico_usd}",
            ]


def _refused(refused: CommandRefused) -> list[str]:
    return [f"refused={refused.subject}", f"reason={refused.reason}"]


if __name__ == "__main__":
    sys.exit(main())
