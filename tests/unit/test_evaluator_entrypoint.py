"""The evaluation job's entry point. A request takes a command, a world version and the runner's
identifiers. Proving a world returns the development scenarios as a flat list and one total
of retrieval targets per registered condition, and the job prints those and nothing sealed,
writing nothing. Evaluating publishes one artifact over every object stored for the world's
runs, from a clean checkout, each cited commit resolved in the checkout's own history; a
dirty tree, an empty listing and a world that is not there are refused by name, and an
unexpected failure prints its type and no traceback. The checkout is read through git: a
file at a commit as committed, absent for a commit or a path that is not there, and the
implementation paths that changed between two commits."""

import json
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.layout import (
    evaluation_key,
    evaluations_prefix,
    runs_prefix,
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.wiring import ConfigurationError, ObjectReaders
from leaveimpact.agent.export import export_rules_only_run
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    HarnessRevision,
    Pending,
    PricingBasis,
    TreeState,
    condition_id,
    decode_registration_bytes,
    export_bytes,
    registration_bytes,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator import __main__ as job
from leaveimpact.evaluator.entrypoint import Command, parse_request, prove
from leaveimpact.evaluator.registered import development_selection
from leaveimpact.evaluator.repository import (
    IMPLEMENTATION,
    REGISTRATION_PATH,
    Repository,
    RepositoryRefused,
    evaluator_revision,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario, bundle
from leaveimpact.world.scenario import ScenarioClassName, Tier
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import composed_world, loaded_world

DIGEST = "a" * 64
ABSENT_COMMIT = "c" * 40
RUNNER = {"GITHUB_RUN_ID": "77", "GITHUB_RUN_ATTEMPT": "1"}

_COMMITTED = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / REGISTRATION_PATH).read_bytes()
)
# The registered resample count buys precision these tests do not need.
DRAFT = replace(_COMMITTED, statistics=replace(_COMMITTED.statistics, resamples=200))
DRAFT_BYTES = registration_bytes(DRAFT)


def git(root: Path, *arguments: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.org"]
        + list(arguments),
        check=True,
        capture_output=True,
    )
    return done.stdout.decode().strip()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def checkout(tmp_path: Path) -> Repository:
    """A checkout with the registration and one file of the evaluator's implementation,
    committed once."""
    root = tmp_path / "checkout"
    registration = root / REGISTRATION_PATH
    module = root / "src" / "leaveimpact" / "evaluator" / "tables.py"
    for path, content in ((registration, DRAFT_BYTES), (module, b"FIRST = 1\n")):
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
    (root / "pyproject.toml").write_bytes(b"[project]\n")
    git(root, "init", "--quiet")
    git(root, "config", "core.autocrlf", "false")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "the registration")
    return Repository(root)


@pytest.fixture
def twin(tmp_path: Path) -> Path:
    """The local twin's root, holding the throwaway world's three sealed files."""
    root = tmp_path / "stores"
    sealed = bundle(composed_world())
    version = sealed.world_version
    truth, held = LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    truth.put_if_absent(world_spec_key(version), sealed.world_spec.content)
    truth.put_if_absent(truth_manifest_key(version), sealed.truth_manifest.content)
    held.put_if_absent(scenario_specs_key(version), sealed.scenario_specs.content)
    return root


def environment(twin: Path) -> dict[str, str]:
    return {"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(twin), **RUNNER}


def stores(twin: Path) -> ObjectReaders:
    return ObjectReaders(LocalObjectReader(twin / "truth"), LocalObjectReader(twin / "world"))


def export_of(world: SealedWorld, scenario: Scenario, commit: str, run_id: str) -> bytes:
    """The real baseline's export of ``scenario``, citing the registration at ``commit``."""
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        DRAFT,
        condition_id(()),
        harness=HarnessRevision(commit, TreeState.CLEAN),
        preregistration_commit=commit,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    run = investigate(context, systems_holding(world).ports)
    return export_bytes(
        export_rules_only_run(run, context, provenance, run_id=run_id, attempt=1, duration_ms=1_200)
    )


def store_runs(twin: Path, world: SealedWorld, **runs: bytes) -> None:
    writer = LocalObjectWriter(twin / "world")
    for name, content in runs.items():
        writer.put_if_absent(f"{runs_prefix(world.version)}{name}/export.json", content)


def run_job(
    capsys: pytest.CaptureFixture[str], twin: Path, checkout: Repository, *argv: str
) -> tuple[int, str, str]:
    status = job.main(argv, environment(twin), checkout.root)
    captured = capsys.readouterr()
    return status, captured.out, captured.err


# --- The request -------------------------------------------------------------------------------


def test_a_request_takes_a_command_the_version_and_the_runners_identifiers() -> None:
    version = "ab" * 32
    request = parse_request(["prove", "--world-version", version], RUNNER)
    assert (request.command, request.world_version) == (Command.PROVE, version)
    assert (request.run_id, request.run_attempt) == ("77", "1")
    given = parse_request(
        ["evaluate", "--world-version", version, "--run-id", "9", "--run-attempt", "2"], {}
    )
    assert (given.command, given.run_id, given.run_attempt) == (Command.EVALUATE, "9", "2")
    for argv, env in (
        (["grade", "--world-version", version], RUNNER),
        (["prove", "--world-version", "abc"], RUNNER),
        (["prove", "--world-version", version], {}),
        (["prove", "--world-version", version, "--run-id", "a/b"], RUNNER),
    ):
        with pytest.raises(ConfigurationError):
            parse_request(argv, env)


# --- Proving a world ---------------------------------------------------------------------------


def test_proving_a_world_selects_the_development_scenarios_and_counts_the_targets(
    world: SealedWorld, twin: Path
) -> None:
    proven = prove(world.version, stores(twin), DRAFT)
    assert (proven.world_version, proven.scenarios) == (world.version, 30)
    assert proven.development == development_selection(world, DRAFT)
    assert len(proven.development) == 6
    targets = dict(proven.targets)
    assert list(targets) == [condition.id for condition in DRAFT.outage.conditions]
    normal = targets["normal"]
    assert normal is not None and normal > 0
    # A condition under which some scenario has no answer has no count, which is not zero.
    assert targets["frappe_down"] is None and targets["corpus_down"] is None
    for answered in ("jira_down", "calendar_down"):
        assert targets[answered] is not None


def test_the_job_prints_what_it_proved_and_nothing_sealed_and_writes_nothing(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    status, out, err = run_job(capsys, twin, checkout, "prove", "--world-version", world.version)
    assert (status, err) == (0, "")
    lines = dict(line.split("=", 1) for line in out.splitlines())
    assert lines["world_version"] == world.version
    assert lines["scenarios"] == "30"
    assert lines["development_scenarios"] == ",".join(development_selection(world, DRAFT))
    assert lines["retrieval_targets[frappe_down]"] == "no answer"
    assert int(lines["retrieval_targets[normal]"]) > 0
    assert lines["wrote"] == "nothing"
    sealed_words = [tier.value for tier in Tier] + [name.value for name in ScenarioClassName]
    assert not [word for word in sealed_words if word in out]
    assert LocalObjectReader(twin / "truth").list_keys(evaluations_prefix(world.version)) == ()


# --- Refusals and the public log ---------------------------------------------------------------


def test_a_refusal_is_printed_by_its_message_and_an_unexpected_failure_by_its_type_alone(
    world: SealedWorld,
    twin: Path,
    checkout: Repository,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absent = WorldVersion("f" * 64)
    status, out, err = run_job(capsys, twin, checkout, "prove", "--world-version", absent)
    assert (status, out) == (1, "")
    assert err.startswith("leaveimpact.evaluator: refused: ") and "Traceback" not in err

    assert job.main(["prove", "--world-version", world.version], RUNNER, checkout.root) == 2
    assert "LEAVE_IMPACT_WORLD_BUCKET is not set" in capsys.readouterr().err

    def fails(*_: object) -> None:
        try:
            raise KeyError("leave_017 holds ticket_042")
        except KeyError as cause:
            raise RuntimeError("the rules read employee_003") from cause

    monkeypatch.setattr(job, "prove", fails)
    status, out, err = run_job(capsys, twin, checkout, "prove", "--world-version", world.version)
    assert (status, out) == (3, "")
    assert "failed with RuntimeError" in err
    for sealed in ("leave_017", "ticket_042", "employee_003", "Traceback", "KeyError"):
        assert sealed not in err


# --- Evaluating the stored runs ----------------------------------------------------------------


def test_evaluating_publishes_one_artifact_over_every_stored_object(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    head = checkout.head()
    first, second, third = world.scenarios[:3]
    store_runs(
        twin,
        world,
        **{
            "run-1-1": export_of(world, first, head, "run-1"),
            "run-2-1": export_of(world, second, head, "run-2"),
            "run-3-1": export_of(world, third, ABSENT_COMMIT, "run-3"),
            "run-4-1": b"not an export",
        },
    )
    status, out, err = run_job(capsys, twin, checkout, "evaluate", "--world-version", world.version)
    assert (status, err) == (0, "")
    lines = dict(line.split("=", 1) for line in out.splitlines())
    key = evaluation_key(world.version, "77", "1")
    assert (lines["evaluation_key"], lines["label"]) == (key, "development")
    assert lines["inventory[eligible]"] == "2"
    assert lines["inventory[registration_not_resolved]"] == "1"
    assert lines["inventory[not_an_export]"] == "1"

    stored = LocalObjectReader(twin / "truth").get(key)
    assert stored is not None and stored.version_id == lines["evaluation_version_id"]
    artifact = json.loads(stored.content)
    assert artifact["world"]["version"] == world.version
    assert artifact["evaluator"] == {"commit": head, "registration_commit": head, "changed": []}
    held = LocalObjectReader(twin / "world")
    for entry in artifact["inventory"]:
        read = held.get(entry["key"])
        assert read is not None and entry["version_id"] == read.version_id
    assert [entry["key"].rsplit("/", 2)[1] for entry in artifact["inventory"]] == [
        "run-1-1",
        "run-2-1",
        "run-3-1",
        "run-4-1",
    ]


def test_a_later_commit_records_what_changed_and_keeps_runs_under_the_same_registration(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    registered = checkout.head()
    store_runs(
        twin, world, **{"run-1-1": export_of(world, world.scenarios[0], registered, "run-1")}
    )
    module = checkout.root / "src" / "leaveimpact" / "evaluator" / "tables.py"
    before = git(checkout.root, "rev-parse", f"{registered}:src/leaveimpact/evaluator/tables.py")
    module.write_bytes(b"FIRST = 2\n")
    (checkout.root / "README.md").write_bytes(b"outside the implementation\n")
    git(checkout.root, "add", ".")
    git(checkout.root, "commit", "--quiet", "-m", "a change to the evaluator")
    head = checkout.head()
    after = git(checkout.root, "rev-parse", f"{head}:src/leaveimpact/evaluator/tables.py")

    revision = evaluator_revision(checkout)
    assert (revision.commit, revision.registration_commit) == (head, registered)
    assert [(c.path, c.before, c.after) for c in revision.changed] == [
        ("src/leaveimpact/evaluator/tables.py", before, after)
    ]

    status, out, _ = run_job(capsys, twin, checkout, "evaluate", "--world-version", world.version)
    assert status == 0 and "inventory[eligible]=1" in out


def test_a_dirty_checkout_and_an_empty_listing_are_refused_and_nothing_is_published(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ("evaluate", "--world-version", world.version)
    status, out, err = run_job(capsys, twin, checkout, *arguments)
    assert (status, out) == (1, "")
    assert "there is no run to evaluate" in err

    store_runs(
        twin, world, **{"run-1-1": export_of(world, world.scenarios[0], checkout.head(), "run-1")}
    )
    (checkout.root / "scratch.txt").write_bytes(b"not committed\n")
    status, out, err = run_job(capsys, twin, checkout, *arguments)
    assert (status, out) == (1, "")
    assert "clean tree" in err
    assert LocalObjectReader(twin / "truth").list_keys(evaluations_prefix(world.version)) == ()


# --- The checkout, read through git ------------------------------------------------------------


def test_a_file_is_read_at_a_commit_as_committed_and_is_absent_where_it_is_not(
    checkout: Repository,
) -> None:
    head = checkout.head()
    assert checkout.file_at(head, REGISTRATION_PATH) == DRAFT_BYTES
    assert checkout.file_at(ABSENT_COMMIT, REGISTRATION_PATH) is None
    assert checkout.file_at(head, "preregistration/another.json") is None
    assert checkout.last_changed(REGISTRATION_PATH) == head
    with pytest.raises(RepositoryRefused, match="no commit of this history holds"):
        checkout.last_changed("preregistration/another.json")
    assert checkout.changed(head, head, IMPLEMENTATION) == ()
    checkout.require_clean()


def test_a_registered_selection_is_what_proving_returns_whatever_the_seed_would_draw(
    world: SealedWorld, twin: Path
) -> None:
    # The registered list survives a change of seed: the tuning was done on those
    # scenarios, and a fresh draw would name ones the evaluator holds out.
    registered = DRAFT.scenario_sets.development
    assert isinstance(registered, tuple)
    reseeded = replace(DRAFT, statistics=replace(DRAFT.statistics, seed=DRAFT.statistics.seed + 1))
    assert development_selection(world, reseeded) != registered
    proven = prove(world.version, stores(twin), reseeded)
    assert (proven.development, proven.registered) == (registered, True)

    pending = replace(
        reseeded,
        scenario_sets=replace(reseeded.scenario_sets, development=Pending("not yet selected")),
    )
    drawn = prove(world.version, stores(twin), pending)
    assert (drawn.development, drawn.registered) == (development_selection(world, reseeded), False)

    # A registered list the world's tiers do not fit is refused, not replaced by a draw.
    unbalanced = tuple(scenario.spec.id for scenario in world.scenarios[:6])
    misfit = replace(DRAFT, scenario_sets=replace(DRAFT.scenario_sets, development=unbalanced))
    with pytest.raises(ValueError, match="from each tier"):
        prove(world.version, stores(twin), misfit)
