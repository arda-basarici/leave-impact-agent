# The development protocol

`registration.json` in this folder is the preregistration: the one file that says what the
investigator milestone measures, on what, and how the result is read. This note explains
the file. It restates none of its values; where a number matters, the file is where it is.

## What the file is

One JSON file with a format version, decoded strictly: every field required, an unknown
key refused, and the bytes accepted only if they are the one form the encoder writes. It
is changed through the encoder and never by hand, and a line in `.gitattributes` keeps a
checkout from rewriting its line endings, so the bytes at a commit are the bytes that were
registered.

Names live in the file and behaviour lives in code. The file names a check, a measure, a
prefetch rule, an outage protocol, a reporting policy; the code holds what each name
means. Each consumer compares what the file names with what its own code computes and
refuses to run on a difference. Neither side is ever substituted for the other: a run
that quietly used today's value would cite a registration it did not follow.

## Draft and frozen

The file has a status. A *draft* may hold values that are not chosen yet. Each such value
is written as pending, with a sentence saying what will resolve it, and a pending value
blocks only the execution that needs it: the rules-only baseline runs while the model
systems' entries are still pending. No entry point fills a pending value with a literal.

A draft can have nothing pending and still be a draft. *Frozen* is a statement that the
reporting design is fixed: it refuses any pending value, and it refuses caps and a budget
whose basis is still unmeasured. The freeze comes before the first full-set measurement
and after the calibration runs, when the forecast of the whole registered workload fits
under the spending threshold with what has already been spent. If it does not fit, the
repeat count is cut first, then the two model arms under a corpus outage; the
answer-quality arms are not cut. If it still does not fit, the file stays a draft and the
measurement does not start.

Every dollar figure in the file is a placeholder carried from the design, cumulative over
the milestone, and marked unmeasured. None is a target or an accepted spend. They are set
again from real usage before the freeze.

## What is measured

Three systems, each registered by kind and variant: the investigator, a rules-only
baseline that calls no model and reads no prose, and a single-shot baseline that makes
one model call over the shared prefetch and one fixed retrieval. Each runs under every
registered condition, and a system under a condition is an *arm*.

A condition is the set of sources scheduled unreachable for a whole run, injected where
the system reads. Conditions are reported in one of two ways, and the name describes the
assignment and its reporting, never how a run turned out:

- *Answer quality.* Every source reachable, or one whose outage still leaves an expected
  answer. These arms carry the full tables and the comparisons between systems.
- *Degraded condition.* The outage leaves the leave or the policy unreadable, so no
  claim-level answer exists. These arms carry the accounting, the cost and a table of what
  the runs did: whether the run met its outage, how it ended, whether it reported
  anything, and what its own reads make of what it reported.

A run is counted in the arm it was assigned to and graded against the condition its own
reads show. A system that never called the failed source ran under no outage and is still
a run of the outage arm, counted there as unexercised.

## How a run is counted

Every arm runs each scenario the registered number of times. A run that was intended and
never made does not pass in the end-to-end reading; it is not left out.

A run is retried after an infrastructure failure and after nothing else. A defect is not
retried, because a retry could hide it. The attempt that counts is the earliest one that
did not fail by infrastructure, or the last when all did. Every attempt is kept and
summarized beside the counted ones, so a failure a retry recovered from still shows. A
run whose attempt numbers have a gap has no attempt that can be shown to be the counted
one: it keeps its grade and its cost, enters no quality estimate, and is counted under
its own reason.

A run that carries a finding (its reads differ from the sealed world, an operation no
conforming harness records, a cost that does not add up, a prefetch that is not the
registered plan) stays in the tables and is counted beside them. Keeping a run is not
vouching for it.

## How the result is read

Three yes-or-no checks are registered by name, each defined mechanically in the
evaluator: whether a report is correct in every part against the expected answer, whether
its coverage actions are the expected kind, and whether the system's own reads reproduce
every claim it made. Each is read two ways: over the runs the check applies to, and end
to end over every run a scenario was meant to have.

The primary comparisons are the investigator against each baseline on the first check,
end to end, under the normal condition, over the primary scenario set. Tier breakdowns
are supporting results named in advance. Everything else is descriptive. No comparison
is registered as a test of superiority: a difference is reported with its interval, and
when the interval crosses zero the report says it includes differences in either
direction. It never says the systems are equivalent. The intervals are wide at this size.

The measures are registered by name too, in families: the answer side over all claims
and per claim type, grounding and citations over graded and limited runs apart, source
discipline, retrieval. A comparison between two systems is made on a family's leading
row; the rest are reported per arm.

## The scenario sets

A small number of scenarios from each tier are *development* scenarios: the ones prompts
and settings are tuned on. They were selected by tier alone, by a draw seeded from the
file, with no expected answer read, and are listed in the file as bare ids. The file
carries no tier beside an id, because a scenario's tier is sealed and this repository is
public.

Every other scenario is in the *primary* set, held out from scenario-specific tuning.
The primary results are over that set. All scenarios are also run and reported together
as a supporting summary. The held-out scenarios share the organization and the
generator's conventions with the development ones, and the report says so; a world from
another seed is the stronger design and is reopened if the budget leaves room.

Once listed, the development scenarios are not redrawn. A later change of seed must not
disown the scenarios the tuning was done on.

## What an evaluation is labeled

The label is derived by the evaluator from the registration it reads and stored in the
evaluation; no run labels itself.

- Under a draft, an evaluation is *development*.
- Under a frozen registration it is *reported*.
- A frozen registration that says it amends an earlier one, and that full-set results on
  this world existed when it was written, gives *exploratory* evaluations. Those two
  statements are the registration author's. No job can read earlier evaluations to check
  them, so an evaluation carries them as declared.
- A run whose cited registration cannot be found in the repository's history is
  *unknown*.

A run enters the tables only when the registration at the commit it cites has the same
bytes as the evaluator's own, and what the run recorded of its own execution is what the
registration says. A run that fails either keeps its grade and its cost in the
evaluation's inventory and enters no table.

## When something goes wrong

No run is replaced after the fact. An evaluation carries the counts of its findings, and
a report has an incident section. Two repairs are kept apart. If the evaluator had a
defect, the same stored runs are evaluated again and both evaluations are kept. If the
execution or the world was compromised, the measurement is run again under an amended
registration and both sets are kept. A set is invalid because a stated condition of the
measurement was breached, never because of its scores.

A change to the registration after full-set results exist is an amendment: the old
numbers stay, further results on the same world are exploratory, and confirmation needs
a world from a new seed.
