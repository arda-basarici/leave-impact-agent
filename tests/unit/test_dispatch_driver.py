"""The dispatch driver (`probes/phase-c-dispatch/dispatch.py`) over the two committed plans
and a fake `gh`: the phase-C plan still reads with the workflow's then defaults and its
ledger still folds to its 240 finished runs; the replay plan equals the demo configuration
field for field; a plan off the measurement world states its site and its ledger; a send
carries the plan's site, ledger and its token; a run is found by its token and never by the
clock (an unrelated run in the same window is ignored, a late listing is waited for, two
bearers stop, a run on another commit stops); a crash after GitHub accepted the send is
reconciled from the intent without a second send; an intent with no run is uncertain, never
sent again, and cleared only by the operator's release; a release of a finished run reads
the launch send off the job log and, for any sent launch, the host store's refusal of the
attempt off a continuation made after the host command's bound; a full
listing younger than the intent proves no absence; a dry run ends before any approval or
ledger line; a recorded stop stands across invocations until acknowledged; the stop check
expects the plan's ledger from the admission's own marker. The fake answers with the fields
the real tool documents (`gh run list --json` lists `databaseId,createdAt,headSha,
displayTitle`; the runner's log lines are the runner script's own), never with a line
copied from the code under test."""

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
INTENDED_AT = "2026-10-22T12:00:00Z"  # the listings' runs are created five seconds later
LAUNCH_ENDED = "2026-10-22T12:10:00Z"  # when a finished run's job ended, as `gh run view` says


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
    last repeated), a run's log and its pending reviews as set, every other read a quiet
    success, every send recorded."""

    def __init__(self, listings: list[list[dict[str, Any]]]) -> None:
        self.listings = list(listings)
        self.sent: list[tuple[str, ...]] = []
        self.views: dict[int, dict[str, Any]] = {}
        self.logs: dict[int, str] = {}
        self.pending: list[dict[str, Any]] = []
        self.approvals: list[dict[str, Any]] = []

    def gh_json(self, *args: str) -> object:
        if args[:2] == ("run", "list"):
            return self.listings.pop(0) if len(self.listings) > 1 else self.listings[0]
        if args[:2] == ("run", "view"):
            default = {
                "status": "completed",
                "conclusion": "success",
                "updatedAt": LAUNCH_ENDED,
                "attempt": 1,
            }
            return self.views.get(int(args[2]), default)
        if args[0] == "api" and args[1].endswith("/approvals"):
            return self.approvals
        if args[0] == "api":
            return self.pending
        raise AssertionError(f"unexpected read {args}")

    def gh(self, *args: str, **_: object) -> str:
        if args[:2] == ("run", "view") and "--log" in args:
            return self.logs.get(int(args[2]), "")
        self.sent.append(args)
        return ""


def runner_log(*lines: str) -> str:
    """Lines as `gh run view --log` prints them: job, step and time before the runner's text."""
    return "".join(
        f"investigate\tRun the plan\t2026-10-22T12:01:00.0000000Z {text}\n" for text in lines
    )


def production_review() -> list[dict[str, Any]]:
    return [{"environment": {"name": "production", "id": 5}, "current_user_can_approve": True}]


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
    assert driver.resolve_run(plan, TOKEN, HEAD, 180, INTENDED_AT) == (9, HEAD)
    assert clock.slept == 10, "two empty reads, five seconds each"


def test_only_an_unrelated_run_within_the_wait_is_uncertain_and_stops(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    wire(driver, monkeypatch, FakeGitHub([[listed(8, "investigate agent base scenario_009 ")]]))
    with pytest.raises(driver.Stop, match="the intent stands"):
        driver.resolve_run(plan, TOKEN, HEAD, 60, INTENDED_AT)
    assert clock.slept >= 60


def test_two_runs_bearing_the_token_stop_the_driver(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    github = FakeGitHub([[listed(8, f"x {TOKEN}"), listed(9, f"y {TOKEN}")]])
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="more than one run bears"):
        driver.resolve_run(plan, TOKEN, HEAD, 60, INTENDED_AT)


def test_a_run_on_another_commit_than_the_checkouts_stops_before_approval(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    wire(driver, monkeypatch, FakeGitHub([[listed(8, f"x {TOKEN}", sha=OTHER_HEAD)]]))
    with pytest.raises(driver.Stop, match="did not dispatch from"):
        driver.resolve_run(plan, TOKEN, HEAD, 60, INTENDED_AT)


# --- The intent across a crash -----------------------------------------------------------------


def no_second_send(*_: object) -> None:
    pytest.fail("a second send")


def intent_line(key: Any) -> dict[str, str]:
    return {
        "kind": "intent",
        "key": key.text,
        "token": TOKEN,
        "head_sha": HEAD,
        "intended_at": INTENDED_AT,
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
    github.views[14] = {"status": "in_progress", "updatedAt": LAUNCH_ENDED, "attempt": 1}
    github.logs[14] = runner_log("no running leave-impact instance")
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="not completed"):
        driver.release(plan, key, "the launch failed on a stopped instance")
    github.views[14] = {"status": "completed", "updatedAt": LAUNCH_ENDED, "attempt": 1}
    assert driver.release(plan, key, "the launch failed on a stopped instance") == 0
    records = driver.read_ledger(plan)
    assert records[-1]["read"] == "run 14 completed; its launch was never sent"
    assert driver.fold(records)[key.text] == driver.empty_entry()
    assert 14 in driver.known_run_ids(records), "the released run stays known"


def stopped_after_launch(driver: ModuleType, plan: Any, key: Any, run_id: int) -> None:
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": key.text, "token": TOKEN, "run_id": run_id}
    )
    driver.append_ledger(
        plan,
        {
            "kind": "finished",
            "key": key.text,
            "run_id": run_id,
            "stop_reasons": ["job conclusion failure"],
            "markers": {"launch.admitted": None},
        },
    )


def continuation(created_at: str, *lines: str) -> tuple[dict[str, Any], str]:
    """A completed continue-run as `gh run view` lists it, and its log in the runner's lines."""
    view = {"status": "completed", "workflowName": "continue run", "createdAt": created_at}
    return view, "".join(
        f"continue\tContinue the run\t2026-10-22T14:30:00.0000000Z {text}\n" for text in lines
    )


NO_ATTEMPT = (
    "status: sending",
    "status: command 5555-6666 on i-0abc",
    "status: container=none",
    "status: attempt_containers=none",
    "status (stderr): leaveimpact.launch: refused: run run-40 has no attempt 1",
    "status: the process exited 1",
)
LATE_ENOUGH = "2026-10-22T14:10:00Z"  # two hours after LAUNCH_ENDED, the host command's bound


def test_release_of_a_sent_launch_needs_the_host_stores_answer_not_the_logs_shape(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """The two histories the second external read constructed: a response lost after SSM
    accepted the send (no command id on the log, the host running the command anyway), and
    a commit whose acknowledgement was lost (an unsuccessful exit without the marker, the
    admission committed). Neither is releasable from the log; the second is from the store's
    refusal on a continuation made after the host command's bound, once the log shows the
    host created the attempt-named admit container the continuation's listing can see. The
    first shows no container at all and is never released by the driver (the fourth
    external read: a listing by attempt name sees nothing of an unnamed container)."""
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    stopped_after_launch(driver, plan, key, 40)
    github = FakeGitHub([[]])
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="log is empty"):
        driver.release(plan, key, "the job failed")
    lost_response = runner_log(
        "launch: sending",
        "Connection was closed before we received a valid response from endpoint URL",
    )
    github.logs[40] = lost_response
    with pytest.raises(driver.Stop, match="pass its run id as --status-run"):
        driver.release(plan, key, "the launch failed")
    github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *NO_ATTEMPT)
    with pytest.raises(driver.Stop, match="no admit container named for run-40 attempt 1"):
        driver.release(plan, key, "the launch failed", status_run=41)
    another_attempts_container = runner_log(
        "launch: sending",
        "launch: command 1111-2222 on i-0abc",
        "launch (stderr):  Container lifecycle-run-40-a2-admit Created ",
        "launch: the process exited 1",
    )
    github.logs[40] = another_attempts_container
    with pytest.raises(driver.Stop, match="no admit container named for run-40 attempt 1"):
        driver.release(plan, key, "the launch failed", status_run=41)
    lost_acknowledgement = runner_log(
        "launch: sending",
        "launch: command 1111-2222 on i-0abc",
        "launch (stderr):  Container lifecycle-run-40-a1-plan Created ",
        "launch (stderr):  Container lifecycle-run-40-a1-threshold Created ",
        "launch (stderr):  Container lifecycle-run-40-a1-admit Created ",
        "launch (stderr): leaveimpact.agent: the connection was lost while the admission committed",
        "launch: the process exited 1",
    )
    for history in (lost_acknowledgement,):
        github.logs[40] = history
        with pytest.raises(driver.Stop, match="pass its run id as --status-run"):
            driver.release(plan, key, "the launch failed")
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *NO_ATTEMPT)
        github.views[41]["workflowName"] = "investigate"
        with pytest.raises(driver.Stop, match="not a completed 'continue run'"):
            driver.release(plan, key, "the launch failed", status_run=41)
        github.views[41], github.logs[41] = continuation("2026-10-22T13:00:00Z", *NO_ATTEMPT)
        with pytest.raises(driver.Stop, match="not yet about the launch's end"):
            driver.release(plan, key, "the launch failed", status_run=41)
        answered = ("status: sending", "status: command 7 on i-0abc", "status: attempt=open")
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *answered)
        with pytest.raises(driver.Stop, match="the attempt exists and the run holds its slot"):
            driver.release(plan, key, "the launch failed", status_run=41)
        other = tuple(line.replace("run-40", "run-39") for line in NO_ATTEMPT)
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *other)
        with pytest.raises(driver.Stop, match="read run-39 attempt 1, not run-40 attempt 1"):
            driver.release(plan, key, "the launch failed", status_run=41)
        second = tuple(line.replace("no attempt 1", "no attempt 2") for line in NO_ATTEMPT)
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *second)
        with pytest.raises(driver.Stop, match="read run-40 attempt 2, not run-40 attempt 1"):
            driver.release(plan, key, "the launch failed", status_run=41)
        alive = tuple(
            line.replace("attempt_containers=none", "attempt_containers=lifecycle-run-40-a1-admit")
            for line in NO_ATTEMPT
        )
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *alive)
        with pytest.raises(driver.Stop, match="lifecycle-run-40-a1-admit.*may commit after"):
            driver.release(plan, key, "the launch failed", status_run=41)
        unlisted = tuple(line for line in NO_ATTEMPT if "attempt_containers" not in line)
        github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *unlisted)
        with pytest.raises(driver.Stop, match="container listing"):
            driver.release(plan, key, "the launch failed", status_run=41)
        assert [r["kind"] for r in driver.read_ledger(plan)] == ["dispatched", "finished"]
    github.views[40] = {"status": "completed", "updatedAt": LAUNCH_ENDED, "attempt": 2}
    github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *NO_ATTEMPT)
    with pytest.raises(driver.Stop, match="2 job attempts"):
        driver.release(plan, key, "the launch failed", status_run=41)
    del github.views[40]
    assert driver.release(plan, key, "the launch failed", status_run=41) == 0
    read = driver.read_ledger(plan)[-1]["read"]
    assert read == (
        "continue-run 41, 7200 s after the launch job ended, read the host: no lifecycle "
        "container of run-40 running, and the store has no attempt 1"
    )


def test_a_launch_the_earlier_runner_printed_is_a_sent_one(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """The runners before the replay step printed the command id and no sending line; a
    log of theirs with the id and an unsuccessful exit is a sent launch, not a never-sent
    one (the third external read)."""
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    stopped_after_launch(driver, plan, key, 40)
    github = FakeGitHub([[]])
    wire(driver, monkeypatch, github)
    github.logs[40] = runner_log("launch: command cmd-123 on i-123", "launch: the process exited 1")
    with pytest.raises(driver.Stop, match="pass its run id as --status-run"):
        driver.release(plan, key, "the launch failed")
    assert [r["kind"] for r in driver.read_ledger(plan)] == ["dispatched", "finished"]


def test_an_admission_on_the_log_refuses_release_whatever_the_markers_say(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    stopped_after_launch(driver, plan, key, 40)
    github = FakeGitHub([[]])
    wire(driver, monkeypatch, github)
    github.logs[40] = runner_log(
        "launch: sending", "launch: command 1 on i-0abc", "launch: admitted=run-40/1"
    )
    github.views[41], github.logs[41] = continuation(LATE_ENOUGH, *NO_ATTEMPT)
    with pytest.raises(driver.Stop, match="carries an admission"):
        driver.release(plan, key, "the work failed", status_run=41)


def test_a_full_listing_younger_than_the_intent_proves_no_absence(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    plan = scratch_plan(tmp_path, driver)
    key = plan.order[0]
    driver.append_ledger(plan, intent_line(key))
    limit = int(driver.LISTING_LIMIT)
    young = [listed(100 + i, f"investigate x {i + 2:012x}") for i in range(limit)]
    wire(driver, monkeypatch, FakeGitHub([young]))
    with pytest.raises(driver.Stop, match="may lie past the listing"):
        driver.release(plan, key, "Actions lists no run")
    assert [r["kind"] for r in driver.read_ledger(plan)] == ["intent"]
    reaching_back = young[:-1] + [dict(young[-1], createdAt="2026-10-22T11:59:00Z")]
    wire(driver, monkeypatch, FakeGitHub([reaching_back]))
    assert driver.release(plan, key, "Actions lists no run") == 0


# --- The dry run and the standing stop ---------------------------------------------------------


def test_a_dry_run_ends_before_any_approval_or_ledger_line(
    tmp_path: Path,
    driver: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = scratch_plan(tmp_path, driver)
    first, second = plan.order
    driver.append_ledger(plan, intent_line(first))
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": second.text, "token": "dsp-ffffffffffff", "run_id": 21}
    )
    github = FakeGitHub([[listed(20, f"investigate agent base scenario_001 {TOKEN}")]])
    github.pending = production_review()
    wire(driver, monkeypatch, github)
    monkeypatch.setattr(driver, "dispatch", no_second_send)
    before = driver.read_ledger(plan)
    assert driver.run(plan, 0, True) == 0
    assert driver.read_ledger(plan) == before and github.sent == []
    assert f"the run bearing {TOKEN} would be adopted for {first.text}" in capsys.readouterr().out
    (tmp_path / "resumed").mkdir()
    resumed = scratch_plan(tmp_path / "resumed", driver)
    driver.append_ledger(
        resumed, {"kind": "dispatched", "key": first.text, "token": TOKEN, "run_id": 21}
    )
    assert driver.run(resumed, 0, True) == 0
    assert [r["kind"] for r in driver.read_ledger(resumed)] == ["dispatched"] and github.sent == []
    assert f"run 21 would be resumed for {first.text}" in capsys.readouterr().out
    # The control: the same state under a real run adopts, approves and finishes both runs.
    good = {20: good_markers(plan, first), 21: good_markers(plan, second)}
    monkeypatch.setattr(driver, "markers_of", good.__getitem__)
    assert driver.run(plan, 0, False) == 0
    assert [args[:3] for args in github.sent] == [("api", "-X", "POST")] * 2


def test_the_run_bound_counts_a_resumed_run_so_max_one_after_a_stop_sends_nothing(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """The wiring run of a sitting is read before the rest: after the review wait stopped
    the driver on a queued run (2026-10-22), `--max 1` must finish that run and stop, not
    count it as free and send the second key."""
    plan = scratch_plan(tmp_path, driver)
    first, second = plan.order
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": first.text, "token": TOKEN, "run_id": 50}
    )
    github = FakeGitHub([[]])
    wire(driver, monkeypatch, github)
    monkeypatch.setattr(driver, "dispatch", no_second_send)

    def markers_of(_run_id: int) -> dict[str, str]:
        return good_markers(plan, first)

    monkeypatch.setattr(driver, "markers_of", markers_of)
    assert driver.run(plan, 1, False) == 0
    kinds = [r["kind"] for r in driver.read_ledger(plan)]
    assert kinds == ["dispatched", "finished"], "the resumed run finished and nothing was sent"
    assert driver.fold(driver.read_ledger(plan)).get(second.text) is None


def test_a_review_approved_by_hand_on_a_run_still_queued_is_not_a_missing_review(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """The wiring run (2026-10-22): the operator approved the review by hand within seconds
    of the dispatch and the job then queued nine minutes for a runner, so nothing was
    pending and nothing had started; the first driver stopped on it. The run's approvals
    are the record of a review already given (`GET .../runs/{id}/approvals`, the state and
    the environments as the API lists them)."""
    plan = scratch_plan(tmp_path, driver)
    github = FakeGitHub([[]])
    github.views[60] = {"status": "queued"}
    wire(driver, monkeypatch, github)
    with pytest.raises(driver.Stop, match="no pending review and has not started"):
        driver.approve_if_pending(plan, 60)
    assert clock.slept >= driver.REVIEW_WAIT_SECONDS
    github.approvals = [
        {
            "state": "approved",
            "user": {"login": "arda-basarici"},
            "environments": [{"name": "production"}],
        }
    ]
    assert driver.approve_if_pending(plan, 60) is None
    assert github.sent == [], "nothing was approved twice"


def test_a_recorded_stop_stands_across_invocations_until_acknowledged(
    tmp_path: Path,
    driver: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = scratch_plan(tmp_path, driver)
    first, second = plan.order
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": first.text, "token": TOKEN, "run_id": 30}
    )
    driver.append_ledger(
        plan,
        {
            "kind": "finished",
            "key": first.text,
            "run_id": 30,
            "stop_reasons": ["work.ending is 'open'"],
            "markers": {"launch.admitted": "run-30/1"},
        },
    )
    wire(driver, monkeypatch, FakeGitHub([[]]))
    monkeypatch.setattr(driver, "dispatch", no_second_send)
    for dry_run in (False, True):
        with pytest.raises(driver.Stop, match="the stop stands until"):
            driver.run(plan, 0, dry_run)
    assert [r["kind"] for r in driver.read_ledger(plan)] == ["dispatched", "finished"]
    with pytest.raises(driver.Stop, match="no finished run"):
        driver.acknowledge(plan, second, "nothing here")
    assert driver.acknowledge(plan, first, "the attempt is open on the host; the slot is held") == 0
    with pytest.raises(driver.Stop, match="already"):
        driver.acknowledge(plan, first, "again")
    assert driver.run(plan, 0, True) == 0
    assert f"the next dispatch would be {second.text}" in capsys.readouterr().out
    driver.status(plan)
    assert f"stopped: {first.text} run 30 (acknowledged): work.ending" in capsys.readouterr().out
    driver.append_ledger(
        plan, {"kind": "dispatched", "key": second.text, "token": "dsp-ffffffffffff", "run_id": 31}
    )
    driver.append_ledger(
        plan,
        {"kind": "finished", "key": second.text, "run_id": 31, "stop_reasons": [], "markers": {}},
    )
    with pytest.raises(driver.Stop, match="nothing to acknowledge"):
        driver.acknowledge(plan, second, "it went well")


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
