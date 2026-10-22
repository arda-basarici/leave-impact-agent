"""The introduced replays' walkthroughs (`leaveimpact.app.walkthroughs`): the file decodes
in order and refuses a wrong format, a missing or unknown field, a name the slug rule
refuses, an unknown tier, empty text and a repeated name; the listing shows the introduced
entries first in the file's order and only for a titled row the file names, a walkthrough
without a row being unreachable and a titled row without one staying in the full list; the
committed file names three replays of the committed replay plan, one per tier."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from leaveimpact.app.public import PublicAttempt, PublicId
from leaveimpact.app.walkthroughs import (
    TIERS,
    Walkthrough,
    committed_walkthroughs,
    decode_walkthroughs,
    listing_view,
    walkthrough_for,
)
from leaveimpact.core.ids import ScenarioId

ROOT = Path(__file__).resolve().parents[2]
REPLAY_PLAN = ROOT / "probes" / "replay-set" / "plan.json"
AT = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def entry(public_id: str, tier: str = "structured", **changes: object) -> dict[str, object]:
    return {
        "public_id": public_id,
        "tier": tier,
        "inspect": "Read the actions.",
        "see": "Every row agrees.",
        **changes,
    }


def file_of(*entries: dict[str, object], version: int = 1) -> str:
    return json.dumps({"format_version": version, "walkthroughs": list(entries)})


def attempt(public_id: str, title: str | None) -> PublicAttempt:
    return PublicAttempt(PublicId(public_id), ScenarioId("scenario_001"), title, AT)


def test_the_file_decodes_in_order_with_every_field() -> None:
    decoded = decode_walkthroughs(file_of(entry("b", "adversarial"), entry("a", "fragmented")))
    assert decoded == (
        Walkthrough(PublicId("b"), "adversarial", "Read the actions.", "Every row agrees."),
        Walkthrough(PublicId("a"), "fragmented", "Read the actions.", "Every row agrees."),
    )


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (file_of(version=2), "format 1, got 2"),
        (json.dumps({"format_version": 1}), "walkthroughs"),
        (file_of({"public_id": "a", "tier": "structured", "inspect": "x"}), "see"),
        (file_of(entry("a", title="T")), "title"),
        (file_of(entry("Scenario 4")), "a public id is lowercase"),
        (file_of(entry("a", "golden")), "tier is one of"),
        (file_of(entry("a", inspect="  ")), "non-empty text"),
        (file_of(entry("a"), entry("a", "fragmented")), "appears twice"),
    ],
)
def test_the_decoder_refuses_rather_than_guesses(content: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        decode_walkthroughs(content)


def test_the_listing_introduces_titled_rows_the_file_names_in_the_files_order() -> None:
    walkthroughs = decode_walkthroughs(
        file_of(entry("third", "adversarial"), entry("first"), entry("unpublished", "fragmented"))
    )
    entries = (
        attempt("first", "A pass"),
        attempt("second", "Titled, no walkthrough"),
        attempt("third", "A refusal"),
        attempt("fourth", None),
    )
    view = listing_view(entries, walkthroughs)
    assert [item.entry.public_id for item in view.introduced] == ["third", "first"]
    assert view.introduced[0].walkthrough.tier == "adversarial"
    assert view.entries == entries, "the full list is the projection, the introduced among it"


def test_a_walkthrough_renders_only_on_a_titled_row_the_file_names() -> None:
    walkthroughs = decode_walkthroughs(file_of(entry("named")))
    assert walkthrough_for(walkthroughs, PublicId("named"), "A title") is not None
    assert walkthrough_for(walkthroughs, PublicId("named"), None) is None
    assert walkthrough_for(walkthroughs, PublicId("other"), "A title") is None


def test_the_committed_file_names_three_replays_of_the_plan_one_per_tier() -> None:
    walkthroughs = committed_walkthroughs()
    assert len(walkthroughs) == 3
    assert sorted(w.tier for w in walkthroughs) == sorted(TIERS)
    plan = json.loads(REPLAY_PLAN.read_text(encoding="utf-8"))
    names = {key.rsplit("/", 1)[1].replace("_", "-") for key in plan["order"]}
    assert {w.public_id for w in walkthroughs} <= names
    for w in walkthroughs:
        assert "run-" not in w.inspect + w.see, "no run id reaches the page"
