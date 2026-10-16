"""The phase C dispatcher: one reported run at a time, each recorded before the next.

Phase C measures the four systems on the measurement world at the base and the padded
corpus level, thirty scenarios each at one repeat: 240 runs through the `investigate.yml`
workflow. PROTOCOL ("How a run is counted") makes two rules of the dispatch itself: the
intended run of a cell and scenario is the earliest in dispatch order, so a second
dispatch of the same pair is surplus and enters no estimate; and a run whose attempt was
never exported holds its slot, so its cell is never dispatched again on that account. The
instance README adds a third: a deploy is approved only between runs. Hand dispatching
240 runs of two to four minutes each would have to keep all three by habit over eight to
fourteen hours of wall clock; this driver keeps them by construction.

The plan is a fixed order written once to `plan.json`: rules only at the base level
first, since it calls no model and proves the pipeline over every scenario at no cost;
then the two cells of the registered headline comparison, the agent and full context at
the padded level, so that an interrupted phase still holds its primary result; then the
remaining five cells. The ledger `ledger.jsonl` is append-only and is the record: a
`dispatched` line is written as soon as the workflow run's id is known, before the driver
waits on it, and a `finished` line when the job has ended, carrying the job's conclusion
and the markers the runner prints (the admission, the attempt's ending, the recovery
count, the publication's state and object digest, the inventory's digest and outcome). A
key with a `dispatched` line is never dispatched again, in this process or a later one; a
key with a `dispatched` line and no `finished` one is resumed by waiting on its run.

The driver stops, with the reason printed and kept in the ledger, on anything an operator
decides: a job that did not succeed, an attempt whose ending is not a closed and completed
one, a publication not in the published state or with an incident, an inventory not
created, or a run whose admission names another scenario, system or world than the key's.
A recovery count above zero is printed and does not stop the driver, since the attempt
counts. The driver also refuses to dispatch while any run of the two run workflows or of
CI is queued, in progress or waiting at its gate, so a pending deploy is decided before the
phase continues, never during a run.

Every dispatched run waits at the production environment's review, the rule that stands
between the instance and any dispatch (DESIGN's launch passage). The driver approves the
review of each run it has itself dispatched, under the operator's own login through the
API, and writes an `approved` line beside the `dispatched` one; the plan is committed and
every dispatch of it is intended, so the review it answers would have been the operator's
click 240 times over, and a dispatch the plan did not make still waits for a human (ruled
2026-10-16, after the phase's first run was approved by hand).

Dispatching goes through the `gh` CLI, which prints no run id for a dispatch; the driver
notes the time, then takes the one investigate run created after it that the ledger does
not know. Two such runs mean someone else dispatched, and the driver stops rather than
guess. A dispatch whose result the CLI could not report (a timeout, a dropped connection)
is never sent again blind: the driver reads whether a run was created anyway, adopts it
with the lost response recorded on its `dispatched` line, and stops only when none appears
within a minute. The case is real: the thirtieth agent run's dispatch reached GitHub and
its response was lost to a local connection abort (2026-10-16); the first driver stopped
there and the run was adopted by hand from the Actions listing.

Usage, from the repository root with `gh` logged in:

    uv run python probes/phase-c-dispatch/dispatch.py plan            # write plan.json once
    uv run python probes/phase-c-dispatch/dispatch.py status          # what is done, what is next
    uv run python probes/phase-c-dispatch/dispatch.py run --dry-run   # the next dispatch, not sent
    uv run python probes/phase-c-dispatch/dispatch.py run --max 1     # one dispatch, then stop
    uv run python probes/phase-c-dispatch/dispatch.py run             # the rest of the plan

Every printed line is also appended to `data/phase-c-dispatch/driver.log` (git-ignored)
so a second terminal can follow it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
PLAN_FILE = HERE / "plan.json"
LEDGER_FILE = HERE / "ledger.jsonl"
LOG_FILE = REPOSITORY / "data" / "phase-c-dispatch" / "driver.log"

WORLD_VERSION = "2e6705ba7d11095a9b797abe08495c5497a7c5fe560fa587868763f11192341c"
CONDITION = "normal"
APPROVAL = "automatic"
WORKFLOW = "investigate.yml"
SCENARIOS = [f"scenario_{n:03d}" for n in range(1, 31)]
CELLS = [
    ("rules_only", "base"),
    ("agent", "padded"),
    ("full_context", "padded"),
    ("rules_only", "padded"),
    ("single_shot", "base"),
    ("single_shot", "padded"),
    ("full_context", "base"),
    ("agent", "base"),
]
ACCEPTED_ENDING = "closed"
ACCEPTED_DETAILS = frozenset({"completed"})
BUSY_WORKFLOWS = ("investigate.yml", "continue-run.yml", "ci.yml")
BUSY_STATUSES = frozenset({"queued", "in_progress", "requested", "pending", "waiting"})
POLL_SECONDS = 20
IDLE_POLL_SECONDS = 60
RUN_ID_WAIT_SECONDS = 180
ADOPTION_WAIT_SECONDS = 60
RUN_WAIT_SECONDS = 3 * 3600
REPOSITORY_NAME = "arda-basarici/leave-impact-agent"
GATED_ENVIRONMENT = "production"
REVIEW_WAIT_SECONDS = 90
MARKER = re.compile(r"\b(launch|work|status|publish|inventory): ([a-z_]+)=(\S*)")


class Stop(Exception):
    """The driver stops here; the message is the operator's reason."""


@dataclass(frozen=True)
class Key:
    system: str
    level: str
    scenario: str

    @property
    def text(self) -> str:
        return f"{self.system}/{self.level}/{self.scenario}"


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_stamp(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def log(line: str) -> None:
    text = f"{stamp(now())} {line}"
    print(text, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def gh(*args: str, timeout: int = 60, input: str | None = None) -> str:
    completed = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {completed.stderr.strip()}")
    return completed.stdout


def gh_json(*args: str) -> object:
    attempt = 0
    while True:
        try:
            return json.loads(gh(*args))
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            attempt += 1
            if attempt >= 6:
                raise Stop(f"six consecutive read failures: {error}") from None
            log(f"read failed ({error}); again in {POLL_SECONDS} s")
            time.sleep(POLL_SECONDS)


def plan_order() -> list[Key]:
    return [Key(system, level, scenario) for system, level in CELLS for scenario in SCENARIOS]


def write_plan() -> None:
    plan = {
        "world_version": WORLD_VERSION,
        "condition": CONDITION,
        "approval": APPROVAL,
        "workflow": WORKFLOW,
        "cells": [{"system": s, "level": lv} for s, lv in CELLS],
        "scenarios": SCENARIOS,
        "order": [k.text for k in plan_order()],
    }
    PLAN_FILE.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
    log(f"plan written: {len(plan['order'])} runs over {len(CELLS)} cells to {PLAN_FILE.name}")


def read_plan() -> list[Key]:
    if not PLAN_FILE.exists():
        raise Stop("no plan.json; run `plan` first")
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    if plan["world_version"] != WORLD_VERSION:
        raise Stop("plan.json names another world than this script")
    keys = [Key(*text.split("/")) for text in plan["order"]]
    if keys != plan_order():
        raise Stop("plan.json's order differs from this script's; the plan is fixed")
    return keys


def read_ledger() -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    lines = LEDGER_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def append_ledger(record: dict) -> None:
    with LEDGER_FILE.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def fold(records: list[dict]) -> dict[str, dict[str, dict | None]]:
    state: dict[str, dict[str, dict | None]] = {}
    for record in records:
        entry = state.setdefault(record["key"], {"dispatched": None, "finished": None})
        entry[record["kind"]] = record
    return state


def known_run_ids(records: list[dict]) -> set[int]:
    return {r["run_id"] for r in records if r["kind"] == "dispatched"}


def busy_runs() -> list[str]:
    busy = []
    for workflow in BUSY_WORKFLOWS:
        runs = gh_json(
            "run",
            "list",
            "--workflow",
            workflow,
            "--limit",
            "10",
            "--json",
            "databaseId,status,workflowName",
        )
        assert isinstance(runs, list)
        for run in runs:
            if run["status"] in BUSY_STATUSES:
                busy.append(f"{run['workflowName']} {run['databaseId']} {run['status']}")
    return busy


def wait_until_idle() -> None:
    while True:
        busy = busy_runs()
        if not busy:
            return
        log("not idle: " + "; ".join(busy) + f"; again in {IDLE_POLL_SECONDS} s")
        time.sleep(IDLE_POLL_SECONDS)


def dispatch(key: Key) -> tuple[datetime, str | None]:
    """Send the dispatch; the time before it and, when the call did not report success, why.

    A failed call does not mean no run: the thirtieth agent run's dispatch reached GitHub
    and its response was lost to a local connection abort (2026-10-16), so the caller reads
    the state rather than sending again, as the runner does for its own sends.
    """
    before = now()
    args = [
        "workflow",
        "run",
        WORKFLOW,
        "-f",
        f"world_version={WORLD_VERSION}",
        "-f",
        f"scenario={key.scenario}",
        "-f",
        f"system={key.system}",
        "-f",
        f"condition={CONDITION}",
        "-f",
        f"level={key.level}",
        "-f",
        f"approval={APPROVAL}",
    ]
    try:
        gh(*args, timeout=120)
    except subprocess.TimeoutExpired:
        return before, "the dispatch call timed out"
    except RuntimeError as error:
        return before, str(error)
    return before, None


def resolve_run_id(
    dispatched_at: datetime, known: set[int], wait_seconds: int = RUN_ID_WAIT_SECONDS
) -> tuple[int, str]:
    deadline = now() + timedelta(seconds=wait_seconds)
    floor = dispatched_at - timedelta(seconds=30)
    while True:
        runs = gh_json(
            "run",
            "list",
            "--workflow",
            WORKFLOW,
            "--limit",
            "10",
            "--json",
            "databaseId,createdAt,headSha",
        )
        assert isinstance(runs, list)
        fresh = [
            r for r in runs if r["databaseId"] not in known and parse_stamp(r["createdAt"]) >= floor
        ]
        if len(fresh) == 1:
            return fresh[0]["databaseId"], fresh[0]["headSha"]
        if len(fresh) > 1:
            ids = ", ".join(str(r["databaseId"]) for r in fresh)
            raise Stop(
                f"more than one new investigate run after the dispatch ({ids}); "
                "someone else dispatched"
            )
        if now() > deadline:
            raise Stop(
                "no investigate run appeared after the dispatch within the wait; check Actions"
            )
        time.sleep(5)


def approve_if_pending(run_id: int) -> str | None:
    """Approve the run's production review if it is pending; the approval's time, or None.

    A dispatched run is created waiting at the environment's review, so the pending
    deployment is normally listed at the first read; the wait covers the moments before
    GitHub lists it. A run already past the review (resumed after the driver died between
    the dispatch and the approval, or approved by hand) has nothing pending and nothing is
    sent.
    """
    deadline = now() + timedelta(seconds=REVIEW_WAIT_SECONDS)
    path = f"repos/{REPOSITORY_NAME}/actions/runs/{run_id}/pending_deployments"
    while True:
        pending = gh_json("api", path)
        assert isinstance(pending, list)
        ours = [p for p in pending if p["environment"]["name"] == GATED_ENVIRONMENT]
        if ours:
            if not ours[0]["current_user_can_approve"]:
                raise Stop(f"run {run_id} waits for a review this login cannot approve")
            body = json.dumps(
                {
                    "environment_ids": [ours[0]["environment"]["id"]],
                    "state": "approved",
                    "comment": "phase C dispatcher: a run of the committed plan",
                }
            )
            gh("api", "-X", "POST", path, "--input", "-", input=body)
            return stamp(now())
        run = gh_json("run", "view", str(run_id), "--json", "status")
        assert isinstance(run, dict)
        if run["status"] in ("in_progress", "completed"):
            return None
        if now() > deadline:
            raise Stop(f"run {run_id} lists no pending review and has not started; check Actions")
        time.sleep(5)


def wait_for_run(run_id: int) -> str:
    deadline = now() + timedelta(seconds=RUN_WAIT_SECONDS)
    while True:
        run = gh_json("run", "view", str(run_id), "--json", "status,conclusion")
        assert isinstance(run, dict)
        if run["status"] == "completed":
            return str(run["conclusion"])
        if now() > deadline:
            raise Stop(f"run {run_id} has not ended within the wait; check Actions")
        time.sleep(POLL_SECONDS)


def markers_of(run_id: int) -> dict[str, str]:
    text = gh("run", "view", str(run_id), "--log", timeout=120)
    found: dict[str, str] = {}
    for match in MARKER.finditer(text):
        step, field, value = match.groups()
        found[f"{step}.{field}"] = value
    return found


def reasons_to_stop(key: Key, conclusion: str, markers: dict[str, str]) -> list[str]:
    reasons = []
    if conclusion != "success":
        reasons.append(f"job conclusion {conclusion}")
    expected = {
        "launch.scenario": key.scenario,
        "launch.system": key.system,
        "launch.world_version": WORLD_VERSION,
    }
    for field, value in expected.items():
        if markers.get(field) != value:
            reasons.append(f"{field} is {markers.get(field)!r}, the key says {value!r}")
    if markers.get("work.ending") != ACCEPTED_ENDING:
        reasons.append(f"work.ending is {markers.get('work.ending')!r}")
    if markers.get("work.detail") not in ACCEPTED_DETAILS:
        reasons.append(f"work.detail is {markers.get('work.detail')!r}")
    if markers.get("publish.state") != "published":
        reasons.append(f"publish.state is {markers.get('publish.state')!r}")
    if markers.get("publish.incident", "None") != "None":
        reasons.append(f"publish.incident is {markers.get('publish.incident')!r}")
    if markers.get("inventory.outcome") != "created":
        reasons.append(f"inventory.outcome is {markers.get('inventory.outcome')!r}")
    return reasons


def finish(key: Key, run_id: int) -> dict:
    conclusion = wait_for_run(run_id)
    markers = markers_of(run_id)
    kept = {
        name: markers.get(name)
        for name in (
            "launch.admitted",
            "launch.reservation_pico_usd",
            "launch.ledger_revision",
            "launch.scenario",
            "launch.system",
            "launch.world_version",
            "work.ending",
            "work.detail",
            "status.recoveries",
            "status.generation",
            "publish.state",
            "publish.object_digest",
            "publish.incident",
            "inventory.inventory_digest",
            "inventory.outcome",
            "inventory.attempts",
            "inventory.refused",
        )
    }
    reasons = reasons_to_stop(key, conclusion, markers)
    record = {
        "kind": "finished",
        "key": key.text,
        "run_id": run_id,
        "finished_at": stamp(now()),
        "conclusion": conclusion,
        "markers": kept,
        "stop_reasons": reasons,
    }
    append_ledger(record)
    recoveries = kept.get("status.recoveries")
    log(
        f"finished {key.text} run {run_id}: {conclusion}, ending={kept.get('work.ending')}/"
        f"{kept.get('work.detail')}, recoveries={recoveries}, publish={kept.get('publish.state')}, "
        f"inventory={kept.get('inventory.outcome')} "
        f"{str(kept.get('inventory.inventory_digest'))[:12]}"
    )
    if recoveries not in (None, "0"):
        log(f"NOTE {key.text}: {recoveries} recoveries on the counted attempt; read the job log")
    return record


def run(max_dispatches: int, dry_run: bool) -> int:
    order = read_plan()
    records = read_ledger()
    state = fold(records)
    known = known_run_ids(records)
    dispatched = 0
    last_sha: str | None = None
    for key in order:
        entry = state.get(key.text, {"dispatched": None, "finished": None})
        if entry["finished"] is not None:
            continue
        if entry["dispatched"] is not None:
            run_id = entry["dispatched"]["run_id"]
            log(f"resuming {key.text}: run {run_id} was dispatched and never recorded as finished")
        else:
            if max_dispatches and dispatched >= max_dispatches:
                log(f"dispatch bound {max_dispatches} reached; next is {key.text}")
                return 0
            if dry_run:
                log(f"dry run: the next dispatch would be {key.text}; nothing sent")
                return 0
            wait_until_idle()
            dispatched_at, failure = dispatch(key)
            if failure is not None:
                log(f"the dispatch call for {key.text} failed ({failure}); reading for a run")
            try:
                run_id, sha = resolve_run_id(
                    dispatched_at,
                    known,
                    ADOPTION_WAIT_SECONDS if failure is not None else RUN_ID_WAIT_SECONDS,
                )
            except Stop as none_found:
                if failure is not None:
                    raise Stop(
                        f"the dispatch of {key.text} failed and no run appeared: {failure}"
                    ) from None
                raise none_found
            known.add(run_id)
            dispatched += 1
            line = {
                "kind": "dispatched",
                "key": key.text,
                "run_id": run_id,
                "head_sha": sha,
                "dispatched_at": stamp(dispatched_at),
            }
            if failure is not None:
                line["dispatch_response"] = f"lost: {failure}"
            append_ledger(line)
            log(f"dispatched {key.text}: run {run_id} on {sha[:7]}")
            if last_sha is not None and sha != last_sha:
                log(f"NOTE the dispatched commit changed from {last_sha[:7]} to {sha[:7]}")
            last_sha = sha
        approved_at = approve_if_pending(run_id)
        if approved_at is not None:
            append_ledger(
                {"kind": "approved", "key": key.text, "run_id": run_id, "approved_at": approved_at}
            )
            log(f"approved {key.text}: run {run_id}'s {GATED_ENVIRONMENT} review, this login")
        record = finish(key, run_id)
        if record["stop_reasons"]:
            raise Stop(f"{key.text} run {run_id}: " + "; ".join(record["stop_reasons"]))
    log("the plan is complete: every key has a finished record")
    return 0


def status() -> int:
    order = read_plan()
    state = fold(read_ledger())
    per_cell: dict[str, list[int]] = {}
    stopped = []
    next_key = None
    last_inventory = None
    for key in order:
        cell = f"{key.system}/{key.level}"
        counts = per_cell.setdefault(cell, [0, 0])
        entry = state.get(key.text)
        if entry is None:
            if next_key is None:
                next_key = key.text
            continue
        if entry["finished"] is None:
            counts[1] += 1
            if next_key is None:
                next_key = key.text + " (resume)"
            continue
        counts[0] += 1
        if entry["finished"]["stop_reasons"]:
            stopped.append(
                f"{key.text} run {entry['finished']['run_id']}: "
                + "; ".join(entry["finished"]["stop_reasons"])
            )
        last_inventory = entry["finished"]["markers"].get("inventory.inventory_digest")
    print(f"{'cell':<24}{'finished':>10}{'open':>6}")
    for cell, (done, open_) in per_cell.items():
        print(f"{cell:<24}{done:>10}{open_:>6}")
    print(f"next: {next_key or 'none, the plan is complete'}")
    print(f"last inventory digest: {last_inventory}")
    for line in stopped:
        print(f"stopped: {line}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("status")
    runner = sub.add_parser("run")
    runner.add_argument(
        "--max", type=int, default=0, help="dispatches this invocation may send; 0 is no bound"
    )
    runner.add_argument(
        "--dry-run", action="store_true", help="name the next dispatch and send nothing"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            write_plan()
            return 0
        if args.command == "status":
            return status()
        return run(args.max, args.dry_run)
    except Stop as stop:
        log(f"STOP {stop}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
