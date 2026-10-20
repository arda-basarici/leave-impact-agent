# What it was measured on

The systems in this report were measured on a synthetic organization whose answer key
was written before any of them ran. That ordering is the point of the instrument. A
benchmark labeled after the fact inherits the labeler's reading. A constructed one has
no labeler, so the question becomes whether the construction can be trusted. This
chapter describes how the organization is built and how its truth is checked, and says
what a reader still has to take on trust.

## One organization, thirty scenarios

The generator builds one organization from a seed. The golden world described below has
{{pin:golden.people}} people in {{pin:golden.teams}} teams, and the measurement world is
of the same size. Its records are spread across four systems of record: an HR system
holding people, skills and leave; an issue tracker holding work items and their
comments; a calendar holding meetings; and a document corpus holding policies, runbooks
and client notes. Into that organization the generator plants
{{pin:scenarios.per_arm}} leave scenarios in three tiers of ten. A *structured* scenario
can be answered from records alone: who is on leave, which deadlines and meetings fall in
the span, who else holds the skill. A *fragmented* scenario depends on facts that live
only in prose, a qualification mentioned in a ticket comment, a responsibility named in
a runbook paragraph, a staffing clause in a policy. An *adversarial* scenario plants a
trap: a stale record contradicted by a newer one, a fact that exists nowhere, a need no
one can cover.

Each scenario belongs to a class, and a class states what it needs as a query over the
organization. A seeded choice picks one admissible construction, plants the entities
and writes the expected answer. The shared rules that every system later uses to compose
its report are then run over the planted truth as a consistency check: if the rules and
the construction disagree, that is a named construction error, never a retry. The check
shares its rules with every system, so a defect the rules themselves carry would pass
it; the audits described below are the check on the rules. The same
rules are asked again under each single-source outage, which is how the key records
which sources a scenario's answer depends on. Not every seed yields a world; a refusal
is recorded and reported, never repaired.

## Prose enters through a gate

Records are planted directly, but prose goes through a gate. A language model writes
the comments, runbook paragraphs and policy clauses from a brief that carries facts,
never sentences. A text is accepted only if two checks pass: a model of a different
family must extract from it exactly the planted facts and nothing else, and a lexical
guard must find no name outside the brief's scope. On the golden world a person also
read every text that would change an answer. A generation that fails is discarded, not
patched. Accepted text becomes immutable world data, and the world's version is the hash
of what was realized, not of the seed, so two worlds from one seed with different prose
are two worlds. The gate also sets a limit chapter 6 returns to: prose accepted only for
being extractable is near-template prose.

## Validation, sealing, and who may read what

A world is written into live systems (a Frappe HR site, a Jira project, Google
calendars and an object store), and a validator with its own read-only credentials
reads them back. It approves a world only when every enumeration is complete and every
record equals its planting, {{pin:validator.measurement.exactness}} exactness kinds and
seven fidelity kinds, and when each scenario's view under the runtime rule matches the
key. A world is served only on a verdict that judged its current manifest under the
current validator version; when the validator gains a check, every served world is
re-judged.

Three sealed artifacts serve three readers. The world specification is private to the
benchmark. The scenario specifications are what a system may see. The truth manifest,
the answer key, is readable by the evaluator alone: the role the application runs under
has no capability over the bucket that holds it, every final object is a create-only
write with a recorded version, and a boundary probe on every deployment checks that the
application still cannot reach the key.

![The instrument. One generator produces two worlds through the same pipeline; validation precedes measurement; the application never holds a capability over the truth bucket; the measurement world's contents and seed stay withheld.](instrument.png)

## Two worlds

Two worlds matter here. The *golden world* is open in its seed and recipe, and it
carried the benchmark's audit. Every one of its {{pin:golden.audit.acceptance_scenarios}}
scenarios passed a human acceptance pass, {{pin:golden.audit.deep_traces}} received a deep
trace from the planted records to the key's outcome, a panel of four model reviewers
read the audit blind with every disagreement adjudicated by hand, and the audit record
was sealed under its content address. The audit's findings
are public; its record holds answer keys and stays with the truth. The *measurement
world* is the one the numbers in this report come from. Its seed was drawn from thirty-two
bytes of entropy after the registration was frozen, so no system was tuned against it.
It was validated under validator version 2, {{pin:audit.measurement.traces}} of its
scenarios were traced by the same audit method with a blind model reader, and
{{pin:audit.measurement.filler_reads}} of its filler documents were read to confirm they
name nothing of the world. Its version is public; its contents, its seed and the digests
that would identify them are withheld until the project's last measurement on it, which
is why this report cites its results and not its contents.

The measurement world also carries something the golden world does not: a pool of filler
documents, requirement-style texts about fictional releases and clients that no scenario
owns. A *corpus level* is a count from that pool. The base level includes none of it; the
padded level includes the first {{pin:level.padded.filler_documents}}. Levels nest, every
answer-bearing document is in every level, and a test holds that a world assembled with
the pool and then stripped of it equals the world assembled without, field for field. So
the answers are the same at both levels, and only the amount a system has to read
changes. Chapter 4 explains why the padding exists.
