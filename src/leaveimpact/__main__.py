"""The container's command: state the image's identity, and under ``smoke`` prove the image
carries what a run loads.

An image that can say which commit built it is the provenance floor every later artifact
(event logs, eval runs, reports) inherits: the Dockerfile refuses to build without
``CODE_VERSION``, and this entry point is how a running container proves it received one.
The identity line is the container's default and the deploy's evidence (the deploy script
runs the image once and reads it); it is replaced by the real service entry point when the
first HTTP surface lands, and Compose's ``restart`` policy flips with it.

``python -m leaveimpact smoke`` (the first live run's step, fork 8) is what the CI image job
runs the pushed image once with, on the runner's own platform: it loads both roles' prompt
assets through the loader the work command composes with and prints each asset's digest
beside the code version, refusing on an asset that is missing or malformed, so an image
whose packaging dropped a prompt file fails before it is deployed. The digests are the ones
a run freezes (``agent.registered``), so the smoke's output is what a registration's role
compares with. It then reads the committed public results by package name and prints the
digest of the artifact they were cut from, so an image whose packaging dropped the results
file, or carries one not of the declared types, fails the same way before the results page
ever renders it (the demo milestone's first build step).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence

from leaveimpact.agent.assets import PromptAssets, load_prompt_assets
from leaveimpact.core.tools import Role
from leaveimpact.results.committed import M2_REPORTED, committed_results
from leaveimpact.results.public import PublicResults

CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"
SMOKE = "smoke"


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    load: Callable[[Role], PromptAssets] = load_prompt_assets,
    results: Callable[[], PublicResults] = committed_results,
) -> int:
    """The identity line with no argument, the smoke under ``smoke``; 1 without a code
    version, on an asset that does not load or on committed results that do not, 2 on any
    other argument."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    environment = os.environ if env is None else env
    version = environment.get(CODE_VERSION, "")
    if not version:
        print(
            "leaveimpact: LEAVEIMPACT_CODE_VERSION unset — image built without provenance",
            file=sys.stderr,
        )
        return 1
    if arguments == [SMOKE]:
        return _smoke(version, load, results)
    if arguments:
        print(
            f"leaveimpact: unknown arguments {arguments}; the image answers to no argument "
            f"or {SMOKE!r}",
            file=sys.stderr,
        )
        return 2
    print(f"leaveimpact {version}: no service yet; the baseline image runs and identifies itself")
    return 0


def _smoke(
    version: str, load: Callable[[Role], PromptAssets], results: Callable[[], PublicResults]
) -> int:
    print(f"code_version={version}")
    for role in Role:
        try:
            assets = load(role)
        except (OSError, ValueError) as error:
            print(
                f"leaveimpact: the {role.value} prompt assets do not load "
                f"({type(error).__name__}): the image is incomplete",
                file=sys.stderr,
            )
            return 1
        for name, digest in assets.digests():
            print(f"{role.value}.{name}={digest}")
    try:
        committed = results()
    except (OSError, ValueError) as error:
        print(
            f"leaveimpact: the committed public results do not load ({type(error).__name__}): "
            "the image is incomplete",
            file=sys.stderr,
        )
        return 1
    print(f"results.{M2_REPORTED}={committed.provenance.artifact_digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
