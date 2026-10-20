# What the model adds beyond the rules

Every system begins with the same frozen prefetch of structured records: it reads the
leave, enumerates the whole employee set, reads the leaves that overlap the span,
enumerates the components and work items, and reads the events that overlap the span.
Every system composes its report with the same rules. They differ only in what documents
reach the model and how.

*Rules only* reads the prefetch and no document, and calls no model. *Single shot* runs
one fixed full-text query built from the leaver's component names, then one model call
that states facts from what came back. *Full context* puts every document of the corpus
level into one call. The *investigator* runs a tool loop: the model reads in turns
through role-scoped tools over the same records and a full-text search over document
sections, then is asked once, at the end, to state the facts it read with the words
they came from.

## The investigator as built

The investigator is a Python service running the loop on LangGraph, with Claude Haiku
4.5 reached through Amazon Bedrock and its state in PostgreSQL. Four decisions in its
construction are worth a hiring reader's attention, each tied to the failure it
prevents. The event log is the authority: recovery replays the log, the audit reads it,
and the run's export is built from it, so a crashed worker resumes from what was
recorded rather than from a framework checkpoint that might disagree with it. A claim
on a run fences a generation, and a dispatch authorized before the fence and sent after
it is cancelled, so a worker that lost its claim cannot append to a run another worker
now owns. Every model call is authorized against the budget before it is sent, carrying
the input bound it was authorized on and the role's output maximum, and an attempt that
closes without an export lists its known consumption and its retained liability as two
numbers, since an absent export is not zero cost. The evaluator runs under its own
identity, reads exports and never re-reads a vendor, so grading cannot touch the systems
it grades. Before any reported run, the worker was killed at every boundary two
reference runs cross, {{pin:crash_matrix.rows}} rows in all, recovering as forecast
once two forecasts had been corrected, and the integration level of the test suite runs
the real log against a PostgreSQL service.

## The rules alone

Rules only is the measure of what the structured records are worth. At both levels it is
correct whole on {{pin:whole.rules_only.base}} of {{pin:scenarios.per_arm}} scenarios:
all {{pin:whole.rules_only.base.tier.structured}} of the structured tier and none of the
other twenty. That is its observed performance, and it is also the design intent, since
the structured tier was built to need no prose and the other two to need it. On
{{pin:empty_reports.rules_only.base}} of the twenty it misses, it reports nothing at
all, because the prefetch holds no impact for the rules to work from. On the rest it is
confident and wrong: it assigns cover where the truth is that nobody qualified exists,
or calls a candidate viable when a comment says otherwise, because nothing it read says
otherwise. Every claim rules only makes is reproduced by its own reads. This is the
distance between grounded and correct described in chapter 2, and it is also the room
any model-reading system has: {{pin:headroom.base}} scenarios at each level.

## One retrieval, one call

At the base level, single shot is correct whole on {{pin:whole.single_shot.base}} of
{{pin:scenarios.per_arm}}. It keeps the structured tier, takes all
{{pin:whole.single_shot.base.tier.adversarial}} of the adversarial tier, and finds
{{pin:whole.single_shot.base.tier.fragmented}} of the fragmented ten. One query over the
leaver's component names reaches the documents the adversarial scenarios turn on, a
stale record beside a newer one, a need with no holder. Of the
{{pin:mechanism.agent.padded.denominator}} prose facts the fragmented and adversarial
scenarios need, its query returned {{pin:mechanism.single_shot.base.returned}} and the
model stated every one it was given; the rest sat in documents the query did not name.

The investigator at the base level is correct whole on {{pin:whole.agent.base}}: the
structured ten, the adversarial ten, and {{pin:whole.agent.base.tier.fragmented}} of the
fragmented. Against single shot that is a paired difference of
{{pin:difference.agent.single_shot.base}}, with the lower end at zero, so a difference
of zero is not excluded. At this corpus level, where everything a scenario needs is a
short search away, the loop's extra reads buy two scenarios and the interval does not
separate the two systems.

![Scenarios correct whole by tier, system and corpus level. The structured tier needs no prose and every system holds it; the two prose tiers are where the systems differ, and where the padded level moves the one-call readers.](tiers.png)

## What a model adds, read by tier

Reading the tier figure column by column: the structured tier is ten for every system
at every level, so the model adds nothing there. The adversarial tier goes from none
under the rules to ten for every model-reading system at the base level: the traps are
findable, and finding them is a matter of reading the document that holds the
contradiction or the absence. The fragmented tier is the hard column. The rules find
none of it, one retrieval finds {{pin:whole.single_shot.base.tier.fragmented}}, the loop
finds {{pin:whole.agent.base.tier.fragmented}}, and only the call shown every document
finds all ten. That last column is the subject of chapter 4, because at the padded level
it is the one that changes.

At the padded level single shot falls to {{pin:whole.single_shot.padded}}, the same count
as rules only and on the same scenarios. {{pin:stopped.single_shot.padded}} of its calls
stop at the output maximum; its query returned
{{pin:mechanism.single_shot.padded.returned}} of the needed facts and the model stated
none of them, so its contribution at this level is exactly nothing and the rules'
report stands alone. The investigator's counts do not move. The model's contribution,
then, has three parts: ten scenarios of trap-finding that any reading which finishes
its call buys, a few
scenarios of scattered prose that depend on how the reading is done, and a dependence
on the call finishing, which chapter 4 measures.
