"""The admissions derivation against the reader's export: over every history the format
fixtures describe, each answer the export states is the one the derivation gives for that
call, the admitted statements are the export's admitted entries in outcome, batch and entry
order, and the operations the gate reads are the export's trace. No fixture holds an
answer a failure at the parse phase keeps out of the export; such an answer is still
derived here, since what a response carried is a function of the response and the log, and
the omission is the reader's reading of the ending."""

from __future__ import annotations

import pytest

from leaveimpact.agent.admissions import (
    admitted_statements,
    answered_calls,
    gate_before,
    trace_operations,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import AttemptState, fold
from leaveimpact.core.model_calls import ParsedBatch
from leaveimpact.core.stated import Admitted, StatedFact
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories


def state_of(name: str) -> AttemptState:
    return fold(histories.HISTORIES[name](), histories.RULES)


def admitted_in_export(name: str) -> tuple[StatedFact, ...]:
    export = export_of(state_of(name))
    return tuple(
        entry.fact
        for call in export.trace.model_calls
        if call.answer is not None
        for batch in call.answer.fact_batches
        if isinstance(batch, ParsedBatch)
        for entry in batch.entries
        if isinstance(entry, Admitted)
    )


@pytest.mark.parametrize("name", list(cases.FIXTURES))
def test_every_answer_the_export_states_is_the_derivations(name: str) -> None:
    state = state_of(name)
    export = export_of(state)
    derived = {call.ordinal: call for call in answered_calls(state)}
    for index, call in enumerate(export.trace.model_calls, start=1):
        if call.answer is None:
            continue
        assert index in derived, call.id
        assert derived[index].answer == call.answer, call.id
        assert derived[index].position == call.dispatches[-1].outcome_position
    assert trace_operations(state) == export.trace.operations


@pytest.mark.parametrize("name", list(cases.FIXTURES))
def test_answered_calls_come_in_outcome_order_which_is_ordinal_order(name: str) -> None:
    """What the transition's one-call-at-a-time rule gives the readers: the positions of the
    outcomes rise with the ordinals, so a walk by ordinal is a walk by outcome."""
    answered = answered_calls(state_of(name))
    ordinals = [call.ordinal for call in answered]
    positions = [call.position for call in answered]
    assert ordinals == sorted(ordinals) and positions == sorted(positions)
    assert len(set(positions)) == len(positions)


@pytest.mark.parametrize("name", list(cases.FIXTURES))
def test_the_admitted_statements_are_the_exports_in_outcome_batch_and_entry_order(
    name: str,
) -> None:
    assert admitted_statements(state_of(name)) == admitted_in_export(name)


def test_a_fact_beside_a_read_is_admitted_over_the_reads_logged_before_its_answer() -> None:
    state = state_of("facts beside tools in one answer")
    (admitted,) = admitted_statements(state)
    assert admitted == cases.SKILL
    (answered,) = answered_calls(state)
    operations = trace_operations(state)
    before = gate_before(state, answered.position, operations)
    assert isinstance(before(cases.SKILL), Admitted)
    # The gate over an earlier position sees none of the reads: the same statement is refused.
    first_read = min(op.position for op in operations if op.position is not None)
    assert not isinstance(gate_before(state, first_read, operations)(cases.SKILL), Admitted)
