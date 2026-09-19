"""Fresh: a recipe turned into a composed world and its bundle, before any external write.

The stage every fresh run shares, whichever shell drives it: the pure assembly turns the
recipe into the semantic world, the materializer writes every pending brief under the
gates and the attempt cap, composition places the accepted prose, and the bundle fixes the
three artifacts with the version over them. The generation job continues into sealing;
the audit sheet's throwaway mode stops here and renders the bundle, so a world that is
never sealed, scored or projected still comes from the one composition the sealed worlds
come from (the step 17 throwaway example). The model calls happen inside: the stage is
paid for by the time it returns, and it creates no resumable state, which is why the job
prints the version right after it (``resume`` is the counterpart once sealing has begun).

The writer and the checker arrive opened, so the stage knows nothing of Bedrock or the
environment; the fakes at unit level and the live models are the same call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.adapters.prose import ProseChecker, ProseWriter
from leaveimpact.generator.entrypoint import WorldRecipe
from leaveimpact.generator.materialize import ProseMetrics, materialize
from leaveimpact.generator.prose.assets import load_prompt_assets
from leaveimpact.world import Bundle, WorldSpec, assemble_semantic_world, bundle, compose

__all__ = ["FreshWorld", "fresh_world"]


@dataclass(frozen=True, slots=True)
class FreshWorld:
    """The composed world, its bundle, and the prose stage's numbers for the log."""

    world: WorldSpec
    bundle: Bundle
    metrics: ProseMetrics


def fresh_world(
    recipe: WorldRecipe,
    writer: ProseWriter,
    checker: ProseChecker,
    log: Callable[[str], None],
) -> FreshWorld:
    """Assemble, materialize, compose and bundle ``recipe``; ``log`` takes the materializer's
    lines."""
    semantic = assemble_semantic_world(
        recipe.seed, recipe.params, recipe.world_start, recipe.plan_name
    )
    materialized = materialize(
        semantic, writer, checker, load_prompt_assets(), recipe.attempt_cap, log
    )
    world = compose(semantic, materialized.prose, materialized.record)
    return FreshWorld(world, bundle(world), materialized.metrics)
