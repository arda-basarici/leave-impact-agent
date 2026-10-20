"""The container's entry: serving is the default and gets the environment, the identity
line the deploy reads as its image check, the smoke that loads both roles' prompt assets
and prints the digests a run freezes, then the committed public results' artifact digest
and the demo configuration's served world, its refusal on any of the three that does not
load, and the refusals of a missing code version and an unknown argument."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from leaveimpact.__main__ import main
from leaveimpact.agent.assets import ASSET_NAMES, PromptAssets, load_prompt_assets
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.core.tools import Role
from leaveimpact.results.committed import M2_REPORTED, committed_results
from leaveimpact.results.public import PublicResults

ENV = {"LEAVEIMPACT_CODE_VERSION": "a" * 40}


def test_serving_is_the_default_and_the_identity_line_a_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    served: list[Mapping[str, str]] = []

    def fake_serve(environment: Mapping[str, str]) -> int:
        served.append(environment)
        return 0

    assert main([], ENV, serve=fake_serve) == 0
    assert served == [ENV]
    assert main(["identity"], ENV, serve=fake_serve) == 0
    assert capsys.readouterr().out == f"leaveimpact {'a' * 40}: the demo surface's image\n"
    assert len(served) == 1
    assert main([], {}, serve=fake_serve) == 1
    assert "LEAVEIMPACT_CODE_VERSION unset" in capsys.readouterr().err
    assert main(["serve"], ENV, serve=fake_serve) == 2
    assert "unknown arguments ['serve']" in capsys.readouterr().err
    assert len(served) == 1


def test_serving_refuses_an_environment_without_a_database_before_binding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real serve path up to its composition: no DATABASE_URL is a refusal naming it,
    never a bound socket."""
    assert main([], ENV) == 1
    assert "DATABASE_URL is not set" in capsys.readouterr().err


def test_the_smoke_prints_every_roles_asset_digests_beside_the_code_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One line per asset per role, the digests the registration's roles are compared with."""
    assert main(["smoke"], ENV) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"code_version={'a' * 40}"
    expected = [
        f"{role.value}.{name}={digest}"
        for role in Role
        for name, digest in load_prompt_assets(role).digests()
    ]
    assert lines[1:-2] == expected
    assert len(expected) == len(Role) * len(ASSET_NAMES)
    assert lines[-2] == f"results.{M2_REPORTED}={committed_results().provenance.artifact_digest}"
    assert lines[-1] == f"demo.demo.json={committed_configuration().served_world_version}"


def test_the_smoke_refuses_an_asset_that_does_not_load(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The packaging's failure the smoke exists for: a role whose asset file is missing is
    reported by role and exception type, and the image fails its smoke."""

    def missing_reader(role: Role) -> PromptAssets:
        if role is Role.READER:
            raise FileNotFoundError("prompts/reader/opening.md")
        return load_prompt_assets(role)

    assert main(["smoke"], ENV, load=missing_reader) == 1
    captured = capsys.readouterr()
    assert "the reader prompt assets do not load (FileNotFoundError)" in captured.err
    assert captured.out.startswith(f"code_version={'a' * 40}\ninvestigator.")


def test_the_smoke_refuses_committed_results_that_do_not_load(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same packaging failure for the results file the page renders: missing or not of
    the declared types, the image fails its smoke after the assets' lines."""

    def missing() -> PublicResults:
        raise FileNotFoundError("m2-reported.json")

    def malformed() -> PublicResults:
        raise ValueError("the public results are format 1, got 2")

    for failing, name in ((missing, "FileNotFoundError"), (malformed, "ValueError")):
        assert main(["smoke"], ENV, results=failing) == 1
        captured = capsys.readouterr()
        assert f"the committed public results do not load ({name})" in captured.err
        assert "results." not in captured.out


def test_the_smoke_refuses_a_demo_configuration_that_does_not_load(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same for the configuration the page and the acceptance read: after the results
    line, the image fails its smoke."""

    def malformed() -> DemoConfiguration:
        raise ValueError("the demo configuration is format 1, got 2")

    assert main(["smoke"], ENV, configuration=malformed) == 1
    captured = capsys.readouterr()
    assert "the demo configuration does not load (ValueError)" in captured.err
    assert "results." in captured.out and "demo." not in captured.out
