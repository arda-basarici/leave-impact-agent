# Report notes — Leave Impact Agent

Raw material for milestone reports and posts: decision narratives distilled at the
moment they happen, so the reports can tell the story without excavating chat logs.
Append-only, newest first. Each entry is a self-contained story with its date and the
decisions it feeds.

---

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
