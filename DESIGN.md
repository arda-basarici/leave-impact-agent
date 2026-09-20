# DESIGN — leave-impact-agent

What is being built and why: the decisions and their reasoning, as a narrative
snapshot of the current design. Edited in place; the chronological trail lives in
`REPORT_NOTES.md` and in git. Wins over `VISION.md` (the frozen founding snapshot)
on disagreement. How it is built → `ARCHITECTURE.md`; the pitch → `README.md`.

The document is organized for the reader who has to trust the ground truth. The
story is what makes an answer key correct by construction; each decision sits where
it protects that, and a decision not yet in force reads as a protection not yet in
place.

## Objective

An agent that investigates what an employee's leave means operationally, reading the
HRMS, the issue tracker, the calendar and chat through their real APIs, and drafts
an evidence-backed coverage plan for a human to approve. Deterministic rules own the
normal path; the agent investigates exceptions; the human decides, and the agent
never does. The organization is generated into real systems by a generator that also
emits the sealed answer key, so every claim the agent makes can be graded against
constructed truth.

**The success criterion.** A valid answer is a report whose facts trace to org data,
whose plan satisfies the scenario's planted constraints, and whose unknowns are
stated rather than invented. It is measured across an evaluation spine by difficulty
tier, and served from a deployment that exists from the first milestone on.

**Probes preceded the remaining design.** The fatal unknowns (Frappe standing at its
real footprint, Frappe's REST surface including its `leave_approver` wart, Jira,
Google Calendar, the generator's seed spike) and the two deployment floors (the
instance under Terraform, the OIDC deploy) were probed before anything was designed
on them, each pass criterion fixed before its probe ran and recorded in
`probes/README.md`, each outcome in `probes/FINDINGS.md` with captures beside it.
Later rulings cite those findings by name; the Bedrock shortlist and Slack were
allowed to trail into the world milestone without blocking its entry. The framework,
tool-layer and post-approval questions were deliberately not decided before that
evidence existed; they remain open below, pinned to the milestone that produces
theirs.

---

## What a valid answer is

**The report and the key speak one typed vocabulary, frozen at the world
milestone.** Everything downstream grades on it and the generator emits truth in the
same words, so the types, their grading keys and the four semantic rules below are
lasting; field names and enum members can still grow. Six claim types:

```text
impact                key (leave_id, subtype, artifact)   subtype: deadline | meeting | responsibility
constraint            key (clause_id, applies_to)
candidate_assessment  key (impact_key, employee_id)       verdict: viable | non_viable | unknown, reasons[]
source_conflict       key (entity, predicate)             observations[], resolved_value, authority_rule
unknown               key (subject, required_fact)        reason: absent | inaccessible | ambiguous | conflicting | insufficient
coverage_action       key (impact_key)                    action: assign | uncovered | unknown, assignee_ids[], rationale?

shared, serialized: claim_id, type, evidence_refs[], derived_from_claim_ids[]
computed from the payload, never serialized: the grading key, entity_refs[]
```

Impacts describe what the leave affects; constraints what a valid response must
obey; candidate assessments who could satisfy a need; coverage actions what the
proposed plan does; conflicts and unknowns where the evidence chain could not be
established. **A responsibility is an impact, never a constraint.** An existing
obligation attached to the leaver, an open ticket or a named client contact in a
document, is something the leave affects; "a release needs two qualified engineers"
is normative, cited from its clause, and never an impact of the leave. **Every type
has its own grading identity** because a universal `(type, entity_id)` fails as soon
as a claim is relational: an assessment is a person *for* a need, a conflict is an
entity *and* a predicate. **Evidence refs are plural from the first schema**: a
single non-viability can rest on Calendar, Frappe and a clause at once, and a
single-source field would tempt the agent to cite one fragment of a multi-source
inference. Not added, deliberately: `violation` (the constraint checker emits
those), `evidence` (that is provenance), `risk` (an impact already is one),
`reasoning` (report layer, not benchmark ontology); a `dependency` impact subtype
waits for a scenario class that needs it.

**A constraint's rule is its clause.** `clause_id` is the key, so a constraint the
agent cannot trace to a clause cannot be expressed: the grounding rule made a type.
Clause-backed requirements become constraint claims; deterministic domain rules (the
cover may not itself be on leave) constrain validity inside the viability rule
without becoming claims. **There is no need apart from an impact.** An impact *is*
the coverage need; cardinality and eligibility come from constraints and rules, so
the assessment and the coverage action key on the impact's key. That key carries the
leave: a run investigates one leave, but the truth manifest holds every scenario's
impacts side by side, and an impact's identity is world-wide, "this leave affects
this artifact".

**Grading identity is computed from a claim's fields, never from a claim id.** Claim
ids are minted by whichever emitter wrote the report, so the same world fact carries
different ids in the agent's report and in the answer key; the grading key
identifies the fact across emitters, while `derived_from_claim_ids` links claims
inside one report. An earlier draft had given the coverage action its own
`basis_claim_ids`; that was the same relation under a second name and is folded in.
**References are typed at run time.** An `EntityRef` pairs an entity kind with an id
and validates the id's namespace at construction, because a union of `NewType`
strings is invisible once the type checker leaves; an impact key validates its
subtype against the kind (deadline → work item, meeting → event, responsibility →
work item or clause, since an obligation may be a ticket or a runbook paragraph).
`entity_refs` say what a claim is about, `evidence_refs` (source, target, field) say
where it was read. **A conflict's observations carry typed values** (`FactValue`: an
entity reference, text or a date, tagged in JSON; the fact base owns and may extend
the union), never text flattened for convenience, because resolution compares them.
A coverage action names its assignees in the plural (the cardinality clause needs
two) and carries an optional rationale, text no grader reads (the judge it was
written for was superseded at the investigator milestone's entry; the grading
paragraph below). The
assessment's reason vocabulary is seeded from the criteria the viability rule names
and closed by that rule.

**Serialization is a stdlib codec in one module**, canonical and decoding through
the same constructors the code path uses, so validation has one home; pydantic stays
out of `core` and may enter at the agent's structured-output edge without the domain
knowing. Well-formedness (unique ids, resolvable references, an acyclic provenance
graph, no two claims of one type on one grading key) is the codec's; the semantic
chain checks belong to the rules.

**The fact base is the rules' only world.** A fact is a subject, a predicate, a
typed value, the evidence reference it was read from and the world date at which it
became observable. A rule that has to reach back into an entity is not reading the
fact base, which is why two rows joined the registry when rules needed them
(`scheduled_at`, an event's half-open instant span; `in_component`, a work item's
component). Each registry row declares its value spec and a fact validates against
it at construction, so the registry is the one declaration of what a predicate
holds. A requirement is stored as a typed value (a minimum count and a tuple of
typed criteria), tagged so a sealed key survives a criterion added later. Country,
timezone and grade have no predicate until a rule reads one.

**Absence is a record of its own.** A `Gap` says the record was observed and this
field held no value, planted where a scenario class plants a missing fact, and never
a failed read: a failed read is the run condition, a separate `RunCondition` (the
reachable sources) passed beside `RunContext`, because one scenario runs under
several. Conflating the three (a gap, a failed read, zero facts) would break the
derivation of closure. The entity's `None`-versus-empty distinction maps to
gap-versus-no-facts in `core`'s derivation, and a ticket without a due date is an
observed negative, not a gap.

**Closure answers in a fixed order and derives three of the five unknown reasons.**
It reads facts and gaps visible at `now` from reachable sources: a positive fact →
known true, with the facts that established it; a source of the predicate's declared
domain unreachable → unknown / inaccessible; a gap → unknown / absent; an open
domain → unknown / insufficient; otherwise known false. Zero facts mean false only
after the evidence domain has been fully observed, and a gap blocks that inference.
`ambiguous` and `conflicting` are the agent's to emit, never the rule's, which keeps
the rule's derivation and the agent's own uncertainty apart.

**Viability evaluates four criteria through closure and combines them.** Any known
false → non-viable with every failing reason; otherwise any unknown → unknown,
deriving from one unknown claim per unresolved fact; otherwise viable. The criteria
and their sources of truth: the required skill, from the clause-backed requirements
that apply to the impact's artifact or its component (`skill`); membership of a work
item's component, a domain rule (`component`); not on leave over the need's window,
the investigated leave's span for a deadline or responsibility and the event's own
span for a meeting, read in the run's reference timezone, and not attending another
event overlapping a meeting (`availability`); the requirement's policy criteria
(`hard_rule`). The investigated leave's span is a parameter of the rule, never a
fact the rule establishes; the evaluator supplies it from the scenario spec, the
investigator from the leave record it read through the people port. An unreadable
work-item component is one unresolved criterion, not an unresolved need, so a known
failure still settles a candidate; an unreadable meeting schedule leaves no window
to ask about and is an unresolved need for everyone. The leaver fails through
`on_leave` like anyone. A fifth criterion, `load`, was pruned and waits in Future
work.

**Criteria assess a candidate; the count judges the plan.** A requirement's count
never touches individual viability, so one viable person against a two-person clause
is a viable candidate and an invalid plan. Three record-returning functions carry
the plan side, because a defective plan is a graded outcome rather than an implicit
failure. The plan check resolves each constraint claim's clause to its `requires`
fact (the agent establishes which clause applies and never transcribes its content)
and reports `insufficient_cardinality` (per requirement, the count a minimum, an
implicit minimum of one without a clause; under the conjunctive model this reduces
to the largest count, a property of the current semantics, not a theorem),
`missing_assessment` and `non_viable_assignee` (an unknown assignee is not viable
for an assign). The truth outcome is computed over an explicit candidate universe,
never the `must_assess` set, with `V` viable and `U` unknown against count `n`: `V ≥
n` assign, `V + U < n` uncovered, otherwise unknown. The expected action is truth;
an expected assignee set is not, since any viable set of the right count is valid.
The chain checks are report-internal and named for what they know: an unknown
assessment derives from unknown claims shaped as the rule emits them (about the
candidate, the impact's artifact, or a clause the report's own constraints cite for
something that could apply to the impact, on a predicate the rule reads for that
subject); an unknown action from an unknown assessment; an assign action's assignees
each hold a viable assessment; an uncovered action holds no viable one; a conflict
resolves to the system of record's observation under the rule it cites; every impact
has exactly one coverage action and every action an impact. A separate completeness
check takes the universe and lists every member without an assessment, so
`uncovered` is never inferred from a report that simply stopped assessing.

**Four semantic rules travel with the vocabulary.** *Viability is relational and
preference is never truth:* the key states whether `(need, employee)` is viable and
why; "the best person" has no exact truth unless an optimization rule is declared,
and none is, which keeps candidate grading from smuggling a reference plan back in.
*Extra candidates are judged from the truth fact base, never from re-reading the
world:* the scenario plants a bounded `must_assess` set with authored verdicts (the
deliberate near-misses that make "why not Deniz?" objectively gradable), and any
further candidate the agent proposes is recomputed by the evaluator's pure viability
rule over evaluator-only normalized facts, every planted atomic fact in structured
form with its provenance wherever it physically landed, so a skill that lives only
in a ticket comment is a fact the evaluator holds without solving the agent's
extraction problem. The evaluator and the deterministic core share those pure rules,
which is not the generator-echo problem but does admit a shared rule bug; the
generator invariant that closes it: for every `must_assess` candidate the authored
verdict must equal the rule's verdict over the fact base, and a mismatch fails
scenario generation rather than grading an agent wrong. *Conflicting observations
resolve through a deterministic authority table:* "live wins" is the design intent,
`system_of_record_wins` is the rule. Each normalized predicate has exactly one
system of record (employment and location facts → Frappe, ticket owner and status →
Jira, meeting participation → Calendar, procedure requirements → the corpus), and a
document is never the record for an operational fact about a person or a work item,
while the corpus is the record for what a procedure requires, a normative fact that
exists nowhere else. Conflicts are keyed by `(entity, predicate)`, not by field
names that happen to look alike (an office location and a calendar timezone are not
a contradiction), and the conflict claim cites the rule id so precedence is testable
instead of intuited. *Closed-world reasoning applies per declared evidence domain:*
each predicate declares the sources that collectively hold all admissible evidence
for it in this synthetic world and whether that domain is closed; positive evidence
→ known true; no positive evidence with a closed domain and every required source
available → known false; no positive evidence with an open or incomplete domain, or
a required source absent or inaccessible → unknown. So a skills list without Kafka
is `non_viable / skill`, an explicitly empty list is the same, a missing skills
field is `unknown / absent`, and a closed domain whose Jira half is unreachable in
this run is `unknown / inaccessible` even when the HR half shows nothing. That is
why expected verdicts are derived per run condition from facts plus closure
declarations rather than stored: a tool-failure run against the same scenario
legitimately turns a `non_viable` into an `unknown`, and that difference is the
tool-failure metric.

**Three coverage outcomes, and the unknowns chain.** `assign` is a positive
conclusion, `uncovered` a negative one (the evidence suffices and nobody qualifies,
the vision's own "no qualified coverage exists for the migration" case), `unknown`
an epistemic limit. Keeping the second apart from the third is what stops the
benchmark rewarding caution: "I don't know whether anyone can cover this" against a
complete world that establishes nobody can is wrong, and so is "nobody can" when a
required source was unreachable. The word `unknown` appears at three levels with one
relation between them: an `unknown` claim records the missing fact and its reason,
an assessment whose verdict is `unknown` derives from that claim, a coverage action
whose action is `unknown` rests on the assessments. Missing evidence → unknown fact
→ unknown assessment → unknown coverage, one chain, not three unrelated uses of a
word. The completeness condition reads over this: every planted impact gets a
coverage action, `unknown` included, or the plan is incomplete.

**Grading falls out of the vocabulary, and no prose is scored.** Impact and
constraint discovery: precision and recall over grading keys, where the key is the
whole fact. For every other type the key names the subject and the payload states
the claim (an assessment's key carries no verdict), so key match and payload
correctness are reported apart and a matched key with a wrong payload is never a
true positive (ruled at the investigator milestone's entry, 2026-09-20). Candidate
assessments: verdict plus reason class against authored or derived truth, the
must-assess set the recall universe.
Distractors: false positives bucketed by the planted reason class (wrong window,
other team, already resolved, stale document, timezone), so a near-miss reads as a
sentence. Source conflicts: detected, and resolved to the authority table's value.
Unknowns: the expected gaps of a missing-information scenario found, and no gap
claimed where the world is complete. Grounding: a claim is grounded when the pure
rules, run over everything the run observed (records returned, reads completed or
failed, the run's condition) and the report's own claim links, reproduce its
payload, which is the deterministic core replayed on the agent's reads; whether the
cited references resolve, were retrieved by that run and were used by the replay is
a separate count, so a broken citation and an unsupported inference are different
numbers. The plan: outcome match against the expected action derived per run
condition, completeness (every sealed impact exactly one action, no action without
an impact) and constraint satisfaction with truth-derived assessments; coherence,
the same constraint check over the report's own assessments plus the chain checks,
is reported beside it so an assignment with no reported assessment shows. The first
draft sent the rationale text behind an action to an LLM judge calibrated on a
hand-graded set; superseded 2026-09-20, since the rationale is optional in the
vocabulary, no hand-graded set exists, calibration is its own measurement problem,
and the claim this benchmark makes rests on deterministic grading against
constructed truth. It returns as future work when rationale quality has a consumer,
the demo's report view. The ontology is frozen whole
and exercised gradually: the first golden set covers the types its scenario classes
need, and no scenario is authored to give a type coverage.

---

## One organization, many scenarios

**One generated organization, read-shared, write-isolated, truth-isolated.** The org
is a single synthetic company of roughly 25 to 30 people in about five teams, both
generator parameters (`ORG_SIZE`, `TEAM_COUNT`) rather than fixed numbers. The agent
sees the whole org: other teams' people, tickets, meetings and policies are the
plausible-wrong candidates that make coverage a real search, which a six-person
sandbox cannot produce. Scenarios are slices of that org, not orgs of their own:
each owns its mutable entities (the leave, its tickets, its events) and a time
window, never writes into another scenario's entities, and carries its own sealed
answer key, which the validator re-derives against the full live org so
cross-scenario contamination is caught rather than assumed away. Org-per-scenario
was rejected: it simplifies ground truth by removing exactly the
irrelevant-but-plausible evidence the evaluation exists to test, and multiplies the
seed and validation runs for no gain. **Ownership lives in the sealed world spec,
not in the systems.** Which entities a scenario owns is recorded in the spec's
owned-entities table; the adapters carry no scenario id. The earlier plan, a Jira
label, a calendar property and a Frappe custom field, was dropped because nothing
would have read them. A slice is therefore enumerable from the spec and could be
reset from it if anything ever writes to the world; the reset itself is not built
until something does.

**People are cheap and scenarios are expensive.** A person is a handful of generated
records per system; a scenario is planted facts, named distractors, a relevant
policy clause, a defensible key and a hand audit. The golden set therefore grows by
adding scenarios in new time windows, not by adding employees. Three constraints
keep the construction honest: a team does not determine its scenario's type (the
generator assigns type independently, the manifest records both, so structure cannot
stand in for reasoning); distractors are planted and named in the key with the
reason each is wrong, so a near-miss is gradable and background filler stays bounded
rather than "hundreds of tickets"; and policy clauses have real-world scope only
(contractors, a country, a grade), with scenarios chosen so a clause becomes
relevant, never clauses written to make one scenario's answer come out.

**Synthetic employees are domain entities, not vendor users.** Work ownership in
Jira lives in a dedicated single-select custom field keyed by stable employee id
(`emp_017 — Alice Demir`); `assignee` stays unassigned so the board never claims the
service account is responsible for the work. Issues, workflows, sprints, components,
comments, changelog and JQL remain real Jira behaviour. Actor identity is outside
the first truth model: every write comes from one service account, so changelog and
comment authors carry no world fact, and the same holds for Calendar's organizer.
Rejected: real accounts (Jira Free caps at ten users, the developer instance at five
and for app development only); a hybrid of real and synthetic people (two identity
paths in every tool and grader, and licensing shaping which people a scenario may
involve); Jira Service Management customer accounts (free and unlimited, but their
appearance in user pickers is a documented gap the vendor is asked to close).

**Time is world state, never the machine's clock.** Every run receives a
`RunContext`: scenario id, world (seed) version, a canonical `now` as an instant
with a reference timezone. That is the reproducibility boundary: same scenario, same
world version, same `now` → same evidence, on any machine, months later. `now` is
injected into the deterministic core, the agent's context and the tools; no core,
adapter or evaluator code reads the wall clock for world semantics, and a test
enforces it. Telling the agent "today is 2026-10-01" is not cheating, since a
deployed assistant knows the date too; only its source is fixed. Seeded data carries
absolute world dates; human dates are interpreted in the employee's or
organization's timezone (the calendar probe's own "13:00 UTC on an Istanbul
calendar" slip is why the instant carries a zone). Three clocks exist and only the
first is truth: world time (`now`, leave and event dates, deadlines,
policy-effective dates); vendor operational time (when Jira physically stored the
issue, API timestamps); run time (when the evaluation executed). No attempt is made
to alter the vendors' clocks. **The tool surface exposes exactly the fields the
generator controls**, which settles vendor timestamps without per-field judgement:
Jira's `created` is absent from `search_work_items` because the seed cannot set it,
and becomes a world fact the moment it can. Tools take explicit date ranges the
agent reasons to; defaults derived from `now` exist for convenience, but the harness
handles time mechanics and never decides which period is relevant, since that
relevance is part of what is evaluated. **Temporal robustness is a metamorphic check
over a declared `stable_now_interval`**, not a universal "advance three days, same
answer": within the interval the key must hold for any `now`; outside it a scenario
may legitimately flip (a notice-period clause), and such flips are a
temporal-reasoning test of their own.

**History is planted only where it can be planted honestly; qualification is derived
from atomic facts, never stored as a conclusion.** Jira's REST API cannot set
`created`, `updated` or `resolutiondate`, so "Bob resolved twelve payments tickets
last year" is not a plantable world fact over REST. Coverage qualification is
therefore expressed as atomic, world-observable facts spread across the systems (an
employee's skills on the Frappe record, a Jira component with its named synthetic
members, a policy clause stating what coverage requires, the calendar's free/busy,
the active tickets a person owns), and the agent derives "Bob is a valid candidate"
from them; no system stores that conclusion, which is the same rule that keeps
decisions out of tools. Ticket dates are world facts like ownership, so they live in
generator-controlled custom date fields (`Opened On`, `Resolved On`) set over REST,
exposed by the adapter as `opened_on` and `resolved_on`, while Jira's own timestamps
stay hidden as vendor time; the CSV importer, which backdates `created` but not
`resolutiondate` and is UI-only, was the wrong question. Date-level history ("opened
in March, resolved in May") is plantable without a manual step; actor-level history
("who handled this before") remains outside the first truth model. Frappe leave
records and calendar events take the dates the seed sets, so past leave and past
meetings are real history where history is needed. **Comments carry a fixed
bracketed prefix for their id, world date and speaker** (`[comment_005, 2026-09-12,
emp_023 — Bob Kaya] blocked on the vendor API`): the comment's content is a world
fact, its vendor timestamp and author are operational facts, and the prefix is the
physical home of the world-side triple, exactly as the owner field carries an
employee id. The adapter reads it into the comment's structured date and author the
way it reads a custom field, a format translation and not an interpretation of the
prose, which stays whole, prefix included, and fails loudly on a comment without it;
the validator checks every projected comment parses. The free-text synthesis the
fragmented tier measures is the comment's content, never who said it when.

**Thirty scenarios, ten per tier; a tier is a capability level, a class is what a
scenario is about, and modifiers ride on top.** The tiers name how far the reasoning
has to reach. Tier 1, structured: every answer-relevant fact sits in a structured
field (dated tickets the leaver owns, meetings in the slice, skills on the HR
record, free/busy, open-ticket load); the capability under test is tool use,
temporal filtering, joins across systems and the deterministic candidate check. Tier
2, fragmented: at least one answer-changing fact needs synthesis beyond structured
fields (a qualification that exists only in a ticket comment, a responsibility that
exists only in a runbook) and/or the single supported clause type ("a release needs
two qualified engineers"), which turns a one-person answer into two or makes a
planted candidate non-viable by `hard_rule`. Tier 3, adversarial: the correct output
depends on reasoning about the evidence itself: a stale runbook naming an outdated
owner against Jira (`source_conflict`, resolved to the system of record), a
genuinely missing fact (`unknown / absent`), or a complete world in which nobody
qualifies (`uncovered`). Underneath the tiers, scenario classes
(`structured_deadline`, `structured_meeting`, `structured_mixed`;
`free_text_qualification`, `free_text_responsibility`,
`release_cardinality_constraint`, `fragmented_composite`; `stale_source_conflict`,
`missing_information`, `uncovered`, `adversarial_composite`) give results a second
reporting axis, so a tier that scores badly decomposes into which mechanism broke.
Distractors (`wrong_team`, `already_resolved`, `outside_window`,
`timezone_boundary`) and candidate pressure (`concurrent_leave`) are orthogonal
modifiers tagged on a scenario, never classes of their own, so the tier definitions
stop growing as features arrive; every modifier occurs on several scenarios, Tier 1
included, so distractor rejection is measured on structured evidence before free
text enters. Tool failure is a run condition applied over any scenario (the same
truth, run once normally and once with Calendar unreachable), never a scenario
class, so degradation is measured against an unchanged key.

**Primitive failure modes repeat independently before any composite.** The
stratification (counts cheap to change, the rule lasting): Tier 1, four deadline,
four meeting, two mixed; Tier 2, three free-text qualification, three free-text
responsibility, two release-cardinality, two combinations; Tier 3, three source
conflict, three missing information, three uncovered, one controlled composite.
Three unknown-outcome cases and three uncovered cases are worth more than six in
which both occur, because the distinction the vocabulary encodes is only measurable
when the cases are separate; an unknown assessment is not an unknown outcome, since
a Tier 2 clause asking a blank record already concludes one, and the Tier 3 class is
where the unresolved evidence decides the action. The set is sized for engineering
evaluation and failure localization, not fine-grained model ranking: at ten
scenarios per tier a score of eight in ten carries a Wilson interval near 49 to 94
%, so two tiers a few points apart are not distinguishable, while the failure
classes behind them are. Claim-level counts are larger but not independent within a
scenario; uncertainty is reported at scenario level, bootstrapped over scenarios.
The set grows after the first evaluator shows which classes need more cover, not
before, and not to narrow an error bar.

**A scenario owns a disjoint fourteen-day slice; the leave sits inside it.** The
slice is the world state the scenario owns and the cheapest write-isolation
mechanism there is; it also gives the shared calendars a believable spread. Slices
are dealt in order with a random gap of up to three days; the leave starts on day
six to nine, so that `now`, two to four days before it, always has slice history
behind it, with the `stable_now_interval` around `now`. Room before and after the
leave is what makes "a meeting the day before", "a meeting during", "a meeting the
day after" plantable without a two-week absence. Thirty slices are about fourteen
months of organizational history, which the calendars and the ticket dates carry
believably; the first cut, one window per month, was the cost of the same isolation
at twice the span. The rule may relax once entity ownership is proven.

**Org-level facts are static across the world; scenarios select, never mutate.**
Several classes rest on facts that no scenario owns: a skills field, a team
membership, a manager link. A missing-information scenario wants the only plausible
candidate to have no skills record, and blanking that field for one slice would leak
into every other slice that touches the person. So a person whose skills field is
blank is blank for all fourteen months, and a scenario produces its class by
choosing the leaver, the need and the `must_assess` set so that the static facts
yield the intended outcome; the generator asserts that the class emerged (a class
invariant beside the `must_assess` invariant) instead of editing shared state.
Verdicts derive from the fact base, so the same person is consistently `unknown`
wherever they are a candidate. With roughly twenty-eight people and thirty
scenarios, leavers repeat, as they would.

**The fact base is world-level and time-filtered by `now`.** A qualification
evidenced in a ticket comment from month three is admissible in month nine and not
in month one. Every fact in the truth base therefore carries the world date at which
its provenance became observable (static HR facts carry world start), and the
evaluator admits only facts dated at or before the scenario's `now`: the "time is
world state" rule applied to truth. The truth manifest thus has two layers, one
world-level fact base with dated provenance and per-scenario keys that own the
impacts, the distractors, the `must_assess` set, the slice and `now`. It also
settles what an evidence domain spans: "relevant Jira history" means the whole
organization's history up to `now`, not the scenario's slice.

---

## Truth before prose

**Semantic generation is deterministic and pure; surface prose is materialized once
and frozen; projection reads the frozen world.** Seed, parameters and generator
version go into the pure generator and the complete structured world comes out as
plain data, with a *brief* for every piece of prose the world needs. A second stage
materializes the briefs into text: deterministic templates for structured-shaped
text, since nothing is learned from paying a model to write a ticket title, an LLM
for the language-bearing artifacts that free-text reasoning is meant to exercise
(runbooks, client notes, ticket comments, procedure prose). Accepted prose joins the
specification as immutable world data, and re-projection never invokes a model. The
world version is the realized bundle's content hash, never the seed, because two
runs from one seed may differ in prose; "the same seed produces the whole world"
would have been false the moment a model wrote a sentence. A *semantic digest*, the
hash of the semantic world with its briefs, is the identity two runs from one seed
share. The realization is hashed and not the recipe because the interpreter finding
is exactly a case where the recipe holds and the realization drifts; the
interpreter's patch version is not part of the identity recipe, any runtime
difference that changes the bundle showing in the hash regardless, and the version
is external metadata never serialized into a hashed artifact, which would define it
circularly. The regression oracle is the pair (generator version, the reference
seed's semantic digest), re-cut deliberately with every bump and always together,
never the digest alone, because the semantic digest carries the vocabulary
fingerprint and the generator version as fields, so a vocabulary addition moves the
reference digest even when nothing drawn changes (a batching argument that rested on
"the reference digest checked unchanged" was corrected on that finding).

**A brief carries facts, never sentences, and the model does surface realization
only.** A brief holds the target's construction fields, the required facts as
positive `Fact` records, the allowed context facts, a surface namespace derived from
those facts through the closed vocabulary (so a class cannot forget a name or leak
one), and a register. "Must include the sentence 'Deniz has Kafka experience'" would
turn the benchmark into paraphrase detection. A required fact's role,
answer-changing or context, is derived by running the rules with the fact removed,
never tagged, because a wrong tag would misdirect the hand audit silently. Nothing
forbidden is listed, since containment refuses any proposition no allowed fact
matches and a second list would be a second source of truth; negative requirements
do not exist, since absence is closure's derivation and "the text must say X is not
the case" would introduce a second logical model. Every prose-targeted evidence
reference must resolve to exactly one brief before composition, a contract that
ranges over the whole bundle, world-owned policy clauses included, so the first
world-owned clause cannot arrive without its brief.

**Generated text is accepted only under semantic containment**: every required
planted fact is present and no additional benchmark-relevant fact is introduced,
`required(brief) ⊆ claims(text) ⊆ allowed(brief)`. A lexicon check is not that
guarantee: "Deniz led the Kafka migration" and "Deniz has never worked with Kafka"
pass the same vocabulary test, and "three engineers must attend" adds a cardinality
without one forbidden word. Four guards enforce it, the paid one last: a namespace
scanner that owns *mentions*, refusing every world name and unlisted date outside
the brief's allowed set by longest match at word boundaries, not guessing invented
proper nouns from capitalization, which false-positives on sentence starts, and
leaving number words to the extractor as the cardinality claims they are, since a
name that makes no claim ("thanks selin") is invisible to an extraction check; a
required-fact check that refuses a fact which vanished in the writing before the
checker is paid; an extraction check by a different model family that receives the
entity dictionary and a schema generated from the predicate registry but never the
brief's facts (the independence claim), returns propositions with polarity and
modality, and refuses any negated, hedged, unknown-subject or unrepresentable one, a
negated planted fact being an added fact and the unrepresentable bucket kept
provisionally, judged by its refusal rate on the first world; it is a
generation-time gate that never becomes truth, which stays the structured brief;
and, for the first golden set, a human reading of every artifact that carries an
answer-changing fact, folded into the acceptance pass, with the extraction check's
agreement recorded as the evidence for retiring it later. The scanner's one
exception, a form of three characters or fewer matching only in exact spelling,
exists because the skill Go would otherwise refuse most sentences; it sits where a
false refusal's cost (an attempt) flips against a missed identity's (the benchmark),
and stands as a heuristic the first world never exercised, both sides of its trade
pinned in tests, a miss being a foreign surface mention, a claim-bearing one the
checker still catches and a no-claim one only the scanner sees, reassessed only on a
golden audit, with a vocabulary-level surface policy the named successor if length
proves a poor proxy.

**Failed generations are discarded and retried, never patched.** A patched artifact
has the provenance "model output plus generator fix plus perhaps a human edit"; a
discarded one needs nothing. Each attempt is a fresh sample of one identical request
with no refusal fed back (the orchestration creates no dependence between attempts,
which is the property claimed, not statistical independence), so retry depth
measures one fixed configuration's difficulty and a systematic fault (twelve
refusals of twelve) stays visible rather than hidden behind a second-attempt pass;
the cap was four until the measurement world's review and is eight since: the world
estimates no per-attempt pass probability, exhaustion compounds across a world's
prose targets, and an exhausted run costs only a re-dispatch of sealing before any
vendor write, so eight is a robustness margin rather than a measured need. It is
recorded configuration and not benchmark truth, revisited only on the named
measurements (first-attempt pass, eventual pass, cap exhausted, refusals by guard,
checker retries, checker unusable); a target accepted above attempt four is read as
a struggling brief, the attempt count sealed per target. The dispatch input's
default trailed the ruling at four until the golden dispatch, so every earlier
dispatch ran at the old value; the default is eight. Rejected text exists nowhere,
because the repository is public and its job logs are world-readable, so a logged
rejected sentence would be a third benchmark-private surface with no access policy;
logs and refusal messages carry target ids, attempt numbers, guard names and counts.
Every model call precedes every external write, so a failed stage leaves nothing
behind. The materializer sits behind a renderer seam so the unit level uses a fake
renderer, and at thirty scenarios the whole stage costs well under a dollar per
world.

**Materialization's provenance seals in the truth manifest.** A brief's required
facts and a checker's reading of a text are exactly what truth expects, and the
world spec, readable by the validator's role, holds nothing truth expects. The
record carries the writer and checker configuration whole, the prompt-asset digests,
per target every attempt and refusal by guard with its findings counted by reason
under a closed vocabulary (failure-path attribution, never proof of writer or
checker blame, which the hand audit supplies), the accepted body's digest and its
extracted propositions, which are what the hand audit is measured against. Nothing
the validator can reach decodes the record: the generator's own decoder is the one
reader the truth manifest has before the evaluator, unreachable by the validator
under the import law. It also seals the stage's aggregate counters, because the log
had been their only carrier and one run sealed its truth, failed in projection and
took them with it; the counters are names in a declared append-only order, so a
counter added later reads back from an older record as unavailable, never zero.
Attempt history is in the record and so in the version: two runs that accept
identical prose through different refusals differ in version and share a semantic
digest, the coherent reading. Prompt assets are pinned by digest so an
identity-bearing prompt change updates the reference provenance deliberately. Prompt
policy is the generator's; the model adapter owns Converse translation only, over a
request-shaped seam whose types are its contract, so it never learns what a runbook
or a guard is. Model ids come from the environment and their absence fails startup,
inference parameters are code, and no credential exists anywhere in code.
Materialization runs inside the generator job, so the generator role holds invoke
rights on the writer and checker models, a role-policy edit in the platform stack.
The live evidence is a manually dispatched probe workflow under the generator role
reporting ids, outcome, latency and token counts and never text; cassettes were
rejected because a recorded model output proves nothing a stub and the probe do not.

**Before sealing a restart regenerates; after sealing it resumes the named
realization.** Reassembly from the seed no longer reproduces the bytes once a model
has written prose, so a resume reads the sealed spec, gates on an equal generator
version (resume is not migration), refuses unless the semantic digests are equal,
lifts the accepted bodies from the sealed plantings and refuses unless the
recomposed version equals the one named. A resumed run is harmless by construction:
every found entity is equal, so it folds no new receipt and changes no vendor state,
and its only writes are the checkpoint object under the mutable
`preparing/<version>/` prefix. Unfinished vendor state refuses a fresh run by name.
The version is printed and flushed before the first persistent mutation, since a
hard kill under the workflow's pipe must not lose the resume handle. A fresh run is
a new attempt not entitled to reuse the previous realization; landing on the same
bytes, the immutable writes hit the equal case.

**An organization is identified by three inputs and guarantees shapes, never
coverage.** The seed is the stochastic realization, the parameter record the shape
(every dial that can change the org lives there or does not exist), the generator
version the algorithm, stamped by the code because a version a caller could pass is
provenance a caller could forge; the interpreter's minor version is recorded and
checked, since Python guarantees only the raw `random()` stream across releases, so
an upgrade fails the suite until the version is bumped and worlds re-cut. The
vocabulary is curated, closed and versioned rather than drawn from a faker library,
because the namespace guard needs a finite set of words, and a recorded digest makes
an unbumped edit visible in the same diff without proving the bump, which the
reference seed's pair does. Members are dealt round-robin with at most two moves
between teams, because independent placement gave ten against three at twenty-eight
people, and ids are minted after the seats are shuffled so an id reveals no
structure. The organization guarantees the affordances the classes need (an unheld
skill, a singleton, a broadly held one, the parameterized number of blank skills
records, components crossing team lines, a contractor, the far seats) and nothing
about coverage: a first draft promised every skill two holders "so coverage is a
search", and would have made `uncovered` and `missing_information` unplantable,
since both select static org facts.

**Constructive selection, never rejection sampling.** A scenario class states what
it needs from the static organization as a query and returns every admissible
construction in a canonical order; the RNG chooses among them; the construction
plants the owned entities and authors the expectations; `core`'s rules then run over
the truth base as an independent check, and a mismatch is a named construction
error, never a retry and never a reclassification. The query is deliberately weaker
than the rule, since a query that mirrored the rule in reverse would make the
invariant's independence a fiction. Modifiers are planters with a class's shape
minus an outcome; a modifier may amend a candidate's verdict and may never change
the declared outcome, which is what makes "orthogonal" testable. **A scenario plants
only entities it owns**, runbooks, client notes and the policy or procedure that
carries its constraint; world-owned policies wait on an applicability model (Future
work). The stable interval is derived from planted observability, never authored,
the latest fact the key needs bounding it below and the earliest later
answer-changing fact above, capped at the day before the leave, so construction
stays independent of the rule implementation there too, the whole-world
re-verification being the independent check. **Required sources are found by asking
the rules under each single-source outage**, never from evidence provenance, because
a negative conclusion carries no evidence fact yet depends on every source of the
predicate's domain. Three records serve three audiences: the agent-visible spec, the
evaluator-only key (an outcome per impact and never a reference plan, `must_assess`
per impact, constraint keys, distractors unique by entity and never an expected
impact's artifact, the stable interval, the required sources), and the construction
record that binds them. Truth is `core`'s derivation over every planted record from
its planted date plus the facts only a world can plant, each stated once as the fact
and once in the brief that will carry it, on purpose.

**A scenario is correct locally against its key; a world is correct globally over
the history observable at each scenario's `now`.** A record one scenario plants can
change a verdict in another slice months later, which per-scenario verification
cannot see, so the golden set is valid only after every scenario is re-verified
against the assembled world, across its stable interval, under both the dated and
the runtime views (what a run can observe is decided by the read requests alone,
never by a planting date, which is benchmark-private), required sources included.
Contamination is a construction error naming the scenario, the changed verdict and
the foreign record, never a repair or a redraw, since a world that needs re-draws is
a class whose affordance is under-specified; preventing it by construction was
rejected as rejection sampling by another name, and it cannot hold once a Tier 2
comment is meant to be admissible months after its slice. Attribution is free
because planted records are only ever added, so a verdict can only flip toward more
established facts.

**The world plan is data, drawn by a planner that never decides whether a plan
exists.** A seeded table of tier, class and modifiers per scenario, produced by a
deterministic backtracking search under a stated rule (the tier counts, every
modifier on at least two scenarios, at most two on any, at least two with none) in
which the RNG orders the legal alternatives; a greedy draw raised on thirty-seven of
two hundred seeds for a rule every one could satisfy. Independent draws per scenario
were rejected because at ten rows a modifier can land zero times. The clean rows are
a baseline, not a causal isolation: ten rows on different scenarios compare low
against higher distractor pressure and do not measure one modifier's effect. Two is
the cap because the collision rules were tested on pairs and the composite classes
own "several things at once". Compatibility is a static class-by-modifier matrix
proven over every admissible construction. **A plan declares the organization shapes
it supports, checked before an organization is drawn**, exact where a count decides
them and swept where a rate does, after the documented minimum shape afforded no
uncovered row on any of two hundred seeds and two teams left the qualification
class's wrong-team pair unplantable on most; size below the default is a measured
refusal rate on record, not an affordance.

**The timezone affordance is guaranteed by the organization, and the far seat is
always a colleague.** At least two employees whose zone differs from the reference
zone by a fixed minimum at every instant of a year, DST-aware and date-free, so the
org generator can check it alone; offsets are computed at the planted instant, never
as city constants, and truth stays reference-zone based. The modifier chooses the
far attendee independently of the leaver, who still attends, so the far colleague
makes the instant plausible working time, and the event sits at the leave's edge so
that its instant is outside the leave in reference-zone truth and inside it under a
wrong-zone or UTC reading. Seed luck was rejected as rejection sampling at world
level; deferring the modifier to Tier 3 would contradict the golden set. Leave dates
are date-only HR facts read in the reference timezone for every employee. That rule
was implicit until the first golden world planted the one case that turns on it, the
leaver as the far seat; under the stated rule the key is right and the scenario
stands, and every later world seats a colleague, the guarantee grown from one far
person to two so the modifier stays affordable by construction.

**Three sealed artifacts serve three readers, and storage follows access.** The
*world spec* (organization, plan, slices, provenance, the other files' hashes) is
benchmark-private, since the plan alone names which traps were planted; the
*scenario specs* hold the agent-visible rows; the *truth manifest* is evaluator-
only. The plantings and the stable intervals live in the spec rather than the truth
manifest, because a validator whose role reads the spec alone could not otherwise
know what was planted; each fact has one home across the three, and the evaluator
joins spec and truth by scenario id. The *world manifest* is a fourth, different
object, the projection's receipt (adapter configuration, the identity map from
semantic to vendor ids, the version and digests), written after the vendors mint
ids, application-readable, outside the hash, holding no fact that can change an
answer; its test is "delete it after identity resolution and lose nothing
answer-relevant", and it structurally holds no credential, no seed (the seed with
the parameters regenerates the plan, which names the planted traps) and no entity
type. It lives in `adapters/manifest`, rank 2, the lowest package that can type both
the adapters' configuration and `world`'s provenance; the generator alone writes it,
and every reader builds its adapters from the configuration there. A first cut had
put the plan in that application-readable file; the identity-map write-back alone
proves the two cannot be one. The truth bucket holds the world spec and the truth
manifest under separate prefixes, the validator's role reading the spec prefix only
and the evaluator's both, the application's neither; the world bucket holds the
scenario specs, the documents and the manifest.

**The sealing order keeps a half-finished run harmless.** The pure assembly fixes
every world-content byte and the version before anything is written. The two truth
objects go first, by conditional create, before the first vendor call, so live
vendor state never exists without its sealed answer key while truth-only orphans are
harmless because nothing serves without a manifest; then the vendor projection under
a mutable, never-served `preparing/` prefix; then, only after the postflight, the
documents into their final prefix so a refused site leaves nothing under a prefix no
job can delete from; then the scenario specs; then every sealed object read back and
compared; and the manifest last, carrying every object's version id, so an object
under `worlds/` with a manifest beside it is a completed projection by construction.
**A world is served only on a verdict that judged its current manifest**, never
"whatever verdict file exists": a stated contract whose decoder arrives with its
first consumer, the serving check at the demo milestone, and a newest-approved
choice, if ever needed, is a listing of the prefix and not a mutable pointer. Vendor
names derive from the version, so no operator chooses them and two worlds on one
site cannot collide by choice.

**Projection is the effectful, idempotent shell.** One projector per system, each
find-or-create by the domain id planted on every entity, accepting an existing
record only when it equals the planted entity as read back (the integration tests
prove the round trip exact for every generator-controlled field, so equality is the
rule and no looser equivalence is named), and stopping on an existing identity
holding other state (`IdentityConflict`) rather than adopt or overwrite. Every
receipt is checkpointed before the next external write, a one-write crash window
kept on purpose, its cost measured by a timing wrapper at the shell and never in the
manifest, the cadence widening only on that evidence; and the window between a write
returning and its checkpoint is loud: the restart finds the record, receipts
nothing, and the refusal names the record to delete. The manifest has two stages:
under `preparing` it is partial and nobody's input but the generator's restart; a
decoder states the stage its caller accepts, and a reader handed a manifest of
another version refuses before using any recorded id. The composition root prepares,
checkpoints, projects, proves and promotes; two site inspections run as a preflight,
the company and the project holding a subset of this world's ids and nothing outside
it, and as a postflight demanding the exact set, Jira's reading every issue's marker
and refusing an unmarked or doubly marked one, Frappe's reading the employee numbers
past the company, the calendar map scoped like a site, with one residual on record:
the search index can trail a write, so a check before a run may miss an orphan
created seconds earlier. `projected` proves projection safety and recoverability,
never acceptance, which is the validator's separate artifact. **Documents are
projected into the world bucket as sealed objects, not into a database**, because
the generator runs on a GitHub runner that cannot reach the instance's PostgreSQL
and holds no database credential; the application's corpus is a cache the instance
fills from those objects: it discovers worlds by listing `worlds/` under its own
role, ingests only a world that satisfies the serving rule, loads the documents into
the version's namespace, verifies exact ids and byte digests against the manifest,
and marks the version ready in one atomic step, retrieval reading ready worlds only.
Ingestion goes through a narrow loader and never through the gated document writer,
since it is cache materialization and not authorship; the loader's build waits for
its first consumer at the investigator milestone's entry.

**The validator is a distinct module that only reads, and validates the projected
systems rather than the generator's intermediate objects.** It re-reads the live
systems the way the investigator reads them and compares them with the sealed spec:
every closed enumeration exact, missing and foreign both named; every record equal
to its planting; each scenario's derived view, read once at its run day, equal to
the plantings' under the runtime rule (one read per scenario, not two instants: a
run's view does not change inside the stable interval, since the systems hold every
projected record at once and the harness dates every returned record to the run's
day, so the interval is the evaluator's alone), a check that could not run saying so
and never counting as passed. Validating the projected systems puts the projection
seam under test, so a shared generation bug cannot produce an evaluation that agrees
with a wrong world. An integrity chain runs before any read (the manifest at
`projected`, its digest authenticating the spec bytes, the truth digest compared
across artifacts without the truth being read), and a refused input is an
`IntegrityRefused`, never a finding. The chain is complete for the structured tier;
prose-carried facts are proven through the containment gates and the corpus's read
fidelity. **The verdict is its own immutable artifact per execution**, keyed
`worlds/<version>/verdicts/<run-id>-<run-attempt>.json` with the run's identifiers
in the key and not in the artifact, so byte-equal verdicts across attempts prove the
live systems held, carrying the digest of the manifest bytes it read, since only
that digest ties a verdict to a projection, and approval computed as exactly "every
check passed". The checkpoint and the verdict go through one byte primitive in
`adapters`, which knows bytes and a path and nothing of either record, since neither
shell may be the other's dependency, and whose two guarantees are stated apart so
that atomic is never read as durable: atomic visibility on every platform, a
temporary renamed over the target; crash durability on the POSIX production platform
only, the parent directory synced, with no such barrier claimed on the development
platform; one writer per target is the invariant, the temporary's name fixed so a
dead process's debris is overwritten rather than adopted. Every sealed codec that
stores an instant with its zone refuses a pair the zone would not have written and
any non-canonical spelling rather than normalizing, so the encoding of a decoding
reproduces the bytes; vendor adapters sit outside that rule, normalizing a vendor's
spelling being exactly their job.

---

## The classes that leave the easy path

The classes beyond the structured tier (a qualification in a comment, a
responsibility in a document, the cardinality clause, the conflict, the missing
fact, the complete world nobody covers, and the two composites) rest on rulings that
mostly extend `core` before any class exists, each found by asking what the rules
would conclude about a scenario the class plants. Every class ran the two source
probes recorded in `probes/FINDINGS.md` (`source-dependence`; the register and
construction probes beside it are `section-probe`, `comment-probe` and
`reservation-book`), and every fact only prose carries is answer-changing by
derivation, a context role being a construction error.

**A responsibility that exists only in a document is a fact of its own.** A registry
row, `names_responsible`, has the section as its subject, the employee as its value
and the corpus as its sole evidence. The impact's artifact is the section itself, so
the section is both the obligation and its provenance. The alternative primitive, a
runbook giving an owner to a ticket the tracker shows unassigned, was rejected: it
attributes a known ticket rather than discovering an obligation with no structured
trace, and it blurs into the conflict class. The checker's parse binds a
carrier-subject proposition to the brief's target rather than the prompt naming the
target, so no identity reaches the model. The construction: the client is the note's
canonical title and nothing else, no client entity, the procedure clause naming the
note by that title so the two scopes coincide; the leaver holds the required skill,
since a designated contact lacking what the handover procedure demands would be a
world contradiction; one contact in one section with no allowed context, so every
extracted benchmark-relevant proposition is the required fact and every hedge
refuses. The class chooses enough non-leaver holders that every compatible modifier
preserves its declared assign outcome; its compatible modifiers are concurrent leave
and the timezone boundary, since wrong team, outside window and already resolved
need a ticket or meeting affordance a section-artifact class does not own, the
parked stale-document modifier being what would give a section a look-alike. The
world proves artifact fidelity (the validator, against the sealed document) and
cache containment (the gate at the corpus load); whether the investigator's
retrieval surfaces a section is an evidence-coverage measurement of the agent, not a
world invariant, so the validator runs no query against the live corpus, which would
reinstate a system demoted to the application's cache for a property that has no
definition without the query.

**Impact grounding is a conclusion.** Impacts were authored and never derived, so a
fact whose only role is to make an impact exist was invisible to the role derivation
by ablation and the required-sources derivation by outage: harmless while every
impact rested on planted records, fatal for a class whose one prose fact is the
impact's ground. A grounding rule asks, per exact impact key, whether the leaver
holds the obligation, and the enumerator over the leaver's facts applies the same
predicate, so discovery and grounding cannot drift apart, and the investigator
harness's deterministic impact detection is that same enumerator over live-derived
facts; construction requires the expected impacts to equal the derived ones in both
directions. The exact-artifact form keeps a missing fact for one section from being
masked by an obligation elsewhere.

**A section-artifact impact narrows its candidates by a clause.** With no component
to ask about, every employee would be viable for a responsibility and its
assessments would carry no signal, so the responsibility class pairs the
model-written client-note section with a template-written procedure clause applying
to that exact section. The two fragmented primitives are then symmetric: which fact
a model wrote is the one thing that moves between them, and a score gap localizes to
it. The requirement stays deterministic, since a model-written clause would be a
third prose mechanism the set never asked for. Registers get one job each: the
client note carries the contact, the runbook the stale owner, the policy and the
procedure requirements.

**Constraint-bearing documents are scenario-owned.** A world-owned clause is not
storage ownership but an applicability rule, and with constraints declared per
scenario a world-owned policy would either change structured keys wherever its scope
landed or leave those keys contradicting the text. So a constraint is carried by a
scenario-owned document whose text names the exact scenario artifact, and scope and
target agree by construction; an exclusive-component reservation was rejected as
debt disguised as planning, and world-owned policies are a named, deferred
capability rather than an implied current feature.

**A policy scopes itself by the release's exact title, and titles are minted without
replacement.** A component-scoped constraint was rejected as the cross-scenario
applicability the deferred capability owns. Titles had been drawn from a few
templates with no uniqueness, so a policy's prose could name two artifacts while the
constraint named one, a mismatch no verifier read; first parked as a rare seed, a
count found twenty-seven colliding handles in sixteen of twenty seeds, and the
ruling moved to a fix by construction: a title book mints ticket and meeting titles
without replacement per component and team, an exhausted context is a loud
invariant, and assembly refuses a constraint whose title names two artifacts.

**The cardinality class carries both consequences in every row, and the organization
seats its cast.** A release ticket the leaver owns, due inside the leave, under a
scenario-owned policy requiring two employees holding skill X: two viable, a
contractor non-viable by `hard_rule`, a non-holder non-viable by `skill`, the
outcome assign, the requirement a minimum and the two-person plan an example never
truth. Both rows exercise both effects while the effects stay separately graded; a
seeded variant would have given each mechanism one row. Exactly two viable
candidates make the count visibly load-bearing, and that is an organization
guarantee rather than seed luck: the class as first written, with holders, blanks
and contractors drawn independently, was unaffordable on any seed, so the second
component is now exactly the cast, chosen as one cross-team selection. Weakening the
class (the contractor outside the component) would stop the employment rule being
load-bearing; exempting it from the component rule would change a domain rule for
one fixture.

**Concurrent leave is coverage-aware, over the record and not the authored
verdicts.** A modifier may never move a declared outcome, so admissibility has to
know whether a cover survives. The first ruling counted authored viable candidates;
it was reopened because `must_assess` is the graded probe set and not the coverage
universe, the deadline class keeping its outcome through a component member its key
never lists. Admissibility keeps the structural pool, less the leaver and the
candidate sent away, to those whose HR record meets every requirement, and compares
the survivors with the required count; it reads the record and never a fact base,
closure or run condition, a conservative proof that can under-afford (the sweep
exposes it) or over-afford (the verifier refuses), both loud; the compatibility
table declares that no valid draft of a class affords the modifier, and
admissibility proves the declaration in the sweep.

**Missing information and uncovered differ in one placement.** Both plant the same
deadline shape under a clause requiring the unheld skill, so every recorded employee
fails by skill and a blank-record employee is unknown only when every other
criterion passes. The missing-information class puts its release in a component
holding a blank-record member, unknown by absence since the tracker answered, and
the outcome is unknown; the uncovered class puts it in a component holding none, so
the blank-record people fail by component, and the outcome is uncovered over the
full universe, a blank-record outsider authored non-viable by component alone so the
dominance rule is graded rather than argued, while the recorded outsider fails by
component and by skill, reasons being the set of every failing criterion, the
one-reason difference between the two outsiders being the rule made visible. Two
organization guarantees make both plantable, exactly one blank record in the first
component and a component with none; a meeting artifact would have needed one
guarantee fewer and made the pair differ in two ways at once. A modifier that could
remove the only unknown, a concurrent leave on the blank-record member, is excluded
for the class by the compatibility matrix under the rule that a modifier never
changes a declared outcome. Under a tracker outage both become unknown by
inaccessibility, the run-condition metric's own axis.

**The stale conflict sits on a real impact, and reads resolve.** The tracker says
the leaver owns the release ticket; a model-written runbook section names a teammate
outside the component as owner. The impact stands, grounded on the tracker; the
failure caught is an agent that believes the document, drops the impact or hands
cover to the named owner, which the component rule makes a graded error. The runbook
register was rewritten twice on the probe's evidence, once for telling the on-call
reader whom to reach, a contact the checker rightly typed, once for padding one fact
into a paragraph, and accepted at five of six on one frame; the section's fact is
answer-changing through the expected conflict alone, which is why the key's field
had to land first, and its allowed context is empty; the organization guarantee
tightened to exactly one blank record in the first component, since four of two
hundred seeds had seated both. The reverse, a document giving the leaver a ticket
the tracker gives to someone else, is a false-positive trap parked as a modifier
rather than built into a class whose row would have no impact of its own. Two gaps
in `core` surfaced: closure did not apply authority, so a positive fact with the
asked value was known true from any source; the raw fact base stays unresolved,
since the conflict derivation needs every source's value, and the semantic reads of
a single-valued predicate resolve through the authority table and return only the
agreeing facts as evidence, a contradicted fact establishing nothing and appearing
in the conflict finding instead, an unreachable system of record giving unknown by
inaccessibility rather than a promotion of lower-authority evidence, while
multi-valued predicates keep the current rule, a skill in a comment being evidence
whether or not HR answered, and a record reachable and silent beside a positive
corpus is known true: answered is the line, not answered positively. And conflicts
were not conclusions, so the stale-owner fact would have been labeled context and
skipped at the hand pass; derived conflicts now enter the conclusions.

**The key seals two derived conclusions, the conflicts and the unknowns.** Without
them the conflict class was gradable only through side effects. Two append-only
fields, the expected conflicts and the expected unknowns, derived by one shared
reading pass over the groundings and assessments and never authored: a class asserts
the constituents its construction exists to produce, conflicts exact and unknowns a
superset, and construction refuses what the rules do not derive. They are scoped to
the evidence the rules returned, because a world's documents stand for every run and
an unscoped derivation would attach one scenario's stale runbook to every later
investigation. The expected unknowns are the complete derived set, which exposed a
fact the key had never stated: every clause-bearing Tier 2 row already concluded
unknowns, a blank record answering unknown by absence while a viable candidate
dominates the outcome (all 160 prose rows over nineteen twenty-row worlds, 310
unknowns). Grading: an expected conflict the report lacks is a miss, a reported
conflict outside the set a relevance error, every reported conflict still checked
against the authority table. A key sealed before the fields decodes them as none,
absent kept distinct from empty.

**Composites are fixed pairings whose constituents stay independently observable.**
The fragmented composite is the responsibility note's section carrying a second
fact, that the cover holds the required skill their HR record lacks, so one text
must carry and one checker must extract two facts of different subject shape; two
carriers and two sections were rejected because neither makes one text synthesize
two facts. The skill predicate's evidence domain gains the corpus as a global
change: a skill is a set, so a second positive source adds evidence and never a
conflict, and the cost falls on the negative side, since under a corpus outage
nobody is found to lack a skill. With the second fact the section gains the only
lever a one-fact note lacked, so the section probe gated the class commit (four of
six on the first run with both facts extracted correctly on every text, the two
refusals a checker-format fault, an omitted empty `other_claims` re-checking the
same text at temperature zero until the retries ran out, six of six after one
sentence in the checker's system prompt, the digest re-pinned) and the
sentence-frame question closed into the probe rather than argument: six of six
two-sentence texts, each sentence the brief's fact with the client's name
substituted, recorded as a limitation and not tuned. The adversarial composite is
the conflict row seated in the missing-information component: resolve what
obligation exists, then conclude unknown rather than uncovered. A seeded combination
would have given breadth without replication; structured constituents are asserted
present, observation rather than ablation; the compatibility matrix excludes from a
composite any modifier that could erase a constituent; a composite's modifier row is
its parents' intersection, with no pair table until a reusable incompatibility is
found, since the existing pair sweep already composes every compatible pair of every
class through the verifier, so the composite's pair is exercised the moment its row
is declared.

**The world records what each admitted scenario binds, and refuses a later candidate
that crosses it.** The first plan seating the responsibility class beside other rows
was refused by the whole-world re-verification on twenty of twenty seeds, on
interactions no per-scenario test can see: a person one scenario's note names
responsible being another's leaver, and a person one scenario's prose gives a skill
being another's candidate authored non-viable by it. The reservation book records,
in construction terms and never class names, the leave subjects, the standing
contacts, the (person, skill) pairs provided in prose and the pairs an authored
verdict assumes absent, and refuses a crossing in both directions, so construction
order never decides correctness; a world the book refuses nothing in is the world it
was. Swept over two hundred seeds of the twenty-row plan: 196 admitted and verified,
none contaminated, one refused by the book (two leavers both named contacts by
earlier rows, a loud refusal at half a percent), three refused by a scenario's own
invariant, which the wrong-team fix removed at the modifier. Not every graded
candidate is reserved, since a shared candidate contradicts nothing and reserving it
would burn identities for no protection. Deriving the other rows' keys from the
whole world was rejected (it turns structured rows into prose-graded ones and makes
the audit read prose written for another scenario), as was a retry on collision
(rejection sampling at world level); the re-verification stays the oracle for
interactions the book does not know. To watch, not built: a class depending on a
blank skills record reading unknown would need the positive-against-absence rule
generalized beyond known false. **The stale owner is a standing fact and the book's
third claim**: the first reading needed no reservation for it, and the first golden
sweep refused seventy-three of two hundred worlds, each a meeting row whose leaver a
runbook named as stale owner, because under a tracker outage the document's claim
cannot be resolved away. **Rows are constructed scarcest class first**, with each
row's seed drawn in plan order beforehand so the order changes no draw, after
thirty-nine of two hundred worlds exhausted a class seated last; scarcity is
measured per class, so the order cannot guarantee no exhaustion, and the contract
promises no world for every seed.

**The tiered plan is one table per tier, each checked on its own slice.** Tier 2
splits three qualification, three responsibility, two cardinality and two composite;
the coverage minima and the clean-row floor are tier-local, because the structured
tier alone already meets every minimum and a rule over the union would let every
fragmented row stay clean. One consequence on record: only the cardinality rows
afford the resolved look-alike, so the tier has no clean cardinality row. A named
plan is an operational generator input the moment the workflow offers it, so
offering one bumps the version, against a first reading that had batched the bump;
the version bumps at the commit that moves the digest, never at a step's end, since
the workflow can run from any pushed commit. The golden plan is the union of the
three tables, thirty rows; the foundation classes landed without a bump because no
offered plan drew them, a test pins the unoffered set, and no entry point reaches an
unoffered class. The wrong-team meeting's team pool excludes every team holding a
graded candidate, after the modifier alone refused eight of four hundred seeds.

**The materialization gates were tuned on one measurement world, then frozen.** One
world under the real pipeline, sealed and validated and never counted among the
thirty, gave the numbers the design had predicted and never measured: first-attempt
pass two of three, eventual pass three of three, no cap exhausted, about a cent and
a half for the run, and a hand sample of three with every required fact read
correctly, a sample that supports no rate. Its review fixed the rules that stand: a
comment's author is the subject of a first-person statement, so a required fact
about the author anchors on its value side only, a third-person claim inside a
comment being unexercised and unplanned; a reading that cannot be a proposition is a
protocol failure retried at temperature zero, a retry that protects only against
provider-side variation and stays because the narrowed class is rare, while a
refused value is a reading fault that refuses the attempt, and a reversed entity
pair is put the registry's way round only when both ids are listed and their kinds
prove the orientation; an offer to take work is a coverage signal the qualification
class does not own, so the writer may not make one, and a pass in which the checker
typed willingness as ownership is recorded as a checker residual rather than
credited to the allowance; a hedge on allowed context is tolerated only when a
structured record establishes the same fact, and an allowed fact is never evidenced
by the brief's own target, since a fact this text evidences is one it must carry, an
invariant checked in code and not left to the classes; and allowed context shares
the carrier's source, because a fact of another source restated as context would
survive its source's outage in the text alone, exactly the mismatch the runtime rule
exists to exclude, so a cross-source fact a text states is required, never allowed.
No second measured world, since repeating the projection lifecycle per register
would make a one-time checkpoint a standing ritual and a seal-only mode permanent
machinery for a temporary exercise; later registers were probed on unsealed passes
with human inspection, no rate reported, the accepted risk being that a defect found
only at the golden audit costs a new golden realization, since materialization fails
before any external projection.

**Each register is fixed on a probe, and the checker keeps its model.** The
client-note register is third person, written by a colleague, because a section has
no author for a first-person statement to bind to; the checker is told that the
carrier description identifies the text and asserts nothing about the world, a
hypothesis fix for the measurement world's hedged-ownership reading, judged by the
golden audit and never proven a root cause; and a one-fact section is one or two
sentences, since paraphrase is what the checker files as other claims. The section
probe fixed two checker-prompt facts, that the carrier rows' value form says the
subject is the text itself and the value the named employee, and that a statement
recorded as a proposition, or one restating it, is never an other claim; zero of six
constructions were accepted before them, six of six after. The ticket-comment
register was rewritten on the writer's side after the golden plan's first dispatch
exhausted the cap on one comment, a collision by construction between a register
asking for "a remark about the work as it stands" and a checker contract that
records every statement about work as an other claim, triggered every time by the
ticket's title, with the checker also reading a component named as the work's
context as the author's membership: a factual remark about what the author knows or
has done, no assessment of the work, no component or team named, zero of six
becoming six of six on the failing target and eleven of fourteen over the three
comment briefs, the section probe six of six under the untouched checker prompt as
the control, the component clause obeyed in about half the texts and recorded as
measured. A checker-side sentence against inferring membership was probed in two
placements, read identically under both, and was dropped; the register change is
what the record credits, and the residual readings are false positives that
containment turns into attempts spent, never an accepted claim; no exhaustion
probability is estimated from fourteen attempts over three unlike briefs, the claim
being only that at a cap of eight the failure mode is no longer systematic. Nova Pro
stays the checker over Haiku 4.5, whose stricter reading filed the writer's own
experience claims as other claims; the pair's different families are part of the
independence claim and a substitution on five sentences would be a different
materialization design with its own ruling, and the disagreement is the finding,
that the automated gate is limited by the checker's proposition recall, which is why
the first set's coverage is three layers together, the lexical guards, the
extraction containment and the human acceptance of every answer-changing text.

**Required-source derivation is semantic, not provenance-based, and its one untested
half is a documented claim with a re-arm list.** The responsibility class plants no
tracker artifact and its key requires the tracker anyway through the known-negatives
of everyone lacking the skill, which a construction test pins. The other half, a
foreign fact that changes the derived required-source set while every ordinary
conclusion stays unchanged, no current class can produce: provenance pins the HR
record and each artifact's source and a foreign fact cannot unpin them, the tracker
is the only source that enters by outage alone and cannot leave without a foreign
fact moving a verdict first, and the corpus is never promoted under a tracker outage
for ownership; a test built to exhibit the shape would need semantics production
lacks and would test the fixture, so none is written; the source-probe tables were
re-read line for line at the close, and one perturbation the probes cannot make is
on record, a second document naming any owner for a ticket, which the fact base does
not admit. Re-arm whenever a rule or registry change creates a new way for
source-outage sensitivity to vary independently of ordinary conclusions: a predicate
gaining another plantable evidence source, a change of authority or fallback, a rule
reading an unused domain, applicability derivation introducing a source, or a change
to the derivation itself.

---

## Sealing and the audit

**Benchmark state is split by audience and authority, and "sealed" is enforced, not
promised.** World and truth live in separate S3 buckets; the application's instance
role can read the world bucket's `worlds/` prefix and has no capability over truth
at all, not a read, not an assume. The evidence a reader can check is taken on the
host itself, on every deploy, under the real instance profile: the deploy job runs a
boundary probe after the deploy script, a list of `worlds/` succeeding as the
positive control, then a list of the truth bucket and a get of a key known to exist
there both refused with the `AccessDenied` code specifically, anything else turning
the deploy red with no rollback, since a broken boundary is the platform's fault and
not an image's. The key must exist because S3 answers a get of an absent key with
`AccessDenied` whenever list is denied, whatever the get permission says; the first
probes proved only the list denial that way, and a platform-owned canary object
outside the final prefixes closed the gap.

**The generator is never part of the deployed runtime and never runs from the
instance.** It knows both halves of the split. An earlier design had it assume a
generator role from the instance profile through STS, and that was a process
distinction, not an IAM one: a role the instance role may assume is a role the
application can obtain, so the boundary was a promise. The generator and the
validator are instead dispatched jobs under one GitHub environment, the single
privileged operator plane, reviewer-gated and `main`-only, separate from the
production environment the deploy job uses so the deploy job cannot write truth;
each job assumes its own OIDC-trusted role (the generator writes the truth and the
world, the validator reads the world and the truth's spec and writes nothing but
verdicts), no long-lived AWS secret anywhere, the session bounded and the workflow's
timeout under it since the exported credentials are static. The split lives in the
two roles' policies, not in a second environment, which would guard against the
project's own committed workflow code at the cost of duplicating the vendor secrets;
binding each role to its workflow file through the token's `job_workflow_ref` claim
is the later hardening. The runner's vendor credentials are environment secrets
scoped to the one step that runs the entry point, and from the investigator
milestone on one credential per consumer, so no secret ever lives in two stores. The
validator's read-only role toward the vendors rests today on the read ports and the
import law under the generator's credentials; separate read principals arrive at the
investigator milestone's entry. The evaluator's role waits for that entry too, when
its execution boundary is known, since a guessed trust frozen now would be a hole in
the sealing claim.

**Integrity is the guarantee underneath secrecy.** Every final object is written
once, by a conditional create the bucket policy enforces on the final prefixes (a
plain put refused, a second create refused, and a refusal accepted only when the
bytes already there are the bytes being sealed), versioned with no delete grant to
any job, its version id recorded; every world records its truth digest; every
evaluation run records world version, scenario id, seed, truth digest and version
id, harness commit and model before grading, so a result months later is the same
question about the same world against the same key. Held-out truth and its audit
notes stay in the truth bucket, never in the public repository; the repository
publishes the audit methodology and fully released example scenarios, and a retired
evaluation set can be published whole.

**Two audit depths make "golden" an honest word.** Every scenario receives
deterministic validation and a human acceptance pass (the scenario, its truth, the
expected claims, obvious consistency), so every scenario in the set has been looked
at. Ten of them, stratified across the tiers so that conflict, missing information,
uncovered, free-text qualification and the cardinality clause are all represented,
receive the full trace: every expected claim followed back through its evidence, the
candidate facts, the distractors, the authority resolution and the coverage outcome.
Thirty scenarios inspected only ten deep would be a generated evaluation set with an
audited subset, and would be named that. The protocol is `AUDIT_METHODOLOGY.md`,
published scenario-free; the checklist an audit ran under is sealed beside its
record.

**The audit is written once under a content-addressed identity.** Four objects under
the truth bucket's create-only audit prefix: an index, the rulings record, the
summary and the checklist. The identity is the digest of the index, a small
canonical JSON binding the other three by digest with the sheet's digest, the
world's sealed provenance and the validator's verdict key; content-addressed like
every key in the layout and never ordinal, so a corrected audit is a new identity
beside the old with the old named in the index's `supersedes` field, never a
rewrite. The prefix was made create-only before the first upload; overwrite is
refused by policy for every principal, delete is held by convention and versioning
rather than policy, a reader verifies by re-hashing the index against the prefix
(the index sits inside the prefix it names and cannot carry its own digest) and the
files against the digests the index carries, and the only writer is a human under
the administrator identity from a workstation.

**A scenario released as an example is retired first.** It keeps its place in the
sealed world and in the audit's provenance (neither is ever edited), it leaves the
scored set of every later blinded evaluation, the evaluation's manifest names it as
retired with the release date, and the release carries a contamination statement. A
release renders the dated view only, since the construction patterns are already
public in this record and what a release adds is one world's roster, one scenario's
plantings and prose, and the rows its cited entities carry: never the rows
observable after the scenario's `now`, never the sheet header's prose rollups, never
a note that cross-references another scenario. No golden scenario is released before
the first evaluation has run over the whole set, since the example a reader values
is the key beside an agent's run on it, and retirement before any evaluation would
be a promise with nothing to enforce it. Until then a throwaway-seed world, never
sealed or scored, illustrates the sheet in the public tree
(`docs/examples/audit_sheet_throwaway.md`), its rows observable after `now` kept,
since that world has nothing to protect.

> **Outcome.** The first golden world is sealed at generator version 14 and its
> audit is sealed under its content-addressed identity, `supersedes` null. The sweep
> behind the offered plan admitted and verified 199 of 200 seeds, none contaminated,
> one exhausted by a qualification row crossing three reservation rules at once, a
> loud refusal under a contract that promises no world for every seed. The hand
> audit executed the acceptance pass over all thirty scenarios, seventeen deep
> traces (ten stratified, five by unexercised structure, two named by a critique
> panel) under a frozen trace, a four-seat critique of the checklist, the sheet, the
> record and the summary with every claim reproduced on the source, and a hand
> recount of the seven uncovered or unknown outcomes from a criterion universe per
> impact, seven of seven equal to the witness. Findings: thirty accept, no defect in
> the world, no open question; the audit's own record corrected in eleven places
> with dated notes, none touching a key; one design gap surfaced and ruled (leave
> dates and the far seat, above). What the audit cannot claim: it verifies the key
> against the rules as coded and a human reading of the evidence, the recount
> sharing the rule's dated view; thirteen scenarios rest on the pass, the executed
> checks and the recount rather than a trace; the reads were an external low-context
> reader's, re-verified before entry, and the rulings the auditor's. Two limitations
> are on record for the evaluator's design: every accepted qualification comment
> opens on one sentence frame ("I have X experience"), a realism limitation not
> tuned unless an agent is found to exploit it; and the three-character
> exact-spelling cut in the namespace scanner remained unexercised, since no comment
> tripped it. The subsequent external repository audit found fourteen defects
> outside the sealed objects, none touching a key; its two construction findings
> became the plan's declared supported domain. The full narrative is in
> `REPORT_NOTES.md`.

---

## Keeping the benchmark out of the product

**Three layers, and adapters that translate but never launder.** The synthetic world
exists independently of any vendor; each external system holds a representation of
it; the agent sees a domain-shaped tool surface (`search_work_items(employee_id=…)`,
`search_policy(…)`) and never a vendor's identity system or query syntax, because
the question is whether an agent can gather evidence across organizational systems,
not whether it knows JQL. The adapters own credentials, HTTP, pagination, retries
and the identity mapping, and they stay thin: every world fact passes through as the
system reports it, contradictions included, since an adapter that normalized a
planted inconsistency away would destroy the evidence the evaluation grades. Tools
answer questions about the world and make no decisions; real-API behaviour surfaces
as a tool failure, itself an evaluated condition; swapping a vendor touches one
adapter.

**A tool is one typed specification over one read-port method, constructed by a
declared registry; MCP was weighed and not chosen.** The thirteen read-port methods
are the whole tool surface. Each tool is a specification (name, description,
argument bounds including the search limit, id validation, the serialization of the
observed record, the logging hook) naming exactly one port method; the model schema
is generated from it, and a tool makes no domain decision. The registry declares per
role which methods become tools, so a tool list is constructed and never prompted,
and least privilege is the registry and a role-scoped read-only vendor principal
together: the registry is a harness-level claim, the principal is what makes it
provable against the vendor. No tool takes a date: the wrapper stamps every
observation with the run's `now`, the rules read the stamp, the model supplies none,
and what a read returns is not filtered by date (time is applied above the port), so
a wrong-time call cannot be expressed and a span argument is scope the model
chooses, logged and not graded. MCP was the alternative transport (ruled
2026-09-20): what a protocol buys is interoperability and discovery across a
boundary the project does not control, and the investigator milestone has one
in-process consumer of a small owned read surface, so a server would add a process,
a transport, an adapter dependency and a second copy of the schema while hiding
nothing. It is reopened by an independently deployed or external client that needs a
shared protocol; the conversation surface runs in the same application and reuses
the registry directly, and the registry is what a server would wrap, so the cost then
is the transport, not a redesign.

**One class per system implements both of its ports, and a domain id has exactly one
vendor representation per place.** The read and the write side share a transport, a
scope and an identity map, and which side a caller holds is the type it is handed.
The vendors enforce no uniqueness, so each adapter checks it on every select and
enumeration, and a duplicate is a `MalformedRecord`, never chosen from. The
vendor-specific choices, each from a probe or a review: Frappe's missing facts ride
custom fields, a skill-bearing employee is one `insert_many` call because Frappe
runs it as one transaction, a leave's kind is a Leave Type with four masters flagged
leave-without-pay so an application needs no allocation, balances being outside the
truth model, every read filters by the configured company and every write plants it,
and employees are named by number, because the skill map has to name the employee
before either document exists, which makes the number unique per site rather than
per company, so one world is one site; Jira's field ids are configured, never
discovered, its owner options are project-scoped because employee ids restart in
every world, and a work item's marker is set in the final request so a half-written
issue stays invisible to the domain and a restart creates the item whole, the marker
alone declared replayable since setting a field to a value is the same world whether
it lands once or twice, while a search on the trailing index waits within a bound
until the item is readable by id and raises `SourceUnreachable` if it never is; a
calendar event is one event per attendee with the id derived from the domain id, so
an insert is idempotent and a conflict means verify, and calendar ids are
configuration because the app-created scope cannot list them, preparation verifying
or creating one calendar per person and saving the manifest after each obtained id,
so an interrupted attempt orphans at most one empty calendar and a manifest lost
after creation leaves orphans only a human can see, which is the whole of that
limitation, the adapter riding the shared transport with plain calls rather than
Google's discovery client, which ships no types and retries on a sleep outside the
injected clock; the corpus ranks full-text hits per section with a document taking
its best section's rank and the id as the stable tie-break, ships its DDL as package
data applied idempotently at composition, and writes a document with its sections in
one explicit transaction, after an implicit one lost every document at the module's
first review.

**Ranks give the default dependency direction; denied edges enforce the trust
boundaries.** A rank law alone would have let the investigator import the fact base,
the keys and the briefs at source level while credentials kept it from the truth
bucket at run time, a boundary the whole answer-key design depends on, left to
convention.

| Rank | Package | Purity | Holds |
|---|---|---|---|
| 0 | `core` | pure | domain types, the predicate registry, the claim vocabulary, `RunContext` and world time, the pure rules, vendor-neutral ports |
| 1 | `world` | pure | the benchmark: world spec, scenarios, truth facts, keys, briefs, the materialization record, the semantic generator, the construction invariants |
| 2 | `adapters` | shell | one external boundary each (`frappe`, `jira`, `calendar`, `corpus`, `prose`), the object store, the shared read wiring |
| 3 | `generator`, `validator` | shell | materialization, projection and sealing; read-only verification of the live systems |
| 3 | `evaluator`, `agent` | shell | the investigator milestone's; named now so the law has their place |
| 4 | `app` | shell | the demo milestone's surface |

The laws, all of them tests: imports point strictly downward; no lateral imports
among the rank-3 shells, so read-only and non-echo are architectural rather than
aspirational; `agent` never imports the benchmark or its judges and `app` never a
benchmark package; `core` never imports `world`, since the production investigator
depends on the domain without depending on the benchmark that grades it, which is
why `world` stays a separate package however small; `core` and `world` perform no
I/O, guarded by a forbidden-import list that is a cheap guard and not a proof;
sibling adapters never import one another, since cross-system orchestration lives
above them and only an untangled shell can obey the top-level law; external identity
is supplied at composition, one `JiraAdapter` taking a credential rather than a
generator's and an agent's variant, so the two principals differ in authority and
share transport; and wall-clock time is read only at a composition root and
converted into context at once, retries and timeouts using monotonic elapsed time,
an infrastructure concern that never touches scenario time. Only the packages a
milestone needs exist, since empty placeholder packages would be structure for its
own sake; each later milestone scaffolds its own package after its own design
session, and the structural test carries the full graph and skips the rest.

**The pure rules live in `core`, shared by the evaluator and the investigator**,
which makes the sharing visible where duplication would hide it. Sharing rules is
not the generator-echo problem; the edges that would be are `evaluator → agent` and
its reverse, both denied. Two independent sources check the shared implementation:
the `must_assess` verdicts, authored independently of the rule, and hand-written
rule cases. Domain-facing ports sit below their implementations because both the
generator and the investigator consume them: an abstraction that describes what the
domain needs belongs below the adapter, one that describes how Jira works belongs
inside the Jira adapter; no interface is manufactured to look hexagonal. Two
verification points, two packages: the truth-level checks are construction
invariants in `world`, run before sealing; the validator verifies that projection
realized the declared world and never reads truth.

**A port returns observed entities, never facts.** `core` derives facts and gaps
from an observed entity in one deterministic derivation, so an adapter never decides
what is true, the per-field meaning of absence is stated once (a missing skills
field is a gap, an empty one zero facts, a missing due date or manager an observed
negative, and a requested leave, a comment, a team and a document derive nothing),
when a fact became observable is the caller's knowledge and a parameter of the
derivation (the entities keep vendor timestamps out), the observed-entity wrapper
carries only the source, explicit rather than inferred from the type because the
registry keys conflicts by source and a second system claiming the same kind of
record is a designed-for case, and the investigator's live reads and the world's
truth base agree on what every field means by construction. The corpus is the
exception and not a reason to return facts: the document port returns text and
derives nothing, the investigator cites which clause applies and never transcribes
content, and no extraction seam exists anywhere. **Reading and writing are two
modules, so read-only is a property of the module graph**: only the generator's
shells may import a gated write module, no package `__init__` may name one, each
store backend is a reader class with a gated writer subclass, and only a gated
module may name a writer at module scope, each rule from a review that found the
boundary porous. The validator's one write, its verdict, crosses as a callable that
seals exactly one key. None of this is a sandbox: the law makes an accidental
violation fail CI, and IAM remains the runtime boundary. A writer adds and never
finds; a fact-bearing reader enumerates, selects by identity or narrows by a natural
window, and never filters by a derived relationship, because a closed domain's
"known false" is honoured only when the run read the universe to completion and a
malformed record raised instead of being dropped by a vendor-side filter.
Reachability is not completeness: the run condition records the first and the
ingestion lifecycle owns the second, a contract the derivation states and the
investigator's harness will have to keep, an explicit record only if reads ever turn
incremental. "What Alice owns" is then a filter over facts derived from every work
item, retrieval efficiency spent for evidence semantics, negligible at this world
size, pagination staying the adapter's. **`RunContext` carries the leave under
investigation as an id and nothing more**: run inputs identify what to investigate,
ports establish the facts, so the leave record is read as evidence a scenario can
contradict, and a run that cannot read it continues degraded rather than inventing
the span, everything downstream unknown and not only `on_leave`, how that grades
being the evaluator's design. **A port reports three outcomes three ways**, because
closure treats them differently: a record that is not there is `None` or empty; a
source that cannot answer raises `SourceUnreachable`, an epistemic limit the run
condition records, the fault per call: the first marks the source unreachable for
the rest of the run and stops the calls, facts already read stay facts because
closure checks a positive fact before reachability, a fault halfway marks the source
unreachable rather than leaving a partial read to be graded as absence, and
`RunCondition` describes the run as it ended; a record that cannot be translated
raises `MalformedRecord`, a defect and never an unknown, which crashes the generator
and the validator, whose job catching a malformed projection is, while whether the
investigator degrades instead is its own milestone's runtime policy. The two share
no base, and a vendor exception never leaves its adapter.

**The investigator, at its milestone's entry, inherits five commitments.** It emits
the frozen vocabulary and nothing else of its output is graded; its deterministic
core is the pure rules `core` holds, the same functions the evaluator runs, over
facts derived through the read ports; it learns the leave from `RunContext` and the
world's date from the run, never the machine's clock; it observes everything the
reads return, dated to the run's day, and knows no planting date; and it may not
import the benchmark. The framework, the tool transport, retrieval and the harness
were ruled at that entry (2026-09-20; the tool paragraph above, the deployment
section below). **The evaluator, at its entry, inherits four.** It
grades the frozen vocabulary by the rules stated above, the pure rules deciding any
candidate the key did not author; it admits truth time-filtered by the scenario's
`now` and only from the sealed objects, recording world version, truth digest and
version id before grading; it shares the pure rules with the investigator through
`core` while neither imports the other; and its decoder honours absent against empty
on the key's derived-conclusion fields. Its execution boundary, its identity, its
metrics beyond the grading and the baselines it grades beside the agent were ruled
at that entry, 2026-09-20, as follows.

**The evaluator runs as a dispatched workflow under its own identity, grades what the
recorded run observed, and never re-reads a vendor.** Its role is trusted only to a
GitHub environment that holds no secrets, so a vendor credential cannot reach the
job even if a reference is added later, and the boundary is IAM rather than a
workflow review; it reads the truth manifest, the sealed spec and run exports, writes
evaluations by conditional create, holds no model grant, and probes its own
boundary on every dispatch (the truth manifest readable as the positive control, a
put under the served worlds and a model invoke refused). Evaluations live with the
truth, since an object naming which claims matched the key reveals the key; run
exports live in the world bucket outside the served-worlds tree, the instance
holding a create-only put there and nothing else. An export is complete enough to
replay the grading: run context, ordered tool requests with a stable identifier per
recorded operation, returned records, completed and failed reads, the final claims,
and the provenance the run record carries (the observed run condition and the
assigned outage schedule, harness commit, model and inference settings, prompt
digests, the tool-list digest, the preregistration commit, observed usage and cost,
any failure category); the evaluation artifact adds the export's key and version id
beside the truth digest and version id. The validator re-reads the live systems and
the evaluator does not: that is the difference between them. The evaluator on the
instance under a second principal was rejected on the executor paragraph's own
sentence, two principals on one host being two configurations and not a boundary;
workstation runs were rejected because evaluation repeats and needs run-and-attempt
provenance.

**The metrics beyond grading come from the export.** Source discipline: required-
source attempts and successes, malformed calls, extra reads recorded as cost and not
as mistakes (the key seals no right query per call, and an extra read may be a
distractor investigated); a retrieval hit rate, whether the key's answer-changing
section or clause appeared in the returned top-k of each search the run made, reported
before citation quality so a missed claim is attributed between returned-and-ignored
and never-retrieved. The run condition is derived from the reads that actually
failed, the assigned schedule recorded beside it; a system that never called the
failed source ran under no outage. Outage runs follow one injection schedule
registered before any run and are reported apart from normal runs. Results are x/n
per class and tier with Wilson intervals beside, one organization stated, and every
reported table shows all attempted runs and failure counts by category beside the
metrics on completed runs, so an exclusion is a visible smaller denominator and
never a better score.

**Two baseline systems are preregistered beside the agent and graded by the same
evaluator from the same export shape.** Rules-only: the pure rules over facts derived
from a frozen structured prefetch, no prose read. Single-shot: one model call, no
tools, over that prefetch plus one fixed corpus retrieval whose query is written down
before any run. The prefetch and its candidate-selection rule are one frozen rule for
all three systems, a floor the agent may extend through tools and the baselines may
not, and it can use no sealed key because the harness cannot import the benchmark.
The comparisons measure the incremental performance, cost and latency of these
specified systems; a causal claim about the model or the tools needs a controlled
arm, and the retrieval and decomposition arms are such arms, added after the core is
measured. The rules-only result on the structured tier is a plumbing check on shared
rules and never an oracle, since the baseline and the evaluator share the rules; a
miss there is investigated, never pre-classified. One model per comparison, held
constant across the agent and the single-shot baseline and recorded per run; which
models the comparison arm lists is the preregistration's to state after the ten-run
reforecast, because a model is one identifier to switch while prompt text and
reported numbers bind to it.

**One committed preregistration file precedes the first reported run and is cited by
commit in every evaluation artifact.** It holds the metric definitions, both
baselines and the fixed query, the prefetch rule, the outage set and injection point,
the per-run cap, the ledger threshold, the model per role, the iteration subset and
the full set, and the budget's three numbers. Development runs carry the draft's
commit and are labeled development; the reporting design is frozen before the first
full-set measurement. A change after full-set results is a new preregistration, the
old numbers kept, further results on the same world labeled exploratory, and
confirmation needs a world from a new seed, which the generator produces for one
projection day.

---

## Verification

**The test suite answers five distinct questions; each level owns one.** The
inherited suite was unit-dominant with an unlabeled integration layer and nothing
end-to-end; this project names the levels because it has real external systems and a
real PostgreSQL.

| Level | Question | What runs | When |
|---|---|---|---|
| unit | is the pure core right? | rules, checks, codecs, no I/O; doctests and pytest | every push, default |
| integration | do the seams hold against real dependencies? | the store against a real PostgreSQL service, never a SQLite stand-in, since the store is evaluated on the terms it runs on; adapters against recorded cassettes | every push, `-m integration` |
| live contract | has an external API drifted from the cassettes? | the same adapter tests re-run against the real sandboxes under a record mode; the narrower `live` marker is a test with no cassette possible | gated by env, on demand |
| agent smoke | does the loop's plumbing work end to end without model spend? | one scenario through the real loop with a scripted fake model | every push |
| e2e | does the deployed thing work? | after deploy, through the public hostname | the deploy job, post-approval |

Network access is blocked for every test by default, so only a cassette-marked test
under a record mode reaches a sandbox; a cassette is scrubbed by hook before it is
written, and a structural gate checks that every request host and every header URL
in every committed cassette is a placeholder or a public API host, since CI has no
sandbox secrets and "the real host is absent" could otherwise pass vacuously there.
**Cassettes are the honest fake**, real payload shapes, and the gated live replay is
what keeps them from drifting silently; hand-written fakes were rejected because
they drift without a signal. Coverage is measured, never gated: the number shows
where the unit layer is thin, and a threshold only invites theater. PostgreSQL runs
as a CI service from the first commit, so the pattern exists when the code arrives.

**The eval is not a test.** The golden-set harness with real models is the project's
end-to-end evidence, and it is an experiment: preregistered design, a budget,
baselines, uncertainty reported, its output a finding rather than a green check. It
lives in its own tooling, and the suite's only contact with it is the agent-smoke
level, plumbing verified with a fake model so an eval run never fails for a non-eval
reason. Listing the eval beside pytest markers would blur exactly the distinction
the project exists to demonstrate. **Structural laws are tests**: the import law and
the module ranks ship as pytest tests, the sibling project's import-graph test being
the precedent.

**The baseline inherits the sibling project where it proved out and improves where
it was thin.** Inherited: the `uv_build` backend, src layout, locked sync in CI,
ruff at 100 columns, pyright strict over `src` and `tests`, doctests, the two-stage
Dockerfile with a provenance-or-refuse version guard and a non-root runtime, a
production Compose with no `build:`, and the check, image, deploy pipeline behind an
approval environment. Improved: images built for `arm64` and `amd64`; the pdoc build
in CI so a module that fails to import fails the push; a `justfile` whose `check`
recipe is the fast subset of the CI gate; the pre-commit framework so a fresh clone
is scanned; Compose health checks; the deploy transport SSM, not SSH.

---

## The deployment the evidence is served from

**The hybrid split.** The application runs on AWS; Frappe HR stays on the existing
netcup box. Frappe is a heavy, stateful, multi-process system used *as* a realistic
HRIS; nothing about hosting it on a hyperscaler adds to the product, while cheap
persistent compute for it already exists. The application is the engineering that
matters, and a cloud deployment with the same operating discipline as the box is
itself a deliverable. The split also makes the boundary honest: the application
reaches Frappe as a remote system behind an `HRProvider` adapter over an
authenticated API, exactly as it would reach a customer's BambooHR, rather than
pretending a local container is an enterprise integration, and "HRIS unavailable"
becomes a real failure mode the system must degrade through. Rejected: everything on
the box (no cloud evidence), the box plus peripheral AWS services (an app that "uses
S3 and Bedrock" is not a cloud deployment), and everything on AWS (paying to host
the simulation for no product reason). The hybrid's own named risk, "a VPS with a
logo", is answered by the surrounding discipline.

**Hosts consume artifacts; they never manufacture them.** Frappe HR needs a custom
image, since no official one carries the `hrms` app, and the box's rule holds for
every deployable: source, CI build, registry, host, the host pulling what CI built.
The intended reference is the image's manifest digest, the one identity a registry
cannot move; today the host pulls the commit tag and CI records the digest in the
build's summary, a gap the updater work at the investigator milestone's entry closes
with the base-image pins and a final-image smoke. CI rebuilds an image only when its
inputs change, never when deployment settings do, since image definition and
deployment definition are different artifacts. Rejected: a one-time build on the box
and builds from the workstation, a release step in an undocumented environment. What
the rule buys is the claim that the production machine is replaceable.

**The application host: one EC2 instance, one Compose stack.** A `t4g.small` runs
the application and its PostgreSQL in Docker Compose, the database on an EBS volume,
Cloudflare in front as the only ingress, inbound restricted to Cloudflare's ranges,
administrative access through SSM with no public SSH port. It is the cheapest
always-on shape that keeps PostgreSQL local; an always-on Fargate service with an
ALB and RDS lands near two and a half times the cost for no architectural benefit at
one-process scale, RDS being a cost floor and the ALB pure overhead behind
Cloudflare, and a serverless agent would deform multi-minute narrated runs around a
fifteen-minute ceiling. Self-managed PostgreSQL carries its own obligation: a
nightly backup shipped off-host and one demonstrated restore as an exit criterion,
since owning recovery is the price of not paying for RDS.

**PostgreSQL is the application's truth; Frappe keeps its MariaDB.** Runs, events,
tool calls, evidence references, plans, decisions and evaluation runs form a
genuinely relational model, and the framework's checkpoints land in the same
database so a run survives its worker. Frappe-on-PostgreSQL is the less-trodden path
and week-one infrastructure eating the schedule is the vision's first-named risk.
PostgreSQL on the box, reached remotely like Frappe, was rejected: the application
store is chatty where Frappe is coarse, so every run would pay hundreds of
cross-provider round trips, it would put the production write path on a public link
and confound the HRIS-unavailable case with the app's own outage, and it unlocks no
better AWS shape, the ephemeral tier it would cheapen being the one where a remote
store hurts most, for about six dollars a month.

**The job seam: runs write an event log, surfaces read it.** An investigation is a
job that appends narrated events and checkpoints to PostgreSQL; the UI streams by
reading that log, never by holding the worker's socket. The seam is justified on its
own, since it is what makes runs resumable, auditable and replayable, and it is also
what makes the worker's location a deployment detail: in-process on the instance
today, an ephemeral task later. No generic compute abstraction is built on top of
it.

**The loop runs on LangGraph, contained within the agent package, with two stores of
explicit authority.** Ruled at the investigator milestone's entry (2026-09-20) on the
five criteria the vision fixed, narrated streaming, tool orchestration, a
human-approval step, an audit trail and resumable runs against this seam, each of
which the framework's checkpoint, interrupt and stream primitives answer, and on the
positioning this project serves, where a named framework is the most frequent gap. A
hand-rolled loop (every mechanism owned, no dependency family) was the lean and was
rejected on that weighing; Anthropic-only SDKs on the two-family shortlist. The read
ports, the tool registry, the claim vocabulary and this seam know nothing of the
framework; tools are constructed from the registry and handed to it; the model is
reached through the framework's Converse chat model, a different client from the
generator's prose seam, which stays as it is. The checkpoint is the execution cursor
for resuming a run and nothing more, since it cannot be rebuilt from the log; the
event log is the authority for audit, narration and the run export; every recorded
operation carries a stable identifier so a resumed node's repeated append is refused
rather than duplicated, and the two stores must reconcile after every tested crash
point. The ruling is provisional on an acceptance spike, the first harness build step,
built as the smallest real vertical slice on PostgreSQL: resume an interrupted run
after a process restart with one approval event; a crash injected around a tool
result, its checkpoint and its event append, recovered with no duplicated or missing
event; streaming and forced tool calls through the actual `eu.` Anthropic and Nova
configurations, which the prose probe's different client path does not establish;
the complete export from the event log alone. A failure is attributed first: a
persistence-design failure fixes the design, which a hand-rolled loop would share; an
integration failure reopens the framework before any further harness code.

**The investigator's runtime policy keeps the fault triad's meanings.** A missing
record is evidence; the first unreachable source marks that source unreachable for
the run and calls stop, facts already read standing; an unreadable leave record
degrades the run, everything downstream unknown. A malformed record propagates and
the run fails by defect, recorded with the fault, excluded from grading and counted,
because the validator certified record fidelity before any run and a degrade would
fold a defect into a legitimate unknown; production fault tolerance behind a real
HRMS is future work the benchmark does not prove, and this document says so. A
provider fault after the SDK's retries fails the run by infrastructure, counted
apart; a response that arrives and refuses, emits no claims or emits output the codec
rejects is system behaviour, graded with its omissions.

**The executor trust boundary, if post-approval execution ships.** The writes run in
a deterministic executor Lambda, not a second agent, with its own IAM role that is
the sole principal able to read the write credentials and with no model-invocation
permission at all; input is the human-approved action manifest, output the exact
approved writes plus an audit artifact. Two principals on one host would be two
configurations, not a boundary; a separate execution identity is what makes the
least-privilege claim provable rather than intended. Gated on the open question
below; if execution is out, the Lambda and its secrets namespace are not built.
Ruled out for the investigator milestone (2026-09-20): no executor, no execution
identity, no write credential, a run still ending in the approved-plan state the
event log holds and nothing consumes. "No IAM split" names the executor's identity
only; the investigator's read-only vendor principals, delivered to the instance, and
the evaluator's identity are ruled on their own. The paragraph stands as the
candidate architecture, entered only if a later milestone brings execution back.

**The surrounding AWS set, and nothing more.** All of it under Terraform in the
platform repository, this repository consuming the contract values it publishes: IAM
roles; GitHub Actions deploying through OIDC federation, the trust policy pinned to
the repository and the production environment through the ID-based subject GitHub
emits, no stored keys; Parameter Store for secrets (Secrets Manager's per-secret fee
buys rotation nothing here needs); CloudWatch; S3 for the sealed worlds, evaluation
reports and audit trails; a Budgets alert created by hand before any infrastructure
existed, so the guardrail predates the resources. Not added until a requirement
names it: ECS services, EKS, RDS, queues, event buses, CDNs, caches, a managed
vector store. **Bedrock is the sole model provider behind a model seam.** The
Converse API gives one request shape across model families, so the seam's question
is which model per role (investigator, extraction sub-tasks, grading), answered by
the evaluation on the golden set rather than fixed up front, from the models the
account can call rather than the catalogue; the seam checks a model's feature
support at startup so a mismatch fails loudly. The shortlist the instance may invoke
is re-cut to what the account can call, the gated 5-series rows returning the day
the account review passes; the prose stage's Haiku 4.5 writer and Nova Pro checker
are configuration, not architecture. Residency is `eu.` inference profiles
throughout at their ten-percent premium: the data is synthetic, so this is a story
ruling, Frankfurt end to end, and the cross-region cache misses the probe observed
are an `eu.` fact that `global.` would only widen. Model choice for the agent waits
for the agent measurements.

**The netcup box was upgraded in place, once, to the tariff above the need.** Lite 3
(8 vCPU / 16 GB) over Lite 2 (4 vCPU / 8 GB): 8 GB is Frappe's recommended footprint
alone, the box's own design is one VPS running every project, and downgrades do not
exist while each upgrade resets the term, so headroom is bought once at box level
rather than in a second upgrade later; Lite 2 is not revisited, the upgrade being
one-way. The upgrade was a probe-day step, and Frappe's footprint is now a measured
number, under a gigabyte idle with a site installed, so the recommendation was
vendor sizing and the 8 GB bought headroom rather than met a need. Compose memory
limits on the Frappe stack and a swapfile keep the heaviest tenant from starving its
neighbour. A second box was rejected as two proxies, two firewalls and two backup
paths for no benefit.

**Cost envelopes are stated and tracked.** Persistent spend excluding tokens is the
box delta plus roughly twenty dollars a month of always-on AWS at list prices for
the provisioned shape (the account holds no free-tier allowance, so these are the
real rates), the instance line removable by stopping it between working days. Model
tokens are the larger line, since an agentic loop re-sends a growing context every
turn; a single investigation is estimated near seventy-five cents on Sonnet-class
pricing with prompt caching, about three times that without, an evaluation pass
scaling with scenario count, and the budget is preregistered in three numbers:
expected $150 for the investigator milestone, hard ceiling $300, mandatory
reforecast after the first ten representative runs. The levers are design-level: a
tiered scenario subset for iteration with the full set only for reported numbers,
the deterministic core pre-fetching structured facts so the agent starts with
evidence, a cheaper model for sub-tasks, the Batch API for any non-interactive step.
Per-run cost is a hypothesis until measured. Enforcement is two mechanisms (ruled
2026-09-20): a preregistered per-run cap on calls and tokens that reserves a
finalization allowance, a run at the cap reporting what it has, marked and graded, or
recording a failed-to-complete output graded with its omissions, never an invented
report; and a cumulative spend ledger from observed usage across runs, baselines,
arms and evaluator executions with an admission stop at a preregistered threshold,
the ten-run reforecast reading it, since a per-run cap bounds one run and not the
milestone. The stack's monthly budget stays the outer alarm.

**The Frappe hostnames sit behind Cloudflare Access; the agent's own hostname stays
ungated until the demo.** The generator's first write from the cloud is a cross-host
call over the public edge, so the service token joins the secrets ceremony and the
Frappe login stops being scannable; the agent's hostname serves a hello page until
the demo milestone and that demo must be public, so the question returns at that
milestone's entry rather than being decided twice. The Access application is
platform work; this document rules only which hostnames. Confirmed at the
investigator milestone's entry (2026-09-20): Access lands within that milestone,
after the three identity tickets (the validator's, the investigator's and the
evaluator's principals), since the change touches the generator's and validator's
proven paths; until it lands the machine clients ride the public edge with
application auth, a dated interim and not a deferral, with a successful read from
the instance under its own read-only principals required before the first live
investigation. Private connectivity between the hosts (a private network, a mesh, a
tunnel) was placed at that entry by the step-13 incident's note and is superseded to
the demo milestone's entry or observed abuse before it: Access gives the token-gated
property without a tunnel or a third control plane, and nothing in the investigator
milestone needs a hostname to be unreachable.

---

## Scope & non-goals

- **In:** the hosting shape above from the first probe day; the deployment itself is
  continuous from the first application slice.
- **Deliberately out:** any AWS service beyond the named set until a requirement
  names it; service count does not add to the design.
- **The organizational tools cost nothing.** Jira, Frappe and Google Calendar run on
  free tiers; spend is AWS and model tokens only. This rules out paid Atlassian
  seats and Atlassian's official MCP server (paid plans only), so Jira access is the
  project's own REST adapter.
- **The schedule cuts.** With four of the envelope's six weeks gone at the probe days,
  six holds only with cuts: post-approval execution is out (no executor Lambda, no IAM
  split; confirmed at the investigator milestone's entry, the split meaning the
  executor's identity only), but a run still ends in an approved-plan state in the event
  log that nothing consumes yet, so an executor later is a new consumer rather than a
  reworked seam; Slack is out for the world and investigator milestones, the adapter
  seam kept; the conversation milestone moves to backlog and is not part of the six-week
  claim; the first corpus is one answer-changing clause type and one staleness pattern.
  Each returns as an addition; none changes the shape of what is built now.
- **Not a world invariant:** whether the investigator's retrieval surfaces a planted
  section. That is the agent's evidence-coverage measurement.

## Future work (curated)

- **World-owned policies.** A scope model, applicability derivation across
  scenarios, cross-scenario constraint discovery and their whole-world verification;
  every constraint is scenario-owned until then. Trigger: a class that needs a
  clause applying across scenarios (a component-scoped constraint is the first
  candidate).
- **The stale-document false-positive modifier.** A document giving the leaver a
  ticket the tracker gives to someone else, the "stale document" distractor reason
  the ontology already names; parked rather than built into a class whose row would
  have no impact of its own. It would also give a section-artifact class its first
  look-alike.
- **The `load` viability criterion.** Pruned: no first-set class names it, and a
  threshold would be either a domain constant the agent can only be told or a clause
  no scenario uses. Returns when a class establishes its semantics.
- **Refusal feedback into the prose writer.** Rejected for the first golden set so
  that retry depth measures one fixed configuration and a systematic fault stays
  visible. Trigger: the golden audit showing a class persistently accepted on
  attempts five to eight, or unpassable, after the shared prompt is fixed; if
  introduced, a new strategy with its own digest and attempts marked base or
  corrected.
- **Benchmark coverage the first set cannot measure**, recorded by the audit for the
  next set's design: the cardinality class constructs viable equal to the count and
  never above it, so minimum-versus-exact semantics is untestable; the
  concurrent-leave modifier is outcome-insensitive by the admissibility rule, and
  outcome-pivotal loss of a cover needs a class; no component-scoped clause, no
  timezone planting beyond the one shape the organization affords, no unknown reason
  beyond an absent record, no pending or rejected leave, no `now` inside a leave.
  Trigger: the first evaluator showing which classes need more cover.
- **Constructibility under the golden plan.** The one exhausted seed in two hundred
  is a refusal the present contract allows; scarcity is measured per class, and a
  row-level key (class with modifiers) is a generalization to take on a loud
  refusal. Re-promoted the day a ruling says the plan must construct for every
  supported seed.
- **Ephemeral compute on AWS**, preregistered for the demo milestone's entry. A
  Fargate task per investigation, Aurora Serverless scaling to zero, an API Gateway
  and Lambda control plane, narration relayed from the event log: the strongest
  cloud shape for bursty agentic work, not the starting point because it is a
  different topology with a cold start near a minute and a week of plumbing that
  would come out of evaluation depth. The job seam makes it a migration rather than
  a rewrite. What does not move when the hosting shape changes: Frappe on the box
  behind the `HRProvider` adapter, the executor as its own execution identity, the
  PostgreSQL event log and checkpoints as the job seam, Bedrock as the sole provider
  behind the model seam, S3 for artifacts, the Budgets alert from day one. Criteria
  fixed now: control-plane acknowledgement within two seconds with the wait
  narrated; p95 cold-to-first-narration within forty-five seconds; migration within
  two days; idle baseline under five dollars a month; no NAT Gateway. Pass, and the
  demo ships on it; fail, and the instance stays with the measured numbers as the
  tombstone.
- **Vector retrieval as a measured arm.** The investigator milestone's core runs on
  the existing full-text search over sections, the section the unit of chunking by
  construction; pgvector in the cache and an embedding model on the platform's list
  enter as a second implementation behind the same port method in the corpus
  adapter, compared with full-text on retrieval hit rate, evidence coverage and
  citation quality over the same golden set after the core is measured, exploratory
  on this world and confirmed on a new-seed world. The comparison is the form in
  which a retrieval store is added, a component inside something evaluated and never
  the project; ranked second of the three post-core arms. A future-effective section
  can displace a current one from the top-k, since the limit precedes any date
  consideration; that stays an open measured limitation, and a filter at the tool
  enters only through a re-run of the realizability proof. Ticket comments stay with
  the work-item tool; copying them into corpus documents would change the source a
  fact is attributed to.
- **Multi-agent decomposition as a preregistered experiment**, ranked third of the
  arms after the model arm and the retrieval arm; arms slip from the bottom and an
  arm not run is reported as not run. The single investigator with all read tools is
  the reference variant, compared with the decomposed variant on the same golden set,
  metrics, calls, cost and latency, model, retrieval, prefetch and inference settings
  held fixed, the decision rule preregistered. The first hypothesis is decomposition
  by source, one reader per system holding only that system's tools and a
  synthesizer holding none; by phase is the second; count, roles and what each role
  sees as well as calls are the preregistration's. All roles in one process share
  the instance identity and the application's read-only principals, so the registry
  is harness-level least privilege and not a principal split.
- **The rationale judge**, superseded at the investigator milestone's entry (the
  grading paragraph); returns when rationale quality has a consumer, the demo's
  report view, with its hand-graded set and calibration budget.
- **MCP as the tool transport**, weighed and not chosen (the tool paragraph); returns
  with an independently deployed or external client that needs a shared protocol.
- **Production fault tolerance.** The investigator fails a run on a malformed record
  because the benchmark's world is certified clean; degrading gracefully behind a
  real HRMS is a different runtime policy the benchmark does not prove.
- **Private connectivity between the hosts**, superseded from the investigator
  milestone's entry to the demo's or observed abuse (the hosting section).
- **A direct Anthropic API path beside Bedrock.** Not committed to; one provider
  keeps credentials, billing and audit in one place. Trigger: Bedrock lacking a
  model or feature the evaluation shows the product needs.
- **Post-approval execution**, Slack, and the conversation milestone: the schedule
  cuts above, each returning as an addition.

## Open questions

Pinned to the milestone whose evidence decides each; the agenda inherited from the
vision's deferred list.

- **Framework**: closed 2026-09-20, LangGraph, provisional on the acceptance spike
  (the job-seam paragraph in the deployment section).
- **MCP versus plain function tools**: closed 2026-09-20, plain function tools from
  a declared registry, MCP tombstoned with its reason and trigger (the tool
  paragraph).
- **Post-approval execution**: closed 2026-09-20, out for this roadmap, the executor
  paragraph kept as the candidate.
- **Retrieval detail**: closed 2026-09-20, full-text over sections for the core,
  vector as a measured arm, comments with the work-item tool (future work).
- **Whether the agent's model client shares the prose adapter's Converse
  translation**: closed 2026-09-20, no; the framework's own Converse client is a
  different consumer, and the prose seam stays as it is.
- **Conversational-surface mechanics**: grounding method, refusal behaviour,
  evaluation reuse; decided at the conversation milestone's entry, strictly after
  the demo ships.
- **Per-run token cost**: the estimate is re-derived from the first ten
  representative runs at the investigator milestone; the reforecast is mandatory.