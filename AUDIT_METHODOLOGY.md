# The hand audit: how a generated world becomes a golden set

A generated world becomes golden only after a human has read every scenario's answer key
against the records that were planted and every model-written text against the facts it
was asked to carry. This document is the method of that reading, published so that the
claim "golden" can be judged. The audit's own output (the rendered sheet, the rulings
record, the summary and the index that binds them) holds the benchmark's answer keys and
stays in the truth bucket, written once beside the world; nothing of it appears here.

## 1. What the audit adds to what the machine already proved

Before the audit runs, the validator has proved that the vendor projection matches the
sealed world (exactness and fidelity checks, every scenario's agent-visible view), and the
generator's own whole-world verification has proved that the sealed key equals what the
rules derive from the planted facts on every day of each scenario's stable interval. The
audit does not repeat either proof. It asks the two questions no rule can answer about
itself:

- Is the constructed truth right: is the key the answer a careful person would give for
  these plantings, read as an organization's records rather than as data structures?
- Does every model-written text say what it was asked to say and nothing more that
  would change an answer?

A defect found by the audit is a defect of the generator, fixed once and answered by a new
world version beside the old, never by editing a sealed world.

## 2. The artifacts

- **The audit sheet**, rendered from the sealed objects by a committed script, one
  markdown file, scenario by scenario in the plan's order. Per scenario: the asked line
  (whose leave, when is now, the investigation window); the key (impacts and their
  authored verdicts, constraints, distractors, required sources, expected conflicts and
  unknowns); the outcome witness (below); the plantings with their observable-from
  dates; the authored facts; the fact-base rows the scenario cites, each with source,
  field and observable-from date, the rows observable only after now (other
  scenarios' later plantings on the same entities) listed apart under their own
  heading; the criterion universe (below); the prose targets with their briefs, attempts,
  refusals and the checker's propositions beside the accepted text. Before the
  scenarios, a provenance header and the rollups the prose check reads (attempts per
  register, refusals by guard and by reason, opening frames). The sheet is
  regenerable and read-only; its digest is cited by everything written about it.
- **The outcome witness.** A key's outcome is a claim over the whole candidate
  universe, while the key's must-assess list names only the authored subset an agent
  must state, so a reader cannot recompute the outcome from the key alone. The sheet
  therefore renders, per impact, the generator's own assessment of every employee at
  the scenario's now under the dated view: the need's facts, the viable named, every
  non-viable with its reasons and the facts that produced them, every unknown with its
  unresolved question, the derived outcome and its agreement with the key. The witness
  is not a second implementation of the rule. The semantic world is rebuilt from the
  sealed provenance by the generator's own assembly, admitted only when its semantic
  digest equals the sealed one, and the three calls the whole-world verification makes
  are rendered for the one day the run is asked about. A witness that disagrees with
  its key is reported, never smoothed over.
- **The criterion universe.** The witness is the rule's own count, so an uncovered or
  unknown outcome, a claim over every employee, could be read off the sheet but not
  proven from it. The sheet therefore also renders, per impact, every employee's facts
  of the four families the viability criteria read: component memberships; the skills
  the record lists with their sources, or the record's absence; leaves and events over
  the need's window; employment type. It is rendered from the fact base under the same
  dated view with no call to the viability or outcome functions, the need's window
  stated as the checklist states it. The reader derives the active criteria the way
  the trace does and counts; the witness becomes the cross-check. The independence is
  from the rule, not from the data: the dated view and the fact reads are the code the
  rule uses.
- **The checklist.** The working methodology: the universal checks, the class and
  modifier contracts, the prose check, the deep-trace steps. Its digest is bound into
  the audit's index, so a sealed audit says which revision of the method was applied.
- **The rulings record.** One block per scenario, the verdict line first, free notes
  and deep traces beneath, written as the audit runs. The record is history: a reading
  later found imprecise is amended in place with a dated note, never silently rewritten.
- **The summary.** The authoritative reading: what the audit established, grouped into
  the rules it demonstrated with the scenarios that established each; a ledger of
  amendments and superseded readings, so no one infers from the record which sentence
  still stands; coverage observations under their own heading; limitations.
- **The index.** One small canonical JSON object binding the record, the summary and
  the checklist by digest, with the sheet's digest, the world's sealed provenance, the
  validator's verdict, the traced scenario ids per tranche and the coverage note ids.
  Its digest is the audit's identity and names the prefix under which all of it is
  written once. A corrected audit is a new index beside the old, its `supersedes`
  field naming the old one; identities are content-addressed, never ordinal.

## 3. The acceptance pass, every scenario

Four reads in order: the asked line; the key against the plantings; the prose targets
where present; the verdict. The fact-base rows are skipped on this pass; they are the
deep trace's material.

**The verdict** is one line, one of `accept`, `defect` with what is wrong and which
check, or `question` with what could not be settled. A preference (a dull scenario, an
odd title, a name pairing) is a note beside an accept, never its own verdict.

| Bucket | Meaning | Consequence |
|---|---|---|
| Defect | The key would be a wrong answer, or a text is a wrong witness. | Blocks golden. Batched: finish the pass, fix the generator once, regenerate once as a new version. |
| Preference | The construction is correct but would have been shaped differently. | A note in the record. Never blocks golden. May become a generator improvement. |
| Question | Cannot be settled from the sheet. | Parked for the deep trace or the interview, then becomes accept or defect. |

**The universal checks** run on every scenario and are the whole check for the
structured tier.

| Check | Passes when |
|---|---|
| Window | Now falls inside the investigation window, and the investigated leave overlaps it. |
| Observability | Every planting's observable-from date is at or before now. |
| Collision | Each impact's artifact truly collides with the leave: a ticket the leaver owns, open, due inside the leave span; a meeting on a leave day the leaver attends; a responsibility, a document section naming the leaver as responsible, or an open undated work item the leaver owns, read at the dated view. |
| Verdict reasons | Each must-assess verdict's reasons hold in the plantings: availability is the person's own leave over the need's window or, for a meeting need only, another event overlapping the meeting; skill is a record, or a text, lacking it; hard rule is the employment type; component is not being a member. |
| Outcome rule | With V viable and U unknown over the whole organization against the required count n (the largest count over the clauses that apply, one when none does): V at or above n is assign; V plus U below n is uncovered; anything else is unknown. The witness's agreement line is read for every scenario; its counts are read wherever the authored subset cannot decide the outcome (an assign with at least n authored viable candidates is decided from the key alone); and every uncovered or unknown outcome is recounted by hand from the criterion universe, the witness then the cross-check. |
| Distractors | Each named distractor is not an impact, for exactly the reason stated. |
| Org coherence | Names and titles read as one organization: no two people with the same name inside one scenario; tickets and meetings named for the component or team they sit in. |

**The class checks** run where the scenario's heading names the class, and test what the
class promises, not a paraphrase. The structured classes promise a structured impact only
(a deadline, a meeting, or both). The fragmented classes promise that an answer-changing
fact lives in prose: a cover's qualifying skill only in a ticket comment while the HR
record lacks it; an obligation in a client-note section with a procedure clause
constraining that section to a skill holder; a release policy requiring two people of a
given skill and employment type, with exactly two viable employees, one contractor
holding the skill and one employee lacking it; or one section carrying both the
responsibility and the cover's otherwise-missing qualification, each answer-changing on
its own. The adversarial classes promise a trap: a runbook naming an outdated owner
against the tracker, resolved to the tracker under the stated authority rule; a release
under a clause requiring a skill nobody holds, in a component holding a member with no
skills record, so the outcome is unknown; the same shape in a component with no such
member, so the outcome is uncovered; or the conflict seated in the missing-information
component. Each fragmented and adversarial class row states exactly which verdicts,
unknowns and outcome the construction must produce; a structured row states the
class's promise (which teammate is the near-miss, and why), tested by a check of its
own since the first audit's panel.

**The modifier checks** run where the heading names the modifier. Four modifiers are
distractors and one is candidate pressure. A wrong-team look-alike in the same component
is owned or attended by another team's person, and the leaver is not on it. An
already-resolved ticket the leaver owned entered the world on its resolution date, never
before. An outside-window artifact sits exactly one day outside the leave span, on either
side, measured against the leave and not the investigation window. A timezone-boundary
event at the leave's edge falls the day before or after in the reference zone and inside
in the far attendee's zone. Concurrent leave gives an authored viable candidate an
approved leave over exactly the investigated span, and their verdict on every impact
they were authored for must carry availability, beside any reason the record already
gave them.

**The prose check** runs on every model-written text. Each required fact is ticked
against the text: stated plainly, without a hedge; a hedge on a required fact is a
defect. A second read looks for anything beyond the required and allowed facts that
would change an answer (a membership, an ownership, a date, a skill, an assessment of the
work); any such extra is a defect. The checker's propositions line is compared with what
the reader saw; something the reader sees that the checker did not is a recall finding
against the containment gate, recorded as a question, not as a defect of the text. Two
rulings the first audit produced in the run, carried into the checklist's next revision
rather than bound in the one it sealed: a sentence that maps to no predicate of the
vocabulary is non-predicate prose, not a recall failure; and register conformance
beyond the fact contract (a component named where the register forbids it, say) is a
prompt-adherence finding at its measured rate, never a defect of the world.

## 4. The deep trace

A stratified subset of scenarios, chosen so that conflict, missing information,
uncovered, free-text qualification and the cardinality clause each appear and every
modifier appears, is traced to its evidence after the acceptance pass; a second tranche
may follow, chosen by the structures the first left unexercised rather than by count,
and a third from a design panel's reading of the record (section 6).
Each trace follows one shape and is written under the scenario's block in the record.

1. **Asked, dated view.** The leaver and the leave; now; the investigation window; the
   stable interval; the need's window per impact (the investigated leave's span for a
   deadline or a responsibility, the meeting's own day in the reference timezone for a
   meeting); confirmation that every relevant planting is observable by now.
2. **Impact evidence.** The impact followed back to the minimum fact-base rows that
   establish it, each with source, field and observable-from date. The required sources
   are the sources of these rows and of the rules' other questions under each source's
   outage: a source is required when a grounding, a verdict, an outcome or a conflict
   moves without it, so a closed multi-source predicate can require a source no cited
   row comes from, and a source hosting only a distractor is not required.
3. **Candidate facts.** First the criterion set, derived from the need the way the rule
   derives it: component, only when the artifact is a work item with a readable
   component; availability, leave overlapping the need's window and, for a meeting,
   attendance at another event overlapping it, the target meeting never disqualifying
   its own attendee; then each applicable clause's criteria, a clause applying when it
   names the artifact or its component. Then, per graded person, only the facts those
   criteria ask about. The check: the key's reason set equals the set of criteria known
   to fail, since the rule lists every failing reason independent of evaluation order
   and a known failure dominates an unresolved question; an unknown rests on named
   unresolved criteria with none known to fail.
4. **Prose check**, where the key's evidence enters through a model-written text: the
   required facts stated plainly and extracted, no further answer-changing proposition,
   the class promise the text fulfils, reading hazards noted here.
5. **Distractors.** For each named distractor, what a careless filter would have
   included it on, and the exact fact or rule that excludes it.
6. **Authority.** None, said so; or both contradictory rows with their sources and the
   authority rule that chooses one.
7. **Outcome recomputed** from the witness and the criterion universe: viable, unknown,
   non-viable, the requirement, the rule applied mechanically, the people behind an
   exceptional bucket named. A scan of cited rows elsewhere in the sheet is
   corroboration and never the proof; the witness over the rebuilt world is the count,
   and for an uncovered or unknown outcome the hand count over the criterion universe
   is the proof with the witness as its cross-check.
8. **Observations**, informative and not needed for correctness, marked non-ruling.
9. **Open questions and rulings.** A trace is not forced closed to finish.
10. **Conclusion.** Whether every expected claim has a complete evidence path; any
    carried note or defect; the effect on the block's verdict.

Two disciplines run through every step. A statement about how a rule behaves is read in
the code at the time of the trace, not remembered, and where the trace relies on code
behaviour the sheet does not show, the trace says so and names the module. And the
sheet's cited rows are a projection for the key, never an exhaustive serialization of
the world: the witness may classify a person on a world fact no cited row carries, so
whole-sheet counts corroborate; the criterion universe renders the four fact families
the criteria read for every employee, and facts outside them stay unrendered.

## 5. The interview shape

The audit is a conversation, one scenario per exchange. A structured reading of the
scenario is put in front of the auditor, checked against the sheet and the code, pushed
back on where a check fails or a claim overreaches, and ruled; the ruling is written at
once. An external reader with no context beyond the sheet excerpts may supply readings,
and every such reading is re-verified against the sheet or the code before it enters the
record; its role is reading, never ruling. Corrections to the audit's own method or
record made during the run are applied with dated notes, and the summary's ledger lists
them.

## 6. The design panel and the universe recount

Before the audit's digest is fixed, a critique panel reads the checklist, the sheet, the
record and the summary, each seat from one framing and blind to the others: one checks
the summary's every claim against the record; one attacks the checklist against the code
and the design's class contracts, asking where a check could pass while the key is
wrong; one looks for what the audit never asked, the untraced scenarios' structures and
the checks no scenario could have failed; one models what a released example would
leak. Every panel claim is reproduced on the source before it is triaged. The panel's
findings become amendments with dated notes, further traces, and checks executed on
named scopes; a check the panel proposes that nobody executes on the world is not
written into the bound checklist but recorded for the next audit, so the sealed
checklist holds only the method that ran. The first panel's structural finding is what
the criterion universe answers: every uncovered or unknown outcome is recounted from it
by hand, the criteria frozen before the people are read, and the witness is compared
afterwards.

## 7. Coverage observations

An audit may find that a class or modifier, correct as constructed, never exercises a
semantic surface an agent could get wrong (a count that is always exactly met, a
modifier whose pressure a common skill absorbs). These are recorded under their own
heading as future benchmark design, never as defects of the world and never as findings
against its golden status.

## 8. What the method does not do

- It verifies the sealed key against the rules as coded and against a human reading of
  the evidence; it is not an independent reimplementation of the rules.
- It traces a subset to its evidence; the rest rest on the acceptance pass with the
  outcome rule read off the witness, the panel-added checks on their scopes and, for
  the uncovered and unknown among them, the universe recount.
- Its independence from the rule is partial by construction: the criterion universe
  shares the rule's dated view and fact reads, and the required-sources check applies
  a rule the traces established rather than a second implementation.
- Not yet in the method, from the first audit's panel: a check binding a
  template-written clause's text to its constraint target and a first-person comment's
  author to the fact's subject; the stable interval's bounds and the distractor
  uniqueness rule as universal checks; a per-check evidence line for the acceptance
  pass, so the untraced scenarios are reconstructible from the record.
- It cannot recover a rejected prose draft: a sealed refusal records the attempt, the
  guard and the finding counts, never the text.
- It records realism observations about the generated prose and construction as
  limitations of the benchmark, not as things tuned.

## 9. Releasing an example

Publishing a scenario's key ends its life as blinded evaluation material. A released
example is first retired under the design record's per-scenario retirement rule: it
keeps its place in the sealed world and the audit's provenance, leaves the scored set
of every later blinded evaluation, is named as retired in that evaluation's manifest,
and carries a contamination statement. The example is chosen to show the method while
leaking the least reusable structure about the scenarios that remain private, which is
not the same as the cleanest trace; the sheet header's opening-frame rollup, the rows
observable only after now and any pass note that cross-references another scenario
never enter a release. No golden scenario is released before the first evaluation has
run over the whole set: the example a reader values is the key beside an agent's run on
it. Until then a throwaway-seed world, never sealed or scored, illustrates the sheet.
