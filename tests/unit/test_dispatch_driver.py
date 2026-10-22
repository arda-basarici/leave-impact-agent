"""The dispatch driver (`probes/phase-c-dispatch/dispatch.py`) over the two committed plans
and a fake `gh`: the phase-C plan still reads with the workflow's then defaults and its
ledger still folds to its 240 finished runs; the replay plan equals the demo configuration
field for field; a plan off the measurement world states its site and its ledger; a send
carries the plan's site, ledger and its token; a run is found by its token and never by the
clock (an unrelated run in the same window is ignored, a late listing is waited for, two
bearers stop, a run on another commit stops); a crash after GitHub accepted the send is
reconciled from the intent without a second send; an intent with no run is uncertain, never
sent again, and cleared only by the operator's release; the stop check expects the plan's
ledger from the admission's own marker. The fake answers with the fields the real tool
documents (`gh run list --json` lists `databaseId,createdAt,headSha,displayTitle`), never
with a line copied from the code under test."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "probes" / "phase-c-dispatch" / "dispatch.py"
PHASE_C = DRIVER.parent
REPLAY = ROOT / "probes" / "replay-set"
DEMO = ROOT / "src" / "leaveimpact" / "app" / "demo.json"

WORLD = "ab" * 32
HEAD = "c" * 40
OTHER_HEAD = "d" * 40
TOKEN = "dsp-000000000001"  # the driver draws twelve hex digits; a fixed low-entropy one here


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dispatch_driver", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeClock:
    """A clock the driver's sleeps advance, so a wait of minutes is a test of milliseconds."""

    def __init__(self) -> None:
        self.at = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        self.slept = 0.0

    def now(self) -> datetime:
        return self.at

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.at += timedelta(seconds=seconds)


class FakeGitHub:
    """`gh_json` and `gh` as the driver calls them: run listings served in sequence (the
    last repeated), every other read a quiet success, every send recorded."""

    def __init__(self, listings: list[list[dict[str, Any]]]) -> None:
        self.listings = list(listings)
        self.sent: list[tuple[str, ...]] = []
        self.views: dict[int, dict[str, Any]] = {}

    def gh_json(self, *args: str) -> object:
        if args[:2] == ("run", "list"):
            return self.listings.pop(0) if len(self.listings) > 1 else self.listings[0]
        if args[:2] == ("run", "view"):
            return self.views.get(int(args[2]), {"status": "completed", "conclusion": "success"})
        if args[0] == "api":
            return []
        raise AssertionError(f"unexpected read {args}")

    def gh(self, *args: str, **_: object) -> str:
        self.sent.append(args)
        return ""


def listed(run_id: int, title: str, sha: str = HEAD) -> dict[str, Any]:
    return {
        "databaseId": run_id,
        "createdAt": "2026-10-22T12:00:05Z",
        "headSha": sha,
        "displayTitle": title,
    }


@pytest.fixture
def clock(driver: ModuleType, monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(driver, "_clock", fake.now)
    monkeypatch.setattr(driver.time, "sleep", fake.sleep)
    monkeypatch.setattr(driver, "_log_file", None)
    return fake


def wire(driver: ModuleType, monkeypatch: pytest.MonkeyPatch, github: FakeGitHub) -> None:
    monkeypatch.setattr(driver, "gh_json", github.gh_json)
    monkeypatch.setattr(driver, "gh", github.gh)
    monkeypatch.setattr(driver, "local_head", lambda: HEAD)
    monkeypatch.setattr(driver, "new_token", lambda: TOKEN)


def scratch_plan(tmp_path: Path, driver: ModuleType, **changes: object) -> Any:
    data: dict[str, object] = {
        "world_version": WORLD,
        "condition": "normal",
        "approval": "automatic",
        "workflow": "investigate.yml",
        "frappe_base_url": "https://hr.example.test",
        "ledger": "ledger-demo",
        "cells": [{"system": "agent", "level": "base"}],
        "scenarios": ["scenario_001", "scenario_002"],
        "order": ["agent/base/scenario_001", "agent/base/scenario_002"],
    }
    data.update(changes)
    for name in [k for k, v in changes.items() if v is None]:
        del data[name]
    (tmp_path / "plan.json").write_text(json.dumps(data), encoding="utf-8")
    return driver.read_plan(tmp_path)


def good_markers(plan: Any, key: Any) -> dict[str, str]:
    """What a successful run's job log yields, parsed by the driver's own marker regex from
    lines in the runner's `word: name=value` form."""
    text = "\n".join(
        [
            f"launch: scenario={key.scenario}",
            f"launch: system={key.system}",
            f"launch: world_version={plan.world_version}",
            "launch: admitted=run-1/1",
            "launch: ledger_revision=2",
            f"launch: ledger={plan.ledger}",
            "work: ending=closed",
            "work: detail=completed",
            "status: recoveries=0",
            "publish: state=published",
            "publish: incident=None",
            "inventory: outcome=created",
        ]
    )
    return {f"{s}.{f}": v for s, f, v in (m.groups() for m in plan_markers(text))}


def plan_markers(text: str) -> Any:
    return re.finditer(r"\b(launch|work|status|publish|inventory): ([a-z_]+)=(\S*)", text)


# --- The committed plans -----------------------------------------------------------------------


def test_the_phase_c_plan_reads_with_the_workflows_then_defaults_and_folds_complete(
    driver: ModuleType,
) -> None:
    plan = driver.read_plan(PHASE_C)
    assert len(plan.order) == 240 and len(plan.cells) == 8 and len(plan.scenarios) == 30
    assert plan.world_version == driver.PHASE_C_WORLD
    assert plan.frappe_base_url == "https://hr-w4.ardabasarici.dev"
    assert plan.ledger == "ledger-development"
    records = driver.read_ledger(plan)
    state = driver.fold(records)
    assert set(state) == {key.text for key in plan.order}
    assert all(entry["finished"] is not None for entry in state.values())
    assert all(entry["dispatched"] is not None for entry in state.values())
    assert all(entry["intent"] is None for entry in state.values()), "phase C wrote no intents"
    assert len(driver.known_run_ids(records)) == 240


def test_the_replay_plan_equals_the_demo_configuration(driver: ModuleType) -> None:
    plan = driver.read_plan(REPLAY)
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    assert plan.world_version == demo["served_world_version"]
    assert plan.frappe_base_url == demo["frappe_base_url"]
    assert plan.ledger == demo["ledger_id"]
    assert plan.cells == ((demo["system"], demo["level"]),)
    assert plan.scenarios == tuple(f"scenario_{n:03d}" for n in range(1, 31))
    assert (plan.condition, plan.approval, plan.workflow) == (
        "normal",
        "automatic",
        "investigate.yml",
    )
    assert len(plan.order) == 30


def test_a_plan_off_the_measurement_world_states_its_site_and_ledger(
    tmp_path: Path, driver: ModuleType
) -> None:
    with pytest.raises(driver.Stop, match="frappe_base_url, ledger"):
        scratch_plan(tmp_path, driver, frappe_base_url=None, ledger=None)


def test_an_order_that_is_not_the_cells_product_is_refused(
    tmp_path: Path, driver: ModuleType
) -> None:
    with pytest.raises(driver.Stop, match="cells' product"):
        scratch_plan(tmp_path, driver, order=["agent/base/scenario_002", "agent/base/scenario_001"])


# --- The send and its resolution -------------------------------------------------------------


def test_a_send_carries_the_plans_site_ledger_and_its_token(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    github = FakeGitHub([[listed(7, f"investigate agent base scenario_001 {TOKEN}")]])
    wire(driver, monkeypatch, github)
    run_id, sha = driver.send(plan, plan.order[0])
    assert (run_id, sha) == (7, HEAD)
    (sent,) = github.sent
    assert sent[:3] == ("workflow", "run", "investigate.yml")
    inputs = set(sent[4::2])
    assert {
        "frappe_base_url=https://hr.example.test",
        "ledger=ledger-demo",
        f"dispatch_token={TOKEN}",
        f"world_version={WORLD}",
        "scenario=scenario_001",
    } <= inputs
    kinds = [r["kind"] for r in driver.read_ledger(plan)]
    assert kinds == ["intent", "dispatched"], "the intent is on disk before the run is known"


def test_the_run_is_found_by_its_token_not_the_clock_and_a_late_listing_is_waited_for(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    hand = listed(8, "investigate agent base scenario_009 ")
    github = FakeGitHub(
        [[], [hand], [hand, listed(9, f"investigate agent base scenario_001 {TOKEN}")]]
    )
    wire(driver, monkeypatch, github)
    assert driver.resolve_run(plan, TOKEN, HEAD, 180) == (9, HEAD)
    assert clock.slept == 10, "two empty reads, five seconds each"


def test_only_an_unrelated_run_within_the_wait_is_uncertain_and_stops(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    wire(driver, monkeypatch, FakeGitHub([[listed(8, "investigate agent base scenario_009 ")]]))
    with pytest.raises(driver.Stop, match="the intent stands"):
        driver.resolve_run(plan, TOKEN, HEAD, 60)
    assert clock.slept >= 60


def test_two_runs_bearing_the_token_stop_the_driver(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    github = FakeGitHub([[listed(8, f"x {TOKEN}"), listed(9, f"y {TOKEN}")]])
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="more than one run bears"):
        driver.resolve_run(plan, TOKEN, HEAD, 60)


def test_a_run_on_another_commit_than_the_checkouts_stops_before_approval(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    wire(driver, monkeypatch, FakeGitHub([[listed(8, f"x {TOKEN}", sha=OTHER_HEAD)]]))
    with pytest.raises(driver.Stop, match="did not dispatch from"):
        driver.resolve_run(plan, TOKEN, HEAD, 60)


# --- The intent across a crash -----------------------------------------------------------------


def no_second_send(*_: object) -> None:
    pytest.fail("a second send")


def intent_line(key: Any) -> dict[str, str]:
    return {
        "kind": "intent",
        "key": key.text,
        "token": TOKEN,
        "head_sha": HEAD,
        "intended_at": "2026-10-22T12:00:00Z",
    }


def test_a_crash_after_github_accepted_the_send_is_reconciled_from_the_intent(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(
        tmp_path, driver, scenarios=["scenario_001"], order=["agent/base/scenario_001"]
    )
    key = plan.order[0]
    driver.append_ledger(plan, intent_line(key))
    github = FakeGitHub([[listed(11, f"investigate agent base scenario_001 {TOKEN}")]])
    wire(driver, monkeypatch, github)
    monkeypatch.setattr(driver, "dispatch", no_second_send)

    def markers(_run_id: int) -> dict[str, str]:
        return good_markers(plan, key)

    monkeypatch.setattr(driver, "markers_of", markers)
    assert driver.run(plan, 0, False) == 0
    records = driver.read_ledger(plan)
    assert [r["kind"] for r in records] == ["intent", "dispatched", "finished"]
    assert records[1]["run_id"] == 11 and records[1]["adopted"].startswith("from the intent")
    assert records[2]["stop_reasons"] == []
    assert github.sent == [], "nothing was dispatched; the review had nothing pending"


def test_an_intent_with_no_run_is_uncertain_never_resent_and_cleared_only_by_release(
    tmp_path: Path,
    driver: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    driver.append_ledger(plan, intent_line(key))
    wire(driver, monkeypatch, FakeGitHub([[]]))
    monkeypatch.setattr(driver, "dispatch", no_second_send)
    with pytest.raises(driver.Stop, match="the intent stands"):
        driver.run(plan, 0, False)
    assert [r["kind"] for r in driver.read_ledger(plan)] == ["intent"]
    assert driver.release(plan, key, "Actions lists no run after the laptop slept") == 0
    records = driver.read_ledger(plan)
    assert records[-1]["kind"] == "released" and records[-1]["run_id"] is None
    assert "no run bears" in records[-1]["read"]
    assert driver.fold(records)[key.text] == driver.empty_entry()
    assert driver.run(plan, 0, True) == 0
    assert f"the next dispatch would be {key.text}" in capsys.readouterr().out


def test_release_refuses_an_intent_whose_run_exists_and_a_run_that_admitted(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    first, second = plan.order
    driver.append_ledger(plan, intent_line(first))
    wire(driver, monkeypatch, FakeGitHub([[listed(12, f"x {TOKEN}")]]))
    with pytest.raises(driver.Stop, match="`run` adopts it"):
        driver.release(plan, first, "typed too soon")
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": second.text, "token": "dsp-ffffffffffff", "run_id": 13}
    )
    driver.append_ledger(
        plan,
        {
            "kind": "finished",
            "key": second.text,
            "run_id": 13,
            "stop_reasons": ["work.ending is 'open'"],
            "markers": {"launch.admitted": "run-13/1"},
        },
    )
    with pytest.raises(driver.Stop, match="holds its slot under PROTOCOL"):
        driver.release(plan, second, "the work stalled")


def test_a_run_that_failed_before_admission_is_released_once_completed(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": key.text, "token": TOKEN, "run_id": 14}
    )
    driver.append_ledger(
        plan,
        {
            "kind": "finished",
            "key": key.text,
            "run_id": 14,
            "stop_reasons": ["job conclusion failure"],
            "markers": {"launch.admitted": None},
        },
    )
    github = FakeGitHub([[]])
    github.views[14] = {"status": "in_progress"}
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="not completed"):
        driver.release(plan, key, "the launch failed on a stopped instance")
    github.views[14] = {"status": "completed"}
    assert driver.release(plan, key, "the launch failed on a stopped instance") == 0
    assert driver.fold(driver.read_ledger(plan))[key.text] == driver.empty_entry()
    assert 14 in driver.known_run_ids(driver.read_ledger(plan)), "the released run stays known"


# --- The stop check ----------------------------------------------------------------------------


def test_the_stop_check_expects_the_plans_ledger_from_the_admissions_own_marker(
    tmp_path: Path, driver: ModuleType
) -> None:
    plan = scratch_plan(
        tmp_path,
        driver,
        cells=[{"system": "agent", "level": "base"}, {"system": "rules_only", "level": "base"}],
        order=[
            "agent/base/scenario_001",
            "agent/base/scenario_002",
            "rules_only/base/scenario_001",
            "rules_only/base/scenario_002",
        ],
    )
    agent, rules = plan.order[0], plan.order[2]
    assert driver.reasons_to_stop(plan, agent, "success", good_markers(plan, agent)) == []
    wrong = {**good_markers(plan, agent), "launch.ledger": "ledger-development"}
    assert driver.reasons_to_stop(plan, agent, "success", wrong) == [
        "launch.ledger is 'ledger-development', the plan says 'ledger-demo'"
    ]
    assert plan.expected_ledger(rules) == "none"
    none = {**good_markers(plan, rules), "launch.ledger": "none"}
    assert driver.reasons_to_stop(plan, rules, "success", none) == []
