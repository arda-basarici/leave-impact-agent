"""The demo surface's shell: the readiness route answers 200 only when the store answers
and the cache serves the allowlisted world, 503 for an unreachable store or an unready
world, and 200 again from the same process once the store returns; its body names states
and never a cause; the index page renders without JavaScript; and the real page escapes a
string carrying markup, since the world's prose is model-written."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent.registered import effective_rules
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.main import Services, create_app, services_from_env
from leaveimpact.app.ready import Readiness, readiness
from leaveimpact.app.store import AppStoreUnavailable
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.ports.errors import Source, SourceUnreachable
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import MemoryLog
from tests.unit.publishable_fixture import Rows
from tests.unit.registration_fixture import COMMITTED, COMMITTED_FILE, DRAFT_FILE
from tests.unit.test_results_codec import results

CODE = "b" * 40
CONFIGURATION = committed_configuration()
GOLDEN = CONFIGURATION.served_world_version
OTHER = WorldVersion("c" * 64)
RECORDED_MARKUP = "<script>alert('the world's prose')</script> & <b>bold</b>"


class FlippingStore:
    """A store whose state a test moves between reads, as an outage and its end would."""

    def __init__(
        self, versions: frozenset[WorldVersion], reachable: bool = True, schema: bool = True
    ) -> None:
        self.versions = versions
        self.reachable = reachable
        self.schema = schema

    def ready_versions(self) -> frozenset[WorldVersion]:
        if not self.reachable:
            raise SourceUnreachable(Source.CORPUS, "connection refused: OperationalError")
        return self.versions

    def app_schema(self) -> bool:
        if not self.reachable:
            raise AppStoreUnavailable("the app store did not answer: OperationalError")
        return self.schema


def services(
    store: FlippingStore, code: str = CODE, configuration: DemoConfiguration = CONFIGURATION
) -> Services:
    # No replay is published and no log is read by the routes these tests exercise.
    return Services(
        code,
        configuration,
        store.ready_versions,
        store.app_schema,
        Rows(),
        lambda: MemoryLog(),  # type: ignore[arg-type, return-value]
        histories.RULES,
        results,
    )


def client(store: FlippingStore, code: str = CODE) -> TestClient:
    return TestClient(create_app(services(store, code)))


def test_readiness_is_the_store_answering_the_served_world_ready_and_the_schema() -> None:
    store = FlippingStore(frozenset({GOLDEN, OTHER}))
    assert readiness(CODE, CONFIGURATION, store.ready_versions, store.app_schema) == Readiness(
        CODE, GOLDEN, store_reachable=True, served_world_ready=True, app_schema=True
    )
    store.versions = frozenset({OTHER})
    read = readiness(CODE, CONFIGURATION, store.ready_versions, store.app_schema)
    assert (read.store_reachable, read.served_world_ready, read.app_schema, read.ready) == (
        True, False, True, False
    )
    store.versions = frozenset({GOLDEN})
    store.schema = False
    read = readiness(CODE, CONFIGURATION, store.ready_versions, store.app_schema)
    assert (read.store_reachable, read.served_world_ready, read.app_schema, read.ready) == (
        True, True, False, False
    )
    store.reachable = False
    read = readiness(CODE, CONFIGURATION, store.ready_versions, store.app_schema)
    assert (read.store_reachable, read.served_world_ready, read.app_schema, read.ready) == (
        False, False, False, False
    )


def test_the_ready_route_answers_200_503_and_200_again_from_one_process() -> None:
    store = FlippingStore(frozenset({GOLDEN}))
    with client(store) as web:
        first = web.get("/ready")
        assert first.status_code == 200
        assert first.json() == {
            "ready": True,
            "code_version": CODE,
            "served_world_version": GOLDEN,
            "store_reachable": True,
            "served_world_ready": True,
            "app_schema": True,
        }
        store.reachable = False
        down = web.get("/ready")
        assert down.status_code == 503
        assert down.json()["store_reachable"] is False and down.json()["ready"] is False
        assert "OperationalError" not in down.text and "refused" not in down.text
        store.reachable = True
        store.versions = frozenset({OTHER})
        unready = web.get("/ready")
        assert unready.status_code == 503
        assert unready.json()["store_reachable"] is True
        assert unready.json()["served_world_ready"] is False
        store.versions = frozenset({GOLDEN})
        store.schema = False
        unbootstrapped = web.get("/ready")
        assert unbootstrapped.status_code == 503
        assert unbootstrapped.json()["app_schema"] is False
        store.schema = True
        assert web.get("/ready").status_code == 200


def test_the_index_renders_the_served_world_and_the_flag_without_javascript() -> None:
    with client(FlippingStore(frozenset({GOLDEN}))) as web:
        page = web.get("/")
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("text/html")
        assert GOLDEN in page.text and "off" in page.text and CODE in page.text
        assert "<script" not in page.text
        assert web.get("/docs").status_code == 404 and web.get("/openapi.json").status_code == 404


def test_the_real_page_escapes_a_recorded_string_with_markup() -> None:
    """The entry's acceptance: recorded markup renders as text. The code version is a
    string the page shows, so a value carrying markup shows what every rendered string
    gets."""
    with client(FlippingStore(frozenset({GOLDEN})), code=RECORDED_MARKUP) as web:
        text = web.get("/").text
        assert RECORDED_MARKUP not in text
        assert "&lt;script&gt;" in text and "&amp;" in text and "<b>bold</b>" not in text


def test_the_composition_root_names_what_the_environment_lacks() -> None:
    env = {
        "LEAVEIMPACT_CODE_VERSION": CODE,
        "DATABASE_URL": "postgresql://x@localhost/x",
        "LEAVEIMPACT_REGISTRATION_FILE": str(COMMITTED_FILE),
    }
    services = services_from_env(env)
    assert services.code_version == CODE
    assert services.configuration == CONFIGURATION
    assert services.rules == effective_rules(COMMITTED)
    for missing in ("LEAVEIMPACT_CODE_VERSION", "DATABASE_URL", "LEAVEIMPACT_REGISTRATION_FILE"):
        partial = {key: value for key, value in env.items() if key != missing}
        try:
            services_from_env(partial)
        except ValueError as error:
            assert missing in str(error)
        else:
            raise AssertionError(f"composed without {missing}")
    foreign = {**env, "LEAVEIMPACT_REGISTRATION_FILE": str(DRAFT_FILE)}
    with pytest.raises(ValueError, match="registration file's digest"):
        services_from_env(foreign)
    missing_file = {**env, "LEAVEIMPACT_REGISTRATION_FILE": str(COMMITTED_FILE) + ".none"}
    with pytest.raises(ValueError, match="LEAVEIMPACT_REGISTRATION_FILE names"):
        services_from_env(missing_file)


def test_a_live_configuration_shows_on_the_page() -> None:
    live = replace(CONFIGURATION, live_runs=True)
    store = FlippingStore(frozenset({GOLDEN}))
    with TestClient(create_app(services(store, configuration=live))) as web:
        assert ">on<" in web.get("/").text
