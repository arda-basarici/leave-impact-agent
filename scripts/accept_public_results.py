"""The offline acceptance of the committed public results: regenerate from the pinned
artifact, compare, and hold both worlds' sealed marks, under the administrator profile.

The results page renders a committed file and never a live decode (the demo milestone's
seventh entry ruling); this is the check that the file is the artifact's projection and
that the demo's served world is open, run on the workstation whenever the projector, the
artifact, the committed file or the demo configuration changes, each run recorded in
FINDINGS. The artifact is the local copy the phase-C runbook fetches
(`probes/phase-c-dispatch/README.md`); the served world is the one the demo configuration
allowlists (`leaveimpact.app.config`, the demo milestone's scaffold step), so an embargoed
world cannot be allowlisted without a red run here; the two world specs are read from the
truth bucket, which only the administrator profile can read. Nothing sealed is printed: a
verdict names paths, marks and public digests.

Usage, from the repository root, after `aws sso login --profile leave-impact`:

    uv run python scripts/accept_public_results.py \\
        data/phase-c-dispatch/evaluation-39061375799-1.json --profile leave-impact

Exit status: 0 accepted, 1 refused with the findings printed, 2 for a configuration or
read fault.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

from leaveimpact.adapters.object_store.layout import world_spec_key
from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.app.config import committed_configuration
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.public_acceptance import accept_public_results
from leaveimpact.results.codec import decode_public_results
from leaveimpact.results.committed import M2_REPORTED, committed_results_bytes
from leaveimpact.world.decoders import decode_world_spec
from leaveimpact.world.disclosure import Disclosure

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")


def sealed_disclosure(truth: S3ObjectReader, version: WorldVersion, what: str) -> Disclosure:
    stored = truth.get(world_spec_key(version))
    if stored is None:
        raise SystemExit(f"accept_public_results: no world spec for the {what} at {version[:12]}")
    return decode_world_spec(stored.content).disclosure


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="accept_public_results.py",
        description="Regenerate the committed public results from the pinned artifact, "
        "compare, and hold the measurement world's and the served world's sealed marks.",
    )
    parser.add_argument("artifact", type=Path, help="the local evaluation artifact")
    parser.add_argument("--committed", default=M2_REPORTED, help="the committed file's name")
    parser.add_argument(
        "--profile", default=None, help="the AWS profile that reads the truth bucket"
    )
    parsed = parser.parse_args(argv)

    committed = committed_results_bytes(parsed.committed)
    measurement = WorldVersion(decode_public_results(committed).provenance.world_version)
    served = committed_configuration().served_world_version
    session = boto3.Session(region_name=REGION, profile_name=parsed.profile)
    truth = S3ObjectReader(session.client("s3"), TRUTH_BUCKET)  # pyright: ignore[reportUnknownMemberType]
    measurement_mark = sealed_disclosure(truth, measurement, "measurement world")
    served_mark = sealed_disclosure(truth, served, "served world")

    verdict = accept_public_results(
        committed,
        parsed.artifact.read_bytes(),
        measurement_disclosure=measurement_mark,
        served_disclosure=served_mark,
    )
    print(f"committed={parsed.committed}")
    print(f"artifact_sha256={verdict.artifact_digest}")
    print(f"recorded_sha256={verdict.recorded_digest}")
    print(f"measurement_world={measurement} sealed {measurement_mark.value}")
    print(f"served_world={served} sealed {served_mark.value}")
    for finding in verdict.findings:
        print(f"finding: {finding}")
    print("verdict=accepted" if verdict.accepted else "verdict=refused")
    return 0 if verdict.accepted else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
