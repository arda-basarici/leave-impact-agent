# Phase C: dispatching the reported runs

The 240 reported runs of M2's exit (four systems at the base and the padded level over
the measurement world's thirty scenarios, one repeat) go through `investigate.yml` one
at a time. `dispatch.py` sends them in the plan's fixed order and writes the ledger that
records each; its module docstring carries the rules it keeps and why. This file is the
runbook.

- `plan.json`: the order, written once by `plan` and committed; the script refuses a plan
  that differs from its own constants.
- `ledger.jsonl`: append-only, committed at the end of every sitting. One `dispatched`
  line per run as soon as its id is known, one `finished` line when the job has ended
  with the runner's markers and the reasons the driver stopped, if any. A key with a
  `dispatched` line is never sent again.
- `data/phase-c-dispatch/driver.log` (git-ignored): every printed line, for a second
  terminal to follow.

## Running it

From the repository root, `gh` logged in, in a terminal that outlives the chat:

```
uv run python probes/phase-c-dispatch/dispatch.py status
uv run python probes/phase-c-dispatch/dispatch.py run --max 1
uv run python probes/phase-c-dispatch/dispatch.py run
```

The first run of a sitting is sent with `--max 1` and read before the rest. `Ctrl+C` is
safe at any moment: a run already dispatched is resumed by the next invocation, which
waits on it and records it.

## The review

Each dispatched run waits at the `production` environment's review. The driver approves
it under your `gh` login right after the `dispatched` line is written, and records an
`approved` line; the plan is committed, so every dispatch of it is intended (ruled
2026-10-16). A run dispatched and not yet approved when the driver died is approved on
resume; one you approved by hand is left alone. A dispatch the plan did not make still
waits for you.

## When it stops

The driver prints `STOP` with the reason and exits 1. The reason is one of: the job did
not succeed; the attempt's ending is not closed and completed (a cap, a defect, an
infrastructure failure); the publication is not published or carries an incident; the
inventory was not created; or the admission names another scenario, system or world than
the key. Each is an operator's decision under PROTOCOL ("How a run is counted") and the
decision is written in the session log before anything else is sent. The driver never
re-dispatches the key: a replacement would be surplus, or would take the slot an
unexported run holds. A retry an attribution row permits goes through `continue-run.yml`
by hand, outside the driver.

## Deploys

The driver refuses to dispatch while any run of `investigate.yml`, `continue-run.yml` or
`ci.yml` is queued, running or waiting at its gate, and says which. A push during the
phase therefore pauses the driver until its deploy is approved or rejected; approve one
only while the driver is stopped or paused, never during a run (the instance README).
During the phase the ledger is committed locally and pushed at the end of a sitting; the
push's deploy is approved before the next sitting's first dispatch, so the image's commit
stays one across a sitting.

## Reading the result

`tally.py` prints the operational table (cost, calls, saturation per cell) from the
runs' exports; `report.py` prints the evaluation's tables (each arm's correct-whole
count, the registered comparisons with their intervals, the mechanism stages, the arms
not run) from the reported artifact. FINDINGS `phase-c` cites both. The artifact is read
from a local file, which one fetch under the SSO profile produces:

```
aws s3api get-object --profile leave-impact --bucket leave-impact-truth-445743457479 \
  --key evaluations/2e6705ba7d11095a9b797abe08495c5497a7c5fe560fa587868763f11192341c/39061375799-1.json \
  --version-id oOBaiqTYdK9aqtdTH5bGDoCZLXPsfcVG data/phase-c-dispatch/evaluation-39061375799-1.json
uv run python probes/phase-c-dispatch/report.py data/phase-c-dispatch/evaluation-39061375799-1.json
```

The script refuses any artifact but the reported one by its format, label, world,
inventory digest and run count, so a figure it prints is that artifact's.
