"""The workflow files' two structural rules, read with a regex so no YAML parser becomes a
dependency for them: a job that may mint the OIDC token (``id-token: write``) uses only
actions pinned by a full commit sha, since a moved tag there is a moved trust boundary (the
deploy job's own comment); and a dispatched workflow stays under GitHub's ten-input cap."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
PINNED = re.compile(r"^\s*-?\s*uses:\s*\S+@[0-9a-f]{40}\s*(#.*)?$")
USES = re.compile(r"^\s*-?\s*uses:")


def _jobs(text: str) -> dict[str, str]:
    """Each job's block under ``jobs:``, by name, split on the two-space-indented keys."""
    _, _, body = text.partition("\njobs:\n")
    names = [m for m in re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", body, re.MULTILINE)]
    return {
        m.group(1): body[m.end() : names[i + 1].start() if i + 1 < len(names) else len(body)]
        for i, m in enumerate(names)
    }


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_a_token_minting_job_pins_every_action_by_commit(workflow: Path) -> None:
    text = workflow.read_text()
    for name, block in _jobs(text).items():
        if not re.search(r"^\s+id-token:\s*write\s*$", block, re.MULTILINE):
            continue
        unpinned = [
            line.strip()
            for line in block.splitlines()
            if USES.match(line) and not PINNED.match(line)
        ]
        assert not unpinned, (
            f"{workflow.name} job {name} uses an action not pinned by sha: {unpinned}"
        )


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_a_dispatched_workflow_stays_under_the_input_cap(workflow: Path) -> None:
    text = workflow.read_text()
    match = re.search(
        r"^  workflow_dispatch:\n    inputs:\n((?:      .*\n|\s*\n)+)", text, re.MULTILINE
    )
    if match is None:
        return
    inputs = re.findall(r"^      ([A-Za-z0-9_-]+):\s*$", match.group(1), re.MULTILINE)
    assert 0 < len(inputs) <= 10, f"{workflow.name} declares {len(inputs)} inputs"


def test_the_two_lifecycle_workflows_are_among_those_checked() -> None:
    names = {path.name for path in WORKFLOWS}
    assert {"investigate.yml", "continue-run.yml", "ci.yml"} <= names
