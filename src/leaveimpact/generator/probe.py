"""The Bedrock probe: one call to each prose model under the generator role, reported by numbers.

The authoritative evidence that the production principal can invoke the pair the platform
granted it, and that each family honours the seam — text under ``end_turn`` from the
writer, the forced tool filled by the checker — comes from the runner the generator runs
on, not from a workstation (the step 13 lesson: probe from the production client's network).
This module is what the probe workflow runs: it reads the same model configuration the
generation job reads, makes one small call per model, and prints per model its id, the
outcome and the usage. It prints no text and no proposition, since the job log is public
and the seam's own logging rule applies here too. A fault of either model fails the run
with the fault's class in the output, which is the diagnosis.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from leaveimpact.adapters.prose.seam import (
    CheckerRequest,
    InferenceConfiguration,
    ModelAccessRefused,
    ModelMisconfigured,
    ModelProtocolFault,
    ModelUnreachable,
    ProseChecker,
    ProseWriter,
    ToolSpec,
    WriterRequest,
)
from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    prose_models_for,
    prose_models_from_env,
)

MODEL_FAULTS = (ModelUnreachable, ModelAccessRefused, ModelMisconfigured, ModelProtocolFault)

WRITER_PROBE = WriterRequest(
    "You answer in one short sentence.",
    "Say that the retry queue migration is on track.",
    InferenceConfiguration(temperature=0.7, max_tokens=100),
)

CHECKER_PROBE = CheckerRequest(
    "You extract what the tool asks and call it exactly once.",
    "The retry queue migration is on track and Deniz owns it.",
    ToolSpec(
        "record_words",
        "Record every capitalized word in the text.",
        {
            "type": "object",
            "properties": {"words": {"type": "array", "items": {"type": "string"}}},
            "required": ["words"],
        },
    ),
    InferenceConfiguration(temperature=0.0, max_tokens=200),
)


def probe(writer: ProseWriter, checker: ProseChecker, out: Callable[[str], None]) -> bool:
    """One call per model, reported as lines of ``name=value``; ``True`` when both answered."""
    ok = True
    out(f"writer_model={writer.model_id}")
    try:
        written = writer.write(WRITER_PROBE)
    except MODEL_FAULTS as fault:
        out(f"writer_outcome={type(fault).__name__}")
        ok = False
    else:
        out("writer_outcome=ok")
        out(f"writer_latency_ms={written.usage.latency_ms}")
        out(f"writer_input_tokens={written.usage.input_tokens}")
        out(f"writer_output_tokens={written.usage.output_tokens}")
    out(f"checker_model={checker.model_id}")
    try:
        call = checker.extract(CHECKER_PROBE)
    except MODEL_FAULTS as fault:
        out(f"checker_outcome={type(fault).__name__}")
        ok = False
    else:
        out("checker_outcome=ok")
        out(f"checker_latency_ms={call.usage.latency_ms}")
        out(f"checker_input_tokens={call.usage.input_tokens}")
        out(f"checker_output_tokens={call.usage.output_tokens}")
        out(f"checker_tool_filled={'words' in call.input}")
    return ok


def main() -> int:
    try:
        models = prose_models_from_env(os.environ)
    except ConfigurationError as error:
        print(f"leaveimpact.generator.probe: {error}", file=sys.stderr)
        return 2
    writer, checker = prose_models_for(models)
    return 0 if probe(writer, checker, print) else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["CHECKER_PROBE", "WRITER_PROBE", "main", "probe"]
