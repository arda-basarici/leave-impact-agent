"""The report and the trail over a real replay's export: the structured introduced example of
the demo's replay set (`scenario_004`, run on the golden world 2026-10-22), committed as
`tests/fixtures/replay-scenario-004-export.json` with a sidecar naming the object it was
fetched from (key, version id, digest), the replay step's re-pointing of the report step's
real-export test so CI renders a real producer's output without a bucket or a model.

Held here: the fixture is the sidecar's bytes; the export decodes and is the scenario the
sidecar names; the report, rendered through the real templates under the committed title,
carries every claim exactly once and its walkthrough above the ending; every evidence
position a claim cites is an anchor the trail mints; no run id reaches either page. The
rows' agreement with the answer key is the operator's offline grading
(`probes/replay-set/grading.json`), which the surface never imports."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from leaveimpact.app.main import templating
from leaveimpact.app.public import PublicId, PublicReplay
from leaveimpact.app.report import ReportView, report_view
from leaveimpact.app.trail import operation_anchor, trail_view
from leaveimpact.app.walkthroughs import committed_walkthroughs, walkthrough_for
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import decode_export_bytes
from tests.unit.publishable_fixture import CONFIGURATION

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPORT = FIXTURES / "replay-scenario-004-export.json"
SIDECAR = FIXTURES / "replay-scenario-004-export.sidecar.json"
TITLE = "Two impacts of one leave, planned whole"
CODE = "c" * 40


@pytest.fixture(scope="module")
def sidecar() -> dict[str, object]:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def export(sidecar: dict[str, object]) -> RunExport:
    content = EXPORT.read_bytes()
    assert hashlib.sha256(content).hexdigest() == sidecar["sha256"]
    assert len(content) == sidecar["bytes"]
    return decode_export_bytes(content)


def header(export: RunExport, sidecar: dict[str, object]) -> PublicReplay:
    return PublicReplay(
        PublicId(str(sidecar["public_id"])),
        export.context.scenario_id,
        TITLE,
        datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
        export.record.status,
    )


def rendered(name: str, replay: PublicReplay, view: object) -> str:
    walkthrough = walkthrough_for(committed_walkthroughs(), replay.public_id, replay.title)
    return (
        templating()
        .env.get_template(name)
        .render(
            code_version=CODE,
            served_world_version=CONFIGURATION.served_world_version,
            live_runs=False,
            replay=replay,
            view=view,
            walkthrough=walkthrough,
        )
    )


def test_the_fixture_is_the_sidecars_object_and_the_scenario_it_names(
    export: RunExport, sidecar: dict[str, object]
) -> None:
    assert str(export.context.scenario_id) == sidecar["scenario_id"]
    assert str(export.context.world_version) == sidecar["world_version"]
    assert str(sidecar["key"]).startswith(f"runs/{sidecar['world_version']}/")
    assert sidecar["tier"] == "structured" and sidecar["public_id"] == "scenario-004"


def test_the_report_states_every_claim_once_with_its_walkthrough_above_the_ending(
    export: RunExport, sidecar: dict[str, object]
) -> None:
    replay = header(export, sidecar)
    view = report_view(replay, export, {})
    assert isinstance(view, ReportView) and len(view.claim_ids()) > 1
    page = rendered("report.html", replay, view)
    for claim_id in view.claim_ids():
        assert page.count(f'id="{claim_id}"') == 1, claim_id
    assert TITLE in page and "Walkthrough" in page
    assert page.index("Walkthrough") < page.index("The run completed.")
    assert "then the two coverage actions" in page, "the committed walkthrough names this replay"
    assert len(view.impacts) == 2, "the structured example has two impacts"


def test_every_cited_position_is_an_anchor_the_trail_mints_and_no_run_id_is_shown(
    export: RunExport, sidecar: dict[str, object]
) -> None:
    replay = header(export, sidecar)
    view = report_view(replay, export, {})
    report = rendered("report.html", replay, view)
    trail = rendered("trail.html", replay, trail_view(replay, export, {}))
    cited = {
        position
        for section in view.impacts
        for block in (section.impact, *section.assessments, *section.actions)
        for item in block.evidence
        for position in item.positions
    }
    assert cited, "the claims cite records the run read"
    for position in cited:
        assert f'id="{operation_anchor(position)}"' in trail, position
    run_id = export.run_id
    assert run_id.startswith("run-") and run_id not in report and run_id not in trail
    assert str(sidecar["version_id"]) not in report
