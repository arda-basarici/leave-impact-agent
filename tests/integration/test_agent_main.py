"""The command-line entry over the real store: the threshold set, the export published and
the inventory written through the entry, each printing its fields and nothing sealed; a
publish or an inventory folds under the registration's rules given on the line; and a
refusal is printed as the store's reason with the status that says so."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store import layout
from leaveimpact.agent import __main__ as entry
from leaveimpact.core.registration_json import registration_bytes
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.integration.log_store_support import Rig, rig
from tests.integration.worker_rig import ATTEMPT, LEDGER, RULES, RUN, completed
from tests.unit import format_fixtures as cases
from tests.unit.registration_fixture import DRAFT, named
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def test_the_entry_sets_the_threshold_publishes_and_writes_the_inventory(
    rig: Rig, world: SealedWorld, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store, inputs = completed(rig, world)
    env = {
        "LEAVE_IMPACT_OBJECT_STORE_ROOT": str(tmp_path / "store"),
        entry.CODE_VERSION: cases.COMMIT,
    }
    # The registration whose rules the admitted run froze: the entry folds under them.
    registration = tmp_path / "registration.json"
    settled = named(DRAFT)
    registration.write_bytes(
        registration_bytes(
            replace(
                settled,
                attribution=RULES.table,
                run_accounting=replace(settled.run_accounting, redispatch=RULES.redispatch),
            )
        )
    )
    under = ["--registration", str(registration)]
    status = entry.main(
        [
            "set-threshold",
            "--ledger",
            "ledger-cli",
            "--amount",
            "7",
            "--authority",
            "operator:cli",
            "--registration-commit",
            cases.COMMIT,
            "--limit",
            "9",
        ],
        env,
        rig.store(),
    )
    assert status == 0
    assert capsys.readouterr().out.splitlines() == [
        "threshold=ledger-cli",
        "revision=1",
        "amount_pico_usd=7",
    ]
    status = entry.main(
        ["publish", "--run", RUN, "--attempt", str(ATTEMPT), *under], env, rig.store()
    )
    captured = capsys.readouterr()
    out = captured.out.splitlines()
    assert status == 0, captured.err
    assert out[0] == f"publication={RUN}/{ATTEMPT}" and out[1] == "state=published"
    version = inputs.context.world_version
    status = entry.main(
        [
            "inventory",
            "--world-version",
            version,
            "--registration-commit",
            cases.COMMIT,
            "--ledger",
            LEDGER,
            *under,
        ],
        env,
        rig.store(),
    )
    captured = capsys.readouterr()
    out = captured.out.splitlines()
    assert status == 0, captured.err
    assert out[2] == "outcome=created" and out[3] == "attempts=1"
    digest = out[0].removeprefix("inventory_digest=")
    assert (tmp_path / "store" / "world" / layout.inventory_key(version, digest)).exists()
    status = entry.main(
        [
            "abandon",
            "--run",
            RUN,
            "--attempt",
            str(ATTEMPT),
            "--authority",
            "operator:cli",
            "--reason",
            "cancelled",
            *under,
        ],
        env,
        rig.store(),
    )
    out = capsys.readouterr().out.splitlines()
    position = store.load(RUN, ATTEMPT, rules=RULES).last_position
    assert status == 1, "a refusal exits 1 with its fields printed (the review's second finding)"
    assert out == [
        f"refused=run {RUN} attempt {ATTEMPT}",
        f"reason=the attempt is closed at position {position}",
    ]


def test_the_entry_imports_spend_made_outside_the_log_into_the_ledger(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The acceptance spike's spend enters the ledger through this command once the price
    table prices its captured sends; here the entry's shape: the head where absent, the
    imported entry, a replay under the same request charging nothing again, and other
    content under that request refused (the close's review, first finding)."""
    store = rig.store()
    import_line = [
        "import-spend",
        "--request",
        "import-spike",
        "--ledger",
        "ledger-import",
        "--amount",
        "250",
        "--authority",
        "import:spike-2026-10-04",
        "--registration-commit",
        cases.COMMIT,
    ]
    printed = [
        "imported=ledger-import",
        "revision=1",
        "amount_pico_usd=250",
        "total_after_pico_usd=250",
    ]
    assert entry.main(import_line, {}, store) == 0
    assert capsys.readouterr().out.splitlines() == printed
    assert entry.main(import_line, {}, store) == 0, "the replay returns the entry"
    assert capsys.readouterr().out.splitlines() == printed
    view = store.ledger_view("ledger-import")
    (imported,) = view.entries
    assert (imported.kind.value, imported.authority) == ("imported", "import:spike-2026-10-04")
    assert view.head.total_pico_usd == 250 and view.head.threshold_pico_usd is None
    changed = [*import_line[:6], "251", *import_line[7:]]
    assert entry.main(changed, {}, store) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "refused=import request import-spike" and "other content" in out[1]
    assert store.ledger_view("ledger-import").head.total_pico_usd == 250
    assert store.open_attempts() == ()


def test_a_publication_recorded_as_failed_exits_1_with_its_record_printed(
    rig: Rig, world: SealedWorld, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, inputs = completed(rig, world)
    env = {
        "LEAVE_IMPACT_OBJECT_STORE_ROOT": str(tmp_path / "store"),
        entry.CODE_VERSION: cases.COMMIT,
    }
    registration = tmp_path / "registration.json"
    settled = named(DRAFT)
    registration.write_bytes(
        registration_bytes(
            replace(
                settled,
                attribution=RULES.table,
                run_accounting=replace(settled.run_accounting, redispatch=RULES.redispatch),
            )
        )
    )
    key = layout.run_export_key(inputs.context.world_version, RUN, ATTEMPT, cases.COMMIT)
    held = tmp_path / "store" / "world" / key
    held.parent.mkdir(parents=True)
    held.write_bytes(b"other bytes")
    status = entry.main(
        ["publish", "--run", RUN, "--attempt", str(ATTEMPT), "--registration", str(registration)],
        env,
        rig.store(),
    )
    out = capsys.readouterr().out.splitlines()
    assert status == 1 and out[1] == "state=failed"
    assert out[4].startswith("incident=the key holds other bytes")
    assert held.read_bytes() == b"other bytes", "nothing overwrites"


def test_a_publish_without_the_rules_the_run_froze_is_refused_by_the_transition(
    rig: Rig, world: SealedWorld, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    completed(rig, world)
    env = {
        "LEAVE_IMPACT_OBJECT_STORE_ROOT": str(tmp_path / "store"),
        entry.CODE_VERSION: cases.COMMIT,
    }
    status = entry.main(["publish", "--run", RUN, "--attempt", str(ATTEMPT)], env, rig.store())
    captured = capsys.readouterr()
    assert status == 1 and captured.out == ""
    assert "refused:" in captured.err and "the registered table and policy" in captured.err
