"""The dispatcher: one run of a committed plan at a time, each recorded before the next.

Phase C measured the four systems on the measurement world at the base and the padded
corpus level, thirty scenarios each at one repeat: 240 runs through the `investigate.yml`
workflow, and this driver was written for them. PROTOCOL ("How a run is counted") makes two
rules of the dispatch itself: the intended run of a cell and scenario is the earliest in
dispatch order, so a second dispatch of the same pair is surplus and enters no estimate;
and a run whose attempt was never exported holds its slot, so its cell is never dispatched
again on that account. The instance README adds a third: a deploy is approved only between
runs. Hand dispatching 240 runs of two to four minutes each would have to keep all three by
habit over eight to fourteen hours of wall clock; this driver keeps them by construction.
The demo milestone's replay set (its step 8) is the second plan it drives: the registered
investigator at the base level over the golden world's thirty scenarios, on the golden
world's HR site and against the demo ledger, so the plan file became the authority and
this module keeps no plan of its own.

A plan is a directory holding `plan.json`, the driver's `ledger.jsonl` and a README; the
plan names the world version, the condition, the approval policy, the workflow, the cells
and the scenarios in a fixed order, the HR site URL and the ledger the runs are admitted
against. The phase-C plan predates the last two fields and ran on the workflow's then
defaults, so a plan on the measurement world reads them as those defaults; any other plan
states them. The driver refuses a plan whose order is not its cells' product with its
scenarios. Phase C's order: rules only at the base level first, since it calls no model
and proves the pipeline over every scenario at no cost; then the two cells of the
registered headline comparison; then the remaining five cells.

The ledger is append-only and is the record, one line a kind: an `intent` line is written
before the send, holding the token the send carries, so a crash between the send and the
next line leaves a key the fold sees as sent-and-unresolved rather than unsent (the parked
defect of 2026-10-17); a `dispatched` line as soon as the run's id is known; an `approved`
line when the driver answered the run's review; a `finished` line when the job has ended,
carrying the job's conclusion and the markers the runner prints (the admission, the ledger
it reserved against, the attempt's ending, the recovery count, the publication's state and
object digest, the inventory's digest and outcome); and a `released` line, written by an
operator through `release` after reading Actions, after which the key may be sent once
more, the one path by which a key with a `dispatched` line is ever sent again (the other
parked defect: a run that failed before admission holds no slot, and PROTOCOL lets it be
dispatched again); and an `acknowledged` line, the operator's after reading a stop, after
which `run` walks past the stopped key, which keeps its record and its slot. A `finished`
line carrying stop reasons stops every later invocation until one of those two operator
lines stands beside it, so a restart never walks past a stop nobody read. A key with a
`dispatched` line and no `finished` one is resumed by waiting on its run. A release of a
finished run reads the job log for its launch send: a launch never sent admitted nothing;
any sent launch is the host's store to answer, since a lost response leaves no command id
and the host runs the command anyway, and a relayed exit says nothing about a commit whose
acknowledgement was lost. The operator dispatches a continue-run for the run by hand, two
hours after the job ended (the bound on how long SSM may deliver and run the command), and
the driver reads its log for the store's own refusal of the attempt before it releases
(the two external reads of the replay step, the first of which also found the dry run
approving a standing run's review: it now ends before any send, approval or ledger line).

A send's identity is its token. `gh workflow run` prints no run id, and the first driver
took the one new run created after the send, a clock window that would have adopted a
hand dispatch made in the same minute and approved its review. The workflow carries the
token into its run name since the replay step, and the driver finds its run by that name
and the commit it dispatched from: one run bearing the token is the run; two stop the
driver; none within the wait is uncertain, never absent, and stops the driver with the
intent standing, so the next invocation looks for the run again and an operator who has
read Actions releases the key when GitHub created nothing. A key with an unresolved intent
is never sent again by the driver. A dispatch call whose result the CLI could not report
(a timeout, a dropped connection) is read the same way; the case is real: the thirtieth
agent run's dispatch reached GitHub and its response was lost to a local connection abort
(2026-10-16).

The driver stops, with the reason printed and kept in the ledger, on anything an operator
decides: a job that did not succeed, an attempt whose ending is not a closed and completed
one, a publication not in the published state or with an incident, an inventory not
created, or a run whose admission names another scenario, system, world or ledger than the
plan's. A recovery count above zero is printed and does not stop the driver, since the
attempt counts. The driver also refuses to dispatch while any run of the two run workflows
or of CI is queued, in progress or waiting at its gate, so a pending deploy is decided
before the plan continues, never during a run.

Every dispatched run waits at the production environment's review, the rule that stands
between the instance and any dispatch (DESIGN's launch passage). The driver approves the
review of each run it has itself dispatched, under the operator's own login through the
API, and writes an `approved` line beside the `dispatched` one; the plan is committed and
every dispatch of it is intended, so the review it answers would have been the operator's
click once per run, and a dispatch the plan did not make still waits for a human (ruled
2026-10-16 for phase C, extended to the committed replay plan 2026-10-22).

Usage, from the repository root with `gh` logged in, the plan directory this file's own
unless `--plan-dir` names another:

    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] status
    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] run --dry-run
    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] run --max 1
    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] run
    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] release --key K --reason R \
        [--status-run ID]
    uv run python probes/phase-c-dispatch/dispatch.py [--plan-dir DIR] acknowledge --key K \
        --reason R

Every printed line is also appended to `data/<plan directory name>/driver.log`
(git-ignored) so a second terminal can follow it.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]

PHASE_C_WORLD = "2e6705ba7d11095a9b797abe08495c5497a7c5fe560fa587868763f11192341c"
# The workflow's defaults when phase C ran, read into a plan on its world and no other.
PHASE_C_FRAPPE_BASE_URL = "https://hr-w4.ardabasarici.dev"
PHASE_C_LEDGER = "ledger-development"
ACCEPTED_ENDING = "closed"
ACCEPTED_DETAILS = frozenset({"completed"})
BUSY_WORKFLOWS = ("investigate.yml", "continue-run.yml", "ci.yml")
BUSY_STATUSES = frozenset({"queued", "in_progress", "requested", "pending", "waiting"})
POLL_SECONDS = 20
IDLE_POLL_SECONDS = 60
RUN_ID_WAIT_SECONDS = 180
ADOPTION_WAIT_SECONDS = 60
RUN_WAIT_SECONDS = 3 * 3600
LISTING_LIMIT = "50"
REPOSITORY_NAME = "arda-basarici/leave-impact-agent"
GATED_ENVIRONMENT = "production"
# The replay set's wiring run sat queued for over two minutes before GitHub placed its
# review (2026-10-22), and the first wait of 90 s stopped the driver on a run that was fine.
REVIEW_WAIT_SECONDS = 600
MARKER = re.compile(r"\b(launch|work|status|publish|inventory): ([a-z_]+)=(\S*)")
# The runner's own lines (deploy/runner/investigate.sh): the line before a send and the
# command id after it (the runners before the replay step printed the id alone), the admit
# command's marker, and on a continuation the host's listing of the attempt's lifecycle
# containers, the launcher's refusal the store answers for a run with no attempt, relayed
# from stderr, and the status step's relayed exit.
LAUNCH_SENDING = re.compile(r"\blaunch: sending\b")
LAUNCH_SENT = re.compile(r"\blaunch: command \S+ on \S+")
LAUNCH_ADMITTED = re.compile(r"\blaunch: admitted=\S+")
STATUS_CONTAINERS = re.compile(r"\bstatus: attempt_containers=(\S+)")
STATUS_NO_ATTEMPT = re.compile(
    r"\bstatus \(stderr\): leaveimpact\.launch: refused: run (run-\d+) has no attempt (\d+)"
)
STATUS_EXITED = re.compile(r"\bstatus: the process exited \d+")
CONTINUATION_WORKFLOW_NAME = "continue run"
# SSM's delivery timeout (the send's default, 3600 s) and the payload's execution timeout
# (3600 s): a launch command the job sent has ended this long after the job ended.
HOST_COMMAND_BOUND_SECONDS = 7200
TOKEN = re.compile(r"^dsp-[0-9a-f]{12}$")
RUN_FIELDS = "databaseId,createdAt,headSha,displayTitle"


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

    @staticmethod
    def of(text: str) -> Key:
        system, level, scenario = text.split("/")
        return Key(system, level, scenario)


@dataclass(frozen=True)
class Plan:
    """A committed plan as `plan.json` states it, with the files that record its driving."""

    directory: Path
    world_version: str
    condition: str
    approval: str
    workflow: str
    cells: tuple[tuple[str, str], ...]
    scenarios: tuple[str, ...]
    order: tuple[Key, ...]
    frappe_base_url: str
    ledger: str

    @property
    def name(self) -> str:
        return self.directory.name

    @property
    def ledger_file(self) -> Path:
        return self.directory / "ledger.jsonl"

    @property
    def log_file(self) -> Path:
        return REPOSITORY / "data" / self.name / "driver.log"

    def expected_ledger(self, key: Key) -> str:
        """What the admission prints as its ledger: rules only reserves nothing."""
        return "none" if key.system == "rules_only" else self.ledger


_log_file: Path | None = None


def _system_clock() -> datetime:
    return datetime.now(UTC)


_clock = _system_clock


def now() -> datetime:
    return _clock()


def stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_stamp(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def log(line: str) -> None:
    text = f"{stamp(now())} {line}"
    print(text, flush=True)
    if _log_file is None:
        return
    _log_file.parent.mkdir(parents=True, exist_ok=True)
    with _log_file.open("a", encoding="utf-8") as handle:
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


def local_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, cwd=REPOSITORY
    )
    if completed.returncode != 0:
        raise Stop(f"git rev-parse HEAD failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


# --- The plan and the ledger ------------------------------------------------------------------


def read_plan(directory: Path) -> Plan:
    """The plan a directory holds, refused when its order is not its cells' product with
    its scenarios or when a plan off the measurement world omits its site or its ledger."""
    file = directory / "plan.json"
    if not file.exists():
        raise Stop(f"no plan.json under {directory}")
    data = json.loads(file.read_text(encoding="utf-8"))
    cells = tuple((cell["system"], cell["level"]) for cell in data["cells"])
    scenarios = tuple(data["scenarios"])
    order = tuple(Key.of(text) for text in data["order"])
    product = tuple(
        Key(system, level, scenario) for system, level in cells for scenario in scenarios
    )
    if order != product:
        raise Stop(
            f"{file}'s order is not its cells' product with its scenarios; the plan is fixed"
        )
    world = data["world_version"]
    if world == PHASE_C_WORLD:
        site = data.get("frappe_base_url", PHASE_C_FRAPPE_BASE_URL)
        ledger = data.get("ledger", PHASE_C_LEDGER)
    else:
        missing = [field for field in ("frappe_base_url", "ledger") if field not in data]
        if missing:
            raise Stop(
                f"{file} is a plan off the measurement world and omits {', '.join(missing)}; "
                "a plan states its site and its ledger"
            )
        site, ledger = data["frappe_base_url"], data["ledger"]
    return Plan(
        directory=directory,
        world_version=world,
        condition=data["condition"],
        approval=data["approval"],
        workflow=data["workflow"],
        cells=cells,
        scenarios=scenarios,
        order=order,
        frappe_base_url=site,
        ledger=ledger,
    )


def read_ledger(plan: Plan) -> list[dict]:
    if not plan.ledger_file.exists():
        return []
    lines = plan.ledger_file.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def append_ledger(plan: Plan, record: dict) -> None:
    with plan.ledger_file.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def empty_entry() -> dict[str, dict | None]:
    return {"intent": None, "dispatched": None, "finished": None, "acknowledged": None}


def fold(records: list[dict]) -> dict[str, dict[str, dict | None]]:
    """Each key's standing intent, dispatch, finish and the operator's acknowledgement of a
    finish that stopped the driver; a `released` line clears all four so the key reads as
    unsent, while every run id the records name stays known."""
    state: dict[str, dict[str, dict | None]] = {}
    for record in records:
        entry = state.setdefault(record["key"], empty_entry())
        if record["kind"] == "released":
            entry.update(empty_entry())
        elif record["kind"] in entry:
            entry[record["kind"]] = record
    return state


def known_run_ids(records: list[dict]) -> set[int]:
    return {r["run_id"] for r in records if r["kind"] == "dispatched"}


def new_token() -> str:
    return f"dsp-{secrets.token_hex(6)}"


# --- GitHub -------------------------------------------------------------------------------------


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


def dispatch(plan: Plan, key: Key, token: str) -> str | None:
    """Send the dispatch bearing ``token``; when the call did not report success, why.

    A failed call does not mean no run: the thirtieth agent run's dispatch reached GitHub
    and its response was lost to a local connection abort (2026-10-16), so the caller reads
    for the run bearing the token rather than sending again.
    """
    args = [
        "workflow",
        "run",
        plan.workflow,
        "-f",
        f"world_version={plan.world_version}",
        "-f",
        f"scenario={key.scenario}",
        "-f",
        f"system={key.system}",
        "-f",
        f"condition={plan.condition}",
        "-f",
        f"level={key.level}",
        "-f",
        f"approval={plan.approval}",
        "-f",
        f"frappe_base_url={plan.frappe_base_url}",
        "-f",
        f"ledger={plan.ledger}",
        "-f",
        f"dispatch_token={token}",
    ]
    try:
        gh(*args, timeout=120)
    except subprocess.TimeoutExpired:
        return "the dispatch call timed out"
    except RuntimeError as error:
        return str(error)
    return None


def runs_bearing(plan: Plan, token: str, intended_at: str) -> list[dict]:
    """The workflow's recent runs whose name carries ``token``: the run name is the one
    channel a dispatch input comes back through (`run-name` in the workflow), and the
    token is twelve hex digits drawn for one send, so a run of another driver, a hand
    dispatch or a continuation never matches.

    An empty answer is a proof of absence only when the listing reaches back past the
    intent: the run was created after ``intended_at``, so a full listing whose oldest run
    is younger than the intent may have the bearer past its end, and the driver stops
    rather than conclude anything from it (the external read of the replay step).
    """
    runs = gh_json(
        "run", "list", "--workflow", plan.workflow, "--limit", LISTING_LIMIT, "--json", RUN_FIELDS
    )
    assert isinstance(runs, list)
    bearing = [run for run in runs if token in str(run.get("displayTitle", ""))]
    if bearing or len(runs) < int(LISTING_LIMIT):
        return bearing
    since = datetime.fromisoformat(intended_at)
    if all(datetime.fromisoformat(str(run["createdAt"])) > since for run in runs):
        raise Stop(
            f"the last {LISTING_LIMIT} runs of {plan.workflow} were all created after the intent "
            f"at {intended_at}, so a run bearing {token} may lie past the listing; nothing is "
            "concluded from it"
        )
    return bearing


def resolve_run(
    plan: Plan, token: str, head_sha: str, wait_seconds: int, intended_at: str
) -> tuple[int, str]:
    """The one run bearing ``token``, polled for up to ``wait_seconds``: its id and sha.

    Two runs bearing it stop the driver, since the token was drawn for one send. None
    within the wait is uncertain, not absent: GitHub may hold the run and list it late, so
    the driver stops with the intent standing and the next invocation looks again. A run
    on another commit than this checkout's is this driver's run on a tree it did not
    dispatch from, and stops the driver before any approval.
    """
    deadline = now() + timedelta(seconds=wait_seconds)
    while True:
        found = runs_bearing(plan, token, intended_at)
        if len(found) == 1:
            run_id, sha = int(found[0]["databaseId"]), str(found[0]["headSha"])
            if sha != head_sha:
                raise Stop(
                    f"run {run_id} bears {token} on {sha[:7]}, this checkout is {head_sha[:7]}; "
                    "the dispatch ran on a tree this driver did not dispatch from"
                )
            return run_id, sha
        if len(found) > 1:
            ids = ", ".join(str(run["databaseId"]) for run in found)
            raise Stop(f"more than one run bears {token} ({ids}); a token names one send")
        if now() > deadline:
            raise Stop(
                f"no run bearing {token} appeared within {wait_seconds} s; the intent stands: "
                "the next `run` looks again, and `release` clears it once Actions shows GitHub "
                "created nothing"
            )
        time.sleep(5)


def approve_if_pending(plan: Plan, run_id: int) -> str | None:
    """Approve the run's production review if it is pending; the approval's time, or None.

    A dispatched run is created waiting at the environment's review, so the pending
    deployment is normally listed at the first read; the wait covers the moments before
    GitHub lists it. A run already past the review (resumed after the driver died between
    the dispatch and the approval, or approved by hand) has nothing pending and nothing is
    sent: the run's approvals say so while it still queues for a runner, which took nine
    minutes on the replay set's wiring run (2026-10-22), so a queued run is not read as a
    missing review once an approval of the environment stands.
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
                    "comment": f"dispatcher: a run of the committed plan {plan.name}",
                }
            )
            gh("api", "-X", "POST", path, "--input", "-", input=body)
            return stamp(now())
        run = gh_json("run", "view", str(run_id), "--json", "status")
        assert isinstance(run, dict)
        if run["status"] in ("in_progress", "completed"):
            return None
        approvals = gh_json("api", f"repos/{REPOSITORY_NAME}/actions/runs/{run_id}/approvals")
        assert isinstance(approvals, list)
        by_hand = [
            a["user"]["login"]
            for a in approvals
            if a["state"] == "approved"
            and any(e["name"] == GATED_ENVIRONMENT for e in a["environments"])
        ]
        if by_hand:
            log(f"run {run_id}'s {GATED_ENVIRONMENT} review was approved by {by_hand[0]}; queued")
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


# --- The records of one run -------------------------------------------------------------------


KEPT_MARKERS = (
    "launch.admitted",
    "launch.reservation_pico_usd",
    "launch.ledger_revision",
    "launch.ledger",
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


def reasons_to_stop(plan: Plan, key: Key, conclusion: str, markers: dict[str, str]) -> list[str]:
    reasons = []
    if conclusion != "success":
        reasons.append(f"job conclusion {conclusion}")
    expected = {
        "launch.scenario": key.scenario,
        "launch.system": key.system,
        "launch.world_version": plan.world_version,
        "launch.ledger": plan.expected_ledger(key),
    }
    for field, value in expected.items():
        if markers.get(field) != value:
            reasons.append(f"{field} is {markers.get(field)!r}, the plan says {value!r}")
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


def finish(plan: Plan, key: Key, run_id: int) -> dict:
    conclusion = wait_for_run(run_id)
    markers = markers_of(run_id)
    kept = {name: markers.get(name) for name in KEPT_MARKERS}
    reasons = reasons_to_stop(plan, key, conclusion, markers)
    record = {
        "kind": "finished",
        "key": key.text,
        "run_id": run_id,
        "finished_at": stamp(now()),
        "conclusion": conclusion,
        "markers": kept,
        "stop_reasons": reasons,
    }
    append_ledger(plan, record)
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


def send(plan: Plan, key: Key) -> tuple[int, str]:
    """One send of ``key``: the intent written, the dispatch made, the run resolved by its
    token and recorded; the run's id and the sha it rides."""
    token = new_token()
    head = local_head()
    intended_at = stamp(now())
    append_ledger(
        plan,
        {
            "kind": "intent",
            "key": key.text,
            "token": token,
            "head_sha": head,
            "intended_at": intended_at,
        },
    )
    failure = dispatch(plan, key, token)
    if failure is not None:
        log(f"the dispatch call for {key.text} failed ({failure}); reading for {token}")
    run_id, sha = resolve_run(
        plan,
        token,
        head,
        ADOPTION_WAIT_SECONDS if failure is not None else RUN_ID_WAIT_SECONDS,
        intended_at,
    )
    line = {
        "kind": "dispatched",
        "key": key.text,
        "token": token,
        "run_id": run_id,
        "head_sha": sha,
        "dispatched_at": stamp(now()),
    }
    if failure is not None:
        line["dispatch_response"] = f"lost: {failure}"
    append_ledger(plan, line)
    log(f"dispatched {key.text}: run {run_id} on {sha[:7]} bearing {token}")
    return run_id, sha


def adopt(plan: Plan, key: Key, intent: dict) -> tuple[int, str]:
    """A key whose intent stands with no dispatched line: the earlier invocation died
    between its send and its record. The run bearing the intent's token is adopted; none
    stops the driver with the intent still standing, never a second send."""
    token = intent["token"]
    log(f"{key.text} has an intent bearing {token} and no dispatched line; reading for its run")
    run_id, sha = resolve_run(
        plan, token, intent["head_sha"], ADOPTION_WAIT_SECONDS, intent["intended_at"]
    )
    append_ledger(
        plan,
        {
            "kind": "dispatched",
            "key": key.text,
            "token": token,
            "run_id": run_id,
            "head_sha": sha,
            "dispatched_at": stamp(now()),
            "adopted": "from the intent, by a later invocation",
        },
    )
    log(f"adopted {key.text}: run {run_id} on {sha[:7]} bearing {token}")
    return run_id, sha


def next_action(key: Key, entry: dict[str, dict | None]) -> str:
    """What `run` does with an unfinished key, in words: the dry run's whole output."""
    if entry["dispatched"] is not None:
        return f"run {entry['dispatched']['run_id']} would be resumed for {key.text}"
    if entry["intent"] is not None:
        return f"the run bearing {entry['intent']['token']} would be adopted for {key.text}"
    return f"the next dispatch would be {key.text}"


def run(plan: Plan, max_runs: int, dry_run: bool) -> int:
    """The plan from its first unfinished key: each resumed, adopted or sent, approved and
    waited for, until the plan is complete, the run bound is reached or the driver stops.
    The bound counts every run the invocation handles, a resumed or adopted one as much as
    a sent one, so `--max 1` after a stop finishes the standing run and sends nothing: the
    wiring run of a sitting is read before the rest whatever path it took to its finish. A
    finished run whose record carries stop reasons stops every invocation until the
    operator's `acknowledged` line stands beside it or a `released` line clears the key, so
    a stop read by nobody is never walked past by a restart. A dry run names what the first
    unfinished key would get and ends there, before any send, approval or ledger line (both
    from the external read of the replay step).
    """
    records = read_ledger(plan)
    state = fold(records)
    handled = 0
    last_sha: str | None = None
    for key in plan.order:
        entry = state.get(key.text, empty_entry())
        finished = entry["finished"]
        if finished is not None:
            if finished["stop_reasons"] and entry["acknowledged"] is None:
                raise Stop(
                    f"{key.text} run {finished['run_id']} stopped the driver ("
                    + "; ".join(finished["stop_reasons"])
                    + "); the stop stands until `acknowledge --key` records that it was read, "
                    "or `release` clears the key"
                )
            continue
        if max_runs and handled >= max_runs:
            log(f"run bound {max_runs} reached; next is {key.text}")
            return 0
        if dry_run:
            log(f"dry run: {next_action(key, entry)}; nothing sent, nothing written")
            return 0
        handled += 1
        if entry["dispatched"] is not None:
            run_id = entry["dispatched"]["run_id"]
            log(f"resuming {key.text}: run {run_id} was dispatched and never recorded as finished")
        elif entry["intent"] is not None:
            run_id, _ = adopt(plan, key, entry["intent"])
        else:
            wait_until_idle()
            run_id, sha = send(plan, key)
            if last_sha is not None and sha != last_sha:
                log(f"NOTE the dispatched commit changed from {last_sha[:7]} to {sha[:7]}")
            last_sha = sha
        approved_at = approve_if_pending(plan, run_id)
        if approved_at is not None:
            append_ledger(
                plan,
                {"kind": "approved", "key": key.text, "run_id": run_id, "approved_at": approved_at},
            )
            log(f"approved {key.text}: run {run_id}'s {GATED_ENVIRONMENT} review, this login")
        record = finish(plan, key, run_id)
        if record["stop_reasons"]:
            raise Stop(f"{key.text} run {run_id}: " + "; ".join(record["stop_reasons"]))
    log("the plan is complete: every key has a finished record")
    return 0


def launch_read(run_id: int) -> str:
    """How far the job's launch send is known to have gone, read off the run log.

    ``none``: the runner printed no sending line, so the job ended before its first send
    (no running instance, a failed checkout). ``admitted``: the admit command's marker came
    back. ``sent``: everything else, which is all the log can say. A response lost after
    SSM accepted the command leaves no command id on the log and the host runs the command
    anyway; a relayed exit proves the process cannot admit later and not that it never
    admitted, since a commit whose acknowledgement was lost exits unsuccessfully without
    the marker (the two external reads of the replay step). Whether a sent launch admitted
    is the host's store to answer, through ``host_read``.
    """
    text = gh("run", "view", str(run_id), "--log", timeout=120)
    if not text.strip():
        raise Stop(f"run {run_id}'s log is empty; nothing is read from it")
    if LAUNCH_ADMITTED.search(text):
        return "admitted"
    if LAUNCH_SENDING.search(text) or LAUNCH_SENT.search(text):
        return "sent"
    return "none"


def host_read(status_run: int, run_id: int, launch_ended_at: str) -> str:
    """The host's answer about the launch's attempt, read off a continue-run the operator
    dispatched by hand for ``run-<run_id>`` attempt 1: the one durable evidence that a sent
    launch admitted nothing. The continuation's status step lists the attempt's lifecycle
    containers the host still runs and then runs the launcher, which asks the store for the
    attempt and prints the store's refusal when there is none; the runner relays both with
    the process's exit. The read counts only when that run completed and was created at
    least ``HOST_COMMAND_BOUND_SECONDS`` after the launch job ended, since SSM may hold a
    command undelivered for an hour and a store read before it started would answer about a
    host that had not admitted yet; and only when the listing names no container, since
    the SSM kill reaches the compose client and not the admit container, which can commit
    after a read that found nothing (the third external read). A status that answered a
    state means the attempt exists and the run holds its slot."""
    run = gh_json("run", "view", str(status_run), "--json", "status,workflowName,createdAt")
    assert isinstance(run, dict)
    if run["workflowName"] != CONTINUATION_WORKFLOW_NAME or run["status"] != "completed":
        raise Stop(
            f"run {status_run} is {run['status']} of {run['workflowName']!r}, not a completed "
            f"{CONTINUATION_WORKFLOW_NAME!r}"
        )
    created = datetime.fromisoformat(str(run["createdAt"]))
    waited = int((created - datetime.fromisoformat(launch_ended_at)).total_seconds())
    if waited < HOST_COMMAND_BOUND_SECONDS:
        raise Stop(
            f"continue-run {status_run} was created {waited} s after run {run_id}'s job ended; "
            f"SSM may hold the launch command undelivered for {HOST_COMMAND_BOUND_SECONDS} s "
            "after it, so the host's answer is not yet about the launch's end"
        )
    text = gh("run", "view", str(status_run), "--log", timeout=120)
    found = STATUS_NO_ATTEMPT.search(text)
    containers = STATUS_CONTAINERS.search(text)
    if found is None or containers is None or not STATUS_EXITED.search(text):
        raise Stop(
            f"continue-run {status_run}'s log holds no store refusal of an attempt of "
            f"run-{run_id} with the host's container listing and the status step's relayed "
            "exit; a status that answered a state means the attempt exists and the run holds "
            "its slot"
        )
    if found.group(1) != f"run-{run_id}" or found.group(2) != "1":
        raise Stop(
            f"continue-run {status_run} read {found.group(1)} attempt {found.group(2)}, not "
            f"run-{run_id} attempt 1"
        )
    if containers.group(1) != "none":
        raise Stop(
            f"continue-run {status_run} found lifecycle containers of run-{run_id} still "
            f"running ({containers.group(1)}); the launch's admit container may commit after "
            "the store was read, so the answer stands only once the host lists none"
        )
    return (
        f"continue-run {status_run}, {waited} s after the launch job ended, read the host: "
        f"no lifecycle container of run-{run_id} running, and the store has no attempt 1"
    )


def release(plan: Plan, key: Key, reason: str, status_run: int | None = None) -> int:
    """The operator's line after reading Actions: a key whose intent stands with no run
    bearing its token, or whose finished run stopped the driver before any attempt was
    admitted, may be sent once more. The line names what was read: for an intent, that no
    run bears the token in a listing reaching back past the intent; for a finished run,
    that the run is completed and either its log shows no launch was sent, or the host's
    store, read through the continue-run ``status_run`` names, holds no attempt of it. Any
    other state is refused: a run that admitted an attempt holds its slot under PROTOCOL, a
    sent launch without the host's answer may have admitted, and the fold's history is
    never edited."""
    entry = fold(read_ledger(plan)).get(key.text, empty_entry())
    if entry["intent"] is None and entry["dispatched"] is None:
        raise Stop(f"{key.text} has nothing to release: it was never sent")
    if entry["finished"] is not None:
        if not entry["finished"]["stop_reasons"]:
            raise Stop(f"{key.text} finished without a stop reason and holds its slot")
        if entry["finished"]["markers"].get("launch.admitted"):
            raise Stop(
                f"{key.text} admitted {entry['finished']['markers']['launch.admitted']} and holds "
                "its slot under PROTOCOL; a retry goes through continue-run by hand"
            )
        run_id = entry["finished"]["run_id"]
        run = gh_json("run", "view", str(run_id), "--json", "status,updatedAt,attempt")
        assert isinstance(run, dict)
        if run["status"] != "completed":
            raise Stop(f"run {run_id} is {run['status']}, not completed; it may still admit")
        if int(run["attempt"]) != 1:
            raise Stop(
                f"run {run_id} has {run['attempt']} job attempts; the driver dispatches once and "
                "re-runs nothing, so a re-run by hand is a history it does not release"
            )
        launch = launch_read(run_id)
        if launch == "admitted":
            raise Stop(
                f"run {run_id}'s log carries an admission its markers did not; the run holds "
                "its slot under PROTOCOL"
            )
        if launch == "none":
            read = f"run {run_id} completed; its launch was never sent"
        elif status_run is None:
            raise Stop(
                f"run {run_id} sent its launch, and the log cannot say whether the host "
                "admitted; dispatch continue-run by hand for run-"
                f"{run_id} attempt 1 no sooner than {HOST_COMMAND_BOUND_SECONDS} s after the job "
                "ended, and pass its run id as --status-run"
            )
        else:
            read = host_read(status_run, run_id, str(run["updatedAt"]))
    elif entry["dispatched"] is not None:
        raise Stop(
            f"{key.text} has run {entry['dispatched']['run_id']} dispatched and not finished; "
            "`run` resumes it"
        )
    else:
        assert entry["intent"] is not None
        token = entry["intent"]["token"]
        found = runs_bearing(plan, token, entry["intent"]["intended_at"])
        if found:
            raise Stop(f"a run bears {token} ({found[0]['databaseId']}); `run` adopts it")
        run_id = None
        read = f"no run bears {token} among the last {LISTING_LIMIT} runs of {plan.workflow}"
    append_ledger(
        plan,
        {
            "kind": "released",
            "key": key.text,
            "run_id": run_id,
            "reason": reason,
            "read": read,
            "released_at": stamp(now()),
        },
    )
    log(f"released {key.text}: {reason} ({read})")
    return 0


def acknowledge(plan: Plan, key: Key, reason: str) -> int:
    """The operator's line after reading a stop: the key's finished run keeps its record and
    its slot, and `run` walks past it from then on. Refused for a key with no finished run,
    a finish that stopped nothing, or a stop already acknowledged."""
    entry = fold(read_ledger(plan)).get(key.text, empty_entry())
    finished = entry["finished"]
    if finished is None:
        raise Stop(f"{key.text} has no finished run to acknowledge")
    if not finished["stop_reasons"]:
        raise Stop(f"{key.text} finished without a stop; there is nothing to acknowledge")
    if entry["acknowledged"] is not None:
        raise Stop(
            f"{key.text} was acknowledged at {entry['acknowledged']['acknowledged_at']} already"
        )
    append_ledger(
        plan,
        {
            "kind": "acknowledged",
            "key": key.text,
            "run_id": finished["run_id"],
            "reason": reason,
            "acknowledged_at": stamp(now()),
        },
    )
    log(f"acknowledged {key.text}: run {finished['run_id']}'s stop was read ({reason})")
    return 0


def status(plan: Plan) -> int:
    state = fold(read_ledger(plan))
    per_cell: dict[str, list[int]] = {}
    stopped: list[str] = []
    next_key = None
    last_inventory = None
    for key in plan.order:
        cell = f"{key.system}/{key.level}"
        counts = per_cell.setdefault(cell, [0, 0])
        entry = state.get(key.text)
        if entry is None or (entry["intent"] is None and entry["dispatched"] is None):
            if next_key is None:
                next_key = key.text
            continue
        if entry["finished"] is None:
            counts[1] += 1
            if next_key is None:
                next_key = key.text + (" (adopt)" if entry["dispatched"] is None else " (resume)")
            continue
        counts[0] += 1
        if entry["finished"]["stop_reasons"]:
            stopped.append(
                f"{key.text} run {entry['finished']['run_id']}"
                + (" (acknowledged)" if entry["acknowledged"] is not None else "")
                + ": "
                + "; ".join(entry["finished"]["stop_reasons"])
            )
        last_inventory = entry["finished"]["markers"].get("inventory.inventory_digest")
    print(
        f"plan {plan.name}: world {plan.world_version[:12]}, site {plan.frappe_base_url}, "
        f"ledger {plan.ledger}"
    )
    print(f"{'cell':<24}{'finished':>10}{'open':>6}")
    for cell, (done, open_) in per_cell.items():
        print(f"{cell:<24}{done:>10}{open_:>6}")
    print(f"next: {next_key or 'none, the plan is complete'}")
    print(f"last inventory digest: {last_inventory}")
    for line in stopped:
        print(f"stopped: {line}")
    return 0


def main(argv: list[str]) -> int:
    global _log_file
    parser = argparse.ArgumentParser(description="the dispatcher of a committed plan")
    parser.add_argument(
        "--plan-dir",
        type=Path,
        default=HERE,
        help="the directory holding plan.json and ledger.jsonl; this file's own by default",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    runner = sub.add_parser("run")
    runner.add_argument(
        "--max",
        type=int,
        default=0,
        help="runs this invocation may handle, resumed or sent; 0 is no bound",
    )
    runner.add_argument(
        "--dry-run", action="store_true", help="name the next dispatch and send nothing"
    )
    releasing = sub.add_parser("release")
    releasing.add_argument("--key", required=True, help="system/level/scenario")
    releasing.add_argument("--reason", required=True, help="what Actions showed, in your words")
    releasing.add_argument(
        "--status-run",
        type=int,
        help="a completed continue-run of the launch's run id whose status read found no "
        "attempt; required for a finished run whose launch was sent",
    )
    acknowledging = sub.add_parser("acknowledge")
    acknowledging.add_argument("--key", required=True, help="system/level/scenario")
    acknowledging.add_argument(
        "--reason", required=True, help="what the stop's run showed and why the plan continues"
    )
    args = parser.parse_args(argv)
    try:
        plan = read_plan(args.plan_dir.resolve())
        _log_file = plan.log_file
        if args.command == "status":
            return status(plan)
        if args.command == "release":
            return release(plan, Key.of(args.key), args.reason, args.status_run)
        if args.command == "acknowledge":
            return acknowledge(plan, Key.of(args.key), args.reason)
        return run(plan, args.max, args.dry_run)
    except Stop as stop:
        log(f"STOP {stop}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
