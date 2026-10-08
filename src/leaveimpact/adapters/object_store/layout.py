"""The key layout of a sealed world in the two buckets: one function per object, no literal outside.

The bucket contract (the platform's README row for this project) fixes the prefixes and
their policy: in the world bucket ``worlds/<version>/…`` is final and create-only and
``preparing/<version>/…`` is mutable and never served; in the truth bucket
``world-spec/<version>.json`` and ``truth-manifest/<version>.json`` are final and
create-only. What is under a final prefix, by name, is this module's, and the generator
and every reader take the key from here so a rename is one edit and a wrong key cannot
be typed twice. The version is the world version, the digest of the sealed bundle, so
every key is content-addressed: the same world seals to the same keys on every run,
which is what lets a restart hit the equal case instead of a conflict.

The sealing order (the step 12 rulings) reads off the layout: the two truth objects
first, then the vendor projection with its checkpoint at the preparing key, then the
documents, the scenario specs and the levels under the final world prefix, and the world
manifest last, so an object under ``worlds/`` with a manifest beside it is a completed projection
by construction. Verdicts are the validator's, immutable per execution, keyed by the
GitHub run id and attempt since a rerun shares the id.

Two more prefixes belong to the measurement and not to a world's sealing. ``runs/<version>/``
in the world bucket holds the application's exports of finished runs, final and
create-only, outside ``worlds/`` so the application's read surface stays the served
worlds; what is under one run's own prefix is the application's to name, and a reader
lists the version's prefix whole. ``evaluations/<version>/`` in the truth bucket holds
the evaluator's artifacts, one per execution, keyed like a verdict: an evaluation says
which claims matched the key, so it lives beside the key.
"""

from __future__ import annotations

from leaveimpact.core.ids import DocumentId, WorldVersion, is_numbered_id
from leaveimpact.world.artifacts import LEVELS, SCENARIO_SPECS, TRUTH_MANIFEST, WORLD_SPEC

WORLD_MANIFEST = "world-manifest.json"
"""The manifest's file name under a world's prefix, and at its checkpoint."""


def world_spec_key(version: WorldVersion) -> str:
    """Truth bucket: the planted world, benchmark-private."""
    return f"world-spec/{version}.json"


def truth_manifest_key(version: WorldVersion) -> str:
    """Truth bucket: every key and the dated fact base, evaluator-only."""
    return f"truth-manifest/{version}.json"


def worlds_prefix() -> str:
    """World bucket: the prefix every served world sits under, what the application lists."""
    return "worlds/"


def world_prefix(version: WorldVersion) -> str:
    """World bucket: everything of one projected world, final and create-only."""
    return f"worlds/{version}/"


def scenario_specs_key(version: WorldVersion) -> str:
    """World bucket: the agent-visible scenario rows.

    The one name under ``worlds/`` that is not this module's alone to change: the
    evaluator's role is granted a get on exactly this object and nothing else there (the
    platform's contract row for the role), so a rename is a change to that role first.

    >>> scenario_specs_key(WorldVersion("ab" * 32))
    'worlds/abababababababababababababababababababababababababababababababab/scenario-specs.json'
    """
    return world_prefix(version) + SCENARIO_SPECS


def levels_key(version: WorldVersion) -> str:
    """World bucket: the levels and the pool's order, what the corpus cache filters by."""
    return world_prefix(version) + LEVELS


def world_manifest_key(version: WorldVersion) -> str:
    """World bucket: the projection's commit record, written last."""
    return world_prefix(version) + WORLD_MANIFEST


def documents_prefix(version: WorldVersion) -> str:
    """World bucket: the canonical documents, one object each, the corpus's source."""
    return world_prefix(version) + "documents/"


def document_key(version: WorldVersion, id: DocumentId) -> str:
    """World bucket: one canonical document by its domain id."""
    return f"{documents_prefix(version)}{id}.json"


def document_id_of(version: WorldVersion, key: str) -> DocumentId | None:
    """The domain id a document key under ``version`` names, or ``None`` for any other key.

    A key is a document's only when its stem is a document id in the domain's grammar —
    ``doc_`` and a number — so an object named after another kind's id, or after nothing
    the domain knows, is a malformed key to the reader and never a foreign document.

    >>> v = WorldVersion("ab" * 32)
    >>> document_id_of(v, document_key(v, DocumentId("doc_007")))
    'doc_007'
    >>> [document_id_of(v, documents_prefix(v) + name) for name in ("notes.txt", "emp_001.json")]
    [None, None]
    """
    prefix, suffix = documents_prefix(version), ".json"
    if not (key.startswith(prefix) and key.endswith(suffix)):
        return None
    stem = key[len(prefix) : -len(suffix)]
    if not (stem.startswith("doc_") and is_numbered_id(stem)):
        return None
    return DocumentId(stem)


def checkpoint_key(version: WorldVersion) -> str:
    """World bucket, mutable: the manifest while the projection prepares."""
    return f"preparing/{version}/{WORLD_MANIFEST}"


def verdicts_prefix(version: WorldVersion) -> str:
    """World bucket: every validator execution's verdict for the world."""
    return world_prefix(version) + "verdicts/"


def verdict_key(version: WorldVersion, run_id: str, run_attempt: str) -> str:
    """World bucket: one execution's verdict; a rerun shares the run id, never the attempt.

    >>> verdict_key(WorldVersion("ab" * 32), "34724172889", "2").rsplit("/", 1)[1]
    '34724172889-2.json'
    """
    return f"{verdicts_prefix(version)}{run_id}-{run_attempt}.json"


def runs_prefix(version: WorldVersion) -> str:
    """World bucket: every stored export of a run on ``version``.

    >>> runs_prefix(WorldVersion("ab" * 32))[:9]
    'runs/abab'
    """
    return f"runs/{version}/"


def run_prefix(version: WorldVersion, run_id: str, attempt: int) -> str:
    """World bucket: one attempt's own prefix under the runs of ``version``, the contract's
    stable shape (``<run-id>-<run-attempt>/``); what sits under it is the application's.

    >>> run_prefix(WorldVersion("ab" * 32), "37135207381", 2).rsplit("/", 2)[1]
    '37135207381-2'
    """
    return f"{runs_prefix(version)}{run_id}-{attempt}/"


def run_export_key(version: WorldVersion, run_id: str, attempt: int, reader_commit: str) -> str:
    """World bucket: the export of one closed attempt as the reader at ``reader_commit``
    built it. A closed log is one and the export is a function of the log and the reader,
    so one key holds one possible content; a repair under another reader is another key,
    which is how a correction is an explicit new version and never an overwrite (the
    event log step's ruling on an export that will not construct, part 7).

    >>> run_export_key(WorldVersion("ab" * 32), "37135207381", 1, "c" * 40).rsplit("/", 1)[1]
    'export-cccccccccccccccccccccccccccccccccccccccc.json'
    """
    return f"{run_prefix(version, run_id, attempt)}export-{reader_commit}.json"


def inventory_prefix(version: WorldVersion) -> str:
    """World bucket: every inventory the harness wrote of its runs on ``version``, under the
    runs prefix because that is the one prefix the instance may put under and the
    evaluator lists and reads whole; no run id has this shape, so no run's prefix is
    shadowed. A reader of the runs prefix excludes it from the exports.

    >>> inventory_prefix(WorldVersion("ab" * 32)).rsplit("/", 2)[1]
    'inventory'
    """
    return f"{runs_prefix(version)}inventory/"


def inventory_key(version: WorldVersion, digest: str) -> str:
    """World bucket: one inventory, named by the digest of its bytes, which is its identity.

    >>> inventory_key(WorldVersion("ab" * 32), "d" * 64).rsplit("/", 1)[1][:8]
    'dddddddd'
    """
    return f"{inventory_prefix(version)}{digest}.json"


def evaluations_prefix(version: WorldVersion) -> str:
    """Truth bucket: every evaluation of runs on ``version``."""
    return f"evaluations/{version}/"


def evaluation_key(version: WorldVersion, run_id: str, run_attempt: str) -> str:
    """Truth bucket: one execution's evaluation; a rerun shares the run id, never the attempt.

    >>> evaluation_key(WorldVersion("ab" * 32), "37135207381", "1").rsplit("/", 1)[1]
    '37135207381-1.json'
    """
    return f"{evaluations_prefix(version)}{run_id}-{run_attempt}.json"


__all__ = [
    "SCENARIO_SPECS",
    "TRUTH_MANIFEST",
    "WORLD_MANIFEST",
    "WORLD_SPEC",
    "checkpoint_key",
    "document_id_of",
    "document_key",
    "documents_prefix",
    "evaluation_key",
    "evaluations_prefix",
    "inventory_key",
    "inventory_prefix",
    "run_export_key",
    "run_prefix",
    "runs_prefix",
    "scenario_specs_key",
    "truth_manifest_key",
    "verdict_key",
    "verdicts_prefix",
    "world_manifest_key",
    "world_prefix",
    "world_spec_key",
]
