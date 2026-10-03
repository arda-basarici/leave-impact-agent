"""The evaluation job's two commands, as compositions over readers: prove a world, evaluate its
stored runs.

*Prove* reads nothing but the sealed world and writes nothing. It loads the world from its
three objects, which proves them to be the version named and every sealed key
reproducible by today's rules; it gives the development scenarios, the registered ones
once the registration lists them and the ones its rule draws, by tier alone, while the
list is pending; and it counts, per registered condition, the statements the answers
depend on. A registered list is never redrawn: it survives a change of seed on purpose,
the tuning having been done on those scenarios, and a fresh draw would name scenarios the
evaluator holds out as if they were free to tune on. It is what a first dispatch runs:
the read boundary and the world shown to hold before any run exists to evaluate.

*Evaluate* is the thin shell over the pure function (the investigator milestone's sixth
build step, ruling 7). It refuses a dirty checkout; lists every object stored for the
world's runs and reads each with the version id the store returns, which is the snapshot
the artifact's inventory records; resolves each cited commit to the registration's bytes
there; and publishes the one artifact through the one callable it is handed. A listing
with nothing under it is refused: an evaluation of no run would be an immutable object
that says nothing. An object listed and gone by the time it is read is refused too, the
snapshot no longer being one.

What either command returns is what the job may print. The job's log is public and the
world is sealed, so the results here hold a world version, scenario ids as a flat list,
totals, keys and labels, and never a tier beside an id, a count per tier, a finding or a
cause. The development scenarios are returned in id order with nothing beside them; the
retrieval targets as one total per condition.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.adapters.object_store.layout import evaluation_key, runs_prefix
from leaveimpact.adapters.wiring import ConfigurationError, EvaluationPublisher, ObjectReaders
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.registration import Pending, Registration, ScenarioSetName
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.evaluator.artifact import (
    Disposition,
    Label,
    StoredRun,
    cited_commits,
    evaluation_artifact,
)
from leaveimpact.evaluator.artifact_json import artifact_bytes
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.registered import development_selection, scenario_set
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
    world, which execution."""

    command: Command
    world_version: WorldVersion
    run_id: str
    run_attempt: str


class EvaluationRefused(Exception):
    """The stored runs cannot be evaluated as a snapshot; the message names keys and counts."""


@dataclass(frozen=True, slots=True)
class Proven:
    """A world proven and read for what a first dispatch reports.

    ``development`` are the development scenarios in id order: the registered list, held
    to the registered number from each tier, when ``registered`` says so, and otherwise
    what the registration's rule draws while its list is pending.
    ``targets`` holds, per registered condition in the registration's order, the number of
    statements the answers depend on over all scenarios, or ``None`` when some scenario
    has no answer under the condition, which is not a count of zero.
    """

    world_version: WorldVersion
    scenarios: int
    development: tuple[ScenarioId, ...]
    registered: bool
    targets: tuple[tuple[str, int | None], ...]


@dataclass(frozen=True, slots=True)
class Published:
    """An evaluation as it landed: its key, the version id the store gave it, its label, and
    how many listed objects ended under each disposition, the ones that occur."""

    key: str
    version_id: str
    label: Label
    dispositions: tuple[tuple[Disposition, int], ...]


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
    return EvaluationRequest(
        Command(parsed.command),
        WorldVersion(parsed.world_version),
        parsed.run_id,
        parsed.run_attempt,
    )


def prove(version: WorldVersion, stores: ObjectReaders, registration: Registration) -> Proven:
    """The sealed world ``version`` loaded and proven, with the development scenarios
    ``registration`` lists, or draws while its list is pending, and the retrieval targets
    counted per registered condition.

    Raises ``SealedWorldRefused`` when the three objects are not that world, and
    ``ValueError`` for a registered development list the world's tiers do not fit.
    """
    world = load_sealed_world(version, stores.truth, stores.world)
    targets = tuple(
        (
            condition.id,
            _targets(world, RunCondition.all_reachable().without(*condition.unreachable)),
        )
        for condition in registration.outage.conditions
    )
    listed = registration.scenario_sets.development
    if isinstance(listed, Pending):
        development, registered = development_selection(world, registration), False
    else:
        # Cutting the primary set is what holds the list to the world and to its tiers.
        scenario_set(world, registration, ScenarioSetName.PRIMARY)
        development, registered = listed, True
    return Proven(world.version, len(world.scenarios), development, registered, targets)


def evaluate(
    request: EvaluationRequest,
    stores: ObjectReaders,
    publish: EvaluationPublisher,
    repository: Repository,
) -> Published:
    """Evaluate every object stored for the runs of the requested world and publish the
    artifact.

    Raises ``RepositoryRefused`` for a dirty checkout or one with no registration,
    ``EvaluationRefused`` for an empty or a moving listing, and whatever the artifact
    refuses: a registration it cannot read as a plan, two eligible exports of one run.
    """
    repository.require_clean()
    head = repository.head()
    registration = repository.file_at(head, REGISTRATION_PATH)
    if registration is None:
        raise RepositoryRefused(f"the checkout holds no {REGISTRATION_PATH}")
    version = request.world_version
    world = load_sealed_world(version, stores.truth, stores.world)
    runs = _stored_runs(stores, version)
    registrations_at = {
        commit: repository.file_at(commit, REGISTRATION_PATH) for commit in cited_commits(runs)
    }
    artifact = evaluation_artifact(
        world, registration, runs, registrations_at, evaluator_revision(repository)
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
    )


def registration_of(repository: Repository) -> Registration:
    """The registration as the checkout's working tree holds it, decoded."""
    try:
        content = (repository.root / REGISTRATION_PATH).read_bytes()
    except OSError as error:
        raise RepositoryRefused(f"the checkout holds no readable {REGISTRATION_PATH}") from error
    return decode_registration_bytes(content)


def _stored_runs(stores: ObjectReaders, version: WorldVersion) -> tuple[StoredRun, ...]:
    """Every object under the world's runs prefix, each read once with its version id."""
    keys = stores.world.list_keys(runs_prefix(version))
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
