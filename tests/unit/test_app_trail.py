"""The trail view over exports: every operation, call, dispatch and counting operation of
the all-types run with its anchors, the evidence anchors the report links to minted here,
the three ledger amounts apart, the admitted statements with their quotations and the
composition's exclusion beside the one it left out; the format fixtures' cases for the
statement kinds a page must state (a malformed batch, a refused statement, a refused input,
a cut call, an unresolved dispatch), an attempt that never ran and a failure at the input
bound with its counting operations' outcomes."""

from __future__ import annotations

from datetime import UTC, datetime

from leaveimpact.app.public import PublicId, PublicReplay
from leaveimpact.app.report import report_view
from leaveimpact.app.trail import TrailView, operation_anchor, trail_view
from leaveimpact.core import RunExport, ScenarioId
from tests.unit import format_fixtures as cases
from tests.unit import report_view_fixture as fixture

PUBLISHED = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def view_of(export: RunExport) -> TrailView:
    replay = PublicReplay(
        PublicId("page"), ScenarioId("scenario_003"), None, PUBLISHED, export.record.status
    )
    return trail_view(replay, export, fixture.INSTANTS)


def test_every_operation_call_and_count_of_the_run_is_on_the_trail_with_its_anchor() -> None:
    view = view_of(fixture.all_types())
    assert [op.anchor for op in view.operations] == [f"op-{p}" for p in (3, 4, 5, 6, 7, 8, 9, 25)]
    leave, people, _, _, _, _, runbook, reread = view.operations
    assert (leave.tool, leave.source, leave.outcome) == ("leave", "frappe", "one record")
    assert leave.records == ("leave leave_005",) and leave.arguments == '{"id": "leave_005"}'
    assert leave.origin == "the frozen prefetch" and leave.origin_anchor is None
    assert people.outcome == "2 records" and people.records == (
        "employee emp_017",
        "employee emp_023",
    )
    assert runbook.records == ("document doc_003",)
    assert reread.origin == "model call call-1" and reread.origin_anchor == "call-call-1"
    assert reread.at.recorded_at == fixture.INSTANTS[25]
    (call,) = view.calls
    assert call.anchor == "call-call-1" and call.role == "investigator"
    assert call.configuration == "eu.model with max_tokens=512, temperature=0"
    (dispatch,) = call.dispatches
    assert dispatch.intent.position == 20 and dispatch.outcome is not None
    assert dispatch.outcome.position == 21
    assert [at.position for at in dispatch.shown] == [3]
    assert dispatch.observation == "complete response, stop reason tool_use, 840 ms"
    assert dispatch.attribution == "read as behaviour by the rule registered-stop-reason"
    assert dispatch.usage == ("120 input tokens", "30 output tokens")
    assert dispatch.tokens == "at least 150 tokens"
    assert dispatch.cost == "$0.0003" and dispatch.bound_anchor == "count-" + view.counts[0].id
    (count,) = view.counts
    assert count.anchor == "count-" + count.id and count.reading == "counted"
    assert count.outcome.startswith("counted 4,096 input tokens")


def test_the_report_links_resolve_to_anchors_the_trail_mints() -> None:
    export = fixture.all_types()
    replay = PublicReplay(
        PublicId("page"), ScenarioId("scenario_003"), None, PUBLISHED, export.record.status
    )
    report = report_view(replay, export, fixture.INSTANTS)
    trail = view_of(export)
    minted = {op.anchor for op in trail.operations}
    cited = {
        operation_anchor(position)
        for section in report.impacts
        for block in (section.impact, *section.assessments, *section.actions)
        for item in block.evidence
        for position in item.positions
    }
    assert cited and cited <= minted


def test_the_answer_shows_the_tool_call_and_the_admitted_statements_with_their_quotations() -> None:
    view = view_of(fixture.all_types())
    answer = view.calls[0].answer
    assert answer is not None and answer.text_present
    (tool_call,) = answer.tool_calls
    assert tool_call.name == "work_item" and tool_call.anchor == "op-25"
    assert tool_call.disposition == "became operation call-1/tu_1"
    (batch,) = answer.batches
    assert batch.malformed_raw is None
    kinds = [(entry.kind, entry.quote) for entry in batch.entries]
    assert kinds == [
        ("admitted", cases.SKILL.quote),
        ("admitted", fixture.REQUIREMENT_QUOTE),
        ("admitted", fixture.OWNER_QUOTE),
    ]
    assert batch.entries[0].summary == "has_skill of emp_023 is kafka, read from comment_001"
    assert batch.entries[1].target_span == "Payments: rotate the keys"
    assert all(entry.excluded is None for entry in batch.entries)


def test_an_excluded_statement_is_marked_on_the_trail_and_in_the_composition() -> None:
    view = view_of(fixture.ticket_returned_two_ways())
    answer = view.calls[0].answer
    assert answer is not None
    assert answer.batches[0].entries[0].excluded == "carrier withdrawn"
    assert view.composition.exclusions == (
        "has_skill of emp_023 is kafka, read from comment_001: carrier withdrawn",
    )


def test_the_ledger_keeps_the_three_amounts_apart() -> None:
    charges = view_of(fixture.all_types()).charges
    assert charges.observed == "$0.0003" and charges.known == "$0.0003"
    assert charges.reserved is not None and charges.state == "reconciled"
    assert charges.charged == "$0.0003" and charges.retained == "$0.0000"
    assert charges.calls == 1 and charges.dispatches == 1
    assert charges.usage == ("120 input tokens", "30 output tokens")
    none = view_of(cases.never_claimed()).charges
    assert none.observed == "not priced" and none.known == "$0.0000"
    assert none.reserved is not None and none.charged == "$0.0000"


def test_the_statement_kinds_the_format_fixtures_hold_each_have_a_line() -> None:
    malformed = view_of(cases.malformed_batch())
    batch = malformed.calls[0].answer.batches[0] if malformed.calls[0].answer else None
    assert batch is not None and batch.malformed_raw is not None and batch.refused_by
    refused = view_of(cases.refused_fact())
    entries = [
        entry
        for call in refused.calls
        if call.answer
        for batch in call.answer.batches
        for entry in batch.entries
    ]
    assert {entry.kind for entry in entries} >= {"refused", "refused input"}
    assert all(entry.reason for entry in entries if entry.kind != "admitted")
    assert any(entry.raw is not None for entry in entries if entry.kind == "refused input")
    cut = view_of(cases.cut_call())
    assert any("max_tokens" in d.observation for call in cut.calls for d in call.dispatches)
    unresolved = view_of(cases.unresolved_then_answered())
    observations = [d.observation for call in unresolved.calls for d in call.dispatches]
    assert any(o.startswith("no outcome recorded") for o in observations)
    assert any(d.outcome is None for call in unresolved.calls for d in call.dispatches)


def test_an_attempt_that_never_ran_and_a_failure_at_the_input_bound_render_whole() -> None:
    never = view_of(cases.never_claimed())
    assert never.operations == () and never.calls == () and never.counts == ()
    assert never.segments == () and never.finalization_entered is None
    assert never.approval.state == "not requested" and never.approval.requested is None
    bound = view_of(cases.input_bound_exhausted())
    assert len(bound.counts) == 3
    readings = [count.reading for count in bound.counts]
    assert readings.count("failed") >= 2
    assert bound.ending.failure_anchor == "count-" + bound.counts[-1].id
    assert any("service error 429" in count.outcome for count in bound.counts)
    assert any("client error, timeout" in count.outcome for count in bound.counts)


def test_the_approval_and_the_segments_are_stated_with_their_stamps() -> None:
    view = view_of(fixture.all_types())
    assert view.approval.state == "approved" and view.approval.approver == "automatic"
    assert view.approval.requested is not None and view.approval.requested.position == 30
    assert view.approval.resumed is not None and view.approval.resumed.position == 32
    assert len(view.segments) == 1 and view.segments[0].startswith("segment 1: harness ")
    assert view.composition.author == "rules" and view.composition.placements == ()
