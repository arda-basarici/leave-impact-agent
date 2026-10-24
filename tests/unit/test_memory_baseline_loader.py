"""The memory baseline's load generator (`probes/memory-baseline/loader.py`) run against an
in-process stand-in for the app: readers walk the listing's replays through every page,
loopers fetch the stream to its end and start again, a refusal by the bound is counted as
its status and retried after the pause, both stop at the hold, and the summary carries
the statuses and the latency quantiles the reading is reduced from. The stand-in serves
the listing's link form and the stream's ending; nothing of the app is imported, as the
instance run imports nothing of it either."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse

LOADER = Path(__file__).resolve().parents[2] / "probes" / "memory-baseline" / "loader.py"
REPLAYS = ("scenario-001", "scenario-002", "scenario-003")


@pytest.fixture(scope="module")
def loader() -> ModuleType:
    spec = importlib.util.spec_from_file_location("memory_baseline_loader", LOADER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def stand_in(bound: int) -> FastAPI:
    """The listing with the templates' link form, a page per route, and a stream that
    sends three frames and ends, admitting ``bound`` at a time and answering 503 past it."""
    app = FastAPI()
    held = 0

    def listing() -> str:
        links = "".join(f'<li><a href="/replays/{name}">{name}</a></li>' for name in REPLAYS)
        return f"<ul>{links}</ul>"

    def page(public_id: str) -> str:
        return f"<h1>{public_id}</h1>"

    async def events(public_id: str, after: str) -> Response:
        nonlocal held
        assert after == "0"
        if held >= bound:
            return Response(status_code=503)
        held += 1

        async def frames() -> AsyncIterator[bytes]:
            nonlocal held
            try:
                for position in (1, 2):
                    yield f"id: {position}\nevent: line\ndata: {{}}\n\n".encode()
                    await asyncio.sleep(0.01)
                yield b"id: 3\nevent: closed\ndata: {}\n\n"
            finally:
                held -= 1

        return StreamingResponse(frames(), media_type="text/event-stream")

    def html_route(path: str, endpoint: Callable[..., str]) -> None:
        app.add_api_route(path, endpoint, methods=["GET"], response_class=HTMLResponse)

    html_route("/replays", listing)
    html_route("/results", lambda: "<p>results</p>")
    for leaf in ("", "/trail", "/timeline"):
        html_route("/replays/{public_id}" + leaf, page)
    app.add_api_route("/replays/{public_id}/events", events, methods=["GET"])
    return app


def level(loader: ModuleType, app: FastAPI, **options: Any) -> dict[str, Any]:
    args = argparse.Namespace(
        base_url="http://stand-in", label="test", hold=0.4, readers=0, streams=0
    )
    for name, value in options.items():
        setattr(args, name, value)
    transport = httpx.ASGITransport(app=app)
    run = cast(Any, loader).run
    return cast(dict[str, Any], asyncio.run(run(args, transport)))


def test_readers_walk_every_page_and_stop_at_the_hold(loader: ModuleType) -> None:
    summary = level(loader, stand_in(bound=8), readers=2)
    reads = summary["reads"]
    assert summary["replays"] == len(REPLAYS)
    assert reads["by_status"] == {"200": reads["latency_ms"]["count"]}
    assert reads["latency_ms"]["count"] >= 10, "two readers over 0.4 s of in-process pages"
    assert reads["error_count"] == 0 and reads["errors"] == []
    assert set(reads["latency_ms"]) == {"count", "p50", "p95", "max", "mean"}
    assert summary["streams_fetched"] == {
        "by_status": {},
        "latency_ms": {},
        "bytes": 0,
        "error_count": 0,
        "errors": [],
    }
    assert summary["started_at"] <= summary["ended_at"], "second resolution, a 0.4 s hold"


def test_loopers_fetch_to_the_ending_and_count_the_bounds_refusal(loader: ModuleType) -> None:
    summary = level(loader, stand_in(bound=1), streams=3)
    fetched = summary["streams_fetched"]
    assert set(fetched["by_status"]) == {"200", "503"}, "one admitted at a time, the rest refused"
    per_stream = 2 * 28 + 30  # two line frames and the closing frame
    assert fetched["bytes"] == fetched["by_status"]["200"] * per_stream
    assert fetched["error_count"] == 0
    assert fetched["latency_ms"]["count"] == sum(fetched["by_status"].values())
    assert summary["reads"]["by_status"] == {}


def test_quantiles_are_nearest_rank(loader: ModuleType) -> None:
    quantiles = cast(Any, loader).quantiles
    assert quantiles([]) == {}
    assert quantiles([5.0, 1.0, 3.0, 2.0, 4.0]) == {
        "count": 5,
        "p50": 3.0,
        "p95": 4.0,
        "max": 5.0,
        "mean": 3.0,
    }


def test_the_listing_link_form_is_the_templates(loader: ModuleType) -> None:
    link = cast(Any, loader).LINK
    page = '<h3><a href="/replays/scenario-004">Two impacts</a> <span>x</span></h3>'
    page += '<a href="/replays">All replays</a><a href="/replays/scenario-030/trail">t</a>'
    assert link.findall(page) == ["scenario-004"], "a page link, never a sub-page"
