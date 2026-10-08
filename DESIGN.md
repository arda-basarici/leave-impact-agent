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

**Closure answers in a fixed order and derives three of the five unknown reasons.** It
reads the facts and gaps a view holds at `now` and asks the view what it observed. A
positive fact → known true, with the facts that established it. Otherwise each place the
answer could live is a *slice* of a source (one record, every record of a kind, the
records of a kind inside a window), and the view says of each whether it was observed
whole: a slice whose source could not be read → unknown / inaccessible; a slice nobody
read → unknown / insufficient; a gap → unknown / absent; an open domain → unknown /
insufficient; otherwise known false. Zero facts mean false only after every slice the
answer could live in has been observed, and a gap blocks that inference. For the truth a
world plants, a slice is observed exactly when its source is reachable, so no sealed key
moved when slices replaced reachability. For a run the two come apart: a source can
answer every call and the one record that would settle a question never be asked for,
and an unread record is not a negative. Read by reachability alone, a run that read
nothing would have every "not on leave" and every "lacks the skill" confirmed by its own
silence. One slice no read can observe whole: the corpus's documents, which have a
search and no enumeration. A negative may stand without it and says that it did, because
a negative that waited for it would be out of reach for every system and compare
nothing. Every answer carries what it rested on, the facts, the gaps and each slice it
asked about with what the view said, and citations and the accounting of reads are
judged against that. `ambiguous` and `conflicting` are the agent's to emit, never the
rule's, which keeps the rule's derivation and the agent's own uncertainty apart.

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
each hold a viable assessment; an uncovered action holds no viable one, unless a
constraint of the report could apply to the impact; a conflict
resolves to the system of record's observation under the rule it cites; every impact
has exactly one coverage action and every action an impact. Completeness is the
coverage check below: a conclusion of uncovered or unknown calls for everyone's
assessment and the gap names who was left out, so `uncovered` is never inferred from
a report that simply stopped assessing; no separate unconditional check runs.

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
→ known true; no positive evidence with a closed domain and every place the fact
could be recorded observed → known false; no positive evidence with an open domain,
or with one of those places unobserved → unknown. Observed is a statement about what
was read, not about what could be reached. The evidence for a skill has three places:
the employee's HR record, the comments of every ticket, and the corpus. A place that
could not be read gives `unknown / inaccessible`, one that nobody read gives `unknown
/ insufficient`, and a field the record leaves blank gives `unknown / absent`. So
with the record read and the tickets listed, a skills list without Kafka is
`non_viable / skill` and an explicitly empty list is the same; a missing skills field
is `unknown / absent`; a run that read the record and never listed the tickets has
`unknown / insufficient`, however reachable the tracker was; and one whose tracker is
unreachable has `unknown / inaccessible` even when the HR record shows nothing. The
corpus is the one stated exception, since it has a search and no enumeration: a
negative may stand without it and records that it did. The truth a world plants
observes whatever its reachable sources hold, which is the case the sealed keys are
derived in. That is
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
claimed where the world is complete. Grounding: the pure rules are run over
everything the run observed (records returned, reads completed or failed, the run's
condition) with the report's own claims as premises, and a claim is reproduced when
they conclude its payload, contradicted when they conclude another, and unsupported,
with a typed reason, when they cannot conclude from what was read; whether the
cited references resolve, were retrieved by that run and were used by the replay is
a separate count, so a broken citation and an unsupported inference are different
numbers. The plan: outcome match against the expected action derived per run
condition, completeness (every sealed impact exactly one action, no action without
an impact) and constraint satisfaction with truth-derived assessments; coherence,
the same constraint check over the report's own assessments plus the chain checks,
is reported beside it so an assignment with no reported assessment shows. The shape
of a grade, what is expected under an outage and where no answer exists were ruled
at the investigator milestone's third build step (the evaluator paragraphs under
"Keeping the benchmark out of the product"). The first
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
dated view admits only facts dated at or before the scenario's `now`: the "time is
world state" rule applied to truth. That view is construction's. The evaluator was
first ruled to grade from it as well; superseded at the investigator milestone's
third build step (2026-10-01), because a run observes every record the systems hold
at its run day whatever the planting date, so the evaluator's oracle is runtime
truth (the oracle paragraph under "Keeping the benchmark out of the product"). The
truth manifest thus has two layers, one
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

**Filler is a world-level pool, and a level is a count into it.** The measurement
world carries documents no scenario owns, answer-neutral by construction, as a
ranked tuple on the world spec beside a short list of levels, each a name and a
filler count with the base level at zero. A level's membership is derived, every
scenario-owned document plus the first so many of the pool, and listed nowhere, so
levels are nested and every answer-bearing document is in every level. The whole
pool is sealed and expected by the validator and the receipt check whatever level a
run uses; the level is a serving filter, applied before search, ranking and
full-context assembly. The spec is in the truth bucket, which the instance never
reads, so the world seals the served side's statement of membership beside its
documents, `levels.json`, the levels and the pool's ids in rank order and nothing a
document says, on both sealing paths; the validator compares it with what the
authenticated spec derives, since a verdict that never read it approved a pool the
spec did not seal (the step 9 external review), and the corpus cache filters every
read by it. The pool is minted after the whole assembly from the same
world-wide counter under a derived generator, so every planted id and record is what
the seed produces without filler, and that claim is a test: the semantic world
assembled with filler, its filler stripped, equals the world assembled without, and
over the composed stand-in world the planted entities, the facts, every key, each
clause's resolved target and the retrieval targets under every condition are equal
with filler on and off. Filler goes through the brief machinery and the same four
gates, with an empty required set and a *decoy* set: facts the text may state whose
subject is the target clause or a fictional entity the brief declares with an id
outside the world's id space, permitted by containment, authored nowhere, sealed
into no fact base, read by no rule. An unknown subject and any proposition about a
world entity stay refused, and the checker's unresolved value is read apart from a
malformed one and refused too, because "the employee taking leave is responsible for
this work" names nobody the scanner can match and refers to a planted person all the
same. The design had two compositions, handbook prose that names nothing and
near-miss documents whose clauses state requirements over fictional artifacts and
real skills. The checker reads a text that names nobody as a statement that nobody
is responsible on nearly every sample (five of twelve accepted on the best wording,
zero of ten on the last), neither a request line nor a system paragraph moved it,
and the handbook composition was dropped rather than re-pin the checker's prompt for
every world written under it. The pool is requirement documents alone, titled from a
name book of fictional releases and clients held apart from every planted table and
every title the templates can make, and the scope matcher moved from the evaluator
into `world`, so the index's scope properties and handle uniqueness run at assembly
over the corpus with filler in it and again at load, one matcher on both sides.
Titles stay unmarked in clause text; the span-loss rate is measured on development
worlds, and marking is reconsidered at the freeze only if that loss is large. A
token count is one tokenizer's, so the world seals document counts and the
registration records the padded level's request size, measured at the freeze under
the named counting rule.

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
the validator can reach decodes the record: the truth manifest's decoder is a
module the import law opens to three named readers and no other (the decoder
paragraph under "Keeping the benchmark out of the product"). It also seals the
stage's aggregate counters, because the log
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
"whatever verdict file exists": the manifest present under its final key and decoded
at `projected`, a verdict under the version's prefix approving, naming this version
and naming the SHA-256 of the manifest bytes just read, and judging under the current
validator version, since an older logic approved a shorter list of checks and a world
judged under one is validated again (the step 9 build; the rule at rank 2, below the
shells). A development world, sealed unprojected with no manifest, is admitted on a
local development root alone, and there on its levels object, the last write of the
unprojected sealing, so a sealing that stopped is never served as a partial world. A
newest-approved choice, if ever needed, is a listing of the prefix and not a mutable
pointer. Vendor names derive from the version, so no operator chooses them and two
worlds on one site cannot collide by choice.

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
fills from those objects (the investigator milestone's step 9): the deploy runs the
cache job after PostgreSQL is healthy, which discovers worlds by listing `worlds/`
under the instance role, admits each by the serving rule, reads the levels object and
every document the manifest receipts, and verifies what it read against the manifest
before loading: the set of document keys under the prefix exactly the receipts' set,
missing and foreign both named; each object read back under the version id the
manifest recorded, the levels object included; no object the manifest never recorded
shaping the world, since a final prefix is create-only and a key the manifest lacks
is what a later put adds. The manifest holds version ids and not content digests,
and on the local twin a version id is the content's digest, so the same comparison is
a byte check there. A version is loaded in one transaction, the world row first and
unready, the levels, the documents with their pool rank, the sections, the counts
read back, `ready` flipped by the last statement, under a transaction-scoped advisory
lock keyed by the version, since a row lock cannot cover a row that is not there yet
(two loaders on a fresh version collided on the primary key before it); a ready
version is left as it is, provided it was cached as the same kind of world under the
same manifest digest. Every read joins the world's row on `ready` and filters by the
level before anything is ranked, a document's pool rank null for a scenario-owned one
and below the level's count for a pool one, which is exactly a corpus of that
level's documents because PostgreSQL's ranking reads no statistic of the table.
Ingestion goes through a narrow loader that implements no write port, gated by the
import law to the adapters and the cache shell, and never through the gated
document writer, since it is cache materialization and not authorship; the
adapter is reader-only, the one class that held both ports having lost its reason
when the documents became objects.

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
`IntegrityRefused`, never a finding. The served levels object is in the chain since
step 9: bound to the manifest's version ids before any reader is built, then
compared with the levels the authenticated spec derives as a fourth block of the
verdict (format 2, validator version 2), equal passing, absent passing only for a
world that seals no pool, a difference named by position. The chain is complete for
the structured tier; prose-carried facts are proven through the containment gates
and the corpus's read fidelity. **The verdict is its own immutable artifact per
execution**, keyed
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
cannot be resolved away. **Rows are constructed in a seeded random order and the
windows are dealt by a seeded permutation**, because the plan concatenates its tiers
and both plan order and the scarcity order that replaced it seat classes by tier: on
twenty seeds the window's start predicted the tier on every one under the forward
dealing, and under the scarcity order the ids a model sees predicted it at 0.69 to
0.92 by kind; the permutation and the shuffle bring every kind within 0.05 of a
random order's own column, with no tier's ranges disjoint, except ticket comments,
which one class alone plants, so a comment's presence names the tier under any order
and its id adds nothing to that (`probes/generator-step/id_leak.py`). The shuffle is
drawn after the row seeds, so the order changes no draw, and the claim is "not a
function of the tier by construction"; the twenty seeds chose this remedy over an id
rewrite after construction and are not the evidence for the claim. The cost is
feasibility: scarcity measured per class had been the order's reason, after
thirty-nine of two hundred worlds exhausted a class seated last, and the random
order exhausts four of two hundred against the scarcity order's one
(`probes/generator-step/random_order_sweep.py`; FINDINGS, `reservation-book`, run
4), accepted on the criterion set before the sweep, near the scarcity order's rate
and far from plan order's. A refused seed is a loud refusal naming the row and the
rules, and the contract promises no world for every seed.

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
scoped to the one step that runs the entry point, and since the investigator
milestone's step 0 one credential per consumer for Frappe and Jira, so no secret ever
lives in two stores; for Calendar the validator shares the generator's secret (below).
The validator and the investigator each hold their own read principals (the read
principals' rulings, 2026-09-22 to 24): on Frappe a user on a read-only role over the
four doctypes a reader touches, with no desk access so the account stays a Website
User; on Jira an account whose API token carries the read scope alone and is honoured
only at Atlassian's gateway root, which a reader's configuration refuses to replace
with any other URL, while the Free-plan account itself keeps the project write
permissions the token cannot exercise. For those two vendors read-only rests on the
credential and not only on the read ports and the import law. Calendar is the recorded
exception: no read-only scope exists over app-created calendars, and the one that
exists is sensitive because it reaches the owner's personal calendar, so both readers
hold the generator's grant, bounded to the calendars the app made and unable to
enumerate or read the account's others, and read-only there rests on the code. The
consequence is stated rather than softened: the instance's Calendar credential can
create, change and delete events on the synthetic calendars; re-validation against the
sealed manifest detects such drift afterwards, prevents none of it, and recovery is a
regeneration. A claim of read-only vendor credentials everywhere is therefore not
available to the report until the dedicated reader account below lands. Each
principal was accepted by a live probe (`probes/FINDINGS.md`, the read-principals
entries): reads equal to the writer's field by field, the permission set read back, a
known-valid write refused, and for Calendar the reach bound measured. If per-role
principals everywhere is ever wanted, Calendar's path is a dedicated reader Google
account holding nothing else, the world calendars shared to it as reader through the
calendar ACL. The validate workflow also probes its role's boundary before the entry
point runs: the world spec, the world prefix and the world manifest allowed, the truth
manifest, the truth listing and two disposable puts refused with AccessDenied. The
evaluator's role was settled at that entry with its execution boundary; a guessed
trust frozen earlier would have been a hole in the sealing claim.

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
is generated from it, and a tool makes no domain decision. The specifications are
declarative data in `core` (the second build step, 2026-10-01): one method table is
the authority for a method's family, source, record kind and cardinality, the
thirteen are declared in one explicit canonical order, validation is one generic
function (an exact JSON object with every argument required, no coercion and no
default, ids and spellings through the one rules, spans bounded by elapsed time),
the serialization is the entity codec's observed record for all thirteen, and the
logging hook and the port binding are the harness's alone. The tool-surface digest
hashes a versioned envelope of what a role's model sees, the ordered generated
definitions with the identifiers and versions of the result codec and the validation
protocol, because a change in how a result is rendered or a call refused is a change
the model sees as much as a changed description; it names the semantic surface, not
provider wire bytes, and its two protocol identifiers are declared policy bumped by
hand under review, the same convention as the export's format version. The registry declares per
role which methods become tools, so a tool list is constructed and never prompted,
and least privilege is the registry and a role-scoped read-only vendor principal
together: the registry is a harness-level claim, the principal is what makes it
provable against the vendor (on Frappe and Jira; for Calendar the principal bounds
reach, not verbs, and the registry carries the read-only claim alone, the hosting
section's recorded exception). No tool takes a date: the wrapper stamps every
observation with the run's `now`, the rules read the stamp, the model supplies none,
and what a read returns is not filtered by date (time is applied above the port), so
a wrong-time call cannot be expressed and a span argument is scope the model
chooses, logged and not graded.

As built at the registry step (M2 step 10, 2026-10-09). One role is declared, the
investigator, and its list is the ten without the three whole-table enumerations,
which the frozen prefetch reads for every run and the turns render before the first
call, so a model call to one would re-read a table with nothing to discover; the list
is a positive declaration in `core` that names that reason, and a prefetch change that
drops an enumeration reopens it. The list authorizes execution: the tools node builds
its executor over the role's surface and the prefetch over the harness's own, so a
known tool the role is not shown is refused at execution, recorded and durable, never
resolved through the global table. The stamp is a structured envelope in the
model-facing result, derived from the admitted `RunContext.now`: one envelope per
operation, holding the record, the records, the absence or the unreachable source under
one key each, the observed record and its codec unchanged; a skip the tools node
appended for a source already unreachable renders as that source unreachable, the
graph's durable decision being the one answer to a model's call against a stopped
source. A refused call is answered with one correction from a closed set built from the
declarations and the argument's name, never from the value the model gave, since a
model's argument is text the model chose and the validator's detail echoes it; the
detail stays in the log and the export, and the rendering derives the correction by
running the validation again on the logged arguments, so first execution and recovery
take one path. The adapter's reason for an unreachable source and a tool name the role
does not declare are never rendered either. The request capture renders the whole
surface this step produces over a sealed world, the definitions as the client sends
them, every result of a full read under the normal condition and under an outage, and
every correction, and asserts the scenario id and the world version appear in none;
the prompts join it at the graph step. The surface digest's envelope carries the
harness's own tool definitions beside the read tools (surface version 2, result codec
`observed-envelope` 1, validation protocol 2); the fact tool's definition is the graph
step's, so the investigator's digest is pinned provisional and moves once when it
lands. The served version and the level are the admitted frozen inputs and nothing
else; the corpus reader is built from them with the adapter's serving check run before
any read, so an unserved version or level fails the attempt first.

MCP was the alternative transport (ruled
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
realized the declared world and never reads truth. Beside the rules, `core` holds what
both parties must compose the same way (the fifth build step): the reading pass that
asks grounding and viability of each impact, the composing pass that gives each impact
its need, its requirements, the count they ask for and the plan rule's outcome, the
condition a run's reads show, the coverage the reads give, the structured projection of
a trace's reads (each record as first returned, the usable ones derived and dated to the
run's day, a record no fact can be made from withdrawn and named), the record a witness
can be cited by, and the frozen prefetch as data with its planner. A composition written
again in either party would be a second reading of the rules, free to drift; the
evaluator's view is the projection plus its sealed overlay, so what a system that reads
no prose concludes from is the structured part of what the grader replays over, by
construction.

The event log step (2026-10-05 to 07) added to `core` the rules the harness runs and
the evaluator audits, with their input types: the counting-rule registry, the run's
account, the within-call decision, the eligibility function, the bound's interface and
the inventory's type and codec. The agent projects events into those inputs and the
evaluator projects exports into the same ones; a first cut put the account in `core`
and the events in `agent`, which left the function nothing to take. The log itself,
its events, keys, transition, ending, status and reader, and the ledger stay in the
agent's package as pure modules beside one PostgreSQL module, since they are the
agent's own execution control, ownership and accounting, which the evaluator must
never read; the import law keeps it from importing the store, and the database's
credentials and the deployment keep it from connecting.

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
Reachability is not completeness: the run condition records the first, and the
second is coverage, what the run's completed reads observed, derived from the trace
by one function that the evaluator and a harness concluding from its own reads both
call. "What Alice owns" is then a filter over facts derived from every work
item, retrieval efficiency spent for evidence semantics, negligible at this world
size, pagination staying the adapter's. **`RunContext` carries the leave under
investigation as an id and nothing more**: run inputs identify what to investigate,
ports establish the facts, so the leave record is read as evidence a scenario can
contradict, and a run that cannot read it continues degraded rather than inventing
the span, everything downstream unknown and not only `on_leave`; such a run has no
claim-level expected answer and is limited instead of graded (the outage paragraph
below). **A port reports three outcomes three ways**, because
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
candidate the key did not author; it admits truth only from the sealed objects,
recording world version, truth digest and version id before grading (the entry also
had it filter truth by the scenario's `now`, superseded at the third build step,
the oracle paragraph below); it shares the pure rules with the investigator through
`core` while neither imports the other; and its decoder honours absent against empty
on the key's derived-conclusion fields. Its execution boundary, its identity, its
metrics beyond the grading and the baselines it grades beside the agent were ruled
at that entry, 2026-09-20, as follows.

**The evaluator runs as a dispatched workflow under its own identity, grades what the
recorded run observed, and never re-reads a vendor.** Its role is trusted only to a
GitHub environment that holds no secrets, so a vendor credential cannot reach the
job even if a reference is added later, and the boundary is IAM rather than a
workflow review; it reads the truth manifest, the sealed spec and run exports (and,
since the third build step's join, the scenario specs: that one object name per
world, granted 2026-10-01 with no list and nothing else under the served worlds, so
a rename of the file is a change to the role first), writes
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
digests, the tool-surface digest, the preregistration commit, observed usage and
cost, any failure category); the evaluation artifact adds the export's key and
version id beside the truth digest and version id.

Its shape was ruled at the investigator milestone's second build step (2026-10-01),
again at the contract step (2026-10-04), which made it format 2, and again at the
event log step (2026-10-05), which made it format 3; it lives in `core` as plain data
with one codec, since the agent writes it and the evaluator reads it and neither may
import the other. One immutable artifact per run attempt, self-identifying by run id
and attempt beside a format version, projected from the event log once the attempt is
closed and written once by conditional create; a run paused at an approval or
recoverable after a process death is a state of the log and has no export. Its digest
is of its canonical bytes, computed by whoever cites it and never stored inside, and a
reader accepts bytes only when their re-encoding reproduces them, so one export has
one byte sequence. Formats 1 and 2 are not read: no export of record was written in
either, and their bytes refuse by version.

Format 3 holds what the event log produces and format 2 could not state. An attempt
admitted and never claimed exports with zero segments: failed by infrastructure at the
abandoned site, no operation, call or approval, zero active time, elapsed from
admission to abandonment, timing complete and an empty trace, with no segment invented
for the admitter or the abandoning operator. An abandonment names its authority, the
generation it fenced and one of two reasons, cancelled or interrupted, and is stated
whenever the command closed the attempt, beside a recorded defect too, since the
command then finalized a defect and abandoned nothing. The trace holds the position at
which the run entered finalization, absent when it never did, so an audit can show the
loop left the reserve; the reservation holds the amount the ledger charged. Every
dispatch carries the input bound it was authorized on and the role's output maximum,
and the counting operations are a list of their own, failed ones included, each with
the request digest it covers, the identifier asked, the answer or the error as it
arrived and the worker's reading of it, so a denial misread as transient leaves a
trace of the misreading. Two harness sites joined the closed list: `input_bound`,
naming the last counting operation when the counts were exhausted, and `unhandled`, a
fault of the harness itself. The timing admits a terminal instant before the
admission, both raw timestamps and their signed difference kept, and the fenced
generation is compared with the segment count by the evaluator and not refused by the
constructor, since a store's mis-stamped generation would otherwise turn into an
attempt closed without export.

Three blocks. The context is what changes the evidence. The record is provenance: the
observed condition as a claim the replay re-derives and verifies, the sources
scheduled unreachable with the schedule's digest, the assigned corpus level, the
preregistration commit, the digest of the attribution table, the model configuration,
pricing selection, prompt digests and tool surface of every role as one role set, the
system kind (four since full context joined) and variant, the retrieval
implementation, the prefetch rule's identity, the cap with its finalization reserves
inside the totals, a terminal status with a failure whose site is an operation, a
model dispatch with its phase or a harness site from a closed list, an abandonment
where an attempt was ended by decision, the segments the attempt ran in with each
one's harness commit and tree state, the reservation and what became of it, the
approval as it stood at termination, the usage aggregate with per-counter reporting
coverage over dispatches, the cumulative cost, and the embedded pricing rows that
priced it. The trace is what the run did: the model calls; the attempted reads, each
with its origin (the prefetch, the harness under a registered policy, or a model
call), its resolved source, its arguments exactly as accepted with no coercion or
default, one of six outcomes (a record, none, a possibly empty sequence, unreachable,
a malformed record, or a call refused before any source was asked) and its position in
the attempt's event order; the final claims in claim-id order; and how they were
composed, by the rules or by a model, under which policy, with what each admitted
requirement's span bound to and which admitted statements the view left out.

A model call holds its dispatches, and a dispatch permits at most one send: the SDK
retries nothing, the graph retries nothing, and a retry is a new dispatch the harness
makes under a registered bound, so every possible send has its own entry. A dispatch
keeps what arrived (a complete response, a broken stream, a service error, a client
error, a refusal before sending, or nothing recorded) and, separately, how the
measurement attributes it by a registered rule: behaviour, infrastructure, defect or
unresolved. Keeping the two apart lets a rule change before the freeze without
rewriting what was observed: a service error the measurement reads as the model's
behaviour is still recorded as a service error. A call's state is derived from its
last dispatch and stored nowhere. An intent with no outcome is an unresolved send
whose usage is unknown, so a call can be answered by a later dispatch while the run's
cost stays a floor and the earlier allocation of its reservation is kept, and a
reservation recorded as reconciled over such a history does not construct. The
allocation is two numbers, pico-dollars and the worst-case tokens counted against the
run's cap, because money does not determine a token count when the rates differ by
class and the cap is in tokens. An error keeps the SDK's retry count and the provider's
request id where its response carried them, as a complete response does: several sends
beneath one dispatch show there or nowhere. A dispatch
also holds the reads its request rendered, since who asked for a read does not say
what a model was shown, and the positions of its intent and its outcome, which with
the operations' positions give one event order, neither clock ordering events. What an
answer carried is held apart from how the call ended: whether text was present, every
tool call with one disposition (a read, handled by the harness as a fact batch,
unparsed, undispatched with a reason, or unresolved), and the fact batches, each
parsed into refused inputs and admitted or refused facts, or malformed. The raw
payload of a malformed batch and the raw arguments of an unparsed call are kept with
the identity of the parser and schema that refused them, the one exception to an
export holding no model prose, so the classification can be checked from the export
alone.

Usage is the raw object the response carried, kept verbatim, and the four counters are
read from it by one function the harness and the evaluator both run, each present only
when reported: the chat client maps an omitted counter to zero, and whether a cache
counter is omitted follows the model family and the streaming mode, not the caching
state. A field the reading has no declaration for, a duplicate that disagrees with its
twin, a total that is not the sum, or a cache write at a lifetime the one cache-write
rate does not price makes the usage unfit to price completely; it raises nothing and
removes nothing. Absent is a different statement from empty throughout: an aggregate
row exists only for counters some dispatch reported, and a cost is incomplete when a
rate row under its selection was neither reported nor recorded in the price table as
meaning nothing billed when absent, that policy being table data a probe earns per
configuration rather than an assumption in code. An error is not free because it
returned no usage: a send with no usage has a cost only under a named zero-cost rule.
Rates and costs are integer pico-dollars per token, exact from a committed table of
integer rates and verified by the evaluator against the embedded rows, the basis never
benchmark truth. Nano-dollars, format 1's unit, cannot state rates already paid (Nova
Pro's published cache-read rate for Frankfurt is 262.5 nano-dollars a token); a test
holds the published rows and shows each is an integer in the new unit.

Time is stored as inputs and the two durations are functions over them, so no stored
duration can disagree with the segments it was summed from. Evidenced active time is
each segment's last durable offset less the approval wait that fell on that segment's
clock, and elapsed time is the wall clock from admission to the terminal event. A
segment whose end was never recorded was killed with an unknown tail, and the timing
is then incomplete, a lower bound. The approval follows the terminal status and not
the claims: a completed or cap-exhausted attempt holds an approval of its frozen
review payload (the claims, the composing policy and its author, the requirements
whose span did not bind, the statements the view left out), an abstention's empty
payload included. The tie runs one way: a failed attempt states the approval as it
stood, usually none and a given one when it failed after it (a terminal append that
failed, an abandonment after a delivered approval), because an export made to deny an
approval the log holds would have to drop the worker's resume and report the whole wait
as waiting. The exporter projects the approval
and does not make it: the rules-only run path applies the automatic policy before the
export is built. A setting is any JSON value in one spelling, an integer-valued float
normalized to the integer and a boolean never equal to a number, in a type of its own;
the generator's provenance type keeps a float as written, because a sealed record
holds `0.0` and has to decode to the bytes it was sealed with. Within a format, the
structural fields are required and an incompatible change bumps the version, while the
extensible blocks follow a declared append-only order so an entry appended later reads
as absent from an older export.

The validator re-reads the live systems and
the evaluator does not: that is the difference between them. The evaluator on the
instance under a second principal was rejected on the executor paragraph's own
sentence, two principals on one host being two configurations and not a boundary;
workstation runs were rejected because evaluation repeats and needs run-and-attempt
provenance.

**The truth manifest is decoded whole by one gated module, and absent stays apart
from empty.** The manifest's value is a set of types that are exactly the file's
content: its scenario rows with their keys, authored facts and briefs, and the
materialization record. One encoder writes it through a pure projection of the
assembled world, and one decoder reads it, taking bytes and accepting them only when
their re-encoding reproduces them. The encoder stays ungated, since it needs an
assembled world as input and gives a reader nothing. The decoder is its own module
in `world`, and the import law names its importers by full path: the generator's
resume, the evaluator's world loading, and the audit-sheet script, an operator's
program, which is why this one gate also scans the operator's programs under
`scripts` and `probes`. A named reader that no longer imports the decoder fails the
law too, so the list stays the statement of who reads the key. An earlier placement
kept the decoder outside `world`, because the law could not then keep a `world`
module from the validator; module-path gates arrived with the object store's write
side and removed the reason. A key's two derived sets, the expected conflicts and
the expected unknowns, are each present or unavailable on their own: an omitted
field decodes as unavailable, an empty list as known empty, and `null` is refused.
Only bytes sealed before the fields existed decode as unavailable (the measurement
world's manifest, confirmed against its live bytes), and the evaluator's join
refuses such a key, so unavailable never reaches a metric.

**The evaluator loads a world by proving it, and refuses the whole world on any
incompatibility.** Loading reads the world spec, the scenario specs and the truth
manifest by key through the object-store reader and records the version ids
returned. It verifies the two digests the world spec cites against the files' bytes,
recomputes the world version from the three byte streams and compares it with the
one requested, requires the plan, the plantings, the scenario specs and the truth
rows to list the same scenarios in the same order, checks that what a plan row and
its truth key both state agrees, and attaches each planting's stable interval to its
key. It then runs world assembly's whole-world re-verification on the joined
scenarios, the function that let the world be sealed, so every sealed key is
reproduced by the rules as they stand today, under both views, on every day of its
stable interval. The golden world was sealed by the rules of generator version 14
and the evaluator derives everything beyond the key with today's; that reproduction
is what licenses it, and it held on all thirty keys at the first live load. A
failure is a defect of the evaluator or of the sealed files, never of a run, and it
refuses the world whole, because a rule that drifted on one scenario cannot be
trusted for the others. No version id is compared at loading: production holds no
inventory of them and the manifest that records them is outside the evaluator role's
reach, while content identity (every key embeds the world version, and the
recomputed hash must equal it) is the stronger check. A refusal's message names
files, scenarios and counts and nothing else, and it is raised with no chained
cause, since the evaluation job's log is public and a decoder's own reason names ids
and values. Suppressing the chain at the raise was not enough, because that hides
the context from the default formatter and leaves the reason on the exception; the
refusal is raised after the handler has ended and keeps the reason as an attribute
no traceback prints.

**The evaluator's oracle is runtime truth: what a run can obtain at its run day.** A
world has two views. The dated view admits a fact from the day its provenance became
observable; the runtime view holds every record the systems hold, dated to the run
day, which is what the harness gives a run. World assembly proves the sealed key
under both, for the normal condition only. What the evaluator derives itself, a
candidate outside the probe set and every expectation under an outage, is not proven
equal, and measured on forty seeds of the golden plan it is not: under the normal
condition none of 2,880 must-assess pairs and none of 1,280 outcomes differ, while
36 of 32,960 other candidate pairs do, 20 of them non-viable for skill by date and
viable at run time, each because a later scenario plants evidence of the skill;
under a tracker outage two must-assess pairs differ the same way. Under the dated
view a report that read the later comment correctly would be graded wrong. So the
oracle is the runtime view, rebuilt from the sealed plantings and the manifest's
authored facts by the call assembly makes, and planting dates do not gate it. Three
views are kept apart by name: runtime truth is the oracle; the observed-run view,
built from what the export's completed reads returned, is what the grounding replay
reads, and truth enters it only through a carrier the run read; the dated view
remains a construction and history diagnostic. Under the normal condition the
oracle's answer must equal
the sealed key, and a difference is raised as an evaluator defect, so the code that
feeds the grader is checked on every call and not only the rules beneath it. How far
the two views disagree is a property of a world and a condition, computed by a pure
function over the complete answer and recorded in FINDINGS (`runtime-truth`): on the
golden world no part of the answer differs under the normal condition or under a
tracker or a calendar outage, so no reported result rests on the choice, and the
ruling stands for the worlds where it does.

**Under an outage the expected answer is derived for the condition, and two
conditions have none.** The registered injection fails a source for the whole run,
so the condition a run ran under is a set of unreachable sources and the oracle is
runtime truth restricted to it. The reading pass construction uses derives the
answer. The expected impacts are those the rules ground under the condition: an
impact whose artifact only the failed source connects to the leaver is not expected.
The probe set of a grounded impact stays the sealed one, its verdicts re-derived,
and a constraint is expected when its clause is readable and what it applies to is
in the scope of a grounded impact. On the forty seeds every verdict or outcome an
outage moves goes to unknown or keeps non-viable with fewer reasons; a failed source
outside a key's required sources moved nothing in 1,400 of 1,400 cases, and one
inside them moved something in 3,400 of 3,400. Two conditions leave no claim-level
answer, and the oracle says so as a state instead of returning an empty expected
set, which a silent report would match perfectly. *The unreadable leave:* the rules
take the leave's span as a premise, so when the leave's record cannot be read
nothing can be concluded. *The unreadable policy:* when the source that holds what
clauses require is unreachable, no run can establish which clause governs an impact
or whether any does; the oracle knows only because the sealed constraints are its
input. Its own answer there cannot be stated as a coherent report, since it expects
every candidate unknown on a clause's requirement and expects no constraint claim,
while the chain admits an unknown about a clause only when the report cites it. A
system that always assigns would be right on the ungoverned impacts and one that
always says unknown on the governed ones, so the state holds for every scenario
under that condition, governed or not. Both states are stated by what must be
readable (the leave's record, the evidence domain of a clause's requirement) and
never by a source's name, and the leave is asked first. The outages that can be
graded are therefore the tracker's and the calendar's; with Frappe or the corpus
down a run is limited, and how a system says it could not know is settled with the
rules-only baseline. Redesigning the oracle so that a producible report exists was
rejected: it needs "whether a policy applies is unknown", and the frozen vocabulary
has no predicate for it. Grading the condition anyway was rejected as a number no
system could score on. A run in which one source both answered and failed, possible
only from an unscheduled vendor fault, ran under a mixed condition and is limited
too, labeled and counted apart.

**A grade is one row per expected or reported claim, four things kept apart, and no
count is stored.** Matching runs on a structurally valid claim set, over the union
of the keys the oracle requires and the keys the report holds. A row states the
*expectation* (required; optional, meaning derivable and true outside the probe set;
unexpected), the *presence* (reported, or missed, which only a required key can be),
the *standing* of a claim the oracle does not expect, and the *payload* flags of a
claim it can judge, optional ones included. Standing is one named bucket per type. A
reported impact is a planted distractor with its reason, unsupported under the
condition, or another false positive. A constraint outside the expected set is a
false positive. An assessment or an action on an unexpected impact is tallied and
not judged, as is an assessment of someone outside the organization. A conflict is
real in the oracle and outside the expected set, a relevance error, or unsupported
by the oracle's facts. An unknown is a gap claimed where the oracle resolves the
fact, or a true gap that no assessment needed. An impact whose grounding is
unresolved under the condition is *unsupported*: no true positive and no factual
false positive, counted against precision and reported apart, because an impact
claim is a positive assertion, the vocabulary has no "possible impact", and
neutrality would make guessing free. A reported impact that shares its artifact with
an expected one carries that relation, which earns nothing and explains the
assessments and actions that land behind it. Recall's universes are the expected
sets for impacts, constraints and conflicts, the probe set for assessments, and for
unknowns those behind a probed candidate's assessment. Under the normal condition
four in five of the unknowns the rules derive concern colleagues outside the probe
set (blank skill records), and under a tracker outage the derived set grows to about
twelve a scenario, so a universe of every derivable unknown would grade verbosity.
Correct optional claims count toward precision and never toward recall. An action's
flag is whether its kind matches the expected outcome, and no assignee set is
compared. Rows are typed per claim type so an impossible combination cannot be
built, and they hold no counts: tables are aggregated from them, and a table can
be recut without regrading.

**The plan is asked three questions, and each omission has one record.** *Validity,
against the oracle:* for every action on an expected impact the plan rule is fed the
oracle's requirements and verdicts, so an assign is valid only when each assignee is
in the organization and viable in the oracle and the viable assignees meet each
applicable clause's count. *Coherence, within the report:* the chain checks, and the
same plan rule fed the report's own assessments and the clauses the report itself
cites, a clause's content read from the fact base since a report states which clause
applies and never transcribes it. A report that missed a constraint fails validity
and stays coherent; one that contradicts a clause it cited fails coherence. A cited
clause whose content cannot be read makes the check uncheckable for that action,
whatever its kind, and is recorded as such, never read as imposing nothing.
*Coverage:* a conclusion of uncovered or unknown is about everyone, so it calls for
an assessment of every organization member. The oracle's expected outcome calls for
it whatever action the report made, which fixes the denominator by truth and makes
it the same for every system graded; the report's own conclusion calls for it too,
the completeness rule of the vocabulary extended from uncovered to unknown. One gap
per impact names the colleagues left unassessed and which of the two called for
them. An omission is recorded once: a probed candidate of an expected impact left
out is a recall miss on its row and stays out of the gap, anyone else is in the gap,
an assignee with no reported assessment is a coherence finding, and an unknown
assessment with nothing behind it is a chain finding. Where no row exists (an impact
the oracle does not expect under the condition, or a limited run) the gap covers the
probe set too, being the only record the omission has. Plan violations stay typed
records keyed by impact beside the rows; a flag on the action row would be a second
copy of them.

**Every export that decodes gets exactly one outcome, and nothing a run did
raises.** *Graded:* the run completed or reported at its cap, and the oracle has an
answer for its condition; a report with no claims is graded through its misses.
*Limited:* no claim-level answer exists (the unreadable leave, the unreadable
policy, a mixed condition), so no comparative answer metric is computed, and every
check that needs no expected answer still runs: the structural check, the report's
coherence and coverage, and the grounding replay with its citations.
*Excluded:* the run failed, by defect or by infrastructure, or its context is not
the one the sealed scenario gives, a harness defect; it is counted with a typed
reason. The order is fixed, context, terminal status, condition, oracle, so a failed
run of another context is a context mismatch and no outcome rests on a trace that
describes another run. A structurally invalid claim set is system behaviour and
stays in the denominator with zero credit: every required key is a missed row, every
reported claim is kept and not matched, and the plan checks are recorded as not
evaluated, a different statement from having found nothing, which the outcome types
enforce. Dropping the offending claims and grading the rest was rejected, since it
needs a rule for which duplicate wins and invites gaming. The condition is read off
the trace's unreachable outcomes alone (a malformed record is a defect, and a
refused call never reached a source); a source with both a completed read and an
unreachable one is mixed in either order; and when the record's stored condition
disagrees, the trace stands and the disagreement is a harness finding on the
outcome. A condition nobody registered, two sources down for the whole run, is
graded mechanically, and whether it enters a reported comparison is the
preregistration's.

**The observed-run view holds what a run's completed reads returned, and truth enters it
only through a carrier the run read.** `core` derives facts from structured records and
nothing from prose, and five kinds of fact exist only in prose: what a clause requires,
whom a section names, a stale owner in a runbook, a skill shown in a comment or stated
in a section. On twenty seeds of the golden plan every one of 620 authored facts is
carried by a comment or a clause (FINDINGS, `grounding-basis`), so a view built from
records alone would leave every claim that rests on prose ungrounded for every system.
The view is `core`'s structured projection of the export's completed reads, with the
sealed overlay this view adds. Structured facts derive from each usable record exactly as
returned, dated to the run's day. A sealed authored fact is
admitted when a completed read returned its carrier and the returned comment or section
equals the sealed one: the evaluator holds the sealed text, and can say what a piece of
prose states only when it is that text. A claim's evidence references admit nothing;
they are assertions the citation check judges. The limit is stated: once a carrier came
back, grounding cannot tell reading from guessing. Whether a query returned the carrier
is retrieval's question and whether the claim is right the grading's. Every returned
record is also compared with the sealed one of its id, and a difference is an *integrity
finding* on the outcome: a record or a part that differs, one the world does not hold, a
sealed one that a completed enumeration should have returned, a read by id answered with
another record. It is never an exception and never a licence to substitute sealed
content. A drifted structured record still derives its facts as returned, since
grounding asks what the run's own reads support; a part that differs admits no authored
fact and counts as unobserved; two differing returns of one record in one run leave
nothing to conclude from it. Whether a run carrying a finding enters a reported table is
the preregistration's. A requirement's scope is the one thing admitted that is not a
fact. The fact base holds what a clause requires and nothing about what it applies to,
so the sealed pairing is admitted through the clause, and loading refuses a world unless
every requirement clause's own text names exactly its target. Titles nest by design, a
qualified title containing the plain one, so the longest title found decides.

**The grounding replay gives each claim one of three standings, on premises taken from
the run.** *Reproduced*: the rules conclude the claim's payload from what the run read.
*Contradicted*: they conclude a different one. *Unsupported*: they cannot conclude, with
a typed reason (the leave not read, a clause not read, the candidates never enumerated).
A claim can be right and unsupported, or wrong and reproduced; the replay asks only
whether a report asserts beyond its evidence. Nothing reaches it from sealed truth
except through the view. The leaver and the span are read off the run's own read of the
leave record; an assessment is replayed with the report's own constraint claims, an
action with the report's own assessments, and a conclusion about everyone with the
candidates the run itself enumerated. A standing is local: it takes the claims a replay
consumed as given, and each record names those premises. So a wrong constraint under
twelve assessments is one failure stored, and tables report the local failures, which
are the roots, apart from the claims *grounded end to end*, of which that constraint
costs thirteen. A third reading, *strictly grounded*, also refuses an answer that stood
without the corpus closed. One judgment is stored and the strict one is derived from
what each answer carries. Storing both was rejected as a second copy that can disagree;
strict alone would make 29 % of verdicts ungroundable for every system, a constant that
compares nothing; lenient alone would hide a limit of the tool surface in a definition.
The word grounded is never used alone for a result with a source left unclosed. An
unknown claim names a subject and a fact and no window, so it is replayed against the
questions the replay of the report's own claims stopped on. With none, the rules are
asked directly when the fact is single-valued, and a multi-valued one is unsupported,
nothing fixing what it claims. On an empty trace, then, an "unknown, insufficient" about
a single-valued fact is reproduced: the replay measures assertion beyond evidence, and
recall is what charges a report for not looking. A reason only an agent can give,
ambiguous or conflicting, is contradicted when the rules establish the fact from the
run's reads and is unsupported, as not replayable, only when they too leave it open. The
adversarial tier plants a stale owner that the tracker's record resolves by authority,
and a report that stops at "conflicting" there is refuted by what it read; filing it as
not replayable would say less than the replay knows. An assignment has no witness of its
own and rests on its premises. A conclusion about everyone has one, the enumeration that
says who everyone is. A truthful report over a full read is reproduced whole, 1,001
claims on a thirty-scenario world with 547 of them strictly grounded, and the same
report over no reads is unsupported throughout.

**A citation is judged on three independent axes, and citing nothing is neither perfect
nor zero.** *Resolves*: the sealed world holds the cited record, comment or section.
*Retrieved*: a completed read of this run returned it, a comment or a section inside its
ticket or document. *Used*: it is a witness of the proof the claim was reproduced by, or
of a reproduced premise's; this is evaluated only for a retrieved citation of a
reproduced claim, so "retrieved and unused" stays apart from "use not evaluated". The
axes are not nested. A record the world does not hold still derives facts when a read
returns it, so a citation can fail to resolve and be retrieved and used; one ordered
status was rejected for assuming otherwise. Nothing is labelled fabricated, since a
returned foreign record points at contamination or a harness defect and not at
invention. A negative settled only by an enumeration or a window has no record to cite.
Presence is its own number, the share of claims that cite anything, beside the quality
of the citations made. Fields are recorded and not judged: an event's schedule comes
from its start and its end together, and a field metric needs that relation, which this
milestone does not define.

**What a run did is measured beside its outcome, for every export that decodes.** A
failed attempt still made calls and cost money, so the metrics are one record beside the
outcome, and each part is evaluated where its inputs exist; a part that was not
evaluated says so and is never a zero. *Source discipline* is read off the trace alone:
every read by source, by how it ended and by who asked, the frozen prefetch or the
model, with a refused call counting for no source; the model's refused tool requests,
apart from model calls that ended as a refusal; repeated reads; and the operations no
conforming harness records (a tool that is not one of the thirteen, or a source,
cardinality, record kind or arguments that are not the tool's), which coverage refuses
to credit and this reports. Required-source attempt and success are joined from the key.
*Extra reads* are defined by what a proof rests on: whatever an answer's witnesses name
is attributed to the earliest completed read that supplied it (a record, an absence, an
enumeration, the part of a window no earlier read had covered), and every other
completed read is extra, a later identical one included. Extra is a cost that fed no
conclusion about the report. It is not a mistake, since the key seals no right query per
call and a reasonable read can hold nothing, and it is no judgment of attention.
*Retrieval* is measured against targets that are derived and never read off the sealed
role tags, which exist for model-written text only. A statement of prose is a target of
a scenario under a condition when the oracle's answer there changes with the statement
removed on every carrier, a requirement removed together with its scope. The unit is the
statement, its carriers alternatives. Each target keeps the claim keys it moves and
whether the oracle requires each, because a skill another scenario plants for a
colleague moves only rows no report must hold. A completed search is a row with the rank
of each target it returned, and each target says whether it was retrieved and whether
the report concluded what it moves, which tells a target retrieved without the correct
conclusion from one never retrieved. Nothing says a system ignored what it retrieved: a
trace cannot tell inattention from misunderstanding. *Usage and cost* are verified and
not copied: the usage aggregate recomputed from the trace's model calls, each call's
cost from its pricing selection and the embedded rates, and the cumulative cost from the
recomputed per-call costs, so a harness wrong the same way twice does not agree with
itself. A mismatch is a harness finding and a missing rate a pricing finding; neither
raises. The arithmetic is checked against the rates the record embeds, and that those
are the committed table's is a digest check owed when the table is an asset. The run
condition is derived from the reads that actually failed, the assigned schedule recorded
beside it; a system that never called the failed source ran under no outage.

**Tables are cut by cell, and each kind of number has its own interval.** In the tables
an arm is one system under one assigned condition at one assigned corpus level, what the
registration calls a cell, and a table's cell is an arm at one stratum: the whole set, a
tier, or a scenario class. Nothing is pooled across systems, conditions or levels. The
arm is what a run was *assigned*, so a system's own behaviour never chooses its arm,
while each run is still graded against the condition its trace shows. The arms the
preregistration
registers define what was intended, so one that produced no export is reported with
every intended run missing. An arm that arrives without being registered is kept and
marked unregistered, never dropped, and whether it enters a reported table is the
reporting policy's. Outage runs follow one injection schedule registered before any
run and are reported apart from normal runs. Two kinds of number come out. A
*scenario-level proportion*, x of n scenarios passing a yes-or-no check, carries a
Wilson interval, the scenario being the trial. A *claim-level ratio* (precision, recall,
a grounded share, a citation share, target coverage) is the sum of numerators over the
sum of denominators across scenarios, with a percentile bootstrap that resamples whole
scenarios within their tiers: the claims of one scenario share its people and its
documents, and counting each as an independent trial would make the interval far too
narrow. Intervals are given for the whole and for each tier. A class, one to four
scenarios, shows its raw counts, which localize a failure and do not estimate a rate. An
observed zero denominator is 0/0, not estimable, and a resample with a zero denominator
is left out and counted, never read as zero. Under repeats the scenario stays the unit:
a ratio pools a scenario's runs before any ratio is taken, a check takes the scenario's
pass fraction, and the repeats of two systems are never paired slot to slot. A
comparison is paired on scenario and assigned condition, each resample drawing the same
scenarios for both sides: two systems at one level, or one system at two levels, the
answers being the same at every level, and never two conditions, whose expected answers
differ. A check is read two ways. Conditional quality is over the
runs the check applies to. End-to-end success is over every run a scenario was meant to
have: a limited or an excluded run does not pass, and is counted apart from a run that
was checked and failed, so a provider fault is never scored as a wrong answer and never
improves a score by leaving. Precision has two readings shown together: strict counts
every reported claim, and type-local leaves out an assessment or an action hung on an
unexpected impact, which is charged once, at the impact. A conflict's observations are a
measure of their own beside its payload, since the payload is the value that stands and
the rule that chose it. Cost and duration carry no interval: the total over every
attempt, the median and range per run, and the count of runs whose cost is a floor.
Every reported table shows the runs intended, made and missing and how each ended,
graded, limited or excluded by reason, so an exclusion is a visible smaller denominator
and never a better score. What the preregistration fixes (the arms, the named checks,
the confidence level and the seed, the repeats and how a missing one counts, which
attempt of a retried run counts) is an argument to the aggregation and is chosen nowhere
in the code. Two limits go with every table. The scenarios belong to one organization
and share its people, so resampling them says nothing about another organization. And
ten scenarios per tier is very few clusters, where a percentile interval's coverage can
be poor and visibly discrete; no correction is applied.

**Three baseline systems are preregistered beside the agent and graded by the same
evaluator from the same export shape.** Rules-only: the frozen structured prefetch,
the structured projection of what it read as its whole view, the shared rules over it
with no constraint, and one reporting policy; no model call, no prose read.
Single-shot: one model call, no tools, over that prefetch plus one fixed corpus
retrieval whose query is written down before any run. Full context: the same one call
shown every document of the corpus level in place of a retrieval's hits. The prefetch is
one frozen rule for all four systems, a floor the agent may extend through tools and the
baselines
may not, and it can use no sealed key because the harness cannot import the
benchmark.
**The prefetch is a dependent plan with the leave's exact span as its window** (the
fifth build step): read the leave the context names; on the leave asked for,
enumerate the employees, read the leaves overlapping the leave's span, enumerate the
components and the work items, read the events overlapping that span as instants in
the reference zone. The returned leave, never a sealed truth, supplies the span, and
the context carries no window; on twenty worlds the exact span gives the oracle's
answer in every scenario and a margin adds nothing. A span past a tool's bound is
chunked by the bound the tool's own validation applies, in elapsed time, so a chunk
across a clock change is never planned. The record names the rule by an identifier
and a digest over the planner-protocol version, the ordered steps, and each named
tool's definition, method facts and surface protocols; a semantic change to the
planner raises the protocol version. Whether a trace conforms to the plan is a check
apart from coverage, which derives only from the operations recorded; the evaluator's
side of it is described with the preregistration below. The candidate universe is the distinct employee set
the whole-organization enumeration returned, complete when the coverage mapping marks
the employee kind covered, the leaver included and never repaired from truth: every
narrower selection a prefetch can compute changes the outcome (255 and 56 of 640
impacts for the leaver's team, and with the component's members), and the selection
that keeps every outcome needs the skill a clause states. At a larger scale narrowing
needs a completeness-bearing retrieval stage, the two whole enumerations being the
load-bearing reads of a negative about a skill or an ownership.
**The rules-only baseline has no conclusion rule of its own.** It emits the rules'
results over its own view: every impact the view grounds; one assessment of every
employee in the universe exactly as the viability rule returns it, since stopping at
enough viable candidates loses 807 of 1,240 must-assess rows and takes 140 coverage
gaps on twenty worlds; one action per impact as the plan rule gives it, an assign
naming the first viable by the code-point order of their ids, a declared tie-break;
the open questions once each; the conflicts met on the evidence used; and no
constraint, its empty constraint list a premise its record declares. Each claim cites
the citable records of its own proof; claims are ordered by type and key and numbered
after, so identical observations give identical bytes. Each prefetch operation is
attempted at most once, a source left alone after its first unreachable answer; retry
is the harness's. It requires the leave returned and the universe covered, and
otherwise abstains, a completed run with no claims under the condition its trace
shows, which is how both degraded states, an unreadable leave and an unreadable
policy, are represented for every system: no claim type, status or field is added,
and the evaluator reports whether the claim set was empty and the standing of each
claim when it was not. An HR system that contradicts itself, another leave for the id
asked or an enumeration without the leaver, and a returned record no fact can be made
from, fail the run by defect at that operation, since a degrade would fold a defect
into a legitimate unknown; so a defect failure names the operation the fault was
found at, a malformed record or returned records the harness could not accept, and an
absent answer anchors none. A system that makes no corpus read is not degraded by its
retrieval mode: the baseline is graded on what it reports, and its confident errors
measure what prose is worth. Its result on the structured tier is a plumbing check on
shared rules and never an oracle, since the baseline and the evaluator share the
rules; a miss there is investigated, never pre-classified, and disagreement on the
other tiers is its measured quality. Forecast before any system existed and met by
the real one on the reference seed: 810, 270 and 540 claims under the normal
condition and the two gradable outages, every one reproduced by the replay with no
finding, 24, 6 and 18 plan findings against the oracle, the structured tier correct
whole under each. The other tiers are never correct whole under the normal condition;
under an outage the oracle expects less and a report that states little is right more
often, 2 fragmented and all 10 adversarial scenarios with the tracker down and 3
fragmented with the calendar down (FINDINGS, `baseline-basis` and `baseline-graded`).
Grounded is not correct: the replay takes the empty constraint list as a premise. No
monotonic partial report is emitted in a degraded state; a structurally non-viable
verdict and an uncovered action when everyone is one stay true under any policy, and
the report view may reopen it once a claim-level oracle can grade it.

The comparisons measure the incremental performance, cost and latency of these
specified systems; a causal claim about the model or the tools needs a controlled
arm, and the retrieval and decomposition arms are such arms, added after the core is
measured. One model per comparison, held constant across the agent and the
single-shot baseline and recorded per run; which models the comparison arm lists is
the preregistration's to state after the ten-run reforecast, because a model is one
identifier to switch while prompt text and reported numbers bind to it.

**One committed preregistration file precedes the first reported run and is cited by
commit in every evaluation artifact** (the sixth build step; format 2 at the contract
step, format 3 at the event log step). It is one JSON file with
a format version, `preregistration/registration.json`, decoded strictly by a codec in
`core` and accepted only as the bytes its encoder writes, with the development
protocol as prose beside it. Names live in the file and behaviour in code: the file
names the checks, the measures, the interval method, the prefetch rule, the outage
protocol and the composing policy, and each consumer compares what it names with what
its own code computes and refuses to run on a difference, neither side substituted for
the other, since a run that used today's value would cite a registration it did not
follow. The composing policy is the harness's to compute, the reporting policy's
three values inside it; the evaluator cannot compute it and holds each export's
recorded policy to the registered one, which shows the export recorded the registered
identity and verifies no implementation. The anchor table's digest is registered
apart, being the part the evaluator can compute and refuses on.

Format 3 of the registration came with the event log step. The re-dispatch policy's
delay is the deliberate backoff and not a bound on the interval between an outcome and
the next authorization, so its field says so; a registration naming defect as the
category retried after is refused at construction; each system's caps name the
input-bound method beside the counting rule, and each role the identifier its counts
are asked of, since the identifier that counts is not the one that infers and no rule
derives one from the other; and the count retries reference the re-dispatch policy's
maximum and delay by name.

**The file is a draft, frozen or bound.** A draft may hold a value not yet chosen,
typed as pending with what resolves it, and a pending value blocks only the execution
that needs it, so the rules-only baseline runs while the model systems' entries wait;
no entry point fills one with a literal. What a system's execution needs is read one
way by the harness, by the evaluator's plan and by the eligibility check: its own
pending values, and for a system that calls a model the attribution table, the
re-dispatch policy and the entry schema. Frozen fixes the procedure before the world
it is measured on exists: it holds exactly one pending value, the world's version, and
refuses any other, any number whose basis is unmeasured, and a world any scenario of
which was tuned on. Bound holds the version and names the commit of the frozen file it
binds, and binding changes nothing else. The evaluator's entry point reads the file at
that commit, requires it frozen there, and compares the two procedures as written, the
registration without its status, its world's version and the frozen commit; a bound
file checked against a digest it carried would show internal consistency only, and a
comparison of decoded values would hold a setting of true equal to one of 1. A change
after full-set results is an amendment, the old numbers kept, further results on the
same world labeled exploratory, and confirmation needs a world from a new seed. One
limit of this format is known. The single-shot system's query protocol can only be
pending, so that system is in no plan and no frozen file until its own step changes
the format.

**Four systems, two corpus levels and five assigned conditions make twenty-four cells,
reported in two ways.** A cell is a system under a condition at a level. Full context
joins the three: the single-shot path shown every document of the level in place of a
retrieval's hits. The level is an assigned factor of its own, base and padded, and the
answers are the same at both. Every system runs the normal condition at both levels
and each outage at the base level only, so no outage is crossed with a size. Rules
only reads no document and is run at both levels all the same, since one export
entered in two cells would be aggregated twice. Four cells, full context under each
outage, are one group with its rule in words and one decision, pending, run, or not
run with a reason, so that all four or none is a property of the type; nobody executes
or reports a cell whose group is not decided as run. A system that calls a model
registers its roles by name, each with its configuration, prompts and tool surface,
and each system holds its own caps. The normal condition and the two outages that
leave an expected answer, the
tracker's and the calendar's, are answer-quality assignments: the full tables and the
comparisons between systems. The HR system's and the corpus's outages leave the leave
or the policy unreadable, so no claim-level answer exists, and are degraded-condition
assignments: the accounting, the cost, and a table that keeps four things apart,
whether the run met its outage, how the evaluator ended it, whether its report was
empty, and what its own reads make of the report. The names describe the assignment
and never a run's outcome: a normal assignment can produce a limited run, and a run
that never called the failed source ran under no outage and is counted in its arm as
unexercised. Each outage is whole-run at the read-port boundary, because a fault
partway through gives a mixed condition the evaluator limits; no two-source outage is
registered. The schedule's digest covers the source sets, the injection and a protocol
version, and a run records it.

**A run is retried after an infrastructure failure only, and the attempt that counts
is the earliest that did not fail by infrastructure.** Two retries at most. A defect
is not retried, because a retry could conceal it, not because it is deterministic.
Counting the first attempt would measure first-attempt reliability and counting the
last is right only while nothing behavioural is retried, so the estimand is stated:
the registered system with up to two infrastructure retries. The counted attempt is
chosen only among the attempts numbered within the registered maximum, so one past it
is kept with its cost and never counts. Every attempt is kept
and summarized beside the counted ones, so a failure a retry recovered from is shown
and not absorbed. A gap is an attempt absent among those numbered from one to the
smaller of the maximum and the highest number present, and a run with one has no
counted attempt under any rule: it keeps its grade and its cost, is counted as made,
does not pass end to end, and enters no conditional estimate. An intended run that
was never made does not pass end to end either. A run with an integrity, an
operation, a cost or a prefetch finding stays in the tables and is counted beside
them; keeping a run is not vouching for it. Whether a scenario's interval is Wilson's
or the bootstrap's follows the plan and not what arrived: a scenario is a single trial
only when at most one run was made and at most one intended, so a missing or an
unverifiable repeat does not change the method. Inside a run a logical call is
dispatched again only where the attribution table allows it and within the registered
re-dispatch bound, both pending in the draft; a dispatch read as a defect is its
call's last and what the attempt failed by defect at, which the export refuses to
state otherwise.

Whether an attempt may follow another is one total function over the closed vocabulary
of endings, in `core`, run by the admission over what the predecessor's log holds and
by the evaluator over a run's exported attempts. The question had been answered twice,
by a column of the attribution table and by the registration's retry rule, and neither
covered a failure that is not at a dispatch. A new attempt requires the predecessor
closed, its export published, the registered maximum not reached and a named rule that
grants it; an ending no rule names is not eligible. Completed or reported at the cap
is the graded result and permits none; a defect at any site, or a log holding a
recorded defect whatever closed the attempt, permits none, since a retry could conceal
it; an infrastructure failure at a dispatch's send follows its row's flag; the bound
exhausted with the last dispatch unresolved permits one; and an abandonment permits
one exactly when the log holds no dispatch intent. That last rule is the guard against
an operator choosing which attempt counts: with no intent in the log no model output
ever existed, so there was nothing to select on, and the evidence is the log's rather
than a reason the operator picks. It rests on recovery replaying from the log, so a
killed worker's attempt is resumed by a claim and not replaced by abandoning it, and a
kill rerolls nothing but the one call in flight. An attempt the harness inventory
lists for a run without a published export, open or closed with no export, enters the
run's history by number with its status and the ledger's three figures, and a run with
any such attempt has no counted attempt: the ruling said the latest, and an unexported
attempt before an exported one is a history the publication rule forbids, so neither
reading counts such a run.

**Three checks are registered, one comparison is primary, and nothing is registered
as a test of superiority.** Correct whole reads the rows: structurally valid, every
required row reported and right, nothing unexpected, no plan finding against the
oracle. Expected action reads the action rows alone. Reproduced whole asks whether a
non-empty report's every claim is reproduced by the run's own reads; an empty report
is outside its conditional denominator and does not pass end to end. The primary
comparison is the agent against full context on correct whole, end to end, under the
normal condition at the padded level, over all thirty scenarios. The overall contrast
is the claim; tier contrasts are breakdowns named in advance, and no claim of success
is made from a tier, an outage cell or any other comparison. Named beside it and
carrying none: the agent against single-shot at both levels; every pair of systems at
four named places, the normal condition at both levels and the two answer-quality
outages at the base level, named outright because the outages run at one level; and
the level contrasts, one system against itself, padded less base, under the normal
condition, for the three systems that read documents, which measure sensitivity to
the padding and do not say why a system changed. A comparison one of whose cells
cannot be built is kept and says why. A difference is reported with its paired
interval by one method at any repeat count, whole scenarios resampled within their
tiers, with the two-by-two counts beside it at one run a scenario. An interval the
method cannot resolve is stated as unresolved with its reason (no eligible scenario,
fewer than two, a zero denominator, every resample equal) and supports no statement
that one system beats another; the arithmetic stays in whole numbers until one
division, so equal resamples are equal. One that crosses zero is said to include
differences in either direction, never equivalence. The mechanism measure, of the
prose statements a scenario's required rows depend on how many had their carrier
returned, were stated, were admitted and were usable, is registered by its name and
its four stages. Twenty-five measure families are registered, the
answer side over all claims and per claim type, grounding and citations over graded
and limited runs apart, source discipline and retrieval one row each; two systems are
compared on a family's leading row and the rest is reported per arm. Ten thousand
resamples take about a twentieth of a second an interval at these sizes (FINDINGS,
`resample-timing`), so the count buys smooth percentiles and does nothing for ten
scenarios a tier.

**Four supporting comparisons are declared, and nothing executes from them.** Vector
retrieval, a multi-agent layout, a second model and a model-authored report each have
their place, their two systems, their endpoint and their analysis in the file, with
an inclusion decided when the procedure is frozen, before the measurement world
exists; anything added later is exploratory and says so. This format registers one
system of each kind, so it cannot state that a supporting system is included, and the
format that can arrives with the first one built.

**No scenario of the measured world is tuned on.** The registration declares the
count in its world section and a frozen file requires it to be zero, so the statement
is in the registered bytes. The scenario sets, the seeded draw and the second cut of
every table left with it: with nothing held apart the primary set would be the full
set, and every table would be computed twice to the same numbers. Development happens
on other worlds, and a development run names its world itself. The world generated
first is one of them: its recipe is public, and a full-context call over its small
corpus reaches the ceiling, so it separates no model systems. Six of its scenarios,
two from each tier by a seeded draw that read no expected answer, are the
live-iteration subset, listed in the development protocol as bare ids.

**Two diagnostics sit beside the tables and remove nothing from them.** Headroom:
under an outage the oracle expects less and a report that states little is right more
often, so per place the evaluator counts the scenarios rules only does not already
pass, of how many, two counts that name no scenario. It is computed on the measurement
world after the freeze and never becomes a reason to change a cell or leave a scenario
out. Incidents: a source that contradicts itself within a run ends that attempt by
defect, and the fault is the world's or the execution's, which a system that reads
more is likelier to meet. So the contradictions are recomputed from every evaluated
export of the world, the ones out of the tables included, and reported by scenario
with the runs that met one and the runs that did not, in every cell; each comparison
says how many of the scenarios it paired carry one. No run and no scenario leaves a
table for it.

**What a model states exists as types in `core`, ahead of any system that states it.**
A stated fact is a predicate from a closed list of five, a subject and a value in the
registry's shapes, the comment or the section that carries it, a verbatim quote, and for
a requirement the span inside the quote that names its target. Everything that needs no
read is held at construction: the carrier's source is inside the predicate's evidence
domain, a fact about a clause is carried by that clause, the span is a substring of the
quote. An input that breaks one of these never becomes a stated fact and is kept as raw
text with a reason. Three statuses are three types, so none can be read as another: what
was emitted, whether it was admitted, and where a requirement's span was placed. The
anchor table moved out of the benchmark's prose vocabulary into `core`, since the harness
may not import the benchmark and has to ask the same question of a quote that the
generator asks of a draft. The two readings differ in the first person: the generator
knows the fact it required and drops the author's group, and the quote guard keeps every
group and lets the author's be met by "I", so the same words in another person's comment
anchor nobody. The table's digest is a function of its rows, spellings and presence rule,
for the registration to record.

**The view a run concludes from is a total function of what was admitted.** The fact base
refuses one source holding two values for a single-valued fact, and a statement's source
is its carrier's, so a comment read as naming an owner other than the ticket's own field
would have stopped the harness on a model's misreading. No sealed world plants such a
pair; a misreading can make one. Within one source the join therefore settles it: a
statement quoted from a record the run's own reads returned two ways is left out, as
nothing else is concluded from that record; two readings of one carrier that differ are
both left out; a statement against a structured field of the same source loses to the
field; and carriers of one source that still disagree are all left out. Each stays
admitted in the trace with the reason it was left out. Statements that agree stay as
corroboration, and a disagreement between sources is still the authority table's. A
stated fact is dated to the run's day like every fact a run derives: the view drops what
is dated later, and a carrier planted for a later scenario is still a record the run
read.

**The model states facts and the shared rules conclude, for every model system.** A
model decides what to read and states what free text asserts, each fact with its
carrier (a ticket comment or a document section) and a verbatim quote; the rules
compose every claim from the structured reads and the stated facts, and no model
writes a verdict. A model asked to write the whole report was wrong in some row of
every scenario tried, and the same model stating quoted facts reached the rules'
ceiling (`REPORT_NOTES.md`, the one-day probe of 2026-10-04, a development result on
a throwaway world). Five predicates can be stated, the ones prose can carry: a skill, a component
membership, a ticket's owner, what a clause requires, whom a document names
responsible. Only a positive assertion is stated, since the rules derive a negative
from a closed evidence domain and a stated one would be a second, unverifiable route
to it. A fact is admitted when its carrier was returned by a read of the run, its quote
is an exact substring of the carrier, its subject is an entity the run read, and the
quote names the person and the skill the fact is about; anything else is refused with
a reason and the run goes on. These gates establish where a statement came from. They
do not show that the text entails it: a negated sentence carries the same names. Facts
accumulate over a run and none is retracted; two readings of one passage that give one
single-valued fact two values are both left out of the final view, and stay in the
trace.

**A clause's scope is a span the model copies and the harness binds once.** A
requirement is stated with the title of what it applies to, copied from inside its own
quote. At composition the span is compared for exact equality with the titles of the
distinct tickets, meetings and documents the run read: one match places the
requirement, none leaves it unplaced, several leave it ambiguous, and a longer read
title that contains the span and occurs in the passage makes it ambiguous too. The
evaluator's own resolver, which searches a clause's text for every title of the world,
was not reused, because its proof holds over the complete catalog and a run reads part
of it: titles nest, so with a qualified title unread the search settles on the plain
one. Where a title ends is not marked in a clause's text, so a span cut short can
still bind the wrong artifact, and one that runs long leaves a read requirement
unapplied; both are the system's measured behaviour. An unplaced or ambiguous
requirement composes no constraint and no unknown, is shown in the report as a
diagnostic, and is inside what an approval covers.

**A statement is admitted over the reads logged before it, by five gates asked in one
order.** The carrier is inside a record a read of the run returned; the quote is an exact
substring of the carrier as read, with no normalization; the subject is a record the run
returned; the value has a form the run can look for, an entity it returned or a skill of
the public vocabulary; and the quote holds the anchors the table asks of that predicate.
The first that fails refuses the statement under its reason, so one statement is counted
once. The decision is made when the answer that carried the statement is recorded, over
the reads logged before it: a later read never rescues a refusal, a restatement can be
admitted, and the evaluator can rerun any admission from the export. A requirement's
target is no gate's business, so a requirement is admitted on its own carrier and quote
and bound when its target has been read. The lexicon the anchors are looked up in is the
public skill table, which moved into `core` for this, and the names and titles of the
records the run returned, never anything sealed. The gates live in `core` because the
harness admits with them and the evaluator reruns them, and the two may not import each
other.

**A requirement of one is anchored by its criteria and not by its number.** A clause
that asks for one person seldom writes the number: "needs an engineer with Go
experience", "the contact named in the account notes needs React experience". With the
count anchored the guard refused 15 of the 17 requirements a truthful reading of the
suite's throwaway world holds, every one a count of one.
The quote guard therefore asks a requirement of one for its criteria only and a
requirement of two or more for its number as well; the generator's reading of the same
table is unchanged, and the rule is a named entry of the table's digest. The guard stays
lexical. A model that reads "two engineers" as one is admitted and graded wrong, and a
requirement of one with no criterion has no anchor left, so what it composes is judged
like any other constraint.

**A clause governs one artifact, and composition says which.** Every requirement the
join left standing has its span bound once, over everything the run read. A clause whose
spans placed on one artifact governs it, whatever else was stated beside them: a span
that ran long costs nothing when another emission of the same requirement placed. A
clause whose spans placed on two artifacts was read with two scopes and has one, so
neither is used and every statement of that requirement is left out of the view: using
both would lay a constraint on something the clause never governed, and taking the first
would make a report depend on emission order. A span that names a document means the
document's one section, since a responsibility that lives in a document is an impact on
its section; a document holding any other number of sections gives no constraint. Both
leave the placement on record and add a reason beside it. A single wrong span is still
bound and used: that is the model's wrong binding, and it shows as a contradicted
constraint in the replay. The rules are given every composed pairing and select by the
need; a constraint is stated as a claim only where its target lies in the scope of a
reported impact, the artifact or its readable component, which is the set an answer key
expects. A requirement bound to something the leave does not touch is stated as no claim
and is no error.

**One composing path and one composing policy, for every system whose claims the rules
write.** The path is the join, the binding and the scope rules, the shared rules, and the
reporting policy; the baseline is that path given no statement, and its claims are the
same claim for claim as before the path existed. The policy an export records is an
identifier and the digest of a specification: a version kept by hand, the reporting
policy's three values, the five predicates, the anchor table's digest, the binding rule,
the exclusion reasons, the scope rules and the rule for which constraints are stated. A
truthful reading of the throwaway world's prose, composed this way, is graded correct
whole on all thirty scenarios under the normal condition and under the tracker and the
calendar outage, with every claim reproduced by the replay. With the tracker down a true
requirement about a ticket is unplaced and a runbook's statement about a ticket is
refused for its unread subject, and no report moves by either. The parser of a model's
entries reads the one shape a model has been shown to fill and keeps an unreadable entry
whole beside its reason; how a model is asked for entries is the graph's.

**A structured source that contradicts itself within a run fails the run by defect.**
The world is static while a run reads it, so two complete reads that cannot both be true
are never a state to conclude from, and a degrade would pass a broken vendor off as
unknowns a model is then graded on. Four shapes, between two operations in either order:
one record returned with two contents; a read by id answered "no such record" for a
record another read returned; an enumeration that omits a record of its kind another read
returned; a window that omits a leave or an event another read returned and whose own
span overlaps it by that port's rule. A failed or refused read, a capped search, a window
the record's span does not overlap and an operation that is not what its tool declares
establish nothing. The failure is sited at the later operation and names the earlier one,
and the finder returns both typed. When the later read is the one that answered "no such
record" the site is the earlier one, since an absent answer anchors no defect and the
read that returned the record is the one the harness could not accept.
The two HR cases above are the same rule. The corpus
is outside it: a document returned two ways is withdrawn, with what was stated from it,
and a malformed record of any source still fails a run at its own operation. The coverage
mapping still withdraws such a record, because a replay must be total over any export.
Whether a port's sequence is the whole answer cannot be seen from a trace, so a lagging
index shows here as an omission and stops runs loudly.

**Two checks changed meaning before any system was measured.** Reproduced whole also
requires that no claim rests on a premise the report does not hold, since a report
otherwise gains by leaving out a claim that would be contradicted. And the chain check
calls an uncovered action beside a viable assessment incoherent only when no constraint
of the report could apply to the impact: under a clause asking for two, one viable
candidate is uncovered by the plan rule and no other action is right. An assignee the
report does not assess viable is the chain's finding alone; the declared-constraint
check reports the count and leaves the assignee to it, since that check goes uncheckable
when a cited clause cannot be read and the chain reads the report alone.

**The mechanism measure says where a needed statement was lost on the way to a
report.** Some of what the rules conclude rests on facts only prose carries, and a
system that reads prose has a model state them. The statements a scenario needs are
fixed by the sealed scenario and the condition a run was assigned, never by the run:
the ones whose removal moves a key every report must hold. On the suite's throwaway
world that is 31 statements in 20 of 30 scenarios under the normal condition, none in
the structured tier, 15 in 8 with the tracker down and 25 in 17 with the calendar
down. Four stages are counted over that one denominator, each requiring the one
before it, so a drop between two neighbours is a count of statements lost at that
step. Returned: a completed read returned a sealed carrier of the statement. Emitted:
an answer states it, subject, predicate and value, from a sealed carrier that had
come back with the sealed text before that answer. Admitted: the record admitted such
an emission. Usable: the composed view keeps it, and for a requirement a span of it
is bound to what the sealed world scopes the clause to. A requirement bound to
another artifact is composed and graded as the model's wrong binding, and it is not
the needed fact in the view; read as usable it would let a run hold every stage and
fail with no stage saying where. A failed attempt keeps its denominator and whatever
its trace shows of the first three stages, and nothing of it is usable: a system that
fails often must not show better stages than one that finishes. A scenario that needs
no prose statement is in scope with nothing to count, in no ratio and never read as
perfect. The measure does not apply to the rules-only system, to a claim set a model
authored, or under an assigned condition with no answer. It is reported for every
scored arm of a system that states facts, at the whole and at each tier, with the
stages by predicate at the whole, and contrasted on the pairs the registration already
compares, the primary's, each secondary's and each level contrast's; the descriptive
product has no registered reading of a stage and holds none. It carries no claim.

**Every statement a model made is put in one class, and a true statement is not
always one the text makes.** Beside the stages a table counts each entry of each
batch once: malformed; on a carrier the world does not seal; on a carrier no read had
returned by that answer; on a carrier that came back with other content; needed; true
and unneeded, which is valid context; true and stated by other prose than the carrier
named; true in a structured record and stated by no prose; false. The last but one
exists because of what a model does with a comment on a ticket: it reads the comment
as naming the ticket's owner, which the ticket's own field holds and no sentence
says. The anchor guard refuses such a statement and it is not an invention, so it is
counted apart from one. The counts are given as emissions and as distinct statements,
with the recorded refusals and exclusions by reason and each recorded placement
against the sealed scope. A truthful stater on the throwaway world shows the layers
apart: let in whole it reaches every stage on every needed statement, and through the
gates only its requirements are admitted, 17 of the 31, because that world's
model-written prose is stand-in text that names nobody and only the class-written
clauses carry their anchors.

**What a harness recorded about stated facts is decided again from the export.** The
gates, the join and the scope rules are shared code, so the evaluator reruns
admission for every stated fact over the reads logged before the answer that carried
it, and reruns composing over the admitted statements and all the run's reads. A
difference is a finding about the harness: an admission the gates refuse or a refusal
they admit, a refusal under another reason, placements or exclusions that are not the
recomputed ones, or admissions that cannot be composed again at all. The stages read
the record and not the rerun. The claims were composed from what the record admitted,
and a measure read from recomputed admissions would describe another run than the
report does; so a run the rerun disputes is counted as one and stays in its tables.
A composition is rerun only where one was made, by the rules, in an attempt that did
not fail.

**Every document a run was shown is held to its level, and a run that went on past a
contradiction says so.** The level is read off the record and never inferred from the
reads. Shown is every document any operation returned, whoever asked: a search, a
read by id, the documents a harness puts before a full-context call, which are
operations of the trace like the rest. A document outside the level's sealed
membership is a finding naming the operation and the document. The membership is the
sealed world's, and a world sealed without filler has one level, the base one, every
document it seals; a run assigned any other level is not evaluated for it, which is
counted apart from a run with no finding. A run whose reads contradicted each other
and that did not fail by defect, because it reported or because it failed later for
another reason, went on where the rule stops a harness, and is counted. The
accounting and the attempt summary hold the four counts from one function, over the
counted runs and over every attempt.

**What a record states about its own ending is held to its export.** Format 3 lets a
record say how many segments an attempt ran in and on which commits, between which two
instants, over which payload its approval was asked, and which generation an
abandonment fenced, and nothing recomputed any of it. Five findings, each the
harness's: an evidenced active time above the elapsed time, which the record admits
because a wall clock can step; a terminal instant before the admission, the elapsed
time then unavailable and never clamped, made absolute or called a lower bound, the
active time still read from the segments' own clocks and the first finding not
evaluated; segments on more than one commit; an approval digest that is not the digest
of the claims and the composition the export holds, computed by the function the
harness computed it with; and a fenced generation that is not the segment count, which
a conforming harness never produces, since a claim raises both counters and nothing
else raises either.
A run whose timing is incomplete, a segment's end never recorded, has a duration that
is a lower bound: a cell's cost ledger counts those runs and gives the segments per
run beside the durations, so an interrupted run never reads as a fast one. Under a
bound registration a run whose segments ran on two commits leaves the tables as a run
from a dirty tree does, named in the listing with its grade; one export of two
programs is not a run of the registered harness.
Every such attempt is also a provenance incident in the analysis, by the identity its
export carries and its commits, read from every evaluated export of the world before
any reason removes a run from a table, so one refused for its tree or its settings is
listed all the same. It is kept apart from a source that contradicted itself: it is
about one attempt, implicates no scenario and enters no comparison's count.

**Each dispatch's reading is held to the registered table, and what the export cannot
give back is said.** The evaluator reads every observation again by the table's own
function and compares the rule and the kind recorded. A dispatch records the rule and
not the cause the harness supplied, so the observation is read under no cause and
under each cause of the closed list, and the recorded rule must be one of those: a
record that names a defect row is held to the row's match and taken at its word for
the cause, the failure at that dispatch saying where and why. A dispatch that was
followed by another must have been read by a row that allows one, the table's row
for the observation whatever rule the record names, an unresolved dispatch always
may be followed, and a call holds no more dispatches than the registered bound. The
check is evaluated only for a run made under the registration read, whose record
names the registered table's digest: a record names the table and not the bound, so
a run of another registration is held to neither.
A run held to no table is counted apart from one with no finding; while the
table's rows are pending that is every run. A response whose metadata shows the SDK
sent more than once is a finding wherever a response carried the count, nothing being
allowed to retry beneath a dispatch. The tool calls a model made are tallied by what
became of each, the undispatched ones by reason.

**What the measurement still lacks before any model system is measured.** The
paragraphs above describe the evaluator and the committed registration as they stand;
the event log step built the harness that fills the export, and what remains is listed
here and rewritten as each lands. Until then the registration stays a draft, and no
reported measurement is made under it.

**The measurement world is generated by the tree, from a seed nobody has seen.** The
seed of an embargoed world is thirty-two bytes of entropy stored as a repository
secret and read by the generator from the job's environment as lowercase hex, parsed
in memory and never passed through `argv`, printed, or transformed into any other
form, because the committed scenario-specs digest and the semantic digest are
functions of the seed and public code alone, and a small seed is found by
enumeration against either. A disposable secret's masking was read in a passing and
a failing log before the mechanism was trusted, and the first dispatch under the
secret source with no secret set refused at the boundary and opened no store. The
recipe's `--embargoed` is sealed into the spec's provenance as a disclosure mark,
outside the semantic encoding, so every reader learns from the world what it may
print and not from a flag an operator remembers: the proving command and the
evaluation job print `withheld` for the digests and the retrieval-target counts, the
audit sheet writes to an ignored path only and refuses an embargoed throwaway, a
resume's mismatch names no digest, and a scan of the checkout for either digest
fails the evaluation job on a hit, one more check that proves nothing about logs. A
seed the reservation book refuses is replaced by a fresh draw, numbered and counted,
never logged. After the last confirmatory measurement the seed and the recipe are
published in FINDINGS.

**A development world is sealed unprojected and read through planted readers.**
Under `--unprojected` the generator opens the two stores alone, no vendor host and
no credential, seals the truth pair, every document and the scenario specs by
conditional create, reads each back, and writes no checkpoint and no manifest; a
local root must be one the repository ignores or does not hold, checked
structurally, since a sealed world carries its answer key. Three readers at the
adapters level present the spec's plantings as the people, work and calendar systems
under the three read ports, with a source and a reachability switch for the outage
conditions, every record returned whatever its observable day since time is applied
above the port; they are built from the truth store, so a development world is read
by the benchmark's own principals and never by the deployed application. Such a
world does not promote through the projector as it stands: a later projected sealing
finds each document sealed, a found entity reports no receipt, no checkpoint holds
one and the coverage proof refuses the run, which the test that was to prove
promotion pins instead; the read-side locator recovery is the projection module's
named revisit. The first one, seed 101 under the golden plan with twelve filler
documents, sealed forty-one objects and proved thirty scenarios with retrieval
targets of 33, 15 and 27 under the three answerable conditions, against the golden
world's 31, 14 and 25 (FINDINGS, `generator-step`).

**Export format 3 is built and the event log fills it; three things it names still
lack their values.** The attribution table is a type in `core` with its matcher and
its digest, and a section of the registration whose rows are pending. By the ruling a
response under a registered stop reason is behaviour, a denial, a throttle, a server
error and a timeout are infrastructure, Nova's model error is behaviour only under the
evidenced signature of a tool call cut at the output limit, and anything unmatched is
infrastructure and flagged; whether an observation may be re-dispatched inside the run
and whether it makes the run eligible for a new attempt are two columns of it, and a
defect is read only with a cause the harness established. The re-dispatch policy's two
values are pending too, a registered maximum per call and a fixed delay, dispatch
numbers surviving restarts because they are the log's. The zero-cost rules and the
price rows arrive with the first live run. A model-calling run is not admitted under a
pending value, and a development registration carries provisional ones. Measurement
runs are not streamed.

**Four audits read a run's account, counts, calls and eligibility from the export, on
the same `core` functions the harness ran.** The account check replays every recorded
authorization over the account as it stood at that position, by one adapter that
rebuilds the transitions from the intents' and outcomes' positions, and holds what the
run spent against its reservation and its token cap under the registered counting
rule; a rules-only export reserves nothing, so its account is not evaluated, a
different statement from evaluated and empty, which is an agent's attempt with no
dispatch. The count check holds every bound to the counting operation it names,
succeeded, earlier than the intent, covering the request's digest and equal to the
bound, every operation to its own outcome read again, every group of counting requests
to the retry rule they were made under, and the method and identifier to the
registered ones. The call check reads each logical call's standing under the table and
the policy and whether the attempt ended where its calls say it did. The eligibility
check projects how an exported attempt ended into the closed vocabulary and asks
whether it permitted the attempt after it; an attempt its predecessor did not permit
keeps its export, grade and cost, carries a finding and is never the counted attempt,
and a missing predecessor establishes no permission. The limit is the report's: the
evaluator checks recorded evidence, authorization arithmetic and observed breaches,
and cannot recompute a tokenization or establish compliance where usage is incomplete.
One finding kind, a count whose method is not the caps', is unreachable while one
method is registered, and stays because the registry is designed to grow. The four ran
over the first export the real store and worker produced with no finding.

**Whether a run's prefetch is the registered plan is checked from its trace, for every
system and every export that decodes.** The planner and the chunking are `core`'s,
shared with the harness, so a fault of the planner is invisible to the check and stays
with the planner's tests. What the evaluator reconstructs by itself is the execution:
the opening read always; the rest of the plan only when that read returned the leave
asked for, the span taken from the returned record and never from sealed truth; no
call once an earlier call of the same source ended unreachable; none after a call that
returned a malformed record, and nothing else ends the plan, since a defect found at a
read that completed is found after the prefetch has finished. Four findings, missing,
wrongly parameterized, reordered and extra, each naming a step and an operation and
never an argument; none changes coverage, which derives from the operations recorded.
A run whose record names another prefetch rule is not evaluated, which is a different
statement from having no finding, and a registration that names a rule this code does
not plan refuses the evaluation whole. Arguments are compared with keys in one order:
the planner and the record spell an object's keys differently, and the first run of
the real harness against the check failed on exactly that.

**An evaluation is one immutable artifact over an explicit set of stored runs.** Every
object listed under a world's runs is in its listing with the store's version id,
the digest of the bytes read, its cost, and exactly one reason for being in or out of
the tables; a run that contributes no estimate was still paid for. A run is eligible
when the registration at the commit it cites has the evaluator's own bytes and what
the run recorded of its execution is what the registration says: the system and its
variant, a registered cell that runs, the schedule's digest, the caps, the prefetch
rule, the retrieval, the composing policy, and for a model system its roles by name,
each with its configuration, its whole prompt set and its tool surface, and the
attribution table its dispatches were read by. Equal bytes alone would show matching
declarations and nothing about what ran, and the bytes are compared before anything at
the cited commit is decoded, so a file of an older format there is another registration
and no error. A system with a value pending that its execution needs has nothing to be
compared with. Under a bound registration the harness's tree is clean as well. A run
that fails any of these, or whose commit resolves to no registration, keeps its grade
and enters no table. Four things refuse the whole evaluation, since tables cut from any
would look complete and be about something else: two eligible exports of one run and
attempt, a registration the evaluator cannot read as a plan, a bound registration
evaluated against another world, and one whose procedure is not the frozen one's at the
commit it names. A set that is merely short is evaluated and shows its shortfall. The
label is derived and stored, never read from a run: development under a draft and under
a frozen registration, whose world does not exist yet, reported under a bound one,
exploratory when that registration declares it amends an earlier one and that
full-set results existed, the two declarations carried as declared because no job
can read earlier evaluations to check them. The evaluator runs from a clean tree,
records its commit, and records which paths of its declared implementation changed
since the registration's commit; whether a change was maintenance or a change to a
metric is a judgment for the report. No run is replaced after the fact: an evaluator
defect means evaluating the same stored runs again, a compromised execution means
measuring again under an amendment, and both results are kept either way. The
artifact's written form is derived from its types by one encoder with no decoder,
the format held by a version and a pinned list of key paths; a run is written as its
outcome and findings, and what the stored export gives back is not written twice. An
explicit codec with a strict decoder replaces it when something reads an artifact
back.

**The evaluation names the harness inventory it was held to, and a stored object has
one of five standings under it.** The request carries the inventory's digest; the
object is read apart from the listing, its bytes must digest to the name and decode as
an inventory of the evaluation's world, and it is refused by its key alone otherwise,
since the decoder's own message quotes what it refused and the job's log is public.
The latest inventory by instant was declined, as naming what was read only after the
fact and needing a tiebreak the listing's order cannot give; an optional inventory was
declined, as two artifact shapes and no way to tell closed without export from never
admitted. The inventory lists every attempt of every world the store holds, so it is
narrowed to the evaluation's world before anything is held to it, by each attempt's
own world version. Every object under the world's runs prefix outside the inventory's
own prefix is placed from its key before a byte is read: current, the published export
of a listed attempt; superseded, an earlier reader's export of one, listed and not
current; unfinished, the object a pending or a failed record names, uploaded with no
record of success; a publication orphan, under a listed attempt's prefix and none of
these; and not in the inventory, under no listed attempt's prefix, published after the
snapshot or by another harness, which invalidates nothing and enters no table, since
the evaluation is of the snapshot. An object under any standing that decodes as an
export of this world is still evaluated, so its reads are read for a source
contradicting itself as every out-of-table trace is. Two more things refuse the whole
evaluation: a listed export absent from the store or with another digest, the store
then not being the snapshot's; and, under the reported label only, an in-scope attempt
the inventory lists as open, where a development evaluation during a batch counts it
and refuses nothing. Closed without export refuses nothing under any label. The
artifact's coverage record holds, over the in-scope attempts, the runs intended,
admitted, never admitted, exported, open and closed without export, the publication
incidents among those, each unexported attempt with its status, its incident and the
ledger's three figures, and the apart counts in one place, failed by defect, failed by
infrastructure, publication incidents and never admitted, because quality among graded
runs alone favours the system whose hard runs go missing most often. An attempt listed
with no export is placed in no cell, the inventory holding no scenario, and is counted
in the whole alone; placing it would need the inventory to carry the frozen inputs'
placement identifiers, a format change taken when a cell's missing runs matter to a
comparison. The artifact is at format 9, the listing of stored objects named apart from
the harness inventory since the close. The first evaluation over an export the real
store, worker, publish and inventory commands produced listed it current with coverage
one of one and out of the tables for its settings, the fixtures' record naming values
the draft registration leaves pending.

**The evaluation job proves the world before it grades anything, and its log holds
nothing sealed.** It runs by hand under its own environment and role: a required
reviewer, the main branch only, no secret, reads of the run exports, the scenario
specs and the two truth objects, and one put under the evaluations prefix. Every
dispatch first probes that boundary, positive controls before refusals, each refusal
asserted on the permission error. The refused put carries the create-only header and
targets a disposable key, because the bucket refuses a put without that header for
every principal and a plain put refused would say nothing about the role. One command
proves the world from its three objects and writes nothing; the other lists the
stored runs, resolves each cited commit in the checkout's own history without running
anything from it, and publishes the artifact. The log is public, so the job prints a
world version, totals, keys and labels, a known refusal
by its message, and any other failure by its type alone with no traceback, which
would print a chain of causes that can quote what the rules were reading. On its
first dispatch the golden world was proven, the six development scenarios selected,
and its retrieval targets counted for the first time: 31 under the normal condition,
14 with the tracker down, 25 with the calendar down (FINDINGS, `evaluator-identity`).
Publication and the grading of a real export are proven by the first live run, not
by a probe.

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
within one process and nothing more, and recovery across processes is from the log,
as the event log passages below rule; the event log is the authority for audit,
narration and the run export; every recorded operation carries a stable identifier so
a resumed node's repeated append is refused rather than duplicated, and the two stores
must reconcile after every tested crash point. The ruling is provisional on an
acceptance spike, the first harness build step,
built as the smallest real vertical slice on PostgreSQL: resume an interrupted run
after a process restart with one approval event; a crash injected around a tool
result, its checkpoint and its event append, recovered with no duplicated or missing
event; streaming and forced tool calls through the actual `eu.` Anthropic and Nova
configurations, which the prose probe's different client path does not establish;
the complete export from the event log alone. A failure is attributed first: a
persistence-design failure fixes the design, which a hand-rolled loop would share; an
integration failure reopens the framework before any further harness code.

**The acceptance spike passed, so the framework ruling stands for the versions and the
configuration it ran on (2026-10-04).** Every must-pass check held (`probes/FINDINGS.md`,
the two `langgraph-spike` entries): forced tool calls and the exact tool-result string
on both model families, streamed and not; the complete export built from the event log
with the checkpoint tables dropped; a process killed at each of the 82 seams of a
scripted run and recovered with the two stores reconciled and one approval event;
invalid tool calls disposed with no port called; one live run through the whole path.
Accepted: `langgraph` 1.2.12 with the synchronous PostgreSQL saver on its own
autocommit connection, `sync` durability, no node retry policy, and `langchain-aws`
1.8.0 as the chat client. A change to the framework or the saver reruns the scripted
checks; a change to the client reruns the provider probes and the live path. The
asynchronous saver is not accepted by this and is a question for the demo milestone's
entry. Three things the spike showed shape the harness that follows. The log is ahead
of the checkpoint and wins: a node looks its result up in the log before executing,
checkpointed state is a cursor of positions and digests, and the model request is
rebuilt from the log, so what the model is shown has to be a rendering the log
reproduces byte for byte. Recovery cannot read the framework's state alone: an empty
list of next tasks also describes a step whose writes are saved and whose checkpoint is
not, so completeness is the log's terminal event agreeing with the checkpoint. And
export format 1 has no place for several things a real run produces (an intent with no
outcome, the approval, a second process's revision, a tool call that did not parse or
was never dispatched, a run that raised), which the contract step's format answers.

**An attempt has one writer at a time, and a claim always wins.** Ruled at the event
log step (2026-10-05), the design interview between the acceptance spike and the
harness, eleven forks each read cold by an external chat before its ruling. An attempt
is a row with a generation, a segment count and an open or closed state; the row is
coordination and the log stays the history. Every authoritative change, a worker's
append, a claim, a terminal event, an abandonment, an outside producer's append, locks
the row, checks the generation and the open state, appends and commits. The acceptance
states that order and no statement count: a guarded insert that reads a snapshot can
commit after a takeover it overlapped, and the step's first probe showed the race in
that plain form and its absence under the lock (FINDINGS, `lock-race`). A claim raises
both counters and appends the segment's start in one transaction, carries the claiming
process's nonce so a retry after a lost acknowledgement gets its receipt and opens
nothing, and is refused on a closed attempt. A claim always wins: no lease and no
liveness check, a worker that finds itself fenced stops and never reclaims, so two
healthy processes cannot fence each other in turn; the cost is that an accidental
double start leaves the displaced segment's end unrecorded and its timing incomplete,
at a rate nobody has measured. The fence closes a gap the contract step left: between
"a stale worker can neither dispatch nor append" and "a request in flight cannot be
cancelled" sits a dispatch authorized before the fence and sent after it, which no
database mechanism prevents. Dispatch authorization is committed under the fence
before any external execution; after fencing the old worker authorizes nothing and
appends no outcome, and a dispatch it had authorized may still be sent, its allocation
accounted and its outcome never accepted, so it stays unresolved. Whoever delivers an
approval or abandons never claims and appends under the same lock with its own
identity; a worker that still owns the attempt and has not ended its segment resumes
after an approval without a new claim, since the automatic policy approves while the
worker runs. An abandonment names the generation it expects and is refused on a
mismatch, so a delayed command cannot abandon a replacement worker, and no operation
closes an attempt regardless of owner: an operator whose command was refused reads the
generation and reissues. A closed attempt rejects every later append, a matching
generation's included; an identical re-append of an event it holds is an idempotent
receipt and the same identifier with other content raises.

**An event has a dense position, a structured key and one of two envelopes, and one
pure transition function decides what may be appended.** The position is a
transactional counter on the attempt row, taken in the insert's transaction after a
check for an existing identifier, so it is dense from one and a rollback keeps
nothing; a database sequence was declined because a rollback keeps its increments. The
identifier is unique on run, attempt, kind and a key derived from what the writer is
doing: an outcome names its call and dispatch, an approval the request it answers, a
segment boundary its segment, a read its origin's ordinal or the tool call it answers.
The envelope is first-append provenance kept unchanged on replay: the position, the
database's timestamp sampled at the insert after the lock, and for a worker's event
the generation, the segment and a whole-millisecond offset read from the worker's
monotonic clock after the lock, nondecreasing within a segment by construction. An
outside producer's event, an admission, an approval, an abandonment, carries its
producer's identity and no segment or offset; its timestamp is when the log accepted
it and not when a decision was made, and raw timestamps are kept and never clamped.
The log has one wall clock and elapsed time's two ends are read off it. Idempotence
compares the versioned canonical content, and what changes an event's meaning is
content: the approver's identity, an abandonment's authority and targeted generation,
a segment start's harness revision; two authorities delivering one decision conflict
and raise, and a returned old event grants no permission to continue under its old
ownership. A worker that stops cleanly without a terminal event writes its segment's
end, an execution-state transition after which that segment authorizes and appends
nothing while the attempt stays open for a claim; a terminal event ends its segment
implicitly, and an abandonment never writes a worker's end. Unique keys do not prevent
two terminal events under two keys, a resume with no accepted approval or work after a
segment end, so one pure function takes the attempt's state and an event and gives the
next state or a refusal, the appender runs it under the lock against the state on the
row, and the reader folds it over the whole log before it builds an export; the rules
are written once and not again as database constraints, and unknown kinds fail loudly.
Sixteen kinds exist, each with a written key specification and what it needs in the
prefix, and the state they fold to keeps the events and a few derived fields, every
per-call, per-count and per-operation view a projection over the events so no two
fields can disagree. A log format version covering codecs and canonicalization is set
on the row at admission and immutable; a worker claims only an attempt of the exact
format it writes, a reader may support older ones, and no open attempt is migrated.
The database schema's version, the log format's and the export format's are three
numbers with their own compatibility rules.

**Admission is one transaction that reserves, creates the attempt and freezes its
inputs, and the settlement rides the closing event.** The admitter writes the ledger's
reservation, the attempt row at generation zero and the admission event at position
one as an outside producer, so a rollback leaves nothing and an admitter that dies
after the commit leaves an attempt recovery can find; the event's timestamp is where
elapsed time starts. The event holds everything the export's record and an empty trace
need, so an export is rebuilt from the log with no mutable file beside it: the full
run context and not the scenario alone, the assignment, the registration commit, the
caps, each role's configuration and pricing selection, the prompt and tool-surface
digests, the prefetch rule, the composing policy, the parser's identity and schema,
the attribution table and the re-dispatch policy by value, the retry rule, the
reservation and the log format version. The admission request carries the context,
since the agent decodes no scenario specification and the import law keeps it from the
package that could; the launcher that builds frozen inputs from a registration and a
sealed world's scenario is the first live run's, at a root the law lets import both
sides. A worker compares its effective configuration with the frozen inputs before its
claim commits and a mismatch refuses the claim with no segment opened; the harness
revision is outside the comparison because it is recorded per segment, a history on
two commits being one the export reports. Equality with the frozen inputs says the
worker selected the admitted inputs, and what a provider returned and what was
rendered and sent stay execution evidence. Before an attempt exists there is no row to
lock, so a row per run serializes attempt numbering and the predecessor's check, and
locks are taken in one order everywhere, run, attempt, ledger. Attempt n plus one
requires n closed, its export published, the registered maximum not reached and n's
ending permitting it, under the one eligibility function; an operator's request does
not go round the third, so a closed defect attempt is not replaced. The request's
identity is held by the caller across its retries and names the run and the attempt
asked for: repeating it returns the recorded result, admission or refusal, and never
reserves twice or advances the number; a refusal consumes no number and is committed
before it is returned, so no raised error rolls it back. Uniqueness on run and attempt
is the backstop, identical frozen inputs under another request getting the receipt and
other inputs a conflict. The settlement is carried by the closing event, a terminal
event or an abandonment, with the ledger updated in that transaction, so closing and
settling are one transition and no closed, unsettled state exists; a settlement event
after the closing one was declined because closure would reject it. Open attempts are
enumerable from the rows alone, with no checkpoint and no worker event.

**A dispatch's worst case is written into its intent, the run's account is a fold over
its events, and the shared ledger is touched at admission and closure only.** The
intent event holds the dispatch's worst case in pico-dollars and in tokens, in the one
insert under the fence, so per-dispatch accounting never touches the shared ledger.
Money and tokens are released by evidence and accounted apart, and how a dispatch is
attributed plays no part in either: an evidenced refusal before sending releases both,
usage priced whole replaces the money allocation with the cost, a count the registered
counting rule establishes replaces the token allocation, an evidenced zero-cost rule
zeroes money and says nothing of tokens, and no outcome, usage with no zero-cost rule
and incomplete usage retain. Each dispatch contributes once, the observed amount when
it is complete and otherwise the allocation, a known floor sitting inside that figure
and never added to it; the first proposal counted an incomplete dispatch's floor
twice. Authorization is a fold over intents and outcomes in position order under the
attempt lock, so two handlers cannot spend the same released room and every prefix is
checked, not the final balance alone: a loop allocation that does not fit, the
finalization reserve left free, enters finalization, a finalization allocation that
does not fit ends the run at its cap with what the view holds, and a refused loop
allocation never skips finalization. The guarantee that contributions stay inside the
allowance holds while every allocation is a true bound, which is why a method is
admitted only on a justified upper-bound basis; when an observed amount exceeds its
allocation the account uses the observed amount, keeps the excess as evidence, records
the breach, authorizes nothing further and ends the attempt by defect at that
dispatch's record phase with the response preserved, the finding naming the bounding
contract and presuming nothing about which of request assembly, the estimator or the
provider broke it. The shared ledger is corrected at closure; the exposure accepted is
a worker that dies between the two and leaves the open reservation short by the excess
until the attempt is abandoned. The account is one pure function in `core`, used by
the worker before it authorizes, by the closing event to settle, and by the evaluator
through an adapter that rebuilds the transitions from the export's positions. The
shared ledger is append-only entries, a threshold set, an admission, a refusal, a
settlement, an import, and one locked head holding the committed total and a revision
that counts committed entries, refusals and threshold changes included; an admission
sees the original reservation or its committed replacement and nothing between. An
open attempt holds its full reservation against the threshold, protecting what it may
still authorize, and at closure that is replaced by the sum of its dispatches'
contributions; a kept attempt that is later resolved reopens nothing and rewrites no
export, and no adjustment entry exists yet. A threshold is an entry naming its
authority and the registration commit it came from, applied prospectively, never above
the registered limit and never below the committed total, so no allowance shrinks and
no closed attempt is repriced. The size of a run's reservation is not ruled: it needs
the price table of the first live run.

**A request is authorized on an established upper bound of its input tokens, by one
registered method, and the token cap counts logical calls.** Which token classes a cap
counts is a registered name in a closed registry in `core`, one rule today summing
input, output, cache read and cache write; a count is established when every counter
the rule names is reported or is absent where the price table records that
configuration's absence as meaning zero tokens, and otherwise the known subtotal is a
floor and the token allocation is retained, a zero price, a waived charge and an
incomplete monetary total proving nothing of tokens. The output bound is the role's
effective maximum output and admission refuses a configuration without one; the money
bound is the input bound at the highest input-side rate the configuration can be
billed, cache writes included, plus the output maximum at the output rate, and a basis
lacking a rate for any of those classes refuses to price rather than taking the
dearest it has. The call cap counts logical calls: the slot is consumed when the
call's first intent commits, a re-dispatch takes none, a refusal or a released
allocation gives none back, and a call keeps its purpose across recovery; counting
dispatches would be sound and a different experimental condition. How a worst case is
computed changes when a run stops at its cap, which is graded, so the method is
registered by name and version beside the counting rule. Two probes decided the method
(FINDINGS, `input-bound`): a request's bytes were never under the reported input on
ninety-two captured sends, and the provider's counting call, served for Haiku 4.5's
base model identifier and refused for its `eu.` profile and for Nova Pro, ran sixteen
to forty-nine tokens above inference on seventeen requests and never below, the same
count twice for the same body. The one method is the provider's count with no margin,
admitted on three things none of which is a proof: the provider's documented statement
that the count matches what inference charges, the profile's constituents all being
the counted model, and the seventeen requests. Bytes were declined even for
development, since the inequality held on two request shapes and nothing establishes
it for the provider's constructed input, which is another object than the body; the
consequence is that a model family with no counting call has no established method and
is no registered model-calling cell, so Nova Pro is out as the second model unless one
is established for it. The registration names the identifier the count is asked of,
since it is not the one that infers and no rule derives one from the other. A counting
operation is two events, a start committed before the remote call and an outcome,
retried under the re-dispatch policy's maximum and delay on a counter of its own that
recovery does not reset, taking no call slot and no allocation, every failed count
staying in the log when a later one succeeds. A failed count is read three ways from
the errors the SDK declares, and nothing is transient by default: throttling,
unavailability, an internal error, a client timeout or a lost connection are retried
and exhausted as an infrastructure failure at the `input_bound` site with a new
attempt permitted; a validation, access or resource refusal is a defect at once, the
registered configuration being wrong; anything else ends the attempt at once by
infrastructure with no rule permitting a new attempt, over calling it a defect, which
would assert a cause nobody has. A denied count therefore ends by infrastructure
though no retry can cure a missing grant; the deployed role's grant for the counting
call is the first live run's, a platform ticket. Only a durable successful count is
reused, under the request's digest, the counting identifier and the method's version,
by a re-dispatch and by a resumed worker alike; the request is frozen before it is
counted, and the check under the lock after the count rejects a changed request, lost
ownership, a closed attempt, a frozen approval and a recorded defect. The export
states the input bound so the arithmetic is audited, and it holds the request's digest
and not its body, so no bound can be recomputed from an export.

**A call's re-dispatch is one pure decision over its dispatches, with a fixed delay.**
From a call's dispatches, the attribution table and the re-dispatch policy, one
function in `core` gives one of five results: answered; ended as behaviour, where a
service error the table reads as behaviour has no answer and is no infrastructure
failure; permitted to dispatch again; failed by infrastructure at the last dispatch;
failed by defect. Stopping observations are applied before exhaustion, so the last
permitted dispatch returning an answer fails nothing, and permitted is not authorized,
since ownership, the attempt's state, the room left and any breach are still checked
under the lock. It is called after each outcome and on recovery, and the transition
function refuses an intent that follows a dispatch whose row allows no other, as it
refuses one beyond the maximum. A dispatch's number is the intents logged for its call
plus one, taken under the lock. The delay is a fixed backoff with no jitter, since one
serialized client has no herd to spread and a fixed wait reproduces, revisited if
concurrent calls are allowed; it is the deliberate backoff and not a bound on the
interval between an outcome and the next authorization, which also holds preparation,
a count and the lock. The wait runs from the log's acceptance of the previous outcome,
and a worker in a new segment compares the database's time with that timestamp and
waits the remainder, since offsets of two segments cannot be subtracted; the wall
clock is used for a wait and never for order, and a wait in a running worker is active
time while downtime is not. The table's rows and the policy's values are pending until
the freeze, a model-calling run is not admitted under a pending value, and a
development registration carries provisional ones. A new attempt is always an explicit
admission request; no worker re-admits a run.

**A tool call is resolved once from the log, by a result or a skip, and what is not
proven unreached is unresolved.** The outcome event holds the response as it arrived,
with everything the parser needs, appended before anything parses it. What a tool call
is, unparsed, a fact batch or undispatched for its stop reason, and what the gates
admitted, is one pure function of the response, the frozen inputs and the permitted
log prefix, called by the worker and by the log reader; the export states what the
recorded response means under the registered parser and not when or whether a worker
finished parsing it. The reason is a worker killed between an outcome's append and a
recorded parse, its attempt then abandoned, which would export a complete response
with no answer and no parse-phase failure, a shape the format refuses; a parser that
raises while an attempt is being closed closes it by defect at that dispatch's parse
phase, and no empty answer is invented. The parser's specification and version, its
schema and the gate policy are frozen inputs verified at claim. The response body is
the provider's Converse object read by one protocol: a tool-use block is a tool call,
the fact tool's call is the batch its input holds, a text block opening with a brace
is a fact payload in the answer's own content, and any other text makes the answer's
text present. One live send under a stand-in prompt returned the fact call with its
one entry nested a level deeper than the schema says, which the parser refused as
undecodable with the outer shape holding, so the protocol was adopted unamended and
the entry's shape goes to the prompt step with a one-level flattening as the candidate
amendment. Resolution is one event kind with two contents keyed by the call, a result
holding the operation, a wrapper's refusal included, or a skip, the cap or a source
already unreachable, a final decision not to run honoured on replay; the uniqueness of
kind and key forbids both for one call, and a skip is no intent. The tool calls of an
answer run in the answer's order and none begins before its predecessor's resolution
has committed; a worker whose append fails stops, a durable defect result stops the
sequence and recovery keeps the stop. The reader's rule: no resolution means
unresolved unless the log and the barrier prove the call could not have been reached,
an earlier call of the same answer having no resolution or a durable stopping result;
who closed the attempt proves nothing, and a single segment with a recorded end proves
nothing either, since a worker can run a tool, fail the append on a transient error
and still write its terminal event. A skip establishes undispatched only when the
segment that wrote it also wrote the event that made the call next; across a segment
boundary the disposition is unresolved and the skip stays as the worker's decision,
conservative by choice. On recovery held resolutions are reused, only unresolved reads
still permitted run again, and the gates are given the reads strictly below the held
outcome's position, the original position on a re-append and never the recovering
worker's current one, admissions rebuilt in outcome order so a tool an answer asked
for never supports a fact of that answer; unreachable-source state comes from durable
outcomes only. A later arm that runs tools in parallel voids this evidence and rules
it again.

**Recovery is from the log on a fresh checkpoint thread per generation, and an
attempt's ending is one function of its log whoever closes it.** A recorded stopping
defect is the ending, at its site, an operator's close included: that close finalizes
a defect and makes no abandonment, and who closed and why the attempt failed are two
facts both in the log. After a defect no further investigation is authorized; the
segment start of the worker that recovers to finalize, the bookkeeping and the closing
event may be appended, no end is invented for a dead segment, and a finalizer's own
failure never replaces the recorded defect. After an approval request the review
payload is frozen, no new intent and no tool resolution, so a call unresolved at the
freeze stays unresolved by construction; a defect found while terminalizing closes the
attempt by defect with the approval kept as evidence of what was approved, and nothing
is composed again. The order: the log before any checkpoint; a closed attempt only
finishes publication; a recorded defect is finalized; a requested approval recovers
the frozen workflow; otherwise the attempt is replayed and continued under the
dispatch and budget rules. The checkpoint thread is derived from the run, the attempt
and the generation, so every checkpoint, pending write and subgraph checkpoint of a
fenced worker lands where no later owner reads, and every claim starts on a fresh
thread and replays from the log. The shared thread was recommended on the reading that
a stale checkpoint is an older cursor whose content the log holds, and reversed
because a checkpoint also holds pending task writes the framework uses to skip tasks,
a fenced worker's node raises on its refused append and leaves an error write, and the
probe to clear that path had grown to late pending writes, competing descendants and
late interrupt state, all three excluded by construction by a thread per generation.
Stated consequence: a generation is one process, no process reads another's
checkpoints, the saver's durability serves inspection and the behaviour equals an
in-memory saver; the PostgreSQL saver stays under the accepted pins and dropping it is
a later, cheap call. A claim on another commit than the first segment's is refused
unless the request carries an override recording its authority and both commits, which
waives no finding, incident or exclusion; a dirty tree is recorded and not refused. A
fenced worker exits and writes nothing; a stop signal writes a segment end and leaves
the attempt open; an error after which no durable append is possible leaves it open
too; any other exception is a terminal failure by defect at the `unhandled` site, a
harness fault stopping the run rather than being replayed into the same crash, the
reason a qualified exception type and a repository-relative location with no message,
excerpt or traceback. The handler sits at the driver around the graph's invocation and
never inside a node, since the framework signals an approval pause there by its own
mechanism. The crash matrix is the acceptance: a child running the real worker is
killed at every boundary the reference run crosses, the store's three per write, the
load's read, the saver's two methods and the handoff's two points, and at the
recovering process's crossings too, each row's outcome forecast in a manifest before
the run and a contradiction a named finding; the first run found the forecast wrong at
the saver's crossings of the terminal step, where a recovery finds the attempt already
closed, and the rows accept that. The commands have rows of their own, the admission's
receipt and refusal paths, the publication's record and put boundaries and the
inventory's snapshot and put, each recovered by running the command again. Measured
over five reference runs on real clocks, active time stood at 0.38 to 0.45 of elapsed
and never above it, so no tolerance is set for the ending check's first finding. A
second reference, the throttled run whose every dispatch is answered by a throttle
until the re-dispatch bound is exhausted and the attempt fails by infrastructure,
gives the exhaustion endings their rows, since the one completing reference had passed
over the replay's ordinal shift under an outage and the recovery's skipped delay, two
faults the external review found and unit tests then held; the reconciliation states
per call what each dispatch's intents and outcomes must be, never past the registered
maximum.

**The log fixes what happened; publication fixes what evidence can be delivered.**
Exportability never defines an attempt's ending and a reader's version never decides a
failure category: the first proposal closed a completed attempt by defect when its
export would not construct, and a reader fault touching every valid abandonment would
then have relabelled each as a failed investigation. The closing event and its
settlement commit whether or not an export can be built, with no dry run and no export
failure site, since the transition function at each append is the enforcement and a
dry run cannot see the terminal timestamp, a concurrent close or another reader. The
job builds and publishes the export immediately after closure, so a reader's fault
shows at the close and not at an evaluation days later; a construction failure is a
publication incident recorded apart from the log, and an abandonment whose export will
not construct still commits and settles. Closed without export is a visible state,
listed in the inventory with the authoritative ending, the incident and the ledger's
figures as three numbers, known consumption, retained liability and their total, since
a retained worst case is not established cost and an absent export is not zero cost. A
successor waits for its predecessor's publication as well as its closure, so missing
evidence is no route to a replacement and a storage outage delays the next attempt.
One publication record per attempt, apart from the log: pending, published or failed
with its incident, the reader's commit and the export format, the closed log's digest,
the object's identity and digest, null together exactly on a failure; published is
never changed back by a late failure handler, and a repaired export under another
reader is a new object by construction, because the key names the reader and one
closed log under one reader has one possible content. Restoring an intended
representation is a repair; a change to how attribution, parsing, counting or endings
are read is a procedure amendment whatever it is called, applied across the
measurement set, and a published export is never overwritten. Publication is
idempotent, a lost acknowledgement retried as a publication recovering the held
object's identity, and an object found uploaded with no record of success is adopted
as an unfinished publication and not another run. On the instance that adoption cannot
be a read-back, since the instance's grant under the runs prefix is one put with no
get and no list, the platform contract's statement; the writer returns a fourth
outcome, present and unverified, exactly when the create was refused as present and
the verifying read was refused by access, and the publish command adopts it only under
its own pending record naming this key and this digest, where the key can hold nothing
else, the verification being the evaluator's presence check by the one principal that
can read. Anywhere else that outcome is a failed publication. The instance's refusal
is not probed from the workstation, a workstation pass saying nothing about the
instance's role; the first live publication observes it.

**Jobs are commands over plain data with no queue, and three identities are kept
apart.** Admit, work, deliver an approval, abandon, publish, write the inventory and
set the threshold are each a function over a request type and a result type with a
command-line entry, the request from the command line, the stores from the
environment, a refusal as its message and nothing sealed in either; a later milestone
may put a queue in front of them, and the work subcommand waits for the step that
builds the first composition it could run, since a subcommand that can only refuse is
not built. No command reads the wall clock: the store stamps with the database's
clock, the worker measures monotonically and the launch identity is drawn. The launch
identity is the provenance of one launcher execution, recorded and never used for
idempotency; the request identity is held by the caller across its retries and names
the run and attempt asked for; a claim's process nonce is the third, and a repeated
work command revives no retired segment. An attempt's status is derived from the log
by the transition function and exposed as three fields, the attempt open or closed
with its ending, the segment never started, open or stopped, the approval not
requested, requested or approved; no field says a worker is alive, and the row's open
or closed value is a transactional projection of the log and no authority of its own.
A human declining a plan is the demo milestone's question and no state is added for
it. The approval command refuses a closed attempt, one with no request, one already
approved and a digest other than the logged request's, and the next work command
claims and replays to the interrupt; the abandon command fences the generation the
load shows, so a worker holding it stops at its next append, and a closed attempt
answers with the store's refusal. The entry's rules come from the registration file,
each pending value absent, and with no file the rules of a system that calls no model;
a run admitted under a table and a policy folds only under them, so the entry refuses
a publish or an inventory without the file.

**The inventory is one consistent snapshot of the store, identified by its content,
and what it proves is stated.** It is read in one transaction at repeatable read, so a
closed attempt is never paired with its figures from before settlement, and built
purely from the rows: the bound registration and the measurement scope, the ledger's
head and entries, every attempt the store holds, of every world, in and out of scope,
with its status, the log position and prefix digest it was read at, the ledger's three
figures and its publication record as observed, the refused admissions, the schema
version and the builder's commit. Identifiers, digests, kinds and integers only, no
reason text that could quote a scenario. An attempt admitted under another
registration's rules has no fold for this builder and is listed from its row with no
status and no figures, absent together and exactly then. Its identity is the digest of
its bytes, which include the snapshot's instant, so two writes of one store state are
two objects and a caller that wants one object per state writes once; a ledger
revision cannot identify it, since a segment start, an approval or a publication
changes it with no ledger entry. It is written under the world's runs prefix in a
prefix of its own, the one place the instance may put, which the evaluator already
lists and reads and the bucket keeps create-only, so the interview's grant question
closed with no platform ticket. The limit, as the report must state it: a
harness-written inventory lets a separate evaluator find implementation mistakes and
inconsistencies. It does not prove that every admission or invocation was logged, that
events describe what happened, that nothing was spent outside the ledger, or that no
attempt is missing from both the inventory and storage. Protection against a harness
that omits would need an observation the harness does not write, and the project has
none; CloudWatch counts the same tokens through another path.

**The investigator's runtime policy keeps the fault triad's meanings.** A missing
record is evidence; the first unreachable source marks that source unreachable for
the run and calls stop, facts already read standing; an unreadable leave record
degrades the run, everything downstream unknown. A malformed record propagates and
the run fails by defect, recorded with the fault, excluded from grading and counted,
because the validator certified record fidelity before any run and a degrade would
fold a defect into a legitimate unknown; production fault tolerance behind a real
HRMS is future work the benchmark does not prove, and this document says so. A
provider fault after the harness's registered re-dispatches fails the run by
infrastructure, counted apart, the SDK itself retrying nothing; a response that arrives and refuses, emits no claims or emits output the codec
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
only; the investigator's vendor principals delivered to the instance (read-only by
credential on Frappe and Jira, by code on Calendar) and the evaluator's identity are
ruled on their own. The paragraph stands as the
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
reforecast after the first ten representative runs. Every one of these dollar figures
is a placeholder and none is a target or an accepted spend: they predate the harness,
assume a larger model than development uses, are cumulative over the milestone and
not a rate per period, are carried in the registration marked unmeasured, and are
set again from real usage before the registration is frozen. The ledger's admission
threshold is staged the same way, a placeholder until the reforecast and then set
from the forecast of the whole registered workload; when that forecast does not fit,
the freeze sets a lower repeat count or decides the four conditional cells as not run,
and failing that the registration stays a draft and the
measurement does not start. The per-run caps are development values too, final ones
set from the calibration runs' usage and never from full-set results. The levers are design-level: a
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
the instance under its own principals (read-only by credential on Frappe and Jira,
bounded by reach on Calendar) required before the first live investigation. Private connectivity between the hosts (a private network, a mesh, a
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
- **Constructibility under the golden plan.** Four exhausted seeds in two hundred
  under the random construction order, one under the scarcity order it replaced, are
  refusals the present contract allows; scarcity is measured per class, and a
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
  the instance identity and the application's vendor principals, so the registry
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