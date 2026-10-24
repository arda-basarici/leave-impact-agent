"""The offline acceptance of the released golden world: the three committed files under
``docs/golden-world`` compared byte for byte with the two buckets' objects, under the
administrator profile.

CI proves the release by content (the unit test joins the three files through the
evaluator's loader and recomputes the version); this is the check that the buckets hold
the same bytes, which only a principal that reads both buckets can make. Run whenever a
released file, the demo configuration or the buckets' objects change, each run recorded in
FINDINGS. The verdict names paths, sizes and digests of an open world, nothing sealed.

Usage, from the repository root, after `aws sso login --profile leave-impact`:

    uv run python scripts/accept_golden_release.py --profile leave-impact

Exit status: 0 accepted, 1 refused with the findings printed, 2 for a configuration or
read fault.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import boto3

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.app.config import committed_configuration
from leaveimpact.core.ids import WorldVersion
from leaveimpact.world.artifacts import SCENARIO_SPECS, TRUTH_MANIFEST, WORLD_SPEC
from leaveimpact.world.decoders import decode_world_spec
from leaveimpact.world.disclosure import Disclosure

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
WORLD_BUCKET = os.environ.get("LEAVE_IMPACT_WORLD_BUCKET", "leave-impact-world-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")
RELEASE = Path("docs") / "golden-world"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="accept_golden_release.py",
        description="Compare the released golden world's files with the buckets' objects.",
    )
    parser.add_argument(
        "--profile", default=None, help="the AWS profile that reads the two buckets"
    )
    parsed = parser.parse_args(argv)

    version = WorldVersion(committed_configuration().served_world_version)
    session = boto3.Session(region_name=REGION, profile_name=parsed.profile)
    client = session.client("s3")  # pyright: ignore[reportUnknownMemberType]
    truth = S3ObjectReader(client, TRUTH_BUCKET)
    world = S3ObjectReader(client, WORLD_BUCKET)
    sources = (
        (WORLD_SPEC, truth, world_spec_key(version)),
        (SCENARIO_SPECS, world, scenario_specs_key(version)),
        (TRUTH_MANIFEST, truth, truth_manifest_key(version)),
    )

    print(f"served_world={version}")
    findings: list[str] = []
    for name, reader, key in sources:
        stored = reader.get(key)
        if stored is None:
            print(f"{name}: no object at {key}", file=sys.stderr)
            return 2
        committed = (RELEASE / name).read_bytes()
        equal = committed == stored.content
        print(
            f"{name}: committed {len(committed)} bytes sha256 "
            f"{hashlib.sha256(committed).hexdigest()}; bucket version {stored.version_id}; "
            f"{'equal' if equal else 'DIFFERS'}"
        )
        if not equal:
            findings.append(f"{name} differs from the bucket's object")
        if name == WORLD_SPEC:
            mark = decode_world_spec(stored.content).disclosure
            print(f"disclosure={mark.value}")
            if mark is not Disclosure.OPEN:
                findings.append("the released world is not sealed open")
    for finding in findings:
        print(f"finding: {finding}")
    print("verdict=accepted" if not findings else "verdict=refused")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
