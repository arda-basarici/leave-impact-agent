"""The generation job's composition on the one failure that has paid for model calls.

A target that exhausts its cap ends the run before any write, and until this test the job
let the exception through with its traceback and printed none of the stage's counters, so
the attempts and tokens of a failed run existed only in the provider's billing (the first
unprojected generation, 2026-10-08: eighty-one attempts, no count printed). The job's
other paths are the entry point's and the sealing's tests; this file holds the composition
at that one seam, with the fresh stage and the model wiring replaced at the module's names.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest

from leaveimpact.adapters.wiring import PREFIX
from leaveimpact.generator import __main__ as job
from leaveimpact.generator.materialize import MaterializationFailed, ProseMetrics


def _unprojected_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A local store outside any repository and the three prose names; no bucket, no host."""
    for name in ("WORLD_BUCKET", "TRUTH_BUCKET", "AWS_REGION"):
        monkeypatch.delenv(PREFIX + name, raising=False)
    monkeypatch.setenv(PREFIX + "OBJECT_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv(PREFIX + "PROSE_WRITER_MODEL", "writer-model")
    monkeypatch.setenv(PREFIX + "PROSE_CHECKER_MODEL", "checker-model")
    monkeypatch.setenv(PREFIX + "BEDROCK_REGION", "eu-central-1")


def _no_models(models: object) -> tuple[object, object]:
    return object(), object()


def test_a_cap_exhausted_prints_the_prose_metrics_and_still_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _unprojected_environment(monkeypatch, tmp_path)
    metrics = ProseMetrics(writer_attempts=81, targets_cap_exhausted=1, writer_input_tokens=42_360)

    def exhausted(*args: object, **kwargs: object) -> NoReturn:
        raise MaterializationFailed({"clause_049": ()}, metrics)

    monkeypatch.setattr(job, "prose_models_for", _no_models)
    monkeypatch.setattr(job, "fresh_world", exhausted)

    with pytest.raises(MaterializationFailed) as caught:
        job.main(["--seed", "101", "--world-start", "2026-01-05", "--unprojected"])

    printed = capsys.readouterr().out.splitlines()
    assert "prose_writer_attempts=81" in printed
    assert "prose_targets_cap_exhausted=1" in printed
    assert "prose_writer_input_tokens=42360" in printed
    assert not any(line.startswith("world_version=") for line in printed)
    assert caught.value.metrics is metrics
    assert not (tmp_path / "store").exists() or not any((tmp_path / "store").iterdir())
