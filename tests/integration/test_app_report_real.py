"""The report and the trail over the real producer's output: a run worked to its closing by the
real worker over the real log store, published through the app store, and read through the
application with a real log session per request. The first rendering tests of a real export
(the report step's acceptance): the rules-only run, whose claims the rules compose from the
prefetch, has every claim on the report exactly once and every evidence position it cites an
anchor the trail mints; the stating run, whose real turns read a policy document and state its
requirement, has its model calls and the admitted statement on the trail; no run id reaches
either page. Step 8 re-points a copy of this at the replay set."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStore
from leaveimpact.app.main import Services, create_app
from leaveimpact.app.public import PublicationDraft, PublicId, PublicReplay
from leaveimpact.app.read_model import instants_of
from leaveimpact.app.report import ReportView, report_view
from leaveimpact.app.store import Published
from leaveimpact.app.trail import operation_anchor
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_app_surface import app_store
from tests.integration.worker_rig import (
    ATTEMPT,
    RULES,
    RUN,
    WorkerEnding,
    WorkerEndingKind,
    WorkRequest,
    admitted,
    composition,
    saver_on,
    work,
)
from tests.unit import worker_support as support
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

CODE = "b" * 40
SLUG = "real"


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def worked(rig: Rig, world: SealedWorld, script: str) -> tuple[LogStore, FrozenInputs]:
    """``SCRIPTS[script]`` worked to its closing through the work command over the rig."""
    named = support.SCRIPTS[script]
    log, inputs = admitted(rig, world, inputs_for=named.inputs)
    ending = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        log,
        composition(inputs, world, saver_on(rig), script=named),
    )
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    return log, inputs


def pages(rig: Rig, log: LogStore, inputs: FrozenInputs) -> tuple[str, str, ReportView]:
    """The run published under the slug, the report and the trail as the application serves
    them, and the view the page is expected to state, built from the same fold the route
    makes."""
    context = inputs.context
    store = app_store(rig)
    store.ensure_schema()
    written = store.publish(
        PublicationDraft(
            PublicId(SLUG),
            RUN,
            ATTEMPT,
            context.world_version,
            context.scenario_id,
            "The reference run",
            "operator:test",
        )
    )
    assert isinstance(written, Published)
    state = log.load(RUN, ATTEMPT, rules=RULES)
    export = export_of(state)
    header = PublicReplay(
        PublicId(SLUG),
        context.scenario_id,
        "The reference run",
        datetime.now(UTC),
        export.record.status,
    )
    view = report_view(header, export, instants_of(state))
    services = Services(
        code_version=CODE,
        configuration=replace(CONFIGURATION, served_world_version=context.world_version),
        ready_versions=lambda: frozenset({context.world_version}),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=rig.store,
        rules=RULES,
    )
    with TestClient(create_app(services)) as web:
        report = web.get(f"/replays/{SLUG}")
        trail = web.get(f"/replays/{SLUG}/trail")
    assert report.status_code == 200 and trail.status_code == 200
    assert RUN not in report.text and RUN not in trail.text
    assert "The reference run" in report.text
    return report.text, trail.text, view


def test_the_rules_only_runs_claims_are_each_on_the_report_with_their_evidence_on_the_trail(
    rig: Rig, world: SealedWorld
) -> None:
    log, inputs = worked(rig, world, "rules-only")
    report, trail, view = pages(rig, log, inputs)
    assert view.claim_ids(), "the rules compose claims from the prefetch"
    for claim_id in view.claim_ids():
        assert report.count(f'id="{claim_id}"') == 1, claim_id
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
    assert "No model was called." in trail and "The plan was approved automatically." in report


def test_the_stating_runs_model_calls_and_admitted_statement_are_on_the_trail(
    rig: Rig, world: SealedWorld
) -> None:
    log, inputs = worked(rig, world, "stating")
    _, trail, _ = pages(rig, log, inputs)
    assert 'id="call-' in trail
    assert "<strong>admitted</strong>: requires of" in trail
