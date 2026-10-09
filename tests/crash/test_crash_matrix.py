"""The crash matrix as a test: every kill point of each reference run (the completing one,
the one stopped by infrastructure, and the two focused references of the real turns at
their families) and of each command's run recovers as the manifest forecasts, and the
manifest names every family the references cross, a command's under its mode, and no other.

Under the ``crash`` marker: child processes, the PostgreSQL service, minutes. The report of a
run is written beside pytest's temporary directory as ``crash-matrix.json`` so a failing row
can be read whole.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.crash.matrix import (
    COMMAND_MODES,
    REFERENCE_SCRIPTS,
    MatrixResult,
    manifest_families,
    run_matrix,
)
from tests.integration.corpus_support import database_url

pytestmark = pytest.mark.crash


@pytest.fixture(scope="module")
def matrix(tmp_path_factory: pytest.TempPathFactory) -> MatrixResult:
    directory = tmp_path_factory.mktemp("crash")
    result = run_matrix(database_url(), directory)
    (directory / "crash-matrix.json").write_text(
        json.dumps(result.summary(), indent=2), encoding="utf-8"
    )
    return result


def test_every_kill_point_recovers_as_forecast(matrix: MatrixResult) -> None:
    summary = matrix.summary()
    assert summary["rows"] >= summary["reference_crossings"] > 60, summary
    assert set(summary["references"]) == set(REFERENCE_SCRIPTS), summary
    assert all(count > 60 for count in summary["references"].values()), summary
    assert set(summary["command_crossings"]) == set(COMMAND_MODES), summary
    assert all(count > 0 for count in summary["command_crossings"].values()), summary
    assert not matrix.failures, json.dumps(summary["failed"], indent=2)


def test_the_manifest_names_every_family_the_references_cross_and_no_other(
    matrix: MatrixResult,
) -> None:
    crossed = matrix.families
    forecast = {f.split("#")[0] for f in manifest_families()}
    assert crossed == forecast, {
        "crossed, not forecast": sorted(crossed - forecast),
        "forecast, not crossed": sorted(forecast - crossed),
    }


def test_the_report_is_written(
    matrix: MatrixResult, tmp_path_factory: pytest.TempPathFactory
) -> None:
    root = Path(tmp_path_factory.getbasetemp())
    assert any(root.rglob("crash-matrix.json"))
