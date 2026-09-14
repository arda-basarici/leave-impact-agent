"""Prompt policy: the assets the models are told, the render from a brief to a request, the
checker's tool and the parse of what it filled.

Above the adapter on purpose (the step 14 rulings in DESIGN, "Materialization"): what the
writer is told about a brief, which tool the checker must call and what its input means are
benchmark decisions, so they live with the generator and the Bedrock layer sends what it is
handed. ``assets`` ships the system texts and register fragments as package data with their
digests; ``render`` turns a brief into the two requests; ``schema`` generates the checker's
tool from the predicate registry and parses the filled tool back into propositions.
"""

from leaveimpact.generator.prose import assets, render, schema
from leaveimpact.generator.prose.assets import (
    CHECKER_SYSTEM,
    WRITER_SYSTEM,
    PromptAssets,
    load_prompt_assets,
)
from leaveimpact.generator.prose.render import (
    CHECKER_INFERENCE,
    WRITER_INFERENCE,
    checker_request,
    describe_fact,
    writer_request,
)
from leaveimpact.generator.prose.schema import (
    TOOL_NAME,
    Extraction,
    ExtractionMalformed,
    parse_extraction,
    tool_schema,
)

__all__ = [
    "CHECKER_INFERENCE",
    "CHECKER_SYSTEM",
    "TOOL_NAME",
    "WRITER_INFERENCE",
    "WRITER_SYSTEM",
    "Extraction",
    "ExtractionMalformed",
    "PromptAssets",
    "assets",
    "checker_request",
    "describe_fact",
    "load_prompt_assets",
    "parse_extraction",
    "render",
    "schema",
    "tool_schema",
    "writer_request",
]
