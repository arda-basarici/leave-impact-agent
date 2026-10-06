"""The live parse probe: one send to a real model asking for both fact shapes the parse
protocol reads, the response scrubbed into the tree and parsed through the protocol.

The criterion is the ``parse-protocol`` row of ``probes/README.md``. A probe: it decides
whether a real response carries the fact tool's call and a ``{`` text payload as
``agent/answer_parse.py`` reads them, and which of the two arrive in one answer; nothing
about fact quality is read from it, and its prompt is not the investigator's.

The request: the ``state_facts`` tool declared with the fact parser's entry schema under a
``facts`` array, the choice left ``auto``, temperature 0, and a system prompt that asks for
one tool call carrying a given entry and, beside it, the same payload as plain text opening
with ``{``. The entry's values are stand-ins (a carrier id, a predicate, a subject, a value,
a quote) that name nothing of any world.

What is written: the raw response outside the repository (``LEAVE_IMPACT_SPIKE_CAPTURES``,
refused inside the tree, as the acceptance spike's captures are), the scrubbed response at
``tests/fixtures/converse/parse-probe-<timestamp>.json``, and one JSON summary on standard
output: the shapes witnessed (``tool_call``, ``text_payload``), how the protocol read each
batch (stated facts, refused entries, malformed), and the usage. A shape that did not arrive
is reported as a gap, never inferred.

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir outside the tree> python probes/parse_protocol/live_probe.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import boto3

from leaveimpact.agent.answer_parse import FACT_TOOL, is_payload, parse_answer, tool_uses
from leaveimpact.agent.fact_entries import ENTRY_SCHEMA
from leaveimpact.core.model_calls import MalformedBatch, ParsedBatch
from leaveimpact.core.stated import Admitted, StatedFact

REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY / "tests" / "fixtures" / "converse"
PROFILE = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-central-1"

ENTRY = {
    "carrier": "comment_000001",
    "predicate": "has_skill",
    "subject": "emp_001",
    "value": "kafka",
    "quote": "has run the kafka cluster since spring",
}
"""A stand-in entry: ids of the shape the parser reads, naming nothing of any world."""

SYSTEM = (
    "You are a test harness's counterpart. Do exactly two things in one answer and nothing "
    "else. First, call the tool `state_facts` once, with `facts` holding exactly this one "
    f"entry, copied verbatim: {json.dumps(ENTRY)}. Second, write as plain text, not inside "
    "the tool call, a JSON object with the same shape and the same single entry: "
    f"{json.dumps({'facts': [ENTRY]})}. The text must begin with the opening brace and hold "
    "nothing but that JSON. No other words."
)
USER = "State the fact both ways now."


def request() -> dict[str, Any]:
    return {
        "modelId": PROFILE,
        "system": [{"text": SYSTEM}],
        "messages": [{"role": "user", "content": [{"text": USER}]}],
        "inferenceConfig": {"maxTokens": 512, "temperature": 0},
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": FACT_TOOL,
                        "description": "State facts read from the records, as entries.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {"facts": {"type": "array", "items": ENTRY_SCHEMA}},
                                "required": ["facts"],
                            }
                        },
                    }
                }
            ],
            "toolChoice": {"auto": {}},
        },
    }


def captures_directory() -> Path:
    held = os.environ.get("LEAVE_IMPACT_SPIKE_CAPTURES")
    if not held:
        raise SystemExit(
            "LEAVE_IMPACT_SPIKE_CAPTURES names a directory outside the tree for the raw response"
        )
    directory = Path(held).resolve()
    if directory == REPOSITORY or REPOSITORY in directory.parents:
        raise SystemExit(f"{directory} is inside the repository; captures live outside it")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def admit(fact: StatedFact) -> Admitted:
    """The probe's gate admits every stated fact: what is read here is the shape, not the
    evidence behind it."""
    return Admitted(fact)


def reading(batch: ParsedBatch | MalformedBatch) -> dict[str, Any]:
    if isinstance(batch, MalformedBatch):
        return {"malformed": True, "refused_by": batch.refused_by.parser}
    stated = sum(isinstance(entry, Admitted) for entry in batch.entries)
    return {"malformed": False, "stated": stated, "entries": len(batch.entries)}


def main() -> int:
    directory = captures_directory()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    client = boto3.client("bedrock-runtime", region_name=REGION)  # pyright: ignore[reportUnknownMemberType]
    response = cast(dict[str, Any], client.converse(**request()))
    response.pop("ResponseMetadata", None)
    (directory / f"parse-probe-{stamp}.response.json").write_text(
        json.dumps(response, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    sys.path.insert(0, str(REPOSITORY / "probes" / "parse_protocol"))
    from scrub import scrub  # noqa: PLC0415 - the sibling script, imported by path

    scrubbed = scrub(response)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    fixture = FIXTURES / f"parse-probe-{stamp}.json"
    fixture.write_text(json.dumps(scrubbed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    blocks = response["output"]["message"]["content"]
    tool_calls = [use for use in tool_uses(response) if use.name == FACT_TOOL]
    text_payloads = [b["text"] for b in blocks if "text" in b and is_payload(b["text"])]
    answer = parse_answer(response, resolved={}, stopping=frozenset(), gate=admit)
    summary = {
        "profile": PROFILE,
        "stop_reason": response.get("stopReason"),
        "shapes": {"tool_call": len(tool_calls), "text_payload": len(text_payloads)},
        "gaps": [
            name
            for name, held in (("tool_call", tool_calls), ("text_payload", text_payloads))
            if not held
        ],
        "batches": [reading(batch) for batch in answer.fact_batches],
        "text_present": answer.text_present,
        "usage": response.get("usage"),
        "fixture": str(fixture.relative_to(REPOSITORY)),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
