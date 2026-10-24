"""The container's command: serve the demo surface with no argument, state the image's
identity under ``identity``, and under ``smoke`` prove the image carries what a run and a
page load.

An image that can say which commit built it is the provenance floor every later artifact
(event logs, eval runs, reports) inherits: the Dockerfile refuses to build without
``CODE_VERSION``, and every command here refuses to run without it. The identity line was
the container's default from the first deploy until the demo milestone's scaffold step put
the service in its place; it stays as a command, since the deploy script runs it as the
image check beside the readiness read of the running service (the entry's HTTP-shell
ruling: the old check never remains the sole gate by omission). ``identity`` and ``smoke``
need no database, no cache and no vendor credential, so they run on a runner, on a laptop
and on the instance alike; only serving reads the store.

``python -m leaveimpact smoke`` (the first live run's step, fork 8) is what the CI image job
runs the pushed image once with, on the runner's own platform: it loads both roles' prompt
assets through the loader the work command composes with and prints each asset's digest
beside the code version, refusing on an asset that is missing or malformed, so an image
whose packaging dropped a prompt file fails before it is deployed. The digests are the ones
a run freezes (``agent.registered``), so the smoke's output is what a registration's role
compares with. It then reads the committed public results by package name and prints the
digest of the artifact they were cut from, and since the scaffold step the demo
configuration the same way, printing the served world it allowlists, so an image whose
packaging dropped either file, or carries one not of the declared shape, fails before the
page ever renders it.

Serving binds the application to every interface of the container on port 8000; the proxy
reaches it over the shared ``web`` network and nothing is published to the host (compose).
One Uvicorn worker: store access is synchronous on Starlette's thread pool and the demo's
load is a stranger reading pages. Forwarded headers are left at Uvicorn's defaults, trusted
from the loopback only, until the live commands step reads a client address for its
per-address limit; the setting then comes from the platform contract's ``web`` subnet row
through compose (``FORWARDED_ALLOW_IPS``), since the proxy dials from that network and the
application publishes no port. Until then the application sees the proxy's address as every
client and nothing reads it (the public switch, 2026-10-24).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence

from leaveimpact.agent.assets import PromptAssets, load_prompt_assets
from leaveimpact.app.config import DEMO, DemoConfiguration, committed_configuration
from leaveimpact.core.tools import Role
from leaveimpact.results.committed import M2_REPORTED, committed_results
from leaveimpact.results.public import PublicResults

CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"
IDENTITY = "identity"
SMOKE = "smoke"
PORT = 8000

Serve = Callable[[Mapping[str, str]], int]


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    load: Callable[[Role], PromptAssets] = load_prompt_assets,
    results: Callable[[], PublicResults] = committed_results,
    configuration: Callable[[], DemoConfiguration] = committed_configuration,
    serve: Serve | None = None,
) -> int:
    """Serve with no argument, the identity line under ``identity``, the smoke under
    ``smoke``; 1 without a code version, on an asset, a results file or a configuration
    that does not load, or when serving refuses to start, 2 on any other argument."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    environment = os.environ if env is None else env
    version = environment.get(CODE_VERSION, "")
    if not version:
        print(
            "leaveimpact: LEAVEIMPACT_CODE_VERSION unset — image built without provenance",
            file=sys.stderr,
        )
        return 1
    if arguments == [IDENTITY]:
        print(f"leaveimpact {version}: the demo surface's image")
        return 0
    if arguments == [SMOKE]:
        return _smoke(version, load, results, configuration)
    if arguments:
        print(
            f"leaveimpact: unknown arguments {arguments}; the image answers to no argument "
            f"(serve), {IDENTITY!r} or {SMOKE!r}",
            file=sys.stderr,
        )
        return 2
    return (_serve if serve is None else serve)(environment)


def _smoke(
    version: str,
    load: Callable[[Role], PromptAssets],
    results: Callable[[], PublicResults],
    configuration: Callable[[], DemoConfiguration],
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
    try:
        demo = configuration()
    except (OSError, ValueError) as error:
        print(
            f"leaveimpact: the demo configuration does not load ({type(error).__name__}): "
            "the image is incomplete",
            file=sys.stderr,
        )
        return 1
    print(f"demo.{DEMO}={demo.served_world_version}")
    return 0


def _serve(environment: Mapping[str, str]) -> int:
    """The real server: the application composed from the environment, run by Uvicorn until
    the stop signal; a composition the environment cannot satisfy is refused before any
    socket is bound."""
    import uvicorn

    from leaveimpact.app.main import app_from_env

    try:
        application = app_from_env(environment)
    except ValueError as error:
        print(f"leaveimpact: {error}", file=sys.stderr)
        return 1
    uvicorn.run(application, host="0.0.0.0", port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
