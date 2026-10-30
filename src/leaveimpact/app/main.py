"""The application: the routes, the templates and the composition root that binds them to
the deployed database, the committed configuration and the registration the image ships.

``create_app`` takes the services as plain values and callables, so a test builds the whole
application over an in-memory log, an in-memory table and a scripted readiness read, never a
database; ``app_from_env`` is the composition root the serving command calls, reading the
database URL, the code version the image was built with and the registration file, whose
digest must be the configuration's before the service starts (``read_model.rules_under``).
Routes that read the store are plain ``def`` routes, which Starlette runs on its thread pool
(the entry's HTTP-shell ruling: store access synchronous and deliberate, nothing held open
while a browser waits); a request that reads the log opens a log session of its own under
the app's bounds and closes it before answering, since the log store keeps its connection
and one shared across the pool's threads would be shared by concurrent requests. The API
explorers FastAPI serves by default are off: the surface is pages a stranger reads, and the
one endpoint that will take visitor input is a form, not an API.

**Every route is classified**, public-global or attempt-scoped, in ``ROUTES`` beside its
handler, and the acceptance sweep refuses an application whose route table holds a path the
classification does not: a surface added at a later step joins the sweep by construction or
fails it. An attempt-scoped route answers through the read model's one admission, and what
it answers when admission fails is fixed here once. ``None`` is the generic not-found page,
byte-identical for an unknown name, a name the predicate refuses and a name the log
contradicts, so a forced row reveals nothing; a store that does not answer, a database
without the app schema, and a served world the cache does not mark ready are the
unavailable page, 503, answered after admission is resolved, so an unavailable cache never
distinguishes a published name from an unknown one. The replay page branches on the
admitted state: an open attempt (a live run investigating or awaiting its decision) is the
progress header, and a closed one is the report, the export folded from the state by the
log reader and rendered as the report view (``report``); a closed attempt the reader
refuses to fold is a defect of the deployment, logged by name and answered as the
unavailable page, never the not-found page, which would say the name does not exist. The
trail page (``trail``) is the same path with the trail view built instead of the report's.
The narration stream (``events``) makes the same admission in a session closed before the
response starts, then refuses beyond the subscription bound and on a rejected cursor, and
streams the attempt's lines over a session per tick (``stream``). The results page
(``results``) renders the committed public results of the investigator milestone's
measurement, decoded once when the application is created, since the file ships in the
image and cannot change under a running process: a file the package cannot decode fails
the creation, which the deploy's readiness check reports, rather than the first visitor's
request. The served-world label every page carries is the results view's constant, a
global of the template environment rendered by the base template, so no page can omit it.

Statement bounds, per request: the listing makes one app-store operation (the version check
and one statement) and one cache read; the replay page one app-store operation, the log's
reads of one attempt on one connection, and one cache read; the stream the replay page's
reads at subscription, one log load of the attempt at its first tick and one read of the
events past its position per tick after; each under the store's three-second connect and
three-second statement bounds.

**The two routes that take a visitor's input** (the live-path commands step, fork 7) are
forms: the start from the index, carrying the key the index minted into it and a scenario
id, and the decision from an open attempt's replay page, carrying the decision and the
digest of the review payload the page showed, the key coming back as the cookie the start
set (``Path`` the attempt's replay path, ``HttpOnly``, ``Secure``, ``SameSite=Strict``,
fork 3). Both routes are ``async`` and read their urlencoded body themselves, since the
service carries no multipart parser for a form this small, from the request's stream
under a byte bound and with the parser's field bound (``form_of``: the group's external
read posted eight mebibytes of empty fields under the flag off and the process's peak
working set rose from 118 to 502 MiB against the container's 384; a body past the bound
is 413 and a form with more fields than the page's is 400, before any rule and before
any store is opened), then run the command on the
thread pool as the plain routes run, in a log session of their own. A start answers a
redirect to the replay page with the cookie on every ``Started``, a repeat included, so a
lost response is survivable; a decision answers the same redirect. A refusal renders by
its kind with the wording fixed here (``_START_WORDING``, ``_DECIDE_WORDING``): the busy
and the per-address refusals share one sentence (fork 8), the world not served is the
unavailable page, and an attempt no visitor started is the not-found page, byte-identical
to an unknown name's, so the sweep's invariant holds on the decision route too. A form
that is not the page's (a key outside the rule, no scenario, no decision, no digest) is
400 before any rule runs. The sweep's classification carries each route's method, so the
attempt-scoped decision route is walked with a post. The per-address window the start
consults is the process's memory (``window``); the address is the request's client as
Uvicorn's proxy-headers middleware rewrites it for a connection from the proxy's subnet
(``FORWARDED_ALLOW_IPS``, set by compose from the platform contract's row).

Templates live beside this module and are packaged with it, read by package name like the
committed configuration. Autoescape is on for them through Jinja2's extension selection,
which the test holds by rendering the real page with a string carrying markup: the world's
prose is model-written and the surface must render it as text. An undefined name in a
template is an error, never empty text, so a template that names a view field wrongly
fails its test instead of dropping a section from the page.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from leaveimpact.adapters.corpus import served_versions
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStore, LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.decide import (
    DecideComposition,
    DecideLog,
    DecideOutcome,
    DecideRefusalKind,
    DecideRefused,
    DecideRequest,
    DecisionRows,
    decide,
    review_of,
)
from leaveimpact.app.live import Decision, StartKey, mint_start_key, start_key_of
from leaveimpact.app.markup import mark_quotes
from leaveimpact.app.narration import timeline_view
from leaveimpact.app.public import PublicReplay, public_id_of
from leaveimpact.app.read_model import (
    Admitted,
    LogSession,
    PublishableReads,
    admitted,
    instants_of,
    listing,
    replay_view,
    rules_under,
)
from leaveimpact.app.ready import AppSchema, ReadyVersions, readiness
from leaveimpact.app.report import Instants, report_view
from leaveimpact.app.results import SERVED_WORLD_LABEL, results_view
from leaveimpact.app.start import (
    Planning,
    StartComposition,
    StartLog,
    StartOutcome,
    StartRefusalKind,
    StartRefused,
    StartRequest,
    StartSections,
    start,
)
from leaveimpact.app.store import (
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
    connect_bounded,
)
from leaveimpact.app.stream import (
    DEFAULT_PACING,
    MEDIA_TYPE,
    Pacing,
    RejectedCursor,
    Subscriptions,
    cursor_of,
    frames,
)
from leaveimpact.app.trail import trail_view
from leaveimpact.app.walkthroughs import (
    Walkthrough,
    committed_walkthroughs,
    listing_view,
    walkthrough_for,
)
from leaveimpact.app.window import AddressWindow, MemoryWindow
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.run_export import RunExport
from leaveimpact.results.committed import committed_results
from leaveimpact.results.public import PublicResults

_log = logging.getLogger(__name__)

CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"
DATABASE = "DATABASE_URL"
REGISTRATION_FILE = "LEAVEIMPACT_REGISTRATION_FILE"
"""The registration the image ships, set by the Dockerfile; the surface folds every attempt
under its rules after checking its digest is the committed configuration's."""
TEMPLATES = files("leaveimpact.app").joinpath("templates")
COOKIE = "start_key"
"""The cookie a start sets with the key, scoped to the attempt's replay path, which the
decision route reads back (fork 3 of the live-path commands step)."""
COOKIE_MAX_AGE_SECONDS = 24 * 60 * 60
"""Longer than any wait and wall the configuration bounds; a repeat of the start renews it."""
FORM_BYTES_BOUND = 1024
"""What a posted form may be, read from the stream and never buffered past it: the start's
key and scenario id or the decision's digest and button are under a hundred bytes each, and
an unbounded read let one post make the process hold the whole body (the group's external
read, finding 1)."""
FORM_FIELDS_BOUND = 8
"""More fields than either form carries; the parser refuses past it before a dictionary is
built."""
GET = frozenset({"GET"})
POST = frozenset({"POST"})

# What a page cannot answer from: the two stores not answering or not bootstrapped, and the
# cache's readiness read failing. Each is the unavailable page; none is a visitor's error.
_UNAVAILABLE = (
    AppStoreUnavailable,
    AppStoreInvariantBroken,
    LogStoreUnavailable,
    LogStoreInvariantBroken,
    SourceUnreachable,
)


Build = Callable[[PublicReplay, RunExport, Instants], object]
"""A page's view built from the public header, the folded export and the log's instants."""


class Surface(Enum):
    """How a route is swept: the same for every visitor, or naming an attempt and answering
    through the admission."""

    PUBLIC_GLOBAL = "public-global"
    ATTEMPT_SCOPED = "attempt-scoped"


@dataclass(frozen=True, slots=True)
class RouteClass:
    """One route's path and methods as FastAPI registers them and its classification."""

    path: str
    surface: Surface
    methods: frozenset[str]


ROUTES: tuple[RouteClass, ...] = (
    RouteClass("/", Surface.PUBLIC_GLOBAL, GET),
    RouteClass("/ready", Surface.PUBLIC_GLOBAL, GET),
    RouteClass("/replays", Surface.PUBLIC_GLOBAL, GET),
    RouteClass("/results", Surface.PUBLIC_GLOBAL, GET),
    RouteClass("/replays/{public_id}", Surface.ATTEMPT_SCOPED, GET),
    RouteClass("/replays/{public_id}/trail", Surface.ATTEMPT_SCOPED, GET),
    RouteClass("/replays/{public_id}/timeline", Surface.ATTEMPT_SCOPED, GET),
    RouteClass("/replays/{public_id}/events", Surface.ATTEMPT_SCOPED, GET),
    RouteClass("/start", Surface.PUBLIC_GLOBAL, POST),
    RouteClass("/replays/{public_id}/decision", Surface.ATTEMPT_SCOPED, POST),
)
"""Every route the application registers, classified with its methods; the acceptance
sweep compares this with the route table and walks each attempt-scoped path, by its
method, with a name the predicate refuses."""

_START_WORDING: dict[StartRefusalKind, tuple[int, str]] = {
    StartRefusalKind.LIVE_RUNS_OFF: (403, "Live runs are off; the replays are open to read."),
    StartRefusalKind.UNKNOWN_SCENARIO: (400, "The served world has no scenario by that name."),
    StartRefusalKind.BUDGET_SPENT: (
        429,
        "Today's budget of live runs is spent; it opens again at midnight UTC.",
    ),
    StartRefusalKind.BUSY: (
        409,
        "A run is in progress; follow it from the replays, and start one when it ends.",
    ),
    StartRefusalKind.ADDRESS_SPENT: (
        409,
        "A run is in progress; follow it from the replays, and start one when it ends.",
    ),
    StartRefusalKind.RESERVATION_REFUSED: (
        409,
        "The demo's ledger could not reserve for a run; the replays are open to read.",
    ),
}
"""The status and the sentence a refused start renders by its kind; the world not served
is the unavailable page and is not here."""
_DECIDE_WORDING: dict[DecideRefusalKind, tuple[int, str]] = {
    DecideRefusalKind.CAPABILITY: (
        403,
        "This browser does not hold the key the run was started with; a decision comes "
        "from the browser that started it.",
    ),
    DecideRefusalKind.NO_REQUEST: (409, "The run has not asked for a decision yet."),
    DecideRefusalKind.LATE: (
        409,
        "The wait for a decision has ended; the run is closed without one.",
    ),
    DecideRefusalKind.LOG_REFUSED: (409, "The run's log refused the decision: {detail}."),
}
"""The status and the sentence a refused decision renders by its kind; an attempt no
visitor started is the not-found page and is not here."""
_DECISIONS = {"approve": Decision.APPROVED, "decline": Decision.DECLINED}
"""The decision form's two button values."""


class FormRefused(Exception):
    """A posted body neither form produces: past the byte bound (413) or with more fields
    than the parser's bound (400); the status and the sentence the route renders."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


class LiveLog(StartLog, DecideLog, Protocol):
    """The log session the two live routes open per request: the start's and the
    decision's operations on one connection, closed before the response."""

    def close(self) -> None: ...


class LiveRows(StartSections, DecisionRows, Protocol):
    """The app store as the two live commands write and read it."""


@dataclass(frozen=True, slots=True)
class Services:
    """What the routes need, bound once at the composition root; ``results`` reads the
    public results the page renders and ``walkthroughs`` the introduced replays' prose, each
    called once at the application's creation."""

    code_version: str
    configuration: DemoConfiguration
    ready_versions: ReadyVersions
    app_schema: AppSchema
    rows: PublishableReads
    log_sessions: Callable[[], LogSession]
    rules: Rules
    results: Callable[[], PublicResults]
    walkthroughs: Callable[[], tuple[Walkthrough, ...]]
    planning: Planning
    """The served world's scenario ids and the planner, from the root above the shells."""
    live: LiveRows
    live_logs: Callable[[], LiveLog]
    window: AddressWindow
    mint_key: Callable[[], StartKey]
    """The index's key for its start form; the composition root mints from entropy."""


def templating() -> Jinja2Templates:
    """The template environment every page renders through: the packaged templates, the
    quote-marking filter, and an undefined name refused rather than rendered as nothing, so
    a mistyped attribute fails a test instead of hiding a section (the renderer lesson of the
    report step). The served-world label is a global of the environment, not a key a page
    passes, so every template under the base, rendered by a route or by a test, carries it."""
    templates = Jinja2Templates(directory=str(TEMPLATES))
    templates.env.undefined = StrictUndefined
    # Jinja types its filter and global tables by its built-in entries; a filter or a global
    # of our own is registered through the table's untyped face.
    filters = cast(dict[str, Any], templates.env.filters)
    filters["mark_quotes"] = mark_quotes
    globals_table = cast(dict[str, Any], templates.env.globals)
    globals_table["served_world_label"] = SERVED_WORLD_LABEL
    return templates


def create_app(services: Services, pacing: Pacing = DEFAULT_PACING) -> FastAPI:
    """The application over ``services``: the index, the readiness route, the listing of
    published replays with the introduced ones first, the results page over the public
    results read once here, the replay, report, trail and timeline pages, the report carrying
    its walkthrough when the file names the row, and the narration stream paced by ``pacing``
    (the module's constants unless a test passes faster ones); the process's subscription
    bound is reachable as ``app.state.subscriptions``. Raises what ``services.results`` and
    ``services.walkthroughs`` raise, so an undecodable committed file is a creation failure."""
    app = FastAPI(title="Leave Impact Agent", docs_url=None, redoc_url=None, openapi_url=None)
    templates = templating()
    configuration = services.configuration
    subscriptions = Subscriptions(pacing.bound)
    app.state.subscriptions = subscriptions
    measurement = results_view(services.results())
    walkthroughs = services.walkthroughs()
    planning = services.planning
    start_composition = StartComposition(
        configuration,
        services.rules,
        planning.scenarios,
        planning.plan,
        lambda: cache_serves(),
        services.window,
    )
    decide_composition = DecideComposition(configuration, services.rules)
    common: dict[str, Any] = {
        "code_version": services.code_version,
        "served_world_version": configuration.served_world_version,
        "live_runs": configuration.live_runs,
    }

    def page(request: Request, name: str, status: int = 200, **context: Any) -> HTMLResponse:
        return templates.TemplateResponse(request, name, {**common, **context}, status_code=status)

    def not_found(request: Request) -> HTMLResponse:
        # One body for every refusal, so two names a visitor tries read the same.
        return page(request, "not_found.html", 404)

    def unavailable(request: Request) -> HTMLResponse:
        return page(request, "unavailable.html", 503)

    def cache_serves() -> bool:
        return configuration.served_world_version in services.ready_versions()

    def refused(request: Request, status: int, reason: str) -> HTMLResponse:
        return page(request, "refused.html", status, reason=reason)

    def index(request: Request) -> HTMLResponse:
        # A key is minted only for a form the page renders: under the flag off there is
        # none, and the template reads the name only inside that branch.
        context: dict[str, Any] = {"scenarios": sorted(planning.scenarios)}
        if configuration.live_runs:
            context["start_key"] = services.mint_key()
        return page(request, "index.html", **context)

    def ready() -> JSONResponse:
        read = readiness(
            services.code_version, configuration, services.ready_versions, services.app_schema
        )
        return JSONResponse(read.as_json(), status_code=200 if read.ready else 503)

    def replays(request: Request) -> HTMLResponse:
        try:
            entries = listing(services.rows, configuration)
            if not cache_serves():
                return unavailable(request)
        except _UNAVAILABLE:
            return unavailable(request)
        return page(request, "replays.html", view=listing_view(entries, walkthroughs))

    def results(request: Request) -> HTMLResponse:
        return page(request, "results.html", view=measurement)

    def admit(request: Request, public_id: str) -> Admitted | HTMLResponse:
        """Every attempt-scoped surface's one path: the name parsed, the admission in a log
        session closed before anything is answered, then the cache's readiness; a refusal
        is the page it answers (not found before unavailable, so an unavailable cache
        never tells a published name from an unknown one)."""
        try:
            name = public_id_of(public_id)
        except ValueError:
            return not_found(request)
        session = services.log_sessions()
        try:
            admission = admitted(name, services.rows, session, configuration, services.rules)
        except _UNAVAILABLE:
            return unavailable(request)
        finally:
            session.close()
        if admission is None:
            return not_found(request)
        try:
            if not cache_serves():
                return unavailable(request)
        except _UNAVAILABLE:
            return unavailable(request)
        return admission

    def attempt_page(request: Request, public_id: str, template: str, build: Build) -> HTMLResponse:
        """The report and the trail share one path: the admission, the open-attempt header,
        the fold, and ``build`` of the page's view from the export."""
        admission = admit(request, public_id)
        if isinstance(admission, HTMLResponse):
            return admission
        header = replay_view(admission)
        state = admission.state
        if state.closed is None:
            return page(request, "replay.html", replay=header, review=review_of(state))
        try:
            export = export_of(state)
        except ValueError as error:
            _log.warning(
                "publishable row %r names a closed attempt the reader cannot fold: %s",
                admission.row.public_id,
                error,
            )
            return unavailable(request)
        view = build(header, export, instants_of(state))
        walkthrough = walkthrough_for(walkthroughs, header.public_id, header.title)
        return page(request, template, replay=header, view=view, walkthrough=walkthrough)

    def replay(request: Request, public_id: str) -> HTMLResponse:
        return attempt_page(request, public_id, "report.html", report_view)

    def trail(request: Request, public_id: str) -> HTMLResponse:
        return attempt_page(request, public_id, "trail.html", trail_view)

    def timeline(request: Request, public_id: str) -> HTMLResponse:
        """The timeline: the narration over the admitted state, open or closed; an open
        attempt's page follows the stream from its last rendered position."""
        admission = admit(request, public_id)
        if isinstance(admission, HTMLResponse):
            return admission
        view = timeline_view(admission.state, services.rules)
        return page(request, "timeline.html", replay=replay_view(admission), view=view)

    def events(request: Request, public_id: str, after: str | None = None) -> Response:
        """The narration stream: the admission as the pages make it; then the cursor and
        the subscription bound, in that order; then the frames over a session per tick.
        ``after`` is read as text, since a typed parameter would be refused before the
        admission."""
        admission = admit(request, public_id)
        if isinstance(admission, HTMLResponse):
            return admission
        state = admission.state
        inputs = state.inputs
        assert inputs is not None, "an admitted attempt holds its admission"
        cursor = cursor_of(after, request.headers.get("last-event-id"), state.last_position)
        if isinstance(cursor, RejectedCursor):
            return PlainTextResponse(cursor.reason, status_code=400)
        closed = state.closed
        if closed is not None and cursor.position >= closed.position:
            return Response(status_code=204)
        # The slot is acquired last, once nothing else can refuse, and held by the route
        # only until the response owns it: a fault in between gives it back (the external
        # read of the step's commits, first finding).
        slot = subscriptions.try_acquire()
        if slot is None:
            return unavailable(request)
        try:
            body = frames(
                services.log_sessions,
                inputs.run_id,
                inputs.attempt,
                services.rules,
                cursor=cursor.position,
                pacing=pacing,
                slot=slot,
            )
            return StreamingResponse(
                body,
                media_type=MEDIA_TYPE,
                headers={"Cache-Control": "no-store"},
                background=BackgroundTask(slot.release),
            )
        except BaseException:
            slot.release()
            raise

    def run_start(asked: StartRequest) -> StartOutcome:
        log = services.live_logs()
        try:
            return start(asked, log, services.live, start_composition)
        finally:
            log.close()

    async def start_run(request: Request) -> Response:
        """The start: the form read under its bounds, the key and the scenario checked for
        shape, the command on the thread pool, the redirect with the cookie or the refusal
        by kind."""
        try:
            form = await form_of(request)
        except FormRefused as error:
            return refused(request, error.status, error.reason)
        try:
            key = start_key_of(form.get("key", ""))
        except ValueError:
            return refused(request, 400, "The form is not the index's: its key is not one.")
        scenario = form.get("scenario_id", "").strip()
        if not scenario:
            return refused(request, 400, "The form names no scenario.")
        asked = StartRequest(key, ScenarioId(scenario), address_of(request))
        try:
            outcome = await run_in_threadpool(run_start, asked)
        except _UNAVAILABLE:
            return unavailable(request)
        if isinstance(outcome, StartRefused):
            if outcome.kind is StartRefusalKind.WORLD_NOT_SERVED:
                return unavailable(request)
            status, wording = _START_WORDING[outcome.kind]
            return refused(request, status, wording)
        location = f"/replays/{outcome.row.public_id}"
        response = RedirectResponse(location, status_code=303)
        response.set_cookie(
            COOKIE,
            key,
            max_age=COOKIE_MAX_AGE_SECONDS,
            path=location,
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return response

    def run_decision(asked: DecideRequest) -> DecideOutcome:
        log = services.live_logs()
        try:
            return decide(asked, log, services.live, decide_composition)
        finally:
            log.close()

    async def decide_run(request: Request, public_id: str) -> Response:
        """The decision: the name parsed, the form read, the key from the cookie (none is
        a key of ``None``, refused after the row as the capability), the command on the
        thread pool, the redirect or the refusal by kind."""
        try:
            name = public_id_of(public_id)
        except ValueError:
            return not_found(request)
        try:
            form = await form_of(request)
        except FormRefused as error:
            return refused(request, error.status, error.reason)
        decision = _DECISIONS.get(form.get("decision", ""))
        if decision is None:
            return refused(request, 400, "The form names no decision.")
        try:
            asked = DecideRequest(name, key_in(request), decision, form.get("payload_digest", ""))
        except ValueError:
            return refused(request, 400, "The form carries no review digest.")
        try:
            outcome = await run_in_threadpool(run_decision, asked)
        except _UNAVAILABLE:
            return unavailable(request)
        if isinstance(outcome, DecideRefused):
            if outcome.kind is DecideRefusalKind.NOT_LIVE:
                return not_found(request)
            status, wording = _DECIDE_WORDING[outcome.kind]
            return refused(request, status, wording.format(detail=outcome.detail))
        return RedirectResponse(f"/replays/{name}", status_code=303)

    # Registered by call rather than by decorator so the handlers are plain closures over
    # the services, named and typed where they are read; the paths are ROUTES' strings so
    # the table and the registration cannot drift.
    (
        index_path,
        ready_path,
        replays_path,
        results_path,
        replay_path,
        trail_path,
        timeline_path,
        events_path,
        start_path,
        decision_path,
    ) = (route.path for route in ROUTES)
    app.add_api_route(index_path, index, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(ready_path, ready, methods=["GET"])
    app.add_api_route(replays_path, replays, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(results_path, results, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(replay_path, replay, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(trail_path, trail, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(timeline_path, timeline, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(events_path, events, methods=["GET"])
    app.add_api_route(start_path, start_run, methods=["POST"])
    app.add_api_route(decision_path, decide_run, methods=["POST"])
    return app


async def form_of(request: Request) -> dict[str, str]:
    """The urlencoded form a browser posts, the last value per name, read from the stream
    under ``FORM_BYTES_BOUND`` and parsed under ``FORM_FIELDS_BOUND``; the two forms are read
    here since the service carries no multipart parser. ``FormRefused`` past either bound:
    a declared length past the byte bound refuses before a byte is read, and the stream is
    bounded as it arrives whatever the headers declare, so a chunked body without a length
    is held to the same bound."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > FORM_BYTES_BOUND:
        raise FormRefused(413, TOO_LARGE)
    received = bytearray()
    async for chunk in request.stream():
        received += chunk
        if len(received) > FORM_BYTES_BOUND:
            raise FormRefused(413, TOO_LARGE)
    try:
        pairs = parse_qsl(
            received.decode("utf-8", errors="replace"),
            keep_blank_values=True,
            max_num_fields=FORM_FIELDS_BOUND,
        )
    except ValueError:
        raise FormRefused(400, "The form carries more fields than any this page posts.") from None
    return dict(pairs)


TOO_LARGE = "The form is larger than any this page posts."


def address_of(request: Request) -> str:
    """The client address the per-address window counts: the connection's peer as the
    proxy-headers middleware rewrote it, or ``unknown`` for a request with no client (a
    test client)."""
    client = request.client
    return client.host if client is not None else "unknown"


def key_in(request: Request) -> StartKey | None:
    """The key the cookie carries, or ``None`` when there is none or it is not a key."""
    value = request.cookies.get(COOKIE)
    if value is None:
        return None
    try:
        return start_key_of(value)
    except ValueError:
        return None


def services_from_env(
    env: Mapping[str, str] | None, planning: Callable[[DemoConfiguration], Planning]
) -> Services:
    """The composition root's reading of the environment: the code version the image was
    built with, the database the deploy composed and the registration the image ships;
    ``ValueError`` names the one missing, or a registration whose digest is not the
    configuration's. ``planning`` is the root above the shells building the served world's
    planning for the configuration, called after this module's own checks and raising what
    it raises."""
    environment = os.environ if env is None else env
    code_version = environment.get(CODE_VERSION, "").strip()
    if not code_version:
        raise ValueError(f"{CODE_VERSION} unset — image built without provenance")
    dsn = environment.get(DATABASE, "").strip()
    if not dsn:
        raise ValueError(f"{DATABASE} is not set and the application needs it")
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        raise ValueError(f"{REGISTRATION_FILE} is not set and the application folds runs under it")
    configuration = committed_configuration()
    try:
        registration = Path(registration_file).read_bytes()
    except OSError as error:
        raise ValueError(f"{REGISTRATION_FILE} names {registration_file!r}: {error}") from error
    store = AppStore(dsn=dsn)
    rules = rules_under(configuration, registration)

    def log_session() -> LogStore:
        return LogStore(dsn=dsn, connect=connect_bounded)

    return Services(
        code_version=code_version,
        configuration=configuration,
        ready_versions=lambda: served_versions(dsn),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=log_session,
        rules=rules,
        results=committed_results,
        walkthroughs=committed_walkthroughs,
        planning=planning(configuration),
        live=store,
        live_logs=log_session,
        window=MemoryWindow(),
        mint_key=mint_start_key,
    )


def app_from_env(
    env: Mapping[str, str] | None, planning: Callable[[DemoConfiguration], Planning]
) -> FastAPI:
    return create_app(services_from_env(env, planning))
