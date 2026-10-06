# The crash matrix's manifest

One authoritative list of the kill points the matrix runs and what each is forecast to leave
(the event log step's ruling on placement and acceptance, part 8). Written before the first
run on 2026-10-06; a forecast that the run contradicts is a finding, and the manifest is
amended with the finding named, never silently.

The reference run is the worker group's two-call script over the golden world's first
scenario: the claim, nine prefetch reads, a count and a dispatch for call 1, two reads the
model asked for, a count and a dispatch for call 2, the finalization, the approval request,
the automatic approval, the resume, the completion. Every crossing the reference makes is a
row; a kill point is named `<family>#<occurrence in its process>`.

## What holds at every row

- The killed child's uncommitted transaction leaves nothing: a kill at `locked`, `decided`
  or `before-commit` of a write leaves that write absent, since the session dies before its
  commit. Nothing a killed child wrote is ever rewritten.
- Recovery claims a fresh generation on a fresh checkpoint thread and replays from the log,
  so no checkpoint of the dead generation is read; the boundary invariant (every position
  and digest a checkpoint or a pending write represents is in the log) holds all the same.
- A request left in flight at a kill (a count started with no outcome, a dispatch intent
  with no outcome) stays unresolved for good: recovery counts or dispatches again under the
  next ordinal or number, and no outcome is ever written under the in-flight one.
- A logged read is never repeated; an unlogged one may be, once: a killed child's port reads
  exceed the operations it logged by at most one, the completing child's equal them. A
  saver seam fires on the framework's background thread, so its kill lands anywhere in the
  main thread's step, between a read and its append included (CI's first run, below).
- One approval, one closing event, one settled ledger entry; the export builds, round-trips,
  and holds the reference's operations and claims.

## Kill points of the first process

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| `load:read` | the admission alone; no claim | the first claim is the recovery's (generation 1); the whole run follows |
| `segment_started:locked` | the admission alone | as above |
| `segment_started:decided` | the admission alone | as above |
| `segment_started:before-commit` | the admission alone | as above |
| `operation:locked` | every earlier write; this read made, not logged | the read is made again (one more port read) and logged |
| `operation:decided` | as above | as above |
| `operation:before-commit` | as above | as above |
| `count_started:locked` | every earlier write | the count is started and counted once |
| `count_started:decided` | as above | as above |
| `count_started:before-commit` | as above | as above |
| `count_outcome:locked` | the count's start, no outcome | the start stays unresolved; a second start under the same reuse key is counted; the bound rests on it |
| `count_outcome:decided` | as above | as above |
| `count_outcome:before-commit` | as above | as above |
| `dispatch_intent:locked` | the count; no intent, no send | the intent is appended and sent once |
| `dispatch_intent:decided` | as above | as above |
| `dispatch_intent:before-commit` | as above | as above |
| `dispatch_outcome:locked` | the intent; the response arrived and is lost | the intent stays unresolved; a second intent under the next number is sent (one more send), answered, and the call stands on it |
| `dispatch_outcome:decided` | as above | as above |
| `dispatch_outcome:before-commit` | as above | as above |
| `finalization_entered:locked` | both calls answered and their reads resolved | finalization is entered once |
| `finalization_entered:decided` | as above | as above |
| `finalization_entered:before-commit` | as above | as above |
| `approval_requested:locked` | the finalization | the request is appended once, the policy approves |
| `approval_requested:decided` | as above | as above |
| `approval_requested:before-commit` | as above | as above |
| `approved:locked` | the request; no approval | the policy approves at the recovery's pause; one approval |
| `approved:decided` | as above | as above |
| `approved:before-commit` | as above | as above |
| `approval:delivered` | the approval; no resume | the recovery reads the logged approval, resumes, completes |
| `approval:node-resumed` | as above | as above |
| `resumed:locked` | the approval | the resume is appended once |
| `resumed:decided` | as above | as above |
| `resumed:before-commit` | as above | as above |
| `completed:locked` | the resume; the attempt open | the closing event is appended once with one settlement |
| `completed:decided` | as above | as above |
| `completed:before-commit` | as above | as above |
| `checkpoint:before` | every event of the step; the checkpoint not written | ignored by the recovery (fresh thread); the boundary invariant holds. After the terminal step the attempt is already closed and the recovery leaves it at its load (the first run's finding, below) |
| `checkpoint:after` | the step's events and its checkpoint | as above |
| `writes:before` | the step's events; the task's pending writes not written | as above |
| `writes:after` | the step's events and its pending writes | as above |

## Kill points of the recovering process

Every twelfth crossing of the reference also gets two rows in which the recovering child is
killed and a third child completes.

| Family | Durable at the boundary | Forecast |
|---|---|---|
| `segment_started:before-commit#1` (of the recovery) | the first kill's state; no second claim | the third child's claim is generation 2; everything the first kill left in flight stays so |
| `completed:decided#1` (of the recovery) | everything but the closing event; the attempt open at generation 2 | the third child claims generation 3, replays to the held approval and resume, closes once; the in-flight set is the first kill's |

## Findings against the forecasts

- **2026-10-06, the first run** (130 rows, 126 passed): the four saver crossings of the
  terminal step (`checkpoint:before#10`, `checkpoint:after#10`, `writes:before#11`,
  `writes:after#11`) come after the closing event committed, so the recovering child found
  the attempt closed and ended `closed_already`, where the forecast had every recovery
  completing the run itself. The worker is right (the ruling on recovery, part 4: a closed
  attempt only finishes publication); the forecast was written as if every crossing preceded
  the closure. The rows accept the recovery leaving a closed attempt, and the reconciliation
  runs on the log as it stood.
- **2026-10-06, the first CI run** (`writes:after#4`): the kill fired on the saver's thread
  while the main thread had read a port and not yet appended the operation, so the recovery
  read it again and the row counted one port read above the reference where the forecast
  allowed a repeat only for a kill inside the operation's own write. The invariant is now
  stated per process (above); the worker did what the ruling on tool calls, part 8, says.
