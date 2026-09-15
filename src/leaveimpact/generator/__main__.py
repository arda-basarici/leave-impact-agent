"""The generation job: ``python -m leaveimpact.generator --seed N --world-start DATE …``.

The composition of the whole run, and nothing of its logic. FRESH: the configuration
boundary turns the command line and the environment into typed records; the pure assembly
turns the recipe into the semantic world; the materializer writes every pending brief under
the gates and its cap; composition places the accepted prose and fixes the bundle; the
version is printed, flushed, before the first persistent world or vendor mutation — the
model calls have happened by then, paid and creating no resumable state — so the operator
of a crashed run has the value a resume needs; then the stores are opened, the production
preparation is wired on the hosts, and the sealing sequence runs. RESUME (``--resume
<version>``): the sealed realization is rebuilt and proven from the truth bucket instead of
generated, and the same
sealing sequence continues from wherever the checkpoint left it (the step 14 rulings in
DESIGN, "Materialization").

What the job prints is what a reader of the Actions log needs and nothing that must not be
there: the materializer's lines — target ids, attempt numbers, guard names, counts — the
prose and checkpoint metrics one per line, and the world version, first before sealing and
last in the form ``world_version=<hex>`` for the workflow to lift into its summary; never a
body of text, a credential, a host or a manifest. A fault in the raw configuration exits
with status 2 and its message; once the typed configuration is built, everything after it —
a target that exhausted its cap, a model that could not be used, a bucket that turns out
not to exist — propagates as the loud operational failure it is, with its own message and
the store's or the seam's fault taxonomy.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Sequence

from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    ProseModels,
    WorldRecipe,
    deployment_from_env,
    parse_recipe,
    prose_models_for,
    prose_models_from_env,
    stores_for,
)
from leaveimpact.generator.materialize import ProseMetrics, materialize
from leaveimpact.generator.metrics import TimedObjectWriter
from leaveimpact.generator.prose.assets import load_prompt_assets
from leaveimpact.generator.resume import resume_world
from leaveimpact.generator.sealing import seal_world
from leaveimpact.generator.systems import AdapterPreparation
from leaveimpact.world import Bundle, WorldSpec, assemble_semantic_world, bundle, compose


def main(argv: Sequence[str] | None = None) -> int:
    try:
        recipe = parse_recipe(sys.argv[1:] if argv is None else argv)
        deployment = deployment_from_env(os.environ)
        models = prose_models_from_env(os.environ)
    except ConfigurationError as error:
        print(f"leaveimpact.generator: {error}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    truth, world_store = stores_for(deployment)
    if recipe.resume is not None:
        print(f"resuming={recipe.resume}")
        world, sealed = resume_world(recipe.resume, truth)
    else:
        world, sealed, prose_metrics = _fresh(recipe, models)
        # Printed before sealing begins: the prose stage is over, and a run that seals and
        # then fails in projection must not take the stage's numbers with it (the
        # measurement world's did, 2026-09-15; the record now seals them too).
        for line in prose_metrics.lines():
            print(line)
    # Flushed: this line is the resume handle, and stdout is a pipe under the workflow, so
    # a hard kill mid-sealing must not lose it in a block buffer.
    print(f"world_version={sealed.world_version}", flush=True)

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


def _fresh(recipe: WorldRecipe, models: ProseModels) -> tuple[WorldSpec, Bundle, ProseMetrics]:
    """Assemble, materialize, compose: the pure world with its prose, before any external write."""
    semantic = assemble_semantic_world(
        recipe.seed, recipe.params, recipe.world_start, recipe.plan_name
    )
    writer, checker = prose_models_for(models)
    materialized = materialize(
        semantic, writer, checker, load_prompt_assets(), recipe.attempt_cap, print
    )
    world = compose(semantic, materialized.prose, materialized.record)
    return world, bundle(world), materialized.metrics


if __name__ == "__main__":
    sys.exit(main())
