"""The restore drill at the unit level: the module imports nothing that sends a request to a
model or a vendor (the drill's "execution disabled", held at its import edges); the command
refuses a missing registration, a stdin that is not JSON or not a list, and a row that is
not an object, each at exit 2 before any store is built; and the checks' failure answers
name what they saw, a store's refusal while a check reads becoming that check's failure.
The pass path and the settlements check run over the real stores in the integration
level, the drill's first test being the real producer's output."""

from __future__ import annotations

import ast
import io
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from leaveimpact.agent.inventory import SnapshotAttempt, StoreSnapshot
from leaveimpact.agent.ledger import LedgerHead
from leaveimpact.agent.log_events import Admitted
from leaveimpact.agent.log_store import LedgerView, LogStoreInvariantBroken
from leaveimpact.app.__main__ import main
from leaveimpact.app.public import PublicId, PublishableRow
from leaveimpact.app.restore import (
    RestoreReads,
    capture_check,
    fold_check,
    listing_check,
    settlement_check,
    verify,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import CLOSED, CONFIGURATION, SERVED, history_in_world

MODULE = Path(__file__).resolve().parents[2] / "src" / "leaveimpact" / "app" / "restore.py"
SIBLING = MODULE.with_name("publication_check.py")

DISPATCHING = frozenset(
    {
        "leaveimpact.agent.worker",
        "leaveimpact.agent.execution",
        "leaveimpact.agent.commands",
        "leaveimpact.agent.graph",
        "leaveimpact.agent.one_call",
        "leaveimpact.agent.turns",
        "leaveimpact.adapters.inference",
        "leaveimpact.adapters.converse",
        "leaveimpact.adapters.wiring",
        "leaveimpact.adapters.transport",
    }
)
"""The modules that admit, claim, dispatch or send: the worker and its execution, the
commands, the graph and its turns, the model and vendor clients and the wiring that builds
them. The drill reads; it imports none of these."""

DSN = "postgresql://nobody@localhost/none"
ENV = {
    "DATABASE_URL": DSN,
    "LEAVEIMPACT_REGISTRATION_FILE": "/app/preregistration/registration.json",
}


@pytest.mark.parametrize("module", [MODULE, SIBLING], ids=["restore", "publication_check"])
def test_the_drill_and_its_sibling_import_no_module_that_dispatches(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert imported & DISPATCHING == set()
    assert "leaveimpact.app.read_model" in imported, (
        "the drill reads through the surface's admission"
    )


class NeverBuilt:
    """A store seam that must not be reached: the command refuses before any store."""

    def __init__(self, dsn: str) -> None:
        raise AssertionError("no store is built before the command's inputs are checked")


@pytest.mark.parametrize(
    ("env", "stdin", "message"),
    [
        ({"DATABASE_URL": DSN}, "[]", "LEAVEIMPACT_REGISTRATION_FILE is not set"),
        (ENV, "not json", "stdin is not the backup's capture"),
        (ENV, '{"ledger_id": "x"}', "the capture is a JSON list of ledger rows"),
        (ENV, "[1]", "the capture is a JSON list of ledger rows"),
    ],
)
def test_the_command_refuses_its_inputs_at_exit_2_before_any_store(
    env: dict[str, str], stdin: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["verify-restore"],
        env,
        store=NeverBuilt,  # type: ignore[arg-type]
        restore_log=NeverBuilt,  # type: ignore[arg-type]
        stdin=io.StringIO(stdin),
    )
    assert code == 2
    assert message in capsys.readouterr().err


class Rows:
    """Publishable reads over a fixed tuple of rows."""

    def __init__(self, rows: tuple[PublishableRow, ...]) -> None:
        self.rows = rows

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]:
        return tuple(row for row in self.rows if row.world_version == world_version)

    def row_of(self, public_id: PublicId) -> PublishableRow | None:
        return next((row for row in self.rows if row.public_id == public_id), None)


class Ledgers:
    """A log whose ledger views are scripted by id; a missing id is the store's refusal."""

    def __init__(self, views: dict[str, LedgerView]) -> None:
        self.views = views

    def load(self, run_id: str, attempt: int, *, rules: Any) -> Any:
        raise AssertionError("no attempt is loaded by these checks")

    def ledger_view(self, ledger_id: str) -> LedgerView:
        if ledger_id not in self.views:
            raise LogStoreInvariantBroken(f"ledger {ledger_id} has no head")
        return self.views[ledger_id]

    def snapshot(self, ledger_id: str) -> Any:
        raise LogStoreInvariantBroken("the snapshot's ledger has no head")


def reads_over(
    capture: list[JsonObject],
    views: dict[str, LedgerView],
    rows: tuple[PublishableRow, ...] = (),
) -> RestoreReads:
    return RestoreReads(
        app_schema=lambda: True,
        ledger_capture=lambda: capture,
        cache_versions=lambda: frozenset({SERVED}),
        rows=Rows(rows),
        log=Ledgers(views),
        configuration=CONFIGURATION,
        rules=histories.RULES,
    )


ROW_A: JsonObject = {
    "ledger_id": "ledger-a",
    "total_pico_usd": 5,
    "revision": 2,
    "threshold_pico_usd": 100,
    "open_reservation_pico_usd": 0,
    "open_attempts": 0,
}


def test_a_capture_the_view_does_not_hold_names_the_ledgers_on_both_sides() -> None:
    reads = reads_over([dict(ROW_A, total_pico_usd=6)], {})
    check = capture_check([ROW_A], reads)
    assert not check.passed
    assert check.detail == (
        "the capture names ledgers ['ledger-a'] and the restored view ['ledger-a']; captured "
        "rows the view does not hold: ['ledger-a']"
    )
    assert capture_check([ROW_A], reads_over([ROW_A], {})).passed


def test_a_head_that_folds_to_another_revision_fails_the_fold_check_by_name() -> None:
    folded = {"ledger-a": LedgerView(LedgerHead(5, 3, 100), ())}
    check = fold_check([ROW_A], reads_over([ROW_A], folded))
    assert not check.passed and check.detail == (
        "ledger ledger-a's head folds to revision 3; the capture says 2"
    )
    assert fold_check(
        [ROW_A], reads_over([ROW_A], {"ledger-a": LedgerView(LedgerHead(5, 2, 100), ())})
    ).passed


def test_an_empty_listing_fails_and_a_stores_refusal_while_reading_is_the_checks_failure() -> None:
    reads = reads_over([ROW_A], {})
    assert not listing_check(reads).passed
    by_name = {check.name: check for check in verify([ROW_A], reads)}
    assert by_name["ledger-fold"].detail == "refused while reading: ledger ledger-a has no head"
    assert by_name["settlements"].detail.startswith("refused while reading: ")
    assert [check.passed for check in by_name.values()] == [
        True,
        True,
        True,
        False,
        False,
        False,
        False,
    ]


class Snapshotting(Ledgers):
    """A log whose snapshot holds the given attempts; loading one is this test's failure,
    since an attempt under another registration is never folded."""

    def __init__(self, attempts: tuple[SnapshotAttempt, ...]) -> None:
        super().__init__({})
        self.attempts = attempts

    def snapshot(self, ledger_id: str) -> StoreSnapshot:
        return StoreSnapshot(5, datetime(2026, 10, 24, tzinfo=UTC), self.attempts, None, ())

    def load(self, run_id: str, attempt: int, *, rules: Any) -> Any:
        raise AssertionError(f"run {run_id} attempt {attempt} was admitted under other rules")


def test_a_closed_attempt_admitted_under_another_registration_is_counted_and_not_folded() -> None:
    events = history_in_world(CLOSED, SERVED)
    first = events[0].event
    assert isinstance(first, Admitted)
    other = replace(first, inputs=replace(first.inputs, attribution_table="f" * 64))
    moved = (replace(events[0], event=other), *events[1:])
    attempt = SnapshotAttempt("run-12", 1, True, "ledger-test", moved, None, ())
    reads = replace(reads_over([ROW_A], {}), log=Snapshotting((attempt,)))
    check = settlement_check(reads)
    assert check.passed and check.detail == (
        "0 closed attempts charged as the account rule, the closing event and the ledger "
        "agree; 1 admitted under another registration, not folded"
    )
