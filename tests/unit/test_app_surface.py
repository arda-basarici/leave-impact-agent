"""The surface over in-memory doubles: the listing as the served world's projection; the replay
page admitted for a row the admission agrees with, with no run id on it; one byte-identical
not-found page for an unknown name, an honest row of another world, a forged row carrying the
served world for another world's attempt, and a name that is not a slug; the unavailable page
when the cache does not serve the version or a store does not answer, after admission so an
unavailable cache never tells a published name from an unknown one; the log session closed on
every path; and the sweep: every registered route classified, every attempt-scoped route
walked with the forged name and the unknown name to the same bytes."""

from __future__ import annotations

from dataclasses import replace

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.main import ROUTES, Services, Surface, create_app
from leaveimpact.app.store import AppStoreInvariantBroken, AppStoreUnavailable
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.ports.errors import Source, SourceUnreachable
from tests.unit import log_histories as histories
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
    """Log sessions over one in-memory log, each closing recorded."""

    def __init__(self, memory: MemoryLog) -> None:
        self.memory = memory
        self.opened = 0
        self.closed = 0

    def __call__(self) -> Sessions:
        self.opened += 1
        return self

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        return self.memory.load(run_id, attempt, rules=rules)

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


class Rig:
    """The whole application over the doubles: a closed run of the served world (``run-12``),
    a closed run of another world (``run-13``), an open run of the served world (``run-14``);
    rows for the first (``served``), an honest row for the second (``embargoed``), a forged row
    carrying the served world for a third run of the other world (``forged``, since one
    attempt has one row) and a row for the open one
    (``live``)."""

    def __init__(self) -> None:
        memory = MemoryLog()
        memory.seed(history_in_world(CLOSED, SERVED))
        memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-13"))
        memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-15"))
        memory.seed(admission_only(SERVED, run_id="run-14"))
        self.sessions = Sessions(memory)
        self.store = Store()
        self.rows = Rows(
            row("served", "run-12", SERVED, title="The handover nobody wrote down"),
            row("embargoed", "run-13", OTHER_WORLD),
            row(FORGED, "run-15", SERVED),
            row("live", "run-14", SERVED),
        )

    def client(self) -> TestClient:
        services = Services(
            CODE,
            CONFIGURATION,
            self.store.ready_versions,
            self.store.app_schema,
            self.rows,
            self.sessions,
            histories.RULES,
        )
        return TestClient(create_app(services))


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
    assert rig.sessions.opened == 2 and rig.sessions.closed == 2


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
    """The sweep: a route the table registers but ROUTES does not classify fails here, so a
    surface added later joins the sweep or is refused; each attempt-scoped path is walked with
    the forged name and the unknown name and must answer the same not-found bytes."""
    rig = Rig()
    app = create_app(
        Services(
            CODE,
            CONFIGURATION,
            rig.store.ready_versions,
            rig.store.app_schema,
            rig.rows,
            rig.sessions,
            histories.RULES,
        )
    )
    registered = {route.path for route in app.routes if isinstance(route, APIRoute)}
    classified = {route.path for route in ROUTES}
    assert registered == classified, registered ^ classified
    scoped = [route for route in ROUTES if route.surface is Surface.ATTEMPT_SCOPED]
    assert scoped, "the sweep walks at least the replay page"
    with TestClient(app) as web:
        for route in scoped:
            forged = web.get(route.path.format(public_id=FORGED))
            unknown = web.get(route.path.format(public_id=UNKNOWN))
            assert forged.status_code == unknown.status_code == 404, route.path
            assert forged.content == unknown.content, route.path
            served = web.get(route.path.format(public_id="served"))
            assert served.status_code == 200, route.path


def test_a_live_flag_still_shows_on_the_index() -> None:
    rig = Rig()
    live = replace(CONFIGURATION, live_runs=True)
    services = Services(
        CODE,
        live,
        rig.store.ready_versions,
        rig.store.app_schema,
        rig.rows,
        rig.sessions,
        histories.RULES,
    )
    with TestClient(create_app(services)) as web:
        assert ">on<" in web.get("/").text
