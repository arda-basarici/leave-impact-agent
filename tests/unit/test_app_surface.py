"""The surface over in-memory doubles: the listing as the served world's projection; the replay
page admitted for a row the admission agrees with, with no run id on it, the report of a
closed attempt with its claims, evidence, quotations marked and the rationale labelled, the
progress header for an open one, and the unavailable page for a closed attempt the reader
cannot fold; one byte-identical
not-found page for an unknown name, an honest row of another world, a forged row carrying the
served world for another world's attempt, and a name that is not a slug; the unavailable page
when the cache does not serve the version or a store does not answer, after admission so an
unavailable cache never tells a published name from an unknown one; the log session closed on
every path; the results page over the public results decoded once at creation, its
labels and figures in their rows, and the served-world line on every page the surface
answers; and the sweep: every registered route classified, every attempt-scoped route
walked with the forged name and the unknown name to the same bytes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from markupsafe import escape

from leaveimpact.agent.log_events import Admitted, LoggedEvent, RefusedBy
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.main import ROUTES, Services, Surface, create_app
from leaveimpact.app.public import PublicId
from leaveimpact.app.results import SERVED_WORLD_LABEL, results_view
from leaveimpact.app.store import AppStoreInvariantBroken, AppStoreUnavailable
from leaveimpact.app.walkthroughs import Walkthrough
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.ports.errors import Source, SourceUnreachable
from leaveimpact.results.committed import committed_results
from leaveimpact.results.public import PublicResults
from tests.unit import log_histories as histories
from tests.unit import report_view_fixture as reported
from tests.unit import stated_fixture as f
from tests.unit import test_results_codec as codec
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.live_routes_fixture import DECISION_FORM, live_services
from tests.unit.log_store_memory import MemoryLog
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    OTHER_WORLD,
    SERVED,
    Rows,
    admission_only,
    history_in_world,
    row,
)

CODE = "b" * 40
FORGED = "forged"
UNKNOWN = "nobody-here"


class Sessions:
    """Log sessions over one in-memory log, each opening and closing counted, the whole
    loads and the reads past a position counted apart (the stream's ticks)."""

    def __init__(self, memory: MemoryLog) -> None:
        self.memory = memory
        self.opened = 0
        self.closed = 0
        self.loads = 0
        self.afters: list[int] = []

    def __call__(self) -> Sessions:
        self.opened += 1
        return self

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        self.loads += 1
        return self.memory.load(run_id, attempt, rules=rules)

    def events_after(
        self, run_id: str, attempt: int, *, after: int
    ) -> tuple[LoggedEvent, ...]:
        self.afters.append(after)
        return self.memory.events_after(run_id, attempt, after=after)

    def close(self) -> None:
        self.closed += 1


class Store:
    """The cache's readiness and the app schema as a test moves them."""

    def __init__(self) -> None:
        self.versions = frozenset({SERVED})
        self.reachable = True
        self.schema = True

    def ready_versions(self) -> frozenset[WorldVersion]:
        if not self.reachable:
            raise SourceUnreachable(Source.CORPUS, "connection refused: OperationalError")
        return self.versions

    def app_schema(self) -> bool:
        if not self.reachable:
            raise AppStoreUnavailable("the app store did not answer: OperationalError")
        return self.schema


def unfoldable_history(*, run_id: str) -> tuple[histories.LoggedEvent, ...]:
    """The all-types history whose admission froze a parser that is not this code's: the log
    folds it and the export reader refuses it."""
    events = reported.reported_history(SERVED, run_id=run_id)
    first = events[0]
    assert isinstance(first.event, Admitted)
    other = replace(first.event.inputs, parser=RefusedBy("another-parser", "e" * 64))
    return (replace(first, event=Admitted(other)), *events[1:])


class Rig:
    """The whole application over the doubles: a closed run of the served world (``run-12``),
    a closed run of another world (``run-13``), an open run of the served world (``run-14``);
    rows for the first (``served``), an honest row for the second (``embargoed``), a forged row
    carrying the served world for a third run of the other world (``forged``, since one
    attempt has one row), a row for the open one (``live``), a row for the all-types run with
    its claims (``reported``, ``run-16``) and one for a closed run whose admission froze another
    parser, which the reader refuses to fold (``unfoldable``, ``run-17``)."""

    def __init__(self) -> None:
        memory = MemoryLog()
        memory.seed(history_in_world(CLOSED, SERVED))
        memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-13"))
        memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-15"))
        memory.seed(admission_only(SERVED, run_id="run-14"))
        memory.seed(reported.reported_history(SERVED, run_id="run-16"))
        memory.seed(unfoldable_history(run_id="run-17"))
        self.sessions = Sessions(memory)
        self.store = Store()
        self.rows = Rows(
            row("served", "run-12", SERVED, title="The handover nobody wrote down"),
            row("embargoed", "run-13", OTHER_WORLD),
            row(FORGED, "run-15", SERVED),
            row("live", "run-14", SERVED),
            row("reported", "run-16", SERVED, title="The handover with its evidence"),
            row("unfoldable", "run-17", SERVED),
        )

    def client(self, walkthroughs: tuple[Walkthrough, ...] = ()) -> TestClient:
        return TestClient(create_app(services(self, walkthroughs=walkthroughs)))


def services(
    rig: Rig,
    results: Callable[[], PublicResults] = codec.results,
    walkthroughs: tuple[Walkthrough, ...] = (),
) -> Services:
    return Services(
        CODE,
        CONFIGURATION,
        rig.store.ready_versions,
        rig.store.app_schema,
        rig.rows,
        rig.sessions,
        histories.RULES,
        results,
        lambda: walkthroughs,
        **live_services(rig.sessions.memory, MemoryAppStore()),
    )


def test_the_listing_is_the_served_worlds_projection_with_links_to_each_name() -> None:
    rig = Rig()
    with rig.client() as web:
        page = web.get("/replays")
    assert page.status_code == 200
    assert "The handover nobody wrote down" in page.text and 'href="/replays/served"' in page.text
    assert 'href="/replays/live"' in page.text and 'href="/replays/forged"' in page.text
    assert "embargoed" not in page.text, "another world's row is not listed"
    assert "run-12" not in page.text and "run-13" not in page.text
    assert rig.sessions.opened == 0, "the listing reads no log"


def test_the_replay_page_shows_the_admitted_attempts_ending_and_no_run_id() -> None:
    rig = Rig()
    with rig.client() as web:
        page = web.get("/replays/served")
        live = web.get("/replays/live")
    assert page.status_code == 200
    assert "The handover nobody wrote down" in page.text
    assert "scenario_003" in page.text and ">completed<" in page.text
    assert "run-12" not in page.text
    assert live.status_code == 200 and ">in progress<" in live.text
    assert "investigating; its report renders when it closes" in live.text
    assert "The run completed. It reported no impact." in page.text
    assert rig.sessions.opened == 2 and rig.sessions.closed == 2


def test_the_report_page_states_the_claims_with_their_evidence_as_the_run_read_it() -> None:
    rig = Rig()
    with rig.client() as web:
        page = web.get("/replays/reported")
    assert page.status_code == 200
    text = page.text
    assert "The handover with its evidence" in text and "run-16" not in text
    assert (
        "Alice Demir (emp_017) is on annual leave from 2026-03-09 to 2026-03-13 (5 days, approved)."
        in text
    )
    assert "Assign Deniz Kaya (emp_023) to Payments: rotate the keys (ticket_042)." in text
    assert "model-generated rationale" in text and reported.RATIONALE in text
    assert "Deniz Kaya (emp_023) cannot cover Release review (event_007): is not available." in text
    assert f"<mark>{f.REMARK}</mark>" in text, "the admitted quotation is marked in the comment"
    assert "Model-supplied quotation (has_skill), marked above." in text
    assert "Recorded in the log at " in text and 'href="/replays/reported/trail#op-7"' in text
    assert 'id="claim_001"' in text and 'href="#claim_001"' in text
    assert "The sources disagree on the owns work item" in text
    assert "The run completed." in text and "It reported no impact." not in text
    assert "<script>" not in text


def test_the_trail_page_states_what_the_run_did_with_the_anchors_the_report_links() -> None:
    rig = Rig()
    with rig.client() as web:
        report = web.get("/replays/reported")
        trail = web.get("/replays/reported/trail")
        live = web.get("/replays/live/trail")
    assert trail.status_code == 200 and "run-16" not in trail.text
    assert 'id="op-7"' in trail.text and 'id="call-call-1"' in trail.text
    assert 'href="/replays/reported/trail#op-7"' in report.text
    assert "<strong>work_items</strong> on jira" in trail.text
    assert "complete response, stop reason tool_use" in trail.text
    assert (
        "<strong>admitted</strong>: has_skill of emp_023 is kafka, read from comment_001"
        in trail.text
    )
    assert f"<blockquote>{f.REMARK}</blockquote>" in trail.text
    assert "retained liability" in trail.text
    assert "The plan was approved automatically." in trail.text
    assert "Looking at the ticket." not in trail.text, "model prose is not report content"
    assert live.status_code == 200 and ">in progress<" in live.text
    assert rig.sessions.opened == rig.sessions.closed == 3


def test_a_closed_attempt_the_reader_cannot_fold_is_unavailable_and_logged() -> None:
    rig = Rig()
    with rig.client() as web:
        page = web.get("/replays/unfoldable")
        trail = web.get("/replays/unfoldable/trail")
    assert page.status_code == trail.status_code == 503
    assert "another-parser" not in page.text
    assert rig.sessions.opened == rig.sessions.closed == 2


def test_every_refusal_is_one_not_found_page_byte_for_byte() -> None:
    """An unknown name, an honest row of another world, the forged row and a name that is not
    a slug: the same 404 body, so a visitor learns neither that a name exists nor its world."""
    rig = Rig()
    with rig.client() as web:
        unknown = web.get(f"/replays/{UNKNOWN}")
        embargoed = web.get("/replays/embargoed")
        forged = web.get(f"/replays/{FORGED}")
        not_a_slug = web.get("/replays/Not%20A%20Slug")
    for response in (unknown, embargoed, forged, not_a_slug):
        assert response.status_code == 404
        assert response.content == unknown.content
    assert OTHER_WORLD not in unknown.text and "run-13" not in unknown.text
    assert rig.sessions.opened == rig.sessions.closed == 3, "a non-slug opens no session"


def test_the_cache_not_serving_the_version_is_unavailable_after_admission() -> None:
    rig = Rig()
    rig.store.versions = frozenset({WorldVersion("c" * 64)})
    with rig.client() as web:
        assert web.get("/replays").status_code == 503
        assert web.get("/replays/served").status_code == 503
        assert web.get(f"/replays/{FORGED}").status_code == 404, "eligibility first"
        assert web.get(f"/replays/{UNKNOWN}").status_code == 404
        assert web.get("/").status_code == 200
    rig.store.versions = frozenset({SERVED})
    with rig.client() as web:
        assert web.get("/replays/served").status_code == 200


def test_a_store_that_does_not_answer_or_is_not_bootstrapped_is_unavailable() -> None:
    rig = Rig()
    rig.store.reachable = False
    with rig.client() as web:
        for path in ("/replays", "/replays/served"):
            response = web.get(path)
            assert response.status_code == 503, path
            assert "OperationalError" not in response.text
        assert web.get(f"/replays/{UNKNOWN}").status_code == 404, "eligibility first"

    class Unbootstrapped(Rows):
        def rows_for(self, world_version: WorldVersion) -> tuple[()]:
            raise AppStoreInvariantBroken("the app schema is not bootstrapped")

        def row_of(self, public_id: object) -> None:
            raise AppStoreInvariantBroken("the app schema is not bootstrapped")

    rig = Rig()
    rig.rows = Unbootstrapped()
    with rig.client() as web:
        assert web.get("/replays").status_code == 503
        assert web.get("/replays/served").status_code == 503
    assert rig.sessions.opened == rig.sessions.closed == 1


def test_a_row_whose_scenario_disagrees_with_the_admission_is_not_found() -> None:
    rig = Rig()
    rig.rows = Rows(row("mislabelled", "run-12", SERVED, ScenarioId("scenario_999")))
    with rig.client() as web:
        assert web.get("/replays/mislabelled").status_code == 404


def test_every_registered_route_is_classified_and_every_scoped_one_refuses_the_forged_name() -> (
    None
):
    """The sweep: a route the table registers but ROUTES does not classify, by path and
    method, fails here, so a surface added later joins the sweep or is refused; each
    attempt-scoped path is walked by its method (a post with the decision form and no
    cookie) with the forged name and the unknown name and must answer the same not-found
    bytes."""
    rig = Rig()
    app = create_app(services(rig))
    registered = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }
    classified = {(route.path, method) for route in ROUTES for method in route.methods}
    assert registered == classified, registered ^ classified
    scoped = [route for route in ROUTES if route.surface is Surface.ATTEMPT_SCOPED]
    assert scoped, "the sweep walks at least the replay page"
    assert any(route.methods == {"POST"} for route in scoped), "the decision route is walked"
    with TestClient(app) as web:
        for route in scoped:
            for method in route.methods:
                data = DECISION_FORM if method == "POST" else None
                forged = web.request(method, route.path.format(public_id=FORGED), data=data)
                unknown = web.request(method, route.path.format(public_id=UNKNOWN), data=data)
                assert forged.status_code == unknown.status_code == 404, (route.path, method)
                assert forged.content == unknown.content, (route.path, method)
                if method == "GET":
                    served = web.get(route.path.format(public_id="served"))
                    assert served.status_code == 200, route.path


def test_a_live_flag_still_shows_on_the_index() -> None:
    rig = Rig()
    live = replace(services(rig), configuration=replace(CONFIGURATION, live_runs=True))
    with TestClient(create_app(live)) as web:
        assert ">on<" in web.get("/").text


# --- The results page -------------------------------------------------------------------


def test_the_results_page_states_the_labels_and_the_figures_in_their_rows() -> None:
    rig = Rig()
    with rig.client() as web:
        assert 'href="/results"' in web.get("/").text
        page = web.get("/results")
    assert page.status_code == 200
    text = page.text
    for label in results_view(codec.results()).labels:
        assert str(escape(label)) in text
    assert "24 of 30" in text and "14 of 30" in text and "+0.20 to +0.47" in text
    assert "no interval: every resample equal" in text
    assert "Unavailable: an arm of the pair was not built." in text
    assert "$2.2125" in text and "$0.0738 over 30 runs" in text
    assert "unavailable: no answer-quality checks (degraded condition)" in text
    assert "20 of 30 scenarios the rules-only reference did not pass" in text
    assert "where-the-single-call-stops.pdf" in text
    assert "structured 24 of 30 (0.63 to 0.90)" in text
    assert "<dt>src/leaveimpact/evaluator/cells.py</dt><dd>bound " + "0" * 40 in text


def test_every_page_the_surface_answers_carries_the_served_world_line() -> None:
    rig = Rig()
    line = str(escape(SERVED_WORLD_LABEL))
    pages = (
        "/",
        "/replays",
        "/results",
        "/replays/served",
        "/replays/served/trail",
        "/replays/served/timeline",
        "/replays/live",
        f"/replays/{UNKNOWN}",
    )
    with rig.client() as web:
        for path in pages:
            assert line in web.get(path).text, path
        rig.store.reachable = False
        unavailable = web.get("/replays")
    assert unavailable.status_code == 503 and line in unavailable.text


def test_the_results_are_decoded_once_at_creation_and_a_broken_file_fails_it() -> None:
    rig = Rig()
    calls = 0

    def counted() -> PublicResults:
        nonlocal calls
        calls += 1
        return codec.results()

    app = create_app(services(rig, counted))
    assert calls == 1
    with TestClient(app) as web:
        for _ in range(3):
            assert web.get("/results").status_code == 200
    assert calls == 1

    def broken() -> PublicResults:
        raise ValueError("the public results.plan.seed is an integer, got str")

    with pytest.raises(ValueError, match="plan.seed"):
        create_app(services(rig, broken))


def section(text: str, heading: str) -> str:
    """The comparison section under the ``h3`` that reads ``heading``, to its end."""
    start = text.index(f"<h3>{heading}</h3>")
    return text[start : text.index("</section>", start)]


def test_the_committed_results_render_the_base_loss_and_the_padded_gain_in_their_rows() -> None:
    """The real producer through the real template: each headline figure sits in the section
    whose heading names its pair and level, so a figure cannot land under another label."""
    rig = Rig()
    with TestClient(create_app(services(rig, committed_results))) as web:
        text = web.get("/results").text
    base = section(text, "Descriptive: the investigator against full context, base")
    assert "<td>24 of 30</td>" in base and "<td>30 of 30</td>" in base
    assert "-0.30 to -0.10" in base
    padded = section(text, "Primary: the investigator against full context, padded")
    assert "<td>24 of 30</td>" in padded and "<td>14 of 30</td>" in padded
    assert "+0.20 to +0.47" in padded
    assert "both 14 · first only 10 · second only 0 · neither 6" in padded
    assert "$9.9594 over 240 runs" in text
    assert text.count("<tr>") >= 8 + 6 + 4


INTRODUCED = (
    Walkthrough(
        PublicId("served"),
        "structured",
        "Read the one action and the assessments beneath it.",
        "Every row agrees with the answer key; nothing here reads a document.",
    ),
)


def test_the_listing_introduces_a_titled_row_the_file_names_before_the_full_list() -> None:
    rig = Rig()
    with rig.client(INTRODUCED) as web:
        page = web.get("/replays")
    assert page.status_code == 200
    text = page.text
    start, everything = text.index("Start here"), text.index("All replays")
    assert start < everything < text.index('<ul class="replays">')
    assert "Read the one action and the assessments beneath it." in text
    assert text.count('href="/replays/served"') == 2, "introduced once, listed once"
    assert "structured" in text and "scenario_003" in text
    with rig.client() as web:
        plain = web.get("/replays").text
    assert "Start here" not in plain and "All replays" not in plain
    assert 'href="/replays/served"' in plain


def test_the_report_carries_its_walkthrough_above_the_ending_only_for_a_named_titled_row() -> None:
    rig = Rig()
    with rig.client(INTRODUCED) as web:
        page = web.get("/replays/served")
        other = web.get("/replays/reported")
    text = page.text
    assert "Walkthrough" in text
    assert text.index("Every row agrees with the answer key") < text.index("The run completed.")
    assert "Walkthrough" not in other.text, "a titled row the file does not name renders alone"
    with rig.client() as web:
        plain = web.get("/replays/served").text
    assert "Walkthrough" not in plain
