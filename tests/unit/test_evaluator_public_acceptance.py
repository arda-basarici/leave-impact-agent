"""The acceptance of a committed public results file: the artifact is hashed before it is
parsed and refused by name when it is not the recorded one, the regenerated projection is
compared byte for byte with a difference named by its first path, the served world is
held open, and a verdict never quotes a figure."""

from __future__ import annotations

import json
from typing import cast

import pytest

from leaveimpact.evaluator import artifact_json
from leaveimpact.evaluator.public_acceptance import accept_public_results
from leaveimpact.evaluator.public_results import project_public_results
from leaveimpact.results.codec import public_results_bytes
from leaveimpact.world.disclosure import Disclosure
from tests.unit.test_evaluator_artifact_json import artifact_of
from tests.unit.throwaway_world import loaded_world


@pytest.fixture(scope="module")
def artifact() -> bytes:
    return artifact_json.artifact_bytes(artifact_of(loaded_world("golden")))


@pytest.fixture(scope="module")
def committed(artifact: bytes) -> bytes:
    return public_results_bytes(
        project_public_results(artifact, world_disclosure=Disclosure.OPEN)
    )


def test_the_committed_projection_of_the_recorded_artifact_is_accepted(
    artifact: bytes, committed: bytes
) -> None:
    verdict = accept_public_results(
        committed, artifact, measurement_disclosure=Disclosure.OPEN,
        served_disclosure=Disclosure.OPEN,
    )
    assert verdict.accepted and verdict.findings == ()
    assert verdict.recorded_digest == verdict.artifact_digest


def test_another_artifact_is_refused_by_digest_before_it_is_parsed(committed: bytes) -> None:
    verdict = accept_public_results(
        committed, b"not even json", measurement_disclosure=Disclosure.OPEN,
        served_disclosure=Disclosure.OPEN,
    )
    assert not verdict.accepted
    (finding,) = verdict.findings
    assert finding.startswith("the artifact given is not the one the committed file records")
    assert verdict.recorded_digest is not None
    assert verdict.recorded_digest in finding and verdict.artifact_digest in finding


def test_a_committed_file_that_differs_from_the_regeneration_is_named_by_its_first_path(
    artifact: bytes, committed: bytes
) -> None:
    data = cast("dict[str, object]", json.loads(committed))
    cast("dict[str, object]", data["plan"])["resamples"] += 1  # pyright: ignore[reportOperatorIssue]
    altered = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    verdict = accept_public_results(
        altered, artifact, measurement_disclosure=Disclosure.OPEN,
        served_disclosure=Disclosure.OPEN,
    )
    (finding,) = verdict.findings
    assert finding == "the regenerated projection differs from the committed file at plan.resamples"
    # The measurement world's mark is a statement the file makes, held to the sealed one.
    verdict = accept_public_results(
        committed, artifact, measurement_disclosure=Disclosure.EMBARGOED,
        served_disclosure=Disclosure.OPEN,
    )
    (finding,) = verdict.findings
    assert finding.endswith("at disclosures.world_disclosure")


def test_a_served_world_that_is_embargoed_is_refused_whatever_the_file_says(
    artifact: bytes, committed: bytes
) -> None:
    verdict = accept_public_results(
        committed, artifact, measurement_disclosure=Disclosure.OPEN,
        served_disclosure=Disclosure.EMBARGOED,
    )
    assert verdict.findings == (
        "the served world is sealed embargoed; the demo serves open worlds",
    )


def test_a_committed_file_not_of_the_declared_types_is_a_finding(artifact: bytes) -> None:
    verdict = accept_public_results(
        b'{"format_version": 1}', artifact, measurement_disclosure=Disclosure.OPEN,
        served_disclosure=Disclosure.OPEN,
    )
    assert verdict.recorded_digest is None
    (finding,) = verdict.findings
    assert finding.startswith("the committed file is not of the declared types")

