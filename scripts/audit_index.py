"""The hand audit's index: one small canonical JSON object binding the audit's files by digest.

A hand audit produces a separately versioned provenance artifact that lives in the truth
bucket beside the world it judged (DESIGN, the sealing section). The artifact is three
files a human wrote or ruled over: the rulings record (the audit's history, never
rewritten), the summary (the authoritative reading, with its ledger of superseded
readings) and the checklist (what "audited" meant when the audit ran). This script builds
the index that binds them: their digests, the digest of the sheet they read, the world's
sealed provenance, and the declarations only the auditor can make (the verdict the
validator issued, which scenarios were deep-traced and in which tranche, the coverage
notes, the dates, and which earlier audit this one supersedes).

The index's own digest is the audit's identity: the prefix under which the three files
and the index are written once to the truth bucket is
``audit/<world-version>/<index-digest>/``. The identity is content-addressed, like every
key in the layout, and never an ordinal: a corrected audit is a new digest beside the old
with ``supersedes`` naming the old one, the way the stream treats worlds. The index cannot
contain its own digest, so the file digests are computed first, the completed object is
serialized through the repository's one byte rule (``canonical_bytes``: fixed field order,
compact separators, UTF-8 through), and the bytes are hashed.

Three modes. ``build`` reads the declaration the auditor wrote
(``data/audit/index_declaration_<v8>.json``), the four local files and the sealed world spec
(for the full semantic digest, seed, plan and generator version, under the SSO profile),
and writes ``data/audit/index_<v8>.json``, printing the identity. ``verify`` re-hashes the
local files against a written index and re-hashes the index itself, so the identity can be
checked before upload and after. ``upload`` seals the audit: after a passing verify, the
index and the three files it binds go under ``audit/<world-version>/<index-digest>/``
through the sealer's conditional create (the object-store writer's ``put_if_absent``: a
key already holding these bytes is accepted as present and equal, one holding other bytes
refuses, a plain put is refused by the bucket policy), each object read back and re-hashed
against the local digest, the version ids printed for the stream's audit folder. The
sheet is not uploaded: it is regenerable and its digest is in the index. The object names
under the prefix are this script's and may move; the index binds the files by digest, so
a reader verifies by content, never by name. The truth bucket's ``audit/`` prefix became
create-only on 2026-09-19 (the platform ticket of 2026-09-17, its probe passed). This is a
human-run tool under the SSO profile, outside the application's import law; the writer
is imported inside ``upload`` alone.

Usage: ``python scripts/audit_index.py build <world_version>`` with ``AWS_PROFILE`` set;
``python scripts/audit_index.py verify <world_version>`` offline;
``python scripts/audit_index.py upload <world_version>`` with ``AWS_PROFILE`` set.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from leaveimpact.core.jsonshape import canonical_bytes

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")
AUDIT_DIR = Path(__file__).resolve().parent.parent / "data" / "audit"

SCHEMA_VERSION = 1

DECLARED_FIELDS = (
    "verdict_key",
    "sheet_digest_acceptance_pass",
    "overall_verdict",
    "traced_stratified",
    "traced_targeted",
    "coverage_notes",
    "audit_started",
    "audit_completed",
    "supersedes",
)
"""What only the auditor can state; every other field is computed or read from the seal."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_files(version: str) -> dict[str, Path]:
    """The four local files the index binds, by the role each plays."""
    short = version[:8]
    return {
        "rulings": AUDIT_DIR / f"rulings_{short}.md",
        "summary": AUDIT_DIR / f"summary_{short}.md",
        "checklist": AUDIT_DIR / "AUDIT_CHECKLIST.md",
        "sheet": AUDIT_DIR / f"audit_sheet_{short}.md",
    }


def index_path(version: str) -> Path:
    return AUDIT_DIR / f"index_{version[:8]}.json"


def declaration_path(version: str) -> Path:
    return AUDIT_DIR / f"index_declaration_{version[:8]}.json"


def load_declaration(version: str) -> dict[str, Any]:
    declared = json.loads(declaration_path(version).read_text(encoding="utf-8"))
    if set(declared) != set(DECLARED_FIELDS):
        raise ValueError(
            f"the declaration holds exactly {DECLARED_FIELDS}, got {tuple(sorted(declared))}"
        )
    return declared


def sealed_provenance(version: str) -> dict[str, Any]:
    """The world's provenance as sealed in the truth bucket's world spec."""
    import boto3

    from leaveimpact.adapters.object_store.layout import world_spec_key
    from leaveimpact.core.ids import WorldVersion

    s3 = boto3.session.Session(region_name=REGION).client("s3")
    body = s3.get_object(Bucket=TRUTH_BUCKET, Key=world_spec_key(WorldVersion(version)))["Body"]
    prov = json.loads(body.read())["provenance"]
    return {
        "semantic_digest": prov["semantic_digest"],
        "seed": prov["seed"],
        "plan": prov["plan_name"],
        "generator_version": prov["generator_version"],
    }


def build_index(version: str, declared: dict[str, Any], sealed: dict[str, Any]) -> dict[str, Any]:
    """The index object in its fixed field order; the digests of the files come first so the
    object never depends on its own bytes."""
    files = audit_files(version)
    digests = {role: sha256_of(path) for role, path in files.items()}
    return {
        "schema_version": SCHEMA_VERSION,
        "world_version": version,
        "semantic_digest": sealed["semantic_digest"],
        "seed": sealed["seed"],
        "plan": sealed["plan"],
        "generator_version": sealed["generator_version"],
        "verdict_key": declared["verdict_key"],
        "sheet_digest_acceptance_pass": declared["sheet_digest_acceptance_pass"],
        "sheet_digest_witness": digests["sheet"],
        "checklist_digest": digests["checklist"],
        "rulings_digest": digests["rulings"],
        "summary_digest": digests["summary"],
        "overall_verdict": declared["overall_verdict"],
        "traced": {
            "stratified": list(declared["traced_stratified"]),
            "targeted": list(declared["traced_targeted"]),
        },
        "coverage_notes": list(declared["coverage_notes"]),
        "audit_started": declared["audit_started"],
        "audit_completed": declared["audit_completed"],
        "supersedes": declared["supersedes"],
    }


def identity_of(index_bytes: bytes) -> str:
    return hashlib.sha256(index_bytes).hexdigest()


def build(version: str) -> int:
    index = build_index(version, load_declaration(version), sealed_provenance(version))
    data = canonical_bytes(index)
    path = index_path(version)
    path.write_bytes(data)
    identity = identity_of(data)
    print(f"index written: {path} ({len(data)} bytes)")
    print(f"audit identity: {identity}")
    print(f"bucket prefix:  audit/{version}/{identity}/")
    return 0


def verify(version: str) -> int:
    """Re-hash the local files against the written index and the index against itself."""
    path = index_path(version)
    data = path.read_bytes()
    index = json.loads(data)
    if canonical_bytes(index) != data:
        print("FAIL: the index file is not in canonical bytes")
        return 1
    files = audit_files(version)
    expected = {
        "rulings": index["rulings_digest"],
        "summary": index["summary_digest"],
        "checklist": index["checklist_digest"],
        "sheet": index["sheet_digest_witness"],
    }
    failed = False
    for role, digest in expected.items():
        actual = sha256_of(files[role])
        status = "ok" if actual == digest else "MISMATCH"
        failed |= actual != digest
        print(f"{role:9s} {status}  {actual[:16]}...")
    print(f"audit identity: {identity_of(data)}")
    return 1 if failed else 0


UPLOADED_NAMES = {"rulings": "rulings.md", "summary": "summary.md", "checklist": "checklist.md"}
"""The three bound files' object names under the prefix; the index is ``index.json``."""


def upload(version: str) -> int:
    """Seal the verified audit under its content-addressed prefix, one conditional create
    per object, each read back and re-hashed; refuses to start on a failing verify."""
    if verify(version) != 0:
        print("FAIL: verify did not pass; nothing uploaded")
        return 1
    from leaveimpact.adapters.object_store.s3 import s3_client
    from leaveimpact.adapters.object_store.s3_write import S3ObjectWriter

    data = index_path(version).read_bytes()
    identity = identity_of(data)
    prefix = f"audit/{version}/{identity}/"
    files = audit_files(version)
    objects = [(prefix + "index.json", data)]
    objects += [(prefix + name, files[role].read_bytes()) for role, name in UPLOADED_NAMES.items()]
    store = S3ObjectWriter(s3_client(REGION), TRUTH_BUCKET)
    failed = False
    for key, content in objects:
        receipt = store.put_if_absent(key, content)
        stored = store.get(key)
        digest = hashlib.sha256(content).hexdigest()
        read_back = (
            "read back equal"
            if stored is not None and stored.content == content
            else "**READ-BACK MISMATCH**"
        )
        failed |= stored is None or stored.content != content
        print(key)
        print(f"    {receipt.outcome.value}, version {receipt.version_id}")
        print(f"    sha256 {digest}, {read_back}")
    print(f"audit identity: {identity}")
    return 1 if failed else 0


def main() -> int:
    match sys.argv[1:]:
        case ["build", version]:
            return build(version)
        case ["verify", version]:
            return verify(version)
        case ["upload", version]:
            return upload(version)
        case _:
            print(__doc__)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
