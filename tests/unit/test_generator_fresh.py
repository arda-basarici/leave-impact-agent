"""The fresh stage over a plan with no prose target: the recipe's world-defining values reach
the bundle's provenance, the materialization record seals the models it was handed and the
cap it ran under, and no model is called when nothing is pending."""

from __future__ import annotations

import json
from datetime import date

from leaveimpact.adapters.prose import CheckerRequest, ToolCall, WriterRequest, WrittenText
from leaveimpact.generator.fresh import fresh_world
from leaveimpact.generator.recipe import WorldRecipe
from leaveimpact.generator.truth_record import decode_materialization
from leaveimpact.world import DEFAULT_PARAMS, WORLD_SPEC, world_version


class RefusingWriter:
    model_id = "fake-writer"

    def write(self, request: WriterRequest) -> WrittenText:
        raise AssertionError("a plan without prose targets writes nothing")


class RefusingChecker:
    model_id = "fake-checker"

    def extract(self, request: CheckerRequest) -> ToolCall:
        raise AssertionError("a plan without prose targets checks nothing")


def test_the_recipe_reaches_the_bundle_and_an_empty_prose_stage_calls_no_model() -> None:
    recipe = WorldRecipe(3, DEFAULT_PARAMS, date(2026, 1, 5), attempt_cap=5, plan_name="tier1")
    lines: list[str] = []

    fresh = fresh_world(recipe, RefusingWriter(), RefusingChecker(), lines.append)

    provenance = json.loads(fresh.bundle.world_spec.content)["provenance"]
    assert (provenance["seed"], provenance["plan_name"]) == (3, "tier1")
    assert provenance["world_start"] == "2026-01-05"
    record = decode_materialization(fresh.bundle.truth_manifest.content)
    assert record is not None
    assert (record.writer.model_id, record.checker.model_id) == ("fake-writer", "fake-checker")
    assert record.attempt_cap == 5
    assert record.targets == ()
    assert fresh.metrics.writer_attempts == 0
    assert fresh.bundle.world_spec.name == WORLD_SPEC
    assert fresh.bundle.world_version == world_version(fresh.bundle.artifacts)
    assert all(scenario.spec.id for scenario in fresh.world.scenarios)
