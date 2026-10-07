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
| `send:before` | the intent committed; nothing sent | the intent stays unresolved, a dispatch authorized and never sent; the recovery sends under the next number and the call stands on it; the sends across every child are the reference's, the killed child having sent nothing (the close's review, second finding: the reconciliation had required a send per committed intent) |
| `send:after` | the intent; the response arrived and is lost before the outcome's lock | as `dispatch_outcome:locked` |
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

Every sixteenth crossing of the reference also gets one row per family the recovering child
crosses, in which that child is killed at its first crossing of the family and a third child
completes. The families are read off a scout of that recovery (the first kill, then an
uninterrupted recovery child whose crossings are recorded), never off the reference's suffix:
a lost outcome makes the recovery append an intent or a count start the suffix no longer
holds (the second read's third finding). The load's read and the saver's seams are not
repeated here; a recovery that finds the attempt closed crosses nothing and gets no row.

| Family | Durable at the boundary | Forecast |
|---|---|---|
| `segment_started:before-commit#1` (of the recovery) | the first kill's state; no second claim | the third child's claim is generation 2; everything the first kill left in flight stays so |
| any write's family `#1` (of the recovery) | the first kill's state, the recovery's claim, and the recovery's writes before this one | the third child claims generation 3 and finishes; the in-flight set is the union of what the two kills left, each counted or dispatched again under the next number; a read the recovery made and did not log is made once more |
| `completed:decided#1` (of the recovery) | everything but the closing event; the attempt open at generation 2 | the third child claims generation 3, replays to the held approval and resume, closes once; the in-flight set is the first kill's |

## Kill points of the second reference, the infrastructure stop

The throttled run (`worker_support.throttled_script`, the child's script `throttled`): the
two-call turns with every dispatch of the first call answered by a throttle, so the call is
dispatched three times under the fixtures' policy (a maximum of three, a delay of zero),
exhausts it and the attempt fails by infrastructure at the third dispatch's send; no read the
model asked for, no finalization, no approval, no claims. It exists because the one completing
reference passed over the replay's ordinal shift under an outage and the recovery's skipped
delay (the worker group's review, sixth finding): the exhaustion endings had no kill row.
Every family the first reference crosses before its model's answer is crossed here too and is
forecast as above; the rows below are the ones whose forecast differs or is new. Every
recovery is held to the ending `failed`, closed by itself or found closed. Forecasts written
on 2026-10-07 before the first run.

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| the families before the model's answer: `load:read`, the segment start, the operations, the count's start and outcome, the dispatch intent | as the first reference's | as the first reference's; the run then fails at the third dispatch as the reference did |
| `send:before` | the intent committed; nothing sent | at dispatch 1 or 2: the intent stays unresolved and counts against the bound, the recovery sends under the next number up to the third and fails there; two sends in all. At dispatch 3: the call is at its maximum with its last dispatch unresolved and never sent, the recovery sends nothing and fails by the unresolved reading; two sends in all |
| `send:after` | the intent; the throttle arrived and is lost before the outcome's lock | as `dispatch_outcome:locked` |
| `dispatch_outcome:locked` | the intent; the throttle arrived and is lost | at dispatch 1 or 2 (occurrences 1 and 2): the intent stays unresolved and counts against the bound, the recovery dispatches the next number up to the third, each throttled, and fails at the third dispatch's send; the sends across every child are three, one per committed intent, so no send beyond the reference's. At dispatch 3 (occurrence 3): the call is at its maximum with its last dispatch unresolved, so the recovery sends nothing and fails at the third dispatch's send by the unresolved reading; the settled events are the reference's, the closing event's reason differs |
| `dispatch_outcome:decided` | as above | as above |
| `dispatch_outcome:before-commit` | as above | as above |
| `failed:locked` | every dispatch resolved; the attempt open | the recovery finds the call failed from the log and finalizes `failed` without running the graph, once, with one settlement |
| `failed:decided` | as above | as above |
| `failed:before-commit` | as above | as above |
| the saver's seams, `checkpoint:before` to `writes:after` | as the first reference's | as the first reference's; after the terminal step the attempt is closed and the recovery leaves it |

## Kill points of the commands

The job seam's commands (the ruling on placement and acceptance, part 8), each run by a
child of its own over a store the parent prepared, one row per crossing of the command's
uninterrupted run, the row's recovery the same command run again under the same request.
No recovery-process rows: a command's recovery is one call, and a kill there is the
first-process row again. The families are named under the mode, since `put:before` is
crossed by two commands and `load:read` by the worker and the publish command.
Forecasts written on 2026-10-07 before the first run.

### Admission, the receipt path (the threshold set, nothing admitted)

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| `admit/admit:locked` | nothing; the run row's insert is in the uncommitted transaction | the command run again under the same request identity admits: one attempt row at position one, one admission event, the ledger's threshold and one admitted entry, no refusal |
| `admit/admit:before-commit` | nothing; the attempt row, the admission event, the reservation and the request's record are all uncommitted | as above |

### Admission, the refusal path (the first attempt admitted and open, the second asked)

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| `admit-refused/admit:locked` | the first attempt as admitted | the command run again refuses: the first attempt untouched at its admission alone, one refused request for attempt two, no ledger entry for the refusal (the predecessor refused, not the ledger) |
| `admit-refused/admit:before-commit` | the first attempt as admitted; the refusal's record uncommitted | as above |

### Publication (the reference attempt completed by an uninterrupted worker)

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| `publish/load:read` | the closed attempt; no record, no object | the command run again publishes: the pending record, the object created, the published record naming it |
| `publish/publication_pending:locked` | as above | as above |
| `publish/publication_pending:before-commit` | as above; the pending record uncommitted | as above |
| `publish/put:before` | the pending record naming the key and digest; no object | the pending record rewritten under the same reader, the object created, published |
| `publish/put:after` | the pending record and the object | the pending record rewritten, the put answers present and equal, published |
| `publish/publication_published:locked` | as above | as above |
| `publish/publication_published:before-commit` | as above; the published record uncommitted | as above |

At every row the end state is one: the record published, naming the export's key under the
reader's commit and the digest of the one object under the run's prefix, repaired from
nothing; the object's bytes are the reader's export of the closed log.

### The inventory (the reference attempt completed and published)

| Family | Durable at the boundary | Recovery, forecast |
|---|---|---|
| `inventory/snapshot:read` | the published attempt; no inventory | the command run again writes one inventory, created, named by its digest, listing the attempt closed and published |
| `inventory/put:before` | as above | as above |
| `inventory/put:after` | the inventory object, nothing in the store (the command writes none) | the command run again takes a new snapshot at a later instant and writes a second inventory, created; both decode, both are named by their digests, both list the attempt closed and published |

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
- **2026-10-07, the external review** (findings 2, 4 and 6): a run with an outage and a run
  with a re-dispatch were outside the one reference script, which is why a 130-row matrix
  passed over the replay's ordinal shift under an outage and the recovery's skipped delay;
  both are held by unit tests now, and a second reference script with an infrastructure
  stop is parked to the step's close. The recovery rows went from two fixed targets to one
  per family the recovering child crosses.
- **2026-10-07, measured after the review:** with one recovery row per family at every
  twelfth crossing the matrix ran 338 rows in ten and a half minutes; at every sixteenth with
  six rows at a time, 282 rows in six minutes fifteen, every row passing. The job's time is
  six minutes, not the four the first forecast guessed from one reference script.
- **2026-10-07, after the second read:** the recovery targets scouted from each sampled
  kill's own recovery path ran 303 rows in nine minutes twenty-five, every row passing; the
  21 rows beyond the suffix method's 282 are the families a lost outcome makes the recovery
  add (a new intent, a new count start), which the reference's suffix could not name.
- **2026-10-07, the commands' first run:** the four command references crossed the fourteen
  families forecast above and no other, and the fourteen rows passed, in eighty-four seconds
  with the worker's reference and the four command references before them; the inventory's
  `put:after` row left two inventories as forecast, every other row one object. The whole
  matrix with them, 317 rows, ran in nine minutes ten, every row passing.
- **2026-10-07, the second reference (the step's close):** the throttled reference's rows
  alone first, 152 of 152 on the first run, every forecast of its section held, the one
  about a lost outcome at the third dispatch included. The whole matrix then: 469 of 469
  rows, the family test red on this section's text, which had grouped families in one cell
  and used wildcards the reader does not parse; the rows were rewritten one family each and
  the matrix rerun, 469 of 469 in twelve minutes forty-six.
- **2026-10-07, the close's review (its second finding):** the reconciliation had required
  one send per committed intent, and a kill between an intent's commit and its send, a
  dispatch authorized and never sent, which the ruling on the fence allows, had no row and
  would have been refused. The model client's send is crossed as `send:before` and
  `send:after` on both references, the invariant reads a resolved intent sent once and an
  in-flight one at most once, and the first run with the two families passed 503 of 503
  rows in fifteen minutes twenty-seven (the two-call reference 116 crossings, the throttled
  one 86).
