"""``python -m leaveimpact.launch <command> ...``: the launcher's two commands, run inside
the deployed image on the instance by a dispatched workflow's sends (the first live run's
step, fork 1).

``plan`` reads the registration and the price table from the files named, the scenario's
specification from the world store under the ``LEAVE_IMPACT_*`` names, builds the plan
(``launch.plan.plan_run``), draws the launch identity, and writes two files under ``--out``:
``request.json``, the admission request the agent's ``admit`` command reads (the request
identity and the admitter the caller gives, the ledger, and the frozen inputs as the
admission event encodes them), and ``work.args``, the work command's cell and role flags one
per line, for the send to append after the execution's own. The request identity is the
caller's and is held across transport retries, so a second send of the same file is the
store's receipt; the run id and the attempt number are the caller's too, and only the
launch identity is drawn here, as the job seam's three identities require.

``status`` loads one attempt's state from the run log under the registration's rules and
prints it as fields (open or closed with its ending, the segment, the approval, a recorded
stop, the generation) with the lifecycle's next step for the recoveries the caller counts
and the approval policy the run was dispatched under (``launch.plan.next_step``). The
workflow reads it between sends and after a completion the transport reported uncertainly.

The job's log is public, which decides what is printed: identities, counts, kinds, file
names and the scenario id (the development protocol lists the ids as bare ids). A
scenario's leave, instant and window are in the request file and never on the log; a file
or object that does not decode is reported by its name and the exception's type, since a
codec's refusal quotes what it refused. Exit status as the agent's entry: 0 for a result,
1 for a refusal, 2 for a configuration fault, 3 for anything unexpected.
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
from uuid import uuid4

from leaveimpact.adapters.object_store.layout import scenario_specs_key
from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.wiring import ConfigurationError, world_store_from_env, world_store_reader
from leaveimpact.agent.log_events import Admitted, encode_event, kind_of
from leaveimpact.agent.log_store import (
    LogStore,
    LogStoreConflict,
    LogStoreInvariantBroken,
    LogStoreUnavailable,
)
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.agent.registered import effective_rules
from leaveimpact.agent.worker import ApprovalPolicy, AutomaticApproval, HumanApproval
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.pricing import decode_price_table
from leaveimpact.core.registration import Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_record import SystemKind
from leaveimpact.launch.plan import RunCell, next_step, plan_run, work_arguments
from leaveimpact.world.decoders import decode_scenario_specs
from leaveimpact.world.scenario import ScenarioSpec

PROGRAM = "python -m leaveimpact.launch"
DATABASE = "DATABASE_URL"
REQUEST_FILE = "request.json"
WORK_ARGUMENTS_FILE = "work.args"
APPROVALS: Mapping[str, ApprovalPolicy] = {
    "automatic": AutomaticApproval(),
    "human": HumanApproval(),
}
"""The approval policies by the work line's word (the agent's entry names the same two)."""


class Command(StrEnum):
    """The commands the launcher offers."""

    PLAN = "plan"
    STATUS = "status"


@dataclass(frozen=True, slots=True)
class PlanLine:
    """The plan command as the line states it."""

    world_version: WorldVersion
    scenario: ScenarioId
    cell: RunCell
    registration: Path
    registration_commit: str
    prices: Path
    region: str
    billing_mode: str
    run_id: str
    attempt: int
    request_id: str
    admitter: str
    ledger: str | None
    out: Path


@dataclass(frozen=True, slots=True)
class StatusLine:
    """The status command as the line states it."""

    run_id: str
    attempt: int
    registration: Path
    approval: ApprovalPolicy


_REFUSALS = (
    LogStoreUnavailable,
    LogStoreInvariantBroken,
    LogStoreConflict,
    AccessRefused,
    ObjectStoreUnreachable,
    ObjectStoreMisconfigured,
    ValueError,
)
"""The failures whose message is written to be printed: the store's, and the plan's own
refusals, which name registration parts, ids and counts."""


# --- The request ---------------------------------------------------------------------------


def parse_request(argv: Sequence[str]) -> PlanLine | StatusLine:
    """The command from ``argv``; ``ConfigurationError`` names what is missing or malformed."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="The launcher's commands.", exit_on_error=False
    )
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser(Command.PLAN.value)
    planning.add_argument("--world-version", required=True, help="the world the run is on")
    planning.add_argument("--scenario", required=True, help="the scenario id")
    planning.add_argument(
        "--system", required=True, choices=[kind.value for kind in SystemKind], help="the system"
    )
    planning.add_argument("--condition", required=True, help="the registered condition")
    planning.add_argument("--level", required=True, help="the registered corpus level")
    planning.add_argument("--registration", required=True, type=Path, help="the registration file")
    planning.add_argument("--registration-commit", required=True, help="its commit")
    planning.add_argument("--prices", required=True, type=Path, help="the price table's file")
    planning.add_argument("--region", required=True, help="the region the clients call from")
    planning.add_argument("--billing-mode", default="on_demand", help="the rate's billing mode")
    planning.add_argument("--run", required=True, help="the run id")
    planning.add_argument("--attempt", required=True, type=int, help="the attempt number")
    planning.add_argument(
        "--request-id", required=True, help="the request identity, held across retries"
    )
    planning.add_argument("--admitter", required=True, help="the admitter's identity")
    planning.add_argument(
        "--ledger", default=None, help="the ledger reserved against; none for rules only"
    )
    planning.add_argument("--out", required=True, type=Path, help="the directory written to")
    status = commands.add_parser(Command.STATUS.value)
    status.add_argument("--run", required=True, help="the run id")
    status.add_argument("--attempt", required=True, type=int, help="the attempt number")
    status.add_argument("--registration", required=True, type=Path, help="the registration file")
    status.add_argument(
        "--approval",
        required=True,
        choices=sorted(APPROVALS),
        help="the approval policy the work command was dispatched with",
    )
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(f"the command line is not a command: {error}") from error
    if Command(parsed.command) is Command.STATUS:
        return StatusLine(
            parsed.run,
            parsed.attempt,
            parsed.registration,
            APPROVALS[parsed.approval],
        )
    kind = SystemKind(parsed.system)
    if kind is SystemKind.RULES_ONLY and parsed.ledger is not None:
        raise ConfigurationError("rules only reserves nothing and is admitted against no ledger")
    if kind is not SystemKind.RULES_ONLY and parsed.ledger is None:
        raise ConfigurationError(f"{kind.value} reserves against a ledger: --ledger")
    return PlanLine(
        WorldVersion(parsed.world_version),
        ScenarioId(parsed.scenario),
        RunCell(kind, parsed.condition, parsed.level),
        parsed.registration,
        parsed.registration_commit,
        parsed.prices,
        parsed.region,
        parsed.billing_mode,
        parsed.run,
        parsed.attempt,
        parsed.request_id,
        parsed.admitter,
        parsed.ledger,
        parsed.out,
    )


# --- The execution -------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: LogStore | None = None,
) -> int:
    """Run one command; ``env`` defaults to the process's environment and ``store``, for
    ``status``, to one over ``DATABASE_URL``."""
    environment = os.environ if env is None else env
    try:
        line = parse_request(sys.argv[1:] if argv is None else argv)
        registration = _decoded(
            line.registration,
            "the registration",
            lambda path: decode_registration_bytes(path.read_bytes()),
        )
        if isinstance(line, StatusLine) and store is None:
            dsn = environment.get(DATABASE, "").strip()
            if not dsn:
                raise ConfigurationError(f"{DATABASE} names the run log's database")
            store = LogStore(dsn=dsn)
    except ConfigurationError as error:
        print(f"leaveimpact.launch: {error}", file=sys.stderr)
        return 2
    try:
        if isinstance(line, StatusLine):
            assert store is not None
            try:
                lines = _status(line, registration, store)
            finally:
                store.close()
        else:
            lines = _plan(line, registration, environment)
    except ConfigurationError as error:
        print(f"leaveimpact.launch: {error}", file=sys.stderr)
        return 2
    except _REFUSALS as refusal:
        print(f"leaveimpact.launch: refused: {refusal}", file=sys.stderr)
        return 1
    except Exception as unexpected:
        print(
            f"leaveimpact.launch: failed with {type(unexpected).__name__}; the traceback is "
            "withheld because this log is public",
            file=sys.stderr,
        )
        return 3
    for printed in lines:
        print(printed)
    return 0


def _plan(line: PlanLine, registration: Registration, env: Mapping[str, str]) -> list[str]:
    prices = _decoded(
        line.prices,
        "the price table",
        lambda path: decode_price_table(json.loads(path.read_bytes())),
    )
    spec = _specification(line.world_version, line.scenario, env)
    plan = plan_run(
        registration,
        registration_commit=line.registration_commit,
        prices=prices,
        cell=line.cell,
        spec=spec,
        world_version=line.world_version,
        run_id=line.run_id,
        attempt=line.attempt,
        region=line.region,
        billing_mode=line.billing_mode,
    )
    arguments = work_arguments(plan)
    launch = f"launch-{uuid4().hex}"
    request = {
        "request_id": line.request_id,
        "admitter": line.admitter,
        "ledger_id": line.ledger,
        "admitted": encode_event(Admitted(plan.inputs)),
    }
    line.out.mkdir(parents=True, exist_ok=True)
    request_file = line.out / REQUEST_FILE
    request_file.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    arguments_file = line.out / WORK_ARGUMENTS_FILE
    arguments_file.write_text("\n".join(arguments) + "\n", encoding="utf-8")
    return [
        f"launch={launch}",
        f"run={line.run_id}",
        f"attempt={line.attempt}",
        f"scenario={line.scenario}",
        f"world_version={line.world_version}",
        f"system={line.cell.system.value}",
        f"reservation_pico_usd={plan.inputs.reservation_pico_usd}",
        f"request={request_file}",
        f"work_arguments={arguments_file}",
    ]


def _specification(
    version: WorldVersion, scenario: ScenarioId, env: Mapping[str, str]
) -> ScenarioSpec:
    """The specification of ``scenario`` on ``version`` from the world store: the question
    the run is asked, which the instance role may read; a specs object that does not decode
    is reported by its key and the exception's type."""
    reader = world_store_reader(world_store_from_env(env))
    key = scenario_specs_key(version)
    stored = reader.get(key)
    if stored is None:
        raise ValueError(f"the world store holds no scenario specs at {key}")
    specs: tuple[ScenarioSpec, ...] | None = None
    failure: str | None = None
    try:
        specs = decode_scenario_specs(stored.content)
    except ValueError as error:
        failure = type(error).__name__
    if specs is None:
        raise ValueError(f"the scenario specs at {key} do not decode ({failure})")
    for spec in specs:
        if spec.id == scenario:
            return spec
    raise ValueError(f"world {version} has no scenario {scenario}")


def _status(line: StatusLine, registration: Registration, store: LogStore) -> list[str]:
    state = store.load(line.run_id, line.attempt, rules=_rules_of(registration))
    return status_lines(state, approval=line.approval)


def status_lines(state: AttemptState, *, approval: ApprovalPolicy) -> list[str]:
    """The attempt's state as the fields the job seam exposes, the recoveries its log
    counts, the world version and registration commit it was admitted under (the
    inventory's scope, which the driver hands on so a continuation needs nothing the host
    kept), and the lifecycle's next step under ``approval``."""
    inputs = state.inputs
    if inputs is None:
        raise ValueError("an attempt with no admission has no status")
    closing = state.closing
    segment = state.current_segment
    approval_state = (
        "none"
        if state.approval_requested is None
        else "approved"
        if state.approved is not None
        else "requested"
    )
    return [
        f"attempt={'closed' if closing is not None else 'open'}",
        f"ending={kind_of(closing).value if closing is not None else 'none'}",
        f"segment={'none' if segment is None else 'ended' if segment.ended else 'open'}",
        f"approval={approval_state}",
        f"stopped={'true' if state.stopped is not None else 'false'}",
        f"generation={state.generation}",
        f"recoveries={state.recoveries}",
        f"world_version={inputs.context.world_version}",
        f"registration_commit={inputs.preregistration_commit}",
        f"next={next_step(state, approval=approval).value}",
    ]


def _rules_of(registration: Registration) -> Rules:
    return effective_rules(registration)


def _decoded[T](path: Path, what: str, decode: Callable[[Path], T]) -> T:
    """``decode(path)``, a failure to read or decode the file reported by its name and the
    exception's type and never its message, which quotes what the file held."""
    try:
        return decode(path)
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            f"{what} {path} does not read or decode ({type(error).__name__})"
        ) from None


if __name__ == "__main__":
    sys.exit(main())
