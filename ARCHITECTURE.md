# ARCHITECTURE — leave-impact-agent

How it's built and why that structure — a narrative snapshot, edited in place.
Decisions and their rationale live in DESIGN (cited here by name); the pitch in
README.

*Snapshot at the world milestone's build, step 8 · last updated 2026-09-12.*

## Design shape

One package per responsibility, ranked; a module imports only its own package or a
lower rank, and a few edges are denied on top of the ranks because they cross a trust
boundary the ranks alone would permit. One line per package, what it may import:

    app        →  agent, adapters, core            (demo milestone; reserved)
    agent      →  adapters, core                   (investigator milestone; reserved)
    evaluator  →  world, adapters, core            (investigator milestone; reserved)
    validator  →  world, adapters, core
    generator  →  world, adapters, core
    adapters   →  core        frappe · jira · calendar · corpus · prose — siblings apart;
                              transport (timeouts, the retry rule, the fault seam) beneath them
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

`tests/unit/test_import_law.py` holds every rule as a test, plus the ones that keep the
law from failing open: every package under `src` must hold a rank; relative imports are
banned because the edge scan cannot rank them; the top level holds only the package
docstring and the composition root, so no unranked module can launder an edge; and an
import is read with its aliases, so `from leaveimpact import world` names `world` as
plainly as its dotted path does. The rank table names `evaluator`,
`agent` and `app` ahead of their milestones; they are not created until then.

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
        ├──► projectors (generator ← adapters) → Frappe · Jira · Calendar · corpus
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
| `core` | the domain, pure: types, ids, the predicate registry, the claim vocabulary with its grading keys, `RunContext`, the deterministic rules (viability, authority table, closure, constraint checks), the ports two consumers share — readers and writers in two modules, observed entities crossing, facts derived inside |
| `world` | the benchmark, pure: the organization, the seeded plan, scenario classes and modifiers under the construction invariants, world assembly with the whole-world re-verification, truth facts with dated provenance, keys, the three artifacts in canonical bytes and the world version; briefs and templates when prose arrives |
| `adapters` | one external boundary per subpackage — `frappe`, `jira`, `calendar`, `corpus`, `prose` — translating vendor shape and identity to `core` types, never laundering a fact; `transport` beneath them carries timeouts, the retry rule and the fault seam; `manifest` beside them is the world manifest, the configuration-and-receipt contract every reader of a projected world decodes |
| `generator` | the generation job: materializes prose under the containment gate; `projection` writes the frozen world restart-safe on each system's identity guarantee, `realize` is the composition root that checkpoints every calendar and receipt into the manifest and promotes it only after the site inspections and the coverage proof, `systems` wires the real adapters, `manifest_store` replaces the file atomically; seals the artifacts |
| `validator` | read-only verification that projection realized the declared world |
| `evaluator` | reserved — grades runs against truth (investigator milestone) |
| `agent` | reserved — the investigator (investigator milestone) |
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

- **`evaluator`, `agent`, `app` are named, not created.** Empty placeholder packages
  would be structure for its own sake; each milestone scaffolds its own after its own
  design session. Revisit at the investigator milestone's entry.
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
