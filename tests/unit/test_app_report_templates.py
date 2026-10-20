"""The report template over the view-level fixtures, through the application's own template
environment with its strict undefined: every branch renders (the all-types page, a withdrawn
record, an unavailable citation, a claim set that is not well-formed with its unlinked section
and defect banner, a degraded run's condition banner, a cap-exhausted ending with its table,
an attempt that never ran), each with every claim's anchor present exactly once, and the
page's prose escaped."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from leaveimpact.app.main import templating
from leaveimpact.app.public import PublicId, PublicReplay
from leaveimpact.app.report import ReportView, report_view
from leaveimpact.app.trail import trail_view
from leaveimpact.core import (
    EvidenceRef,
    RunCondition,
    RunExport,
    ScenarioId,
    Source,
    TerminalStatus,
    Unknown,
    UnknownReason,
)
from leaveimpact.core.ids import claim_id
from leaveimpact.core.predicates import PredicateName
from tests.unit import format_fixtures as cases
from tests.unit import report_view_fixture as fixture
from tests.unit import stated_fixture as f

PUBLISHED = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
TEMPLATES = templating()


def rendered(export: RunExport, title: str | None = "A <b>title</b>") -> tuple[str, ReportView]:
    status = export.record.status
    replay = PublicReplay(PublicId("page"), ScenarioId("scenario_003"), title, PUBLISHED, status)
    view = report_view(replay, export, fixture.INSTANTS)
    page = TEMPLATES.env.get_template("report.html").render(
        view=view,
        replay=replay,
        code_version="b" * 40,
        served_world_version="7" * 64,
        live_runs=False,
    )
    return page, view


def trail_of(export: RunExport) -> str:
    replay = PublicReplay(
        PublicId("page"), ScenarioId("scenario_003"), None, PUBLISHED, export.record.status
    )
    view = trail_view(replay, export, fixture.INSTANTS)
    return TEMPLATES.env.get_template("trail.html").render(
        view=view,
        replay=replay,
        code_version="b" * 40,
        served_world_version="7" * 64,
        live_runs=False,
    )


def anchors_once(page: str, view: ReportView) -> None:
    for id in view.claim_ids():
        assert page.count(f'id="{id}"') == 1, id


def test_the_all_types_page_renders_every_claim_once_and_escapes_the_title() -> None:
    page, view = rendered(fixture.all_types())
    anchors_once(page, view)
    assert "A &lt;b&gt;title&lt;/b&gt;" in page and "<b>title</b>" not in page
    assert "model-generated rationale" in page
    assert f"<mark>{fixture.REQUIREMENT_QUOTE}</mark>" in page
    assert f"<mark>{fixture.OWNER_QUOTE}</mark>" in page
    assert 'the field <span class="cited">due_on</span>' in page
    assert "Unlinked claims" not in page and "Degraded run" not in page


def test_a_withdrawn_record_and_an_unavailable_citation_render_their_notices() -> None:
    page, view = rendered(fixture.ticket_returned_two_ways())
    anchors_once(page, view)
    assert "Withdrawn: this run's own reads returned it with different contents" in page
    assert "quotation (has_skill) read from it; excluded from the view: carrier withdrawn." in page
    page, view = rendered(fixture.citing_an_unread_record())
    anchors_once(page, view)
    assert "Evidence unavailable: no completed read of this run returned it." in page


def test_a_claim_set_that_is_not_well_formed_renders_the_banner_and_the_unlinked_section() -> None:
    page, view = rendered(fixture.malformed_set())
    anchors_once(page, view)
    assert "Defect: the claim set is not well-formed." in page
    assert "Unlinked claims" in page and 'id="claim_012"' in page
    assert "claim_099 (unavailable)" in page


def test_a_degraded_run_renders_the_condition_banner_with_its_unknowns_linked() -> None:
    export = fixture.all_types()
    inaccessible = Unknown(
        claim_id=claim_id(13),
        evidence_refs=(EvidenceRef(Source.CORPUS, f.CLAUSE_REF),),
        subject=f.CLAUSE_REF,
        required_fact=PredicateName.REQUIRES,
        reason=UnknownReason.INACCESSIBLE,
    )
    degraded = replace(
        export,
        record=replace(
            export.record, observed_condition=RunCondition.all_reachable().without(Source.CORPUS)
        ),
        trace=replace(export.trace, claims=(*export.trace.claims, inaccessible)),
    )
    page, view = rendered(degraded)
    anchors_once(page, view)
    assert "Degraded run." in page and "could not reach\n  corpus." in page
    assert 'href="#claim_013"' in page
    trail = trail_of(degraded)
    assert "Degraded run." in trail and 'href="/replays/page#claim_013"' in trail


def test_a_cap_exhausted_ending_renders_its_table_and_a_never_run_attempt_its_headline() -> None:
    export = fixture.all_types()
    capped = replace(export, record=replace(export.record, status=TerminalStatus.CAP_EXHAUSTED))
    page, _ = rendered(capped)
    assert "stopped under the registered caps" in page
    assert "<td>model calls</td><td>1</td><td>20</td>" in page
    page, view = rendered(cases.never_claimed(), title=None)
    assert view.claim_ids() == ()
    assert "Nothing ran: no worker claimed the attempt." in page
    assert "The leave record (leave_005) is not among this run's reads." in page
    assert "<h1>page</h1>" in page


def test_the_trail_template_renders_every_fixture_whole() -> None:
    page = trail_of(fixture.all_types())
    assert 'id="op-3"' in page and 'id="call-call-1"' in page and 'id="count-' in page
    assert "excluded from the view" not in page
    page = trail_of(fixture.ticket_returned_two_ways())
    assert "excluded from the view: carrier withdrawn" in page
    assert "<dt>excluded</dt>" in page
    page = trail_of(cases.malformed_batch())
    assert "Malformed: the parser" in page and "<pre>" in page
    page = trail_of(cases.refused_fact())
    assert "<strong>refused input</strong>" in page and "The entry as it arrived" in page
    page = trail_of(cases.never_claimed())
    assert "No read was made." in page and "No model was called." in page
    assert "reserved</dt><dd>$" in page
    page = trail_of(cases.input_bound_exhausted())
    assert "service error 429" in page and 'id="count-' in page
    page = trail_of(cases.approval_wait_across_restart())
    assert "<dt>Execution</dt>" in page and "<dt>requested</dt>" in page
