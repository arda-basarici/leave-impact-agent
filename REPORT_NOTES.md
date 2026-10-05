# Report notes — Leave Impact Agent

Raw material for milestone reports and posts: decision narratives distilled at the
moment they happen, so the reports can tell the story without excavating chat logs.
Append-only, newest first. Each entry is a self-contained story with its date and the
decisions it feeds.

---

## 2026-10-05 — The durable checkpoint was kept and stopped being what recovery reads

*M2, the design interview for the event log and job seam: how a run attempt is recovered
after its process dies, and what a worker that lost ownership can still write. Feeds: the
M2 report's harness section, on recovery from the log and what the framework's checkpoint
is for; and the methodology section, on a recommendation withdrawn before any code.*

**[RULED, NOT BUILT. This is a design ruling with no production code behind it. The two
measurements cited are the acceptance spike's, on its prototype log. What would revise
it: the build's crash matrix, which has to pass on the new recovery path, and any replay
from the log that turns out to repeat a model request.]**

The harness keeps two stores for a run attempt. The event log is the audit authority and
the only thing an export is built from. The framework's checkpoint is the execution
cursor. Every node looks in the log before it does anything, so a result already logged
is reused and nothing is executed twice. The acceptance spike proved recovery on that
arrangement by killing a child process at 82 points around the appends and the checkpoint
writes, all 82 recovering (the spike's crash matrix, cited at commit `f2d1f28`).

The spike assumed one writer per run. The interview replaced that with ownership: an
attempt has a generation, a worker claims it, and a later claim fences the earlier worker
so that its next append is refused. That left a question the spike never had to ask. The
framework writes checkpoints on a background thread after a node returns, so a fenced
worker can still write one after the new owner has resumed, and no check against the
log's generation can be made atomic with a write to another store.

The proposal was to leave both workers on one checkpoint thread and rely on the log. The
argument was that a stale checkpoint is only an older cursor whose content the log
already holds, and the spike had measured recovery from an older checkpoint. A probe in
the build would confirm it by making a fenced worker write a checkpoint late.

An outside read of the proposal objected that a checkpoint is more than a position. The
framework also saves each task's pending writes and uses them to decide which tasks to
skip on resume, so "every node checks the log" does not protect a node that recovery
decides not to run. That connected to something the spike had already recorded for
another reason: when a node raises, the framework saves an error write for it. A fenced
worker's node raises at exactly that moment, on its refused append. A late error write
against a checkpoint the new owner also resumed from is therefore a concrete path, and
the "older cursor" argument did not cover it.

Nothing was shown to corrupt a recovery, by the review or by anyone else. What changed
was the cost of being sure. The probe that would clear the shared thread had grown from
one case to three classes of hazard: late pending writes, two workers creating different
descendants of one checkpoint, and stale interrupt state surviving an approval. The
alternative excludes all three by construction. The checkpoint thread is derived from the
run, the attempt and the generation, so everything a fenced worker writes lands where no
later owner reads, and every claim starts on a fresh thread and replays from the log. The
spike had measured that path too: a run restarted from the beginning on a new thread
completed from the log with no model request (the spike's catalogue, the unloadable
checkpoint row, same commit). The recommendation was withdrawn and the thread per
generation ruled.

The consequence is the part worth telling plainly. A generation is one claim by one
process, so no process ever reads another's checkpoints. The PostgreSQL saver's
durability now serves inspection, and the system behaves as it would with an in-memory
saver. Recovery is from the log. The saver was kept anyway, with the accepted
configuration and the pinned versions unchanged, because dropping it is a cheap later
decision and reopening the framework ruling in the middle of this one was not.

A third option was on the table and was the simplest: no durable checkpoint at all, the
log as the only store. Once every node replays from the log a durable checkpoint is
largely redundant, and the ruled design is one configuration change away from that. It
was not taken, for reasons that are partly engineering and partly about what the project
shows: the spike's must-pass rows were accepted on the PostgreSQL saver, the demo
milestone plans its asynchronous variant, and a reader judging the framework work would
look for durable checkpointing. The weighing shifted during the discussion. Recovery by
replaying an append-only log under generation fencing, held by a crash matrix, came to
look like the stronger thing to show than a checkpoint that resumes.

It also made the recovery driver smaller. Across processes there is one path, a fresh
thread and a replay. The spike's other recovery states still exist, but only inside a
process that is alive.

Figure: the two stores before and after the ruling, with which process reads which
checkpoint thread across a takeover.

## 2026-10-05 — An operator could have chosen which attempt counts, and the guard that closed it reads the log instead of the reason

*M2, the design interview for the event log and job seam: when a failed run may be
attempted again. Feeds: the M2 report's methodology section, on attempt accounting and
selection effects; and the limitations section, for the residual stated below.*

**[RULED, NOT BUILT. A design ruling; the eligibility function and its audit do not exist
yet. No count of abandonments exists either, since no reported run has been made. What
would revise it: the first reported runs, if attempts that cannot be resumed after their
first model call turn out to be common enough that losing them distorts a comparison.]**

The fork opened on a finding in the tree. The question "may this run be attempted again"
was answered in two places that had never been reconciled. The attribution table, which
fixes before any result how each model-call failure is read, carries a per-row flag
saying whether a failure on that reading makes the run eligible for a new attempt. The
registration's run accounting carries a retry rule: one failure category an attempt is
retried after, and a maximum number of attempts. Neither said anything about a failure
that is not at a model call.

Reconciling them was straightforward. Eligibility became a conjunction: the predecessor
closed, the maximum not reached, the category the registered one, and a named rule
granting it, with any ending no rule names not eligible. The harder problem appeared
while writing the row for abandonment.

The registered rule for which attempt of a run is counted takes the earliest attempt
that is not an infrastructure failure. An abandonment is an infrastructure failure, and
it happens by an operator's decision. So an operator watching a run go badly could
abandon it and have a fresh attempt counted in its place. The proposal said so and
offered only evidence against it: the abandoned attempt still exports with everything it
did, and a report lists attempts and failures beside the metrics.

An outside read answered that listing the history exposes a selection without
neutralizing it. A replacement that succeeds improves the end-to-end result, and even
without one the excluded attempts move the denominators of the quality measures. It
proposed that eligibility be governed by a registered reason with supporting evidence,
and in the same reply conceded the weakness of both obvious mechanisms: a reason the
operator picks is not evidence, and refusing abandonment while a worker is "live" fails
because ownership does not prove liveness and stopping the process first walks around it.

The rule adopted is mechanical and does not read the reason at all. An abandonment
permits a new attempt only when the attempt's log holds no dispatch intent, the event
that authorizes a model call. With no intent in the log, no model output ever existed, so
there was no answer quality to select on, and the evidence is the log's and not anyone's
account of why. That covers an attempt nobody ever claimed, one that died in the
prefetch, and one whose resume was refused before its first call.

It works only because of how recovery was already designed. A killed worker's attempt
stays open, and whoever resumes it replays from the log and reuses every model outcome
already recorded. Killing a process rerolls nothing except the one call in flight. A lost
worker is recovered by a new claim, so abandoning is rarely the necessary move, and after
the first intent it no longer buys a fresh attempt.

Two things are left, and both are stated in the ruling. The residual is that one
in-flight call: a kill during a dispatch leaves it unresolved, and its re-dispatch is a
new sample. Nobody can know that call's quality before it returns, so no path for
selecting on it was found, but it is a sample taken twice. The cost is that an attempt
which cannot be resumed after its first intent is lost, and its run reports an
infrastructure failure where a more permissive rule would have allowed a replacement.

The abandonment still records a reason from a closed list, so a report can tell an
operator's cancellation from an interruption. Eligibility does not consult it. The same
function is called in two places: at admission, on the previous attempt's log, and by
the evaluator over a run's exported attempts, where an attempt its predecessor did not
permit keeps its export, grade and cost and is never the counted one.

## 2026-10-05 — Three comparisons in one day held two different things equal or two equal things different, and none was found by reading the code

*M2, the contract step's fourth build group: the preregistration at format 2 (cells with a
corpus level, three statuses, one primary comparison) and the analysis that reads it.
Feeds: the M2 report's methodology section, on what a review and a forecast are each good
for; and the evaluation section, on why an interval at this sample size is stated with
its reason when it does not resolve.*

**[Evaluator and registration code only. No model system was measured, and every number
below is from the test suite's throwaway world or from hand-built cases. What would
revise it: nothing in the three faults themselves, which are fixed and held by tests; the
claim that the habit generalises rests on three instances from one day.]**

The group changed the committed registration from one format to another and rebuilt the
analysis around it. Three times that day a line of code compared two values, the
comparison was wrong, and the suite was green. Each was caught from outside the code that
held it.

The first was in the bootstrap. A ruling says an interval the bootstrap cannot resolve is
printed as unresolved with its reason, and one reason is that every resample gave the
same value. The check compared floats. The external read of that commit built ten
scenarios of ten repeats, one system passing one more repeat than the other in each, and
got an interval from 0.09999999999999987 to 0.10000000000000014 where every resample is
one tenth: a positive interval that excludes zero, made of rounding (reproduced to the
digit on commit `fc423c7`). A tolerance was declined, since no value for one could be
defended. The arithmetic now stays in whole numbers until one division, so one
mathematical value is one float (`f296345`). The fix then failed an older test of the
project's own, which had asserted a "narrow paired interval" for a loss that is the same
in every resample by construction. That test had been passing on the same noise.

The second was found by accident. An arm of the analysis gained a corpus level, and its
name gained the level with it. The name is an input to the seed each interval's bootstrap
is derived from, so every seed in the suite changed at once. One assertion failed: a
paired comparison inside one tier, nine scenarios, three of them differing between the
two systems, asserted to have an interval strictly above zero. A resample of nine drawn
with replacement holds none of the three in (6/9)^9 of draws, which is 2.6 percent, and
the lower end of a 95 percent percentile interval sits at the 2.5th percentile. So
whether the lower end is exactly zero or just above it is decided by the seed. The
assertion had been true of one seed and was written as if it were true of the method
(`tests/unit/test_evaluator_tables.py`, changed in `9c63335`). It now asserts not below
zero, with the arithmetic beside it. Nobody found this by reading the test. The seed
change was a side effect of an unrelated rename, and without it the assertion would still
be there.

The third is the one that matters for the measurement. A registration is frozen before
the world it is measured on exists, and bound to the world afterwards, and binding is
allowed to change three values and nothing else. The evaluator checks that by comparing
the bound file's procedure with the frozen one's. The first build compared the two as
decoded Python values. Python holds `True` equal to `1`. The external read of the switch
commit changed one role's setting in a frozen file from `stream: true` to `stream: 1`,
bound it, and the binding was accepted while the two procedure digests differed
(reproduced on `9c63335`). The check now compares the canonical bytes, section by section
(`d06a665`). What makes this one worth recording is that the project already had the
lesson. The type that holds a run's model settings refuses to let a boolean equal a
number, on a ruling made days earlier for exactly this reason, and has a test for it. The
rule lived inside that type. One layer up, where two encoded registrations were compared
as dictionaries, nothing carried it, and the session that wrote the comparison had
written forecasts for everything else in the commit.

Those forecasts are the other half of the story. Before any code ran the session wrote
down what the switch should produce: twenty-four cells in the committed draft, twenty
with no group and four in one; the rules-only baseline unchanged against the previous
commit; and the count of key paths in the evaluation artifact. The first was met. The
second was met in a form stronger than asked: 150 of 150 baseline exports at the base
level were identical in bytes to the previous commit's, and 30 of 30 runs at the padded
level had the same claims and grades (a capture script run once before and once after,
kept in the working notes as `baseline_capture.py`). The third was forecast as 614 paths
and came out at 613. The difference was a miscount in the forecast's own arithmetic, one
section written as fifteen paths that has fourteen, and every path the forecast listed
was reached. So the forecasts did their job on shape: they would have caught a table that
silently lost a section or a baseline that drifted. They caught nothing in the binding
check, because nobody forecast what an adversarial input does to an equality.

The same external read also refused a reading the session had made of a ruling. Incidents,
the scenarios on which some run met a source that contradicted itself, are to be read
from every evaluated export. The session had read them from the exports that enter the
tables, flagged that as its own reading, and built it. The reviewer took one export with
two conflicting reads, changed only its variant so that it left the tables for its
settings, and the incident disappeared from the report while the inventory still showed
the contradiction (reproduced on `9c63335`, fixed in `d06a665`). An export that is out of
the tables for a bookkeeping reason was still a run against the same world, and a
contradiction it met touches every cell that rests on that scenario.

What the day suggests, on three instances: a forecast written before the run checks that
the thing built has the shape intended, and it is cheap. It does not check a comparison,
because a comparison is wrong only on inputs chosen to make its two sides differ in the
respect it ignores. Those inputs came from a reviewer building them on purpose twice and
from a seed moving by accident once.

## 2026-10-04 — A model's misreading would have crashed the harness through the fact base, and both reviews of the fix found a further hole in it

*M2, the contract step's first build group: the types in `core` for facts a model states
from free text (the stated fact, the anchor table, the span binding, the view the rules
conclude from). Feeds: the M2 report's harness section, on what separates a model's
behaviour from a failure of the system that measures it; and the methodology section, on
reading a ruling against the code before building on it.*

**[Types and pure functions only. No model system ran through them and nothing here is a
measurement. The counts are from one throwaway world (seed 23, the earlier shape
probe's cached one) and the replays are of answers saved by two development probes.
What would revise it: the composer that consumes these types, which is not built, and
the first run of a real system over them.]**

The contract was fully ruled before this group started: a model states facts with a
carrier and a verbatim quote, the shared rules conclude from them, and two readings of
one passage that disagree are both left out. The group's design pass was meant to be
mechanical, a reading of the existing code to decide where each type goes. It turned up
two places where a ruling met the code and lost.

The first was in the fact base. It refuses, at construction, one source holding two
values for a single-valued predicate of one subject. That refusal is right for a sealed
world, where it means the generator contradicted itself. A stated fact takes its source
from its carrier, the tracker for a ticket comment and the corpus for a document
section. So a comment read as naming an owner other than the ticket's own owner field is
the tracker holding two values, and two runbook sections read as naming two owners is
the corpus holding two. The ruling covered two readings of one carrier and said nothing
about these. Built as ruled, the harness would have raised a `ValueError` in the middle
of a run because a model misread a sentence.

Whether that could happen on the worlds the generator makes was a one-minute count, and
the count is what shaped the fix (`probe_stated_collisions.py`, among the stream's
scratch scripts). The world plants no single-valued fact in a comment at all, and of 21
subject-and-predicate pairs carried by sections none holds two values. No sealed world
can trigger the refusal. Only a model can, or filler nobody vetted. That made the
question one of classification: a misreading is behaviour to export and grade, and a
crash would have filed it as a harness failure. The ruling that followed made the view a
total function of what was admitted. Within one source a structured field stands against
a statement that contradicts it, and statements from several carriers of one source that
disagree are all left out, each still admitted in the trace with the reason. Between
sources nothing changed; a runbook against the tracker is still the authority table's.

The second was a date. The ruling said a stated fact's observation date is its
carrier's. Every other fact a run derives is dated to the run's day, the evaluator
re-dates sealed prose facts the same way, and the view drops anything dated later. On
the same world all 29 prose carriers are dated after the earliest scenario's day (the
same script). A scenario's own facts never sit on a later carrier, so on those the two
datings agree. They part on a carrier planted for a later scenario, which the live
systems return to an earlier run all the same: dated by its carrier, the fact leaves the
harness's view while the oracle, which reads runtime truth, keeps it. The sentence was
amended to the run's day. Its intent, that the model never states a date, was untouched.

The build then took six commits (`6dfaf19` to `bc7a387`), and before review the built
code was shown real model output. The span binding replayed over the 182 rows saved by
the span probe's second pass placed 141, left 38 unplaced and 3 ambiguous, with no
difference from what the probe's own scratch function had recorded (`replay_binding.py`).
The anchor guard replayed over the shape probe's saved answers agreed with the rough
version it replaced where it mattered: 420 of 420 and 134 of 134 planted facts pass at
the two smaller corpus sizes, and all 29 inventions are refused at the largest
(`replay_anchor_guard.py`). At the largest size it passes 107 of 126 where the rough
check passed 120. Sixteen of the difference cannot be constructed, each because the model
gave a document id where a section id belongs, which the contract refuses before any
anchor is looked at and the rough check had ignored. Three are refused for an anchor, and
they are one case: an ownership statement in a comment on the ticket itself, "I own this
work on the Payments API component". The table asks an ownership quote to name the
ticket by title, and a comment on its own ticket never writes its title. This was kept as
a known cost. No conclusion moves, since the ticket's owner field is the same source's
record and stands whatever the comment says; the cost is a higher refusal count on text
the generator did not plant.

Then the fix was reviewed twice and each review found a hole in it. A reviewer run
inside the build session, read-only and asked to break the code, compared the moved
anchor table with the old one over a 643-probe battery and threw 30,000 random sets of
statements at the join; the bare fact base refused 19,418 of them and the join raised on
none (both are the reviewer's own scratch runs and are not in the repository). Totality
held. What it found was a case the three rules did not reach. A ticket returned with
different contents by two reads is withdrawn by the projection and derives nothing, its
owner field included. A statement quoted from that ticket's own comment then had no
field to contradict, entered the view as the tracker's value and outranked the runbook
by authority. The crash had been closed and a wrong conclusion left open beside it. A
fourth reason now leaves out any statement whose carrier the reads withdrew, checked
before the other three.

The external read of the six commits found the other. The join counted a statement once
by subject, predicate, value and carrier. Two admitted requirements of one clause that
agree on the count and the criteria and name different target spans therefore collapsed
to whichever the model emitted first, with nothing recorded. The span is the only input
the binding has, so a requirement's scope followed emission order. It was reproduced
both ways round and fixed by putting the span in the statement's identity (`4628239`):
both statements reach the binding and make one fact in the view. Nothing consumed the
join's output yet, so this was caught as a defect of the foundation and never as a wrong
report. What several spans of one clause should compose to, an overrun beside a placed
one or two placed on two artifacts, is not ruled and waits for the composer.

All three came from one place. Each rule was written for the sealed world's guarantees
and then handed inputs a model can produce and a generator cannot: two values from one
source, a statement from a record the run cannot vouch for, one requirement emitted
twice with different scopes. The join's tests now run every subset of a small pool of
statements, the check that would have caught the first of them before a reviewer did.

Figure: a three-row table of the holes, each with the input a model can produce, what
the code did with it before, and what it does now (crash; wrong authority; scope by
emission order).

## 2026-10-04 — Killing the process at every seam found the one design fault of the framework spike, and it was in the recovery driver's reading of "nothing next"

*M2, the harness phase's first step: the acceptance spike that decides whether the
agent loop stays on LangGraph. Its crash check kills a scripted run at each point where
the event log or the checkpoint store is written, recovers it in a fresh process and
reconciles the two stores. Feeds: the M2 report's harness section, on how recovery
decides what state a run is in; and a possible post on crash-testing an agent loop.*

**[One scripted scenario of three model turns, a single-task graph, the synchronous
PostgreSQL saver, `langgraph` 1.2.12 and `langgraph-checkpoint-postgres` 3.1.2. The
result holds for that configuration. What would revise it: a graph with parallel tasks,
the asynchronous saver, or a change of either pinned version, each of which reruns the
matrix.]**

The spike's persistence design keeps two stores. Each node appends what it did to an
event log before it returns, and the framework writes its checkpoint afterwards, on a
background thread. The log is therefore ahead of the checkpoint, and the rule is that
the log wins: a node looks its result up in the log before it executes anything, and
the checkpoint holds only a cursor. Whether that survives a crash was the question. The
check was built to be exhaustive about where a crash can fall. A hook sits before and
after every event append and before and after both of the saver's write methods, plus
the points of the approval handoff, and a scripted run crosses 82 of them (19 appends
and 21 saver writes, each before and after, and two further handoff points;
`probes/langgraph-spike/run_matrix.py`, execution `20261004T155751Z-9f36a4` at commit
`f2d1f28`). For each crossing a child process is killed there with a hard exit, no
exception raised, and a second process is started with no knowledge of what happened.

The second process needs a driver: something that reads both stores, decides what
state the run is in, and takes the next step. Its first version had a branch that
looked obviously right. If a checkpoint exists and the framework's state snapshot lists
nothing as next, the run is complete, and the driver checks that the log holds the
terminal event the checkpoint names. On the first full run of the matrix, a development
run on uncommitted code, that branch refused eight crossings with the message that the
checkpoint was complete and the log held no terminal event. Every one of the eight was
a kill just before a checkpoint's write. The refusal was the driver's own invariant
doing its job: it would not call a run complete that the log said was unfinished.

The first diagnosis was wrong. The saver writes a task's pending writes as several
rows, and a kill in the middle of them seemed to explain a run the framework thought
was finished: some rows saved, the one that names the next node lost. Reading the
store at the boundary took a few minutes and showed the rows whole, the result and the
next-node trigger both present, in every repetition. The second description was wrong
too. It said that after a kill between the input's checkpoint and its pending writes
the framework has nothing to continue and its own resume returns as if there were
nothing to do, and a branch was written to restart the run in that case. An
independent reviewer produced exactly that state, one input checkpoint and no writes,
and the framework listed its start task as next and carried on. The branch had never
run in any of the 82 rows. It was removed, and the claim was retracted in the record.

What is true is simpler and is a property of how the framework reports state. A
snapshot lists as next only the tasks that have no saved writes. A step whose task
finished and saved its writes, but whose checkpoint was never written, has no such
task, so it shows nothing next, exactly as a completed run does. The snapshot's values
make it worse: they show the saved writes as already applied. After a kill just before
the last checkpoint, the snapshot holds the run's terminal result while no durable
checkpoint does. A driver that trusts "nothing next" stops there and reports a
complete run whose final checkpoint does not exist. The fix is an order of questions.
The driver first asks whether the snapshot still has tasks; if it does, the step's
writes are saved and unapplied, and continuing the graph applies them and writes the
checkpoint. Only with no tasks left does it ask about completeness, and completeness
is the log's terminal event agreeing with the digest the checkpoint holds. With that
order all 82 crossings recover and reconcile, and 9 of them take the new branch (the
same execution). The variant that kills a second time at the same crossing in the
recovering process ended recovered in 43 rows and was not reached again in 39, because
the recovery reused what the log held; none failed. That split moved by one or two
between executions, which is expected: the order of a task's pending writes against
the step's checkpoint is not fixed, and it is the reason a crossing is named by what
was being written and never by its position in the run.

The reviews around the spike found something different, and the contrast is worth
keeping. Each group of scripts was read by an independent reviewer before its commit
and by a second one after it, and nearly all of what they found was a check that could
not fail for the thing its label said. A duration was compared with the function that
computed it. An approval count was asserted to be one where the log's primary key made
any other value impossible. A boundary invariant merged a checkpoint's state and its
pending writes into one dictionary before comparing digests, so a right digest stored
later covered a wrong one stored earlier; one independent reader called that helper
sound before the next caught it. None of these reopened the design. The design fault,
the driver's reading of an empty list, was found by none of the readers. The matrix
found it on its first complete run, because it puts a real process in each state and
asks it to continue.

Figure: the 82 crossings as a grid, seam kind (event append, checkpoint write,
pending-write set, approval handoff; before and after) against the recovery branch the
second process took (no checkpoint, continued from a checkpoint, writes saved and
checkpoint not, resumed with the logged approval, delivered the approval, already
complete), with the eight cells the first driver refused marked.

## 2026-10-04 — A tool call cut at the output limit reaches the harness looking like a call, and the client repairs what was cut

*M2, the same acceptance spike, its provider half and its parser fixtures: what the
pinned chat client hands the harness when a model's tool call is truncated, malformed
or empty. Feeds: the M2 report's harness section, on when a tool call may be
dispatched; and a possible post on trusting a provider client's tool calls.*

**[Two model families through one pinned client, `langchain-aws` 1.8.0 on
`langchain-core` 1.6.6, against the `eu.` Haiku 4.5 and Nova Pro profiles; the fixture
half is crafted responses through the client's parser with no network. The live run
through the whole graph never had a call cut, so the rule below was not exercised on
the live path. What would revise it: a client version change, which reruns both.]**

The harness is going to run under a cap, and a run at its cap ends mid-response. So
the spike asked what a tool call looks like when the output limit cuts it. A forced
tool call was sent with an output limit of 8 tokens (FINDINGS, "langgraph-spike, the
provider half", execution `20261004T120535Z-d40f6d` at commit `9d76213`). Haiku, not
streamed, answered with HTTP 200, the stop reason `max_tokens`, and a tool call whose
input was an empty object. Streamed, it sent one argument fragment, the empty string,
and then `max_tokens`; the client reported a tool call with arguments `{}` and listed
no invalid call. In both cases the message the harness receives holds a tool call. For
a tool that takes an id, the tool's own validation would refuse the empty arguments.
For a tool that takes no arguments at all, of which the surface has several, the cut
call is a complete and valid call. Nova behaves differently: the same request, not
streamed, came back as HTTP 424 with a `ModelErrorException`, the kind of error a retry
policy treats as transient, although here it is a deterministic result of the limit.

The parser fixtures were written to see how far the client goes
(`probes/langgraph-spike/run_parser_fixtures.py` at commit `f2d1f28`). They put a stub
where the client's network layer is and feed crafted responses through the client's
own parser, because a bad call injected already parsed would skip whatever the client
discards or repairs. A streamed argument string cut in the middle of a value,
`{"id": "emp_0`, came out as a tool call with arguments `{"id": "emp_0"}`, under a
`max_tokens` stop and under a `tool_use` stop alike. The client completes the JSON. A
streamed tool with no arguments came out as `{}` whether the stream carried no
argument fragment, an empty one, or the two characters `{}`, which is byte for byte
what the cut call above looks like. Arguments that were plain text, or a JSON array
where an object belongs, were the only shapes the client flagged: they arrive as an
invalid tool call, beside no valid one.

Neither provider guards the other side either. Asked for a call that breaks the
tool's schema, both families produced one in 3 of 3 tries, `LIA-42` and `emp_42`
arriving as an employee id against the schema's pattern (the same provider-half
execution). The schema sent with the tools is a description the model reads, and what
comes back is not checked against it.

Three rules went into the harness from this. A tool call is dispatched only when the
response stopped on `tool_use`; under any other stop reason the calls in the message
are recorded and not executed, whatever their arguments look like. The tool's own
validation is the only gate on arguments, since neither the provider nor the client
is one. And the client's list of tool calls is not evidence of what the model sent:
where that matters, the captured response is. The spike's graph applies the first
rule, and beside the export it lists a call that was present and never dispatched as
its own case, since the current export format can only record such a response as a
text.

## 2026-10-04 — A one-day probe before the harness settled who writes the claims, and showed the benchmark is too small to separate the systems it compares

*M2, between the evaluator phase and the harness phase: an outside review of the
project's direction asked whether any real model could reach the all-or-nothing
headline, and the question was answered by running a model against the evaluator on a
throwaway world before any harness code existed. Three rulings came out of it; the
question of what M2 compares is open. Feeds: the M2 report's evaluation-design section,
on what the model is allowed to assert and on what the benchmark can and cannot
separate; and the milestone post.*

**[PRELIMINARY — one throwaway world, one model, ten to thirty calls per cell, prose
gated for extractability and written by the model family that read it, no retrieval or
tool loop. Every number below decided a direction and none is a result. What would
revise it: the same measurements on the registered systems, through the harness, on the
development scenarios and then the held-out set.]** All model numbers are from one
world generated for the purpose (seed 23, the golden plan, real prose from the
generator's own fresh stage, never sealed, never projected into a vendor) with Haiku
4.5 at temperature 0. The probe's scripts and raw outputs are kept outside the
repository; each number names the script that produced it.

The evaluator was finished before any model had been run against it. That was the
plan's order, evaluation first, and it left a risk nobody had tested. The headline check
grades a scenario correct only when every required row is reported, every payload is
right, nothing unexpected is stated and the plan agrees with the oracle. A truthful
report is about thirty claims. A review of the project's direction, written from
outside the build, pointed out that a model might floor on this for reasons that have
nothing to do with investigation: one wrong reason in thirty rows fails the scenario,
and nothing in the plan showed a real model's output until the first live run, eight
steps later. The review also named the design question underneath, which the plan had
left to the step that builds the agent: does the model write every claim, or does it
supply what it read and let the shared rules conclude.

The session did not argue the question. It read how the evaluator already treats prose
and found the answer half built. The evaluator's own view of a run admits a sealed
prose fact when the run read the comment or the section that carries it, then runs the
rules over the structured reads plus those facts. A system could be built the same way
with the model's stated facts in the sealed facts' place. So the first thing written
was that pipeline with no model in it: the frozen prefetch, every document read by its
id, the prose facts supplied as an argument, the rules composing the report, the real
evaluator grading it. Its first run was refused by the rules themselves. A scope
pairing whose clause has no readable requirement in the view is an error, not an empty
case, so the pairings have to be limited to clauses the run read. With that, three rows
came out that needed no model (`probe_harness`, reproduced on the throwaway seed 23
world by `probe_reference_rows`): with no prose facts 10 of 30 scenarios grade correct
whole, the structured tier and nothing else; with only what the clauses require, 16 of
30; with every sealed prose fact of the parts read, 30 of 30. The last row is the one
that mattered. The shape fits the evaluator as built, and the only addition to the
rules-only report was the constraint claims. The middle row was a surprise: reading
what a clause requires is worth six scenarios by itself, and the clauses are template
text.

Then the model. Shown everything the run read, about 9,700 input tokens for the whole
world, and asked to state three kinds of prose fact with the exact words that assert
each, it produced 26 of 30 scenarios correct whole (`probe_model`, first prompt, thirty
calls). It invented nothing and every quote was verbatim, 434 of 434. The misses were
not noise. The same two facts were missed in all thirty calls, a skill sentence sitting
beside a contact sentence in a client note, and each of the four failed scenarios was
one wrong assessment out of thirty-odd claims (that the four trace to those two facts is
an inference from the second pass, which fixed the facts and the scenarios together). The prompt had described skills with a
comment as its example and sections only as naming a contact. Three sentences were
added, saying a text can assert several facts and a section can state a skill, and the
second pass was 30 of 30 with 420 of 420 planted facts matched (`probe_model`, second
prompt, thirty calls). That wording was written after the misses were seen, so it is
tuned on this world and proves nothing about a world it has not seen. The first pass
also showed something one repeat would never show: on identical prose, at temperature
0, four of thirty calls dropped all four runbook-ownership facts. None of the four was
a scenario that needed them.

The other shape was run as the contrast: the model writes the whole report itself, in
the codec's exact format, given one object of each claim type and three worked
examples. It scored 0 of 6 (`probe_claims_arm`, two scenarios per tier). Five of the
six answers decoded and most were near misses: one to three wrong rows out of thirty or
more, a conflict claim missing, one wrong impact that made everything under it
unexpected. It failed even the structured scenarios, which the rules get right with no
model at all. The contrast is real and it is also partly circular, and the session said
so before the number could harden into a finding. The facts arm concludes with the same
rules the oracle runs, so given the right facts it matches the oracle by construction.
The authoring arm was asked to reproduce those rules' verdicts and reasons and was
never told the rules. What was measured is narrower than "constraining the model made
it correct": a model executing deterministic logic over thirty candidates makes a few
errors, and an all-or-nothing check turns each one into a failed scenario. A fair
version states the rules in the prompt, and until that runs the 0 of 6 is a direction.

The shape question was settled by this. The more important thing the probe showed was
not asked for. The whole world's reads are about ten thousand tokens. One call to the
development model, with everything in context, reaches the ceiling. On a world this size
rules-only reads ten of thirty and a call shown everything reads thirty, so the agent
can at best tie it, and a table in which every model-based system scores full marks
measures nothing. (The registered single-shot baseline makes one fixed corpus query with
a limit and is not that call; where it lands is unmeasured.) The external read named
this as the larger problem, and it is: the planned side comparisons assumed a world hard
enough to separate what they compare. A model comparison has nothing to separate when
the development model is at the ceiling, and two retrieval methods will both find
everything in a corpus that fits one context several times over. The prose
makes it worse. The generator's gate accepted a text only when a second model could
extract exactly the planted fact, with the names verbatim and no hedge, so the measured
difficulty of the prose is fourteen near-template sentences. That was recorded at the
world milestone as a limit on realism. It is a limit on measurement too.

The proposal was to find out cheaply whether size alone creates difficulty: pad the
input and rerun. The first suggestion, documents from other throwaway worlds, was
rejected on a check of how worlds are built. Every world draws from the same ids and
the same names, so another world's note that someone has experience with a skill would
be read as a fact about this world's person of that name and would change answers. The
filler was written instead as handbook prose under an instruction to name nothing, and
every section was scanned against this world's names, with 43 of 495 sections dropped.
At about 40,000 input tokens the model still matched 134 of 140 planted facts and all
ten prose-dependent scenarios graded correct whole. At about 108,000 it matched 93 of
140 and seven of ten scenarios passed (`probe_padded`, ten calls per size, second
prompt). Three things went wrong at the large size. One call returned two facts where
seventeen were expected. In two calls the model named the document where the section
was asked for, and 33 otherwise correct facts were refused on the id's form. And 29
facts were invented. Nothing was ever stated from a filler section.

Two readings of that last table are worth keeping. The scenario grade hid most of the
damage: seven scenarios passed while only four of the ten calls stated all fourteen
facts, because each scenario leans on one or two of them. The per-fact count is the
sensitive instrument for a size experiment and the headline check is not, which is why
stated-against-planted moved from wanted to required. And the 29 inventions all passed
the verbatim-quote check. Every one was the same move (nineteen skills, ten contacts,
counted from the saved answers): a requirement clause such as "the release needs an
engineer with iOS experience" read as a named employee having that skill or being that
contact. The quote was in the text. The text did not assert the fact. The external
read suggested requiring the quote itself to name the person and the skill the fact is
about, and the session tried it on the saved runs before adopting it
(`probe_anchor_check`, a rough version that matches a skill by its id): it refused all
29 inventions and passed 420 of 420 and 134 of 134 planted facts at the two smaller
sizes and 120 of 126 at the largest, the six refusals being quotes the model had
truncated. The check is partly a property of this generator, whose gate put the names
into every planted sentence. On text that says "she" it would cost recall, and that
belongs beside any claim made for it.

Three things were ruled. The model states quoted facts and the rules conclude, for the
agent and for the single-shot baseline, and the model writes no verdict. More than one
repeat, since the dropped classes are per-call variance and a call costs little at this
size. And the multi-agent comparison stays in the plan, against the external read's
proposal to drop it. What M2 compares is open: whether to add a size dial with
answer-neutral documents, whether a full-context call becomes a system of its own,
whether the authoring contrast is registered with a fair prompt, and what the existing
side comparisons are run on. The honest state is that the probe found where a tool loop
could earn its place, a corpus near a hundred thousand tokens for this model, and did
not test whether it does.

Figure: planted facts matched and facts invented against input size, at about 9,700,
40,000 and 108,000 tokens (420 of 420 over thirty calls, then 134 of 140 and 93 of 140
over ten; inventions 0, 0 and 29), with scenarios correct whole as a second series to
show how little of the damage the headline check sees.

## 2026-10-03 — A preregistration that binds only what the code reads, and what the gates and the reviews caught on the way to its first dispatch

*M2 step 6, the investigator milestone's sixth build step: the preregistration as a
committed file, the harness and the evaluator reading it, and the evaluation job proved
once against the golden world. Seven rulings by interview, then eight commit groups, each
opened by a design pass and closed by an external review with no chat context; this entry
covers the last four groups and the dispatch (commits `6bb06c0` to `761a58d`, per
`git log`). Feeds: the M2 milestone report's method section, on what was fixed before any
system was measured and how a run is tied to it; the final report's section on honest
measurement, on eligibility, labels and the held-out scenarios; and its process section,
on what a gate that runs the real system finds that a reading of the code does not.*

The preregistration could have been a document. It was built as one JSON file that the
code decodes, because a document can say anything and nothing checks it. The rule that
shaped the file is that names live in it and behaviour lives in code. The file names a
check, a measure, a prefetch rule, an outage protocol, a reporting policy; the code holds
what each name means; and each consumer compares what the file names with what its own
code computes and refuses to run on a difference. Neither side is substituted for the
other, since a run that quietly used today's value would cite a registration it did not
follow. The consequence is that the file binds only what some code reads. A sentence of
intent that no consumer checks has no place in it, and the prose that explains the file
sits beside it and restates no value. The file is a draft or frozen. A draft may hold a
value nobody has chosen yet, written as pending with what will resolve it, and a pending
value blocks only the execution that needs it, so the rules-only baseline has been
running under the draft while the agent's model and prompts are still pending. Frozen
refuses anything pending and any number still marked unmeasured, which today includes
every cap and every dollar figure.

The first thing the session built on top of it was the check that a run's opening reads
are the registered plan. The planner is shared between the harness and the evaluator, so
the evaluator reconstructs only the execution: which planned calls a run was obliged to
make given what its earlier ones returned. The check was written, and the first run of
its gate, the real baseline on every scenario, failed on all thirty, on the same two
calls. A recorded operation holds its arguments with keys
in sorted order; the planner spells them in the order it builds them; and the encoding
used for the comparison keeps insertion order. Two identical requests never matched. No
reading of either module shows this, because each is right alone. The comparison now
sorts keys at every depth, and the real baseline conforms on thirty scenarios under each
of the five registered conditions, read back from its exported bytes (the gate in
`tests/unit/test_evaluator_prefetch_conformance.py`). The external review then found what
the gate could not, a misclassification: when a long leave's second chunk is replaced by
a second read of the first, the check reported one wrongly parameterized call, where its
own docstring promised a missing call and an extra one. The fallback had accepted any
spare operation of the right tool. It was reproduced by a new test before the fix
(commit `96dfea1`).

The evaluation artifact came next, and with it the question of which runs enter a table.
A run is eligible when the registration at the commit it cites has the evaluator's own
bytes and when what the run recorded of its own execution is what the registration says.
The second half is there because equal bytes show matching declarations and nothing
about what ran. The review found a hole in exactly that half. Prompts were compared as
one pooled set over all of a system's roles, so with two prompts registered, one role
holding the first and another holding the second passed, though neither had run under
the registered set. Each role's whole prompt set is compared now (commit `aa3bc3a`); the
test that had covered it used a single role. One ruled choice was also reversed during
the build and said so at the time: the design pass had an export of an unregistered arm
refuse the whole evaluation, and the ruling's own text lists the outage schedule among
the settings a run is compared on, so such a run is ineligible like any other settings
mismatch, keeps its grade and its cost in the inventory, and refuses nothing.

How the artifact is written was a fork of its own. The export and the registration each
have a codec written field by field, because a second party decodes them strictly and a
hand-written pair keeps encoder and decoder honest with each other. Nothing reads an
artifact back in this milestone, and some thirty-five types written out by hand with
nothing to mirror would have been transcription. The artifact is written by one walk
over its dataclasses, with explicit cases only where the written form differs from the
type, and the format is held by a version and a pinned list of every key path the walk
produces, 442 of them (`tests/unit/artifact_shape.txt`). Three situations are recorded
as the point where an explicit codec with a strict decoder replaces it: something
decodes an artifact, artifacts from two versions of the code are read side by side, or
bytes must be equal across platforms. The pin itself had to be earned. Its first
version, made from the baseline's own runs, looked complete at 346 paths and was thin in
a way the path count hid: counting paths per row type showed none under conflicts,
constraints or unknowns, and five kinds of finding with no fields, since the baseline
reports none of those. That was found by the build's own count, not by a review, and the
fixture was widened with truthful reports of every scenario, reports stripped of their
assessments, an undeclared tool, a short enumeration and a priced model call until each
type was present.

The last group built the job that runs all this, and its workflow had a fault that would
only have shown at the first real evaluation. The draft wrote its logs into the
checkout, and the evaluate command refuses a checkout that differs from its commit, so
the job would have refused itself. It was caught while writing the file and the logs go
to the runner's temporary directory. Whether anything else in the job's setup trips the
same refusal is not known yet. The review of this group found the most consequential
of the three faults the reviews caught. The command that proves a world printed the development scenarios by
running the seeded draw every time, while the registered list is deliberately kept when
a seed changes, so that tuning already done is not disowned. With the seed moved by one,
the command would have printed scenarios the evaluator holds out as if they were free to
tune on, which is the one thing the held-out set exists to prevent. It now returns the
registered list once one exists and draws only while the list is pending (commit
`761a58d`).

The dispatch itself was quiet. One run, the proving command, on commit `3835e15` (run
37145648012; everything in this paragraph is from
`probes/captures/evaluator-identity/run-37145648012-attempt-1.log` and the approval
record beside it). It waited for its reviewer and has one approval. Under the
evaluator's role four reads were allowed: the world spec, the truth manifest, the
scenario specs and a listing of the stored runs. Three operations were refused, each on
the permission error: a get of the world's manifest, a model call, and a put under the
sealed worlds. That put carries the create-only header on purpose. The bucket refuses a
put without it for every principal, administrators included, so a plain put refused
would have said nothing about the role, which is what the validator's older probe does
and why it was not copied. The golden world was proven from its three objects, six
development scenarios were selected by tier alone, and the retrieval targets of the
golden world were derived for the first time: 31 under the normal condition, 14 with the
tracker down, 25 with the calendar down, and no answer under the two outages that leave
the leave or the policy unreadable. Nothing was written. The log is public, so its 410
lines were searched for every tier name, every scenario class name, a traceback and any
leave, employee or ticket id, and none occurs.

What the step leaves unproven is stated in the same places it was built. No export of a
model system exists, so the evaluate command has run only against a local store and a
temporary git repository, and publication of an artifact is proven by the first live
run and not by a probe. The six development scenarios were drawn by tier, and whether
two of them share a scenario class on the golden world cannot be printed, class being
sealed. The suite stands at 4,309 passing tests (the last full run of the session, after
commit `761a58d`), which says the pieces agree with each other and nothing about a
measurement that has not been made.

Figure: a small table of the six catches by who made them (the gate on the real
harness, the external review three times, the build's own count and reread twice), each
with what a wrong version would have reported, would carry the process section without
prose.

## 2026-10-03 — The baseline that reads no prose is grounded whole and wrong exactly where the answer lives in prose, and the forecast was met by the real thing

*M2 step 5, the investigator milestone's fifth build step: the rules-only baseline, the
first system the benchmark measures, from the frozen prefetch through the shared rules to
the export the evaluator grades. Six rulings by interview, each measured before it was
argued and read by an external reviewer with no chat context (session 48), then six
commit groups built and reviewed in batches (session 49, 2026-10-03). Feeds: the M2
milestone report's baseline section, on what a system that reads only structured records
is worth and on why its numbers are the floor the agent is measured against; the final
report's section on honest measurement, on grounded not meaning correct and on
forecasting a system before building it; and its process section, on what the batch
reviews caught, including one that turned into a ruling.*

The plan said "the rules-only baseline" as if it were a plumbing exercise: run the shared
rules over a fixed set of reads, export, grade. The interview found that nearly every
word in that sentence hid a decision, and measured each one before ruling, on twenty
seeds of the golden plan assembled in memory (the probe `probes/baseline-basis` and its
capture, FINDINGS `baseline-basis`). The first was whom the baseline assesses. The design
at the milestone's entry had said the leaver's team and the holders of each needed
skill, which reads sensibly until one asks where the needed skill is stated: only in a
policy clause, which a system that reads no prose never sees. The two selections a
prefetch can actually compute, the leaver's team and the team with the component's
members, change the coverage outcome on 255 and 56 of 640 impacts and leave 781 and 307
of 1,440 must-assess verdicts outside; the only selection that keeps every outcome needs
the clause. The ruling made the candidate universe the whole employee enumeration,
complete when the coverage rule marks it covered, with a scale note that a larger
organization would need a retrieval stage that bears completeness. The second was the
window: the run carries no window, so the prefetch derives one from the leave it read,
and the leave's exact span gives the oracle's answer in 600 of 600 scenarios, a day of
margin adding nothing. The third was how much to report: assessing everyone is 15,120
assessments on twenty seeds where stopping at enough viable candidates is 2,793, and the
cheaper policy leaves out 807 of the 1,240 rows a report must hold and takes a coverage
gap on every one of the 140 impacts where the oracle calls for everyone. Everyone is
assessed.

The result that names the entry came from the first measurement. A full read with the
document reads left out, the rules asked with no constraint and the answer compared with
the oracle: the 200 structured-tier scenarios are the oracle's answer whole, and none of
the 400 others is, the split being exactly "the sealed key's required sources include
the corpus". On the 540 impacts it finds, 140 outcomes are an assign where the truth is
uncovered or unknown; of 1,240 must-assess verdicts, 360 are viable where the truth is
non-viable or unknown; none of 80 conflicts and none of 392 unknowns is stated. Every
error is a confident positive. Then the same answer was written as a report and graded by
the real evaluator on the reference seed: 810 claims, every one reproduced by the
grounding replay, no finding of any kind, and 24 plan findings against the oracle. The
replay accepts the baseline's empty constraint list as a premise, because a system that
read no clause holds none; it cannot say that no clause governs. So grounded is not
correct, the two are separate measurements, and the distance between them on the two
prose tiers is a number the report can put beside the agent's: what the prose is worth,
measured on a system that never reads it. The same reasoning settled the degraded
states. The vocabulary cannot even state "the leave record could not be read" (an
unknown is about an employee, a work item, an event or a clause, and the registry's
subjects are those four), so both unreadable states are represented by abstention, a
completed run with no claims, nothing added to the export. The reviewer's version of the
abstention ruling was adopted almost whole; its one wrong turn, that a partial report in
a degraded state always breaks the coherence rule, was corrected in the record (a
structurally non-viable verdict stays true under any policy), and the partial report was
parked for the report view rather than refused on a false ground.

The build was a forecast made good. Group 0 committed the interview's measurements as a
probe before any baseline code existed, and the reviewer's first catch was that its
"equal to the oracle's answer whole" was a flag built by hand that compared five parts
and left out the required count, the requirements, the non-probed assessments and what
each assessment left open; the probe now decides equality by the full-read test's own
comparison, and the capture came back identical on every line, the structured tier's
keys holding no constraint and no resolved requirement. The probe also gained the line
the rulings had been missing, what the evaluator's own rows grade correct whole: the
structured tier 10 of 10 under each condition, the fragmented tier 0, 2 and 3 of 10, the
adversarial 0, 10 and 0. Five groups later the real baseline, through its real export
and the real evaluator, gave the forecast's numbers exactly: 810, 270 and 540 claims
under the normal condition, the tracker outage and the calendar outage, every one
reproduced with no finding and every citation resolving, retrieved and used; 24, 6 and
18 plan findings; the structured tier correct whole 10 of 10
(`tests/unit/test_agent_rules_only_graded.py`, commit `db07c03`; FINDINGS
`baseline-graded`). The honest part of that sentence is the method, not the match: the
simulation was built from the evaluator's own view and the oracle's own composition, so
the forecast and the system share their rules by design, and agreement shows the
plumbing holds, not that the rules are right. Two gaps between simulation and system were
closed on the way rather than assumed: the simulation's view held 1,800 skill facts
carried by ticket comments that the baseline never sees, and removing them changed no
conclusion in 600 scenarios; and the simulation read the scenario's wider window where
the baseline reads the leave's span, and the answers were equal in 600 of 600.

What made the build possible was moving more into the shared core than the plan said. A
harness may not import the benchmark, and three things the baseline needed lived there
or in the evaluator: the pass that composes the rules per impact, the view a trace's
reads give those rules, and the record a claim's citation may name. Writing any of them
again in the harness would have been a second reading of the rules, free to drift from
the one the grader runs. The structured projection of a trace's reads was the decision
with teeth: the evaluator's view became that projection plus a sealed overlay (the prose
a returned comment or section admits, the comparison of every returned record with the
sealed one), and the baseline's view became the projection alone, so what the graded
concludes from is the structured part of what the grader replays over, by construction.
That equality was shown as two independent implementations before one replaced the
other: the gate's seventeen tests were run green against the evaluator's old view and
then against the one rebuilt on the projection (commits `8295d26`, `f2c7434`).

One review finding turned into a ruling. The baseline detects three things the plan's
own reads cannot: the HR system answering the leave id asked with another leave, an
employee enumeration without the leaver, and a returned record no fact can be made from.
The interview had ruled each a defect that fails the run "at that operation", on the
ground that degrading would fold a defect into a legitimate unknown. The export's own
rule, written two steps earlier, held that a defect failure names an operation that read
a malformed record, and the operations in question read records fine. The reviewer
reproduced the refusal ("a defect failure names an operation that read a malformed
record, got 'op-2'"), and the two shapes were brought: make the contradiction an outcome
in the trace, which would rewrite what the source answered and add a seventh outcome
kind to a format two rulings had frozen; or broaden the export's invariant so a defect
names the operation the fault was found at, a malformed record or returned records the
harness could not accept. The second was ruled, one existing expectation amended by the
ruling and said so, and the reviewer's second read narrowed it once more: the broadened
rule had admitted an absent answer, and absence is evidence, for the leave an
abstention, never a fault (commits `7cdba9e`, `dcf0cb0`). The other catches were of the
kind a second reader exists for: the prefetch digest blind to the validation protocol
and the result codec; the correct-whole reading skipping an optional row's payload,
optional in recall only; the prefetch going on after a malformed record. Each was
reproduced on the committed code before it was fixed, and none changed a number.

[PRELIMINARY — one throwaway world of thirty scenarios with stand-in prose; no sealed
world run, no model called; the single-shot baseline and the agent do not exist, so the
"what prose is worth" number has no second system beside it yet. The sealed golden
world's numbers by condition arrive with the evaluation job's first dispatch.]

Figure: the forecast against the real thing, three conditions by claims reproduced and
plan findings, with the structured tier's 10 of 10 beside the other tiers' 0, 2 and 3;
or the simpler one, per tier, "grounded" and "correct" as two bars that agree on one
tier and part on two.

## 2026-10-02 — A run that read nothing would have had every negative confirmed, and one of the step's own numbers had no script behind it

*M2 step 4, the investigator milestone's fourth build step: the grounding replay and
source discipline, from the coverage a run's reads give the shared rules through the
observed-run view, the replay with its citations and the trace metrics to the tables and
their intervals. Six rulings by interview, each read by an external reviewer with no
chat context, then six commit groups, each reviewed in one batch after its push (session
47, 2026-10-02). Feeds: the M2 milestone report's evaluation-design section, on what
"grounded" is allowed to mean and on which interval goes with which number; the final
report's section on honest measurement, on a negative no system can establish and on a
number that was corrected twice; and its process section, on what the batch reviews
caught and on the one finding that was declined.*

Step 4 asks one thing of a run: do the rules, fed only what its reads returned, conclude
what its report claims. The plan treated that as a replay of code that already existed.
The second ruling's interview found that the replay as it stood would have been wrong in
the direction that flatters a system. Closure, the rule that decides whether a fact is
known true, known false or unknown, inferred a negative when every source of the fact's
evidence domain was reachable and no fact was there. For the truth a world plants that
is sound, since a reachable source holds everything. A view built from a run's reads
holds only what the run asked for, and reachability says nothing about that: a run that
read nothing would have had every "lacks the skill" and every "not on leave" confirmed
by its own silence. How much of the answer rests on a negative was counted before
anything was ruled, on the sealed must-assess verdicts of twenty seeds of the golden
plan. Of 1,440, 420 are viable, which needs "not on leave" known false and "not busy"
for a meeting; 420 are non-viable with skill among the reasons, 244 on availability, 236
on component alone, 40 on a hard rule, and 80 are unknown (`probes/grounding-basis` and
its capture; FINDINGS, `grounding-basis`). Nearly every assessment touches one. The
ruling was that an unread record is not false. The unit a view is asked about became a
slice of a source, and whether a slice was observed is read off the trace by where the
fact lives: a component's record settles membership and the employee's record cannot, a
leave read by its id settles nothing about "no leave overlaps these days" and a window
containing them does, one ticket gives positive evidence of a skill and only the
enumeration of tickets closes the tracker's part of a negative. The change went into the
shared rules, which the oracle also runs, so the risk was to the answer key itself. The
truth's coverage was defined as covered where the source is reachable, the old behaviour
exactly, and it was held to that: no existing expectation of the suite was edited, both
committed measurements regenerated identical to their captures after each of the three
changes, and the golden world reloaded live with its thirty keys reproduced (FINDINGS,
`coverage-in-core`).

The first ruling had found the other half of the problem. The rules derive facts from
structured records and nothing from prose, and on the same twenty seeds all 620 authored
facts sit on a ticket comment or a document clause: what a clause requires, whom a
section names, a skill a comment shows (`grounding-basis`). A view built from returned
records alone would leave every claim resting on prose ungrounded for every system. So a
sealed fact enters a run's view when a completed read returned its carrier and the
returned text equals the sealed text, which the evaluator already holds. The limit was
written into the ruling and not discovered later: once a carrier came back, grounding
cannot tell reading from guessing. Whether a query found the carrier is the retrieval
measure's question, whether the claim follows from what came back is grounding's, and
whether it is right is the grading's. The corpus then produced a negative nobody can
establish. It has a search and no enumeration, and a skill can be stated in any section
of any document, so "no document says this person knows Kafka" is out of reach of every
tool. Four ways of handling it were weighed. A strict reading alone makes the 420 skill
verdicts, 29 % of the total, ungroundable for every system, a constant that compares
nothing. A lenient reading alone hides a limit of the tool surface inside a definition.
Storing both judgments keeps a second copy that can disagree with the first. What was
ruled is one stored judgment, the operational one, with the source it stood without
recorded beside it, and the strict reading derived wherever a table is cut; the word
grounded is never used alone for a result with a source left unclosed.

One number in these rulings was wrong twice. The fifth ruling needed to know which
pieces of prose move the answer, because the sealed "answer-changing" tags exist only
for model-written text and the 340 class-written requirement clauses carry none. The
external reviewer's read said all 580 carriers move a conclusion when removed. Re-run
over the runtime view, 578 did: all 520 clauses and 58 of the 60 comments. The two
comments that move nothing, on seeds 10 and 19, each show a skill that a later
scenario's clause states again for the same person, the mechanism step 3's oracle
measurement had already found, and the reviewer's 580 does hold under the dated view the
tags were derived in. That settled the unit: the target is the statement, and its
carriers are alternatives. The ruling then recorded "578 statements on one carrier, 2 on
two". Nobody had counted statements. The line was a subtraction from the carrier count,
written down by the author in the very ruling that corrected the reviewer's number for
not reproducing. It surfaced at the first build group, whose job was to turn the
interview's seven scratch scripts into one committed probe with a capture: the probe
counts 618 statements, 616 on one carrier and 2 on two (`grounding-basis`). The step's
rulings record carries the correction with its date, and the project's working rules
gained a line: a number in a ruling has a script behind it, or says it was derived by
hand.

The build ran in six groups, each read after its push by the external reviewer, who sees
the repository and no chat, and every finding was reproduced on the committed code
before it was triaged. The reviewer found something real in every group. In the probe:
the three properties that make a requirement's scope admissible through its clause all
read the sealed pairing and never the clause, so a clause naming nothing would have
passed. The property added searches every title of the world in the clause's text, and
it needed a rule to work, since titles nest by design and plain containment was
ambiguous in 26 of 340 clauses, while the longest title found decides all 340
(`grounding-basis`). In the shared rules: an operation was credited with what its tool
observes on the strength of the tool's name and arguments, so an `employee` call
recorded against the tracker and answered "no such record" grounded a negative about the
HR system (`coverage-in-core`). In the observed view: a read by id answered with another
record left no finding (FINDINGS, `observed-view`). In the replay: a citation counted as
used through a premise that was itself contradicted, and the leave record, from which
the replay takes who is leaving and when, was missing from the proof of every impact
(`a0f9a0b`). In the trace metrics: a target that two returned documents carry was
recorded as two search hits at two ranks (`4b0bbf7`). The aggregation drew five
(`7f9ac03`). An arm that produced no export left no row to say so. A scenario run twice
with one run limited was given Wilson's interval as if it were one trial. A limited
run's invalid report was in no count. An invalid report's claims came back as unexpected
ones. And a conflict's observations reached no measure, so a conflict resolved correctly
from an observation nobody made scored in full everywhere. That last one was the
author's omission against a step 3 ruling, which keeps the observations as a flag apart
from the payload: the flag was on every row and nothing read it. The reviewer offered
two repairs, and the one taken was the separate measure, since the other would have
reopened that ruling.

One finding was declined, twice. The reviewer wanted an unknown whose reason only an
agent can give, ambiguous or conflicting, always filed as not replayable. The third
ruling says otherwise, after an amendment made to this same reviewer's read at the
interview: such a claim is contradicted when the rules establish the fact from the run's
reads. The case that decides it is the one the adversarial tier plants, a stale owner in
a runbook that the tracker's record resolves by authority, where a report that stops at
"conflicting" is refuted by what it read. The reviewer raised it again on the fix
commit's second read, and the owner let the ruling stand. The reviewer's procedural
point was fair all the same: the repository stated the ruling in one docstring sentence,
and a reader without the interview could not know it was a decision. The module's
docstring now carries it with its reason (`60f9cb5`). One gap the reviews did not find
came out of a measurement. Counting which reads a conclusion rests on showed that a
conclusion about everyone takes its candidates from the run's enumeration of the
employees while its proof was empty, so that read could not be credited through it. On
the test world the read was credited anyway in all 14 such cases, through an HR record
some assessment had consulted (the step's rulings record); it was fixed for what the
proof should say, and it amends a sentence of the fourth ruling (`300ef94`).

The aggregation started from two sentences that disagreed. The build plan said results
are x of n per class and tier with Wilson intervals. DESIGN's paragraph on the golden
set said claim-level counts are not independent within a scenario and uncertainty is
bootstrapped over scenarios. Each is right about a different number. Thirty scenarios
passing or failing a check are roughly independent trials, and Wilson fits them. The
claims inside one scenario share its people and its documents, so a system that misreads
one clause gets a dozen claims wrong together, and a ratio over claims takes a bootstrap
that resamples whole scenarios within their tiers. A class has one to four scenarios and
shows raw counts only. The sixth ruling also fixed what the code may not decide: the
arms, the named checks, the seed, the repeats and the retry rule belong to the
preregistration and are arguments with no default.

What exists at the end of the step is the instrument, checked against a report that
cannot be wrong. No harness exists yet, so no system has been measured. The gates run
the oracle's own answer, written as claims, over the reads a complete investigation
makes, recorded by a test through in-memory systems, on the tests' throwaway world of
thirty scenarios with stand-in prose. There the replay reproduces the report whole:
1,001 claims under the normal condition, 613 with the tracker down and 722 with the
calendar down, of which 547, 613 and 349 are strictly grounded
(`tests/unit/test_evaluator_evidence_measures.py`). Retrieval targets are derived by
removing each statement through the oracle. Under the normal condition 20 scenarios have
one, 31 targets are the planting scenario's own and 4 are another scenario's, skills
planted for a colleague that move only rows no report must hold; with the tracker down
the counts are 8, 15 and 0, with the calendar down 17, 25 and 2
(`tests/unit/test_evaluator_retrieval_targets.py`). Of 960 completed reads, 158 supplied
something a conclusion rests on, and nearly all the others are the fixture reading every
document by its id (`tests/unit/test_evaluator_proof_contribution.py`). Eight of ten
scenarios is 0.490 to 0.943 by Wilson (`tests/unit/test_evaluator_intervals.py`), the
figure DESIGN has quoted since the world milestone as the reason the set is sized for
failure localization. A truthful report at the ceiling of a measure says the ceiling can
be reached and nothing about whether the measure separates real systems (FINDINGS,
`grounding-gates`).

Figure: the 1,440 must-assess verdicts as one bar split by the negative each rests on
(viable 420, skill 420, availability 244, component 236, hard rule 40, unknown 80), the
420 skill verdicts marked as the ones no read can close strictly. A second candidate:
the three readings of grounded on the truthful report, reproduced, grounded end to end
and strictly grounded, per condition (1,001 / 1,001 / 547; 613 / 613 / 613; 722 / 722 /
349).

## 2026-10-01 — The answer key had two readings of time, and one outage turned out to have no answer

*M2 step 3, the investigator milestone's third build step: the evaluator's grading, from
the truth manifest's decoder through the joined world, the oracle, the grade's rows and
the plan checks to one outcome per export. Six rulings by interview, each read by an
external reviewer with no chat context, then twelve planned commits reviewed in batches
after their pushes (session 46, 2026-10-01). Feeds: the M2 milestone report's
evaluation-design section, on which truth a run is graded against and on what the outage
results are allowed to cover; the final report's section on honest measurement, on a
claim that was narrowed the day it was made and then earned by a second run; and its
process section, on what the batch reviews caught.*

The step's one-line plan said the evaluator grades against truth "time-filtered at the
scenario's now", and DESIGN said the same since the world milestone: a fact is
admissible from the day its provenance became observable. The second ruling's interview
started from what world assembly actually proves, and that turned out to be narrower
than the plan assumed. A world has two views. The dated view applies the planting dates.
The runtime view is what a run obtains: every record the systems hold, dated to the run
day, because the harness knows no planting date. Assembly proves the sealed key under
both views, and only for the normal condition. Whatever the evaluator derives on its
own, a candidate outside the probe set or any expectation under an outage, was never
shown to agree. So it was measured, on forty seeds of the golden plan. Under the normal
condition none of 2,880 must-assess pairs and none of 1,280 outcomes differ between the
views, and 36 of 32,960 other candidate pairs do. Twenty of those flip a verdict from
non-viable for skill to viable, each because a later scenario plants a comment or a
document that evidences the skill. Under a tracker outage two must-assess pairs differ,
and one trace explains both: the scenario's own ticket comment evidences the candidate's
skill, the tracker is down, a document a later scenario plants restates the skill, the
dated view hides that document and a run can read it. An agent that read it and called
the candidate viable would have been graded wrong by a dated oracle. The ruling made
runtime truth the oracle and kept the dated view as a construction diagnostic (FINDINGS,
`runtime-truth`; the probe and its capture under `probes/`).

Two live runs on the golden world followed, and both had a way to fail. The golden world
was sealed by the rules of generator version 14, and the evaluator derives everything
beyond the key with today's rules, so world loading reproduces every sealed key before
anything is graded and refuses the world if one does not come back. That was the step's
named risk, and the first live load cleared it: thirty of thirty keys (`d648b27`). The
second run compared the two views on the golden world itself and found no differing pair
under any of the five conditions (`50fcde5`). The FINDINGS entry then said that no
graded item of the reported results rests on the choice of view. The reviewer's batch
read pointed out that the comparison covered verdicts, reasons and outcomes for the
sealed impacts, and that under an outage the derived impact sets, constraints, conflicts
and unknowns had never been compared, so the sentence claimed more than the run showed.
The claim was narrowed the same day (`59b758d`). The owner then ruled to extend the
comparison instead of living with the narrow sentence: the oracle's core became a
function that can be asked of either view, the comparison covers the complete answer
part by part, and a second declared run found nothing differing (`60b23e4`, `7caa170`).
On six throwaway worlds the same function does find differences, so it is able to. The
sentence the first run overclaimed is the one the second run supports, and the report
can say the choice of oracle was tested on the reported world, where it changes nothing,
and matters on worlds where later evidence exists.

The corpus outage is the part that changed what the milestone will report. The plan
checks' tests use a truthful report, a fixture built from the oracle that states exactly
what it concludes, so that each test breaks one thing. Under a corpus outage that
fixture failed the report's own coherence check on 12 of 30 scenarios, 119 chain
findings (`87ce8af`). The cause is in what the corpus holds. Only the corpus says which
clause applies to an artifact. With it down the oracle expects no constraint claim,
since the clause cannot be read, and expects every candidate of that impact unknown on
what the clause requires. The chain admits an unknown about a clause only when the
report cites the clause, and a run with the corpus down cannot name it. The oracle can,
because the sealed constraints are an input of its rules. So the expected answer there
was something no report could state coherently, and behind that sat a plainer problem: a
run cannot tell an impact a clause governs, where unknown is expected, from one no
clause governs, where the normal answer is. A system that always assigns would be right
on the second kind and one that always says unknown on the first. The author recorded
the finding, held it with a test that stated the fact, and left the ruling to the step
that registers the outage set. The reviewer did not accept that: a perfect report built
from the oracle receives a coherence failure, so the behaviour could not stay as
expected and needed a ruling. It was ruled the same day. Beside the unreadable leave the oracle has a second
state with no claim-level answer, the unreadable policy, for every scenario under that
condition, and such a run is limited to the checks that need no expected answer
(`d26bfe0`). Of the four single-source outages two can be graded, the tracker's and the
calendar's. That narrows the outage table the milestone promised, and the weighing was
explicit: a number no system could score on is worth less to a reader than a stated
reason for declining to produce it. The check that found it cost nothing, since the
fixture already existed: ask whether the oracle's own answer, written as a report,
passes the report's checks.

Two smaller findings from the batch reviews are worth keeping. The join's refusal
messages were written to carry no sealed content, because an evaluation job logs in
public, and each refusal was raised from the decoder's or the rule's own exception,
whose message names ids and values; a printed traceback shows the whole chain. The fix
went further than suppressing the chain at the raise, which only hides the context from
the default formatter: the refusal is raised after the handler has ended, with no cause
and no context, and a test formats the complete traceback and looks for the sealed
content (`59b758d`). And the coverage check took three passes to count one omission
once. Its first form recorded a probed candidate left out both as a recall miss and as a
coverage finding. The second left the probe set out of every gap, which lost the
omission wherever no recall row exists, in a limited run. Reproducing that finding
before fixing it showed the same hole on the graded path, where a report under a tracker
outage still claims the ticket's impact the oracle no longer expects. The rule that
holds is stated by where the other record exists: the probe set is left out of a gap
only for an impact the oracle expects (`d6cbccd`).

## 2026-10-01 — A provider assumption became a column in the price table, and a digest became provable at the byte

*M2 step 2, the investigator milestone's second build step: the run export, the
artifact a run leaves behind and the evaluator grades, built as plain data in the core
package with its codec, its pricing arithmetic and the tool specifications, eight
commits each reviewed after its push (session 45, 2026-10-01). Feeds: the M2 milestone
report's evaluation-design section, on what a cost claim is allowed to say and on why
the export is one byte sequence; the final report's reproducibility section, on
enforcing a canonical encoding where the reader meets bytes; and its process section,
on a post-push reviewer reversing a call the author had argued and the owner had
accepted.*

The step's interview had settled, among six rulings, how a run's usage and cost are
recorded: a counter the provider did not report is unavailable and never a zero, and a
cost that would have priced a missing counter is incomplete. The first pricing commit
then quietly narrowed that rule in code. A constant named `ALWAYS_REPORTED` declared
that input and output tokens are the two classes every provider reports, so a cost was
complete when those two were present, and a cache counter the provider had not
reported added nothing, on the reading that an absent cache counter means no cached
tokens were billed (`eb98474`). The docstring called it a provider assumption and
promised that the acceptance spike would check it against the real configurations.
The author had argued the narrower rule in chat on the grounds that Bedrock reports
cache counters only when caching is in play, so the literal ruling would mark nearly
every uncached call incomplete, and the owner had accepted it before the review. The
external reviewer, reading the pushed commit with no chat context, named the defect in
one sentence: a cost could be understated while labelled complete, which is the one
thing the completeness flag exists to prevent, and a fact a spike might later prove
should become recorded policy rather than a global assumption in code.

The repair moved the assumption out of code and into data. Each rate row of the
committed price table now carries a policy, `when_absent`, with two values: unknown,
the default for every rate, under which a missing counter makes the cost incomplete;
and zero, which a row earns only once a probe shows, per model configuration, that the
provider omits that counter exactly when nothing of that class was billed. The policy
travels in the pricing rows every export embeds, so a cost's completeness is
verifiable from the record alone, with no code constant to consult and no spike
finding to remember. Until the spike earns the zero entry for a configuration, a
missing cache counter makes a cost incomplete, which is the ruling's literal reading
restored (`aadb2d8`; the spike's obligation is in the stream's TODO under build
step 7). The lesson is the same shape as one already in the
repo's lessons, that a prompt instruction stays only on a probe that shows it moves
the model: a claim about a vendor is data a probe earns, and the place it lives is a
record a reader can check, not a constant the author believed. The reviewer deserves
the credit here; the author had the honest instinct to name the assumption and the
wrong instinct about where to put it.

The second movement is about the export's bytes. The project has carried a one byte
rule since the world milestone: everything hashed or compared is canonical JSON, so a
digest is a property of the value and never of a serializer's defaults. The codec
commit gave the export that encoding, and the review found two ways one export could
still be two byte sequences. Tool arguments kept the caller's key insertion order, so
two equal exports whose arguments were spelled `{"a":2,"b":1}` and `{"b":1,"a":2}`
compared equal as values and produced different bytes. And the decoder took an
already-parsed object, so input that normalized on the way in was accepted without a
trace: a duplicate in a set-valued list collapsed silently, role-indexed entries out of
order were sorted by the constructor, and a reader would have cited a digest of bytes
that no writer of this project could have produced. The repair has two parts. Argument
objects are frozen with their keys sorted to the leaf, since a key's position says
nothing in JSON. And the reader now meets the artifact as bytes: a bytes decoder parses
them, decodes the tree, re-encodes it, and accepts the input only if the re-encoding
reproduces it byte for byte, so a pretty-printed spelling, a duplicate, or an unsorted
entry is refused as not canonical (`7241e1a`; the tests build each case). The consequence for the evaluation design is that the digest the evaluation
artifact cites is provably of a canonical tree: one export is one byte sequence, and
the rule is enforced where the reader actually meets bytes rather than trusted from
the writer's good behaviour.

The same step moved the entity codec, the one JSON shape of the seven observable
records, from the world's sealed-spec codecs into the core package, where both the
agent and the evaluator can reach it, without moving a sealed byte. Two guards say so:
the suite's pinned semantic digest, which hashes every planted entity's canonical
encoding and did not change, and the historical-bytes live test rerun against the
objects in the buckets after the move (twelve cases green and the same reasoned skip
at commit `7aa9523`; the amendment is in the probes' findings file under the
historical-bytes entry).

## 2026-09-19 — Fifteen traces had accepted everything, and the panel's question was whether anyone else could check that

*M1 step 16, the hand audit's close: a four-seat critique panel over the audit of the
first golden world, its findings answered the same day, the audit sealed under a
content-addressed identity, M1's exit (session 35, 2026-09-19). Feeds: the M1 milestone
report's evaluation section, on what "golden" can honestly mean and on auditing an
audit; the final report's process section, on a panel as a gate, on sealing only the
method that ran, and on an external reader as a reading engine.*

By the end of the previous session the hand audit looked finished. Thirty scenarios
had been accepted, fifteen of them traced to their evidence in a frozen ten-step shape,
and no trace had found a defect in the world. The reason to run a panel anyway was not
a suspicion that a key was wrong. It was that "we found nothing" is a weak sentence
unless someone outside the audit can check the claims it rests on, and the audit's own
prose had grown confident enough that its claims deserved an adversary. Four seats read
the checklist, the sheet, the rulings record and the summary blind to each other: one
checked every sentence of the summary against the record, one attacked the checklist
against the code and the design contracts, one hunted for what the audit had never
asked, one modelled what a released example would leak. The run cost about 795k
subagent tokens (the seat reports and synthesis are in the private stream,
`panels/2026-09-19-audit-panel/`), and every finding was reproduced on the source
before it was triaged, which is how two of the seats' claims were narrowed before they
entered any record.

**The strongest finding was about proof, not defects.** The audit's outcome check reads
an "outcome witness" the sheet renders: the generator's own assessment of every
employee, produced by the same viability and outcome functions the world was built
with. For an assign outcome that is fine, because the graded candidates in the key are
enough to show it. For the seven outcomes that say "uncovered" or "unknown", the claim
is a negative over the whole organization, nobody qualifies, or exactly one person's
missing record decides it, and the sheet gave a human no way to prove that
independently: the cited fact rows were a projection for the key, not the roster, and
the witness was the rule counting itself. The methodology-breaker seat put it plainly,
and the external reviewer who read the raw seats ranked it the one technical change to
make before sealing. The answer was a new block in the sheet, a criterion universe: for
every impact, every employee's facts of the four families the criteria read, component
memberships, skills or the record's absence, leaves and events over the need's window,
employment type, rendered from the fact base under the dated view with no call to the
viability or outcome functions (`b1e8c0e`). The seven outcomes were then recounted by
hand from that block, the criteria frozen before any person was read, and all seven
equalled the witness and the key. The recount also made a pattern visible that the
traces had only argued: the two shapes differ by exactly where the organization's two
blank skills records sit. When the eligible component contains one of them, the count
is zero viable, one unknown, twenty-seven non-viable, and the outcome is unknown; when
both blank records sit outside it, the count is zero, zero, twenty-eight, and the
outcome is uncovered. One reviewer's proposal was not taken as offered: a rendering that
labels each criterion as passed, failed or dominated would need the core rule to expose
states it does not carry, since its result holds reasons only for a non-viable verdict
and unresolved questions only for an unknown one, and the fact block gives a reader the
same visibility without touching the core. The limit is stated in the summary and in
the design record in the same words: the independence is from the rule, not from the
data, because the dated view and the fact reads are the code the rule uses.

**One design gap, and the alternative that died.** The seat attacking the checklist
found a scenario whose timezone distractor had the leaver as its far attendee, alone on
the event. In the leaver's own zone the meeting fell on the last day of their leave; in
the reference zone it fell the day after, and the key marked it a non-impact. The
modifier's docstring admitted the case, a unit test named it, the design record's
timezone ruling spoke only of a far colleague, and the trace had accepted by applying
the rule without asking the audit's founding question, whether a careful reader would
call this an impact. The organization has one far person, who is the far seat in every
timezone planting and the leaver in one of them, so the case was a matter of when, not
whether. Regenerating the world was the alternative on the table and it died on cost
against correctness: a new version, a new projection of twenty-eight calendar
creations and the whole audit redone, for a key that is right under a rule the code
already applied and the design had simply never written down. The ruling wrote it down:
leave dates are date-only HR facts read in the scenario's reference timezone for every
employee, and a person's location does not redefine the leave interval, because the HR
record carries no zone. The key stands and the scenario is that convention's test. For
future worlds the far seat will always be a colleague, and because the organization's
guarantee of one far person no longer suffices when that person is the leaver, the
guarantee grows to two far seats in the same change [BUILT 2026-09-19, session 36,
commit 33a7b69: generator version 15; the golden world stays at version 14].

**Sealing only the method that ran.** The audit's identity is the digest of a small
index that binds the record, the summary and the checklist by their digests, so the
checklist inside the seal is a claim: this is the method this audit applied. The panel
had proposed a dozen new checks. Folding all of them into the checklist and then
sealing it would have claimed checks nobody ran. The rule adopted: only checks actually
executed on this world enter the bound checklist, each marked with the scope it ran on,
and everything else goes to the public methodology's note for the next audit. Three
were executed: the required-sources line derived for the fifteen untraced scenarios,
the structured tier's class promises on its ten, and the stale owner's placement
outside the component on the four conflict scenarios; all passed. The reviewer had
suggested two index fields, the checklist applied and the checklist next; the push-back
that held was that a "next" digest is a method claim no reader can verify, so one bound
file with executed scopes is the honest shape. Two further traces the panel named for
structures the fifteen had left unexercised, a prose-only skill that makes a graded
person viable and a wrong-team meeting sitting in the impacted meeting's own slot,
both accepted, bringing the traced count to seventeen.

**No example before the first evaluation.** The leak seat's model decided the release
question. The sheet's cited entries are each cited entity's whole record, which means
they carry rows dated after the scenario's `now` that are other scenarios'
answer-changing plantings; thirteen of thirty scenarios carried one such row, and any
deadline scenario's witness is a named partition of the organization. A released
example would therefore leak the private rest unless cut at `now` and stripped of the
witness, the header's prose rollups and every cross-referencing note. The ruling: no
golden scenario is released at M1's close; the release waits for the first M2
evaluation report, so the example a reader sees is a key beside an agent's actual run
on it, and retirement before any evaluation exists would be a promise with nothing to
enforce it. The per-scenario retirement rule went into the design record now (a
released scenario keeps its place in the sealed world and the audit's provenance,
leaves the scored set of every later blinded evaluation, is named as retired in that
evaluation's manifest, carries a contamination statement), the least-leaky candidate
is recorded privately and never designated in public, and a throwaway-seed world,
never sealed or scored, will illustrate the sheet in the public tree.

**The seal, and the shape of the evidence.** With the amendments applied, the record
corrected in eleven places with dated notes and a ledger and none of them touching a
key, the index was rebuilt and the four objects were created once under the truth
bucket's create-only audit prefix, each read back and re-hashed equal, on 2026-09-19:
audit identity `93745e04fe11de480da1e785873fddb0d2f7e843e21c573f8f3beb7b87da44d1`, the
sha256 of the index object, with the object version ids kept in the private stream's
audit folder and never in the record, since the record is sealed by digest before the
upload exists (the upload mode in `16638f2`, the design record's account in `40d452b`).
The chain the milestone can state in one sentence: thirty accepted, seventeen traced,
seven recounted without the rule, three panel checks on named scopes, a four-seat
panel, the amendments, the seal. The reading-engine pattern carried the day's human
hours: an external low-context reader did the seven counts and the two traces from
packets built off the new sheet, the main chat re-verified every claim against the
sheet and the code before entry, and the reader caught one wording slip of the main
chat's own brief before it reached the record. The cost of that pattern is the
re-verification; its benefit showed on both sides of the seam in one day.

Figure: the two-shape universe count as a small table or diagram, unknown (0 viable, 1
unknown, 27 non-viable) against uncovered (0, 0, 28), with the blank record's
placement inside or outside the eligible component as the one variable.

## 2026-09-15 — The first world the models wrote took five runs, and the gate on its numbers changed the cap it was meant to confirm

*M1 step 15 of the build plan: the measurement world the step 14 design demanded before
the remaining prose classes — the qualification rows generated under the real
pipeline, sealed, projected, approved — and then the gate that the design tied to it:
one session (session 26, 2026-09-15) reviewing every fix the five runs forced and every
item on the revisit list, one question per exchange, an external low-context reviewer's
read on each relayed by Arda, Arda's ruling on each. Feeds: the M1 milestone post; the
final report's evaluation section, on measuring a generator before trusting it and on
what a sample of three can and cannot say; and its process section, on interview mode
with an external reviewer and on letting a probe decide before the argument starts.*

The design of the day before had said, in one sentence, that no more prose classes
would be built until one world had been generated for real and its numbers read. This
entry is what that sentence bought. The world was three ticket comments, each planted
to carry one skill fact, and the pipeline that had passed every unit test refused to
produce them four dispatches in a row. Each failure was on a mechanism the unit level
could not see, and each was decided in minutes by the same move: one writer call, one
checker call, the raw tool input printed, and the shape of the fault visible before
anyone argued about it.

**Four runs, four faults, one probe each.** The first run (34802507979) made twelve
writer calls and never reached the checker: the namespace scanner demanded the
author's own name in the body, and a person writing a comment says "I", never "Ines
Yilmaz", so every draft died on a lexical anchor for a name the text could not
naturally contain (fix in `a011245`). The second run (34802945370) made one writer
call and then spent the checker's whole retry budget on one text: the checker had
written the ownership relation backwards, the person owning the ticket instead of the
ticket owned by the person, the value spec refused the wrong type, and the code
treated that as the checker's protocol failing, retried three times at temperature
zero, got the same reading three times, and aborted the stage (fix in `adacec1`). The
third run (34803388159, twelve writer and twelve checker calls) reached
the checker every time and was refused every time: told not to name herself, the
writer padded each comment with "I can take this on", the checker read the offer as
ownership, and ownership was outside the brief. The fourth fault never made a run;
a local probe between runs found the writer, now forbidden to offer, padding with
readiness instead ("I'm ready to dig into this"), which the checker read as hedged
ownership and as an availability claim no predicate can express. Both were fixed in
one commit (`8e17a65`): the ticket-comment register now asks for a remark about the
work as it stands, in the past or present tense, never an offer, plan, request or
promise; the brief allows the author's own ticket and its component as true context;
a reversed entity pair is put the registry's way round when the ids and their kinds
prove the swap. The fifth dispatch (34803999468) passed: the hardest comment on its third attempt,
the other two on their first. Two more refusals then came from outside the prose
stage, a calendar quota and a Frappe site that already held a world, and are the
previous session's story (`dc1a7a9`).

**The numbers, recovered from the wrong place.** The stage's counters were printed
only after sealing returned, and the passing run sealed and then died in the calendar
loop, so the tokens and latencies died with it. Bedrock's CloudWatch metrics carried
them, per model at one-minute resolution, attributed to each run by its time window,
and the hour's sums reconciled exactly (`probes/FINDINGS.md`, the measurement-world
entry). The passing run was five writer calls and five checker calls for three
comments: about 640 tokens in and 27 out per writer call at 0.8 s, about 1,490 in and
104 out per checker call at 1.0 s, about $0.015 by Cost Explorer's share; the whole
night of 71 calls cost $0.093. The counters now print before sealing and seal into the
record (`1256d37`), so the next world's numbers travel with it.

**The gate, and where the reviewer moved the answer.** Six questions were put in
order, each with the evidence beside it, and on four of them the reviewer's relayed
read either matched the recommendation or sharpened its wording. The first-person
exemption was adopted but stated narrowly, as the target supplying the subject of a
first-person statement rather than as a general relaxation of subject anchoring, and
the docstring now says the drop is positional and names the convention it relies on.
The untyped rule and the canonical pair were adopted with two honest residuals: the
swap's no-guess branch has no live predicate, since none pairs equal subject and value
kinds, and retrying a temperature-zero checker on a protocol failure can only help
against provider-side variation, which run 2 demonstrated by spending three retries on
an identical answer. The prohibition on offers was adopted and credited for the pass,
with a distinction the reviewer insisted on: an offer is a coverage signal the
qualification class does not own, so forbidding it is containment expressed upstream;
the allowed ownership fact is legitimate context because it is true, and it holds only
where it is true; but a text that passed because the checker read "something I can
work through" as hedged ownership is not a success of the allowance, it is a checker
residual.

Two rulings went further than Claude's recommendation because the reviewer pushed.
The hedge tolerance from the fourth fix, which let a hedged mention of allowed context
pass, had been justified in code as "nothing rests on it". Claude identified the
condition under which that is true, that the allowed fact is established by a
structured record the agent under test reads directly, and recommended recording the
condition and enforcing it at the next class. The reviewer's answer was that knowingly
introducing a rule that becomes unsafe as soon as the next class lands is the wrong
order: encode the invariant now, let the next class test the boundary. It was encoded
the same hour, in a different place than proposed. A brief's construction now refuses
an allowed fact evidenced by the brief's own target, since a fact this text evidences
is one the text must carry, and the guard tolerates a hedge on allowed context only
when a structured record establishes the fact, refusing a hedge on a fact that only
other prose establishes as a softened conflict the world never planted. The other
push was on the cap. The baton had framed the cap of four as confirmed by a maximum of
three attempts observed. Claude's arithmetic said otherwise: attempts are fresh
samples, so a brief that passes one attempt in three exhausts a cap of four about one
time in five, and five such briefs in a world fail the generation about two runs in
three; at a cap of eight the same figures are about one in twenty-five and one in
five [PRELIMINARY — a per-attempt rate read from one target's three-attempt pass, a
point estimate that supports no prediction]. The reviewer agreed the inference from
the maximum was unsound, agreed eight should be the default rather than a golden-run
knob, and added what Claude had left out: the earlier entry in these notes had called
four a diagnostic cap that assumes a good prompt, and raising it should not abandon
that. So attempts above four are now read as a struggling brief, from the sealed
attempt count and with no new field, and the cost of an exhausted run is stated
plainly as a re-dispatch of sealing before any vendor write. (The design document
itself had recorded only that the cap would be revisited; the diagnostic reason lived
in these notes, and the record now says which is which.)

**What was refused, and why the worst run argued for it.** Feeding a refusal back into
the writer's next attempt was rejected for this milestone, and the strongest argument
against it was the run that most seemed to call for it. Run 3's twelve refusals of
twelve exposed a wrong register prompt, fixed once for every future world; with
feedback, the same defect would have looked like one refusal followed by a corrected
pass, and the prompt would still be wrong. Attempts stay identical writer requests, so
retry depth remains a measure of one fixed configuration's difficulty, and if feedback
is ever introduced it will be a new strategy with its own digest and attempts marked
base or corrected.

**The record learns to say why.** The gate could not answer two of its own questions:
what the two refused drafts of the hardest comment had been refused for, and how often
the checker produced claims no predicate expresses. Refused text is discarded by
design, because the repository's job logs are public, and a refusal was sealed as a
guard name and a count. The ruling adopts a closed vocabulary of reasons on each sealed
refusal, seven names and no content, plus one run-level counter for pairs the checker
wrote backwards and the code put right, which is a normalization and not a refusal.
The reviewer's caveat is the honest one: a reason says which check refused, not whether
the writer or the checker was at fault, and only the hand audit separates a checker
misreading a clean text from a checker reasonably failing on a confused one. Records
sealed before the change will decode with the reasons unavailable, never as zero. The
three-character exact-spelling cut in the scanner was kept as a heuristic without
contrary evidence, the world having exercised only the path it was designed for, and
one wording was corrected on the way: a miss there is of a foreign surface mention,
which the checker still catches when the mention makes a claim; only a mention that
makes no claim has the scanner as its sole layer.

**A sample of three.** Arda read the three accepted texts against their sealed
propositions. Two say exactly the skill they were planted to carry and nothing else,
and the checker read them exactly. The third, "I've got experience with Go, so the
retry queue migration is something I can work through", was read as the skill, which
is right, and as hedged ownership of the ticket, which the sentence never says; the
only ownership cue in the checker's request is the opening line naming the ticket
beside the author, which is the hypothesis, on one sample, for where the proposition
came from. It passed harmlessly because ownership is on the ticket's own field, which
is precisely the condition the hedge tolerance now enforces. Three of three required
facts read correctly and one of three texts over-read is what the sample says, and a
sample of three supports no rate. What it also shows, and what the golden world's
audit will look for, is that all three texts share one sentence frame at temperature
0.7: "I've worked with X before, so ...". A benchmark whose qualification comments all
sound alike is a shape an agent could learn. Two corrections to the handoff that
started the session belong here so the next reader does not repeat them: the comment
bodies live in the benchmark-private world spec, not in the scenario specs, and the
pair canonicalization landed in the fourth fix's commit, not the second's.

Figure: the four-run table of writer and checker calls (12/0, 1/4, 12/12, 5/5) as a
before-and-after bar, one bar pair per fault.

## 2026-09-14 — Prose entered the world through a gate, and the gate was rebuilt five times before any model wrote a word

*M1 step 14 of the build plan: the design interview of session 23 (ten questions, an
external reviewer's read on each, Arda's ruling on each), then five commits — the
semantic world and composition, the artifacts, the Bedrock seam, the materializer, the
wiring — each reviewed after its push, with the review fixes as their own commits
(2026-09-14). Feeds: the M1 milestone post; the final report's evaluation section under
"ground truth by construction" — how model-written text joins a benchmark whose answer
key is fixed before the model is paid; the architecture section on the two identities
of a world; and the process section on reviewing a design against a low-context
reader.*

Until this step every byte of a world was a function of its seed. The moment a
language model writes a runbook paragraph, that stops being true, and the whole step is
the consequence of one sentence in the founding design: the seed identifies the
semantic specification, the frozen bundle identifies the realized world, and the two are
not the same thing. Everything else followed from taking that sentence literally.

**Ten questions, one reviewer, one ruler.** The step opened with a design interview,
one question per exchange, and Arda relayed each proposal to a second chat with almost
no context and brought its verdict back. That reviewer's closing "my ruling" was, by
Arda's own instruction that morning, the reviewer's verdict and never his; the ruling
stayed with him. The shape that came out: the pure assembly no longer produces a world
but a *semantic world*, complete in every structured record and holding, where a model
must write, a typed pending target instead of text — a brief that says which comment or
section, under which parent, at which position, carrying which facts, in which
register. A pure `compose` places the accepted text afterward. Two identities are
recorded: a semantic digest, the hash of everything the seed determines, which two runs
from one seed share whatever prose they accept, and the world version, the hash of the
realized bundle, which they do not. The reviewer's sharpest early contribution was to
move the regression oracle: the suite had pinned a reference seed's world version, and
that pin could not survive non-deterministic prose, so the pair became generator
version plus reference semantic digest, and the realized version became provenance no
test expects to reproduce. Two of Claude's own additions were adopted the same way: a
required fact's role — answer-changing or context — is derived by running the rules
once with the fact removed rather than tagged by the class author, because the hand
audit at step 16 reads every artifact carrying an answer-changing fact and a wrong tag
would misdirect it silently; and the surface namespace a text may use is derived from
the brief's facts through the closed vocabulary, so a class cannot forget a name or
leak one.

The rest of the interview fixed the machinery the reviewer and Claude then mostly agreed
on. The record of how each text was accepted seals with the world and is part of its
identity; rejected text exists nowhere, not even in the job log, because the repository
is public and its Actions logs are world-readable, so a quoted rejected sentence would
be a third benchmark-private surface with no access policy. A restart before sealing
regenerates; after sealing it resumes a version the operator names, proven six ways,
and auto-discovering an unfinished version by listing the mutable prefix was rejected
as guessing. Four guards run in order, the paid one last: a namespace scanner, a
lexical required-fact check, an extraction by a second model family that never sees the
brief's facts and returns propositions with polarity and an assertion mode — the text's
modality, never the checker's confidence, so "Deniz might know Kafka" is affirmed and
hedged whatever the checker believes — and the human pass. Containment is the required
statements contained in the affirmed, asserted ones, and those contained in the
required plus the allowed; anything negated, hedged, about an unlisted subject, or
expressible by no predicate refuses. Attempts are fresh samples from one prompt with
nothing fed back, under a cap of four recorded in provenance, and the reviewer's
arithmetic was worth keeping: at a 70 % per-attempt pass rate that cap gives about 61 %
whole-world success over sixty targets, at 80 % about 91 %, so four is a diagnostic cap
that assumes a good prompt, to be revisited on the first world's numbers and not
before. And the one push-back taken whole: prompt policy belongs above the adapter.
The Bedrock layer sends a request it is handed and returns text or a filled tool; what
a runbook, a guard or a required fact is never reaches it.

**One check the interview missed, caught against the project's own rule.** The
interview had put the materialization record in the world spec's provenance. While
building the artifacts Claude read the record's contents against the standing storage
rule — storage follows who may know a thing — and they contradicted: the world spec is
readable by the validator's role and holds nothing truth expects, and a brief's
required facts and a checker's reading of a text are exactly what truth expects. The
record and the briefs moved to the evaluator-only truth manifest before a line of
encoder was written, on Arda's ruling. That choice had a price paid later in the
wiring: a resume needs the record to re-compose the world, and the truth manifest has
no decoder by design, so the generator got a private decoder of that one section,
unreachable by the validator under the import law — a narrower thing than "the
generator can read truth anyway".

**Five reviews, and what each moved.** The post-push review found something real each
time, and reproducing every finding before triage (the method since step 9) confirmed
all of them. On composition: nothing bound a composed body to the digest its record
claimed to have accepted, so a sealed record could describe a text the world did not
contain; `compose` now refuses a body whose digest is not its record's. On the same
types: a target record could hold impossible histories — four attempts and no
refusals — and now demands exactly one refusal per failed attempt, since the first guard
that refuses ends an attempt. On the seam: the "closed fault vocabulary" was
mechanically false on the success path, because a response without usage silently
became zero tokens and a malformed count leaked a raw `ValueError`; usage is now read
strictly and any defect is the seam's own protocol fault. On the materializer: the
scanner had left a foreign world name in another case to the extraction check, which
deliberately ignores mentions that make no claim — "thanks selin" would have passed
every guard while naming an identity the brief did not admit. The fix was a ruling on
an asymmetry: a false refusal costs one attempt, a missed identity costs the benchmark,
so every world name is refused in any case, employees by given name as well as full
name, with one exception for forms of three characters or fewer matched in exact
spelling, because "go" is in most sentences and the skill Go would otherwise refuse
them all. The reviewer then found the two-pass version of that scanner still wrong —
an allowed short form masked first erased the longer foreign form it sat inside, "Deniz"
hiding "Deniz Kowalski" — and one global longest-first pass over allowed and foreign
forms together replaced it. On the wiring: the job printed the world version before
sealing as the operator's resume handle, but stdout under the workflow's pipe is
block-buffered, so a hard kill mid-sealing could lose the one line the recovery
protocol depends on; the line is flushed now, and the wording "before the first side
effect" became "before the first persistent world or vendor mutation", since the paid
model calls precede it and create no resumable state. And the probe workflow could exit
green while its own diagnostic line said the tool was not filled; its exit now depends on
that condition.

**What is verified live, and what is not.** Both models answered from the workstation
under the administrator profile — the two structural live tests, under four seconds
for the pair — and the manual probe workflow was green under the generator role on
2026-09-14, so the production principal holds its invoke grant and the forced tool
choice `any` over a single tool is honoured by both families on the shortlist, which
had been a documented assumption until then. A side finding worth its line: the
test suite's network guard matches the resolved IP a socket connects to, not the
hostname, so an endpoint cannot be allow-listed by name and the live level now runs
without the block, which is what "live" means. The suite grew from 1677 to 1754 tests
across the step (the pytest runs of session 23), 77 of them the gate's own.

[PRELIMINARY — no prose has been materialized for a real world yet. Tier 1 has no
briefs; the first Tier 2 world at step 15 gives the first-attempt pass rate, the
refusal distribution by guard and the cost per world that the design predicts (DESIGN
estimates well under a dollar per world at thirty scenarios; the per-token prices are in
the Bedrock probe of 2026-08-26, `probes/captures/bedrock/models.md`). The cap of
four, the other-claims bucket and the absence of refusal feedback are all to be judged
on those numbers and on nothing else.]

Figure: the pipeline as one diagram — semantic world → materialize → compose → freeze
the two identities → print the resume handle → seal — with the resume path rejoining at
the seal after its proofs; the two identities labelled where they are born.

## 2026-09-13 — The validator earned its keep on the first world: two boundary faults, no world fault

*M1 step 13 of the build plan, the first world live: the `generate world` workflow run
34780738512 (attempt 1 red, attempt 2 green), the validator runs 34784309718 (refused)
and 34785009950 (approved), the reader fix `c9823a7`, the platform's Bot Fight Mode
ruling in its commit `b894ac6` (session 22, 2026-09-13/14). Feeds: the M1 milestone
post; the final report's evaluation section under "ground truth by construction" —
what an independent re-read of the live systems is worth, shown on the day it caught
something; and the operations section on the edge, where the first cloud-network client
of a proxied hostname met the free plan's bot heuristic at the exact moment of the
first real run.*

The first world took two attempts to generate and two to validate, and neither fault
was in the world. Both were boundaries: an edge heuristic turned against the project's
own clients, and a vendor's read order leaking into a field the design had declared
canonical. The second one is the reason the validator exists, and it found it on the
first world it ever read.

**The edge that had never met a machine.** The generator's first attempt sealed the
truth artifacts, the world spec and the truth manifest of version `d674d576…`, at 20:26
UTC, then made its first call to the Frappe site and got a 403 whose body was
Cloudflare's "Just a moment…" page, with `cf-mitigated: challenge` in the headers.
Frappe never saw the request. The sealing order had paid off in the smallest way
possible: truth first, so a truth-only orphan and nothing else. Pinning the cause took
one table with three rows: the GitHub-hosted runner, 403; the AWS application instance,
403 with curl's own user agent and with the httpx one alike; the workstation, 200 with
both. So the discriminator was the network, not the client. Cloud address space is
what the zone's free-plan Bot Fight Mode scores as automated, and it challenges on the
first request. Cloudflare's own documentation, checked that evening, closed the door
on a scoped fix: Bot Fight Mode runs outside the ruleset engine, so no custom rule,
page rule or skip action can exempt a request from it, and it is zone-wide only; the
first tier with an exception is Super Bot Fight Mode on the Pro plan (about $25 a
month, a figure corroborated by secondary sources rather than quoted from the docs),
and whether an Access service token would itself be challenged is stated nowhere
official.

Two things in the platform's own record made this less of a surprise and more of a
lesson. The Terraform file that imported Bot Fight Mode on 2026-08-28 carried a comment
saying it "can challenge a legitimate client (an API caller, a monitor)", and the
platform design held a trigger row for "a paid Cloudflare plan" that fired on exactly
this event. And the observation of 2026-08-30 that machine clients pass, taken as
reassurance at the time, turned out to rest on one client, the UptimeRobot monitor,
which is on Cloudflare's verified-bot list and therefore exempt by design. Every
machine client had passed because the only one that had ever knocked was a verified
bot; no unverified client from a cloud network had ever reached these hostnames
before the first real run. The ruling was taken in the platform stream the same night:
Bot Fight Mode off, the paid-plan trigger re-cut, the hollow monitor observation
corrected in the docs. Arda raised the wider frame himself, a private Cloudflare Tunnel
network between the AWS host and the netcup box with no inbound port on either side;
that closes the M2 path, the agent on the instance talking to Frappe, but not the
generator's, since a GitHub runner sits in neither network and has no fixed address.
It lands as the platform's service-to-service connectivity step at M2 entry, with a
five-minute probe on the service-token question the docs leave open.

> ⚠ REVISED by the M2-entry design session, 2026-09-20 — private connectivity moved to the
> demo milestone's entry or observed abuse; Cloudflare Access with a service token lands
> within M2 instead, since it gives the token-gated property without a tunnel (DESIGN's
> hosting section, the platform's Access ticket).

**The rerun that wrote nothing.** Attempt 2, same run id, went green in 375.6 seconds
(the entry point's `run_seconds` line). The truth objects kept attempt 1's timestamps:
the reassembled bytes were identical and both conditional puts landed in the equal
case, the content-addressed restart proven live on its first try. The checkpoint
numbers the design had deferred to this step came out of the same log: 106 checkpoint
writes, p50 0.295 s and p95 0.623 s per write, 40.0 s in total, 491,265 bytes, 10.7 %
of the run. That is the cost of the one-write crash window kept from step 10, and it is
small enough that the cadence stays at one checkpoint per record. On the sites: 28
employees, 12 leave applications and 18 departments in the Frappe company
`World WD674D5763`, 9 issues in the Jira project of the same name, no documents because
no Tier 1 class plants one (counts read back over the vendor APIs after the run).

**Eighteen mismatches, all in one field.** The validator refused the world (run
34784309718, verdict `worlds/<v>/verdicts/34784309718-1.json`). Every exactness kind
passed, every scenario view passed, six of seven fidelity kinds passed; the seventh,
employee fidelity, listed 18 of 28 employees differing in `skills` and nothing else.
The live rows told the story at once: for employee 002 the sealed skills were `airflow,
go, redis, spark` and Frappe returned `redis, spark, go, airflow`, with row indexes 3,
4, 2, 1. The projector had written the sorted order faithfully and the stored record
still held it; what Frappe leaves unspecified is the order in which a list call over a
child table returns its join. The reader kept whatever order came back, the sealed
employee holds a lexically sorted tuple (the construction's own `tuple(sorted(...))`),
and the fidelity check is field equality, so any reordering was a mismatch. The
pattern fit exactly: all sixteen employees with three or more skills failed, and two of
the five with exactly two did, as the join order happened to fall. The cassette tests
could not have caught this, structurally: a recorded response has one order. The world
was right and the observation boundary was wrong, which is the failure mode an
independent re-read is built to expose, and the design's phrase for it held: validate
the projected systems, not the generator's intermediate objects, so a bug in the
shared reading code cannot produce an evaluation that agrees with a wrong world.

**Where to fix it, and what not to schedule.** The first proposal was to sort at the
reader and to note a `frozenset` as the type-honest eventual form for the field. The
external reviewer, reading the proposal relayed by Arda, pushed back on the second
half and was right: a frozenset gives order-independent equality but every
serialization boundary then has to impose an order again, so it moves the
canonicalization rather than removing it, and for a system that cares about
deterministic bytes and snapshot equality a sorted, duplicate-free tuple is a
legitimate domain carrier, not a compromise. The bug was narrower than the type: the
sealed construction produced the canonical tuple, the vendor stored the rows, and only
the reader let the vendor's order through. Fix the reader boundary, keep the
representation, and record no refactor debt that no consumer has asked for. One more
ruling came with it, on duplicates: if Frappe ever returned the same skill twice for
one employee, sorting must not quietly yield `python, python, sql`, and a
`sorted(set(...))` must not quietly hide it either. Different ordering is normalized;
duplicate membership fails loud, which is the reviewer's own invariant from
2026-09-12, one semantic identity has exactly one vendor representation per place.
Commit `c9823a7` did exactly that: the reader returns the sorted tuple, a skill listed
twice is a `MalformedRecord` naming the employee, and the doctests carry a reversed
example and a duplicated one. No cassette was re-recorded, because no request or
payload changed. Nothing was regenerated and nothing reprojected: same sealed world,
same vendor state, a corrected reader.

**Approved, with the first verdict kept beside it.** The revalidation (run 34785009950,
1 minute 38 seconds) approved the world: every check passed, and the verdict's manifest
digest equals the live world manifest's (`92576aa3…`), which is the serving rule's
condition met for the first time. The refused verdict stays under its own run key
next to the approved one; a refusal is evidence, and the pair is the record of what the
validator caught. That is half of M1's exit, the first world live with its golden set
beside it.

Two things are still claims rather than evidence, and are recorded as such. The
validator role's denial on the real `truth-manifest/<version>.json` key is not yet
demonstrated (the canary proves no bucket-wide read; an IAM policy simulation attempted
this session was inconclusive and is not counted). And the `benchmark` environment
refusing a wrong subject was ruled not worth a demonstration, since the trust policy
was read back on 2026-09-12 and a negative demo would cost a trust edit to prove what
the read-back shows.

Figure: the three-network table (GitHub runner 403, AWS instance 403, workstation 200)
as the one picture of the edge fault. Figure: the two verdicts side by side, 18
employee mismatches in one field, then zero, same world version and same manifest
digest.

## 2026-09-13 — Four times the claim was stronger than the mechanism: how step 12 turned every boundary sentence into a check

*M1 step 12 of the build plan, the generator's entry point and the sealing of a world
into the two buckets: nine design rulings first, one question per exchange with the
external reviewer answering each cold (session 21, 2026-09-13), then six builds each
pushed and reviewed — the object store (`26ae48d`, reviews `73617d2`, `5c47f8f` and the
checksum fix), the key layout and the sealed documents (`48b7584`), the sealing sequence
(`272b033`), the generator's entry point (`4020df7`), the shared wiring and the
validator's entry point (`531a440`), the deploy-time probe (`ff9038d`); the unit suite
went from 1622 to 1673 tests across the step (the suite runs of the session). Feeds: the
M1 report's sealing and boundary section — what "sealed" is enforced by, layer by
layer: the bucket policy, IAM, the import law, the probe on the host — and the
methodology section on external review, whose pattern this step shows four times over:
a claim, a reviewer reading it literally, and a probe or a law rule that makes it true.*

The step's story is not any one of its rulings. It is that four times a sentence in the
design or the code claimed a boundary stronger than the mechanism under it, and four
times the correction was a structural check rather than a stronger sentence. The
external reviewer found all four, reading the text literally and asking what actually
enforced it; the project's answer each time was to make the enforcement something that
runs.

**The seal that was a promise.** The founding design had the generator "run from the
instance under a short-lived role the application process never holds", a role assumed
through STS from the instance profile. On 2026-09-12, while the platform ask for the
buckets and roles was being ruled, the reviewer pointed at what that sentence really
said: an EC2 instance profile is one role, and a role that role may assume is a role
the application process can obtain, because the application runs under the same
profile. The distinction was between processes, not between principals, and the
answer key's secrecy rested on discipline. The ruling that replaced it moved the
privileged jobs off the instance entirely: the generator and the validator are
`workflow_dispatch` jobs under one GitHub environment, `benchmark`, reviewer-gated and
`main`-only, each assuming its own OIDC-trusted role through the web-identity
exchange, and the instance role assumes nothing. The platform stream built and applied
it the same evening (its commit `529c998`), and the trust was proven by a throwaway
workflow run rather than by policy text (run 34719626730 in this repository's
findings): both roles assumed, the generator's two models answering under it, the
validator refused on the truth bucket. One reviewer suggestion was pushed back and
held — two environments to split generator from validator structurally — because the
threat it closes is the project's own committed workflow code under a gate the owner
approves by hand, and the cost would have been every vendor secret duplicated.

**The probe that proved less than it said.** The refusal check that closed the platform
ask made two calls under the validator role: a list of the truth bucket, refused, and a
get of a truth key, refused, "two calls, because a missing key reads as AccessDenied
only while list is also denied". At the step 12 interview the reviewer read that
sentence the other way round, which is the right way: S3 answers a get of an absent
key with AccessDenied precisely when list is denied, so that a caller cannot learn
whether the key exists — whatever the get permission says. The truth bucket had been
empty when the probe ran. The get had proven nothing about GetObject; the list denial
made it ambiguous, not meaningful. The project's own record carried the backwards
reasoning in two places, the session log and the findings, and both received a dated
correction rather than a rewrite. The fix needed a key known to exist: the platform
stream added a canary object at `access-probe/read-denied-canary` (its commit
`57ec6df`), placed outside the create-only prefixes because Terraform's S3 object
resource cannot send the conditional-create header the bucket policy demands there —
which means, for the validator, the canary proves no bucket-wide read and the
`truth-manifest/` denial itself is proven against a real key once a world exists.
For the application the canary is the meaningful get, and it is taken on every deploy:
a probe script runs on the host, in the same SSM command as the deploy, under the real
instance profile — the identity asserted first, a list of the world bucket's `worlds/`
succeeding as the positive control, then the truth list and the canary get both
refused with the `AccessDenied` code specifically, anything else turning the deploy
run red with no rollback, since a broken boundary is the platform's fault and not an
image's. Its first live run was the deploy of its own commit (CI run 34729636594 on
`ff9038d`): identity `assumed-role/leave-agent-instance`, positive control passed,
both refusals with the pinned code.

**Truth first, except in production.** The sealing sequence was written to the order
the interview had ruled: the two truth objects sealed by conditional create before any
vendor call, so that live vendor state never exists without its answer key, while
truth-only orphans are harmless because nothing serves without a manifest. The code
did that, and the unit test proved it — and the reviewer noticed that the function
took a `Prepared` record as an argument, and that in production the only way to
obtain one is the site preparation, which creates the Frappe company and the Jira
project before it returns. The test had manufactured `Prepared` directly and so
observed the first vendor call one stage too late; "before any vendor call" was true
of the composition root's calls and false of the run's. Sealing now owns the call to
prepare, through an outer seam that is the root's interleaved protocol plus that one
call, and the test's fake records the truth bucket's contents inside prepare itself.
Two smaller hardenings landed with it: the sequence reassembles the bundle from the
world it is handed and refuses before any write when they differ, and every
world-content encoding, the documents' included, is computed before the first write,
so the frozen-bytes sentence is literally true — the final manifest being the one
deliberate exception, derived afterwards from those fixed bytes and the version ids
observed on read-back, since a commit record cannot precede the receipts it records
(the closing review's precision).

**The write boundary, porous twice.** The object store was designed as two protocols
in two modules, the writer's gated by the import law to the adapters and the
generator, so that a validator which cannot name the writer cannot call it. The
reviewer's reading of the first commit: the concrete store class implemented both
protocols and lived in a module the validator could import, so the validator could
name the class and call its write methods without ever naming the gated module. The
fix split every backend into a reader class with no write method on it at runtime and
a gated writer subclass, and the law gained the concrete writer modules and a rule
that no package `__init__` may name a gated module. Four commits later the shared
read wiring, built so the generator and the validator construct the same readers from
the same manifest, imported the writer classes at module scope to build the verdict
publisher — and `from leaveimpact.adapters.wiring import S3ObjectWriter` worked. The
reviewer caught that one too. The imports moved inside the publisher function, and
the law gained the rule that makes the fix a property: within the adapters package,
only a gated module may name an object-store writer at module scope, since a
module-scope import makes the class an attribute of any module a shell may import.
Both rules were proven by negative probes, a module that should fail the law made to
fail it. The verdict itself crosses the wiring as one callable that seals exactly one
key computed from the version and the run's identifiers, the writer closed over and
never exposed; the validator package names no writer and chooses no key. The honest
limit is written into the design with it: the law is not a sandbox, it makes an
accidental violation fail CI, and IAM remains the runtime boundary.

Three things ride beside the four arcs. The object store's SDK mapping was observed
before it was written, by a throwaway workflow under the generator role (run
34724172889, commit `e499060`): the 412 on a present key is a `PreconditionFailed`
whatever the bytes, so equality is the store's own read-back; the 403 under a final
prefix arrives as a modelled `AccessDenied`; and, as a side observation, a plain
dispatched workflow's token carries `job_workflow_ref` naming its own file, which
disproved the reviewer's docs-based reading that the claim is reusable-only and put
the per-workflow trust binding on the platform's list as a later option. The store's
fault vocabulary was closed at three classes after the reviewer's own finding that a
broad SDK-error fallback had made local defects look transient: "unreachable" is now
an allowlist of the SDK's transport branches, everything else is misconfiguration, and
the one exception class the SDK raises both for a bad request and for a corrupted
response body is classified at the body read, where its location decides its meaning.
And the documents left PostgreSQL: they seal into the world bucket as canonical
objects, one per document, after the vendor postflight so a refused site leaves
nothing under a prefix no job can delete from, and the application's corpus becomes
a cache the instance fills under the serving rule, with an atomic ready mark so a
half-loaded world is never queryable.

What the M1 report should take from the step is the layering rather than the count.
"Sealed" is enforced by the bucket policy (conditional create on the final prefixes,
no delete grant), by IAM (two OIDC roles, an instance role that assumes nothing), by
the import law (gated writer modules, reader classes without write methods, no
module-scope laundering), and by the probe on the host that turns the application's
refusal into a line in every deploy's log. Each layer exists because a sentence
claiming it was found insufficient by someone reading the sentence literally.

Figure: a four-row table — the claim as first written, the mechanism that was missing,
and what made it structural (OIDC jobs and the trust probe; the canary and the deploy
probe; sealing owning the site preparation; the two law rules with their negative
probes).

## 2026-09-12 — The checker that borrowed the answer key's calendar: how the validator exposed a world-side gap by exposing it in itself first

*M1 step 11 of the build plan, the independent validator: the sealed artifacts redrawn
and decoded (`5c8d765`, reviews `9971acc` and `482d104`), the byte-level file store
(`b5eebf7`, review `fb67e44`), the three checks (`6b225d5`, reviews `8b05e5f` in
`world` and `0aa2345` in the validator), the verdict and the composition (`69a0b71`,
review `8823526`), all 2026-09-12; the unit suite went from 1546 to 1599 tests across
the step, the composition tests driving the real projectors into in-memory ports and
then judging what landed (the `just check` runs of the session). Feeds: the M1
report's validation section — what "approved" claims, which layer proves what, and
the chain from live systems to sealed truth that the validator completes without ever
reading a key — and the M2 harness constraint the step produced: the harness observes
everything the reads return, dated to the run's day.*

The validator is the layer built to give independent evidence: it re-reads the four
live systems and proves they hold exactly the declared world, so that a bug shared
between generation and projection cannot yield an evaluation that agrees with a wrong
world. The step's story is that the first cut of that layer was itself the shared bug.
It passed for the wrong reason, the external reviewer saw why, and the correction ran
one layer down into the world generator, where it belonged all along.

**Four rulings, and the file that could not feed its reader.** Like the projection
step, this one was designed before it was coded, one ruling per exchange with the
external reviewer answering each cold. The first exchange did not get to its question.
The validator runs under a role that reads one prefix of the truth bucket, the sealed
world spec, and never the truth manifest with its answer keys; but the world spec as
sealed at step 8 held the organisation, the plan, the slices and the provenance, and
nothing of what each scenario had planted. The plantings and each scenario's stable
interval lived inside the truth manifest's construction records. Step 10's projectors
had never noticed, because they read the assembled world in memory, not the bytes. A
validator reading the spec from bytes could not know what was supposed to be there.
Three ways out were on the table: extend the spec, let the validator regenerate the
world from its provenance and check the digests, or widen the role to both prefixes.
Regeneration would have put the truth in the validator's memory and made "never reads
the truth" a discipline instead of a boundary, and would have tied the validator's
verdict to interpreter drift that has nothing to do with the live systems; the wider
role breaks the access ruling. The spec was extended, with one home per fact: the
plantings with their observable-from dates and the stable intervals moved into the
world spec, the truth manifest narrowed to keys and authored facts, the serialized key
deliberately narrower than the in-memory construction record, the generator version
bumped to 4 and the reference world's snapshot re-cut (`5c8d765`). The reviewer's
framing of the two files is the one the code now documents: the world spec is what
was supposed to be projected, the truth manifest is what those plantings are expected
to imply.

The remaining rulings held with two push-backs. The validator's claim decomposed into
three layers: identity exactness per closed enumeration, missing and foreign both
named; record fidelity, each record read back equal to its planting; and the derived
view of a run, the facts a scenario's reads yield compared with the facts the
plantings yield. The reviewer proposed "projection equivalence" for the second layer,
equality after vendor normalization, and I pushed back with the projector's own
docstring: the adapters' round trips are proven exact for every generator-controlled
field, so naming a looser equivalence would admit a looseness the record says does not
exist; plain equality stayed. The reviewer also wanted exactness for calendar events
over the whole of each world-exclusive calendar rather than the world's time horizon;
the read port offers events by window only, on purpose, since the investigator never
enumerates a calendar, so the scope became the horizon, one bounding interval over
every scenario window so a foreign event in a gap between windows fails rather than
hides, and debris outside every window went to the fix log as the composition root's
hygiene concern. The decoders became a codec over one value: `PlantedWorldSpec` is
exactly the file's content, a pure function projects the assembled world onto it, the
encoder takes it, and three claims are proven separately (the projection equals the
expected value, decoding an encoding yields the value, encoding a decoding of the
sealed bytes yields the bytes). The verdict became its own artifact, never a stage on
the manifest, approved exactly when every check passed, carrying the validator's
version and the SHA-256 of the manifest bytes it judged. That last field was my
addition to the reviewer's shape, for a reason worth keeping: the world version and
the artifact digests identify the world, not the projection, and a re-projection of
the same world onto other sites changes every receipt and the calendar map while
leaving all of those digests untouched, so only the manifest's own digest ties a
verdict to what it judged. The file store the manifest used moved out of the
generator into the adapters package as a primitive over bytes and a path, knowing no
record type, so the generator's manifest and the validator's verdict share it without
either importing the other.

**The checker that borrowed the calendar.** The third part landed the checks
(`6b225d5`) and the reviewer's finding on it was the step's turn. A live record knows
nothing of when the synthetic world "made it observable"; the entity types keep vendor
timestamps out by design. My view layer therefore looked up each live record's
planting date in the sealed spec by identity, stamped its facts with that date, and
compared the result at two instants inside the stable interval with the truth's dated
view. It passed. The reviewer's point was that the investigator will never possess
those dates. The runtime rule already written in the derivation module says what a
live harness does: it stamps every returned record with the run's day. Nothing the
investigator reads is hidden by date. Leaves and events are narrowed by window, so
other slices' plantings stay out of a run, but the work-item read enumerates the whole
Jira project, so every scenario's tickets are visible in every run. The validator had
produced a cleaner historical view than the runtime can obtain, borrowing
benchmark-private chronology to do it, and so would have hidden exactly the mismatch
it exists to expose.

Before ruling, I probed the reference world for the two facts that decided the size
of the problem. No planting in any of the ten scenarios is observable only after its
scenario's `now`. And when every planted fact of every scenario is made visible at
each scenario's today, the way the live systems actually present the world, not one
verdict changes (a scratch probe over seed 7, 2026-09-12, before the world commit
`8b05e5f`). The reviewer had opened a larger question, whether the runtime needed some
mechanism to make the synthetic observability real, and the probe closed it: the
runtime rule exists and is fine, the validator had simply used the wrong rule. What
the probe also showed is the gap one layer down. The pre-seal verification proved each
key under the truth's dated view, which hides later plantings; the live systems hide
nothing; so the keys were realizable only if they also held under the all-visible
view. They did, but nothing asserted it, and a future scenario class whose key depended
on a future planting staying hidden would have sealed cleanly and failed live.

Three rulings followed, adopted as written with one refinement each from the
reviewer. The live side of the validator uses only the runtime rule; planting dates
leave the validator entirely, and the helper that had made them available went with
them so nothing tempts a later hand. The expected side is the record set the runtime
ports would return, stated once in a new module of the world package: the
organisation whole, every scenario's work items, the leaves and events overlapping the
scenario's window under the ports' own overlap rules, every fact dated to the run day.
The whole-world re-verification at assembly now runs every stable day of every
scenario twice, under the dated truth and under that runtime view, and refuses a world
whose key holds only while a later or foreign planting stays hidden. The test that
pins it is the case the dated view cannot see: scenario 2 plants a leave for scenario
1's viable cover over scenario 1's leave, dated after scenario 1's window; the dated
view stays clean on every stable day, a run's windowed read returns the leave, the
cover is away, and the finding names the cover under the runtime view (`8b05e5f`).
The reviewer's refinement on this ruling was the wording: not "every planted fact
visible", since leaves and events are still window-filtered at the wire, but "the
complete record set the runtime ports would return, with no benchmark-only
observable-from filtering". The refinement on the validator's side was a condition:
the two-instant check could go only if the read requests themselves do not move with
the candidate `now`. They do not; the window is a field of the scenario spec, a run
input fixed per scenario, and the run context carries `now` and no window. So the
two-instant check that had stood in the design since the scenario framework was
dropped, with its reason recorded where someone might otherwise restore it: under the
runtime rule a run's view does not change inside the stable interval, and a second
read proves nothing the first did not (`0aa2345`). The interval is the evaluator's, a
run anywhere in it grading against one key.

The division that came out is the one the report should state, because it is cleaner
than what either of us had at the start of the step: the generator proves the world is
realizable through the runtime rule, the validator proves the realized systems match
that realizable world, and the evaluator grades with the stable interval and the key.
The validator's chain is complete for the structured tier: live systems realize the
sealed spec, the sealed spec implies the sealed truth, and the validator never reads a
key and never uses a planting date to build the live view — it reads the plantings'
dates in the spec, since the spec serializes them, and constructs the runtime view
without them (the wording sharpened at the step 12 closing review). For the
prose-carried facts of the later tiers, the ones only
a runbook or a comment can plant, the proof runs through the materializer's
containment gates and the corpus adapter's read fidelity, not through this validator;
that is a Tier 2 obligation, stated in the package docstring, not an unfinished part
of this step.

**The smaller adoptions, one line each.** The world decoders leaked a `KeyError` on an
unknown zone name and silently normalized a timestamp whose offset disagreed with its
named zone; the fix became one instant rule in core, semantic half and lexical half,
the second added when the reviewer showed that `fromisoformat` accepts spellings the
encoder never writes, so the round-trip claim now holds for every value a sealed
codec accepts, and the vendor adapters are deliberately outside it because normalizing
a vendor's spelling is their job (`9971acc`, `482d104`). The file store's rename was
atomic but not durable across a host crash without a sync of the parent directory;
the reviewer filed it as a P2 against the receipt contract, I answered with the ruled
contract, restartability after the faults the transport reports and a loud coverage
refusal for the window between a write and its checkpoint, and the reviewer
downgraded their own severity while tightening my phrasing (a rollback can land behind
more than one external write); the barrier was taken anyway on the POSIX production
path, the two guarantees stated apart, and the test of it ran inside a Linux container
since the development platform cannot sync a directory through `os.open` (`fb67e44`).
The corpus port offers documents by id and by search and no enumeration, so the
foreign direction of document exactness needed an inspection outside the port, the
same shape as Frappe's held employee numbers and Jira's held markers (`69a0b71`). And
the closing review found a hole in the integrity chain I had drawn: the scenario specs
are authenticated by the world spec's digest, so the manifest's own copy of that
digest was never compared, and a manifest recording a false one was approved with the
false digest carried into the verdict's provenance; reproduced by a scratch script
against the pushed commit before the fix, cross-checked now, and the same commit made
the "each enumeration read once" claim true in the code rather than only in the
docstring, and paid the step's own documentation debt in DESIGN instead of deferring it
(`8823526`).

Figure: two views of one world side by side, dated against runtime, for scenario 1's
stable days: the same records, the late-planted leave for the cover absent from the
dated column and present in the runtime column, with the cover's verdict flipping
beneath it. The records and the verdicts come from the realizability test in the
runtime-view suite.

## 2026-09-12 — The receipt nobody could read back: how a manifest became a checkpoint, and why "projected" stopped meaning "approved"

*M1 step 10 of the build plan, the projection of the synthetic world into the four
systems: the world manifest (`1bbf44a`, review `c27e25a`), the projectors (`81ba24e`,
reviews `d6452a6` and `871ebc0`), the site inspections (`73a0546`) and the composition
root (`925feed`, reviews `985c4ec` and `a9d8718`), all 2026-09-12; the unit suite went
from 1509 to 1546 tests across the step, every projector and root test against
in-memory ports, no sandbox touched (the `just check` runs of the session). Feeds: the
M1 report's projection and restart-safety section, and its evaluation-integrity story —
what the manifest's "projected" stage does and does not claim, and which layer proves
what.*

Step 10 was designed before it was coded, in an interview with an external reviewer
who saw each question cold: one ruling per exchange, the reviewer's feedback answered
point by point, then Arda's call. Seven rulings came out of that, and the interesting
part of the step is that two of them did not survive contact with the code. The
record below keeps both the rulings and the reversals, because the reversals are the
story.

**Seven rulings, most of which held.** The world manifest — the projection's receipt:
which Frappe company, which Jira project and field ids, which Google calendar belongs
to whom, and one locator per entity the projection wrote — went to the adapters
package, the lowest rank that can type adapter configuration and world provenance
together, so the generator writes it and the validator and the application decode it
without either importing the generator. The residual window in the Jira identity
marker (an issue can exist before its planted id lands, and a restart against a lagging
search index could then create a second) was closed not by a checkpoint file but by a
preparation guard that reads every issue in the project, marker filter off, and refuses
an unmarked issue or a marker held twice, naming the keys for a human to delete; it
runs before projection, where index lag can blind it, and again after, where the run's
own duration has let the index catch up. The calendar map is persisted after each
obtained calendar id, because Google mints those ids and the restricted scope the app
runs under cannot list them back, so an id whose response is lost is an empty orphan
only a human sees; per-calendar persistence bounds that at one orphan per interrupted
attempt. The projectors got a per-system restart strategy rather than one algorithm:
Frappe, Jira and the corpus find by domain id, verify the found record equals the
planted one, and add what is missing; the calendar inserts directly, since its vendor
event id is derived from the domain id and the insert is itself the ensure — a missing
copy created, an existing one verified by read-back, a half-written event completed —
whereas finding one event by id would cost one read per calendar and turn a
recoverable partial write into an error. An existing record that differs became a
third port fault, `IdentityConflict`, on the reviewer's point that the existing
"malformed" fault means "cannot translate" and this record translated fine: the
identity points at other state, and nothing adopts or overwrites it. A Frappe site
inspection looks past the company for a world employee number another company on the
site already holds, since employee names are unique per site and the ordinary reader
is company-scoped by design. And the names a world takes in the vendors derive from its
version — a Jira project key of `W` and nine hex digits, a company named by the same
key — with the project's description carrying the full version so a found project can
be verified by a read before anything is written into it.

**The receipt nobody could read back.** The projectors commit (`81ba24e`) collected
each system's locators in a local dictionary and returned them when the batch
finished. The reviewer's finding was exact: a reader returns a domain entity and never
a vendor locator, on purpose, so that vendor ids stay inside the adapters. Jira's issue
key therefore exists in exactly one place, the writer's return value. If the source
died after the third issue, the batch raised, the three locators were gone, and a
restart would find the three issues, correctly not re-create them, and have no way to
learn their keys. The same held for Frappe's generated leave names. The fix I proposed
before the commit, when the shape first showed, was a third manifest stage —
"projecting", with receipts growing under it — to preserve an invariant the first
review round had introduced: that a manifest still preparing carries no receipts. The
reviewer's fix was better and I said so: keep two stages, let receipts grow under
"preparing", and give the projector a sink it calls with each locator before the next
external write, so the root can checkpoint it durably. A third stage would have
encoded internal workflow progress that nothing consumes, since a restart re-runs
preparation anyway. Then the reviewer withdrew their own earlier invariant as too
strong, in writing. The regression test that landed with the fix (`d6452a6`) does what
the review asked: two writes land and reach the checkpoint, the source dies before the
third entity is touched, the checkpoint survives into the rerun, the found two are not
re-reported, and the union covers every planted id.

The guarantee that came out is narrower than "crash-safe receipts", and the narrowing
was the reviewer's second contribution on the same thread. What the sink proves is that
a later projection failure cannot lose the receipt of an earlier completed write. What
it cannot prove is survival of a process death, or a failed checkpoint, in the window
between an external write returning and its locator reaching the file — there is no
transaction spanning Jira and a local file, and no callback placement closes that. The
project's recovery contract is restartability after the faults the transport reports,
not after a kill at any instruction, and the docstring says exactly that. What I added
to the record: the window is loud, never silent. A restart finds the record, receipts
nothing for it, and the post-projection coverage check refuses to promote the
manifest; the operator's remedy is the same as for any debris, delete the marked record
and rerun. The reviewer's list of unrecoverable locators named Jira issue keys and
Frappe leave names; reading the writers showed a third, Jira component ids, which the
docstring now lists beside them (`871ebc0`).

**What the root proves, and what it must not pretend to.** The composition root
(`925feed`) drives the sequence the rulings fixed: resume from the stored manifest or
start fresh, one calendar per employee with a save after each new id, the site
inspections as a preflight allowing a subset of the world, the projectors with every
receipt checkpointed, the inspections again demanding the exact set, a coverage proof,
then the promotion to "projected". Its first review (`985c4ec`) found four things I
had left open, all reproduced before triage and all adopted: the remembered calendar
map was never scope-checked, so a checkpoint carrying a stranger's calendar would have
widened the application's read surface, since the calendar adapter reads every
configured calendar; a resumed checkpoint's header — digests, generator version,
organisation parameters — was trusted rather than compared against the fresh values
the root held; the coverage proof allowed foreign receipts; and the Frappe inspection
silently skipped a company employee without a number. The resume now builds the
fresh manifest every time and takes from the checkpoint only what grew in it, the
calendar map and the receipts, after every header field is compared.

The second review round asked for more, and this is where I pushed back. The
reviewer's finding was that the postflight proves exactness only for employees and
Jira issues, while the readers also enumerate leaves, components, events and
documents: a foreign record of any of those kinds, carrying a valid planted-style id,
would survive promotion and enter the investigator's fact surface, where the
closed-world enumeration contract grades absence as known false. True, and the root's
docstring had claimed "this world and nothing outside it". My answer was that the
root's inspections exist for one class of failure — its own interrupted writes leaving
state its find-or-create cannot see, which only Jira issues can do, since every other
kind lands with its identity in one write — plus the integrity of its own checkpoint
and the namespaces projection depends on. A foreign leave is not projection debris; it
is contamination from outside the generator, improbable under per-world naming, and
the independent proof that the live systems hold exactly the declared world is the
validator's, the next step, which already re-reads every enumerable kind. Proving full
exactness in the root and again in the validator would be the same proof twice, in the
layer not built to give independent evidence. The reviewer agreed, called their own
earlier recommendation a conflation of two guarantees, and tightened two things I
would have left loose: the manifest's "projected" stage now means the projection
lifecycle completed with the generator's own invariants proven, not that the world was
independently accepted — only a validator-approved world is served — and the step-11
claim is written explicitly as set equality of observed and expected identities per
closed enumeration, missing and foreign both refused, over the named surfaces
(`a9d8718`; the claim is in the step-11 plan, not yet code —
[PRELIMINARY — the validator does not exist yet]). The one immediate change from that
round, a foreign receipt refused on load before any vendor call, landed in the same
commit.

> ⚠ REVISED by the step 11 entry above (2026-09-12) — the exactness claim is now code,
> scoped by the world horizon for the windowed kinds and by an inspection outside the
> port for corpus documents.

The division that came out of the argument reads, in the reviewer's words, cleaner
than either of us had it at the start: the generator proves that its projection
procedure converged safely and that its checkpoints are internally consistent; the
validator proves that the realized world equals the declared one. Those are different
questions, and the manifest's stage answers only the first.

Figure: the checkpoint trail of one fresh run as a timeline — one save at the start,
one per calendar, one per receipt, one promotion — against the trail of a run cut off
after two work-item writes and resumed, showing where the second run's saves begin.
The numbers come straight from the root's tests, which count the saves.

## 2026-09-12 — Four leaks and a rollback: what the adapter tranche learned about trusting a gate, a vendor, and a transaction

*M1 step 9 of the build plan, the four adapters that carry the synthetic world into
Frappe HR, Jira, Google Calendar and the project's own PostgreSQL corpus (the calendar
in `860c3f7`, the corpus in `2ecdcb8`, the end-of-adapter review fixes in `e9f04e6` and
`3dc390a`, all 2026-09-12; 1495 unit tests and ten integration tests at the seal).
Feeds: the M1 report's adapters and grounding section — translate, never launder, and
what evidence discipline costs at the wire — its evaluation-design section, where the
cassette gate stands as a measurement-integrity mechanism, and the M1 post.*

The adapters are the part of the system a reader might skim: vendor JSON in, domain
entities out, and a retry rule. What the tranche actually produced is three lessons
about where trust breaks, and each of them arrived as a surprise rather than a plan.

**The gate that was right, and then not enough.** The adapter integration tests run
against recorded HTTP cassettes, and the cassettes are committed, so every recording
against a real sandbox is a chance to commit a secret or a hostname. The day before the
calendar work, the scrub had been made structural for a reason the CI pipeline forced:
CI has no sandbox credentials, so a check that "the real host is absent" would pass
there vacuously. The gate instead demands that every request host be a placeholder or
a public API host, that every listed header be redacted, and that every secret-shaped
JSON key read as the placeholder. Its record on the first two adapters was exact: the
Frappe recording leaked the site in a request `Host` header after the URI was clean,
and the Jira recording leaked it in a `Location` header on a create. Both caught on
the gate's first real run, both fixed by widening the scrub.

The calendar recording then produced the case the gate could not see. Google's
response to creating a secondary calendar carries the owning account's e-mail address
under a key called `dataOwner`, and every event carries it again under `creator.email`.
Neither key was on the list. The identity net that should have caught the address by
value was blind for a reason nobody had checked: google-auth writes the account into
its token file as an empty string, so the net had nothing to look for. The leak was
found by a manual scan of the cassette for the mail domain, not by the test. The
repair is the point: both keys joined the list, and the gate gained a second net that
does not depend on any list at all, a signature for a consumer mail address anywhere
in the file, beside the existing signatures for token shapes. The gate was made to
fail on the leaked cassette before the recording was redone, so the new net is known
to bite. Minutes later the same cassette tripped the repository's commit-time secret
scanner on `nextSyncToken`, Google's opaque sync cursor, which the adapter never
sends; it was redacted by key rather than allowlisted, because an allowlist on a
cassette would also hide a real token. The lesson generalises past this project: a
key list is necessary and never sufficient, since a vendor will put a secret under a
key nobody listed, and a gate needs a signature net beside the list.

**A ruling deviated, with the reviewer's concurrence.** The design interview two days
earlier had named Google's discovery client for the calendar. Reading the sealed
Frappe and Jira adapters made the cost visible: the client ships no types, so under
strict type checking every call would hide behind an `Any`; it brings a second HTTP
stack with its own retry loop that sleeps on the wall clock outside the injected
sleep, so a recorded rate limit would pause a cassette replay; and it would need a
third wire-test style. The six calendar calls are plain paths under one base URL. So
the calendar rides the shared transport, and google-auth keeps only the credential and
its refresh. The external reviewer approved the deviation and refined three things,
each adopted: the domain event id must be encoded into Google's alphabet (it was the
plan, a digest, now doctested and later corrected to say what it always was, a SHA-1
hex digest that happens to sit inside that alphabet); a 409 on an insert with a
supplied id must mean "read the copy back and compare", never "written", so that an
id collision or a cancelled event Google still remembers is a loud error; and every
read should ask for one time zone so identical copies on calendars in different zones
arrive in one form. The first recording proved the two claims the design rested on:
Google answered 409 when the review meeting was added a second time and both copies
verified equal, and the restricted scope the app runs under is allowed to delete the
calendars it created.

The representation that the recording exercised is one Google event per attendee's
calendar, so each synthetic person's calendar shows their own busy time the way a
free/busy query expects, and the reader makes one domain event of the copies. It
treats any inconsistency as malformed rather than choosing a copy: copies that
disagree, a copy on a non-attendee's calendar, an event present on fewer calendars
than it names attendees. The reviewer's review of that commit found the one case it
still laundered: two Google events on one calendar carrying the same planted id and
identical fields collapsed into one. It was reproduced in the pure grouping function
and closed the same day, and the reviewer's proposed invariant was adopted as a rule
for all three vendor adapters at the end-of-tranche review: one semantic identity has
exactly one vendor representation per place, and duplicates are malformed, never
deduplicated. Frappe's enumerations, which had enforced exactly-one on a select but
not on a listing, gained the same check.

**The bug the projector would have met first.** The end-of-adapter review, run over
the corpus commit with the deferred items from every earlier round, found the
tranche's one genuine defect. The corpus adapter opened a default psycopg connection.
On such a connection a plain `SELECT` opens a transaction that the driver never
closes; a later explicit transaction block, entered while that transaction is open,
creates only a savepoint; releasing the savepoint commits nothing; and closing the
connection rolls the whole thing back. The projector's own sequence is exactly that
shape, read by id, miss, add. Reproduced live on the development database before any
fix: the same adapter read its own document back, its connection reported "in
transaction" just before close, and a fresh adapter opened afterwards saw nothing
(reproduced on the development database before any fix was written). Every
projected document would have been lost, silently, on the first real run. The
integration tests had passed because each of them wrote before it read, which is the
convenient order and not the caller's. The fix is an autocommit connection with
explicit transaction blocks kept around the document write and the schema bootstrap,
and a regression test that replays the caller's order: a missed read, a write, a
close, a fresh adapter that finds the document. The test was confirmed to fail on the
old adapter and pass on the new (`e9f04e6`; reviewer approved). The transferable
lesson is about test order: a lifecycle claim has to be reproduced in the sequence
the real caller uses, not the one that is easy to write.

**A design sentence that the code had quietly outgrown.** The reviewer also raised a
cross-cutting mismatch: the design document said every scenario-owned entity carries
the scenario id in each system, as a Jira label, a calendar property and a Frappe
custom field, and no adapter plants one, nor do the writer ports carry one. The
reviewer read it as an implementation drifting from its design. The diagnosis was
refined in discussion: the scenario-framework step, days earlier, had already placed
ownership in the sealed world specification's table of owned entities, so the design
sentence was the stale party, not the code. The ruling went to that reading on
2026-09-12, and the two design sentences were rewritten in `3dc390a`: a scenario's
slice is enumerable from the specification, not from the vendors, and the projector's
promise that a rerun adds nothing is now qualified by the one case it cannot keep, a
secondary calendar whose id Google chooses and whose creation response was lost, which
the restricted scope cannot rediscover. That qualification is a design check the
projector step inherits: how the composition root persists the calendar map is what
keeps the orphan case narrow.

A field note from the same day, because it cost an hour of confusion: the integration
recipe took 92 seconds for six corpus tests, and the cause was `localhost` resolving
to IPv6 first on the development machine while the database container publishes on
IPv4 only, so every connection waited out a ten-second timeout before falling back.
Pointing the recipe at the loopback address brought the whole integration level to
about five seconds (timed connects, 2026-09-12: 10.07 s by name, 0.04 s by address).

Figure: a small table of the four cassette leaks across the tranche — where each
arrived (request `Host` header, response `Location` header, `dataOwner` and
`creator.email` keys, `nextSyncToken`), which net caught it (the structural gate, the
structural gate, a manual scan, the commit-time scanner), and what the gate gained in
response — would carry the "necessary, never sufficient" point in one glance.

*M1 step 6 of the build plan, the organization generator: the closed vocabulary with
its version and digest, then seeded people, teams, skills, managers, components
(commits `9050eb8`, `5139149` on 2026-09-11, two review follow-ups; 465 tests at the
seal). Feeds: the M1 report's generator section — what the organization guarantees and
what it deliberately leaves to the scenarios — and its evaluation-design section, on
how the golden set's classes are plantable at all; the M1 post.*

The plan for the organization generator carried, in its first draft, an invariant that
read as plainly sensible: every skill in the vocabulary has at least two holders, so
that finding cover is a search rather than a lookup. It was proposed in the opening
plan of the session, before any code, as one of four structural invariants the org
would enforce. It died within the hour, and the way it died is the story worth
keeping.

The external review, agreeing with the shape of the org record, added an aside that
the retained skill vocabulary "permits unused-but-valid skills later". That remark
prompted a check of the proposed invariant against the golden set as the design
document defines it (the "first golden set" section of DESIGN). Tier 3 contains three
`uncovered` scenarios, each needing a complete world in which nobody qualifies for the
need — a skill with no holder at all, or none available. It also contains three
`missing_information` scenarios, each wanting the only plausible candidate to have no
skills record whatsoever, not an empty one. And the golden-set ruling of two days
earlier says that org-level facts are static across the whole world: a scenario
produces its class by choosing the leaver and the need so that the static facts yield
the intended outcome, never by editing shared state for one slice. Put together, a
generator that guaranteed two holders for every skill would have made six of the
thirty scenarios impossible to plant. The invariant did not merely constrain the
world; it deleted the hardest part of the evaluation.

The turn that followed is the design the generator now implements. The organization
guarantees *shapes* — the raw material scenarios select from — and never coverage. By
construction there is at least one skill nobody holds, one skill exactly one person
holds, one skill held by at least a third of the people who have a record, exactly the
parameterized number of people whose skills record is absent, and every component
drawn across at least two teams so that "same team" and "relevant component" can
disagree. Coverage-as-a-search, the property the withdrawn invariant was reaching for,
became the scenario's business: the class invariant that runs at construction and
fails generation by name when the intended outcome does not emerge. The external
review's follow-up sharpened the form of these guarantees, asking that they stay
existence claims ("at least one zero-holder skill") rather than a locked histogram, so
the scenario step keeps room to select.

Two further rulings came out of looking at the generated thing rather than its
tests. A readable print of the seed-7 organization under default parameters showed
one team of ten and another of three out of twenty-eight people — independent random
placement of the remaining seats after one lead and one member per team — and a
three-person team leaves a scenario nothing to search inside it. Members are now dealt
round-robin with at most two moves between teams, so sizes differ by a few. The same
print showed one contractor where a fifteen-percent share over twenty-three non-leads
had been expected to give about three, and a different seed could have given none,
which would leave every contractor-scoped policy clause without scope anywhere in the
world. The generator now guarantees one contractor whenever the share is above zero,
the same reasoning as the skill anchors: a prerequisite a scenario class depends on is
constructed, not left to probability. (Both figures from the seed-7 sample printed
before the second commit; the team sizes after the change were 6, 6, 6, 5, 5.)

The transferable lesson is uncomfortable because the withdrawn invariant sounded so
reasonable. A generator guarantee that reads as obviously good can quietly remove the
test cases the evaluation exists for, and the only defence is mechanical: every
invariant the world enforces gets checked against the list of classes the golden set
must plant, before it is built. The check took minutes; the invariant would have cost
the adversarial tier.

## 2026-09-11 — Provenance is not dependence: the sources a conclusion needs are found by taking them away

*M1 step 7 of the build plan, the scenario framework: constructive selection, modifiers
as declarative planters, the rules as verifier, the required-sources field of the key
(commits `3f10da4`, `1b0f0b9` on 2026-09-11; regression tests in
`tests/unit/test_world_construction.py`). Feeds: the M1 report's evaluation-design
section — what a scenario key's required sources mean and how the tool-failure
condition is defined — and the section on keeping the rules a verifier rather than an
author of truth.*

A scenario key records the systems a complete investigation must have read, so that a
run which never touched one of them can be graded as incomplete rather than merely
wrong. The framework's first version derived that list the obvious way: collect the
sources of every evidence fact the viability rule cited while assessing the
candidates, add the sources of the facts about the impact's artifact and the leave
under investigation, and the union is what the investigation needed. It passed its
tests and it was wrong in a way the external review put in one example.

A candidate who does not hold Kafka is non-viable for a Kafka requirement. That
conclusion cites no evidence fact at all — the evidence is the absence — yet under
the closed-world rule it depends on every source in the skill predicate's declared
domain having answered: the HR record and the tracker both, since a skill may be
evidenced in a ticket comment. With the tracker unreachable the same question stops
being a known negative and becomes an unknown, inaccessible. So the tracker was
required, and a list built from positive evidence would never contain it. Provenance
answers "which record established this?"; dependence asks "which sources had to be
observable for this conclusion to stand?"; under closed-world reasoning the two are
not the same set.

Two repairs were considered and rejected. The domain's assessment record could be
extended to report every predicate it consulted, positive or negative — a change in
`core` for a consumer in `world`, and one more field to keep faithful as the rule
grows. Or the framework could list the rule's reading order itself — which predicates
viability touches for each criterion — which is a copy of the rule's internals kept in
step by hand, exactly the coupling the constructive-selection ruling was written to
avoid. The definition the reviewer had used to state the bug was itself the cheapest
implementation: a source is required if taking it away changes anything the rules
conclude. The framework now computes the normal conclusions, re-runs every assessment
and outcome with each source in turn made unreachable, and marks a source required
when any conclusion moves. It knows nothing about what the rules read, it uses the run
condition the evaluator already defines for tool-failure runs, and it is by
construction the tool-failure metric's own notion of dependence. The regression test
is the reviewer's example verbatim: a release meeting under a Kafka clause, a
candidate lacking Kafka, no tracker fact about the meeting — and the tracker comes out
required through the negative alone.

The second round found the comparison one level too coarse. The signature that decided
whether "anything moved" carried each candidate's verdict and reason classes, and an
unknown carries no reason class; so an unknown because the record is blank and an
unknown because a source could not answer compared equal, and a source whose loss only
changed *why* a candidate was unknown looked unrequired. The fix carries each
assessment's unresolved questions — subject, predicate and the derived reason — into
the signature. The honest part of this round: the regression the reviewer proposed
(a blank-record candidate under the same clause, assert the tracker is required)
passed before the fix as well as after. Over the whole organization, every other
candidate with a normal skills record already flipped from known-negative to
unknown-inaccessible when the tracker went away, so the tracker was required through
them regardless of the blank candidate. The signature was still wrong as a definition,
and would have surfaced with a small explicit universe or a predicate nobody holds
negatively; it was fixed and recorded as a correction of the definition, not an
observed miss, and the sharper test pins the counterfactual through the domain's own
assessment call — the same candidate, unresolved for absence with the tracker
reachable and for inaccessibility without it.

The reviewer, checking the finished comparison for overreach, listed the cases it
handles the way one would want: a source whose facts another source duplicates is not
individually required; a source that flips a verdict or an outcome is; a source that
only changes why something is unknown now is; a source that removes redundant evidence
without moving a conclusion is ignored. That list is the sentence for the report:
required sources are counterfactual, not archival.

Figure: a small table for one scenario — rows the candidates and the outcome, columns
the normal run and each single-source outage — with the cells that move highlighted;
the tracker column moving for a candidate who cited no tracker fact is the picture.

## 2026-09-10 — A query is not a fact: the port that let the tracker answer "owned by" would have graded a missing record as a known negative

*M1 step 5 of the build plan, the seam between the domain and the four systems: the
read and write ports, the observed-entity wrapper, the leave as a run input, the fault
contract, and the derivation that turns a record into facts (commits `89c54a9`,
`820d1b6`, with review follow-ups `acae3bb`, `d940436`, `c072818`; 246 tests including
doctests at the seal). Feeds: the M1 report's architecture section — where the port
boundary sits and why read-only is a property of the import graph — and its
evaluation-design section — how the boundary protects closed-world grading; the M1
post.*

The step opened, as the previous ones had, with an interview of one question per
exchange, each answer sent past an external low-context reviewer before it was ruled.
Four rulings came out of it. The first decided what crosses a port: observed domain
entities — an employee, a work item, an event, wrapped with the source it was read
from — and never facts. The alternative, adapters returning facts directly, would have
put the meaning of every field into four vendor modules where it could drift; keeping
it in the domain means an adapter translates shape and identity and nothing else, and
the gap logic that closure depends on lives beside closure. Documents are the
deliberate exception, and the reviewer sharpened why: a document section is an id and
text, so what a clause requires cannot be derived from it without parsing prose, and
the design already said truth stays the structured brief. The requirement fact
therefore enters the fact base from the world's brief, the investigator establishes
which clause applies and cites it without transcribing its content, and the plan check
resolves the citation to the truth's requirement. No extraction seam exists anywhere,
in the world milestone or the investigator's, which is a smaller architecture than the
one first sketched.

The second ruling split reading from writing into two modules, and here the reviewer
improved the proposal. The first version would have scanned the investigator's code
for writer class names; the reviewer's version denies the write module by its import
path, which the import-law test already knows how to read. Working that through
exposed the one evasion a module rule alone would miss: a re-export of a writer from
the domain package's own `__init__` would have laundered it behind an import the law
reads as harmless. So the rule became an allowlist over every module that names the
write module — only the adapters that implement it and the generator that projects
through it — and the test proved itself against a planted re-export before the commit.
The writers have a single production consumer, which the project's own rule about
ports would normally forbid; they are a port anyway, for the least-privilege type and
for the in-memory implementation both sides share under the tests, and the design
says so rather than pretending to hexagonal symmetry.

The third ruling put the leave under investigation on the run context as an id and
nothing more, in the reviewer's phrasing: run inputs identify what to investigate,
ports establish the facts about it. The leave record, its employee and its span are
read through the people port, so they are evidence the run established and a scenario
can contradict, never a truth the harness told it. The consequence for a run whose HR
system is unreachable is that it has no interval at all — not merely an unknown leave
fact but no way to scope which tickets and meetings matter — and the rule is that such
a run continues degraded and surfaces the unknowns rather than inventing the span; how
that grades is the evaluator's design. The fourth ruling kept three fault outcomes
apart because closure treats them differently: a record that is not there is a plain
`None` or an empty tuple, a source that cannot answer after the adapter's retries raises
one typed exception, a record the adapter cannot translate raises another, and the two
share no base so a single `except` cannot fold a defect into a legitimate unknown. The
reviewer's triad is the sentence the report can carry — missing data is evidence,
unavailable infrastructure is an epistemic limit, malformed data is a defect — and
their small catch on the third case was real: a malformed record may have no domain
identity yet, so it is reported with an opaque source-side locator, not an entity
reference the adapter could not have built.

The moment worth telling came at the review of the first commit. The work reader had
been given two convenience queries, "work items owned by this person" and "work items
in this component", written without a ruling because they read like ordinary tracker
calls. The reviewer noticed that both filter on exactly the relationships the domain
is supposed to derive as facts — ownership and component are registered predicates —
while the people and calendar readers already followed the opposite principle: return
the universe, filter by a fact you derived. The asymmetry was more than aesthetic. The
predicate registry declares each fact's evidence domain closed, and closure turns
"source reachable, zero facts" into a known negative. That declaration is honest only
when the run actually read every record the source holds. A vendor-side filter can
drop a record before the adapter ever translates it — a work item whose owner field is
malformed simply fails to match the query — and the domain then grades "the query
returned nothing" as "this person owns nothing", the very distinction the previous
step had built the gap and the run condition to preserve. With an enumerating read the
same record raises a malformed-record defect instead. The rule that came out is the
reviewer's wording, more precise than "enumerate everything": a fact-bearing reader
enumerates its domain, selects by identity, or narrows by a natural window such as a
date span; it never filters by a relationship the domain derives; document search is
content retrieval and derives no facts. The leave query lost its employee filter for
the same reason and kept its span.

The reviewer added a precision worth keeping. Enumerating readers make the
closed-domain declaration possible to honour, not automatically true: closure has no
notion of "the tracker was read to completion", only of facts, gaps and which sources
were reachable. The fault ruling from earlier in the step closes most of the gap — the
first unreachable fault marks the source unreachable for the rest of the run, so
reachability at the end of a run means every enumeration the run attempted completed,
and facts read before the fault stay facts because closure checks a positive fact
before it checks reachability. What remains is the harness that never called the read
at all, which is a lifecycle contract for the investigator milestone — every
enumerating read runs to completion before the rules — and not a new completeness
type; that type arrives only if reads ever become incremental. The cost is stated
honestly: "what does this person own" becomes a filter over facts derived from the
whole project rather than a server-side query, retrieval efficiency spent for the
benchmark's evidence semantics, negligible at this world size, and pagination stays the
adapter's without reintroducing a relationship filter, since "the next page of the
universe" is not "only the records for which a fact is assumed true".

The second commit built the derivation itself: one function per observable record,
and the meaning of every field's absence stated in one place — a missing skills field
is a gap, an empty one is zero facts; a missing due date or manager is an observed
negative; a requested leave, a comment, a team and a document derive nothing. When a
fact became observable is the caller's knowledge, passed as a parameter, because the
entities keep vendor timestamps out on purpose. The main test rebuilt the four-person
rule fixture from entities and checked that the derived base contains every
hand-written fact but the four only a world can plant — the skill mentioned in a ticket
comment, the owner a stale runbook asserts, the two clause requirements — so the
fixture and the derivation stand as two independent sources for each other. Stated as
a proposal for the steps that build the truth base: the world should derive its truth
from the entities it generated through this same derivation and then add what only a
world knows, so the truth base and the base a live harness derives agree on what every
field means by construction rather than by a table kept in step.

The last review round showed what "two independent sources" does and does not check.
The event's schedule fact — a half-open span built from the event's start and its end
— cited the `start` field as its evidence, and so did the fixture's hand-written
helper, so the equivalence test passed while proving only that two copies of one
assumption agreed. An evidence reference is a locator for re-verification, and
re-reading a start time cannot re-establish an interval. The schedule now cites the
whole event record, the same shape a leave's absence uses when it cites the leave
record, and the fixture changed with it; a direct assertion on the provenance was
added so the shared assumption cannot hide again. The transferable lesson is that a
consistency test between two artifacts written by the same hand checks the hand's
consistency, not its correctness; independence has to be argued per assumption, and
provenance is one the fixture did not independently hold. The same round caught a
fixture comment written without the bracketed prefix a translated comment must carry,
and a fixture named five-person that has held four people since it was written.

Figure: the boundary as a pipeline — port observation → complete enumeration or
natural window → entity translation → fact derivation → relationship filtering →
closure — beside the before/after of the work reader's surface (owned-by and
in-component gone, one enumerating read in their place).

## 2026-09-10 — The rules are questions to the fact base: a verdict table caught the veto the code had hidden, and "uncovered, not unknown" turned out to be arithmetic

*M1 step 4 of the build plan, the deterministic core in `core/`: value specs, the fact
base with gaps and the run condition, closure, the authority table, the viability
rule, the plan side, the chain checks (commits `bc8582a`, `8cafa99`, `f30451d`, with
review follow-ups `8d5a192`, `b8f3805`, `5b5fc4c`; 221 tests including doctests at
the seal). Feeds: the M1 report's deterministic-core and evaluation-design sections
— why the same rule functions serve the generator and the evaluator, and what
"derived per run condition" costs in practice; the M1 post.*

The step opened with a five-question interview, one ruling per exchange, and each
answer went past an external low-context reviewer before it was ruled. That loop
earned its keep in the first question. The proposal was that a fact's value shape is
the predicate's to declare — a value spec on each registry row, validated at
construction and mirrored as the JSON tag — with a single `Requirement(count,
skill)` shape for what a clause asks. The reviewer wanted the requirement's criterion
tagged on the wire so a sealed answer key survives a later grade or country
criterion; the counter-argument was that a one-variant union is structure ahead of
need. The compromise was to tag the wire and keep Python narrow. One question later
the ruling on `hard_rule` — a policy criterion such as "an employee, not a
contractor" living inside the same requirement — made the union real, and the wire
shape was already right. The lesson the report can carry is about sealed artifacts:
a format decision is cheap before the first world is sealed and expensive after,
which is the one place where "you aren't going to need it" loses to a tag.

Two rulings shaped everything downstream. Absence became a record of its own: a
`Gap` says the record was observed and the field held no value, planted where a
scenario class plants missing information, and never a failed read — a failed read
is the run condition, a set of reachable sources passed beside the run context
because one scenario runs under several. That split lets closure read in five steps:
a positive fact is known true, a domain source unreachable in this run is unknown for
inaccessibility, a gap is unknown for absence, an open domain is unknown for
insufficiency, and only then is zero evidence false. The second ruling kept a
requirement's count away from any individual: criteria assess a person, the count
judges a plan, so one viable person against a two-person clause is a viable candidate
and an invalid plan. `load` was pruned from the reasons a candidate can fail for —
no first-set scenario names it, and a threshold would be either a constant the agent
can only be told or a clause no scenario uses; it returns when a class gives it
semantics.

The build ran in three commits, reviewed as foundation first and dependents together.
The moment worth telling is in part 2. Once the viability rule existed, the five-person
test fixture was run under three conditions — every source reachable, the tracker
down, the calendar down — and the verdicts printed as a table for Arda's read. One row
was wrong on sight: with the tracker down, the ticket's component could not be read,
and the code had marked the whole need unresolved, so the leaver herself showed as
*unknown* although her leave was a known failure. The ruling said a known failure
dominates an unresolved question; the code had let one unreadable fact veto every
other criterion. The fix made an unreadable component one unresolved criterion and
kept the leave window — a run input, not a fact the rule establishes, since a run
whose HR system is down still knows which leave it investigates. A meeting whose
schedule is unreachable stays an unresolved need for everyone, because without the
window no criterion has anything to ask. The table caught what the tests had not,
because the tests encoded the same assumption the code did.

The same table produced the case the post should open with. The release meeting's
clause asks for two Kafka engineers who are employees. With the tracker down, one
candidate's Kafka lives only in a ticket comment and reads inaccessible; the other
three are settled — on leave, in an overlapping meeting, a contractor. The expected
outcome is *uncovered*, not *unknown*. That looks like a mistake until the rule is
read: with `V` viable and `U` unknown against a required `n`, the outcome is assign
when `V ≥ n`, uncovered when `V + U < n`, unknown otherwise. Here `V + U = 1 < 2`:
even if the unknown resolved in the candidate's favour, one person cannot fill a
two-person clause, so the epistemic gap does not change the answer. The formula
reasons about what the unknowns could become, and "uncovered" here is a certain
conclusion, not caution. That is the distinction the vocabulary was built to make
measurable, showing up unprompted in a fixture.

The two review rounds found five things, every one reproduced against the shipped
code before it was adopted, which matters because the reviewer could not run the
suite and worked from the pushed diffs. The one that would have bitten silently: the
closure function validated the subject of a query but not the value, so asking
whether someone holds `"Kafka"` where a lower-case slug is declared returned a known
false rather than raising — a programming error turned into a statement about the
world. The one I got wrong: the reviewer asked for a runtime check that a
requirement's criteria are the criterion classes, and I left it out as "the type
checker's job". The reviewer's follow-up showed the chain: the value spec admitted
the object, and the codec's unreachable branch would have failed with an assertion
instead of a `ValueError`. The codebase's own rule, that an object which exists is
valid, applied, and the check went in shaped so the strict type checker does not flag
it as redundant. The one that reached back: a source-conflict claim could describe a
skill set or two sources agreeing, neither a disagreement — a hole from the
claim-vocabulary step that only became observable once the chain checks trusted the
claim. It is now refused at both levels, the claim constructor and the authority
rule, because the two answer different questions: can a report represent this, and
may the table resolve this.

The last finding drew the boundary the evaluator will live on. The chain checks read
a report alone and never ask the fact base; an unknown assessment must derive from
unknown claims shaped as the rule emits them. A clause-shaped unknown originally
passed for any clause, so an assessment could be justified by an unrelated policy.
The tightening: the clause must be one the report's own constraint claims cite for
something that could apply to the impact — the artifact itself, or a component when
the artifact is a ticket. Whether the ticket really belongs to that component is
truth, and stays the evaluator's; that the report has not justified an unknown with a
stranger's clause is coherence, and the checker can say so from the report. Report-
internal versus truth-dependent is the same line the uncovered check keeps: a report
with no viable assessment passes the chain check even if it simply stopped assessing,
and a separate completeness check that takes the candidate universe is where the
world enters.

[PRELIMINARY — the fixture is five people and two impacts; the first generated world
at step 13 is where these rules meet thirty scenarios and the tool-failure runs, and
where the "every non-skilled candidate turns unknown when the tracker is down"
behaviour, correct under the closure rule, gets its first measured cost.]

Figure: the fixture's verdict table — four people × two impacts × three run
conditions, verdict and reason per cell, expected outcome per row (regenerable from
`tests/unit/world_fixture.py` and `assess_impact`); the "uncovered with one unknown"
cell annotated with the `V + U < n` arithmetic.

## 2026-09-09 — The gate had a name all along: the 5-series block is an account review, and the public threads never said so

*M0's trailing thread, the Bedrock Support case (case 178776610200708; detail in
`probes/FINDINGS.md`, the dated 2026-09-09 entry). Feeds: the report's model-seam
section, as the second half of the "listed is not callable" story; a teaching aside
on where to look when the public record looks unresolved.*

The 26 August entry below ended with a research pass that found no official
criterion for the Sonnet 5 / Opus 5 block and no confirmed fix in any public thread,
and with a Support case queued "for the record". The case was opened the next day
and the answer came back within hours: access to those models "requires an account
review process", which Support submits on the customer's behalf once it has a
business use case (task types, usage pattern, why the region) and a business website.
That is the criterion the seven-source research pass could not find, and the reason
it could not is ordinary: the people who got this answer stopped posting. A thread
that looks unresolved on re:Post is often one where the resolution moved into a
private channel. The lesson for the report is small and transferable — when a gate
behaves like account state, ask the account's owner before surveying the crowd, and
do it early, because the answer arrived faster than the research did.

The case then sat unanswered through the platform detour, auto-closed after ten
days, and was re-opened and answered on 9 September. The reply is deliberately plain
about what this is: an individual developer's portfolio project, synthetic data, a
few hundred evaluation requests per run a handful of times a week under a Budgets
cap, Frankfurt because the rest of the stack lives there, the portfolio site as the
"business website". Inventing a company to pass a review would be a poor trade for
a project whose pitch is honest measurement, and a refusal is itself a usable fact:
"an individual account was reviewed and declined" is more credible in a report than
"blocked, cause unknown". [PRELIMINARY — the review's outcome and duration are
pending; either revises this entry's last paragraph.]

Nothing in the plan moved. The ruling not to build around the 5-series was made for
schedule reasons, not for lack of a path, and the review has no stated duration;
M2's Anthropic candidates stay Haiku 4.5 and Sonnet 4.6, and a pass later is a
one-line edit to the model list in the platform stack.

## 2026-08-26 — Listed is not callable: the Bedrock catalogue said AUTHORIZED to every model the runtime then refused

*M0 day 2, the bedrock probe (PARTIAL, then PASS for the reachable shortlist, same
day; detail in `probes/FINDINGS.md`, prices in `probes/captures/bedrock/models.md`).
Feeds: the report's model-seam and cost sections; a teaching aside for any post about
"choosing a model on Bedrock".*

The probe's question was modest: for each of six shortlisted models, does the
instance role get a round-trip, a tool call, and a prompt-cache hit, and what does
the model cost in Frankfurt. Four days earlier the account bootstrap had recorded
"Bedrock needs no model-access request in this account", on the strength of Haiku 4.5
answering cold. On the day, the three Amazon Nova rows passed everything on the first
run (`probe-run-1.jsonl`), and every Anthropic row failed — for two different
reasons that took a while to tell apart.

The control plane was no help in telling them apart. `get-foundation-model-availability`
reported AUTHORIZED and AVAILABLE for all six; the Bedrock console's old "Model
access" page has been retired; the catalogue lists the 5-series with a price. Only the
runtime knew the truth, and it knew it per model: Haiku 4.5 wanted Anthropic's
"use case details" form, which the console offers on the first playground invoke;
Sonnet 5, Opus 5 and Opus 4.8 were "not available for this account, contact AWS
Sales"; Sonnet 4.6 answered with no form at all. Reproducing the failures from an
AdministratorAccess session settled that this was account state, not the role's
grant — which mattered, because the grant had just been pinned to the shortlist and
was the first suspect.

The form's behaviour was the surprise worth recording. It was submitted at ~20:02;
Haiku 4.5 opened three minutes later. Sonnet 4.6, which had been open *before* the
form, went form-gated, then spent six minutes returning AccessDenied, then opened at
20:15:58, and flapped once more mid-run. Propagation is per model and not monotonic:
a model you could call can stop answering while the form works its way through. The
practical rule for a fresh account: budget twenty minutes and a retry loop, and
never trust the first answer in either direction. The 5-series gate did not move,
and a research pass (seven sources, re:Post and r/aws threads since roughly June)
found the same signature across regions and account types with no official
criterion and no confirmed fix — so the ruling was not to plan around the 5-series
at all. A fix later is a one-line edit to the model list in `variables.tf`; a
Support case is queued for the record.

> ⚠ REVISED by the 2026-09-09 entry — the Support case named the criterion: a
> manual account review with a business use case and website as intake.

Two smaller facts fell out. Anthropic's rows are not in the Pricing API (it carries
only legacy Claude 2/3 US SKUs), so their prices came from the pricing page read in a
browser by a subagent; the `eu.` inference profiles cost a flat 10 % over `global.`
across the board. And Nova Pro missed its cache once in five passes — an `eu.`
profile can route a call to a region that has not yet seen the prefix — which is a
line item for the M2 cost model, since the $0.75-per-investigation estimate assumes
caching works.

What the shortlist looks like after all this: two Anthropic models (Haiku 4.5,
Sonnet 4.6) and three Amazon (Nova Lite, Nova Pro, Nova 2 Lite), all answering from
the role, with Nova Lite about 14× cheaper than Haiku 4.5 on input. The choice among
them is deliberately not made here; M2's evaluation on the golden set makes it. The
probe's job was to find out what can be measured, and the honest summary is that the
catalogue could not tell us.

Figure: a small table — model × (control-plane says / runtime does / minutes to open
after the form) — makes the "listed ≠ callable" point in one glance.

## 2026-08-26 — The subject GitHub actually sends: an OIDC trust policy that matched the documentation and not the token

*M0 day 2, the oidc-deploy floor (PASS; detail in `probes/FINDINGS.md`,
`captures/oidc-deploy/`). Feeds: the report's deployment section (keyless CD, the
production gate) and the hosting appendix.*

The floor was preregistered as one sentence: a commit to `main` changes the running
service on the instance, with no AWS key stored anywhere. The mechanism is standard
— GitHub Actions federates into the account through OIDC, assumes a deploy role, and
runs the deploy script on the host over SSM `send-command` — and the probe plan
carried one open fact to record: what `sub` claim the token actually has, since
repositories created after mid-2026 were rumoured to emit a new form.

The rumour was right and the documentation was not, or at least not for this
repository. The trust policy was first written with the documented, name-based
subject. STS refused twelve retries with "Not authorized to perform
sts:AssumeRoleWithWebIdentity" before the job log gave up the real claim:
`repo:arda-basarici@133336041/leave-impact-agent@1342572683:environment:production`
— owner and repository each carrying their numeric id. Pinning the trust to that
form is the stronger pin, not a workaround: a repository renamed or deleted and
re-created under the same name inherits nothing, because the ids differ. The role is
trusted by repository *and environment*, which is why the production gate is part
of the security story rather than a convenience.

The gate had its own lesson. A workflow that references an environment which does
not exist creates it, bare; the first deploy went straight through with nobody
asked. Only after a reviewer and a `main`-only branch policy were set on the
environment did the re-run stop at "Review pending". A new GitHub environment is
not a gate until someone configures it to be one — worth one line in any runbook
that leans on it.

Two identity flips are on record: the first approved run replaced "no application"
with `leaveimpact 51d3f16`, and the very next commit — the one that recorded the
probe — flipped it to `leaveimpact 2f028b2` at 12:26:24Z through the same gate. In
between, the boot script changed (the proxy stack took over the shared network and
`trusted_proxies` is now rendered from the same pinned Cloudflare ranges as the
security group), so the instance itself was replaced: new instance, same Elastic
IP and data volume, certificate re-read from Parameter Store, HTTPS 200 with no
manual step, in 1m13s (the first boot had taken 4m53s, most of it waiting for the
secrets to be put). "The host regenerates from code" stopped being a claim and
became a measured event.

One deviation from the plan's wording is deliberate and should be told as such: the
row said "pushes an arm64 image to ECR", and there is no ECR. The baseline review
had already ruled GHCR as the registry, and a second registry would have existed
only to satisfy the row. The thing the row exists to prove — federation, a role
trusted by repository and environment, a commit landing on the host through SSM —
is exercised in full; preregistered criteria stay as written and the findings carry
the deviation with its reason.

## 2026-08-24 — One command, three systems, zero duplicates: the seed spike closed probe day 1 — and a network fault earned its place in the adapter design

*The last day-1 probe of M0 (seed-spike, criterion preregistered in `probes/README.md`
before the run). Feeds: the M0 probe-days post; the report's world-generator section
(the spec→projections→manifest seam) and its evaluation-design section (stable-now);
the M2 adapter section (the retry lesson).*

The spike's question was whether the M1 generator's core seam works at all: one org
spec — 5 people, 1 project, 8 issues, a week of meetings, 2 approved leaves —
projected into three systems that never see each other, idempotently. The three
systems (Frappe HR on the box, Jira Cloud Free, Google Calendar) are deliberately not
synchronized; what makes them "the same org" is only that all three projections read
the same spec, keyed by the same employee ids. Consistency by construction, not by
reconciliation — the project's ground-truth-by-construction signature applied to the
environment itself.

Before the spike could run, a ruling: the earlier probes had left residue (a "Probe
Org" company in Frappe, auto-created projects in Jira, test events in calendars), and
Arda asked for clean plates. The options differed in kind. Scrubbing shared systems
can never prove it got everything — every future world inherits doubt about what's
left. Fresh containers — a new Frappe site per world (`bench new-site` ≈ 2 min, the
Host header selects the site), a new Jira project key, new secondary calendars — are
provably clean *by creation*, and "reset a world" becomes drop-and-recreate instead of
a cleanup audit. Arda ratified fresh containers; the compose frontend switched from a
pinned single-site name to `$host` routing the same hour, and the probe created its
own site (`hr-w1`) rather than inheriting the probe site's residue. One honest limit:
Jira Free is one site, so the *project key* is the container there — residue outside
the world's key coexists but is invisible to the agent's tools, which query by
project and owner field.

The run itself passed everything on the first attempt (capture:
`probes/captures/seed-spike/run-01.json` — 64 creations). Two results matter beyond
"it worked." First, **Jira Free accepted everything over REST** — including creating
the `W1` project itself with the company-managed kanban template, previously an
open question, and JQL date arithmetic on custom date fields: `"Opened On" <=
"2026-09-08" AND ("Resolved On" IS EMPTY OR "Resolved On" > "2026-09-08")` returned
exactly the spec's open set per person. World dates as custom fields — the ruling
that had closed the resolution-date gap on paper the day before — now holds in
practice, and the manual CSV import is fully out of the seeding path. Second,
**stable-now became mechanical**: the spike's verify step computes `answer(now)` —
who is on leave in now's week, which issues are open as of now, which calendar
blocks are busy — at two instants inside a declared stable interval (Sep 8 and
Sep 10) and requires identical answers. It held, and the *reason* it held is the
design's teeth: the spec plants no world date inside the declared interval. That
guarantee is now the generator's contract, not a hope.

The idempotence half took a fight. Reruns kept dying on a transient transport fault:
an authorized Frappe GET would intermittently hang or get connection-reset, and the
origin's nginx access log proved the request *never arrived* — something between the
client and the box (the Cloudflare edge, or the hosting provider's connection
policing; the stream's fix log already records SSH resets on the same box under rapid
connections) was killing it. Unauthenticated calls never failed in reproduction; the
same call passed moments later. Mid-diagnosis Arda made a process correction that
shaped the outcome: don't burrow — surface what's known and discuss the approach.
The known facts supported a pragmatic fix over a root-cause hunt: a retry on
*connection-level* faults only (never on HTTP errors), safe here because every write
is find-or-create. Run 5 then delivered the criterion cleanly — **0 creations,
identical verify results** — and its capture shows the retry earning its keep: two
faults on one call, third attempt clean (`run-05.json`; runs 02–04 are the fault
captures). The transferable lesson went into FINDINGS: every M1/M2 adapter needs
connection-fault retries, because the transport to real external tools is measurably
imperfect even at probe scale. Root cause stays open in the fix log (cheapest next
clue: Cloudflare's Security → Events page).

A design consequence surfaced by Arda's question rather than any probe: when this
project is shared, *nobody visits the three tools*. They are the agent's world —
credentialed, private (a Free Jira site, Frappe behind Caddy on the box, a consumer
Google account) — not the audience's window. The audience surface is the demo
milestone's report view, which means evidence there must be **self-contained**: the
quoted fact, its source system, its provenance rendered in the report itself, with
deep links decorative at best. Noted for the demo milestone's design before any of
its UI exists.

Figure: the twin-instant check as a small diagram (one week band, two `now` marks,
three system answers converging to the same tuple); or the run-01 vs run-05 creation
counts (64 → 0) as the idempotence before/after.

## 2026-08-23 — Two vendor surprises from the HRIS probe: the setting that is silently ignored, and the approval check the admin token walks through

*M0 day 1, the frappe-rest probe (PASS same day; detail in `probes/FINDINGS.md`).
Written 2026-08-24 from the stream session log and FINDINGS. Feeds: the M0 probe-days
post; the report's adapter section (vendor-behavior risk) and its security/permissions
section (the runtime principal ruling).*

The HRIS probe was supposed to verify a boring round-trip — employees, leave
allocations, leave applications over REST — and it did (balance arithmetic exact:
20 → 15 for a Mon–Fri week, → 19 for a single day; capture
`probes/captures/frappe-rest/run-03.json`). What earns this entry are two behaviors
no documentation had promised.

First, a silent ignore. Frappe HR v16 resolves an employee's holiday list only
through a *submitted Holiday List Assignment* document. The legacy fields the v15
docs describe — `Company.default_holiday_list`, `Employee.holiday_list` — are still
accepted by the API and then ignored: run 2 set both and leave creation still failed
with "No Holiday List was found" (`run-02.json` is the failure capture). The lesson
is not about holiday lists; it's that a vendor API can accept a write and quietly do
nothing with it, which is exactly the class of behavior a generator that claims
ground truth by construction cannot tolerate on faith. The seed's independent
read-back verification exists for this reason, and this was its first live
justification.

Second, an inverted wart. Going in, the worry was that setting `leave_approver`
would need workarounds. Setting it turned out trivial — the real finding pointed the
other way: an *Approved, submitted* leave application whose approver is **not** the
submitting principal goes through when the token belongs to a System Manager. The
admin token bypasses the approval check entirely. For the generator this is a
convenience (it seeds approved history in one call — the god of its world needs no
approver's consent). For the agent it is a threat model: the same convenience in the
investigator's hands would let it fabricate approved state. The ruling that fell out:
the agent's runtime principal must be a role-scoped User, never the Administrator
token — least privilege has to hold at *both* layers, the tool registry in the
harness and the API principal underneath it. One probe, one sentence in the security
section that would otherwise have been discovered in production.

A third, quieter fact rounded the picture: backdated `posting_date` is taken as
given, so Frappe needs no custom-field detour for world dates — its documents' own
date fields already separate world time from the vendor's `creation` timestamp. The
same split Jira needed custom fields to achieve, Frappe gives away.

## 2026-08-23 — The box doesn't build: how a missing Docker image ruled the supply chain, and a reviewer tightened "pinned" into a digest

*M0 day 1, the frappe-up probe (PASS; detail in `probes/FINDINGS.md`). Written
2026-08-24 from the stream session log and FINDINGS. Feeds: the report's
ops/deployment section; candidate material for a post on supply-chain discipline at
hobby scale.*

The plan said "run Frappe HR in Compose on the box." The catch discovered en route:
**no official image carries the HR app.** `frappe/erpnext` ships without `hrms`, and
hrms requires erpnext — so somebody had to build a custom image, and the question
became *who and where*. The candidates: a one-time build on the box, builds from the
workstation, or CI as the only manufacturer. The first two died on the same
principle, now written into DESIGN: **production hosts consume artifacts, they never
manufacture them.** A box that builds its own images is a box whose running software
cannot be traced to a commit; a workstation build is the same problem with worse
reproducibility. So GitHub Actions builds the image from a pinned `frappe_docker`
commit (frappe 16.31.0 / erpnext 16.32.3 / hrms 16.16.0, `apps.json` fed in as a
BuildKit secret), pushes to GHCR — and the build took 4m36s against a 15-minute
estimate.

The sharpening came from outside: an external reviewer corrected the claim that
referencing the image by a version *tag* made it "pinned." A tag is mutable — whoever
can push the registry can move it, and the box would follow silently. The box now
references the image **by digest** (`FRAPPE_IMAGE=ghcr.io/…@sha256:…` in the box's
env file), which is immutable by construction; the `:16` and git-sha tags exist for
humans only. Updating means editing one line — an explicit act with a diff, never an
ambient drift. The correction was adopted the same day; the reviewer's other
suggestion (trigger builds only on image-input changes) turned out to already be the
workflow's shape.

One measured number worth keeping: the running stack's idle footprint with a site
installed is ~0.9 GB (box `used` 604 → 1,472 MB, `captures/frappe-up/`), against
Frappe's "8 GB recommended" sizing that had shaped early memory planning — recommended
sizing is not measured need, and the box's 16 GB holds two tenants comfortably.

## 2026-08-23 — Employees who never log in: the person model that dissolved the 10-user ceiling

*The world-shape rulings session (ruling 2 of five, written to DESIGN "The world's
shape") and the Jira probe that proved it the same day (PASS; detail in
`probes/FINDINGS.md`). Written 2026-08-24 from the stream session log and FINDINGS.
Feeds: the report's world-design section — likely its opening argument; the M0/M1
posts.*

The blocking question looked like a licensing problem: Jira Free allows 10 users, the
synthetic org wants 25–30 people, and buying seats for fake employees violates the
project's $0-tools constraint (org tools cost nothing; the spend is AWS and tokens —
Arda's line). Every path that treated synthetic people as *Atlassian accounts* was
some mix of expensive, fragile, and dishonest (a "dev instance" is licensed for
dev/testing only; shared accounts fake what they claim to test).

The ruling dissolved the problem instead of solving it: **synthetic employees are
domain entities, not vendor users.** In Jira they exist as values of a single-select
custom field (`Synthetic Owner`, keyed by employee id), `assignee` stays empty, and
actor identity — who *technically* wrote the comment, whose token created the issue —
sits outside the truth model entirely, as vendor plumbing. The 10-user ceiling
doesn't bind because the org consumes one service account, whatever its size. The
same model transferred unchanged to the HRIS (employees are `Employee` records keyed
by `employee_number`, the manager relation a domain link, one service User as
everyone's approver) and to Calendar (one OAuth principal owning one secondary
calendar per person). Three vendors, one identity rule.

The probe then proved Free holds up its end (`probes/captures/jira/`): the select
field created over REST and placed on screens, exact JQL per person
(`"Synthetic Owner" = "emp_001 — Probe Alice"` returns that person's issues and
nothing else), comments naming synthetic people round-tripping with the service
account as author — exactly as the actor-identity ruling expects — and an idempotent
second run. The one real limitation surfaced honestly: CSV import (the only way to
backdate Jira's own `created` timestamp) cannot set `resolutiondate`, is UI-only, and
its first attempt silently stamped import-time on every row because the wizard's
date-format field kept its default against the file's format — a silent fallback, not
an error. The consequence became a better ruling the next day: world dates live in
custom date fields the generator controls (`Opened On`, `Resolved On`), Jira's own
timestamps are hidden as vendor time, and the CSV import is demoted to cosmetics.
The vocabulary that keeps all of this straight — synthetic world → vendor
representation → domain-facing tools, with adapters that translate identity and
never launder a planted inconsistency — is Arda's framing, and it's the sentence the
report's world section should open with.

Figure: the three-layer diagram (world / vendor representation / domain tools) with
the person model crossing it — one synthetic employee shown as a field value in Jira,
an Employee record in the HRIS, a calendar id in Google, and *no user account
anywhere*.

---

*Candidates not yet written (material exists; write when a report or post needs it):*

- *M0 closes with every row verified, the non-blocking one too (2026-08-26) — Slack
  proved on the first run after a scripted-not-run interlude; the ruling to finish
  trailing probes rather than carry them, and the 90-day-history fact that makes
  Slack content a run-time write in the world generator. The cost line as an
  honesty anecdote: the design doc's ~$21 held and the working estimate of ~$18–19
  was the low guess (Pricing API, `probes/captures/instance/pricing.md`). Material:
  SESSION_LOG session 7, FINDINGS slack entry.*
- *The instance floor (2026-08-26) — the whole host from Terraform, the secrets rail
  (Origin CA pair as SecureString, read at boot by a path-scoped role), the
  Cloudflare-only security group, and the three interview rulings annotated lasting
  vs cheap. Material: SESSION_LOG session 5, FINDINGS instance entry.*

- *The hosting ruling (2026-08-22) — app on AWS, HRIS on the box, decided by the
  career-strategy gap's own wording; tombstoned extremes and the preregistered
  ephemeral-compute probe. Material: SESSION_LOG 2026-08-22 (design session part 1),
  DESIGN's hosting matrix.*
- *The three-lens review pivot (2026-08-23) — three independent review agents
  converged on "the world's shape is undecided," moving the next step from a probe to
  five rulings. Material: SESSION_LOG 2026-08-23 (calendar session).*
- *Calendar scopes measured, not assumed (2026-08-23) — `calendar.app.created` can
  create calendars it then cannot list; the working non-sensitive scope pair; the
  UTC-authoring slip as a timezone-distractor lesson. Material: SESSION_LOG +
  FINDINGS calendar entry.*
- *The vision method (2026-08-20→22) — grading SteamLens's vision with build
  hindsight, draft-then-interview, deploy-from-day-one as a mid-interview ruling.
  Material: SESSION_LOG founding entry, VISION.md.*
- *Probe day 0 as a teach-through (2026-08-22) — the AWS account bootstrapped with
  every term defined at first use; why the admin SSO user beats root. Material:
  SESSION_LOG day-0 entry, the AWS study file.*
