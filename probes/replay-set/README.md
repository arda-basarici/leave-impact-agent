# The replay set: dispatching the demo's thirty replays

The demo surface (M3) shows the registered investigator at the base level over the golden
world's thirty scenarios: thirty runs of `investigate.yml` on the golden world's HR site
against the demo ledger (the demo milestone's step 8, its forks file in the stream). They
go through the phase-C driver, `../phase-c-dispatch/dispatch.py`, with this directory as
the plan: the driver's module docstring carries the rules it keeps and why, and the
phase-C README the review arrangement and what a `STOP` means. This file is the runbook
for this plan.

- `plan.json`: the one cell over the thirty scenarios in id order, the world version, the
  HR site and the ledger, equal to the demo configuration the surface ships
  (`src/leaveimpact/app/demo.json`), which a unit test asserts; written once and
  committed.
- `ledger.jsonl`: append-only, committed at the end of every sitting; one `intent` line
  before each send, one `dispatched` line when the run bearing the send's token is
  found, one `approved` line, one `finished` line with the runner's markers; a
  `released` or an `acknowledged` line only by an operator's hand through `release` or
  `acknowledge`, the phase-C README saying when each applies.
- `data/replay-set/driver.log` (git-ignored): every printed line.

## Running it

From the repository root, `gh` logged in, in a terminal that outlives the chat, after the
`hr-w3` investigator pair is in the two SSM parameters:

```
uv run python probes/phase-c-dispatch/dispatch.py --plan-dir probes/replay-set status
uv run python probes/phase-c-dispatch/dispatch.py --plan-dir probes/replay-set run --max 1
uv run python probes/phase-c-dispatch/dispatch.py --plan-dir probes/replay-set run
```

The first run is the wiring run: its job log is read for the `LEDGER=ledger-demo` line
and the `hr-w3` site before the rest is sent, and its `launch.ledger_revision` is
compared with the forecast in the step's forks file. `Ctrl+C` is safe at any moment: a
run already dispatched is resumed by the next invocation, a send whose run was not yet
recorded is adopted by its token, and a key is never sent twice by the driver.

## After the batch

Each finished record's `launch.admitted` names the run and attempt the `publish`
operator command takes on the host. `publish_list.py` generates the thirty commands from
the ledger, in plan order, with the host's preamble (the deployed tag and the database
password exported the deploy script's way), so no run id is ever typed; it refuses an
incomplete plan, a stopped run, a malformed admission or a title naming no row:

```
uv run python probes/replay-set/publish_list.py --titles data/replay-set/titles.json
```

The titles file (public id to title, the three introduced examples) is written after the
local grading picks them, since a published row's title is fixed at its publish.

`grade_replays.py` grades the thirty admitted exports locally against the golden world with
the evaluator's own grader and writes `grading.json` beside this file: per run the outcome,
correct whole or not, where a miss falls short (rows unexpected, not matched, required and
not reported, or differing in payload, per kind) and the oracle's plan findings by kind,
with the tier, the export's key, version id and digest; never a claim's or the world's
text. It reads the two buckets under the administrator profile, since the golden world's
`runs/` prefix also holds older development runs a workflow evaluation would take as the
scenarios' first runs. `tests/unit/test_replay_grading.py` holds the committed file to the
plan and the ledger. The operational tally (cost, calls, tokens) is the phase-C script's:

```
AWS_PROFILE=leave-impact uv run python probes/replay-set/grade_replays.py
AWS_PROFILE=leave-impact uv run python probes/phase-c-dispatch/tally.py --plan-dir probes/replay-set
```
