# The development protocol

`registration.json` in this folder is the preregistration: the one file that says what the
investigator milestone measures, on what, and how the result is read. This note explains
the file. It restates none of its values; where a number matters, the file is where it is.

## What the file is

One JSON file with a format version, decoded strictly: every field required, an unknown
key refused, and the bytes accepted only if they are the one form the encoder writes. It
is changed through the encoder and never by hand, and a line in `.gitattributes` keeps a
checkout from rewriting its line endings, so the bytes at a commit are the bytes that were
registered. The file is at format 3. Nothing reads format 1 or 2, and no run was made under
either that a report could cite.

Names live in the file and behaviour lives in code. The file names a check, a measure, an
interval method, a prefetch rule, an outage protocol, a composing policy; the code holds
what each name means. Each consumer compares what the file names with what its own code
computes and refuses to run on a difference. Neither side is ever substituted for the
other: a run that quietly used today's value would cite a registration it did not follow.

## Draft, frozen, bound

The file has a status, and there are three.

A *draft* may hold values that are not chosen yet. Each such value is written as pending,
with a sentence saying what will resolve it, and a pending value blocks only the execution
that needs it: the rules-only baseline runs while the model systems' entries are still
pending. A model system needs more than its own entry. Its runs are read by the
attribution table, dispatched under the re-dispatch policy and parsed by the entry schema,
so it stays blocked while any of the three is pending. No entry point fills a pending
value with a literal.

*Frozen* says the procedure is fixed, and it is fixed before the world it will be measured
on exists. A frozen file has exactly one value pending, the world's version. It refuses
any other, it refuses caps and a budget whose basis is still unmeasured, and it refuses a
world any scenario of which was tuned on.

*Bound* is the frozen procedure with its world. It holds the world's version and names
the commit of the frozen file it binds. Binding changes those two values and the status
and nothing else. The evaluator checks this instead of trusting it: it reads the file at
the named commit, requires it to be frozen there, and compares the two procedures as
written. A bound file whose procedure differs from the frozen one's, or that is evaluated
against another world, refuses the whole evaluation.

The freeze comes after the calibration runs, when the forecast of the whole registered
workload fits under the spending threshold with what has already been spent. What the
freeze sets is in the file as pending today: the padded level's size, the repeat count,
the caps, the attribution table's rows, the re-dispatch bound, the decision on the
conditional cells and the inclusion of each supporting comparison. If the forecast does
not fit, the file stays a draft and the measurement does not start.

Every dollar figure in the file is a placeholder carried from the design, cumulative over
the milestone, and marked unmeasured. None is a target or an accepted spend. They are set
again from real usage before the freeze.

## The world

The measured world does not exist yet. It is generated from a seed drawn from a secret
after the procedure is frozen, and bound once it has been validated and audited. No prompt
and no setting is tuned on any of its scenarios, and the file says so in a field a frozen
registration requires to be zero. That zero is the measurement world's. Development
happens on other worlds, and a development run names its world itself: under a draft or a
frozen file an evaluation is labelled development whatever world it is of.

The seed is thirty-two bytes of entropy, created as a repository secret in lowercase hex
through a path no terminal history keeps, and it reaches the generator through the job's
environment, parsed in memory and never printed in any form. The two digests the repository
commits for a world are functions of the seed and public code, so a seed anyone could
enumerate is no secret. A seed the generator's reservation book refuses, about one in fifty
under the golden plan, is replaced by a fresh draw; each draw is numbered and its outcome
recorded, the value never. The world is sealed *embargoed*, a mark in its provenance: every
reader withholds its digests and its retrieval-target counts from public output, the
evaluation job scans the checkout for either digest and fails on a hit, and the seed and
the recipe are published after the last confirmatory measurement on the world.

The world generated first, version
`7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4`, is a development
world. Its recipe is public and its corpus is small enough that one call shown every
document reaches the ceiling, so it separates no model systems. Six of its scenarios are
the live-iteration subset, the ones prompts are tried on first: `scenario_009`,
`scenario_010`, `scenario_013`, `scenario_018`, `scenario_023`, `scenario_028`. They were
drawn two from each tier by a seeded draw that read no expected answer, and are listed
here as bare ids because a scenario's tier is sealed and this repository is public. The
registration no longer holds them, and nothing in the evaluator treats them differently.

A development world is sealed *unprojected*: nothing is written to the HR system, the
tracker or the calendars, and the benchmark's own readers present the world's plantings as
those three systems, so a development run takes the same read path as a measured one and
the deployed application never sees the world. Its recipe is local. The generator reads
four variables, the writer model, the checker model and their Bedrock region
(`LEAVE_IMPACT_PROSE_WRITER_MODEL`, `LEAVE_IMPACT_PROSE_CHECKER_MODEL`,
`LEAVE_IMPACT_BEDROCK_REGION`) and the store's root (`LEAVE_IMPACT_OBJECT_STORE_ROOT`),
which must be a path the repository ignores, `data/object-store` here, or one outside it.
`python -m leaveimpact.generator --seed N --world-start DATE --plan golden
--filler-documents 12 --filler-sections 4 --unprojected` seals the world and prints its
version; `--attempt-cap` raises the default of eight where a filler section exhausts it,
which the first development world needed at sixteen. The proof, `python -m
leaveimpact.evaluator prove --world-version HEX --run-id ID --run-attempt 1` over the same
root, takes by hand the run identity the workflow reads from its runner. A rerun of a
sealed version is `--resume HEX --unprojected` with the recipe repeated, and reseals
nothing. A development world does not later become a projected one; it stays unprojected.

## How the measurement world is accepted

A draft, written at the generator step's close. The definitions, the sampling rules and the
replacement rules are frozen with the procedure, before the world is drawn; the numbers are
set at the freeze from development evidence. Nothing here is decided by a result.

A *world defect* is one of three things: the validator refuses the world; a scope problem,
a clause whose target the index cannot resolve to one artifact or a handle two artifacts
share; or an audit finding that a planted fact is not readable from its carrier. Two
repairs are kept apart. A defect in filler alone is repaired by regenerating the filler
from a seed derived from the world's under the frozen filler recipe, with the planted
content byte-identical, which the stripped-equality test proves; a defect in a planted part
regenerates the world from a fresh draw. Neither repair is ever made on agent performance.

Seeds are drawn one at a time, each thirty-two bytes of fresh entropy, numbered. Every
rejection, by the reservation book or by a defect, is recorded with its number, its reason
and the version of the world it refused, in a private record this repository does not hold;
the accepted world's version is the one the registration binds. The number of draws before
the procedure is abandoned is the freeze's.

Before the world is bound, two samples are read by hand. A seeded draw of *k* scenarios per
tier, stratified because the slots are shuffled, each traced by the world milestone's audit
method (`AUDIT_METHODOLOGY.md`); and *n* filler documents drawn by the same rule and read
by a person or by a model of another family than the writer's, checking that each reads as
the requirement it imitates and names nothing of the world. *k* and *n* are the freeze's.

## What is measured

Four systems, each registered by kind and variant: the investigator; a rules-only baseline
that calls no model and reads no prose; a single-shot baseline that makes one model call
over the shared prefetch and one fixed retrieval; and full context, the same single call
shown every document instead of a retrieval's hits. A system that calls a model registers
its roles by name, each with its model configuration, its prompts and its tool surface, and
a run is compared with them role by role.

A *condition* is the set of sources scheduled unreachable for a whole run, injected where
the system reads. Conditions are reported in one of two ways, and the name describes the
assignment and its reporting, never how a run turned out:

- *Answer quality.* Every source reachable, or one whose outage still leaves an expected
  answer. These carry the full tables and the comparisons between systems.
- *Degraded condition.* The outage leaves the leave or the policy unreadable, so no
  claim-level answer exists. These carry the accounting, the cost and a table of what the
  runs did: whether the run met its outage, how it ended, whether it reported anything,
  and what its own reads make of what it reported.

A *corpus level* is a name and a count the world seals. The world carries a ranked pool of
answer-neutral documents that no scenario owns, and a level holds every scenario-owned
document and the first so many of the pool, so levels are nested and the answers are the
same at every one. There are two, the base level with none of the pool and a padded one.
Membership is derived from the count and listed nowhere. The file records beside the padded
level the size of the full-context request at that level in tokens, measured at the freeze
under the registered counting rule, because the world is model-neutral and a token count is
one tokenizer's.

A *cell* is one system under one condition at one level. Every system runs the normal
condition at both levels. The outages run at the base level only, so no outage is crossed
with a size. Rules only reads no document and gives the same answers at both levels; it is
run at each all the same, so that each cell has its own runs and the report can show they
are equal.

Four cells are conditional: full context under each outage. They form one group with one
rule and one decision, all four or none, taken from the cost forecast before any
measurement result exists. Until the group is decided as run nobody executes those cells
and nothing is reported for them.

A run is counted in the cell it was assigned to and graded against the condition its own
reads show. A system that never called the failed source ran under no outage and is still
a run of the outage cell, counted there as unexercised.

## How a run is counted

Every cell runs each scenario the registered number of times. A run that was intended and
never made does not pass in the end-to-end reading; it is not left out.

A run is retried after an infrastructure failure and after nothing else. A defect is not
retried, because a retry could hide it. The attempt that counts is chosen among the
attempts numbered within the registered maximum: the earliest one that did not fail by
infrastructure, or the last when all did. An attempt past the maximum is kept with its
cost and never counts. Every attempt is summarized beside the counted ones, so a failure a
retry recovered from still shows. A run whose attempt numbers have a gap within that range
has no attempt that can be shown to be the counted one: it keeps its grade and its cost,
enters no quality estimate, and is counted under its own reason.

Whether a run may be attempted again is one function over the closed vocabulary of
endings, run by the harness at admission and by the evaluator over the exported attempts.
A new attempt needs the predecessor closed, its export published, the registered maximum
not reached, and a rule that names its ending: a completed or capped attempt permits none,
a defect permits none, an infrastructure failure at a send follows the attribution table's
row, a bound exhausted with the last dispatch unresolved permits one, and an abandonment
permits one exactly when the attempt's log holds no dispatch intent, so an operator cannot
choose which attempt counts by abandoning one whose answer was seen. A run with an attempt
the harness inventory lists and no published export of it, open or closed with no export,
has no counted attempt either; it is counted in the whole and in no cell, since the
inventory holds no scenario, and a publication incident is reported apart from a graded
failure, an infrastructure failure and a run never admitted.

What a model dispatch observed and how the measurement reads it are recorded apart. The
reading is the attribution table's: behaviour of the system, an infrastructure fault, or a
defect of the harness, with whether the call may be dispatched again inside the run and
whether a failure there allows a new attempt. The table is registered so that which
failures count against a system is fixed before any result exists.

A run that carries a finding (its reads differ from the sealed world, an operation no
conforming harness records, a cost that does not add up, a prefetch that is not the
registered plan) stays in the tables and is counted beside them. Keeping a run is not
vouching for it.

Three more findings are counted the same way. A run whose recorded admissions or
composition are not what the gates and the composing rules give again. A run shown a
document outside the corpus level its record assigns, every document any read returned
being held to the level's sealed membership; a level the world seals no membership for is
counted as not evaluated, which is not a run with no finding. And a run whose reads
contradicted each other and that did not fail by defect.

And five about what a record states of itself. A run whose record gives an active time
above its elapsed time, a terminal instant before its admission, segments on more than
one harness commit, a fenced generation not its segment count, or an approval digest
that is not the digest of the claims it exports. A run with a dispatch whose recorded
reading is not the registered table's, or that was dispatched again where its row allows
none or beyond the registered bound; a run held to no table, because the table's rows are
not set or the record names another, is counted as not evaluated. And a run with a response
whose metadata shows the SDK sent more than once, nothing being allowed to retry beneath a
dispatch. One of these also decides eligibility: under a bound registration a run whose
segments ran on more than one commit enters no table, as a run from a dirty tree does, and
is listed with its grade. A duration is evidenced active time, a lower bound for a run with
a segment whose end was never recorded; a cost table says how many of its runs those are.

## How stated facts become claims

No model writes a verdict. A model states facts with the words it read them from, and the
rules compose the claims, for every system including the baseline, which states none. The
file binds three things about this. The composing policy, which names everything that
decides a composed report. The anchor table the guard on stated facts is read from. And
the entry schema a model's facts are parsed by, pending until the investigator is built.

The harness computes the composing policy and refuses to run under another. The evaluator
cannot compute it, and holds each run's recorded policy to the registered one. An equal
value there shows the run recorded the registered identity. It verifies no implementation.

## How the result is read

Three yes-or-no checks are registered by name, each defined mechanically in the
evaluator: whether a report is correct in every part against the expected answer, whether
its coverage actions are the expected kind, and whether the system's own reads reproduce
every claim it made. Each is read two ways: over the runs the check applies to, and end
to end over every run a scenario was meant to have.

There is one primary comparison: the investigator against full context, under the normal
condition at the padded level, on the first check read end to end, over all scenarios.
The overall contrast is the claim. Tier contrasts are breakdowns named in advance and
shown beside it, and no claim of success is made from a tier, an outage cell or any other
comparison.

Named in advance beside the primary, and carrying no claim:

- *Secondary.* The investigator against single-shot, at both levels.
- *Descriptive.* Every pair of systems at each named place: the normal condition at both
  levels, and the two answer-quality outages at the base level.
- *Level contrasts.* One system against itself, padded less base, under the normal
  condition, for each system that reads documents. This measures sensitivity to the
  padding. It does not say why a system changed.
- *The mechanism measure.* Of the prose statements a scenario's required rows depend on,
  how many had their carrier returned to the run, were stated correctly, were admitted,
  and were usable in the composed view: four stages over one denominator, which the sealed
  scenario and the assigned condition fix. It says where a system succeeded or failed on
  the way to its report. Each stage requires the one before it. A statement is stated
  correctly when its subject, predicate and value are the needed ones, read from a sealed
  carrier the run had already been returned. It is usable when the composed view keeps it
  and, for a requirement, its span is bound to what the sealed world scopes the clause to.
  A failed attempt keeps its denominator and nothing of it is usable. A scenario whose
  answer needs no prose statement enters no ratio. The measure is reported for each system
  that states facts, at the whole, by tier and by predicate, and contrasted on the
  primary's pair, the secondary pairs and the level contrasts, nowhere else. It is read
  from what a run's export records, and the evaluator decides the recorded admissions and
  the composition again and counts the runs where the two differ.

Every interval is from one method at any repeat count: whole scenarios resampled within
their tiers, a scenario's repeats kept together, two cells paired on the scenario. With
one run a scenario the two-by-two counts are printed beside the interval. An interval the
method cannot resolve is printed as unresolved with its reason: no eligible scenario,
fewer than two, a zero denominator, or every resample equal. The point estimate is still
shown, and an unresolved interval supports no statement that one system beats another.
No comparison is registered as a test of superiority: a difference is reported with its
interval, and when the interval crosses zero the report says it includes differences in
either direction. It never says the systems are equivalent. The uncertainty is about new
scenarios from this generator in this one organization, and the intervals are wide at this
size.

A system's normal and outage cells are shown side by side and never differenced. Their
expected answers differ, so a difference between them would compare two questions.

The measures are registered by name too, in families: the answer side over all claims
and per claim type, grounding and citations over graded and limited runs apart, source
discipline, retrieval. A comparison between two systems is made on a family's leading
row; the rest are reported per cell.

## Headroom

Under an outage the expected answer asks for less, and a system that states little is
right more often. The file registers a procedure that characterizes this: per place, the
number of scenarios the rules-only baseline does not already pass, of how many. It is two
counts and names no scenario. It is computed on the measurement world after the freeze
and disclosed in the report, and it never becomes a reason to change a cell or leave a
scenario out. It is a diagnostic, not the most a system could improve by.

## Supporting comparisons

Four comparisons are declared with their place, their two systems, their endpoint and
their analysis: vector retrieval against full-text retrieval in single-shot, a multi-agent
layout against the single investigator, the primary contrast under a second model, and a
model-authored report against rule composition. Whether each is built is decided at the
freeze, from time and cost, before any measurement result is seen. The list closes there.
A comparison on it is prespecified whenever it runs; anything added later is exploratory
and says so.

This format registers one system of each kind, so it can declare a supporting comparison
and cannot yet register the second system one would run. That arrives with the first one
that is built.

## What an evaluation is labeled

The label is derived by the evaluator from the registration it reads and stored in the
evaluation; no run labels itself.

- Under a draft or a frozen registration, an evaluation is *development*.
- Under a bound registration it is *reported*.
- A bound registration that says it amends an earlier one, and that full-set results on
  this world existed when it was written, gives *exploratory* evaluations. Those two
  statements are the registration author's. No job can read earlier evaluations to check
  them, so an evaluation carries them as declared.
- A run whose cited registration cannot be found in the repository's history is
  *unknown*.

A run enters the tables only when the registration at the commit it cites has the same
bytes as the evaluator's own, and what the run recorded of its own execution is what the
registration says. A run that fails either keeps its grade and its cost in the
evaluation's listing and enters no table. Under a bound registration a run from a
harness with uncommitted changes stays out as well.

An evaluation names the harness inventory it was held to, by the digest of the inventory's
bytes, and refuses to run without one. Every export the inventory lists as published has
to be stored as recorded, or the evaluation is refused; under a bound registration no
in-scope attempt may be open, while an evaluation under a draft or a frozen one counts an
open attempt and refuses nothing. A stored object the inventory does not list as a current
publication is placed by its key, superseded, unfinished, an orphan or outside the
inventory, and enters no table; one published after the inventory's snapshot invalidates
nothing, since the evaluation is of the snapshot.

## When something goes wrong

No run is replaced after the fact. An evaluation carries the counts of its findings, and
a report has an incident section. Two repairs are kept apart. If the evaluator had a
defect, the same stored runs are evaluated again and both evaluations are kept. If the
execution or the world was compromised, the measurement is run again under an amended
registration and both sets are kept. A set is invalid because a stated condition of the
measurement was breached, never because of its scores.

One incident is computed by the evaluator itself. When two complete reads of one
structured source cannot both be true, the attempt that met them ends by defect, and the
fault is the world's or the execution's and not the system's. A system that reads more is
likelier to meet it. So it is reported by scenario for the whole measurement: which runs
met it and which did not, in every cell, with the runs that are out of the tables read for
it like the ones that are in. Each comparison says how many of the scenarios it paired
carry one. Nothing is excluded for it; whether a world is compromised is a person's
decision the section exists to inform.

A second incident is about an attempt and no scenario. An attempt whose segments ran on
more than one harness commit is listed with its run, its attempt and the commits, whether
its run is in the tables or out of them for any reason. It marks no scenario and enters no
comparison's count.

A third thing is reported apart and is an incident of no scenario. The log fixes what
happened and publication fixes what evidence can be delivered: an attempt whose export
would not construct or could not be published keeps the ending its log gives and is listed
with that ending, the incident and the ledger's figures as three numbers, known
consumption, retained liability and their total, since a retained worst case is not
established cost and an absent export is not zero cost. Its run has no counted attempt,
and a repaired export supports a new inventory and a new evaluation while the earlier one
stands as what was available at its snapshot.

A change to the registration after full-set results exist is an amendment: the old
numbers stay, further results on the same world are exploratory, and confirmation needs
a world from a new seed.
