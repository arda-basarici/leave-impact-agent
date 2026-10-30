"""The narration over every history the suite holds: one line per event with the event's
position, kind and instant; the prefix property, that the lines over any prefix of a log are
the prefix of the lines over the whole, which is what "each line claims only what its event
establishes" means for the counts; every event kind reached and every outcome variant naming
itself; a claim read as first, a resumption or a recovery by the transition's own
classification; an answer line's counts as the admissions module reads them over the reads
below the answer; and no model prose on any line."""

from __future__ import annotations

import pytest

from leaveimpact.agent.admissions import answered_calls
from leaveimpact.agent.log_events import EventKind, LoggedEvent, kind_of
from leaveimpact.agent.log_transition import AttemptState, fold
from leaveimpact.app.narration import Line, extend, narration
from leaveimpact.core.model_calls import ParsedBatch
from leaveimpact.core.stated import Admitted
from tests.unit import log_histories as histories
from tests.unit import narration_histories as variants

ALL: dict[str, histories.Build] = {
    **histories.HISTORIES,
    "approved then stopped before the resume": histories.approved_then_stopped_before_resume,
    "resumed then stopped at the bound": histories.resumed_then_stopped_at_the_bound,
    "three claims left open": lambda: histories.left_open_claims(3),
    **variants.VARIANTS,
}


def lines_of(events: tuple[LoggedEvent, ...]) -> tuple[Line, ...]:
    return narration(fold(events, histories.RULES), histories.RULES)


def line_of(name: str, kind: EventKind, nth: int = 1) -> Line:
    """The ``nth`` line of ``kind`` in the history ``name``."""
    matching = [line for line in lines_of(ALL[name]()) if line.kind is kind]
    return matching[nth - 1]


@pytest.mark.parametrize("name", list(ALL))
def test_one_line_per_event_with_its_position_kind_and_instant(name: str) -> None:
    events = ALL[name]()
    lines = lines_of(events)
    assert [(line.position, line.kind, line.recorded_at) for line in lines] == [
        (event.position, kind_of(event.event), event.timestamp) for event in events
    ]
    assert all(line.text for line in lines)


@pytest.mark.parametrize("name", list(ALL))
def test_the_lines_over_a_prefix_are_the_prefix_of_the_lines_over_the_whole(name: str) -> None:
    events = ALL[name]()
    whole = lines_of(events)
    for n in range(1, len(events) + 1):
        assert lines_of(events[:n]) == whole[:n], f"the lines over the first {n} events differ"


@pytest.mark.parametrize("name", list(ALL))
def test_extending_a_prefix_by_the_rest_gives_the_state_and_the_lines_over_the_whole(
    name: str,
) -> None:
    """The stream's tick after its first: the state folded over a prefix, extended by the
    events past it, is the state over the whole, and the lines it adds are the whole's
    lines past the prefix, for every cut of every history."""
    events = ALL[name]()
    whole_state = fold(events, histories.RULES)
    whole_lines = narration(whole_state, histories.RULES)
    for n in range(len(events) + 1):
        prefix = fold(events[:n], histories.RULES) if n else AttemptState()
        state, added = extend(prefix, events[n:], histories.RULES)
        assert state == whole_state, f"the state extended from {n} events differs"
        assert added == whole_lines[n:], f"the lines added past {n} events differ"


def test_every_event_kind_is_reached_by_some_history() -> None:
    reached = {line.kind for name in ALL for line in lines_of(ALL[name]())}
    assert reached == set(EventKind)


VARIANT_LINES: tuple[tuple[str, EventKind, int, str], ...] = (
    ("a declined attempt", EventKind.DECLINED, 1, "a person declined the plan"),
    ("facts beside tools in one answer", EventKind.ADMITTED, 1, "run admitted: scenario"),
    (
        "facts beside tools in one answer",
        EventKind.SEGMENT_STARTED,
        1,
        "a worker claimed the attempt (segment 1)",
    ),
    (
        "facts beside tools in one answer",
        EventKind.OPERATION,
        1,
        "the frozen prefetch's read 1: work_items on jira, 1 record",
    ),
    (
        "facts beside tools in one answer",
        EventKind.OPERATION,
        4,
        "the read model call 1 asked for in tool call tu_1: work_item on jira, one record "
        "(work_item ticket_042)",
    ),
    (
        "facts beside tools in one answer",
        EventKind.COUNT_STARTED,
        1,
        "a counting request was started for role investigator",
    ),
    (
        "facts beside tools in one answer",
        EventKind.COUNT_OUTCOME,
        1,
        "the counting request answered: 4,096 input tokens; read as counted",
    ),
    (
        "facts beside tools in one answer",
        EventKind.DISPATCH_INTENT,
        1,
        "model call 1 authorized (dispatch 1, role investigator): 1 read shown, input bounded "
        "at 4,096 tokens, output at most 512 tokens, worst case 4,608 tokens and $0.0084",
    ),
    (
        "facts beside tools in one answer",
        EventKind.DISPATCH_OUTCOME,
        1,
        "model call 1, dispatch 1 answered: a complete response (stop reason tool_use, 840 "
        "ms); 1 tool call, 1 statement made, 1 admitted by the gates, 0 refused; read as the "
        "model's behaviour under rule registered-stop-reason",
    ),
    (
        "facts beside tools in one answer",
        EventKind.APPROVAL_REQUESTED,
        1,
        "the review payload is frozen with 0 claims; the run awaits the decision",
    ),
    (
        "facts beside tools in one answer",
        EventKind.APPROVED,
        1,
        "the registered automatic policy approved the review payload",
    ),
    (
        "facts beside tools in one answer",
        EventKind.RESUMED,
        1,
        "the worker resumed after the approval",
    ),
    (
        "facts beside tools in one answer",
        EventKind.COMPLETED,
        1,
        "the run completed: the system produced its final claims; the reservation was",
    ),
    ("a malformed batch", EventKind.DISPATCH_OUTCOME, 1, "1 fact payload unreadable"),
    (
        "a refused fact that cannot construct a value",
        EventKind.DISPATCH_OUTCOME,
        1,
        "0 tool calls, 2 statements made, 1 admitted by the gates, 1 refused, 1 input no "
        "statement could be made of",
    ),
    (
        "a cut call",
        EventKind.DISPATCH_OUTCOME,
        1,
        "a complete response (stop reason max_tokens, 840 ms); 1 tool call, 0 statements made",
    ),
    (
        "an unresolved dispatch followed by an answered one",
        EventKind.DISPATCH_INTENT,
        2,
        "model call 1 authorized (dispatch 2",
    ),
    (
        "a recovered attempt",
        EventKind.SEGMENT_STARTED,
        2,
        "a worker recovered the attempt (segment 2, recovery 1)",
    ),
    (
        "an approval wait across a restart",
        EventKind.SEGMENT_ENDED,
        1,
        "the worker stopped cleanly (segment 1); the run awaits the decision on its review payload",
    ),
    (
        "an approval wait across a restart",
        EventKind.SEGMENT_STARTED,
        2,
        "a worker recovered the attempt (segment 2, recovery 1)",
    ),
    # Segment 2 claimed and never ended cleanly, so the claim after the approval is a
    # recovery under the transition's reading, not a resumption.
    (
        "an approval wait across a restart",
        EventKind.SEGMENT_STARTED,
        3,
        "a worker recovered the attempt (segment 3, recovery 2)",
    ),
    (
        "an abandoned attempt",
        EventKind.ABANDONED,
        1,
        "an operator cancelled the attempt; it is abandoned; the reservation was",
    ),
    (
        "a recorded defect an operator finalized",
        EventKind.OPERATION,
        2,
        "a malformed record at LIA-42: no world id; the run is stopped here by a defect at "
        "operation call-1/tu_1",
    ),
    (
        "a recorded defect an operator finalized",
        EventKind.ABANDONED,
        1,
        "the attempt lost its worker and was judged not resumable; it is abandoned",
    ),
    (
        "a multi-tool answer whose first call ends the attempt",
        EventKind.FAILED,
        1,
        "the run failed: a defect at operation call-1/tu_1: a malformed record",
    ),
    (
        "a request whose input bound was never established",
        EventKind.COUNT_OUTCOME,
        1,
        "the counting request failed on a transient cause (service error 429 "
        "ThrottlingException); read as failed",
    ),
    (
        "a request whose input bound was never established",
        EventKind.COUNT_OUTCOME,
        2,
        "the counting request failed on a transient cause (the client gave up, timeout); read "
        "as failed",
    ),
    (
        "a request whose input bound was never established",
        EventKind.FAILED,
        1,
        "the run failed: an infrastructure fault at counting operation",
    ),
    (
        "an attempt admitted and never claimed",
        EventKind.ABANDONED,
        1,
        "an operator cancelled the attempt",
    ),
    (
        "approved then stopped before the resume",
        EventKind.APPROVED,
        1,
        "a human approved the review payload",
    ),
    (
        "approved then stopped before the resume",
        EventKind.SEGMENT_STARTED,
        2,
        "to resume it after the approval (segment 2)",
    ),
    (
        "approved then stopped before the resume",
        EventKind.SEGMENT_ENDED,
        2,
        "the worker stopped cleanly (segment 2) without ending the run; it awaits a worker to "
        "continue it or an abandonment",
    ),
    (
        "approved then stopped before the resume",
        EventKind.SEGMENT_STARTED,
        3,
        "a worker recovered the attempt (segment 3, recovery 1)",
    ),
    (
        "a read that found nothing and one the wrapper refused",
        EventKind.OPERATION,
        2,
        "work_item on jira, no such record (evidence of absence)",
    ),
    (
        "a read that found nothing and one the wrapper refused",
        EventKind.OPERATION,
        3,
        "tool call tu_2: employee on no source, the call was refused before any source was "
        "asked: the id names no employee",
    ),
    (
        "two skipped reads",
        EventKind.OPERATION,
        2,
        "tool call tu_1 was not run: the cap was reached",
    ),
    (
        "two skipped reads",
        EventKind.OPERATION,
        3,
        "tool call tu_2 was not run: the source was already unreachable in this run",
    ),
    (
        "an unreachable source",
        EventKind.OPERATION,
        1,
        "work_items on jira, jira unreachable: connection refused after three retries",
    ),
    (
        "a count the service refused",
        EventKind.COUNT_OUTCOME,
        1,
        "the counting request was refused (service error 403 AccessDeniedException); read as "
        "a misconfiguration",
    ),
    (
        "a count that failed unclassified",
        EventKind.COUNT_OUTCOME,
        1,
        "failed in a way the method does not classify (a local error, builtins.KeyError); the "
        "run is stopped here by an infrastructure fault at counting operation",
    ),
    (
        "a broken stream",
        EventKind.DISPATCH_OUTCOME,
        1,
        "model call 1, dispatch 1: the stream broke (connection reset mid-stream); read as an "
        "infrastructure fault under rule stream; the run is stopped here by an infrastructure "
        "fault at call-1 dispatch 1 (send)",
    ),
    (
        "a client error",
        EventKind.DISPATCH_OUTCOME,
        1,
        "the client gave up with no answer (timeout: read timed out), so whether the request "
        "ran is unknown; read as an infrastructure fault under rule gave_up",
    ),
    (
        "a request refused before send",
        EventKind.DISPATCH_OUTCOME,
        1,
        "the client refused the request before sending it (the request exceeds the client's "
        "size bound); read as an infrastructure fault under rule never_sent",
    ),
    (
        "a finalization that ends at the cap",
        EventKind.FINALIZATION_ENTERED,
        1,
        "the run stopped investigating and began to finalize",
    ),
    (
        "a finalization that ends at the cap",
        EventKind.APPROVAL_REQUESTED,
        1,
        "the review payload is frozen with 0 claims, at the cap; the run awaits the decision "
        "and will report what it has",
    ),
    (
        "a finalization that ends at the cap",
        EventKind.CAP_EXHAUSTED,
        1,
        "the run ended at the cap: the system reported what it had; the reservation was "
        "reconciled, $0.0084 charged",
    ),
    (
        "a human's approval resumed under an override",
        EventKind.SEGMENT_STARTED,
        2,
        "a worker claimed the attempt to resume it after the approval (segment 2) on harness "
        "commit cccccccccccc…, under an operator's override of the first segment's commit "
        "bbbbbbbbbbbb…",
    ),
    (
        "a failure in the harness's prefetch",
        EventKind.FAILED,
        1,
        "the run failed: an infrastructure fault at the harness (prefetch): the prefetch "
        "raised before its first read",
    ),
)


PARSE_FAILED: tuple[tuple[str, EventKind, int, str], ...] = (
    (
        "a response the parser cannot read",
        EventKind.DISPATCH_OUTCOME,
        1,
        "model call 1, dispatch 1 answered: a complete response (stop reason end_turn, 840 "
        "ms); the response could not be read as an answer (a response holds an output "
        "object); read as the model's behaviour under rule registered-stop-reason",
    ),
    (
        "a response the parser cannot read",
        EventKind.FAILED,
        1,
        "the run failed: a defect at call-1 dispatch 1 (parse): a response holds an output object",
    ),
)


@pytest.mark.parametrize(("name", "kind", "nth", "expected"), (*VARIANT_LINES, *PARSE_FAILED))
def test_every_outcome_variant_names_itself(
    name: str, kind: EventKind, nth: int, expected: str
) -> None:
    assert expected in line_of(name, kind, nth).text


def test_an_answer_lines_counts_are_the_admissions_over_the_reads_below_it() -> None:
    """The admissions module derives each answer over the reads logged before it; the line
    states that derivation's counts, computed from the state just after the outcome and never
    from the whole log, which the prefix property holds over every history."""
    for name in ALL:
        events = ALL[name]()
        lines = lines_of(events)
        try:
            answered = answered_calls(fold(events, histories.RULES))
        except ValueError:
            # A body the parser cannot read: the module refuses it by design, and the
            # line for it is asserted on its own above.
            continue
        for call in answered:
            admitted = sum(
                isinstance(entry, Admitted)
                for batch in call.answer.fact_batches
                if isinstance(batch, ParsedBatch)
                for entry in batch.entries
            )
            assert f", {admitted} admitted by the gates, " in lines[call.position - 1].text


def test_no_line_carries_model_prose() -> None:
    texts = [line.text for line in lines_of(histories.facts_beside_tools())]
    assert not any("Looking at the ticket." in text for text in texts)
    assert not any("Hypothesis" in text for text in texts)
    texts = [line.text for line in lines_of(histories.recovered_attempt())]
    assert not any("Done." in text for text in texts)


def test_a_line_names_no_producer_identity() -> None:
    texts = " ".join(
        line.text for line in lines_of(variants.overridden_claim_after_a_human_approval())
    )
    assert "human:reviewer" not in texts and "operator:ops" not in texts
    assert "policy:automatic" not in " ".join(
        line.text for line in lines_of(histories.facts_beside_tools())
    )
