"""The timeline page over the surface rig: a closed attempt's page shows every line with its
position and instant, keyed by attempt and position, with no script and the links to the
report and the trail; an open attempt's page shows the lines so far and carries the script
that follows the stream from the last rendered position, keyed the same way, with the
no-script note; the replay, report and trail pages link to the timeline; and a line whose
text carries markup renders as text, since the narration's words come from the log."""

from __future__ import annotations

from markupsafe import escape

from leaveimpact.agent.log_events import EventKind, OperationEvent, OperationResult, PrefetchKey
from leaveimpact.core import RefusedCallOutcome, Source
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import CLOSED, SERVED, history_in_world
from tests.unit.test_app_stream import LIVE, client_of, expected_lines, feed
from tests.unit.test_app_surface import Rig


def test_a_closed_attempts_timeline_is_its_whole_narration_without_a_script() -> None:
    rig = Rig()
    page = client_of(rig).get("/replays/served/timeline")
    assert page.status_code == 200
    lines = expected_lines(history_in_world(CLOSED, SERVED))
    for line in lines:
        assert f'<li id="served:{line["position"]}">' in page.text
        assert (
            f"position {line['position']}, recorded in the log at {line['recorded_at']}"
            in page.text
        )
        assert str(escape(line["text"])) in page.text
    assert "<script" not in page.text
    assert "This run has ended; the timeline is its record" in page.text
    assert 'href="/replays/served"' in page.text and 'href="/replays/served/trail"' in page.text
    assert rig.sessions.opened == rig.sessions.closed


def test_an_open_attempts_timeline_shows_the_lines_so_far_and_follows_the_stream() -> None:
    rig = Rig()
    page = client_of(rig).get("/replays/live/timeline")
    assert page.status_code == 200
    (first,) = expected_lines(history_in_world(CLOSED, SERVED, run_id=LIVE[0]))[:1]
    assert '<li id="live:1">' in page.text and str(escape(first["text"])) in page.text
    assert "Following the run live" in page.text
    assert "Scripting is off" in page.text
    assert "<script>" in page.text
    assert 'var attempt = "live";' in page.text and "var after = 1;" in page.text
    assert '"/events?after=" + after' in page.text
    assert 'addEventListener("line"' in page.text
    assert 'addEventListener("closed"' in page.text
    assert 'addEventListener("unavailable"' in page.text
    assert "textContent = data.text" in page.text and "innerHTML" not in page.text
    assert "in progress" in page.text
    # Group 3's external read: the open timeline leads back to the page where a decision
    # is asked, in its header always and in its status line when the request's frame lands.
    assert '<a href="/replays/live">The replay page, where a decision is asked</a>' in page.text
    assert f'data.kind === "{EventKind.APPROVAL_REQUESTED.value}"' in page.text
    assert 'link.href = "/replays/" + encodeURIComponent(attempt)' in page.text
    assert "Audit trail" not in page.text, "the trail needs an export, which an open run has not"


def test_the_other_pages_link_to_the_timeline() -> None:
    client = client_of(Rig())
    assert 'href="/replays/live/timeline"' in client.get("/replays/live").text
    assert 'href="/replays/served/timeline"' in client.get("/replays/served").text
    assert 'href="/replays/served/timeline"' in client.get("/replays/served/trail").text


def test_a_line_carrying_markup_renders_as_text() -> None:
    rig = Rig()
    log = histories.History()
    log.admit(histories.inputs(reservation=10 * histories.cases.ALLOCATION))
    log.claim()
    refused = OperationResult(
        "work_items", Source.JIRA, {}, RefusedCallOutcome("<b>bold</b> is not an argument")
    )
    log.worker(OperationEvent(PrefetchKey(1), refused), offset=100)
    for logged in log.logged()[1:]:
        feed(rig, logged)
    page = client_of(rig).get("/replays/live/timeline")
    assert page.status_code == 200
    assert "&lt;b&gt;bold&lt;/b&gt; is not an argument" in page.text
    assert "<b>bold</b>" not in page.text
