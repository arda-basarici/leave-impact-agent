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
reads at subscription and then one log load of the attempt per tick; each under the store's
three-second connect and three-second statement bounds.

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
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined
from starlette.background import BackgroundTask

from leaveimpact.adapters.corpus import served_versions
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStore, LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration, committed_configuration
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
    """One route's path as FastAPI registers it and its classification."""

    path: str
    surface: Surface


ROUTES: tuple[RouteClass, ...] = (
    RouteClass("/", Surface.PUBLIC_GLOBAL),
    RouteClass("/ready", Surface.PUBLIC_GLOBAL),
    RouteClass("/replays", Surface.PUBLIC_GLOBAL),
    RouteClass("/results", Surface.PUBLIC_GLOBAL),
    RouteClass("/replays/{public_id}", Surface.ATTEMPT_SCOPED),
    RouteClass("/replays/{public_id}/trail", Surface.ATTEMPT_SCOPED),
    RouteClass("/replays/{public_id}/timeline", Surface.ATTEMPT_SCOPED),
    RouteClass("/replays/{public_id}/events", Surface.ATTEMPT_SCOPED),
)
"""Every route the application registers, classified; the acceptance sweep compares this
with the route table and walks each attempt-scoped path with a name the predicate refuses."""


@dataclass(frozen=True, slots=True)
class Services:
    """What the routes need, bound once at the composition root; ``results`` reads the
    public results the page renders, called once at the application's creation."""

    code_version: str
    configuration: DemoConfiguration
    ready_versions: ReadyVersions
    app_schema: AppSchema
    rows: PublishableReads
    log_sessions: Callable[[], LogSession]
    rules: Rules
    results: Callable[[], PublicResults]


def templating() -> Jinja2Templates:
    """The template environment every page renders through: the packaged templates, the
    quote-marking filter, and an undefined name refused rather than rendered as nothing, so
    a mistyped attribute fails a test instead of hiding a section (the renderer lesson of the
    report step). The served-world label is a global of the environment, not a key a page
    passes, so every template under the base, rendered by a route or by a test, carries it."""
    templates = Jinja2Templates(directory=str(TEMPLATES))
    templates.env.undefined = StrictUndefined
    templates.env.globals["served_world_label"] = SERVED_WORLD_LABEL
    # Jinja types its filter table by its built-in filters' signatures; a filter of our own
    # is registered through the table's untyped face.
    filters = cast(dict[str, Any], templates.env.filters)
    filters["mark_quotes"] = mark_quotes
    return templates


def create_app(services: Services, pacing: Pacing = DEFAULT_PACING) -> FastAPI:
    """The application over ``services``: the index, the readiness route, the listing of
    published replays, the results page over the public results read once here, the replay,
    report, trail and timeline pages, and the narration stream paced by ``pacing`` (the
    module's constants unless a test passes faster ones); the process's subscription bound
    is reachable as ``app.state.subscriptions``. Raises what ``services.results`` raises, so
    an undecodable results file is a creation failure."""
    app = FastAPI(title="Leave Impact Agent", docs_url=None, redoc_url=None, openapi_url=None)
    templates = templating()
    configuration = services.configuration
    subscriptions = Subscriptions(pacing.bound)
    app.state.subscriptions = subscriptions
    measurement = results_view(services.results())
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

    def index(request: Request) -> HTMLResponse:
        return page(request, "index.html")

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
        return page(request, "replays.html", entries=entries)

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
            return page(request, "replay.html", replay=header)
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
        return page(request, template, replay=header, view=view)

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
        run_id, attempt = inputs.run_id, inputs.attempt

        def read() -> AttemptState:
            tick = services.log_sessions()
            try:
                return tick.load(run_id, attempt, rules=services.rules)
            finally:
                tick.close()

        try:
            body = frames(read, services.rules, cursor=cursor.position, pacing=pacing, slot=slot)
            return StreamingResponse(
                body,
                media_type=MEDIA_TYPE,
                headers={"Cache-Control": "no-store"},
                background=BackgroundTask(slot.release),
            )
        except BaseException:
            slot.release()
            raise

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
    ) = (route.path for route in ROUTES)
    app.add_api_route(index_path, index, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(ready_path, ready, methods=["GET"])
    app.add_api_route(replays_path, replays, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(results_path, results, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(replay_path, replay, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(trail_path, trail, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(timeline_path, timeline, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(events_path, events, methods=["GET"])
    return app


def services_from_env(env: Mapping[str, str] | None = None) -> Services:
    """The composition root's reading of the environment: the code version the image was
    built with, the database the deploy composed and the registration the image ships;
    ``ValueError`` names the one missing, or a registration whose digest is not the
    configuration's."""
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
    return Services(
        code_version=code_version,
        configuration=configuration,
        ready_versions=lambda: served_versions(dsn),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=lambda: LogStore(dsn=dsn, connect=connect_bounded),
        rules=rules_under(configuration, registration),
        results=committed_results,
    )


def app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(services_from_env(env))
