# What a correct answer contains

A system's answer is a report: a set of typed claims about one leave, in a vocabulary
frozen at the world milestone and shared with the answer key. An illustrative example
first, with invented names. Dana is on leave for two weeks. The tracker shows a release
ticket due in that window, so the report claims an *impact*. A policy clause says a
release needs an engineer with iOS experience, so it claims a *constraint* keyed by that
clause. The HR system lists nobody with that skill, but a ticket comment says "Priya has
shipped two iOS releases", so a system that read the comment states that fact with those
words, and the rules then assess Priya as viable and propose assigning her: a *candidate
assessment* and a *coverage action*. A system that never read the comment assesses
nobody as viable and must either leave the impact uncovered or admit an *unknown*. If
the HR record and the comment disagreed about Priya, the report would carry a *source
conflict* naming which the authority rule trusts.

Those are the six claim types. An impact is something the leave affects, a deadline, a
meeting or a standing responsibility. A constraint is what a valid response must obey,
keyed by the policy clause it comes from, so a constraint a system cannot trace to a
clause cannot be expressed at all. A candidate assessment says whether a named person
could cover a named impact, and why. A coverage action says what the plan does about an
impact: assign someone, leave it uncovered, or admit it cannot tell. A source conflict
records two records that disagree and which one the authority rule trusts. An unknown
records a fact the answer needed and the systems did not hold. Every claim carries the
evidence it was read from. A claim's identity is computed from its fields rather than
from an id, so a report and the key can be compared even when their writers assigned
different ids.

## Who writes the claims

No model in this evaluation writes a verdict. A model states facts: this comment says
this person has this skill, and here are the words that say so. The shared rules, the
same deterministic code in every system and in the construction of the key, compose
every claim from the structured records plus the facts a model stated. The rules decide
who is viable, what the plan does, and where an unknown or a conflict stands. The model
only states what it read.

That split was settled by a probe before the harness, or any model-reading system, was
built, on a throwaway world with the development model. Asked to write the whole report
itself in the codec's format, the model was correct on none of six scenarios; five of
the six answers decoded, and most of those missed by one to three rows out of thirty or
more. It failed scenarios the rules get right with no model at all. Asked only to state
what it read, with the rules concluding, the same model reached 26 of 30 on the first
prompt and 30 of 30 after the prompt was amended on that same world. The comparison is
partly circular, because the facts arm concludes with the same rules the key was built
from, and the probe noted this. It set a direction and is not a result. As a result, in
every system here the model reads and states facts, and the rules build the report's
structure.

## Correct whole

The headline check is *correct whole*, and it is all-or-nothing per scenario: the
report is structurally valid, every required claim is present with the right payload,
nothing unexpected is claimed, and the plan it proposes raises no finding against the
key. One wrong assessment in thirty rows fails the scenario. The check is severe on
purpose, because a person cannot approve a coverage plan with one wrong name in it.

Two other checks are registered beside it and carry no claim. *Expected action* reads
the coverage actions alone. *Reproduced whole* asks whether the run's own reads
reproduce every claim it made: the rules are replayed over only what the run actually
retrieved, with its claims as premises, and a claim is reproduced when the rules
conclude it, contradicted when they conclude otherwise, unsupported when they cannot.
That replay is how grounding is measured; no model grades another model.

A claim is *grounded* when the run's own reads reproduce it, and grounded is a different
property from correct. A system that reads no prose can have every claim it makes
reproduced by its own reads and still be wrong wherever the answer lives in prose. A
negative claim, that nobody holds a skill or that no clause applies, can be confirmed
only after every place the answer could live has been read, so a system that read
nothing cannot have its negatives confirmed by silence. Chapter 3 measures that
distance.

## The key is what a run could have found

The expected answer is runtime truth: what a system could obtain from the live records
on the day it runs, not the dated view the generator used while constructing the
scenario. The two were compared on forty seeds before the choice was made. They agree on
every outcome and on every must-assess pair under the normal condition, and they
disagree on {{pin:runtime_truth.other_pairs_differ}} pairs the evaluator derives
itself, which is why the key follows what a run can obtain rather than what the
construction assumed. The key is sealed before any run and read by the evaluator alone.

## The terms were fixed before the world existed

Every number in the results chapters comes from one evaluation under a registration
that was frozen before the measurement world was drawn and bound to it after the world
was accepted. The registration names the four systems and their roles, the two corpus
levels, the three checks, one primary comparison, the confidence level and resample
count, and the budget. It also sets a retry rule: only an infrastructure failure may be
retried, and a fixed rule over the run's own log, not an operator, chooses the counted
attempt. The evaluator reads the file at the freeze commit and refuses to run on a
difference. The evaluation this report cites carries the label *reported*, which the
evaluator derived from that bound registration.

## How the intervals are computed

A single system's pass count carries a Wilson interval at
{{pin:statistics.confidence_percent}} percent, the textbook interval for a proportion
of thirty trials. A difference between two systems is paired on scenario: each scenario
contributes whether the first system passed it and whether the second did, and the
difference is resampled {{pin:statistics.resamples}} times over whole scenarios within
tiers, giving a percentile interval at the same confidence. Every scenario ran once, so
no term for run-to-run variation enters either interval; they describe variation across
scenarios of this generator in one organization and nothing else.
