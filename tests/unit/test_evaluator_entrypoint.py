"""The evaluation job's entry point. A request takes a command, a world version and the runner's
identifiers. Proving a world returns one total of retrieval targets per registered
condition, and the job prints those and nothing sealed, writing nothing. Evaluating
publishes one artifact over every object stored for the world's runs, from a clean
checkout, each cited commit resolved in the checkout's own history, held to the harness
inventory the request names, read by digest and verified against its name; a dirty tree, a
missing or misnamed inventory, a listed export the store lacks or holds otherwise, an open
attempt under a reported label, an empty listing and a world that is not there are refused
by name, and an unexpected failure prints its type and no traceback. A bound registration
is held to the frozen one at the commit it names before anything is listed: evaluated when
its procedure is that one's, refused when
the commit holds no frozen registration, a procedure that differs, or when it binds another
world. The checkout is read through git: a file at a commit as committed, absent for a
commit or a path that is not there, and the implementation paths that changed between two
commits."""

import json
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.layout import (
    evaluation_key,
    evaluations_prefix,
    inventory_key,
    runs_prefix,
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.wiring import ConfigurationError, ObjectReaders
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    HarnessRevision,
    Inventory,
    PricingBasis,
    Registration,
    TreeState,
    condition_id,
    export_bytes,
    inventory_bytes,
    inventory_digest,
    registration_bytes,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator import __main__ as job
from leaveimpact.evaluator.entrypoint import Command, parse_request, prove
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
from tests.unit.export_fixture import export_baseline
from tests.unit.inventory_fixture import inventory_over, listed, open_attempt
from tests.unit.reads_fixture import systems_holding
from tests.unit.registration_fixture import DRAFT as COMMITTED
from tests.unit.registration_fixture import bound, frozen, light
from tests.unit.throwaway_world import composed_world, loaded_world

DIGEST = "a" * 64
ABSENT_COMMIT = "c" * 40
RUNNER = {"GITHUB_RUN_ID": "77", "GITHUB_RUN_ATTEMPT": "1"}

DRAFT = light(COMMITTED)
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


def export_of(
    world: SealedWorld,
    scenario: Scenario,
    commit: str,
    run_id: str,
    registration: Registration = DRAFT,
) -> bytes:
    """The real baseline's export of ``scenario`` under ``registration``, citing the
    registration at ``commit``."""
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        registration,
        condition_id(()),
        "base",
        harness=HarnessRevision(commit, TreeState.CLEAN),
        preregistration_commit=commit,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    run = investigate(context, systems_holding(world).ports)
    return export_bytes(
        export_baseline(run, context, provenance, run_id=run_id, attempt=1, duration_ms=1_200)
    )


def store_runs(twin: Path, world: SealedWorld, **runs: bytes) -> str:
    """``runs`` stored under their names, and an inventory listing every export among them
    as published at its key; its digest, which an evaluation names."""
    writer = LocalObjectWriter(twin / "world")
    objects = {
        f"{runs_prefix(world.version)}{name}/export.json": content for name, content in runs.items()
    }
    for key, content in objects.items():
        writer.put_if_absent(key, content)
    return store_inventory(twin, inventory_over(world.version, objects))


def store_inventory(twin: Path, inventory: Inventory) -> str:
    """``inventory`` stored at the key its digest names; the digest."""
    content = inventory_bytes(inventory)
    digest = inventory_digest(content)
    LocalObjectWriter(twin / "world").put_if_absent(
        inventory_key(inventory.scope.world_version, digest), content
    )
    return digest


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
    assert (request.run_id, request.run_attempt, request.inventory) == ("77", "1", None)
    given = parse_request(
        [
            "evaluate",
            "--world-version",
            version,
            "--run-id",
            "9",
            "--run-attempt",
            "2",
            "--inventory",
            DIGEST,
        ],
        {},
    )
    assert (given.command, given.run_id, given.run_attempt) == (Command.EVALUATE, "9", "2")
    assert given.inventory == DIGEST
    for argv, env in (
        (["grade", "--world-version", version], RUNNER),
        (["prove", "--world-version", "abc"], RUNNER),
        (["prove", "--world-version", version], {}),
        (["prove", "--world-version", version, "--run-id", "a/b"], RUNNER),
        # An evaluation names the inventory it reads, by a 64-hex digest.
        (["evaluate", "--world-version", version], RUNNER),
        (["evaluate", "--world-version", version, "--inventory", "abc"], RUNNER),
    ):
        with pytest.raises(ConfigurationError):
            parse_request(argv, env)


# --- Proving a world ---------------------------------------------------------------------------


def test_proving_a_world_counts_the_targets_and_draws_no_scenario(
    world: SealedWorld, twin: Path
) -> None:
    proven = prove(world.version, stores(twin), DRAFT)
    assert (proven.world_version, proven.scenarios) == (world.version, 30)
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
    # The registration tunes on no scenario of its world, so none is drawn or printed.
    assert not [name for name in lines if "scenario_" in name or "development" in name]
    assert "scenario_0" not in out
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
    digest = store_runs(
        twin,
        world,
        **{
            "run-1-1": export_of(world, first, head, "run-1"),
            "run-2-1": export_of(world, second, head, "run-2"),
            "run-3-1": export_of(world, third, ABSENT_COMMIT, "run-3"),
            "run-4-1": b"not an export",
        },
    )
    status, out, err = run_job(
        capsys, twin, checkout, "evaluate", "--world-version", world.version, "--inventory", digest
    )
    assert (status, err) == (0, "")
    lines = dict(line.split("=", 1) for line in out.splitlines())
    key = evaluation_key(world.version, "77", "1")
    assert (lines["evaluation_key"], lines["label"]) == (key, "development")
    assert lines["inventory[eligible]"] == "2"
    assert lines["inventory[registration_not_resolved]"] == "1"
    # The object that is no export is one the harness never listed.
    assert lines["inventory[not_in_inventory]"] == "1"
    assert lines["harness_inventory"] == inventory_key(world.version, digest)
    # The run admitted under a commit that resolves to no registration is out of scope.
    assert (lines["coverage[admitted]"], lines["coverage[exported]"]) == ("2", "2")
    assert (lines["coverage[open]"], lines["coverage[closed_without_export]"]) == ("0", "0")

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
    digest = store_runs(
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

    status, out, _ = run_job(
        capsys, twin, checkout, "evaluate", "--world-version", world.version, "--inventory", digest
    )
    assert status == 0 and "inventory[eligible]=1" in out


def test_a_dirty_checkout_and_an_empty_listing_are_refused_and_nothing_is_published(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = store_inventory(twin, listed(world.version))
    arguments = ("evaluate", "--world-version", world.version, "--inventory", empty)
    # The inventory alone under the runs prefix lists no run.
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


def test_an_inventory_absent_misnamed_or_contradicted_by_the_store_is_refused(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    head = checkout.head()
    export = export_of(world, world.scenarios[0], head, "run-1")
    key = f"{runs_prefix(world.version)}run-1-1/export.json"

    def refused(digest: str) -> str:
        arguments = ("evaluate", "--world-version", world.version, "--inventory", digest)
        status, out, err = run_job(capsys, twin, checkout, *arguments)
        assert (status, out) == (1, "")
        assert err.startswith("leaveimpact.evaluator: refused: ") and "Traceback" not in err
        return err

    absent = "9" * 64
    assert f"no harness inventory is stored at {inventory_key(world.version, absent)}" in refused(
        absent
    )
    # An inventory stored under another digest's name does not digest to it.
    misnamed = "8" * 64
    LocalObjectWriter(twin / "world").put_if_absent(
        inventory_key(world.version, misnamed), inventory_bytes(listed(world.version))
    )
    assert "does not digest to its name" in refused(misnamed)
    # One that does not decode is refused by its key alone: the decoder quotes the value it
    # refused, and this log is public.
    marked = inventory_bytes(listed(world.version)).replace(b"ledger-1", b"PRIVATE-MARKER")
    marked = marked.replace(b'"refused":[]', b'"refused":["PRIVATE-MARKER"]')
    undecodable = inventory_digest(marked)
    LocalObjectWriter(twin / "world").put_if_absent(
        inventory_key(world.version, undecodable), marked
    )
    err = refused(undecodable)
    assert "does not decode as an inventory" in err and "PRIVATE-MARKER" not in err
    # One listing the export before it is stored (another object keeps the listing from
    # being empty, which is refused first), then with other bytes than stored.
    LocalObjectWriter(twin / "world").put_if_absent(
        f"{runs_prefix(world.version)}stray/export.json", b"not an export"
    )
    before = store_inventory(twin, inventory_over(world.version, {key: export}))
    assert f"{key} is not in the listing" in refused(before)
    other = export_of(world, world.scenarios[1], head, "run-1")
    store_runs(twin, world, **{"run-1-1": other})
    assert f"{key} holds other bytes than recorded" in refused(before)
    assert LocalObjectReader(twin / "truth").list_keys(evaluations_prefix(world.version)) == ()


def test_an_open_attempt_in_scope_holds_a_reported_evaluation_and_is_counted_by_a_draft(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    draft_at = checkout.head()
    objects = {
        f"{runs_prefix(world.version)}run-1-1/export.json": export_of(
            world, world.scenarios[0], draft_at, "run-1"
        )
    }
    LocalObjectWriter(twin / "world").put_if_absent(*next(iter(objects.items())))
    held_open = open_attempt(world.version, "run-2", 1, registration_commit=draft_at)
    digest = store_inventory(twin, inventory_over(world.version, objects, extra=(held_open,)))
    arguments = ("evaluate", "--world-version", world.version, "--inventory", digest)
    status, out, err = run_job(capsys, twin, checkout, *arguments)
    assert (status, err) == (0, "")
    assert "label=development" in out and "coverage[open]=1" in out

    procedure = light(frozen())
    frozen_at = commit_registration(checkout, procedure, "the procedure, frozen")
    made = bound(world.version, procedure, frozen_commit=frozen_at)
    head = commit_registration(checkout, made, "the world, bound")
    scoped = {
        f"{runs_prefix(world.version)}run-3-1/export.json": export_of(
            world, world.scenarios[2], head, "run-3", registration=made
        )
    }
    LocalObjectWriter(twin / "world").put_if_absent(*next(iter(scoped.items())))
    still_open = open_attempt(world.version, "run-4", 1, registration_commit=head)
    digest = store_inventory(twin, inventory_over(world.version, scoped, extra=(still_open,)))
    status, out, err = run_job(
        capsys, twin, checkout, "evaluate", "--world-version", world.version, "--inventory", digest
    )
    assert (status, out) == (1, "")
    assert "waits for every attempt in its scope to close; open: run-4 attempt 1" in err
    # The first evaluation was the draft's and stands; nothing else was published.
    assert len(LocalObjectReader(twin / "truth").list_keys(evaluations_prefix(world.version))) == 1


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


# --- A bound registration ----------------------------------------------------------------------


def commit_registration(checkout: Repository, registration: Registration, message: str) -> str:
    (checkout.root / REGISTRATION_PATH).write_bytes(registration_bytes(registration))
    git(checkout.root, "add", ".")
    git(checkout.root, "commit", "--quiet", "-m", message)
    return checkout.head()


def test_a_bound_registration_is_evaluated_when_its_procedure_is_the_frozen_one(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    procedure = light(frozen())
    frozen_at = commit_registration(checkout, procedure, "the procedure, frozen")
    made = bound(world.version, procedure, frozen_commit=frozen_at)
    head = commit_registration(checkout, made, "the world, bound")
    digest = store_runs(
        twin,
        world,
        **{"run-1-1": export_of(world, world.scenarios[0], head, "run-1", registration=made)},
    )
    status, out, err = run_job(
        capsys, twin, checkout, "evaluate", "--world-version", world.version, "--inventory", digest
    )
    assert (status, err) == (0, "")
    lines = dict(line.split("=", 1) for line in out.splitlines())
    assert (lines["label"], lines["inventory[eligible]"]) == ("reported", "1")
    stored = LocalObjectReader(twin / "truth").get(lines["evaluation_key"])
    assert stored is not None
    read = json.loads(stored.content)["registration"]
    assert (read["status"], read["frozen_commit"]) == ("bound", frozen_at)


def test_a_bound_registration_is_refused_unless_it_binds_this_world_and_the_frozen_procedure(
    world: SealedWorld, twin: Path, checkout: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    draft_at = checkout.head()
    procedure = light(frozen())
    frozen_at = commit_registration(checkout, procedure, "the procedure, frozen")

    def refused(registration: Registration, message: str) -> str:
        head = commit_registration(checkout, registration, message)
        store = {f"run-{head[:7]}": export_of(world, world.scenarios[0], head, f"run-{head[:7]}")}
        digest = store_runs(twin, world, **store)
        arguments = ("evaluate", "--world-version", world.version, "--inventory", digest)
        status, out, err = run_job(capsys, twin, checkout, *arguments)
        assert (status, out) == (1, "")
        assert err.startswith("leaveimpact.evaluator: refused: ") and "Traceback" not in err
        return err

    # A changed seed is a changed procedure, whatever else the file says.
    reseeded = replace(procedure.statistics, seed=procedure.statistics.seed + 1)
    changed = bound(world.version, replace(procedure, statistics=reseeded), frozen_commit=frozen_at)
    err = refused(changed, "bound, with another seed")
    assert f"is not the frozen one's at {frozen_at}; they differ in statistics" in err
    # The commit named holds the draft, which nobody froze.
    err = refused(bound(world.version, procedure, frozen_commit=draft_at), "bound to a draft")
    assert f"the registration at the frozen commit {draft_at} is draft, not frozen" in err
    err = refused(bound(world.version, procedure, frozen_commit=ABSENT_COMMIT), "bound to nothing")
    assert f"the frozen commit {ABSENT_COMMIT} holds no registration" in err
    err = refused(bound("e" * 64, procedure, frozen_commit=frozen_at), "bound to another world")
    assert f"is bound to the world {'e' * 64}" in err and world.version in err
    assert LocalObjectReader(twin / "truth").list_keys(evaluations_prefix(world.version)) == ()
