"""The container's entry: the identity line the deploy reads, the smoke that loads both
roles' prompt assets and prints the digests a run freezes, its refusal on an asset that does
not load, and the refusals of a missing code version and an unknown argument."""

from __future__ import annotations

import pytest

from leaveimpact.__main__ import main
from leaveimpact.agent.assets import ASSET_NAMES, PromptAssets, load_prompt_assets
from leaveimpact.core.tools import Role

ENV = {"LEAVEIMPACT_CODE_VERSION": "a" * 40}


def test_the_identity_line_is_the_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], ENV) == 0
    assert capsys.readouterr().out == (
        f"leaveimpact {'a' * 40}: no service yet; the baseline image runs and identifies itself\n"
    )
    assert main([], {}) == 1
    assert "LEAVEIMPACT_CODE_VERSION unset" in capsys.readouterr().err
    assert main(["serve"], ENV) == 2
    assert "unknown arguments ['serve']" in capsys.readouterr().err


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
    assert lines[1:] == expected
    assert len(expected) == len(Role) * len(ASSET_NAMES)


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
