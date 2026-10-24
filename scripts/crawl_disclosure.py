"""The hostname half of the disclosure sweep: every public page fetched through the edge and
read with the sweep's two predicates, under the administrator profile, after the public
switch and after any change to a page or to the edge.

The offline half (``sweep_disclosure.py``) reads the tree at a commit; this one reads what a
public reader is served, which the tree cannot show: the templates render the golden world's
content, and the proxy and the edge add to the body (the first crawl found an analytics
script no template names). The page list comes from the replay listing's own links, so a
published attempt is never missed. Each body is read for the embargoed world's two digests
in their cited forms, the evaluator's own predicate, and for the committed gate's structural
patterns, which are loaded from the gate test by path on purpose: the gate is their one
home, a copy here would drift, and this script runs on the workstation only. Nothing of the
sealed world is printed: a hit names the path and the kind of digest, never a value.

The fetches are paced under the zone's rate rule and the first 429 ends the crawl, since a
refused page is not a read page. The requests carry a named user agent: the edge's managed
rules answer 403 to Python's default one, found when a first request forgot it.

Usage, from the repository root, after ``aws sso login --profile leave-impact``:

    uv run python scripts/crawl_disclosure.py --profile leave-impact

Exit status: 0 held (every page 200, both predicates clean), 1 refused with the findings
printed, 2 for a configuration or read fault.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3

from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.entrypoint import cited_forms
from leaveimpact.evaluator.public_crawl import Pattern, crawl_paths, page_findings
from leaveimpact.evaluator.sealed_world import SealedWorldRefused, load_sealed_world
from leaveimpact.results.codec import decode_public_results
from leaveimpact.results.committed import committed_results_bytes

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
WORLD_BUCKET = os.environ.get("LEAVE_IMPACT_WORLD_BUCKET", "leave-impact-world-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")
HOSTNAME = "https://leave-agent.ardabasarici.dev"
USER_AGENT = "leave-impact-agent disclosure crawl"
PACE_SECONDS = 0.5
GATE_TEST = Path("tests/unit/test_disclosure_sweep.py")


def gate_patterns(repository: Path) -> tuple[Pattern, ...]:
    """The committed gate's pointer and name patterns, loaded from the test file by path."""
    path = repository / GATE_TEST
    spec = importlib.util.spec_from_file_location("disclosure_gate", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"the gate test is not at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.POINTERS) + tuple(module.NAMES)


def fetch(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl_disclosure.py",
        description="Fetch every public page through the hostname and read each for the "
        "embargoed world's digests and the gate's structural patterns.",
    )
    parser.add_argument(
        "--profile", default=None, help="the AWS profile that reads the two buckets"
    )
    parser.add_argument("--hostname", default=HOSTNAME, help="the public origin to crawl")
    parser.add_argument(
        "--world-version",
        default=None,
        help="the embargoed world; by default the one the committed results report",
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
        print(f"crawl_disclosure: {refused}", file=sys.stderr)
        return 2
    embargoed = {
        "scenario-specs digest": cited_forms(world.scenario_specs.digest),
        "semantic digest": cited_forms(world.semantic_digest),
    }
    patterns = gate_patterns(Path.cwd())
    print(f"hostname={parsed.hostname}")
    print(f"world={version} sealed {world.disclosure.value}; patterns={len(patterns)}")

    status, listing = fetch(parsed.hostname + "/replays")
    if status != 200:
        print(f"crawl_disclosure: the listing answered {status}", file=sys.stderr)
        return 2
    paths = crawl_paths(listing.decode("utf-8", errors="replace"))
    print(f"pages={len(paths)} ({(len(paths) - 4) // 4} attempts listed)")

    statuses: dict[int, int] = {}
    total_bytes = 0
    findings: list[str] = []
    hosts: set[str] = set()
    started = time.monotonic()
    for path in paths:
        status, body = fetch(parsed.hostname + path)
        statuses[status] = statuses.get(status, 0) + 1
        total_bytes += len(body)
        if status == 429:
            print(f"finding: {path} answered 429; the crawl stops here")
            break
        if status != 200:
            findings.append(f"{path}: answered {status}")
        found = page_findings(
            body.decode("utf-8", errors="replace"), embargoed=embargoed, patterns=patterns
        )
        findings.extend(f"{path}: the {kind}" for kind in found.embargoed)
        findings.extend(f"{path}:{hit}" for hit in found.structural)
        hosts.update(found.external_hosts)
        time.sleep(PACE_SECONDS)

    fetched = sum(statuses.values())
    print(f"fetched={fetched} in {time.monotonic() - started:.0f}s bytes={total_bytes}")
    print(f"statuses={dict(sorted(statuses.items()))}")
    print(f"external_hosts={sorted(hosts) or 'none'}")
    for finding in findings:
        print(f"finding: {finding}")
    held = fetched == len(paths) and not findings and set(statuses) == {200}
    print(f"verdict={'held' if held else 'refused'}")
    return 0 if held else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
