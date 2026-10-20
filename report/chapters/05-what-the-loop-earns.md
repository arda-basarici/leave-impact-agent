# What the loop earns

A comparison of answer quality alone would flatter whichever system reads most. This
chapter puts cost beside quality. It first states what was fixed before any reported
run, since costs mean something only relative to the budgets the systems ran with.

## Fixed before the runs

The registration was frozen before the measurement world was drawn. It fixed each
system's budget as a cap on calls and on tokens, derived from a calibration on a
development world: twice the call count of the largest completed calibration run, with
a floor of eight, and twice its counted tokens rounded up to ten thousand. The
investigator may make {{pin:caps.agent.calls}} calls and spend
{{pin:caps.agent.tokens}} tokens; single shot {{pin:caps.single_shot.calls}} and
{{pin:caps.single_shot.tokens}}; full context {{pin:caps.full_context.calls}} and
{{pin:caps.full_context.tokens}}, its token cap being the model's window less the output
maximum; rules only, which calls no model, {{pin:caps.rules_only.calls}} and
{{pin:caps.rules_only.tokens}} as the floor the cap rule sets. A run that reaches a cap
is graded on what it has and reported as capped. None of the {{pin:runs.total}} reported
runs reached one.

The registration also fixed the money: {{pin:budget.expected_usd}} expected and
{{pin:budget.ceiling_usd}} as the ceiling, cumulative over the milestone, with the
measurement phase itself forecast by hand at about {{pin:forecast.phase_usd}} from the
calibration's per-run figures. It also fixed what counts: one run per scenario; a retry
only after an infrastructure failure, never after a defect; and a counted attempt
chosen by a rule over the run's own log, not by anyone's judgment. Every run closed on
its first attempt, so the retry rule was never exercised.

## What the measurement cost

The {{pin:runs.total}} runs cost {{pin:cost.total_usd}} in model calls, priced from the
provider's published rates by the harness itself; a cost with a missing counter is
recorded as incomplete and never priced as zero, and no cell here has one. That figure
covers the measurement workload only. Development runs, the calibration, and the
generation of the worlds were paid separately, and no single reconciled figure exists
for them; chapter 6 records this as a gap.

| System and level | Cost of the cell | Per run | Calls per run | Input tokens per run | Correct whole |
|---|---|---|---|---|---|
| Investigator, base | {{pin:cost.agent.base.usd}} | {{pin:cost.agent.base.per_run_usd}} | {{pin:calls_per_run.agent.base}} | {{pin:observed_input_tokens.agent.base}} | {{pin:whole.agent.base}} |
| Investigator, padded | {{pin:cost.agent.padded.usd}} | {{pin:cost.agent.padded.per_run_usd}} | {{pin:calls_per_run.agent.padded}} | {{pin:observed_input_tokens.agent.padded}} | {{pin:whole.agent.padded}} |
| Full context, base | {{pin:cost.full_context.base.usd}} | {{pin:cost.full_context.base.per_run_usd}} | 1 | {{pin:observed_input_tokens.full_context.base}} | {{pin:whole.full_context.base}} |
| Full context, padded | {{pin:cost.full_context.padded.usd}} | {{pin:cost.full_context.padded.per_run_usd}} | 1 | {{pin:observed_input_tokens.full_context.padded}} | {{pin:whole.full_context.padded}} |
| Single shot, base | {{pin:cost.single_shot.base.usd}} | {{pin:cost.single_shot.base.per_run_usd}} | 1 | {{pin:observed_input_tokens.single_shot.base}} | {{pin:whole.single_shot.base}} |
| Single shot, padded | {{pin:cost.single_shot.padded.usd}} | {{pin:cost.single_shot.padded.per_run_usd}} | 1 | {{pin:observed_input_tokens.single_shot.padded}} | {{pin:whole.single_shot.padded}} |
| Rules only, both levels | {{pin:cost.rules_only.base.usd}} | {{pin:cost.rules_only.base.per_run_usd}} | 0 | 0 | {{pin:whole.rules_only.base}} |

Per-run cost is the cell's total divided by its thirty runs. The input-token column is
the lowest and highest run in the cell; the investigator's figure is summed over its
calls.

![Per-run cost against scenarios correct whole, one mark per system and level. Filled marks are the base level, hollow marks the padded level; rules only sits at zero cost.](cost-quality.png)

## Reading cost against quality

At the base level the investigator costs more than the single call shown everything
and is correct on fewer scenarios: {{pin:cost.ratio.agent_to_full_context.base}} times
the cost per run, {{pin:cost.agent.base.per_run_usd}} against
{{pin:cost.full_context.base.per_run_usd}}. If the corpus fits one request with room to
answer, there is no case for the loop in this evaluation, on quality or on cost.

At the padded level the single call shown everything is both more expensive and less
accurate than the investigator. It now costs {{pin:cost.full_context.padded.per_run_usd}}
a run, more than the investigator's {{pin:cost.agent.padded.per_run_usd}}; the report
does not decompose that rise between the level's input and the call's output. It is
also correct on
{{pin:whole.full_context.padded}} scenarios to the investigator's
{{pin:whole.agent.padded}}. The investigator's cost barely moved between levels; it
reads what its searches return and the filler is answer-neutral, though how many filler
documents its searches returned was not measured. Single shot stays the cheapest
model-reading system at {{pin:cost.single_shot.padded.per_run_usd}} a run and, at this
level, buys nothing over the rules.

What the loop earns, then, is stated conditionally. On a corpus that fits one request
with room to answer, it earns nothing and costs more. On the padded corpus, where the
one-call readers run out of output, it holds its quality and its cost while they lose
theirs. Whether a real organization's records resemble either corpus is outside this
evaluation, and whether the loop's advantage survives a one-call reader with a larger
output allowance is a question it did not pose.
