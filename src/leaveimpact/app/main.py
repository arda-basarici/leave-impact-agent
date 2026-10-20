"""The application: the routes, the templates and the composition root that binds them to
the deployed database and the committed configuration.

``create_app`` takes the services as plain values and callables, so a test builds the whole
application over an in-memory readiness read and never a database; ``app_from_env`` is the
composition root the serving command calls, reading the database URL and the code version
the image was built with. Routes that read the store are plain ``def`` routes, which
Starlette runs on its thread pool (the entry's HTTP-shell ruling: store access synchronous
and deliberate, nothing held open while a browser waits). The API explorers FastAPI serves
by default are off: the surface is pages a stranger reads, and the one endpoint that will
take visitor input is a form, not an API.

Templates live beside this module and are packaged with it, read by package name like the
committed configuration. Autoescape is on for them through Jinja2's extension selection,
which the test holds by rendering the real page with a string carrying markup: the world's
prose is model-written and the surface must render it as text.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from leaveimpact.adapters.corpus import served_versions
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.ready import AppSchema, ReadyVersions, readiness
from leaveimpact.app.store import AppStore

CODE_VERSION = "LEAVEIMPACT_CODE_VERSION"
DATABASE = "DATABASE_URL"
REGISTRATION_FILE = "LEAVEIMPACT_REGISTRATION_FILE"
"""The registration the image ships, set by the Dockerfile; the surface folds every attempt
under its rules after checking its digest is the committed configuration's."""
TEMPLATES = files("leaveimpact.app").joinpath("templates")


@dataclass(frozen=True, slots=True)
class Services:
    """What the routes need, bound once at the composition root."""

    code_version: str
    configuration: DemoConfiguration
    ready_versions: ReadyVersions
    app_schema: AppSchema


def create_app(services: Services) -> FastAPI:
    """The application over ``services``: the index page and the readiness route."""
    app = FastAPI(title="Leave Impact Agent", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES))

    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "code_version": services.code_version,
                "served_world_version": services.configuration.served_world_version,
                "live_runs": services.configuration.live_runs,
            },
        )

    def ready() -> JSONResponse:
        read = readiness(
            services.code_version,
            services.configuration,
            services.ready_versions,
            services.app_schema,
        )
        return JSONResponse(read.as_json(), status_code=200 if read.ready else 503)

    # Registered by call rather than by decorator so the handlers are plain closures over
    # the services, named and typed where they are read.
    app.add_api_route("/", index, methods=["GET"], response_class=HTMLResponse)
    app.add_api_route("/ready", ready, methods=["GET"])
    return app


def services_from_env(env: Mapping[str, str] | None = None) -> Services:
    """The composition root's reading of the environment: the code version the image was
    built with and the database the deploy composed; ``ValueError`` names the one missing."""
    environment = os.environ if env is None else env
    code_version = environment.get(CODE_VERSION, "").strip()
    if not code_version:
        raise ValueError(f"{CODE_VERSION} unset — image built without provenance")
    dsn = environment.get(DATABASE, "").strip()
    if not dsn:
        raise ValueError(f"{DATABASE} is not set and the application needs it")
    return Services(
        code_version=code_version,
        configuration=committed_configuration(),
        ready_versions=lambda: served_versions(dsn),
        app_schema=AppStore(dsn=dsn).schema_supported,
    )


def app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(services_from_env(env))
