"""The reader's acceptance: every format fixture, re-expressed as the event history its
ruling describes, folds through the transition function and rebuilds its hand-built export
whole (the event log step's ruling on placement and acceptance, part 7). The expected exports
were built before any reader and stay independent of it; a history the rules refuse is
reviewed by name and the log is not loosened for it.

Beside the equality, what the reader derives rather than copies is read back from the
rebuilt export: the answer from the response body, each tool call's disposition from the
resolutions the log holds, the admissions from the reads logged before the answer, the
cost from the usage, the segments' last offsets from their events, the ending from the
ending function."""

from __future__ import annotations

import pytest

from leaveimpact.agent.log_ending import SegmentStatus, status_of
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import fold
from leaveimpact.core import (
    ApprovalState,
    AsOperation,
    OperationId,
    TerminalStatus,
    Undispatched,
    UndispatchedReason,
    UnresolvedToolCall,
    decode_export_bytes,
    export_bytes,
)
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories


def rebuilt(name: str):  # noqa: ANN201 - the export type is the fixtures'
    return export_of(fold(histories.HISTORIES[name](), histories.RULES))


def test_every_fixture_has_a_history() -> None:
    assert list(histories.HISTORIES) == list(cases.FIXTURES)


@pytest.mark.parametrize("name", list(cases.FIXTURES))
def test_a_fixture_rebuilt_from_its_history_is_the_hand_built_export(name: str) -> None:
    expected = cases.FIXTURES[name]()
    actual = rebuilt(name)
    assert actual == expected
    assert export_bytes(actual) == export_bytes(expected)
    assert decode_export_bytes(export_bytes(actual)) == expected


def test_an_open_attempt_has_no_export() -> None:
    open_history = histories.HISTORIES["a cut call"]()[:-1]
    state = fold(open_history, histories.RULES)
    with pytest.raises(ValueError, match="built from a closed attempt"):
        export_of(state)
    status = status_of(state)
    assert status.open and status.segment is SegmentStatus.OPEN
    assert status.approval is ApprovalState.APPROVED


def test_dispositions_are_what_the_log_proves() -> None:
    """A resolved call is the operation it became; a call after a stopping result was never
    reached; a call with no resolution and nothing to prove it unreached is unresolved."""
    ended = rebuilt("a multi-tool answer whose first call ends the attempt")
    (call,) = ended.trace.model_calls
    assert call.answer is not None
    first, second = call.answer.tool_calls
    assert first.disposition == AsOperation(OperationId("call-1/tu_1"))
    assert second.disposition == Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)
    lost = rebuilt("a tool call whose result was lost before it was logged")
    (call,) = lost.trace.model_calls
    assert call.answer is not None
    assert isinstance(call.answer.tool_calls[0].disposition, UnresolvedToolCall)


def test_the_ending_is_the_recorded_defect_whoever_closed() -> None:
    finalized = rebuilt("a recorded defect an operator finalized")
    assert finalized.record.status is TerminalStatus.FAILED
    assert finalized.record.failure is not None
    assert finalized.record.failure.category.value == "defect"
    assert finalized.record.abandonment is not None
    assert finalized.record.abandonment.authority == "operator"
