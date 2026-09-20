# Report notes — Leave Impact Agent

Raw material for milestone reports and posts: decision narratives distilled at the
moment they happen, so the reports can tell the story without excavating chat logs.
Append-only, newest first. Each entry is a self-contained story with its date and the
decisions it feeds.

---

## 2026-09-19 — Fifteen traces had accepted everything, and the panel's question was whether anyone else could check that

*M1 step 16, the hand audit's close: a four-seat critique panel over the audit of the
first golden world, its findings answered the same day, the audit sealed under a
content-addressed identity, M1's exit (session 35, 2026-09-19). Feeds: the M1 milestone
report's evaluation section, on what "golden" can honestly mean and on auditing an
audit; the final report's process section, on a panel as a gate, on sealing only the
method that ran, and on an external reader as a reading engine.*

By the end of the previous session the hand audit looked finished. Thirty scenarios
had been accepted, fifteen of them traced to their evidence in a frozen ten-step shape,
and no trace had found a defect in the world. The reason to run a panel anyway was not
a suspicion that a key was wrong. It was that "we found nothing" is a weak sentence
unless someone outside the audit can check the claims it rests on, and the audit's own
prose had grown confident enough that its claims deserved an adversary. Four seats read
the checklist, the sheet, the rulings record and the summary blind to each other: one
checked every sentence of the summary against the record, one attacked the checklist
against the code and the design contracts, one hunted for what the audit had never
asked, one modelled what a released example would leak. The run cost about 795k
subagent tokens (the seat reports and synthesis are in the private stream,
`panels/2026-09-19-audit-panel/`), and every finding was reproduced on the source
before it was triaged, which is how two of the seats' claims were narrowed before they
entered any record.

**The strongest finding was about proof, not defects.** The audit's outcome check reads
an "outcome witness" the sheet renders: the generator's own assessment of every
employee, produced by the same viability and outcome functions the world was built
with. For an assign outcome that is fine, because the graded candidates in the key are
enough to show it. For the seven outcomes that say "uncovered" or "unknown", the claim
is a negative over the whole organization, nobody qualifies, or exactly one person's
missing record decides it, and the sheet gave a human no way to prove that
independently: the cited fact rows were a projection for the key, not the roster, and
the witness was the rule counting itself. The methodology-breaker seat put it plainly,
and the external reviewer who read the raw seats ranked it the one technical change to
make before sealing. The answer was a new block in the sheet, a criterion universe: for
every impact, every employee's facts of the four families the criteria read, component
memberships, skills or the record's absence, leaves and events over the need's window,
employment type, rendered from the fact base under the dated view with no call to the
viability or outcome functions (`b1e8c0e`). The seven outcomes were then recounted by
hand from that block, the criteria frozen before any person was read, and all seven
equalled the witness and the key. The recount also made a pattern visible that the
traces had only argued: the two shapes differ by exactly where the organization's two
blank skills records sit. When the eligible component contains one of them, the count
is zero viable, one unknown, twenty-seven non-viable, and the outcome is unknown; when
both blank records sit outside it, the count is zero, zero, twenty-eight, and the
outcome is uncovered. One reviewer's proposal was not taken as offered: a rendering that
labels each criterion as passed, failed or dominated would need the core rule to expose
states it does not carry, since its result holds reasons only for a non-viable verdict
and unresolved questions only for an unknown one, and the fact block gives a reader the
same visibility without touching the core. The limit is stated in the summary and in
the design record in the same words: the independence is from the rule, not from the
data, because the dated view and the fact reads are the code the rule uses.

**One design gap, and the alternative that died.** The seat attacking the checklist
found a scenario whose timezone distractor had the leaver as its far attendee, alone on
the event. In the leaver's own zone the meeting fell on the last day of their leave; in
the reference zone it fell the day after, and the key marked it a non-impact. The
modifier's docstring admitted the case, a unit test named it, the design record's
timezone ruling spoke only of a far colleague, and the trace had accepted by applying
the rule without asking the audit's founding question, whether a careful reader would
call this an impact. The organization has one far person, who is the far seat in every
timezone planting and the leaver in one of them, so the case was a matter of when, not
whether. Regenerating the world was the alternative on the table and it died on cost
against correctness: a new version, a new projection of twenty-eight calendar
creations and the whole audit redone, for a key that is right under a rule the code
already applied and the design had simply never written down. The ruling wrote it down:
leave dates are date-only HR facts read in the scenario's reference timezone for every
employee, and a person's location does not redefine the leave interval, because the HR
record carries no zone. The key stands and the scenario is that convention's test. For
future worlds the far seat will always be a colleague, and because the organization's
guarantee of one far person no longer suffices when that person is the leaver, the
guarantee grows to two far seats in the same change [BUILT 2026-09-19, session 36,
commit 33a7b69: generator version 15; the golden world stays at version 14].

**Sealing only the method that ran.** The audit's identity is the digest of a small
index that binds the record, the summary and the checklist by their digests, so the
checklist inside the seal is a claim: this is the method this audit applied. The panel
had proposed a dozen new checks. Folding all of them into the checklist and then
sealing it would have claimed checks nobody ran. The rule adopted: only checks actually
executed on this world enter the bound checklist, each marked with the scope it ran on,
and everything else goes to the public methodology's note for the next audit. Three
were executed: the required-sources line derived for the fifteen untraced scenarios,
the structured tier's class promises on its ten, and the stale owner's placement
outside the component on the four conflict scenarios; all passed. The reviewer had
suggested two index fields, the checklist applied and the checklist next; the push-back
that held was that a "next" digest is a method claim no reader can verify, so one bound
file with executed scopes is the honest shape. Two further traces the panel named for
structures the fifteen had left unexercised, a prose-only skill that makes a graded
person viable and a wrong-team meeting sitting in the impacted meeting's own slot,
both accepted, bringing the traced count to seventeen.

**No example before the first evaluation.** The leak seat's model decided the release
question. The sheet's cited entries are each cited entity's whole record, which means
they carry rows dated after the scenario's `now` that are other scenarios'
answer-changing plantings; thirteen of thirty scenarios carried one such row, and any
deadline scenario's witness is a named partition of the organization. A released
example would therefore leak the private rest unless cut at `now` and stripped of the
witness, the header's prose rollups and every cross-referencing note. The ruling: no
golden scenario is released at M1's close; the release waits for the first M2
evaluation report, so the example a reader sees is a key beside an agent's actual run
on it, and retirement before any evaluation exists would be a promise with nothing to
enforce it. The per-scenario retirement rule went into the design record now (a
released scenario keeps its place in the sealed world and the audit's provenance,
leaves the scored set of every later blinded evaluation, is named as retired in that
evaluation's manifest, carries a contamination statement), the least-leaky candidate
is recorded privately and never designated in public, and a throwaway-seed world,
never sealed or scored, will illustrate the sheet in the public tree.

**The seal, and the shape of the evidence.** With the amendments applied, the record
corrected in eleven places with dated notes and a ledger and none of them touching a
key, the index was rebuilt and the four objects were created once under the truth
bucket's create-only audit prefix, each read back and re-hashed equal, on 2026-09-19:
audit identity `93745e04fe11de480da1e785873fddb0d2f7e843e21c573f8f3beb7b87da44d1`, the
sha256 of the index object, with the object version ids kept in the private stream's
audit folder and never in the record, since the record is sealed by digest before the
upload exists (the upload mode in `16638f2`, the design record's account in `40d452b`).
The chain the milestone can state in one sentence: thirty accepted, seventeen traced,
seven recounted without the rule, three panel checks on named scopes, a four-seat
panel, the amendments, the seal. The reading-engine pattern carried the day's human
hours: an external low-context reader did the seven counts and the two traces from
packets built off the new sheet, the main chat re-verified every claim against the
sheet and the code before entry, and the reader caught one wording slip of the main
chat's own brief before it reached the record. The cost of that pattern is the
re-verification; its benefit showed on both sides of the seam in one day.

Figure: the two-shape universe count as a small table or diagram, unknown (0 viable, 1
unknown, 27 non-viable) against uncovered (0, 0, 28), with the blank record's
placement inside or outside the eligible component as the one variable.

## 2026-09-15 — The first world the models wrote took five runs, and the gate on its numbers changed the cap it was meant to confirm

*M1 step 15 of the build plan: the measurement world the step 14 design demanded before
the remaining prose classes — the qualification rows generated under the real
pipeline, sealed, projected, approved — and then the gate that the design tied to it:
one session (session 26, 2026-09-15) reviewing every fix the five runs forced and every
item on the revisit list, one question per exchange, an external low-context reviewer's
read on each relayed by Arda, Arda's ruling on each. Feeds: the M1 milestone post; the
final report's evaluation section, on measuring a generator before trusting it and on
what a sample of three can and cannot say; and its process section, on interview mode
with an external reviewer and on letting a probe decide before the argument starts.*

The design of the day before had said, in one sentence, that no more prose classes
would be built until one world had been generated for real and its numbers read. This
entry is what that sentence bought. The world was three ticket comments, each planted
to carry one skill fact, and the pipeline that had passed every unit test refused to
produce them four dispatches in a row. Each failure was on a mechanism the unit level
could not see, and each was decided in minutes by the same move: one writer call, one
checker call, the raw tool input printed, and the shape of the fault visible before
anyone argued about it.

**Four runs, four faults, one probe each.** The first run (34802507979) made twelve
writer calls and never reached the checker: the namespace scanner demanded the
author's own name in the body, and a person writing a comment says "I", never "Ines
Yilmaz", so every draft died on a lexical anchor for a name the text could not
naturally contain (fix in `a011245`). The second run (34802945370) made one writer
call and then spent the checker's whole retry budget on one text: the checker had
written the ownership relation backwards, the person owning the ticket instead of the
ticket owned by the person, the value spec refused the wrong type, and the code
treated that as the checker's protocol failing, retried three times at temperature
zero, got the same reading three times, and aborted the stage (fix in `adacec1`). The
third run (34803388159, twelve writer and twelve checker calls) reached
the checker every time and was refused every time: told not to name herself, the
writer padded each comment with "I can take this on", the checker read the offer as
ownership, and ownership was outside the brief. The fourth fault never made a run;
a local probe between runs found the writer, now forbidden to offer, padding with
readiness instead ("I'm ready to dig into this"), which the checker read as hedged
ownership and as an availability claim no predicate can express. Both were fixed in
one commit (`8e17a65`): the ticket-comment register now asks for a remark about the
work as it stands, in the past or present tense, never an offer, plan, request or
promise; the brief allows the author's own ticket and its component as true context;
a reversed entity pair is put the registry's way round when the ids and their kinds
prove the swap. The fifth dispatch (34803999468) passed: the hardest comment on its third attempt,
the other two on their first. Two more refusals then came from outside the prose
stage, a calendar quota and a Frappe site that already held a world, and are the
previous session's story (`dc1a7a9`).

**The numbers, recovered from the wrong place.** The stage's counters were printed
only after sealing returned, and the passing run sealed and then died in the calendar
loop, so the tokens and latencies died with it. Bedrock's CloudWatch metrics carried
them, per model at one-minute resolution, attributed to each run by its time window,
and the hour's sums reconciled exactly (`probes/FINDINGS.md`, the measurement-world
entry). The passing run was five writer calls and five checker calls for three
comments: about 640 tokens in and 27 out per writer call at 0.8 s, about 1,490 in and
104 out per checker call at 1.0 s, about $0.015 by Cost Explorer's share; the whole
night of 71 calls cost $0.093. The counters now print before sealing and seal into the
record (`1256d37`), so the next world's numbers travel with it.

**The gate, and where the reviewer moved the answer.** Six questions were put in
order, each with the evidence beside it, and on four of them the reviewer's relayed
read either matched the recommendation or sharpened its wording. The first-person
exemption was adopted but stated narrowly, as the target supplying the subject of a
first-person statement rather than as a general relaxation of subject anchoring, and
the docstring now says the drop is positional and names the convention it relies on.
The untyped rule and the canonical pair were adopted with two honest residuals: the
swap's no-guess branch has no live predicate, since none pairs equal subject and value
kinds, and retrying a temperature-zero checker on a protocol failure can only help
against provider-side variation, which run 2 demonstrated by spending three retries on
an identical answer. The prohibition on offers was adopted and credited for the pass,
with a distinction the reviewer insisted on: an offer is a coverage signal the
qualification class does not own, so forbidding it is containment expressed upstream;
the allowed ownership fact is legitimate context because it is true, and it holds only
where it is true; but a text that passed because the checker read "something I can
work through" as hedged ownership is not a success of the allowance, it is a checker
residual.

Two rulings went further than Claude's recommendation because the reviewer pushed.
The hedge tolerance from the fourth fix, which let a hedged mention of allowed context
pass, had been justified in code as "nothing rests on it". Claude identified the
condition under which that is true, that the allowed fact is established by a
structured record the agent under test reads directly, and recommended recording the
condition and enforcing it at the next class. The reviewer's answer was that knowingly
introducing a rule that becomes unsafe as soon as the next class lands is the wrong
order: encode the invariant now, let the next class test the boundary. It was encoded
the same hour, in a different place than proposed. A brief's construction now refuses
an allowed fact evidenced by the brief's own target, since a fact this text evidences
is one the text must carry, and the guard tolerates a hedge on allowed context only
when a structured record establishes the fact, refusing a hedge on a fact that only
other prose establishes as a softened conflict the world never planted. The other
push was on the cap. The baton had framed the cap of four as confirmed by a maximum of
three attempts observed. Claude's arithmetic said otherwise: attempts are fresh
samples, so a brief that passes one attempt in three exhausts a cap of four about one
time in five, and five such briefs in a world fail the generation about two runs in
three; at a cap of eight the same figures are about one in twenty-five and one in
five [PRELIMINARY — a per-attempt rate read from one target's three-attempt pass, a
point estimate that supports no prediction]. The reviewer agreed the inference from
the maximum was unsound, agreed eight should be the default rather than a golden-run
knob, and added what Claude had left out: the earlier entry in these notes had called
four a diagnostic cap that assumes a good prompt, and raising it should not abandon
that. So attempts above four are now read as a struggling brief, from the sealed
attempt count and with no new field, and the cost of an exhausted run is stated
plainly as a re-dispatch of sealing before any vendor write. (The design document
itself had recorded only that the cap would be revisited; the diagnostic reason lived
in these notes, and the record now says which is which.)

**What was refused, and why the worst run argued for it.** Feeding a refusal back into
the writer's next attempt was rejected for this milestone, and the strongest argument
against it was the run that most seemed to call for it. Run 3's twelve refusals of
twelve exposed a wrong register prompt, fixed once for every future world; with
feedback, the same defect would have looked like one refusal followed by a corrected
pass, and the prompt would still be wrong. Attempts stay identical writer requests, so
retry depth remains a measure of one fixed configuration's difficulty, and if feedback
is ever introduced it will be a new strategy with its own digest and attempts marked
base or corrected.

**The record learns to say why.** The gate could not answer two of its own questions:
what the two refused drafts of the hardest comment had been refused for, and how often
the checker produced claims no predicate expresses. Refused text is discarded by
design, because the repository's job logs are public, and a refusal was sealed as a
guard name and a count. The ruling adopts a closed vocabulary of reasons on each sealed
refusal, seven names and no content, plus one run-level counter for pairs the checker
wrote backwards and the code put right, which is a normalization and not a refusal.
The reviewer's caveat is the honest one: a reason says which check refused, not whether
the writer or the checker was at fault, and only the hand audit separates a checker
misreading a clean text from a checker reasonably failing on a confused one. Records
sealed before the change will decode with the reasons unavailable, never as zero. The
three-character exact-spelling cut in the scanner was kept as a heuristic without
contrary evidence, the world having exercised only the path it was designed for, and
one wording was corrected on the way: a miss there is of a foreign surface mention,
which the checker still catches when the mention makes a claim; only a mention that
makes no claim has the scanner as its sole layer.

**A sample of three.** Arda read the three accepted texts against their sealed
propositions. Two say exactly the skill they were planted to carry and nothing else,
and the checker read them exactly. The third, "I've got experience with Go, so the
retry queue migration is something I can work through", was read as the skill, which
is right, and as hedged ownership of the ticket, which the sentence never says; the
only ownership cue in the checker's request is the opening line naming the ticket
beside the author, which is the hypothesis, on one sample, for where the proposition
came from. It passed harmlessly because ownership is on the ticket's own field, which
is precisely the condition the hedge tolerance now enforces. Three of three required
facts read correctly and one of three texts over-read is what the sample says, and a
sample of three supports no rate. What it also shows, and what the golden world's
audit will look for, is that all three texts share one sentence frame at temperature
0.7: "I've worked with X before, so ...". A benchmark whose qualification comments all
sound alike is a shape an agent could learn. Two corrections to the handoff that
started the session belong here so the next reader does not repeat them: the comment
bodies live in the benchmark-private world spec, not in the scenario specs, and the
pair canonicalization landed in the fourth fix's commit, not the second's.

Figure: the four-run table of writer and checker calls (12/0, 1/4, 12/12, 5/5) as a
before-and-after bar, one bar pair per fault.

## 2026-09-14 — Prose entered the world through a gate, and the gate was rebuilt five times before any model wrote a word

*M1 step 14 of the build plan: the design interview of session 23 (ten questions, an
external reviewer's read on each, Arda's ruling on each), then five commits — the
semantic world and composition, the artifacts, the Bedrock seam, the materializer, the
wiring — each reviewed after its push, with the review fixes as their own commits
(2026-09-14). Feeds: the M1 milestone post; the final report's evaluation section under
"ground truth by construction" — how model-written text joins a benchmark whose answer
key is fixed before the model is paid; the architecture section on the two identities
of a world; and the process section on reviewing a design against a low-context
reader.*

Until this step every byte of a world was a function of its seed. The moment a
language model writes a runbook paragraph, that stops being true, and the whole step is
the consequence of one sentence in the founding design: the seed identifies the
semantic specification, the frozen bundle identifies the realized world, and the two are
not the same thing. Everything else followed from taking that sentence literally.

**Ten questions, one reviewer, one ruler.** The step opened with a design interview,
one question per exchange, and Arda relayed each proposal to a second chat with almost
no context and brought its verdict back. That reviewer's closing "my ruling" was, by
Arda's own instruction that morning, the reviewer's verdict and never his; the ruling
stayed with him. The shape that came out: the pure assembly no longer produces a world
but a *semantic world*, complete in every structured record and holding, where a model
must write, a typed pending target instead of text — a brief that says which comment or
section, under which parent, at which position, carrying which facts, in which
register. A pure `compose` places the accepted text afterward. Two identities are
recorded: a semantic digest, the hash of everything the seed determines, which two runs
from one seed share whatever prose they accept, and the world version, the hash of the
realized bundle, which they do not. The reviewer's sharpest early contribution was to
move the regression oracle: the suite had pinned a reference seed's world version, and
that pin could not survive non-deterministic prose, so the pair became generator
version plus reference semantic digest, and the realized version became provenance no
test expects to reproduce. Two of Claude's own additions were adopted the same way: a
required fact's role — answer-changing or context — is derived by running the rules
once with the fact removed rather than tagged by the class author, because the hand
audit at step 16 reads every artifact carrying an answer-changing fact and a wrong tag
would misdirect it silently; and the surface namespace a text may use is derived from
the brief's facts through the closed vocabulary, so a class cannot forget a name or
leak one.

The rest of the interview fixed the machinery the reviewer and Claude then mostly agreed
on. The record of how each text was accepted seals with the world and is part of its
identity; rejected text exists nowhere, not even in the job log, because the repository
is public and its Actions logs are world-readable, so a quoted rejected sentence would
be a third benchmark-private surface with no access policy. A restart before sealing
regenerates; after sealing it resumes a version the operator names, proven six ways,
and auto-discovering an unfinished version by listing the mutable prefix was rejected
as guessing. Four guards run in order, the paid one last: a namespace scanner, a
lexical required-fact check, an extraction by a second model family that never sees the
brief's facts and returns propositions with polarity and an assertion mode — the text's
modality, never the checker's confidence, so "Deniz might know Kafka" is affirmed and
hedged whatever the checker believes — and the human pass. Containment is the required
statements contained in the affirmed, asserted ones, and those contained in the
required plus the allowed; anything negated, hedged, about an unlisted subject, or
expressible by no predicate refuses. Attempts are fresh samples from one prompt with
nothing fed back, under a cap of four recorded in provenance, and the reviewer's
arithmetic was worth keeping: at a 70 % per-attempt pass rate that cap gives about 61 %
whole-world success over sixty targets, at 80 % about 91 %, so four is a diagnostic cap
that assumes a good prompt, to be revisited on the first world's numbers and not
before. And the one push-back taken whole: prompt policy belongs above the adapter.
The Bedrock layer sends a request it is handed and returns text or a filled tool; what
a runbook, a guard or a required fact is never reaches it.

**One check the interview missed, caught against the project's own rule.** The
interview had put the materialization record in the world spec's provenance. While
building the artifacts Claude read the record's contents against the standing storage
rule — storage follows who may know a thing — and they contradicted: the world spec is
readable by the validator's role and holds nothing truth expects, and a brief's
required facts and a checker's reading of a text are exactly what truth expects. The
record and the briefs moved to the evaluator-only truth manifest before a line of
encoder was written, on Arda's ruling. That choice had a price paid later in the
wiring: a resume needs the record to re-compose the world, and the truth manifest has
no decoder by design, so the generator got a private decoder of that one section,
unreachable by the validator under the import law — a narrower thing than "the
generator can read truth anyway".

**Five reviews, and what each moved.** The post-push review found something real each
time, and reproducing every finding before triage (the method since step 9) confirmed
all of them. On composition: nothing bound a composed body to the digest its record
claimed to have accepted, so a sealed record could describe a text the world did not
contain; `compose` now refuses a body whose digest is not its record's. On the same
types: a target record could hold impossible histories — four attempts and no
refusals — and now demands exactly one refusal per failed attempt, since the first guard
that refuses ends an attempt. On the seam: the "closed fault vocabulary" was
mechanically false on the success path, because a response without usage silently
became zero tokens and a malformed count leaked a raw `ValueError`; usage is now read
strictly and any defect is the seam's own protocol fault. On the materializer: the
scanner had left a foreign world name in another case to the extraction check, which
deliberately ignores mentions that make no claim — "thanks selin" would have passed
every guard while naming an identity the brief did not admit. The fix was a ruling on
an asymmetry: a false refusal costs one attempt, a missed identity costs the benchmark,
so every world name is refused in any case, employees by given name as well as full
name, with one exception for forms of three characters or fewer matched in exact
spelling, because "go" is in most sentences and the skill Go would otherwise refuse
them all. The reviewer then found the two-pass version of that scanner still wrong —
an allowed short form masked first erased the longer foreign form it sat inside, "Deniz"
hiding "Deniz Kowalski" — and one global longest-first pass over allowed and foreign
forms together replaced it. On the wiring: the job printed the world version before
sealing as the operator's resume handle, but stdout under the workflow's pipe is
block-buffered, so a hard kill mid-sealing could lose the one line the recovery
protocol depends on; the line is flushed now, and the wording "before the first side
effect" became "before the first persistent world or vendor mutation", since the paid
model calls precede it and create no resumable state. And the probe workflow could exit
green while its own diagnostic line said the tool was not filled; its exit now depends on
that condition.

**What is verified live, and what is not.** Both models answered from the workstation
under the administrator profile — the two structural live tests, under four seconds
for the pair — and the manual probe workflow was green under the generator role on
2026-09-14, so the production principal holds its invoke grant and the forced tool
choice `any` over a single tool is honoured by both families on the shortlist, which
had been a documented assumption until then. A side finding worth its line: the
test suite's network guard matches the resolved IP a socket connects to, not the
hostname, so an endpoint cannot be allow-listed by name and the live level now runs
without the block, which is what "live" means. The suite grew from 1677 to 1754 tests
across the step (the pytest runs of session 23), 77 of them the gate's own.

[PRELIMINARY — no prose has been materialized for a real world yet. Tier 1 has no
briefs; the first Tier 2 world at step 15 gives the first-attempt pass rate, the
refusal distribution by guard and the cost per world that the design predicts (DESIGN
estimates well under a dollar per world at thirty scenarios; the per-token prices are in
the Bedrock probe of 2026-08-26, `probes/captures/bedrock/models.md`). The cap of
four, the other-claims bucket and the absence of refusal feedback are all to be judged
on those numbers and on nothing else.]

Figure: the pipeline as one diagram — semantic world → materialize → compose → freeze
the two identities → print the resume handle → seal — with the resume path rejoining at
the seal after its proofs; the two identities labelled where they are born.

## 2026-09-13 — The validator earned its keep on the first world: two boundary faults, no world fault

*M1 step 13 of the build plan, the first world live: the `generate world` workflow run
34780738512 (attempt 1 red, attempt 2 green), the validator runs 34784309718 (refused)
and 34785009950 (approved), the reader fix `c9823a7`, the platform's Bot Fight Mode
ruling in its commit `b894ac6` (session 22, 2026-09-13/14). Feeds: the M1 milestone
post; the final report's evaluation section under "ground truth by construction" —
what an independent re-read of the live systems is worth, shown on the day it caught
something; and the operations section on the edge, where the first cloud-network client
of a proxied hostname met the free plan's bot heuristic at the exact moment of the
first real run.*

The first world took two attempts to generate and two to validate, and neither fault
was in the world. Both were boundaries: an edge heuristic turned against the project's
own clients, and a vendor's read order leaking into a field the design had declared
canonical. The second one is the reason the validator exists, and it found it on the
first world it ever read.

**The edge that had never met a machine.** The generator's first attempt sealed the
truth artifacts, the world spec and the truth manifest of version `d674d576…`, at 20:26
UTC, then made its first call to the Frappe site and got a 403 whose body was
Cloudflare's "Just a moment…" page, with `cf-mitigated: challenge` in the headers.
Frappe never saw the request. The sealing order had paid off in the smallest way
possible: truth first, so a truth-only orphan and nothing else. Pinning the cause took
one table with three rows: the GitHub-hosted runner, 403; the AWS application instance,
403 with curl's own user agent and with the httpx one alike; the workstation, 200 with
both. So the discriminator was the network, not the client. Cloud address space is
what the zone's free-plan Bot Fight Mode scores as automated, and it challenges on the
first request. Cloudflare's own documentation, checked that evening, closed the door
on a scoped fix: Bot Fight Mode runs outside the ruleset engine, so no custom rule,
page rule or skip action can exempt a request from it, and it is zone-wide only; the
first tier with an exception is Super Bot Fight Mode on the Pro plan (about $25 a
month, a figure corroborated by secondary sources rather than quoted from the docs),
and whether an Access service token would itself be challenged is stated nowhere
official.

Two things in the platform's own record made this less of a surprise and more of a
lesson. The Terraform file that imported Bot Fight Mode on 2026-08-28 carried a comment
saying it "can challenge a legitimate client (an API caller, a monitor)", and the
platform design held a trigger row for "a paid Cloudflare plan" that fired on exactly
this event. And the observation of 2026-08-30 that machine clients pass, taken as
reassurance at the time, turned out to rest on one client, the UptimeRobot monitor,
which is on Cloudflare's verified-bot list and therefore exempt by design. Every
machine client had passed because the only one that had ever knocked was a verified
bot; no unverified client from a cloud network had ever reached these hostnames
before the first real run. The ruling was taken in the platform stream the same night:
Bot Fight Mode off, the paid-plan trigger re-cut, the hollow monitor observation
corrected in the docs. Arda raised the wider frame himself, a private Cloudflare Tunnel
network between the AWS host and the netcup box with no inbound port on either side;
that closes the M2 path, the agent on the instance talking to Frappe, but not the
generator's, since a GitHub runner sits in neither network and has no fixed address.
It lands as the platform's service-to-service connectivity step at M2 entry, with a
five-minute probe on the service-token question the docs leave open.

> ⚠ REVISED by the M2-entry design session, 2026-09-20 — private connectivity moved to the
> demo milestone's entry or observed abuse; Cloudflare Access with a service token lands
> within M2 instead, since it gives the token-gated property without a tunnel (DESIGN's
> hosting section, the platform's Access ticket).

**The rerun that wrote nothing.** Attempt 2, same run id, went green in 375.6 seconds
(the entry point's `run_seconds` line). The truth objects kept attempt 1's timestamps:
the reassembled bytes were identical and both conditional puts landed in the equal
case, the content-addressed restart proven live on its first try. The checkpoint
numbers the design had deferred to this step came out of the same log: 106 checkpoint
writes, p50 0.295 s and p95 0.623 s per write, 40.0 s in total, 491,265 bytes, 10.7 %
of the run. That is the cost of the one-write crash window kept from step 10, and it is
small enough that the cadence stays at one checkpoint per record. On the sites: 28
employees, 12 leave applications and 18 departments in the Frappe company
`World WD674D5763`, 9 issues in the Jira project of the same name, no documents because
no Tier 1 class plants one (counts read back over the vendor APIs after the run).

**Eighteen mismatches, all in one field.** The validator refused the world (run
34784309718, verdict `worlds/<v>/verdicts/34784309718-1.json`). Every exactness kind
passed, every scenario view passed, six of seven fidelity kinds passed; the seventh,
employee fidelity, listed 18 of 28 employees differing in `skills` and nothing else.
The live rows told the story at once: for employee 002 the sealed skills were `airflow,
go, redis, spark` and Frappe returned `redis, spark, go, airflow`, with row indexes 3,
4, 2, 1. The projector had written the sorted order faithfully and the stored record
still held it; what Frappe leaves unspecified is the order in which a list call over a
child table returns its join. The reader kept whatever order came back, the sealed
employee holds a lexically sorted tuple (the construction's own `tuple(sorted(...))`),
and the fidelity check is field equality, so any reordering was a mismatch. The
pattern fit exactly: all sixteen employees with three or more skills failed, and two of
the five with exactly two did, as the join order happened to fall. The cassette tests
could not have caught this, structurally: a recorded response has one order. The world
was right and the observation boundary was wrong, which is the failure mode an
independent re-read is built to expose, and the design's phrase for it held: validate
the projected systems, not the generator's intermediate objects, so a bug in the
shared reading code cannot produce an evaluation that agrees with a wrong world.

**Where to fix it, and what not to schedule.** The first proposal was to sort at the
reader and to note a `frozenset` as the type-honest eventual form for the field. The
external reviewer, reading the proposal relayed by Arda, pushed back on the second
half and was right: a frozenset gives order-independent equality but every
serialization boundary then has to impose an order again, so it moves the
canonicalization rather than removing it, and for a system that cares about
deterministic bytes and snapshot equality a sorted, duplicate-free tuple is a
legitimate domain carrier, not a compromise. The bug was narrower than the type: the
sealed construction produced the canonical tuple, the vendor stored the rows, and only
the reader let the vendor's order through. Fix the reader boundary, keep the
representation, and record no refactor debt that no consumer has asked for. One more
ruling came with it, on duplicates: if Frappe ever returned the same skill twice for
one employee, sorting must not quietly yield `python, python, sql`, and a
`sorted(set(...))` must not quietly hide it either. Different ordering is normalized;
duplicate membership fails loud, which is the reviewer's own invariant from
2026-09-12, one semantic identity has exactly one vendor representation per place.
Commit `c9823a7` did exactly that: the reader returns the sorted tuple, a skill listed
twice is a `MalformedRecord` naming the employee, and the doctests carry a reversed
example and a duplicated one. No cassette was re-recorded, because no request or
payload changed. Nothing was regenerated and nothing reprojected: same sealed world,
same vendor state, a corrected reader.

**Approved, with the first verdict kept beside it.** The revalidation (run 34785009950,
1 minute 38 seconds) approved the world: every check passed, and the verdict's manifest
digest equals the live world manifest's (`92576aa3…`), which is the serving rule's
condition met for the first time. The refused verdict stays under its own run key
next to the approved one; a refusal is evidence, and the pair is the record of what the
validator caught. That is half of M1's exit, the first world live with its golden set
beside it.

Two things are still claims rather than evidence, and are recorded as such. The
validator role's denial on the real `truth-manifest/<version>.json` key is not yet
demonstrated (the canary proves no bucket-wide read; an IAM policy simulation attempted
this session was inconclusive and is not counted). And the `benchmark` environment
refusing a wrong subject was ruled not worth a demonstration, since the trust policy
was read back on 2026-09-12 and a negative demo would cost a trust edit to prove what
the read-back shows.

Figure: the three-network table (GitHub runner 403, AWS instance 403, workstation 200)
as the one picture of the edge fault. Figure: the two verdicts side by side, 18
employee mismatches in one field, then zero, same world version and same manifest
digest.

## 2026-09-13 — Four times the claim was stronger than the mechanism: how step 12 turned every boundary sentence into a check

*M1 step 12 of the build plan, the generator's entry point and the sealing of a world
into the two buckets: nine design rulings first, one question per exchange with the
external reviewer answering each cold (session 21, 2026-09-13), then six builds each
pushed and reviewed — the object store (`26ae48d`, reviews `73617d2`, `5c47f8f` and the
checksum fix), the key layout and the sealed documents (`48b7584`), the sealing sequence
(`272b033`), the generator's entry point (`4020df7`), the shared wiring and the
validator's entry point (`531a440`), the deploy-time probe (`ff9038d`); the unit suite
went from 1622 to 1673 tests across the step (the suite runs of the session). Feeds: the
M1 report's sealing and boundary section — what "sealed" is enforced by, layer by
layer: the bucket policy, IAM, the import law, the probe on the host — and the
methodology section on external review, whose pattern this step shows four times over:
a claim, a reviewer reading it literally, and a probe or a law rule that makes it true.*

The step's story is not any one of its rulings. It is that four times a sentence in the
design or the code claimed a boundary stronger than the mechanism under it, and four
times the correction was a structural check rather than a stronger sentence. The
external reviewer found all four, reading the text literally and asking what actually
enforced it; the project's answer each time was to make the enforcement something that
runs.

**The seal that was a promise.** The founding design had the generator "run from the
instance under a short-lived role the application process never holds", a role assumed
through STS from the instance profile. On 2026-09-12, while the platform ask for the
buckets and roles was being ruled, the reviewer pointed at what that sentence really
said: an EC2 instance profile is one role, and a role that role may assume is a role
the application process can obtain, because the application runs under the same
profile. The distinction was between processes, not between principals, and the
answer key's secrecy rested on discipline. The ruling that replaced it moved the
privileged jobs off the instance entirely: the generator and the validator are
`workflow_dispatch` jobs under one GitHub environment, `benchmark`, reviewer-gated and
`main`-only, each assuming its own OIDC-trusted role through the web-identity
exchange, and the instance role assumes nothing. The platform stream built and applied
it the same evening (its commit `529c998`), and the trust was proven by a throwaway
workflow run rather than by policy text (run 34719626730 in this repository's
findings): both roles assumed, the generator's two models answering under it, the
validator refused on the truth bucket. One reviewer suggestion was pushed back and
held — two environments to split generator from validator structurally — because the
threat it closes is the project's own committed workflow code under a gate the owner
approves by hand, and the cost would have been every vendor secret duplicated.

**The probe that proved less than it said.** The refusal check that closed the platform
ask made two calls under the validator role: a list of the truth bucket, refused, and a
get of a truth key, refused, "two calls, because a missing key reads as AccessDenied
only while list is also denied". At the step 12 interview the reviewer read that
sentence the other way round, which is the right way: S3 answers a get of an absent
key with AccessDenied precisely when list is denied, so that a caller cannot learn
whether the key exists — whatever the get permission says. The truth bucket had been
empty when the probe ran. The get had proven nothing about GetObject; the list denial
made it ambiguous, not meaningful. The project's own record carried the backwards
reasoning in two places, the session log and the findings, and both received a dated
correction rather than a rewrite. The fix needed a key known to exist: the platform
stream added a canary object at `access-probe/read-denied-canary` (its commit
`57ec6df`), placed outside the create-only prefixes because Terraform's S3 object
resource cannot send the conditional-create header the bucket policy demands there —
which means, for the validator, the canary proves no bucket-wide read and the
`truth-manifest/` denial itself is proven against a real key once a world exists.
For the application the canary is the meaningful get, and it is taken on every deploy:
a probe script runs on the host, in the same SSM command as the deploy, under the real
instance profile — the identity asserted first, a list of the world bucket's `worlds/`
succeeding as the positive control, then the truth list and the canary get both
refused with the `AccessDenied` code specifically, anything else turning the deploy
run red with no rollback, since a broken boundary is the platform's fault and not an
image's. Its first live run was the deploy of its own commit (CI run 34729636594 on
`ff9038d`): identity `assumed-role/leave-agent-instance`, positive control passed,
both refusals with the pinned code.

**Truth first, except in production.** The sealing sequence was written to the order
the interview had ruled: the two truth objects sealed by conditional create before any
vendor call, so that live vendor state never exists without its answer key, while
truth-only orphans are harmless because nothing serves without a manifest. The code
did that, and the unit test proved it — and the reviewer noticed that the function
took a `Prepared` record as an argument, and that in production the only way to
obtain one is the site preparation, which creates the Frappe company and the Jira
project before it returns. The test had manufactured `Prepared` directly and so
observed the first vendor call one stage too late; "before any vendor call" was true
of the composition root's calls and false of the run's. Sealing now owns the call to
prepare, through an outer seam that is the root's interleaved protocol plus that one
call, and the test's fake records the truth bucket's contents inside prepare itself.
Two smaller hardenings landed with it: the sequence reassembles the bundle from the
world it is handed and refuses before any write when they differ, and every
world-content encoding, the documents' included, is computed before the first write,
so the frozen-bytes sentence is literally true — the final manifest being the one
deliberate exception, derived afterwards from those fixed bytes and the version ids
observed on read-back, since a commit record cannot precede the receipts it records
(the closing review's precision).

**The write boundary, porous twice.** The object store was designed as two protocols
in two modules, the writer's gated by the import law to the adapters and the
generator, so that a validator which cannot name the writer cannot call it. The
reviewer's reading of the first commit: the concrete store class implemented both
protocols and lived in a module the validator could import, so the validator could
name the class and call its write methods without ever naming the gated module. The
fix split every backend into a reader class with no write method on it at runtime and
a gated writer subclass, and the law gained the concrete writer modules and a rule
that no package `__init__` may name a gated module. Four commits later the shared
read wiring, built so the generator and the validator construct the same readers from
the same manifest, imported the writer classes at module scope to build the verdict
publisher — and `from leaveimpact.adapters.wiring import S3ObjectWriter` worked. The
reviewer caught that one too. The imports moved inside the publisher function, and
the law gained the rule that makes the fix a property: within the adapters package,
only a gated module may name an object-store writer at module scope, since a
module-scope import makes the class an attribute of any module a shell may import.
Both rules were proven by negative probes, a module that should fail the law made to
fail it. The verdict itself crosses the wiring as one callable that seals exactly one
key computed from the version and the run's identifiers, the writer closed over and
never exposed; the validator package names no writer and chooses no key. The honest
limit is written into the design with it: the law is not a sandbox, it makes an
accidental violation fail CI, and IAM remains the runtime boundary.

Three things ride beside the four arcs. The object store's SDK mapping was observed
before it was written, by a throwaway workflow under the generator role (run
34724172889, commit `e499060`): the 412 on a present key is a `PreconditionFailed`
whatever the bytes, so equality is the store's own read-back; the 403 under a final
prefix arrives as a modelled `AccessDenied`; and, as a side observation, a plain
dispatched workflow's token carries `job_workflow_ref` naming its own file, which
disproved the reviewer's docs-based reading that the claim is reusable-only and put
the per-workflow trust binding on the platform's list as a later option. The store's
fault vocabulary was closed at three classes after the reviewer's own finding that a
broad SDK-error fallback had made local defects look transient: "unreachable" is now
an allowlist of the SDK's transport branches, everything else is misconfiguration, and
the one exception class the SDK raises both for a bad request and for a corrupted
response body is classified at the body read, where its location decides its meaning.
And the documents left PostgreSQL: they seal into the world bucket as canonical
objects, one per document, after the vendor postflight so a refused site leaves
nothing under a prefix no job can delete from, and the application's corpus becomes
a cache the instance fills under the serving rule, with an atomic ready mark so a
half-loaded world is never queryable.

What the M1 report should take from the step is the layering rather than the count.
"Sealed" is enforced by the bucket policy (conditional create on the final prefixes,
no delete grant), by IAM (two OIDC roles, an instance role that assumes nothing), by
the import law (gated writer modules, reader classes without write methods, no
module-scope laundering), and by the probe on the host that turns the application's
refusal into a line in every deploy's log. Each layer exists because a sentence
claiming it was found insufficient by someone reading the sentence literally.

Figure: a four-row table — the claim as first written, the mechanism that was missing,
and what made it structural (OIDC jobs and the trust probe; the canary and the deploy
probe; sealing owning the site preparation; the two law rules with their negative
probes).

## 2026-09-12 — The checker that borrowed the answer key's calendar: how the validator exposed a world-side gap by exposing it in itself first

*M1 step 11 of the build plan, the independent validator: the sealed artifacts redrawn
and decoded (`5c8d765`, reviews `9971acc` and `482d104`), the byte-level file store
(`b5eebf7`, review `fb67e44`), the three checks (`6b225d5`, reviews `8b05e5f` in
`world` and `0aa2345` in the validator), the verdict and the composition (`69a0b71`,
review `8823526`), all 2026-09-12; the unit suite went from 1546 to 1599 tests across
the step, the composition tests driving the real projectors into in-memory ports and
then judging what landed (the `just check` runs of the session). Feeds: the M1
report's validation section — what "approved" claims, which layer proves what, and
the chain from live systems to sealed truth that the validator completes without ever
reading a key — and the M2 harness constraint the step produced: the harness observes
everything the reads return, dated to the run's day.*

The validator is the layer built to give independent evidence: it re-reads the four
live systems and proves they hold exactly the declared world, so that a bug shared
between generation and projection cannot yield an evaluation that agrees with a wrong
world. The step's story is that the first cut of that layer was itself the shared bug.
It passed for the wrong reason, the external reviewer saw why, and the correction ran
one layer down into the world generator, where it belonged all along.

**Four rulings, and the file that could not feed its reader.** Like the projection
step, this one was designed before it was coded, one ruling per exchange with the
external reviewer answering each cold. The first exchange did not get to its question.
The validator runs under a role that reads one prefix of the truth bucket, the sealed
world spec, and never the truth manifest with its answer keys; but the world spec as
sealed at step 8 held the organisation, the plan, the slices and the provenance, and
nothing of what each scenario had planted. The plantings and each scenario's stable
interval lived inside the truth manifest's construction records. Step 10's projectors
had never noticed, because they read the assembled world in memory, not the bytes. A
validator reading the spec from bytes could not know what was supposed to be there.
Three ways out were on the table: extend the spec, let the validator regenerate the
world from its provenance and check the digests, or widen the role to both prefixes.
Regeneration would have put the truth in the validator's memory and made "never reads
the truth" a discipline instead of a boundary, and would have tied the validator's
verdict to interpreter drift that has nothing to do with the live systems; the wider
role breaks the access ruling. The spec was extended, with one home per fact: the
plantings with their observable-from dates and the stable intervals moved into the
world spec, the truth manifest narrowed to keys and authored facts, the serialized key
deliberately narrower than the in-memory construction record, the generator version
bumped to 4 and the reference world's snapshot re-cut (`5c8d765`). The reviewer's
framing of the two files is the one the code now documents: the world spec is what
was supposed to be projected, the truth manifest is what those plantings are expected
to imply.

The remaining rulings held with two push-backs. The validator's claim decomposed into
three layers: identity exactness per closed enumeration, missing and foreign both
named; record fidelity, each record read back equal to its planting; and the derived
view of a run, the facts a scenario's reads yield compared with the facts the
plantings yield. The reviewer proposed "projection equivalence" for the second layer,
equality after vendor normalization, and I pushed back with the projector's own
docstring: the adapters' round trips are proven exact for every generator-controlled
field, so naming a looser equivalence would admit a looseness the record says does not
exist; plain equality stayed. The reviewer also wanted exactness for calendar events
over the whole of each world-exclusive calendar rather than the world's time horizon;
the read port offers events by window only, on purpose, since the investigator never
enumerates a calendar, so the scope became the horizon, one bounding interval over
every scenario window so a foreign event in a gap between windows fails rather than
hides, and debris outside every window went to the fix log as the composition root's
hygiene concern. The decoders became a codec over one value: `PlantedWorldSpec` is
exactly the file's content, a pure function projects the assembled world onto it, the
encoder takes it, and three claims are proven separately (the projection equals the
expected value, decoding an encoding yields the value, encoding a decoding of the
sealed bytes yields the bytes). The verdict became its own artifact, never a stage on
the manifest, approved exactly when every check passed, carrying the validator's
version and the SHA-256 of the manifest bytes it judged. That last field was my
addition to the reviewer's shape, for a reason worth keeping: the world version and
the artifact digests identify the world, not the projection, and a re-projection of
the same world onto other sites changes every receipt and the calendar map while
leaving all of those digests untouched, so only the manifest's own digest ties a
verdict to what it judged. The file store the manifest used moved out of the
generator into the adapters package as a primitive over bytes and a path, knowing no
record type, so the generator's manifest and the validator's verdict share it without
either importing the other.

**The checker that borrowed the calendar.** The third part landed the checks
(`6b225d5`) and the reviewer's finding on it was the step's turn. A live record knows
nothing of when the synthetic world "made it observable"; the entity types keep vendor
timestamps out by design. My view layer therefore looked up each live record's
planting date in the sealed spec by identity, stamped its facts with that date, and
compared the result at two instants inside the stable interval with the truth's dated
view. It passed. The reviewer's point was that the investigator will never possess
those dates. The runtime rule already written in the derivation module says what a
live harness does: it stamps every returned record with the run's day. Nothing the
investigator reads is hidden by date. Leaves and events are narrowed by window, so
other slices' plantings stay out of a run, but the work-item read enumerates the whole
Jira project, so every scenario's tickets are visible in every run. The validator had
produced a cleaner historical view than the runtime can obtain, borrowing
benchmark-private chronology to do it, and so would have hidden exactly the mismatch
it exists to expose.

Before ruling, I probed the reference world for the two facts that decided the size
of the problem. No planting in any of the ten scenarios is observable only after its
scenario's `now`. And when every planted fact of every scenario is made visible at
each scenario's today, the way the live systems actually present the world, not one
verdict changes (a scratch probe over seed 7, 2026-09-12, before the world commit
`8b05e5f`). The reviewer had opened a larger question, whether the runtime needed some
mechanism to make the synthetic observability real, and the probe closed it: the
runtime rule exists and is fine, the validator had simply used the wrong rule. What
the probe also showed is the gap one layer down. The pre-seal verification proved each
key under the truth's dated view, which hides later plantings; the live systems hide
nothing; so the keys were realizable only if they also held under the all-visible
view. They did, but nothing asserted it, and a future scenario class whose key depended
on a future planting staying hidden would have sealed cleanly and failed live.

Three rulings followed, adopted as written with one refinement each from the
reviewer. The live side of the validator uses only the runtime rule; planting dates
leave the validator entirely, and the helper that had made them available went with
them so nothing tempts a later hand. The expected side is the record set the runtime
ports would return, stated once in a new module of the world package: the
organisation whole, every scenario's work items, the leaves and events overlapping the
scenario's window under the ports' own overlap rules, every fact dated to the run day.
The whole-world re-verification at assembly now runs every stable day of every
scenario twice, under the dated truth and under that runtime view, and refuses a world
whose key holds only while a later or foreign planting stays hidden. The test that
pins it is the case the dated view cannot see: scenario 2 plants a leave for scenario
1's viable cover over scenario 1's leave, dated after scenario 1's window; the dated
view stays clean on every stable day, a run's windowed read returns the leave, the
cover is away, and the finding names the cover under the runtime view (`8b05e5f`).
The reviewer's refinement on this ruling was the wording: not "every planted fact
visible", since leaves and events are still window-filtered at the wire, but "the
complete record set the runtime ports would return, with no benchmark-only
observable-from filtering". The refinement on the validator's side was a condition:
the two-instant check could go only if the read requests themselves do not move with
the candidate `now`. They do not; the window is a field of the scenario spec, a run
input fixed per scenario, and the run context carries `now` and no window. So the
two-instant check that had stood in the design since the scenario framework was
dropped, with its reason recorded where someone might otherwise restore it: under the
runtime rule a run's view does not change inside the stable interval, and a second
read proves nothing the first did not (`0aa2345`). The interval is the evaluator's, a
run anywhere in it grading against one key.

The division that came out is the one the report should state, because it is cleaner
than what either of us had at the start of the step: the generator proves the world is
realizable through the runtime rule, the validator proves the realized systems match
that realizable world, and the evaluator grades with the stable interval and the key.
The validator's chain is complete for the structured tier: live systems realize the
sealed spec, the sealed spec implies the sealed truth, and the validator never reads a
key and never uses a planting date to build the live view — it reads the plantings'
dates in the spec, since the spec serializes them, and constructs the runtime view
without them (the wording sharpened at the step 12 closing review). For the
prose-carried facts of the later tiers, the ones only
a runbook or a comment can plant, the proof runs through the materializer's
containment gates and the corpus adapter's read fidelity, not through this validator;
that is a Tier 2 obligation, stated in the package docstring, not an unfinished part
of this step.

**The smaller adoptions, one line each.** The world decoders leaked a `KeyError` on an
unknown zone name and silently normalized a timestamp whose offset disagreed with its
named zone; the fix became one instant rule in core, semantic half and lexical half,
the second added when the reviewer showed that `fromisoformat` accepts spellings the
encoder never writes, so the round-trip claim now holds for every value a sealed
codec accepts, and the vendor adapters are deliberately outside it because normalizing
a vendor's spelling is their job (`9971acc`, `482d104`). The file store's rename was
atomic but not durable across a host crash without a sync of the parent directory;
the reviewer filed it as a P2 against the receipt contract, I answered with the ruled
contract, restartability after the faults the transport reports and a loud coverage
refusal for the window between a write and its checkpoint, and the reviewer
downgraded their own severity while tightening my phrasing (a rollback can land behind
more than one external write); the barrier was taken anyway on the POSIX production
path, the two guarantees stated apart, and the test of it ran inside a Linux container
since the development platform cannot sync a directory through `os.open` (`fb67e44`).
The corpus port offers documents by id and by search and no enumeration, so the
foreign direction of document exactness needed an inspection outside the port, the
same shape as Frappe's held employee numbers and Jira's held markers (`69a0b71`). And
the closing review found a hole in the integrity chain I had drawn: the scenario specs
are authenticated by the world spec's digest, so the manifest's own copy of that
digest was never compared, and a manifest recording a false one was approved with the
false digest carried into the verdict's provenance; reproduced by a scratch script
against the pushed commit before the fix, cross-checked now, and the same commit made
the "each enumeration read once" claim true in the code rather than only in the
docstring, and paid the step's own documentation debt in DESIGN instead of deferring it
(`8823526`).

Figure: two views of one world side by side, dated against runtime, for scenario 1's
stable days: the same records, the late-planted leave for the cover absent from the
dated column and present in the runtime column, with the cover's verdict flipping
beneath it. The records and the verdicts come from the realizability test in the
runtime-view suite.

## 2026-09-12 — The receipt nobody could read back: how a manifest became a checkpoint, and why "projected" stopped meaning "approved"

*M1 step 10 of the build plan, the projection of the synthetic world into the four
systems: the world manifest (`1bbf44a`, review `c27e25a`), the projectors (`81ba24e`,
reviews `d6452a6` and `871ebc0`), the site inspections (`73a0546`) and the composition
root (`925feed`, reviews `985c4ec` and `a9d8718`), all 2026-09-12; the unit suite went
from 1509 to 1546 tests across the step, every projector and root test against
in-memory ports, no sandbox touched (the `just check` runs of the session). Feeds: the
M1 report's projection and restart-safety section, and its evaluation-integrity story —
what the manifest's "projected" stage does and does not claim, and which layer proves
what.*

Step 10 was designed before it was coded, in an interview with an external reviewer
who saw each question cold: one ruling per exchange, the reviewer's feedback answered
point by point, then Arda's call. Seven rulings came out of that, and the interesting
part of the step is that two of them did not survive contact with the code. The
record below keeps both the rulings and the reversals, because the reversals are the
story.

**Seven rulings, most of which held.** The world manifest — the projection's receipt:
which Frappe company, which Jira project and field ids, which Google calendar belongs
to whom, and one locator per entity the projection wrote — went to the adapters
package, the lowest rank that can type adapter configuration and world provenance
together, so the generator writes it and the validator and the application decode it
without either importing the generator. The residual window in the Jira identity
marker (an issue can exist before its planted id lands, and a restart against a lagging
search index could then create a second) was closed not by a checkpoint file but by a
preparation guard that reads every issue in the project, marker filter off, and refuses
an unmarked issue or a marker held twice, naming the keys for a human to delete; it
runs before projection, where index lag can blind it, and again after, where the run's
own duration has let the index catch up. The calendar map is persisted after each
obtained calendar id, because Google mints those ids and the restricted scope the app
runs under cannot list them back, so an id whose response is lost is an empty orphan
only a human sees; per-calendar persistence bounds that at one orphan per interrupted
attempt. The projectors got a per-system restart strategy rather than one algorithm:
Frappe, Jira and the corpus find by domain id, verify the found record equals the
planted one, and add what is missing; the calendar inserts directly, since its vendor
event id is derived from the domain id and the insert is itself the ensure — a missing
copy created, an existing one verified by read-back, a half-written event completed —
whereas finding one event by id would cost one read per calendar and turn a
recoverable partial write into an error. An existing record that differs became a
third port fault, `IdentityConflict`, on the reviewer's point that the existing
"malformed" fault means "cannot translate" and this record translated fine: the
identity points at other state, and nothing adopts or overwrites it. A Frappe site
inspection looks past the company for a world employee number another company on the
site already holds, since employee names are unique per site and the ordinary reader
is company-scoped by design. And the names a world takes in the vendors derive from its
version — a Jira project key of `W` and nine hex digits, a company named by the same
key — with the project's description carrying the full version so a found project can
be verified by a read before anything is written into it.

**The receipt nobody could read back.** The projectors commit (`81ba24e`) collected
each system's locators in a local dictionary and returned them when the batch
finished. The reviewer's finding was exact: a reader returns a domain entity and never
a vendor locator, on purpose, so that vendor ids stay inside the adapters. Jira's issue
key therefore exists in exactly one place, the writer's return value. If the source
died after the third issue, the batch raised, the three locators were gone, and a
restart would find the three issues, correctly not re-create them, and have no way to
learn their keys. The same held for Frappe's generated leave names. The fix I proposed
before the commit, when the shape first showed, was a third manifest stage —
"projecting", with receipts growing under it — to preserve an invariant the first
review round had introduced: that a manifest still preparing carries no receipts. The
reviewer's fix was better and I said so: keep two stages, let receipts grow under
"preparing", and give the projector a sink it calls with each locator before the next
external write, so the root can checkpoint it durably. A third stage would have
encoded internal workflow progress that nothing consumes, since a restart re-runs
preparation anyway. Then the reviewer withdrew their own earlier invariant as too
strong, in writing. The regression test that landed with the fix (`d6452a6`) does what
the review asked: two writes land and reach the checkpoint, the source dies before the
third entity is touched, the checkpoint survives into the rerun, the found two are not
re-reported, and the union covers every planted id.

The guarantee that came out is narrower than "crash-safe receipts", and the narrowing
was the reviewer's second contribution on the same thread. What the sink proves is that
a later projection failure cannot lose the receipt of an earlier completed write. What
it cannot prove is survival of a process death, or a failed checkpoint, in the window
between an external write returning and its locator reaching the file — there is no
transaction spanning Jira and a local file, and no callback placement closes that. The
project's recovery contract is restartability after the faults the transport reports,
not after a kill at any instruction, and the docstring says exactly that. What I added
to the record: the window is loud, never silent. A restart finds the record, receipts
nothing for it, and the post-projection coverage check refuses to promote the
manifest; the operator's remedy is the same as for any debris, delete the marked record
and rerun. The reviewer's list of unrecoverable locators named Jira issue keys and
Frappe leave names; reading the writers showed a third, Jira component ids, which the
docstring now lists beside them (`871ebc0`).

**What the root proves, and what it must not pretend to.** The composition root
(`925feed`) drives the sequence the rulings fixed: resume from the stored manifest or
start fresh, one calendar per employee with a save after each new id, the site
inspections as a preflight allowing a subset of the world, the projectors with every
receipt checkpointed, the inspections again demanding the exact set, a coverage proof,
then the promotion to "projected". Its first review (`985c4ec`) found four things I
had left open, all reproduced before triage and all adopted: the remembered calendar
map was never scope-checked, so a checkpoint carrying a stranger's calendar would have
widened the application's read surface, since the calendar adapter reads every
configured calendar; a resumed checkpoint's header — digests, generator version,
organisation parameters — was trusted rather than compared against the fresh values
the root held; the coverage proof allowed foreign receipts; and the Frappe inspection
silently skipped a company employee without a number. The resume now builds the
fresh manifest every time and takes from the checkpoint only what grew in it, the
calendar map and the receipts, after every header field is compared.

The second review round asked for more, and this is where I pushed back. The
reviewer's finding was that the postflight proves exactness only for employees and
Jira issues, while the readers also enumerate leaves, components, events and
documents: a foreign record of any of those kinds, carrying a valid planted-style id,
would survive promotion and enter the investigator's fact surface, where the
closed-world enumeration contract grades absence as known false. True, and the root's
docstring had claimed "this world and nothing outside it". My answer was that the
root's inspections exist for one class of failure — its own interrupted writes leaving
state its find-or-create cannot see, which only Jira issues can do, since every other
kind lands with its identity in one write — plus the integrity of its own checkpoint
and the namespaces projection depends on. A foreign leave is not projection debris; it
is contamination from outside the generator, improbable under per-world naming, and
the independent proof that the live systems hold exactly the declared world is the
validator's, the next step, which already re-reads every enumerable kind. Proving full
exactness in the root and again in the validator would be the same proof twice, in the
layer not built to give independent evidence. The reviewer agreed, called their own
earlier recommendation a conflation of two guarantees, and tightened two things I
would have left loose: the manifest's "projected" stage now means the projection
lifecycle completed with the generator's own invariants proven, not that the world was
independently accepted — only a validator-approved world is served — and the step-11
claim is written explicitly as set equality of observed and expected identities per
closed enumeration, missing and foreign both refused, over the named surfaces
(`a9d8718`; the claim is in the step-11 plan, not yet code —
[PRELIMINARY — the validator does not exist yet]). The one immediate change from that
round, a foreign receipt refused on load before any vendor call, landed in the same
commit.

> ⚠ REVISED by the step 11 entry above (2026-09-12) — the exactness claim is now code,
> scoped by the world horizon for the windowed kinds and by an inspection outside the
> port for corpus documents.

The division that came out of the argument reads, in the reviewer's words, cleaner
than either of us had it at the start: the generator proves that its projection
procedure converged safely and that its checkpoints are internally consistent; the
validator proves that the realized world equals the declared one. Those are different
questions, and the manifest's stage answers only the first.

Figure: the checkpoint trail of one fresh run as a timeline — one save at the start,
one per calendar, one per receipt, one promotion — against the trail of a run cut off
after two work-item writes and resumed, showing where the second run's saves begin.
The numbers come straight from the root's tests, which count the saves.

## 2026-09-12 — Four leaks and a rollback: what the adapter tranche learned about trusting a gate, a vendor, and a transaction

*M1 step 9 of the build plan, the four adapters that carry the synthetic world into
Frappe HR, Jira, Google Calendar and the project's own PostgreSQL corpus (the calendar
in `860c3f7`, the corpus in `2ecdcb8`, the end-of-adapter review fixes in `e9f04e6` and
`3dc390a`, all 2026-09-12; 1495 unit tests and ten integration tests at the seal).
Feeds: the M1 report's adapters and grounding section — translate, never launder, and
what evidence discipline costs at the wire — its evaluation-design section, where the
cassette gate stands as a measurement-integrity mechanism, and the M1 post.*

The adapters are the part of the system a reader might skim: vendor JSON in, domain
entities out, and a retry rule. What the tranche actually produced is three lessons
about where trust breaks, and each of them arrived as a surprise rather than a plan.

**The gate that was right, and then not enough.** The adapter integration tests run
against recorded HTTP cassettes, and the cassettes are committed, so every recording
against a real sandbox is a chance to commit a secret or a hostname. The day before the
calendar work, the scrub had been made structural for a reason the CI pipeline forced:
CI has no sandbox credentials, so a check that "the real host is absent" would pass
there vacuously. The gate instead demands that every request host be a placeholder or
a public API host, that every listed header be redacted, and that every secret-shaped
JSON key read as the placeholder. Its record on the first two adapters was exact: the
Frappe recording leaked the site in a request `Host` header after the URI was clean,
and the Jira recording leaked it in a `Location` header on a create. Both caught on
the gate's first real run, both fixed by widening the scrub.

The calendar recording then produced the case the gate could not see. Google's
response to creating a secondary calendar carries the owning account's e-mail address
under a key called `dataOwner`, and every event carries it again under `creator.email`.
Neither key was on the list. The identity net that should have caught the address by
value was blind for a reason nobody had checked: google-auth writes the account into
its token file as an empty string, so the net had nothing to look for. The leak was
found by a manual scan of the cassette for the mail domain, not by the test. The
repair is the point: both keys joined the list, and the gate gained a second net that
does not depend on any list at all, a signature for a consumer mail address anywhere
in the file, beside the existing signatures for token shapes. The gate was made to
fail on the leaked cassette before the recording was redone, so the new net is known
to bite. Minutes later the same cassette tripped the repository's commit-time secret
scanner on `nextSyncToken`, Google's opaque sync cursor, which the adapter never
sends; it was redacted by key rather than allowlisted, because an allowlist on a
cassette would also hide a real token. The lesson generalises past this project: a
key list is necessary and never sufficient, since a vendor will put a secret under a
key nobody listed, and a gate needs a signature net beside the list.

**A ruling deviated, with the reviewer's concurrence.** The design interview two days
earlier had named Google's discovery client for the calendar. Reading the sealed
Frappe and Jira adapters made the cost visible: the client ships no types, so under
strict type checking every call would hide behind an `Any`; it brings a second HTTP
stack with its own retry loop that sleeps on the wall clock outside the injected
sleep, so a recorded rate limit would pause a cassette replay; and it would need a
third wire-test style. The six calendar calls are plain paths under one base URL. So
the calendar rides the shared transport, and google-auth keeps only the credential and
its refresh. The external reviewer approved the deviation and refined three things,
each adopted: the domain event id must be encoded into Google's alphabet (it was the
plan, a digest, now doctested and later corrected to say what it always was, a SHA-1
hex digest that happens to sit inside that alphabet); a 409 on an insert with a
supplied id must mean "read the copy back and compare", never "written", so that an
id collision or a cancelled event Google still remembers is a loud error; and every
read should ask for one time zone so identical copies on calendars in different zones
arrive in one form. The first recording proved the two claims the design rested on:
Google answered 409 when the review meeting was added a second time and both copies
verified equal, and the restricted scope the app runs under is allowed to delete the
calendars it created.

The representation that the recording exercised is one Google event per attendee's
calendar, so each synthetic person's calendar shows their own busy time the way a
free/busy query expects, and the reader makes one domain event of the copies. It
treats any inconsistency as malformed rather than choosing a copy: copies that
disagree, a copy on a non-attendee's calendar, an event present on fewer calendars
than it names attendees. The reviewer's review of that commit found the one case it
still laundered: two Google events on one calendar carrying the same planted id and
identical fields collapsed into one. It was reproduced in the pure grouping function
and closed the same day, and the reviewer's proposed invariant was adopted as a rule
for all three vendor adapters at the end-of-tranche review: one semantic identity has
exactly one vendor representation per place, and duplicates are malformed, never
deduplicated. Frappe's enumerations, which had enforced exactly-one on a select but
not on a listing, gained the same check.

**The bug the projector would have met first.** The end-of-adapter review, run over
the corpus commit with the deferred items from every earlier round, found the
tranche's one genuine defect. The corpus adapter opened a default psycopg connection.
On such a connection a plain `SELECT` opens a transaction that the driver never
closes; a later explicit transaction block, entered while that transaction is open,
creates only a savepoint; releasing the savepoint commits nothing; and closing the
connection rolls the whole thing back. The projector's own sequence is exactly that
shape, read by id, miss, add. Reproduced live on the development database before any
fix: the same adapter read its own document back, its connection reported "in
transaction" just before close, and a fresh adapter opened afterwards saw nothing
(reproduced on the development database before any fix was written). Every
projected document would have been lost, silently, on the first real run. The
integration tests had passed because each of them wrote before it read, which is the
convenient order and not the caller's. The fix is an autocommit connection with
explicit transaction blocks kept around the document write and the schema bootstrap,
and a regression test that replays the caller's order: a missed read, a write, a
close, a fresh adapter that finds the document. The test was confirmed to fail on the
old adapter and pass on the new (`e9f04e6`; reviewer approved). The transferable
lesson is about test order: a lifecycle claim has to be reproduced in the sequence
the real caller uses, not the one that is easy to write.

**A design sentence that the code had quietly outgrown.** The reviewer also raised a
cross-cutting mismatch: the design document said every scenario-owned entity carries
the scenario id in each system, as a Jira label, a calendar property and a Frappe
custom field, and no adapter plants one, nor do the writer ports carry one. The
reviewer read it as an implementation drifting from its design. The diagnosis was
refined in discussion: the scenario-framework step, days earlier, had already placed
ownership in the sealed world specification's table of owned entities, so the design
sentence was the stale party, not the code. The ruling went to that reading on
2026-09-12, and the two design sentences were rewritten in `3dc390a`: a scenario's
slice is enumerable from the specification, not from the vendors, and the projector's
promise that a rerun adds nothing is now qualified by the one case it cannot keep, a
secondary calendar whose id Google chooses and whose creation response was lost, which
the restricted scope cannot rediscover. That qualification is a design check the
projector step inherits: how the composition root persists the calendar map is what
keeps the orphan case narrow.

A field note from the same day, because it cost an hour of confusion: the integration
recipe took 92 seconds for six corpus tests, and the cause was `localhost` resolving
to IPv6 first on the development machine while the database container publishes on
IPv4 only, so every connection waited out a ten-second timeout before falling back.
Pointing the recipe at the loopback address brought the whole integration level to
about five seconds (timed connects, 2026-09-12: 10.07 s by name, 0.04 s by address).

Figure: a small table of the four cassette leaks across the tranche — where each
arrived (request `Host` header, response `Location` header, `dataOwner` and
`creator.email` keys, `nextSyncToken`), which net caught it (the structural gate, the
structural gate, a manual scan, the commit-time scanner), and what the gate gained in
response — would carry the "necessary, never sufficient" point in one glance.

*M1 step 6 of the build plan, the organization generator: the closed vocabulary with
its version and digest, then seeded people, teams, skills, managers, components
(commits `9050eb8`, `5139149` on 2026-09-11, two review follow-ups; 465 tests at the
seal). Feeds: the M1 report's generator section — what the organization guarantees and
what it deliberately leaves to the scenarios — and its evaluation-design section, on
how the golden set's classes are plantable at all; the M1 post.*

The plan for the organization generator carried, in its first draft, an invariant that
read as plainly sensible: every skill in the vocabulary has at least two holders, so
that finding cover is a search rather than a lookup. It was proposed in the opening
plan of the session, before any code, as one of four structural invariants the org
would enforce. It died within the hour, and the way it died is the story worth
keeping.

The external review, agreeing with the shape of the org record, added an aside that
the retained skill vocabulary "permits unused-but-valid skills later". That remark
prompted a check of the proposed invariant against the golden set as the design
document defines it (the "first golden set" section of DESIGN). Tier 3 contains three
`uncovered` scenarios, each needing a complete world in which nobody qualifies for the
need — a skill with no holder at all, or none available. It also contains three
`missing_information` scenarios, each wanting the only plausible candidate to have no
skills record whatsoever, not an empty one. And the golden-set ruling of two days
earlier says that org-level facts are static across the whole world: a scenario
produces its class by choosing the leaver and the need so that the static facts yield
the intended outcome, never by editing shared state for one slice. Put together, a
generator that guaranteed two holders for every skill would have made six of the
thirty scenarios impossible to plant. The invariant did not merely constrain the
world; it deleted the hardest part of the evaluation.

The turn that followed is the design the generator now implements. The organization
guarantees *shapes* — the raw material scenarios select from — and never coverage. By
construction there is at least one skill nobody holds, one skill exactly one person
holds, one skill held by at least a third of the people who have a record, exactly the
parameterized number of people whose skills record is absent, and every component
drawn across at least two teams so that "same team" and "relevant component" can
disagree. Coverage-as-a-search, the property the withdrawn invariant was reaching for,
became the scenario's business: the class invariant that runs at construction and
fails generation by name when the intended outcome does not emerge. The external
review's follow-up sharpened the form of these guarantees, asking that they stay
existence claims ("at least one zero-holder skill") rather than a locked histogram, so
the scenario step keeps room to select.

Two further rulings came out of looking at the generated thing rather than its
tests. A readable print of the seed-7 organization under default parameters showed
one team of ten and another of three out of twenty-eight people — independent random
placement of the remaining seats after one lead and one member per team — and a
three-person team leaves a scenario nothing to search inside it. Members are now dealt
round-robin with at most two moves between teams, so sizes differ by a few. The same
print showed one contractor where a fifteen-percent share over twenty-three non-leads
had been expected to give about three, and a different seed could have given none,
which would leave every contractor-scoped policy clause without scope anywhere in the
world. The generator now guarantees one contractor whenever the share is above zero,
the same reasoning as the skill anchors: a prerequisite a scenario class depends on is
constructed, not left to probability. (Both figures from the seed-7 sample printed
before the second commit; the team sizes after the change were 6, 6, 6, 5, 5.)

The transferable lesson is uncomfortable because the withdrawn invariant sounded so
reasonable. A generator guarantee that reads as obviously good can quietly remove the
test cases the evaluation exists for, and the only defence is mechanical: every
invariant the world enforces gets checked against the list of classes the golden set
must plant, before it is built. The check took minutes; the invariant would have cost
the adversarial tier.

## 2026-09-11 — Provenance is not dependence: the sources a conclusion needs are found by taking them away

*M1 step 7 of the build plan, the scenario framework: constructive selection, modifiers
as declarative planters, the rules as verifier, the required-sources field of the key
(commits `3f10da4`, `1b0f0b9` on 2026-09-11; regression tests in
`tests/unit/test_world_construction.py`). Feeds: the M1 report's evaluation-design
section — what a scenario key's required sources mean and how the tool-failure
condition is defined — and the section on keeping the rules a verifier rather than an
author of truth.*

A scenario key records the systems a complete investigation must have read, so that a
run which never touched one of them can be graded as incomplete rather than merely
wrong. The framework's first version derived that list the obvious way: collect the
sources of every evidence fact the viability rule cited while assessing the
candidates, add the sources of the facts about the impact's artifact and the leave
under investigation, and the union is what the investigation needed. It passed its
tests and it was wrong in a way the external review put in one example.

A candidate who does not hold Kafka is non-viable for a Kafka requirement. That
conclusion cites no evidence fact at all — the evidence is the absence — yet under
the closed-world rule it depends on every source in the skill predicate's declared
domain having answered: the HR record and the tracker both, since a skill may be
evidenced in a ticket comment. With the tracker unreachable the same question stops
being a known negative and becomes an unknown, inaccessible. So the tracker was
required, and a list built from positive evidence would never contain it. Provenance
answers "which record established this?"; dependence asks "which sources had to be
observable for this conclusion to stand?"; under closed-world reasoning the two are
not the same set.

Two repairs were considered and rejected. The domain's assessment record could be
extended to report every predicate it consulted, positive or negative — a change in
`core` for a consumer in `world`, and one more field to keep faithful as the rule
grows. Or the framework could list the rule's reading order itself — which predicates
viability touches for each criterion — which is a copy of the rule's internals kept in
step by hand, exactly the coupling the constructive-selection ruling was written to
avoid. The definition the reviewer had used to state the bug was itself the cheapest
implementation: a source is required if taking it away changes anything the rules
conclude. The framework now computes the normal conclusions, re-runs every assessment
and outcome with each source in turn made unreachable, and marks a source required
when any conclusion moves. It knows nothing about what the rules read, it uses the run
condition the evaluator already defines for tool-failure runs, and it is by
construction the tool-failure metric's own notion of dependence. The regression test
is the reviewer's example verbatim: a release meeting under a Kafka clause, a
candidate lacking Kafka, no tracker fact about the meeting — and the tracker comes out
required through the negative alone.

The second round found the comparison one level too coarse. The signature that decided
whether "anything moved" carried each candidate's verdict and reason classes, and an
unknown carries no reason class; so an unknown because the record is blank and an
unknown because a source could not answer compared equal, and a source whose loss only
changed *why* a candidate was unknown looked unrequired. The fix carries each
assessment's unresolved questions — subject, predicate and the derived reason — into
the signature. The honest part of this round: the regression the reviewer proposed
(a blank-record candidate under the same clause, assert the tracker is required)
passed before the fix as well as after. Over the whole organization, every other
candidate with a normal skills record already flipped from known-negative to
unknown-inaccessible when the tracker went away, so the tracker was required through
them regardless of the blank candidate. The signature was still wrong as a definition,
and would have surfaced with a small explicit universe or a predicate nobody holds
negatively; it was fixed and recorded as a correction of the definition, not an
observed miss, and the sharper test pins the counterfactual through the domain's own
assessment call — the same candidate, unresolved for absence with the tracker
reachable and for inaccessibility without it.

The reviewer, checking the finished comparison for overreach, listed the cases it
handles the way one would want: a source whose facts another source duplicates is not
individually required; a source that flips a verdict or an outcome is; a source that
only changes why something is unknown now is; a source that removes redundant evidence
without moving a conclusion is ignored. That list is the sentence for the report:
required sources are counterfactual, not archival.

Figure: a small table for one scenario — rows the candidates and the outcome, columns
the normal run and each single-source outage — with the cells that move highlighted;
the tracker column moving for a candidate who cited no tracker fact is the picture.

## 2026-09-10 — A query is not a fact: the port that let the tracker answer "owned by" would have graded a missing record as a known negative

*M1 step 5 of the build plan, the seam between the domain and the four systems: the
read and write ports, the observed-entity wrapper, the leave as a run input, the fault
contract, and the derivation that turns a record into facts (commits `89c54a9`,
`820d1b6`, with review follow-ups `acae3bb`, `d940436`, `c072818`; 246 tests including
doctests at the seal). Feeds: the M1 report's architecture section — where the port
boundary sits and why read-only is a property of the import graph — and its
evaluation-design section — how the boundary protects closed-world grading; the M1
post.*

The step opened, as the previous ones had, with an interview of one question per
exchange, each answer sent past an external low-context reviewer before it was ruled.
Four rulings came out of it. The first decided what crosses a port: observed domain
entities — an employee, a work item, an event, wrapped with the source it was read
from — and never facts. The alternative, adapters returning facts directly, would have
put the meaning of every field into four vendor modules where it could drift; keeping
it in the domain means an adapter translates shape and identity and nothing else, and
the gap logic that closure depends on lives beside closure. Documents are the
deliberate exception, and the reviewer sharpened why: a document section is an id and
text, so what a clause requires cannot be derived from it without parsing prose, and
the design already said truth stays the structured brief. The requirement fact
therefore enters the fact base from the world's brief, the investigator establishes
which clause applies and cites it without transcribing its content, and the plan check
resolves the citation to the truth's requirement. No extraction seam exists anywhere,
in the world milestone or the investigator's, which is a smaller architecture than the
one first sketched.

The second ruling split reading from writing into two modules, and here the reviewer
improved the proposal. The first version would have scanned the investigator's code
for writer class names; the reviewer's version denies the write module by its import
path, which the import-law test already knows how to read. Working that through
exposed the one evasion a module rule alone would miss: a re-export of a writer from
the domain package's own `__init__` would have laundered it behind an import the law
reads as harmless. So the rule became an allowlist over every module that names the
write module — only the adapters that implement it and the generator that projects
through it — and the test proved itself against a planted re-export before the commit.
The writers have a single production consumer, which the project's own rule about
ports would normally forbid; they are a port anyway, for the least-privilege type and
for the in-memory implementation both sides share under the tests, and the design
says so rather than pretending to hexagonal symmetry.

The third ruling put the leave under investigation on the run context as an id and
nothing more, in the reviewer's phrasing: run inputs identify what to investigate,
ports establish the facts about it. The leave record, its employee and its span are
read through the people port, so they are evidence the run established and a scenario
can contradict, never a truth the harness told it. The consequence for a run whose HR
system is unreachable is that it has no interval at all — not merely an unknown leave
fact but no way to scope which tickets and meetings matter — and the rule is that such
a run continues degraded and surfaces the unknowns rather than inventing the span; how
that grades is the evaluator's design. The fourth ruling kept three fault outcomes
apart because closure treats them differently: a record that is not there is a plain
`None` or an empty tuple, a source that cannot answer after the adapter's retries raises
one typed exception, a record the adapter cannot translate raises another, and the two
share no base so a single `except` cannot fold a defect into a legitimate unknown. The
reviewer's triad is the sentence the report can carry — missing data is evidence,
unavailable infrastructure is an epistemic limit, malformed data is a defect — and
their small catch on the third case was real: a malformed record may have no domain
identity yet, so it is reported with an opaque source-side locator, not an entity
reference the adapter could not have built.

The moment worth telling came at the review of the first commit. The work reader had
been given two convenience queries, "work items owned by this person" and "work items
in this component", written without a ruling because they read like ordinary tracker
calls. The reviewer noticed that both filter on exactly the relationships the domain
is supposed to derive as facts — ownership and component are registered predicates —
while the people and calendar readers already followed the opposite principle: return
the universe, filter by a fact you derived. The asymmetry was more than aesthetic. The
predicate registry declares each fact's evidence domain closed, and closure turns
"source reachable, zero facts" into a known negative. That declaration is honest only
when the run actually read every record the source holds. A vendor-side filter can
drop a record before the adapter ever translates it — a work item whose owner field is
malformed simply fails to match the query — and the domain then grades "the query
returned nothing" as "this person owns nothing", the very distinction the previous
step had built the gap and the run condition to preserve. With an enumerating read the
same record raises a malformed-record defect instead. The rule that came out is the
reviewer's wording, more precise than "enumerate everything": a fact-bearing reader
enumerates its domain, selects by identity, or narrows by a natural window such as a
date span; it never filters by a relationship the domain derives; document search is
content retrieval and derives no facts. The leave query lost its employee filter for
the same reason and kept its span.

The reviewer added a precision worth keeping. Enumerating readers make the
closed-domain declaration possible to honour, not automatically true: closure has no
notion of "the tracker was read to completion", only of facts, gaps and which sources
were reachable. The fault ruling from earlier in the step closes most of the gap — the
first unreachable fault marks the source unreachable for the rest of the run, so
reachability at the end of a run means every enumeration the run attempted completed,
and facts read before the fault stay facts because closure checks a positive fact
before it checks reachability. What remains is the harness that never called the read
at all, which is a lifecycle contract for the investigator milestone — every
enumerating read runs to completion before the rules — and not a new completeness
type; that type arrives only if reads ever become incremental. The cost is stated
honestly: "what does this person own" becomes a filter over facts derived from the
whole project rather than a server-side query, retrieval efficiency spent for the
benchmark's evidence semantics, negligible at this world size, and pagination stays the
adapter's without reintroducing a relationship filter, since "the next page of the
universe" is not "only the records for which a fact is assumed true".

The second commit built the derivation itself: one function per observable record,
and the meaning of every field's absence stated in one place — a missing skills field
is a gap, an empty one is zero facts; a missing due date or manager is an observed
negative; a requested leave, a comment, a team and a document derive nothing. When a
fact became observable is the caller's knowledge, passed as a parameter, because the
entities keep vendor timestamps out on purpose. The main test rebuilt the four-person
rule fixture from entities and checked that the derived base contains every
hand-written fact but the four only a world can plant — the skill mentioned in a ticket
comment, the owner a stale runbook asserts, the two clause requirements — so the
fixture and the derivation stand as two independent sources for each other. Stated as
a proposal for the steps that build the truth base: the world should derive its truth
from the entities it generated through this same derivation and then add what only a
world knows, so the truth base and the base a live harness derives agree on what every
field means by construction rather than by a table kept in step.

The last review round showed what "two independent sources" does and does not check.
The event's schedule fact — a half-open span built from the event's start and its end
— cited the `start` field as its evidence, and so did the fixture's hand-written
helper, so the equivalence test passed while proving only that two copies of one
assumption agreed. An evidence reference is a locator for re-verification, and
re-reading a start time cannot re-establish an interval. The schedule now cites the
whole event record, the same shape a leave's absence uses when it cites the leave
record, and the fixture changed with it; a direct assertion on the provenance was
added so the shared assumption cannot hide again. The transferable lesson is that a
consistency test between two artifacts written by the same hand checks the hand's
consistency, not its correctness; independence has to be argued per assumption, and
provenance is one the fixture did not independently hold. The same round caught a
fixture comment written without the bracketed prefix a translated comment must carry,
and a fixture named five-person that has held four people since it was written.

Figure: the boundary as a pipeline — port observation → complete enumeration or
natural window → entity translation → fact derivation → relationship filtering →
closure — beside the before/after of the work reader's surface (owned-by and
in-component gone, one enumerating read in their place).

## 2026-09-10 — The rules are questions to the fact base: a verdict table caught the veto the code had hidden, and "uncovered, not unknown" turned out to be arithmetic

*M1 step 4 of the build plan, the deterministic core in `core/`: value specs, the fact
base with gaps and the run condition, closure, the authority table, the viability
rule, the plan side, the chain checks (commits `bc8582a`, `8cafa99`, `f30451d`, with
review follow-ups `8d5a192`, `b8f3805`, `5b5fc4c`; 221 tests including doctests at
the seal). Feeds: the M1 report's deterministic-core and evaluation-design sections
— why the same rule functions serve the generator and the evaluator, and what
"derived per run condition" costs in practice; the M1 post.*

The step opened with a five-question interview, one ruling per exchange, and each
answer went past an external low-context reviewer before it was ruled. That loop
earned its keep in the first question. The proposal was that a fact's value shape is
the predicate's to declare — a value spec on each registry row, validated at
construction and mirrored as the JSON tag — with a single `Requirement(count,
skill)` shape for what a clause asks. The reviewer wanted the requirement's criterion
tagged on the wire so a sealed answer key survives a later grade or country
criterion; the counter-argument was that a one-variant union is structure ahead of
need. The compromise was to tag the wire and keep Python narrow. One question later
the ruling on `hard_rule` — a policy criterion such as "an employee, not a
contractor" living inside the same requirement — made the union real, and the wire
shape was already right. The lesson the report can carry is about sealed artifacts:
a format decision is cheap before the first world is sealed and expensive after,
which is the one place where "you aren't going to need it" loses to a tag.

Two rulings shaped everything downstream. Absence became a record of its own: a
`Gap` says the record was observed and the field held no value, planted where a
scenario class plants missing information, and never a failed read — a failed read
is the run condition, a set of reachable sources passed beside the run context
because one scenario runs under several. That split lets closure read in five steps:
a positive fact is known true, a domain source unreachable in this run is unknown for
inaccessibility, a gap is unknown for absence, an open domain is unknown for
insufficiency, and only then is zero evidence false. The second ruling kept a
requirement's count away from any individual: criteria assess a person, the count
judges a plan, so one viable person against a two-person clause is a viable candidate
and an invalid plan. `load` was pruned from the reasons a candidate can fail for —
no first-set scenario names it, and a threshold would be either a constant the agent
can only be told or a clause no scenario uses; it returns when a class gives it
semantics.

The build ran in three commits, reviewed as foundation first and dependents together.
The moment worth telling is in part 2. Once the viability rule existed, the five-person
test fixture was run under three conditions — every source reachable, the tracker
down, the calendar down — and the verdicts printed as a table for Arda's read. One row
was wrong on sight: with the tracker down, the ticket's component could not be read,
and the code had marked the whole need unresolved, so the leaver herself showed as
*unknown* although her leave was a known failure. The ruling said a known failure
dominates an unresolved question; the code had let one unreadable fact veto every
other criterion. The fix made an unreadable component one unresolved criterion and
kept the leave window — a run input, not a fact the rule establishes, since a run
whose HR system is down still knows which leave it investigates. A meeting whose
schedule is unreachable stays an unresolved need for everyone, because without the
window no criterion has anything to ask. The table caught what the tests had not,
because the tests encoded the same assumption the code did.

The same table produced the case the post should open with. The release meeting's
clause asks for two Kafka engineers who are employees. With the tracker down, one
candidate's Kafka lives only in a ticket comment and reads inaccessible; the other
three are settled — on leave, in an overlapping meeting, a contractor. The expected
outcome is *uncovered*, not *unknown*. That looks like a mistake until the rule is
read: with `V` viable and `U` unknown against a required `n`, the outcome is assign
when `V ≥ n`, uncovered when `V + U < n`, unknown otherwise. Here `V + U = 1 < 2`:
even if the unknown resolved in the candidate's favour, one person cannot fill a
two-person clause, so the epistemic gap does not change the answer. The formula
reasons about what the unknowns could become, and "uncovered" here is a certain
conclusion, not caution. That is the distinction the vocabulary was built to make
measurable, showing up unprompted in a fixture.

The two review rounds found five things, every one reproduced against the shipped
code before it was adopted, which matters because the reviewer could not run the
suite and worked from the pushed diffs. The one that would have bitten silently: the
closure function validated the subject of a query but not the value, so asking
whether someone holds `"Kafka"` where a lower-case slug is declared returned a known
false rather than raising — a programming error turned into a statement about the
world. The one I got wrong: the reviewer asked for a runtime check that a
requirement's criteria are the criterion classes, and I left it out as "the type
checker's job". The reviewer's follow-up showed the chain: the value spec admitted
the object, and the codec's unreachable branch would have failed with an assertion
instead of a `ValueError`. The codebase's own rule, that an object which exists is
valid, applied, and the check went in shaped so the strict type checker does not flag
it as redundant. The one that reached back: a source-conflict claim could describe a
skill set or two sources agreeing, neither a disagreement — a hole from the
claim-vocabulary step that only became observable once the chain checks trusted the
claim. It is now refused at both levels, the claim constructor and the authority
rule, because the two answer different questions: can a report represent this, and
may the table resolve this.

The last finding drew the boundary the evaluator will live on. The chain checks read
a report alone and never ask the fact base; an unknown assessment must derive from
unknown claims shaped as the rule emits them. A clause-shaped unknown originally
passed for any clause, so an assessment could be justified by an unrelated policy.
The tightening: the clause must be one the report's own constraint claims cite for
something that could apply to the impact — the artifact itself, or a component when
the artifact is a ticket. Whether the ticket really belongs to that component is
truth, and stays the evaluator's; that the report has not justified an unknown with a
stranger's clause is coherence, and the checker can say so from the report. Report-
internal versus truth-dependent is the same line the uncovered check keeps: a report
with no viable assessment passes the chain check even if it simply stopped assessing,
and a separate completeness check that takes the candidate universe is where the
world enters.

[PRELIMINARY — the fixture is five people and two impacts; the first generated world
at step 13 is where these rules meet thirty scenarios and the tool-failure runs, and
where the "every non-skilled candidate turns unknown when the tracker is down"
behaviour, correct under the closure rule, gets its first measured cost.]

Figure: the fixture's verdict table — four people × two impacts × three run
conditions, verdict and reason per cell, expected outcome per row (regenerable from
`tests/unit/world_fixture.py` and `assess_impact`); the "uncovered with one unknown"
cell annotated with the `V + U < n` arithmetic.

## 2026-09-09 — The gate had a name all along: the 5-series block is an account review, and the public threads never said so

*M0's trailing thread, the Bedrock Support case (case 178776610200708; detail in
`probes/FINDINGS.md`, the dated 2026-09-09 entry). Feeds: the report's model-seam
section, as the second half of the "listed is not callable" story; a teaching aside
on where to look when the public record looks unresolved.*

The 26 August entry below ended with a research pass that found no official
criterion for the Sonnet 5 / Opus 5 block and no confirmed fix in any public thread,
and with a Support case queued "for the record". The case was opened the next day
and the answer came back within hours: access to those models "requires an account
review process", which Support submits on the customer's behalf once it has a
business use case (task types, usage pattern, why the region) and a business website.
That is the criterion the seven-source research pass could not find, and the reason
it could not is ordinary: the people who got this answer stopped posting. A thread
that looks unresolved on re:Post is often one where the resolution moved into a
private channel. The lesson for the report is small and transferable — when a gate
behaves like account state, ask the account's owner before surveying the crowd, and
do it early, because the answer arrived faster than the research did.

The case then sat unanswered through the platform detour, auto-closed after ten
days, and was re-opened and answered on 9 September. The reply is deliberately plain
about what this is: an individual developer's portfolio project, synthetic data, a
few hundred evaluation requests per run a handful of times a week under a Budgets
cap, Frankfurt because the rest of the stack lives there, the portfolio site as the
"business website". Inventing a company to pass a review would be a poor trade for
a project whose pitch is honest measurement, and a refusal is itself a usable fact:
"an individual account was reviewed and declined" is more credible in a report than
"blocked, cause unknown". [PRELIMINARY — the review's outcome and duration are
pending; either revises this entry's last paragraph.]

Nothing in the plan moved. The ruling not to build around the 5-series was made for
schedule reasons, not for lack of a path, and the review has no stated duration;
M2's Anthropic candidates stay Haiku 4.5 and Sonnet 4.6, and a pass later is a
one-line edit to the model list in the platform stack.

## 2026-08-26 — Listed is not callable: the Bedrock catalogue said AUTHORIZED to every model the runtime then refused

*M0 day 2, the bedrock probe (PARTIAL, then PASS for the reachable shortlist, same
day; detail in `probes/FINDINGS.md`, prices in `probes/captures/bedrock/models.md`).
Feeds: the report's model-seam and cost sections; a teaching aside for any post about
"choosing a model on Bedrock".*

The probe's question was modest: for each of six shortlisted models, does the
instance role get a round-trip, a tool call, and a prompt-cache hit, and what does
the model cost in Frankfurt. Four days earlier the account bootstrap had recorded
"Bedrock needs no model-access request in this account", on the strength of Haiku 4.5
answering cold. On the day, the three Amazon Nova rows passed everything on the first
run (`probe-run-1.jsonl`), and every Anthropic row failed — for two different
reasons that took a while to tell apart.

The control plane was no help in telling them apart. `get-foundation-model-availability`
reported AUTHORIZED and AVAILABLE for all six; the Bedrock console's old "Model
access" page has been retired; the catalogue lists the 5-series with a price. Only the
runtime knew the truth, and it knew it per model: Haiku 4.5 wanted Anthropic's
"use case details" form, which the console offers on the first playground invoke;
Sonnet 5, Opus 5 and Opus 4.8 were "not available for this account, contact AWS
Sales"; Sonnet 4.6 answered with no form at all. Reproducing the failures from an
AdministratorAccess session settled that this was account state, not the role's
grant — which mattered, because the grant had just been pinned to the shortlist and
was the first suspect.

The form's behaviour was the surprise worth recording. It was submitted at ~20:02;
Haiku 4.5 opened three minutes later. Sonnet 4.6, which had been open *before* the
form, went form-gated, then spent six minutes returning AccessDenied, then opened at
20:15:58, and flapped once more mid-run. Propagation is per model and not monotonic:
a model you could call can stop answering while the form works its way through. The
practical rule for a fresh account: budget twenty minutes and a retry loop, and
never trust the first answer in either direction. The 5-series gate did not move,
and a research pass (seven sources, re:Post and r/aws threads since roughly June)
found the same signature across regions and account types with no official
criterion and no confirmed fix — so the ruling was not to plan around the 5-series
at all. A fix later is a one-line edit to the model list in `variables.tf`; a
Support case is queued for the record.

> ⚠ REVISED by the 2026-09-09 entry — the Support case named the criterion: a
> manual account review with a business use case and website as intake.

Two smaller facts fell out. Anthropic's rows are not in the Pricing API (it carries
only legacy Claude 2/3 US SKUs), so their prices came from the pricing page read in a
browser by a subagent; the `eu.` inference profiles cost a flat 10 % over `global.`
across the board. And Nova Pro missed its cache once in five passes — an `eu.`
profile can route a call to a region that has not yet seen the prefix — which is a
line item for the M2 cost model, since the $0.75-per-investigation estimate assumes
caching works.

What the shortlist looks like after all this: two Anthropic models (Haiku 4.5,
Sonnet 4.6) and three Amazon (Nova Lite, Nova Pro, Nova 2 Lite), all answering from
the role, with Nova Lite about 14× cheaper than Haiku 4.5 on input. The choice among
them is deliberately not made here; M2's evaluation on the golden set makes it. The
probe's job was to find out what can be measured, and the honest summary is that the
catalogue could not tell us.

Figure: a small table — model × (control-plane says / runtime does / minutes to open
after the form) — makes the "listed ≠ callable" point in one glance.

## 2026-08-26 — The subject GitHub actually sends: an OIDC trust policy that matched the documentation and not the token

*M0 day 2, the oidc-deploy floor (PASS; detail in `probes/FINDINGS.md`,
`captures/oidc-deploy/`). Feeds: the report's deployment section (keyless CD, the
production gate) and the hosting appendix.*

The floor was preregistered as one sentence: a commit to `main` changes the running
service on the instance, with no AWS key stored anywhere. The mechanism is standard
— GitHub Actions federates into the account through OIDC, assumes a deploy role, and
runs the deploy script on the host over SSM `send-command` — and the probe plan
carried one open fact to record: what `sub` claim the token actually has, since
repositories created after mid-2026 were rumoured to emit a new form.

The rumour was right and the documentation was not, or at least not for this
repository. The trust policy was first written with the documented, name-based
subject. STS refused twelve retries with "Not authorized to perform
sts:AssumeRoleWithWebIdentity" before the job log gave up the real claim:
`repo:arda-basarici@133336041/leave-impact-agent@1342572683:environment:production`
— owner and repository each carrying their numeric id. Pinning the trust to that
form is the stronger pin, not a workaround: a repository renamed or deleted and
re-created under the same name inherits nothing, because the ids differ. The role is
trusted by repository *and environment*, which is why the production gate is part
of the security story rather than a convenience.

The gate had its own lesson. A workflow that references an environment which does
not exist creates it, bare; the first deploy went straight through with nobody
asked. Only after a reviewer and a `main`-only branch policy were set on the
environment did the re-run stop at "Review pending". A new GitHub environment is
not a gate until someone configures it to be one — worth one line in any runbook
that leans on it.

Two identity flips are on record: the first approved run replaced "no application"
with `leaveimpact 51d3f16`, and the very next commit — the one that recorded the
probe — flipped it to `leaveimpact 2f028b2` at 12:26:24Z through the same gate. In
between, the boot script changed (the proxy stack took over the shared network and
`trusted_proxies` is now rendered from the same pinned Cloudflare ranges as the
security group), so the instance itself was replaced: new instance, same Elastic
IP and data volume, certificate re-read from Parameter Store, HTTPS 200 with no
manual step, in 1m13s (the first boot had taken 4m53s, most of it waiting for the
secrets to be put). "The host regenerates from code" stopped being a claim and
became a measured event.

One deviation from the plan's wording is deliberate and should be told as such: the
row said "pushes an arm64 image to ECR", and there is no ECR. The baseline review
had already ruled GHCR as the registry, and a second registry would have existed
only to satisfy the row. The thing the row exists to prove — federation, a role
trusted by repository and environment, a commit landing on the host through SSM —
is exercised in full; preregistered criteria stay as written and the findings carry
the deviation with its reason.

## 2026-08-24 — One command, three systems, zero duplicates: the seed spike closed probe day 1 — and a network fault earned its place in the adapter design

*The last day-1 probe of M0 (seed-spike, criterion preregistered in `probes/README.md`
before the run). Feeds: the M0 probe-days post; the report's world-generator section
(the spec→projections→manifest seam) and its evaluation-design section (stable-now);
the M2 adapter section (the retry lesson).*

The spike's question was whether the M1 generator's core seam works at all: one org
spec — 5 people, 1 project, 8 issues, a week of meetings, 2 approved leaves —
projected into three systems that never see each other, idempotently. The three
systems (Frappe HR on the box, Jira Cloud Free, Google Calendar) are deliberately not
synchronized; what makes them "the same org" is only that all three projections read
the same spec, keyed by the same employee ids. Consistency by construction, not by
reconciliation — the project's ground-truth-by-construction signature applied to the
environment itself.

Before the spike could run, a ruling: the earlier probes had left residue (a "Probe
Org" company in Frappe, auto-created projects in Jira, test events in calendars), and
Arda asked for clean plates. The options differed in kind. Scrubbing shared systems
can never prove it got everything — every future world inherits doubt about what's
left. Fresh containers — a new Frappe site per world (`bench new-site` ≈ 2 min, the
Host header selects the site), a new Jira project key, new secondary calendars — are
provably clean *by creation*, and "reset a world" becomes drop-and-recreate instead of
a cleanup audit. Arda ratified fresh containers; the compose frontend switched from a
pinned single-site name to `$host` routing the same hour, and the probe created its
own site (`hr-w1`) rather than inheriting the probe site's residue. One honest limit:
Jira Free is one site, so the *project key* is the container there — residue outside
the world's key coexists but is invisible to the agent's tools, which query by
project and owner field.

The run itself passed everything on the first attempt (capture:
`probes/captures/seed-spike/run-01.json` — 64 creations). Two results matter beyond
"it worked." First, **Jira Free accepted everything over REST** — including creating
the `W1` project itself with the company-managed kanban template, previously an
open question, and JQL date arithmetic on custom date fields: `"Opened On" <=
"2026-09-08" AND ("Resolved On" IS EMPTY OR "Resolved On" > "2026-09-08")` returned
exactly the spec's open set per person. World dates as custom fields — the ruling
that had closed the resolution-date gap on paper the day before — now holds in
practice, and the manual CSV import is fully out of the seeding path. Second,
**stable-now became mechanical**: the spike's verify step computes `answer(now)` —
who is on leave in now's week, which issues are open as of now, which calendar
blocks are busy — at two instants inside a declared stable interval (Sep 8 and
Sep 10) and requires identical answers. It held, and the *reason* it held is the
design's teeth: the spec plants no world date inside the declared interval. That
guarantee is now the generator's contract, not a hope.

The idempotence half took a fight. Reruns kept dying on a transient transport fault:
an authorized Frappe GET would intermittently hang or get connection-reset, and the
origin's nginx access log proved the request *never arrived* — something between the
client and the box (the Cloudflare edge, or the hosting provider's connection
policing; the stream's fix log already records SSH resets on the same box under rapid
connections) was killing it. Unauthenticated calls never failed in reproduction; the
same call passed moments later. Mid-diagnosis Arda made a process correction that
shaped the outcome: don't burrow — surface what's known and discuss the approach.
The known facts supported a pragmatic fix over a root-cause hunt: a retry on
*connection-level* faults only (never on HTTP errors), safe here because every write
is find-or-create. Run 5 then delivered the criterion cleanly — **0 creations,
identical verify results** — and its capture shows the retry earning its keep: two
faults on one call, third attempt clean (`run-05.json`; runs 02–04 are the fault
captures). The transferable lesson went into FINDINGS: every M1/M2 adapter needs
connection-fault retries, because the transport to real external tools is measurably
imperfect even at probe scale. Root cause stays open in the fix log (cheapest next
clue: Cloudflare's Security → Events page).

A design consequence surfaced by Arda's question rather than any probe: when this
project is shared, *nobody visits the three tools*. They are the agent's world —
credentialed, private (a Free Jira site, Frappe behind Caddy on the box, a consumer
Google account) — not the audience's window. The audience surface is the demo
milestone's report view, which means evidence there must be **self-contained**: the
quoted fact, its source system, its provenance rendered in the report itself, with
deep links decorative at best. Noted for the demo milestone's design before any of
its UI exists.

Figure: the twin-instant check as a small diagram (one week band, two `now` marks,
three system answers converging to the same tuple); or the run-01 vs run-05 creation
counts (64 → 0) as the idempotence before/after.

## 2026-08-23 — Two vendor surprises from the HRIS probe: the setting that is silently ignored, and the approval check the admin token walks through

*M0 day 1, the frappe-rest probe (PASS same day; detail in `probes/FINDINGS.md`).
Written 2026-08-24 from the stream session log and FINDINGS. Feeds: the M0 probe-days
post; the report's adapter section (vendor-behavior risk) and its security/permissions
section (the runtime principal ruling).*

The HRIS probe was supposed to verify a boring round-trip — employees, leave
allocations, leave applications over REST — and it did (balance arithmetic exact:
20 → 15 for a Mon–Fri week, → 19 for a single day; capture
`probes/captures/frappe-rest/run-03.json`). What earns this entry are two behaviors
no documentation had promised.

First, a silent ignore. Frappe HR v16 resolves an employee's holiday list only
through a *submitted Holiday List Assignment* document. The legacy fields the v15
docs describe — `Company.default_holiday_list`, `Employee.holiday_list` — are still
accepted by the API and then ignored: run 2 set both and leave creation still failed
with "No Holiday List was found" (`run-02.json` is the failure capture). The lesson
is not about holiday lists; it's that a vendor API can accept a write and quietly do
nothing with it, which is exactly the class of behavior a generator that claims
ground truth by construction cannot tolerate on faith. The seed's independent
read-back verification exists for this reason, and this was its first live
justification.

Second, an inverted wart. Going in, the worry was that setting `leave_approver`
would need workarounds. Setting it turned out trivial — the real finding pointed the
other way: an *Approved, submitted* leave application whose approver is **not** the
submitting principal goes through when the token belongs to a System Manager. The
admin token bypasses the approval check entirely. For the generator this is a
convenience (it seeds approved history in one call — the god of its world needs no
approver's consent). For the agent it is a threat model: the same convenience in the
investigator's hands would let it fabricate approved state. The ruling that fell out:
the agent's runtime principal must be a role-scoped User, never the Administrator
token — least privilege has to hold at *both* layers, the tool registry in the
harness and the API principal underneath it. One probe, one sentence in the security
section that would otherwise have been discovered in production.

A third, quieter fact rounded the picture: backdated `posting_date` is taken as
given, so Frappe needs no custom-field detour for world dates — its documents' own
date fields already separate world time from the vendor's `creation` timestamp. The
same split Jira needed custom fields to achieve, Frappe gives away.

## 2026-08-23 — The box doesn't build: how a missing Docker image ruled the supply chain, and a reviewer tightened "pinned" into a digest

*M0 day 1, the frappe-up probe (PASS; detail in `probes/FINDINGS.md`). Written
2026-08-24 from the stream session log and FINDINGS. Feeds: the report's
ops/deployment section; candidate material for a post on supply-chain discipline at
hobby scale.*

The plan said "run Frappe HR in Compose on the box." The catch discovered en route:
**no official image carries the HR app.** `frappe/erpnext` ships without `hrms`, and
hrms requires erpnext — so somebody had to build a custom image, and the question
became *who and where*. The candidates: a one-time build on the box, builds from the
workstation, or CI as the only manufacturer. The first two died on the same
principle, now written into DESIGN: **production hosts consume artifacts, they never
manufacture them.** A box that builds its own images is a box whose running software
cannot be traced to a commit; a workstation build is the same problem with worse
reproducibility. So GitHub Actions builds the image from a pinned `frappe_docker`
commit (frappe 16.31.0 / erpnext 16.32.3 / hrms 16.16.0, `apps.json` fed in as a
BuildKit secret), pushes to GHCR — and the build took 4m36s against a 15-minute
estimate.

The sharpening came from outside: an external reviewer corrected the claim that
referencing the image by a version *tag* made it "pinned." A tag is mutable — whoever
can push the registry can move it, and the box would follow silently. The box now
references the image **by digest** (`FRAPPE_IMAGE=ghcr.io/…@sha256:…` in the box's
env file), which is immutable by construction; the `:16` and git-sha tags exist for
humans only. Updating means editing one line — an explicit act with a diff, never an
ambient drift. The correction was adopted the same day; the reviewer's other
suggestion (trigger builds only on image-input changes) turned out to already be the
workflow's shape.

One measured number worth keeping: the running stack's idle footprint with a site
installed is ~0.9 GB (box `used` 604 → 1,472 MB, `captures/frappe-up/`), against
Frappe's "8 GB recommended" sizing that had shaped early memory planning — recommended
sizing is not measured need, and the box's 16 GB holds two tenants comfortably.

## 2026-08-23 — Employees who never log in: the person model that dissolved the 10-user ceiling

*The world-shape rulings session (ruling 2 of five, written to DESIGN "The world's
shape") and the Jira probe that proved it the same day (PASS; detail in
`probes/FINDINGS.md`). Written 2026-08-24 from the stream session log and FINDINGS.
Feeds: the report's world-design section — likely its opening argument; the M0/M1
posts.*

The blocking question looked like a licensing problem: Jira Free allows 10 users, the
synthetic org wants 25–30 people, and buying seats for fake employees violates the
project's $0-tools constraint (org tools cost nothing; the spend is AWS and tokens —
Arda's line). Every path that treated synthetic people as *Atlassian accounts* was
some mix of expensive, fragile, and dishonest (a "dev instance" is licensed for
dev/testing only; shared accounts fake what they claim to test).

The ruling dissolved the problem instead of solving it: **synthetic employees are
domain entities, not vendor users.** In Jira they exist as values of a single-select
custom field (`Synthetic Owner`, keyed by employee id), `assignee` stays empty, and
actor identity — who *technically* wrote the comment, whose token created the issue —
sits outside the truth model entirely, as vendor plumbing. The 10-user ceiling
doesn't bind because the org consumes one service account, whatever its size. The
same model transferred unchanged to the HRIS (employees are `Employee` records keyed
by `employee_number`, the manager relation a domain link, one service User as
everyone's approver) and to Calendar (one OAuth principal owning one secondary
calendar per person). Three vendors, one identity rule.

The probe then proved Free holds up its end (`probes/captures/jira/`): the select
field created over REST and placed on screens, exact JQL per person
(`"Synthetic Owner" = "emp_001 — Probe Alice"` returns that person's issues and
nothing else), comments naming synthetic people round-tripping with the service
account as author — exactly as the actor-identity ruling expects — and an idempotent
second run. The one real limitation surfaced honestly: CSV import (the only way to
backdate Jira's own `created` timestamp) cannot set `resolutiondate`, is UI-only, and
its first attempt silently stamped import-time on every row because the wizard's
date-format field kept its default against the file's format — a silent fallback, not
an error. The consequence became a better ruling the next day: world dates live in
custom date fields the generator controls (`Opened On`, `Resolved On`), Jira's own
timestamps are hidden as vendor time, and the CSV import is demoted to cosmetics.
The vocabulary that keeps all of this straight — synthetic world → vendor
representation → domain-facing tools, with adapters that translate identity and
never launder a planted inconsistency — is Arda's framing, and it's the sentence the
report's world section should open with.

Figure: the three-layer diagram (world / vendor representation / domain tools) with
the person model crossing it — one synthetic employee shown as a field value in Jira,
an Employee record in the HRIS, a calendar id in Google, and *no user account
anywhere*.

---

*Candidates not yet written (material exists; write when a report or post needs it):*

- *M0 closes with every row verified, the non-blocking one too (2026-08-26) — Slack
  proved on the first run after a scripted-not-run interlude; the ruling to finish
  trailing probes rather than carry them, and the 90-day-history fact that makes
  Slack content a run-time write in the world generator. The cost line as an
  honesty anecdote: the design doc's ~$21 held and the working estimate of ~$18–19
  was the low guess (Pricing API, `probes/captures/instance/pricing.md`). Material:
  SESSION_LOG session 7, FINDINGS slack entry.*
- *The instance floor (2026-08-26) — the whole host from Terraform, the secrets rail
  (Origin CA pair as SecureString, read at boot by a path-scoped role), the
  Cloudflare-only security group, and the three interview rulings annotated lasting
  vs cheap. Material: SESSION_LOG session 5, FINDINGS instance entry.*

- *The hosting ruling (2026-08-22) — app on AWS, HRIS on the box, decided by the
  career-strategy gap's own wording; tombstoned extremes and the preregistered
  ephemeral-compute probe. Material: SESSION_LOG 2026-08-22 (design session part 1),
  DESIGN's hosting matrix.*
- *The three-lens review pivot (2026-08-23) — three independent review agents
  converged on "the world's shape is undecided," moving the next step from a probe to
  five rulings. Material: SESSION_LOG 2026-08-23 (calendar session).*
- *Calendar scopes measured, not assumed (2026-08-23) — `calendar.app.created` can
  create calendars it then cannot list; the working non-sensitive scope pair; the
  UTC-authoring slip as a timezone-distractor lesson. Material: SESSION_LOG +
  FINDINGS calendar entry.*
- *The vision method (2026-08-20→22) — grading SteamLens's vision with build
  hindsight, draft-then-interview, deploy-from-day-one as a mid-interview ruling.
  Material: SESSION_LOG founding entry, VISION.md.*
- *Probe day 0 as a teach-through (2026-08-22) — the AWS account bootstrapped with
  every term defined at first use; why the admin SSO user beats root. Material:
  SESSION_LOG day-0 entry, the AWS study file.*
