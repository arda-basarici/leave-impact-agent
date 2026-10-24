# The golden world, released

The three sealed objects of the first golden world, the one the demo serves and replays,
exactly as the generator sealed them on 2026-09-16 and as the two buckets hold them.
Released with the demo (the demo milestone's second entry ruling): the demo publishes the
world's prose on every page, so its scenario specs and answer keys are published beside
it. Nothing of the measurement world is here; that world stays embargoed until the last
measurement on it, and this repository's evaluation refuses to run if its digests appear
anywhere in the tree.

| field | value |
|---|---|
| world version | `7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4` |
| generator version | 14 |
| recipe | seed 16, world start 2026-01-05, plan `golden`, public |
| semantic digest | `17428de2544546b44442bc0c3a4fad05e0f533f7599e053ca99fc2c65bcbb67a` |
| disclosure | open |
| scenarios | 30 |
| HR site | `hr-w3` (projected; the demo's live runs read it, no visitor does) |

| file | bucket key | bytes | sha256 |
|---|---|---|---|
| `world-spec.json` | truth bucket, `world-spec/<version>.json` | 48,668 | `7800015e1207a7ac03b56d550693c377d517d1703b4354518a5bf87e1d32fdb0` |
| `scenario-specs.json` | world bucket, `worlds/<version>/scenario-specs.json` | 6,198 | `67975c51be3dd4c5eeb93fecee992a0fc7f969e2947c31d6edf681f1bef3a0ef` |
| `truth-manifest.json` | truth bucket, `truth-manifest/<version>.json` | 181,476 | `24fed413b3222818abe39f361894fed10d4ca2b15c5c2e38ca504a1db189ee41` |

## What each file holds

- **`world-spec.json`**: the organization (people, teams, components, skills), the plan's
  thirty rows, and every planting with its observable-from date: leaves, work items with
  their comments, calendar events, documents with their sections. Its provenance names the
  seed and the recipe, and it cites the other two files by digest.
- **`scenario-specs.json`**: the thirty rows a run is asked, and nothing more: the scenario
  id, the leave under investigation, the instant `now`, the reference timezone and the
  window. This is the one object of the three the application's own reader is granted.
- **`truth-manifest.json`**: the answer keys. Per scenario its tier, class and modifiers,
  the expected impacts with their verdicts, the constraints, the distractors, the required
  sources, the expected conflicts and unknowns, the facts only the world could plant and
  the briefs its model-written texts were asked to carry; then the dated world-level fact
  base and the record of how each text was accepted. The evaluator grades against this
  file and the application never reads it.

The world version is the SHA-256 over the three files' canonical bytes in the order above
(`leaveimpact.world.artifacts.world_version`), so the version is a check on the files: the
unit test `tests/unit/test_golden_release.py` joins the three committed files through the
evaluator's own loader and requires the recomputed version to equal the version the demo
configuration serves. `scripts/accept_golden_release.py` compares the committed bytes with
the buckets' under the administrator profile; its first run is recorded in FINDINGS
(`golden-release`).

## Reading it as a human

The audit sheet is the one rendering of the three files for a human reader, scenario by
scenario in the plan's order, keys included (`AUDIT_METHODOLOGY.md`;
`docs/examples/audit_sheet_throwaway.md` shows its shape on a throwaway world). Render it
from these files, with no bucket access:

    uv run python scripts/audit_sheet.py --released docs/golden-world

The sheet lands as `data/audit/audit_sheet_7b806ed6.released.md`, under a folder the
repository ignores, since it is regenerable. Its outcome witness is proven from the sealed
files: the evaluator's loader joins the three and requires today's rules to reproduce
every sealed key. The sheet the audit itself read on 2026-09-19 rebuilt the semantic world
from the seed with the generator of that day (version 14) and verified the semantic digest
equal; the generator has moved since (version 19 assembles another world from seed 16),
so that rebuild is no longer available from the current tree, and the audit day's sheet
stays bound by digest in the audit's sealed index.

## What releasing the keys changes

The golden world has been read end to end by the people who built the investigator, and
its replays are labelled development runs for that reason; releasing its keys changes no
claim. The numbers on the results page come from a different, withheld world. A reader who
wants a world nobody tuned against is the revisit trigger the entry ruling names.
