# What this does not show

This chapter collects the limits in one place, starting with those that most change
what a reader may conclude.

## What was registered, and what was found

The evaluation carries the label *reported*: it ran once, under a registration bound to
the measurement world, and the primary comparison was the investigator against full
context at the padded level on correct whole. The registration reads a comparison as an
interval and never as a test of superiority, and the primary interval,
{{pin:difference.agent.full_context.padded}}, excludes zero. No other comparison carries a
claim. The evaluator that produced the evaluation artifact ran at a commit that differs by two
files from the commit at which the registration was bound; both are fixes to the
evaluator's cells and entrypoint made after the bind. The artifact names both files, and
the registration's bytes are the bound ones.

## One world, one repeat, one model

The intervals describe variation across scenarios of this generator in one organization
of about thirty people, with one run per scenario. They say nothing about run-to-run
variability. During development, a repeat under identical prompts at temperature zero
reproduced its runs exactly; that repeat covered a handful of runs and is not part of
the reported evaluation. In every system measured, one model, Claude Haiku 4.5, played
every role. Nothing here says how a different model, or the same model at another
temperature, would rank. A change to the registration after these results, which a
changed system would need, makes later evaluations on this world exploratory by the
registration's own rule; confirmation needs a world from a new seed.

## The padded level was chosen so the baseline would fail

The systems already differ at the base level. Padding reverses the ranking of the
investigator and full context, and the padded size was the smallest candidate at which
full context already failed on at least one calibration scenario of a development
world, chosen before the measurement world existed. The calibration's denominator was
six scenarios. The primary comparison therefore sits at a level chosen to expose the
single call's limit, and a reader should treat the padded result as a finding about
that regime only.

## Output saturation is the mechanism, and only that

The one-call readers' answers did not fit the output budget they ran under, and the
stopped calls are recorded in the exports, call by call. How many of their lost
scenarios the stopped calls account for is not recorded. The stop is not evidence of an
input-context limit, and the report makes no claim that the model could not read the
padded request. A one-call reader with a larger output allowance, or a batched
finalization, would face a different comparison. The investigator's level invariance,
the same count and the same six misses at both levels, is one world's finding; a world
padded past this level's request size would test it again.

## The registered ranges are envelopes, not bounds

The registration recorded the full-context request size per level from the six
calibration scenarios: {{pin:level.base.full_context_input_tokens}} tokens at base. The
thirty reported base-level runs measured {{pin:observed_input_tokens.full_context.base}},
above the registered upper end, and the padded runs measured
{{pin:observed_input_tokens.full_context.padded}} against the registered
{{pin:level.padded.full_context_input_tokens}}, an overlap rather than containment. The
scenario sets differ, so neither is an error. Still, a range recorded from six
calibration scenarios need not contain the values observed on thirty.

## What the audit establishes

The measurement world's acceptance rested on the validator's verdict over every record
and on spot checks: {{pin:audit.measurement.traces}} scenarios traced end to end by the
audit method and {{pin:audit.measurement.filler_reads}} filler documents read. Spot checks
establish no defect rate; the untraced scenarios rest on the validator and on the
generator's class contracts. Two separate limits apply. The embargo withholds the
measurement world from readers until the last measurement on it. Independently,
twenty-seven of its scenarios, the thirty less the three traced, have no trace. The
golden world's audit was fuller and its findings are public, though its record stays
with the truth because it holds answer keys; it checks the key against the rules as
coded and against a human reading, and no independent oracle was used.

## The prose is near-template

A text enters the world only when a second model can extract exactly the planted fact
from it, so the prose any system reads is close to template sentences with names in
them. The anchor guard that refuses a stated fact whose quote does not name its subject
is partly a property of that generator. On prose that says "she", the same guard would
cost recall. This limits both realism and measurement. The results test reading what is
stated and say nothing about inference.

## Not run, not built

Four outage cells for full context were registered, and the freeze decided not to run
them. Four supporting comparisons were registered and decided not built before any
result was seen: vector retrieval against full-text retrieval, a multi-agent layout, the
primary contrast under a second model, and a model-authored report against rule
composition. A retrieval arm built later is exploratory on this world. The outage
conditions themselves were exercised once each on a development scenario and are
development evidence only.

## Recorded gaps

The harness records input tokens and calls per run, but no output-token totals. The
model spend is the harness's own pricing from the provider's published rates and has
not been reconciled against the provider's bill for the two days of the runs. No single
figure exists for the milestone's total model spend including development. Run times
are recorded per cell in the evaluation artifact and not reported here. The harness publishes its
own inventory of attempts, and the evaluator checks its listing against that inventory.
This check finds implementation mistakes. It does not prove that every admission was
logged or that nothing was spent outside the ledger.
