"""The role mapping the ending view and the narration word an authority through: the three
roles, and the module's two spellings held to the producers they name, the sweeper's
constant and the launcher's admitter line, so a renamed producer fails here and never
silently reads as an operator."""

from __future__ import annotations

import re
from pathlib import Path

from leaveimpact.app.roles import SWEEPER_IDENTITY, WORKFLOW_PREFIX, role_of
from leaveimpact.app.sweeper import DEMO_SWEEPER

INVESTIGATE = Path(__file__).resolve().parents[2] / "deploy" / "runner" / "investigate.sh"


def test_the_three_roles() -> None:
    assert role_of("demo-sweeper") == "the demo's sweeper"
    assert role_of("workflow:investigate") == "the operator's workflow"
    assert role_of("operator") == "an operator"
    assert role_of("arda") == "an operator", "any other identity is an operator's"


def test_the_sweeper_spelling_is_the_sweepers_own_constant() -> None:
    assert DEMO_SWEEPER.identity == SWEEPER_IDENTITY


def test_the_workflow_prefix_is_the_launchers_admitter() -> None:
    script = INVESTIGATE.read_text(encoding="utf-8")
    found = re.search(r'^ADMITTER="([^"]+)"$', script, re.MULTILINE)
    assert found is not None, "the launcher declares its admitter on one line"
    assert found.group(1).startswith(WORKFLOW_PREFIX)
    assert role_of(found.group(1)) == "the operator's workflow"
