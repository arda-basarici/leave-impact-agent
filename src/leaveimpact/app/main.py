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
distinguishes a published name from an unknown one. The replay page is this step's header,
the row's public data and the attempt's ending; the report view replaces its body at the
next step.

Statement bounds, per request: the listing makes one app-store statement and one cache
read; the replay page one app-store statement, the log's reads of one attempt on one
connection, and one cache read; each under the store's three-second connect and
three-second statement bounds.

Templates live beside this module and are packaged with it, read by package name like the
committed configuration. Autoescape is on for them through Jinja2's extension selection,
which the test holds by rendering the real page with a string carrying markup: the world's
prose is model-written and the surface must render it as text.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from leaveimpact.adapters.corpus import served_versions
from leaveimpact.agent.log_store import LogStore, LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.public import public_id_of
from leaveimpact.app.read_model import (
    LogSession,
    PublishableReads,
    admitted,
    listing,
    replay_view,
    rules_under,
)
from leaveimpact.app.ready import AppSchema, ReadyVersions, readiness
from leaveimpact.app.store import (
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
    connect_bounded,
)
from leaveimpact.core.ports.errors import SourceUnreachable

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
    RouteClass("/replays/{public_id}", Surface.ATTEMPT_SCOPED),
)
"""Every route the application registers, classified; the acceptance sweep compares this
with the route table and walks each attempt-scoped path with a name the predicate refuses."""


@dataclass(frozen=True, slots=True)
class Services:
    """What the routes need, bound once at the composition root."""

    code_version: str
    configuration: DemoConfiguration
    ready_versions: ReadyVersions
    app_schema: AppSchema
    rows: PublishableReads
    log_sessions: Callable[[], LogSession]
    rules: Rules


def create_app(services: Services) -> FastAPI:
    """The application over ``services``: the index, the readiness route, the listing of
    published replays and the replay page."""
    app = FastAPI(title="Leave Impact Agent", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES))
    configuration = services.configuration
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

    def replay(request: Request, public_id: str) -> HTMLResponse:
        try:
            name = public_id_of(public_id)
        except ValueError:
            return not_found(request)
        session = services.log_sessions()
        try:
            admission = admitted(name, services.rows, session, configuration, services.rules)
            if admission is None:
                return not_found(request)
            view = replay_view(admission)
            if not cache_serves():
                return unavailable(request)
        except _UNAVAILABLE:
            return unavailable(request)
        finally:
            session.close()
        return page(request, "replay.html", replay=view)

    # Registered by call rather than by decorator so the handlers are plain closures over
    # the services, named and typed where they are read; the paths are ROUTES' strings so
    # the table and the registration cannot drift.
    index_path, ready_path, replays_path, replay_path = (route.path for route in ROUTES)
    app.add_api_route(index_path, index, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(ready_path, ready, methods=["GET"])
    app.add_api_route(replays_path, replays, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route(replay_path, replay, methods=["GET"], response_class=HTMLResponse)
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
    )


def app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(services_from_env(env))
