"""The parse protocol over real responses: the acceptance spike's two captured Converse
responses, scrubbed, replayed through ``parse_answer`` with the answers stated in full.

The protocol was designed against hand-built fixtures (the log group's build); this is the
first time a response a real model returned goes through it (the worker group's sixth fork).
What the two captures show: a text block beside two read tool calls under a ``tool_use``
stop, read in content order with the text present, the calls unresolved or resolved as the
log says; and a text-only ``end_turn`` answer. Neither holds a ``state_facts`` call or a
``{`` text block, so the gate is never asked here and a gate that is asked fails the test;
that half of the protocol is the live parse probe's, and its absence is stated in
``tests/fixtures/converse/SCRUB.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from leaveimpact.agent.answer_parse import (
    FACT_TOOL,
    parse_answer,
    reported_usage,
    stop_reason_of,
    tool_uses,
)
from leaveimpact.core.model_calls import (
    Answer,
    AsOperation,
    HandledAsBatch,
    ParsedBatch,
    ToolCall,
    Undispatched,
    UndispatchedReason,
    UnresolvedToolCall,
)
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.stated import FactRefusal, RefusedInput, StatedFact

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "converse"
EMPLOYEE, TEAM = "tooluse_Z16Z4yHJueebEEAflBd2rP", "tooluse_XY3tLBziCrkhuWX00vNlwH"


def captured(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def never_asked(fact: StatedFact) -> Any:
    pytest.fail(f"the gate was asked about {fact!r}; these responses carry no fact batch")


def test_the_first_call_is_a_text_beside_two_reads_unresolved_until_the_log_resolves_them() -> None:
    response = captured("live-path-call-1.json")
    assert stop_reason_of(response) == "tool_use"
    assert [(use.id, use.name) for use in tool_uses(response)] == [
        (EMPLOYEE, "employee"),
        (TEAM, "team"),
    ]
    unresolved = parse_answer(response, resolved={}, stopping=frozenset(), gate=never_asked)
    assert unresolved == Answer(
        True,
        (
            ToolCall(EMPLOYEE, "employee", UnresolvedToolCall()),
            ToolCall(TEAM, "team", Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)),
        ),
        (),
    ), "with no resolution the first read blocks the second, as the barrier reads it"
    resolved = parse_answer(
        response,
        resolved={
            EMPLOYEE: AsOperation(OperationId("op/model/1/" + EMPLOYEE)),
            TEAM: AsOperation(OperationId("op/model/1/" + TEAM)),
        },
        stopping=frozenset(),
        gate=never_asked,
    )
    assert resolved == Answer(
        True,
        (
            ToolCall(EMPLOYEE, "employee", AsOperation(OperationId("op/model/1/" + EMPLOYEE))),
            ToolCall(TEAM, "team", AsOperation(OperationId("op/model/1/" + TEAM))),
        ),
        (),
    )
    usage = reported_usage(response)
    assert usage is not None and usage.raw.get("inputTokens") == 8628


def test_the_second_call_is_a_text_answer_with_no_read_and_no_batch() -> None:
    response = captured("live-path-call-2.json")
    assert stop_reason_of(response) == "end_turn"
    assert tool_uses(response) == ()
    assert parse_answer(response, resolved={}, stopping=frozenset(), gate=never_asked) == Answer(
        True, (), ()
    )


def test_a_stopping_first_read_makes_the_second_unreached() -> None:
    response = captured("live-path-call-1.json")
    answer = parse_answer(
        response,
        resolved={EMPLOYEE: AsOperation(OperationId("op/model/1/" + EMPLOYEE))},
        stopping=frozenset({EMPLOYEE}),
        gate=never_asked,
    )
    assert answer.tool_calls[1] == ToolCall(
        TEAM, "team", Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)
    )


def test_the_live_probes_fact_tool_call_is_a_batch_of_one_entry_the_parser_refuses() -> None:
    """The live parse probe (2026-10-06): the model called ``state_facts`` and nested the entry
    one list deeper than the schema says, so the protocol reads a batch of one refused input
    (undecodable, an entry is an object), the text payload asked for did not arrive, and no
    text is present. The outer shape held; the entry's shape is step 11's prompt to earn."""
    (fixture,) = sorted(FIXTURES.glob("parse-probe-*.json"))
    response = json.loads(fixture.read_text(encoding="utf-8"))
    assert stop_reason_of(response) == "tool_use"
    (use,) = tool_uses(response)
    assert use.name == FACT_TOOL and isinstance(use.input, dict)
    answer = parse_answer(response, resolved={}, stopping=frozenset(), gate=never_asked)
    assert answer.text_present is False and answer.tool_calls == (
        ToolCall(use.id, FACT_TOOL, HandledAsBatch(0)),
    )
    (batch,) = answer.fact_batches
    assert isinstance(batch, ParsedBatch) and len(batch.entries) == 1
    (entry,) = batch.entries
    assert isinstance(entry, RefusedInput) and entry.reason is FactRefusal.UNDECODABLE
    assert entry.detail == "an entry is an object, got list"
