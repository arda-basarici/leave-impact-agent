"""The generation job: ``python -m leaveimpact.generator --seed N --world-start DATE …``.

The composition of the whole sealing run, and nothing of its logic: the configuration
boundary turns the command line and the environment into typed records, the pure
assembly turns the recipe into a world and its sealed bundle, the stores are opened on
what the deployment names, the production preparation is wired on the hosts, and the
sealing sequence runs. What the job prints is what a reader of the Actions log needs and
nothing that must not be there: the run's checkpoint numbers, one per line, and the world
version as the last line in the form ``world_version=<hex>`` for the workflow to lift into
its summary and output — never a credential, a host or a manifest. A fault in the raw
configuration — a flag or variable missing or malformed, as the boundary parses them —
exits with status 2 and its message; once the typed configuration is built, everything
after it, a bucket that turns out not to exist included, propagates as the loud
operational failure it is, with its traceback and the store's own fault taxonomy.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Sequence

from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    deployment_from_env,
    parse_recipe,
    stores_for,
)
from leaveimpact.generator.metrics import TimedObjectWriter
from leaveimpact.generator.sealing import seal_world
from leaveimpact.generator.systems import AdapterPreparation
from leaveimpact.world import assemble_world, bundle


def main(argv: Sequence[str] | None = None) -> int:
    try:
        recipe = parse_recipe(sys.argv[1:] if argv is None else argv)
        deployment = deployment_from_env(os.environ)
    except ConfigurationError as error:
        print(f"leaveimpact.generator: {error}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    world = assemble_world(recipe.seed, recipe.params, recipe.world_start)
    sealed = bundle(world)
    truth, world_store = stores_for(deployment)
    timed = TimedObjectWriter(world_store)
    with AdapterPreparation(deployment.hosts, timed, world, sealed.world_version) as preparation:
        result = seal_world(world, sealed, preparation, truth, timed)
    elapsed = time.perf_counter() - started

    for line in timed.summary(elapsed).lines():
        print(line)
    print(f"run_seconds={elapsed:.1f}")
    print(f"manifest_key={result.manifest_key}")
    print(f"world_version={result.manifest.world_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
