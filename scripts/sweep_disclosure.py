"""The offline half of the disclosure sweep: the embargoed world's two digests searched for
in the tree at HEAD, under the administrator profile, before the tree goes public.

The structural predicates (no pointer outside the tree, no third-person narration) are a
unit test; this one cannot be, since a committed test would carry the digests it looks
for. The evaluator already refuses to run when the checkout publishes the measurement
world's scenario-specs digest or semantic digest, whole or in a cited prefix form
(`leaveimpact.evaluator.entrypoint.require_undisclosed`); this script runs that same check
on demand against the current HEAD, so the public switch and every later push of prose
can be preceded by it without an evaluation. The sealed world is read from the two
buckets, which only the administrator profile can read whole, and nothing of it is
printed: the verdict names the commit, the world's version (public) and its mark, and on a
refusal the paths and the kind of digest found, never a value.

The scan is over the commit, so a change not yet committed is not in it; the tree's state
is printed so an operator sees when the scan is behind the working copy.

Usage, from the repository root, after `aws sso login --profile leave-impact`:

    uv run python scripts/sweep_disclosure.py --profile leave-impact

Exit status: 0 held, 1 refused with the findings printed, 2 for a configuration or read
fault.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3

from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.entrypoint import DisclosureRefused, require_undisclosed
from leaveimpact.evaluator.repository import Repository, RepositoryRefused
from leaveimpact.evaluator.sealed_world import SealedWorldRefused, load_sealed_world
from leaveimpact.results.codec import decode_public_results
from leaveimpact.results.committed import committed_results_bytes

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
WORLD_BUCKET = os.environ.get("LEAVE_IMPACT_WORLD_BUCKET", "leave-impact-world-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sweep_disclosure.py",
        description="Search the tree at HEAD for the embargoed world's digests, whole or "
        "cited by prefix, under the administrator profile.",
    )
    parser.add_argument(
        "--world-version",
        default=None,
        help="the embargoed world; by default the one the committed results report",
    )
    parser.add_argument(
        "--profile", default=None, help="the AWS profile that reads the two buckets"
    )
    parsed = parser.parse_args(argv)

    version = WorldVersion(
        parsed.world_version
        or decode_public_results(committed_results_bytes()).provenance.world_version
    )
    session = boto3.Session(region_name=REGION, profile_name=parsed.profile)
    client = session.client("s3")  # pyright: ignore[reportUnknownMemberType]
    try:
        world = load_sealed_world(
            version, S3ObjectReader(client, TRUTH_BUCKET), S3ObjectReader(client, WORLD_BUCKET)
        )
    except SealedWorldRefused as refused:
        print(f"sweep_disclosure: {refused}", file=sys.stderr)
        return 2

    repository = Repository(Path.cwd())
    head = repository.head()
    try:
        repository.require_clean()
        tree = "clean"
    except RepositoryRefused as dirty:
        tree = str(dirty)
    print(f"head={head}")
    print(f"tree={tree}")
    print(f"world={version} sealed {world.disclosure.value}")
    try:
        require_undisclosed(world, repository, head)
    except DisclosureRefused as refused:
        print(f"finding: {refused}")
        print("verdict=refused")
        return 1
    print("verdict=held")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
