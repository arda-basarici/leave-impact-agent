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
READ_TIMEOUT_SECONDS = 90.0
"""A stream's one tick may take the store's bounds summed (twelve seconds) and the third and
fourth crawls saw two reads pass thirty seconds through the hostname with the host's CPU
near idle; the timeout is for a page that never answers, not a slow one."""
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


def fetch(url: str, *, retries: int) -> tuple[int, bytes, int]:
    """The status, the body and the number of reads it took: a read that times out is tried
    again up to ``retries`` times, since the first crawls after the switch saw one read in
    ten stall from one workstation while the host answered the same page in a third of a
    second in-network and through the edge from itself, so a stall is the client's path and
    not a page's answer; the last timeout is a failure the caller reports. The run prints how
    many pages needed a retry, so a record of the crawl says what the path was like."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 2):
        try:
            with urllib.request.urlopen(request, timeout=READ_TIMEOUT_SECONDS) as response:
                return response.status, response.read(), attempt
        except urllib.error.HTTPError as error:
            return error.code, error.read(), attempt
        except TimeoutError:
            if attempt == retries + 1:
                raise
        except urllib.error.URLError as error:
            # A handshake that times out arrives wrapped; any other reason is not a stall.
            if not isinstance(error.reason, TimeoutError) or attempt == retries + 1:
                raise
    raise AssertionError("unreachable")


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
        "--retries",
        type=int,
        default=1,
        help="how many more times a read that timed out is tried (the run reports the count)",
    )
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

    status, listing, _ = fetch(parsed.hostname + "/replays", retries=parsed.retries)
    if status != 200:
        print(f"crawl_disclosure: the listing answered {status}", file=sys.stderr)
        return 2
    paths = crawl_paths(listing.decode("utf-8", errors="replace"))
    print(f"pages={len(paths)} ({(len(paths) - 4) // 4} attempts listed)")

    statuses: dict[int, int] = {}
    total_bytes = 0
    retried: list[str] = []
    findings: list[str] = []
    hosts: set[str] = set()
    started = time.monotonic()
    for path in paths:
        status, body, reads = fetch(parsed.hostname + path, retries=parsed.retries)
        if reads > 1:
            retried.append(path)
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
    print(f"retried_after_a_timeout={len(retried)} {retried}")
    print(f"external_hosts={sorted(hosts) or 'none'}")
    for finding in findings:
        print(f"finding: {finding}")
    held = fetched == len(paths) and not findings and set(statuses) == {200}
    print(f"verdict={'held' if held else 'refused'}")
    return 0 if held else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
