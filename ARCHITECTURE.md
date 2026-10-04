# ARCHITECTURE — leave-impact-agent

How it's built and why that structure — a narrative snapshot, edited in place.
Decisions and their rationale live in DESIGN (cited here by name); the pitch in
README.

*Snapshot at the world milestone's close, amended after the M1 repository audit and
through the investigator milestone's first six build steps · last updated
2026-10-04.*

## Design shape

One package per responsibility, ranked; a module imports only its own package or a
lower rank, and a few edges are denied on top of the ranks because they cross a trust
boundary the ranks alone would permit. One line per package, what it may import:

    app        →  agent, adapters, core            (demo milestone; reserved)
    agent      →  adapters, core
    evaluator  →  world, adapters, core
    validator  →  world, adapters, core
    generator  →  world, adapters, core
    adapters   →  world, core frappe · jira · calendar · corpus · prose — siblings apart;
                              transport (timeouts, the retry rule, the fault seam) beneath them;
                              world only for the sealed artifacts' names and document bytes
                              (object_store) and the organization parameters and generator
                              version a manifest records (manifest), never a scenario or a key
    world      →  core
    core       →  nothing inside the package

The rules, stated once:

- **Downward only.** `core` (rank 0) under `world` (1) under `adapters` (2) under the
  shells `generator`, `validator`, `evaluator`, `agent` (3) under `app` (4).
- **The investigator is blind to the benchmark.** `agent` and `app` never import
  `world`, `generator`, `validator` or `evaluator` — the answer key is unreachable at
  source level, not only by credential.
- **Shells never import one another.** The generator cannot reach the validator or the
  evaluator; read-only and non-echo are properties of the graph.
- **The domain does not know synthetic worlds exist.** `core` never imports `world`.
- **Pure below the adapters.** `core` and `world` perform no I/O.
- **One adapter, one external boundary.** Sibling adapters never import one another;
  a helper shared by all sits at the `adapters` level (`transport`: the HTTP session
  under the retry rule, where a request declares whether it is replayable).
- **Identity at composition.** An adapter takes a credential; it never embodies a
  principal.
- **Read-only is a module path.** The write ports live in `core/ports/write`, imported
  only by `adapters` and `generator`; the validator and the investigator are readers by
  construction, and the readers are re-exported from `core` while the writers are not.
- **World time is explicit.** `RunContext` carries `now`; the wall clock is read only
  at a composition root and converted into context at once.
- **The answer key has named readers.** `world.truth_decoder`, the one decoder of the
  truth manifest, is imported only by the modules the law names by full path: the
  generator's resume, the evaluator's world loading and the audit-sheet script. This
  gate alone scans the operator's programs under `scripts` and `probes` beside the
  package, and a named reader that no longer imports the decoder fails as a stale
  grant.

`tests/unit/test_import_law.py` holds every rule as a test, plus the ones that keep the
law from failing open: every package under `src` must hold a rank; relative imports are
banned because the edge scan cannot rank them; the top level holds only the package
docstring and the composition root, so no unranked module can launder an edge; and an
import is read with its aliases, so `from leaveimpact import world` names `world` as
plainly as its dotted path does. The rank table named `evaluator`,
`agent` and `app` ahead of their milestones; the first two were scaffolded at the
investigator milestone's first build step, `app` waits for the demo milestone.

### The life of a world

    seed + params + generator version
        │  pure semantic generation (world)
        ▼
    world spec · scenarios · truth fact base · keys · briefs
        │  materialization (generator ← adapters/prose): templates, LLM prose,
        │  the containment gate; accepted text frozen, failures discarded
        ▼
    the sealed bundle: world spec · scenario specs · truth manifest
    world version = the hash of the three, in order
        ├──► projectors (generator ← adapters) → Frappe · Jira · Calendar; the documents
        │        seal into the world bucket, and the app's PostgreSQL is a cache the
        │        loader fills from them (investigator milestone; unfilled today)
        │        └──► world manifest (adapters/manifest): the resolved adapter
        │             configuration, one locator per projected id, the world version
        │             and digests — the projection's receipt and checkpoint, staged
        │             preparing → projected, written after vendors mint ids, never hashed
        ├──► world bucket: world manifest, scenario specs, documents (app-readable)
        └──► truth bucket: world-spec/ (validator + evaluator) ·
        │                  truth-manifest/ (evaluator only); the app reads neither
        ▼
    validator re-reads the live systems, re-derives structured expectations,
    compares with the world spec — reads the spec and the systems, never the keys

The seed identifies the semantic specification; the frozen bundle identifies the
realized world (DESIGN, "The generator: pure specification, materialized prose, frozen
world"). Every later artifact — an evaluation run, a report — records the world version
and the truth digest, so a number months later is the same question about the same
world.

## Module responsibilities

Signatures live in the docstrings, rendered by `scripts/regen_docs.py`; this table is
the map.

| package | single responsibility |
|---|---|
| `core` | the domain, pure: types, ids, the predicate registry, the claim vocabulary with its grading keys, `RunContext`, the deterministic rules (viability, authority table, closure, constraint checks), the ports two consumers share — readers and writers in two modules, observed entities crossing, facts derived inside; since the investigator milestone's second build step also what the agent writes and the evaluator reads, since neither may import the other: `entities_json` the one codec of the seven observable kinds and the observed record (lifted from the world's spec codecs, which call it), `timeshape` the canonical shapes of a date, a zoned instant and a span, `provenance` the model configuration, `run_trace` / `run_record` / `run_export` the run export as plain data (operations with their six outcomes, compact model calls, the provenance block, the self-identifying root under a format version), `run_export_json` its codec under the one byte rule with a bytes decoder that accepts only what re-encodes to itself, `pricing` the price table and the exact integer cost arithmetic, `tools` the method table, the thirteen tool specifications in canonical order, generic validation, schema generation and the tool-surface digest; since its fourth build step `coverage`, the slices of a source an answer can live in and where each predicate's facts are kept, with the proof every closure answer now carries (the facts, the gaps and each slice asked about), and `read_coverage`, the one mapping from a trace's operations to what they observed, kept here because the evaluator replaying a run and a harness concluding from its own reads need the same mapping and may not import each other; since its fifth build step the rest of what those two must compose the same way: `readings` the reading pass (grounding and viability of each impact) and the composing pass (each impact's need, requirements, required count and outcome), `read_condition` the condition a run's reads show, `read_projection` the structured projection of a trace's reads (each record as first returned, the usable ones derived and dated, a record no fact can be made from withdrawn and named, the view a system that reads no prose concludes from), `closure.citable_record` the record a witness can be cited by, `prefetch` the frozen prefetch as data with its planner, chunking by each tool's own bound, and the rule's digest, and `worldtime`'s day-span-to-instants conversion the planner needs; since its sixth build step the preregistration both of them read: `registration` the registration as plain data (draft or frozen, typed pending values on declared fields, three system types under a kind tag, the outage schedule with its computed digest, the arms, run accounting, the statistics by name, the prefetch, caps and budget each with what stands behind its numbers, the scenario sets) and `registration_json` its strict codec, one written form, a bytes decoder that accepts only what re-encodes to itself; since the contract step what a model states and what becomes of it, again because the harness and the evaluator's replay need one reading and may not import each other: `stated` the stated fact (one of five predicates, its carrier, a verbatim quote, a requirement's target span) with what it holds at construction and its three statuses as three types (emission, admission, placement), `anchors` the lexical anchor table with the surface form and the lexicon it reads, lifted from the world's prose vocabulary, read one way by the generator's gate and another by the quote guard, with the one presence test and the table's digest, `binding` the span binding by exact title equality over the distinct artifacts a run read, `stated_view` the total join of the structured projection with the admitted statements (the readings that cannot stand together left out with a reason), and `stated_json` their codec |
| `world` | the benchmark, pure: the organization, the seeded plan, scenario classes and modifiers under the construction invariants, world assembly with the whole-world re-verification, truth facts with dated provenance, keys, the three artifacts in canonical bytes, the world version over them and the semantic digest of what the seed determines; the truth manifest's own types, projection and encoder in `artifacts` and its decoder alone in the gated `truth_decoder`, bytes accepted only when their re-encoding reproduces them; `runtime_view` the facts a run can obtain at its run day, and in `construction` the expectations (the conflicts and the unknowns a key holds) derived from `core`'s reading pass, which construction, assembly and the evaluator's oracle share since the fifth build step moved the pass itself into `core`; `prose` the vocabulary of materialized text — propositions, the derived namespace, the materialization record, and the lexical anchors named again from `core`, where they moved at the contract step — `briefs` the typed pending targets a model writes and the pre-compose contract, `composition` the pure placement of accepted prose into the semantic world and the composed world's own invariant |
| `adapters` | one external boundary per subpackage — `frappe`, `jira`, `calendar`, `corpus`, `prose` — translating vendor shape and identity to `core` types, never laundering a fact (`prose` is the Converse translation for the writer and the checker behind a request-shaped seam, `seam` the request and answer types with the closed faults and `bedrock` the one call; prompt policy stays the generator's); `transport` beneath them carries timeouts, the retry rule and the fault seam; `filestore` is the byte primitive under every local artifact, one file replaced whole or not at all; `manifest` beside them is the world manifest, the configuration-and-receipt contract every reader of a projected world decodes; `object_store` is the bucket the sealed world lands in — `read` the capability every consumer holds, `write` the generator's alone under the import law, `s3` and `local` the readers of the two backends, `s3_write` and `local_write` their gated writer subclasses; `layout` the key of every sealed object, `documents` the sealed documents read by id and enumerated, `documents_write` the projector's gated writer over them; `wiring` beside them is the read side both shells share — the deployment from the environment, the stores as readers, the four readers from a manifest, and the one verdict-publication callable that closes over the only writer a validator run touches |
| `generator` | the generation job: `materialize` is the attempt loop that writes every pending brief, gates each draft and keeps the record and the run's metrics, `guards` the three containment checks as pure functions, `prose` the prompt policy — the assets as package data with pinned digests, the render from a brief to the two requests, the checker's tool generated from the registry and the parse of what it filled; `fresh` the stage every fresh run shares before any external write (assemble, materialize, compose, bundle), the job's first half and the whole of the audit sheet's throwaway mode; `resume` rebuilds and proves a sealed realization from the truth bucket so sealing continues from its checkpoint, reading the sealed materialization record through `world`'s gated truth decoder as one of its named readers, `probe` the one-call-per-model check the probe workflow runs under the generator role; `projection` writes the frozen world restart-safe on each system's identity guarantee, `realize` is the composition root that checkpoints every calendar and receipt into the manifest and promotes it only after the site inspections and the coverage proof, `systems` wires the real adapters, `manifest_store` checkpoints the manifest to a file atomically or to the bucket's mutable prefix; `sealing` drives the ruled order — truth first, the site preparation and the vendor projection with the documents after its postflight, the scenario specs, every object read back, the manifest last with every version id; `recipe` the world recipe as plain data, what defines a world plus the prose stage's two run controls, apart from the boundary that parses it so the fresh stage loads no store on import; `entrypoint` is the configuration boundary (the recipe from the command line, the deployment from the environment, the stores it names), `metrics` the checkpoint timer at the shell, `__main__` the job |
| `validator` | read-only verification that projection realized the declared world: `verify` the integrity chain and the three layered checks, `verdict` the artifact, `entrypoint` the request from the command line and the composition that reads the sealed world, judges the live systems and publishes through the wiring's callable, `__main__` the job |
| `evaluator` | grades recorded runs against the sealed truth in the frozen claim vocabulary, key match and payload apart, grounding as `core`'s rules replayed over the run's own reads; never re-reads a vendor, which is the validator's job before any run. The grading, since the investigator milestone's third build step: `sealed_world` loads the three sealed files through the object-store reader, joins them by scenario, proves the cited digests and the world version and reproduces every sealed key with assembly's whole-world re-verification, refusing the world whole with a message that carries no sealed content; `oracle` derives what the rules conclude under a condition over runtime truth through `core`'s composing pass, anchored on the sealed key under the normal condition, or states that no answer exists (the leave unreadable, the policy unreadable); the condition a run ran under is `core`'s `read_condition` since the fifth build step; `characterization` compares the dated view's complete answer with runtime truth's, per world and condition; `rows` is the grade as plain data, one typed record per expected or reported claim with expectation, presence, standing and payload apart, and `matching` writes it; `plan_checks` asks plan validity against the oracle, coherence within the report and coverage, one record per omission; `grading` gives every export one outcome, graded, limited or excluded, and reads whether a graded report is correct whole off its rows. What a run's own reads support, since the fourth build step: `world_index` is the sealed world by identity (every record, every comment and section, the facts each carries, the statements and their carriers, each requirement clause's scope with the proof that the clause's text states it); `observed_view` lays the sealed overlay over `core`'s structured projection of the run's reads (the prose a returned carrier admits, the comparison of every returned record with the sealed one) and reports every difference as an integrity finding; `plan_reading` is the one reading of a plan that coherence and the replay share; `replay` gives each claim its standing on premises taken from the run, `grounded` derives the end-to-end and the strict readings from its records, `citations` judges each evidence reference on three axes. What a run did: `trace_metrics` is the entry that returns the outcome with the metrics beside it, from `source_discipline` (one row per operation, the findings no conforming harness records), `cost_check` (usage and cost recomputed in three layers), `proof_contribution` (which reads first supplied what a proof rests on), `retrieval_targets` (the statements an answer depends on, by removal through the oracle) and `retrieval` (which of them a run's reads returned). Tables: `cells` groups evaluated runs by system and assigned condition with the scenario as the unit and keeps the accounting, `measures` and `evidence_measures` state each ratio as one run's numerator and denominator with its scope, `intervals` holds Wilson and the seeded tier-stratified bootstrap, `tables` estimates a measure or a check in a cell, pairs two systems and keeps the cost ledger; what the preregistration fixes is an argument to these and chosen nowhere in them. Under the registration, since the sixth build step: `attempts` reads a run's attempts as a history (the counted attempt by the registered rule, the gap, the excess attempt and the attempt after a stopping outcome); `run_checks` holds the three checks a registration can name; `registered` resolves the registration's names against the registries here, projects the plan the tables are cut under, cuts the scenario sets and makes the seeded development draw; `diagnostics` holds repeat consistency and the degraded table, raw counts both; `analysis` computes every registered table from a set of evaluated runs in one pure pass; `prefetch_conformance` checks a trace's prefetch reads against obligations reconstructed from what each read returned, a sixth part of the trace metrics. The artifact: `artifact` is one evaluation as plain data and the pure function that makes it (every stored object listed with its version, digest, cost and one reason, eligibility on the registration's bytes and the recorded settings, the label derived from the registration); `artifact_json` its written form, an encoder derived from the types with no decoder, held by a format version and a pinned list of key paths. The job: `repository` reads the job's own checkout through git (a clean tree, the registration at a cited commit, the implementation paths changed since the registration), `entrypoint` holds the two commands as compositions over readers (prove a world, evaluate its stored runs), and `__main__` composes them from the environment and prints what a public log may hold; the workflow is `evaluate-run.yml` |
| `agent` | the investigator and the two preregistered baselines it is measured against (rules-only, single-shot), over the read ports alone, claims in the frozen vocabulary, a plan a human approves; the loop's framework contained inside the package. Since the investigator milestone's fifth build step: `execution` is the one path for a declared tool call (validation, the port and the method, one recorded operation with one of the six outcomes, a model's refusal recorded and the prefetch's raised, a source stopped at its first unreachable answer) and the prefetch run over it; `rules_only` the first system (the prefetch, the structured projection as its whole view, a defect at its operation or an abstention with no claims, the shared rules through `core`'s composing pass); `report` the one reporting policy that writes the rules' conclusions as claims; `export` the run as the artifact the evaluator grades, under the provenance the harness supplies; since the sixth build step `registered` builds that provenance from the decoded registration and refuses an unregistered arm, a pending variant, or an outage protocol, a prefetch or a reporting policy other than this code's. The event log lands at step 8, the registry at 10, the graph at 11 |
| `app` | reserved — the demo surface (demo milestone) |

## A rank law alone would have let the investigator read the answer key

**Denied edges sit above the ranks.** The first cut of the layout was a plain rank
order, `world` at rank 1 and `agent` at rank 3, which made `from leaveimpact.world
import truth` a legal import in the investigator. Credentials would still have kept the
truth bucket out of reach at run time, but the whole answer-key design (DESIGN, "The
answer-key contract") rests on the agent working only from what landed in the systems,
and a boundary that only the deployment enforces is a boundary the test suite cannot
see. The law therefore has two parts: ranks for the default direction, and an explicit
denied-edge table for the trust boundaries. The same reasoning promoted the validator
to its own package: inside `generator`, nothing could have stopped a validator module
from importing a projector, and "read-only" would have been a comment.

**`world` stays apart from `core` however small it is.** The two hold different kinds
of things — what the real system believes, and what exists only because the world is
constructed — and the production investigator should depend on the first without
depending on the second. A merged package would keep the files apart and lose the
property.

## Deliberately not done (restraint)

- **`app` is named, not created.** Empty placeholder packages would be structure for
  its own sake; each milestone scaffolds its own after its own design session.
  `evaluator` and `agent` were scaffolded at the investigator milestone's first build
  step, each holding its contract docstring and nothing else until its first module
  landed, and both hold modules now; `app` waits the same way for the demo milestone.
- **The purity guard is a banned-import list, not an allowlist.** It catches the
  libraries this project actually uses for I/O and misses `open()`; the pure packages
  are also reviewed as pure. Revisit if the guard ever proves thin in review.
- **The generator-version rule is enforced by a snapshot pair, not proven in general.**
  A recorded digest of the vocabulary tables and a recorded interpreter minor version
  fail the suite when either changes, so the fix lands in the same file as the version
  and the diff shows whether the version moved. Since the bundle step, a reference
  seed's world version is recorded beside the generator version as a pair in the tests:
  a changed hash with an unchanged version fails, which catches an unbumped change to
  the drawing algorithm too; re-cutting the pair is the deliberate act that accompanies
  a bump. What no test can catch is a change that leaves the reference world's bytes
  untouched — that stays with review.
- **No ports beyond the four the generator and investigator share.** The prose
  renderer has one consumer and stays a seam inside its adapter. A port is added when a
  second consumer appears, not before. The write side of each port has one production
  consumer and is declared anyway — for the least-privilege type the import law enforces
  and the in-memory implementation under `tests`, not for symmetry.
