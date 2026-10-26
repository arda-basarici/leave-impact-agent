"""The hostname half of the disclosure sweep, over bodies built by hand and by the real
encoders, with the gate's own patterns: the page list follows the listing, a cited prefix of
an embargoed digest is found and named without its value, a structural hit is placed on its
line, a clean body of the kind the pages serve is clean under the real patterns, and what
the application's frame encoder and the templates' escaping do to a pattern does not hide
it (the first external read of the crawl: the raw scan passed both)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from markupsafe import escape

from leaveimpact.agent.log_events import EventKind
from leaveimpact.app.narration import Line
from leaveimpact.app.stream import line_frame
from leaveimpact.evaluator.entrypoint import cited_forms
from leaveimpact.evaluator.public_crawl import (
    GLOBAL_PATHS,
    crawl_paths,
    page_findings,
    views_of,
)
from tests.unit.test_disclosure_sweep import NAMES, POINTERS

DIGEST = "7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4"
EMBARGOED = {"semantic digest": cited_forms(DIGEST)}
PATTERNS = POINTERS + NAMES
POINTER_NAME = next(name for name, _ in POINTERS if name.startswith("a forks"))
POINTER_TEXT = "forks" + " file"
"""The gate's own pattern for a private rulings record, its literal assembled at run time so
this file does not hold it: the gate reads every tracked file, this one included."""

LISTING = """
<ul>
  <li><a href="/replays/scenario-004">scenario_004</a></li>
  <li><a href="/replays/scenario-019">scenario_019</a></li>
  <li><a href="/replays/scenario-004">scenario_004 again</a></li>
</ul>
<a href="/results">results</a>
"""


def test_the_page_list_is_the_listing_s_attempts_each_with_four_surfaces() -> None:
    paths = crawl_paths(LISTING)
    assert paths[: len(GLOBAL_PATHS)] == GLOBAL_PATHS
    assert paths[len(GLOBAL_PATHS) :] == (
        "/replays/scenario-004",
        "/replays/scenario-004/trail",
        "/replays/scenario-004/timeline",
        "/replays/scenario-004/events?after=0",
        "/replays/scenario-019",
        "/replays/scenario-019/trail",
        "/replays/scenario-019/timeline",
        "/replays/scenario-019/events?after=0",
    )


def test_an_empty_listing_yields_the_global_routes_alone() -> None:
    assert crawl_paths("<ul></ul>") == GLOBAL_PATHS


def test_a_cited_prefix_of_an_embargoed_digest_is_named_and_not_valued() -> None:
    body = f"<p>run admitted: scenario 4 of world {DIGEST[:12]}…</p>"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.embargoed == ("semantic digest",)
    assert not found.clean
    assert DIGEST[:8] not in " ".join(found.embargoed + found.structural)


def test_a_bare_prefix_without_the_ellipsis_is_not_a_hit() -> None:
    body = f"<p>commit {DIGEST[:12]} built the image</p>"
    assert page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS).clean


def test_a_structural_hit_is_placed_on_its_line_under_the_gate_s_name() -> None:
    body = f"<h1>Replay</h1>\n<p>ruled in the step's {POINTER_TEXT}</p>\n<p>fine</p>"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.structural == (f"2: {POINTER_NAME}",)


def test_a_model_s_product_name_in_a_page_is_not_narration() -> None:
    body = "<dd>Claude Haiku 4.5 at temperature 0</dd>"
    assert page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS).clean


def test_external_hosts_are_reported_as_a_fact_beside_a_clean_verdict() -> None:
    body = (
        '<a href="https://ardabasarici.dev/projects">site</a>\n'
        '<script type="module" src="https://static.example.net/beacon.min.js/v1"></script>\n'
        '<a href="/replays/scenario-004">local</a>'
    )
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.clean
    assert found.external_hosts == frozenset(
        {"https://ardabasarici.dev", "https://static.example.net"}
    )


def test_the_patterns_are_applied_as_given() -> None:
    only = (("a marker", re.compile(r"MARKER")),)
    found = page_findings(f"x\nMARKER\nsee the {POINTER_TEXT}", embargoed={}, patterns=only)
    assert found.structural == ("2: a marker",)


def test_a_cited_prefix_inside_a_real_narration_frame_is_found() -> None:
    line = Line(
        position=1,
        recorded_at=datetime(2026, 10, 22, 20, 2, 48, tzinfo=UTC),
        kind=EventKind("admitted"),
        text=f"run admitted: scenario scenario_004 of world {DIGEST[:12]}…, attempt 1",
    )
    body = line_frame(line).decode("utf-8")
    assert "…" not in body, "the encoder escapes the ellipsis, which is the case under test"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.embargoed == ("semantic digest",)
    assert dict(views_of(body))["frame data"].endswith(f"{DIGEST[:12]}…, attempt 1")


def test_a_possessive_pattern_escaped_by_the_template_is_found_in_the_decoded_view() -> None:
    body = f"<p>{escape(chr(39).join(['the stream', 's access note']))}</p>"
    assert "&#39;" in body, "the template escapes the apostrophe, which is the case under test"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.structural == ("html-decoded 1: a stream's possession",)


def test_a_cited_prefix_ending_in_an_entity_ellipsis_is_found() -> None:
    body = f"<p>world {DIGEST[:12]}&#8230;</p>"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.embargoed == ("semantic digest",)


def test_a_frame_whose_data_is_not_json_is_read_as_text() -> None:
    body = f"event: line\ndata: plain {DIGEST[:8]}…\n\n"
    found = page_findings(body, embargoed=EMBARGOED, patterns=PATTERNS)
    assert found.embargoed == ("semantic digest",)
