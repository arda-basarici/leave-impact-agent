# When the loop helps, and when full context does better

The central comparison in this report is between the investigator and a system that
reads everything in one call. At the base level the single call wins. At the padded
level it stops. This chapter gives both results, the mechanism the records show for the
second, and what the experiment can and cannot say about why.

## At the base level, the single call is correct on everything

With no filler in the corpus, full context is correct whole on
{{pin:whole.full_context.base}} of {{pin:scenarios.per_arm}} scenarios. The
investigator is correct whole on {{pin:whole.agent.base}}. The paired difference,
investigator less full context, is {{pin:descriptive.agent.full_context.base}}: the
single call passes six scenarios that the loop fails, and the loop passes none that the
single call fails (both, loop alone, single call alone, neither:
{{pin:descriptive.agent.full_context.base.two_by_two}}). This is a descriptive
comparison, not the registered one, and it is stated first because it is the half of
the result a reader could otherwise miss. When the whole corpus fits one request with
room to answer, a model shown all of it and asked once is the best reader at this level.

## Why the corpus was padded

That base-level result was foreseen, and it is the reason the benchmark has a padded
level. Before the harness, or any model-reading system, was built, a probe on a
throwaway world put the whole corpus, about ten thousand tokens, in front of one call to
the development model. The call scored at the ceiling. On a corpus that small a loop
could at best tie the single call, so the comparison the benchmark exists for had no
room above the baseline. Padding the same world to about
a hundred thousand tokens brought the same call down to stating two thirds of the
planted facts with inventions among them. Those are preliminary numbers from one world
and one model, recorded as a direction and not a result. The direction was that a
second, larger workload was needed beside the small one; where a loop earns its place
was not tested.

So the measurement world carries the filler pool described in chapter 1, and the base
level keeps the small regime while the padded level adds a larger one. The padded
level's size was chosen by a rule written before the calibration runs: the smallest of
three candidate paddings at which full context is not correct whole on at least one
calibration scenario of a development world, never enlarged afterwards. The rule as
written said "on every calibration scenario", which no candidate could satisfy, and the
freeze read it as "at least one" and said so. Full context graded the same at all three
candidates, so the rule chose the smallest, a full-context request of about
{{pin:calibration.padded_level_tokens}} tokens: {{pin:level.padded.filler_documents}}
filler documents, registered as {{pin:level.padded.full_context_input_tokens}} input
tokens against the base level's {{pin:level.base.full_context_input_tokens}}. The padded
level was chosen so that the single-call baseline would fail on a development world,
before the measurement world existed, and the calibration that chose it had six
scenarios.

## At the padded level, the single call stops

At the padded level full context is correct whole on {{pin:whole.full_context.padded}}
of {{pin:scenarios.per_arm}}. Its level contrast, padded less base, is
{{pin:level_contrast.full_context}}, and the loss is entirely on the two prose tiers.
The exports record the mechanism directly: {{pin:stopped.full_context.padded}} of its
calls ended at the registered output maximum of
{{pin:roles.full_context.reader.max_tokens}} tokens with the fact batch cut off. That
maximum is the output setting the systems were developed under, carried into the
registration unchanged; it bounds what a call may write, not what it may read. What the
call is asked to write explains why it matters. The one-call reader is instructed to
state every fact of four kinds that the supplied text asserts, each with its exact
quote, in one call, so what it produces is an inventory of facts for the rules, not the
coverage report, and padding grows the text that inventory is drawn from. Exhaustive
extraction over more text is an output-volume problem under a fixed single-call
allowance. A call that stops inside a tool use returns its arguments as an empty object,
so none of the facts the model had begun to state survive. Single shot shows the same
pattern: {{pin:whole.single_shot.base}} at base and {{pin:whole.single_shot.padded}} at
padded, with {{pin:stopped.single_shot.padded}} of its padded calls stopping at the same
wall; its level contrast is {{pin:level_contrast.single_shot}}.

The stopped calls and the failed scenarios overlap but are not the same set. Of full
context's sixteen padded failures, {{pin:stops.full_context.padded.stopped_and_failed}}
had a stopped call and {{pin:stops.full_context.padded.not_stopped_and_failed}} did
not; {{pin:stops.full_context.padded.stopped_and_passed}} stopped calls belonged to
scenarios that passed anyway. Of single shot's twenty failures,
{{pin:stops.single_shot.padded.stopped_and_failed}} had a stopped call and
{{pin:stops.single_shot.padded.not_stopped_and_failed}} did not. So most padded
failures coincided with a cut-off call and some did not, and a cut-off call was not a
failure where the scenario needed nothing it was cut off from. The malformed fact batch
is the concrete mechanism; the overlap alone does not say how many scenarios a larger
allowance would have passed.

The obvious objection was tested before the runs. A task-relevant instruction, asking
only for facts about the person on leave, was probed against the exhaustive one on the
calibration world: it nearly ended the stops, none of six full-context calls and one of
six single-shot calls, and restored little of what was missed, trading saturation for
under-statement, so the registration kept the exhaustive instruction for both one-call
readers. That probe is development evidence and sits outside the reported
comparison.

![Scenarios correct whole out of thirty for each system at each corpus level, with Wilson intervals at {{pin:statistics.confidence_percent}} percent. Filled marks are the base level, hollow marks the padded level.](headline.png)

The investigator is correct whole on {{pin:whole.agent.padded}} at the padded level, as
at the base. Its level contrast is zero in every resample
({{pin:level_contrast.agent.two_by_two}} paired), and the same six scenarios fail at
both levels. The registered primary comparison, the investigator against full context
at the padded level, is {{pin:whole.agent.padded}} against
{{pin:whole.full_context.padded}}: an observed difference of
{{pin:difference.agent.full_context.padded.points}} percentage points of scenarios, with
a paired interval of {{pin:difference.agent.full_context.padded.points_interval}} points
at {{pin:statistics.confidence_percent}} percent. Both pass fourteen scenarios, the
investigator alone passes ten, full context alone passes none, neither passes six
({{pin:difference.agent.full_context.padded.two_by_two}}). The interval excludes zero.
Against single shot at the padded level the investigator's difference is
{{pin:difference.agent.single_shot.padded}}.

The preceding paragraphs make three kinds of statement, and the report keeps them
apart. The counts and the interval are what was observed. The stopped calls are
recorded evidence of a mechanism: the one-call readers' fact inventories did not fit
the output budget the registration gave them. The experiment cannot establish anything
about input. It does not show that the model could not read a
{{pin:calibration.padded_level_tokens}}-token request, and the freeze ruled, before any
run, that output saturation is reported as such and never as evidence of an input
limit. A one-call reader with a larger output allowance, or one that finalized in
batches, would face a different comparison, and this report makes no claim about it.

## Where the investigator's loss sits

The six scenarios the investigator misses are the most informative result in the
evaluation. All six are fragmented-tier scenarios, and the mechanism measure says where
in the pipeline the facts they need are lost. It follows the
{{pin:mechanism.agent.padded.denominator}} prose facts that the required rows of
twenty scenarios depend on through four recorded stages,
{{pin:mechanism.stage_names}}: whether the document carrying the fact (its *carrier*)
was returned to the run, whether the model emitted the fact, whether the record
admitted it, and whether it was usable by the rules.

![Needed prose facts, of {{pin:mechanism.agent.padded.denominator}}, reaching each stage of the recorded pipeline for the investigator and for full context at the padded level. The bars show where facts stop appearing; they do not say why.](mechanism.png)

For the investigator at the padded level the stages read
{{pin:mechanism.agent.padded.stages}}. Every needed carrier was returned, so retrieval
is complete and the losses occur after it. By subtraction, five facts were returned and
not emitted, and one was emitted and admitted but not usable by the rules. Six missing
usable facts and six failed scenarios are different units, and equal totals do not
establish a one-to-one match; what the funnel supports is that the five omissions sit
at the moment the model is asked to state what it read, a finalization question, and
that the one usability loss needs its own explanation. That is the first thing the next
design pass has to look at. For full context at the padded level the same stages read
{{pin:mechanism.full_context.padded.stages}}: every carrier was in the request, and
almost nothing was stated, which is the stopped call of the previous section seen fact
by fact.

The investigator holds fourteen of the twenty scenarios that any model-reading system
can win, at both corpus levels. That invariance is one world's finding.
