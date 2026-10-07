"""The evaluation job's two commands, as compositions over readers: prove a world, evaluate its
stored runs.

*Prove* reads nothing but the sealed world and writes nothing. It loads the world from its
three objects, which proves them to be the version named and every sealed key
reproducible by today's rules, and it counts, per registered condition, the statements the
answers depend on. It draws no scenario: the registration tunes on none of its world's. It
is what a first dispatch runs: the read boundary and the world shown to hold before any
run exists to evaluate.

*Evaluate* is the thin shell over the pure function (the investigator milestone's sixth
build step, ruling 7). It refuses a dirty checkout; holds a bound registration to its
world and to the frozen registration it names, read at that commit, before anything is
listed; reads the harness inventory the request names by digest, verified against its name
and refused when absent, misnamed, undecodable or of another world (the event log step's
ruling on the job seam, part 6); lists every object stored for the world's runs outside
the inventory prefix and reads each with the version id the store returns, which is the
snapshot the artifact's listing records; resolves each cited commit and each admitting
commit to the registration's bytes there; and publishes the one artifact through the one
callable it is handed. A listing with nothing under it is refused: an evaluation of no
run would be an immutable object that says nothing. An object listed and gone by the time
it is read is refused too, the snapshot no longer being one; so is a published object the
inventory lists that the listing lacks or holds with other bytes, and a reported
evaluation while an attempt in its scope is open (the artifact's two refusals).

What either command returns is what the job may print. The job's log is public and the
world is sealed, so the results here hold a world version, totals, keys and labels, and
never a scenario's tier, a count per tier, a finding or a cause. The retrieval targets are
one total per condition.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.adapters.object_store.layout import evaluation_key, inventory_key, runs_prefix
from leaveimpact.adapters.wiring import ConfigurationError, EvaluationPublisher, ObjectReaders
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import Inventory
from leaveimpact.core.registration import Registration, RegistrationStatus
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.evaluator.artifact import (
    Disposition,
    Label,
    StoredRun,
    cited_commits,
    evaluation_artifact,
    require_binding,
)
from leaveimpact.evaluator.artifact_json import artifact_bytes
from leaveimpact.evaluator.harness_inventory import (
    HarnessCoverage,
    HarnessInventoryRead,
    is_inventory_object,
    read_inventory,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.repository import (
    REGISTRATION_PATH,
    Repository,
    RepositoryRefused,
    evaluator_revision,
)
from leaveimpact.evaluator.retrieval_targets import retrieval_targets
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.world.artifacts import SHA256_HEX


class Command(StrEnum):
    """What the job is asked to do."""

    PROVE = "prove"
    EVALUATE = "evaluate"


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    """What the command line and the runner's identifiers define: which command, which
    world, which execution, and for an evaluation the harness inventory it reads, by its
    digest (``None`` for a proof, which reads none)."""

    command: Command
    world_version: WorldVersion
    run_id: str
    run_attempt: str
    inventory: str | None


class EvaluationRefused(Exception):
    """The stored runs cannot be evaluated as a snapshot, or the registration is bound to
    another world or to a procedure nobody froze; the message names keys, counts, commits,
    world versions and the registration's sections."""


@dataclass(frozen=True, slots=True)
class Proven:
    """A world proven and read for what a first dispatch reports.

    ``targets`` holds, per registered condition in the registration's order, the number of
    statements the answers depend on over all scenarios, or ``None`` when some scenario
    has no answer under the condition, which is not a count of zero.
    """

    world_version: WorldVersion
    scenarios: int
    targets: tuple[tuple[str, int | None], ...]


@dataclass(frozen=True, slots=True)
class Published:
    """An evaluation as it landed: its key, the version id the store gave it, its label,
    how many listed objects ended under each disposition, the ones that occur, the harness
    inventory it was held to and the coverage that inventory gives."""

    key: str
    version_id: str
    label: Label
    dispositions: tuple[tuple[Disposition, int], ...]
    harness_inventory: HarnessInventoryRead
    coverage: HarnessCoverage


def parse_request(argv: Sequence[str], env: Mapping[str, str]) -> EvaluationRequest:
    """The request from ``argv``, the run's identifiers from the flags or ``GITHUB_RUN_*``."""
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.evaluator",
        description="Prove a sealed world, or evaluate the runs stored for it.",
        exit_on_error=False,
    )
    parser.add_argument("command", choices=[command.value for command in Command])
    parser.add_argument("--world-version", required=True, help="the 64-hex world version")
    parser.add_argument("--run-id", default=env.get("GITHUB_RUN_ID", "").strip())
    parser.add_argument("--run-attempt", default=env.get("GITHUB_RUN_ATTEMPT", "").strip())
    parser.add_argument(
        "--inventory", default=None, help="the 64-hex digest of the harness inventory to read"
    )
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(
            f"the command line is not an evaluation request: {error}"
        ) from error
    if not SHA256_HEX.fullmatch(parsed.world_version):
        raise ConfigurationError(
            f"--world-version is a 64-hex world version, got {parsed.world_version!r}"
        )
    for name, value in (("--run-id", parsed.run_id), ("--run-attempt", parsed.run_attempt)):
        if not value or "/" in value:
            raise ConfigurationError(
                f"{name} is required (or GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT in the environment) "
                f"and carries no slash, got {value!r}"
            )
    command = Command(parsed.command)
    inventory: str | None = parsed.inventory
    if command is Command.EVALUATE and inventory is None:
        raise ConfigurationError("evaluate names the harness inventory it reads: --inventory")
    if inventory is not None and not SHA256_HEX.fullmatch(inventory):
        raise ConfigurationError(f"--inventory is a 64-hex digest, got {inventory!r}")
    return EvaluationRequest(
        command,
        WorldVersion(parsed.world_version),
        parsed.run_id,
        parsed.run_attempt,
        inventory,
    )


def prove(version: WorldVersion, stores: ObjectReaders, registration: Registration) -> Proven:
    """The sealed world ``version`` loaded and proven, with the retrieval targets counted
    per condition ``registration`` holds.

    Raises ``SealedWorldRefused`` when the three objects are not that world.
    """
    world = load_sealed_world(version, stores.truth, stores.world)
    targets = tuple(
        (
            condition.id,
            _targets(world, RunCondition.all_reachable().without(*condition.unreachable)),
        )
        for condition in registration.outage.conditions
    )
    return Proven(world.version, len(world.scenarios), targets)


def evaluate(
    request: EvaluationRequest,
    stores: ObjectReaders,
    publish: EvaluationPublisher,
    repository: Repository,
) -> Published:
    """Evaluate every object stored for the runs of the requested world and publish the
    artifact.

    Raises ``RepositoryRefused`` for a dirty checkout or one with no registration,
    ``EvaluationRefused`` for a request naming no inventory or one that is absent,
    misnamed, undecodable or of another world, for an empty or a moving listing and for a
    bound registration that binds another world or a procedure other than the frozen one
    it names, and whatever the artifact refuses: a registration it cannot read as a plan,
    a listed publication the store does not hold as recorded, an open attempt under a
    reported label, two eligible exports of one run.
    """
    repository.require_clean()
    head = repository.head()
    registration = repository.file_at(head, REGISTRATION_PATH)
    if registration is None:
        raise RepositoryRefused(f"the checkout holds no {REGISTRATION_PATH}")
    version = request.world_version
    _require_bound_as_frozen(decode_registration_bytes(registration), version, repository)
    inventory, inventory_read = _named_inventory(stores, version, request.inventory)
    world = load_sealed_world(version, stores.truth, stores.world)
    runs = _stored_runs(stores, version)
    registrations_at = {
        commit: repository.file_at(commit, REGISTRATION_PATH)
        for commit in cited_commits(runs, inventory)
    }
    artifact = evaluation_artifact(
        world,
        registration,
        runs,
        registrations_at,
        evaluator_revision(repository),
        inventory=inventory,
        inventory_read=inventory_read,
    )
    version_id = publish(version, request.run_id, request.run_attempt, artifact_bytes(artifact))
    tally = Counter(entry.disposition for entry in artifact.inventory)
    return Published(
        evaluation_key(version, request.run_id, request.run_attempt),
        version_id,
        artifact.label,
        tuple(
            (disposition, tally[disposition]) for disposition in Disposition if tally[disposition]
        ),
        artifact.harness_inventory,
        artifact.coverage,
    )


def registration_of(repository: Repository) -> Registration:
    """The registration as the checkout's working tree holds it, decoded."""
    try:
        content = (repository.root / REGISTRATION_PATH).read_bytes()
    except OSError as error:
        raise RepositoryRefused(f"the checkout holds no readable {REGISTRATION_PATH}") from error
    return decode_registration_bytes(content)


def _require_bound_as_frozen(
    registration: Registration, version: WorldVersion, repository: Repository
) -> None:
    """Refuse a bound ``registration`` that binds a world other than ``version``, or whose
    procedure is not the one frozen at the commit it names. Before anything is listed: an
    evaluation under it would be labelled reported."""
    commit = registration.world.frozen_commit
    if registration.status is not RegistrationStatus.BOUND or commit is None:
        return
    if registration.world.version != version:
        raise EvaluationRefused(
            f"the registration is bound to the world {registration.world.version}, and the "
            f"evaluation asked for is of {version}"
        )
    try:
        require_binding(registration, repository.file_at(commit, REGISTRATION_PATH))
    except ValueError as refused:
        reason = str(refused)
    else:
        return
    # Raised after the handler has ended, so the decoder's own exception, whose message may
    # quote the file, is no part of what a traceback prints.
    raise EvaluationRefused(reason)


def _named_inventory(
    stores: ObjectReaders, version: WorldVersion, digest: str | None
) -> tuple[Inventory, HarnessInventoryRead]:
    """The harness inventory ``digest`` names for ``version``, read from the world store and
    verified; refused by name when the request names none or the object is not there."""
    if digest is None:
        raise EvaluationRefused("an evaluation names the harness inventory it reads, and none was")
    key = inventory_key(version, digest)
    stored = stores.world.get(key)
    if stored is None:
        raise EvaluationRefused(f"no harness inventory is stored at {key}")
    try:
        return read_inventory(version, digest, stored.content)
    except ValueError as refused:
        reason = str(refused)
    # Raised after the handler has ended: the decoder's message names a field and no value,
    # and nothing of the object reaches a traceback.
    raise EvaluationRefused(reason)


def _stored_runs(stores: ObjectReaders, version: WorldVersion) -> tuple[StoredRun, ...]:
    """Every object under the world's runs prefix outside the inventory prefix, each read
    once with its version id."""
    keys = [
        key
        for key in stores.world.list_keys(runs_prefix(version))
        if not is_inventory_object(version, key)
    ]
    if not keys:
        raise EvaluationRefused(
            f"nothing is stored under {runs_prefix(version)}: there is no run to evaluate"
        )
    runs: list[StoredRun] = []
    for key in keys:
        stored = stores.world.get(key)
        if stored is None:
            raise EvaluationRefused(f"{key} was listed and is gone: the listing is no snapshot")
        runs.append(StoredRun(key, stored.version_id, stored.content))
    return tuple(runs)


def _targets(world: SealedWorld, condition: RunCondition) -> int | None:
    """How many statements the answers depend on under ``condition`` over every scenario,
    or ``None`` when a scenario has no answer there."""
    total = 0
    for scenario in world.scenarios:
        answer = oracle_for(world, scenario, condition)
        if not isinstance(answer, Answerable):
            return None
        total += len(retrieval_targets(world, answer))
    return total


__all__ = [
    "Command",
    "EvaluationRefused",
    "EvaluationRequest",
    "Proven",
    "Published",
    "evaluate",
    "parse_request",
    "prove",
    "registration_of",
]
