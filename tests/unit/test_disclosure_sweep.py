"""The structural half of the disclosure sweep: no pointer outside the tree and no
third-person narration in any tracked file (the demo milestone's exit step).

The repository is public and is read by people who have only the tree. Two of the
sweep's three predicates can be held by a test that names nothing sealed: a reference
to a record that lives outside the repository (the private stream's logs, forks files,
tickets and handoffs, a workstation path) is a pointer a reader cannot follow, and a
sentence that narrates what a named person or the assistant did is a voice the
repository's documents do not use (a ruling is stated with its date and reason, not its
speaker). The third predicate, no digest of the embargoed world, cannot be a committed
test, since the test would carry the digest; it is the evaluator's scan, run offline by
``scripts/sweep_disclosure.py`` under the administrator profile.

The scan here is over the tracked text files of the working tree, read in Python, so
the patterns can carry the one exception a model's name needs (``Claude Haiku 4.5`` is a
product; ``Claude's reading`` is narration). A file that must hold a pattern is allowed
by path with its reason, and an allowed file is still reported when a pattern other than
its reason's appears in it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]

STREAM_NOUNS = "|".join(
    (
        "subscription",
        "subscriptions",
        "bound",
        "ending",
        "closing",
        "cursor",
        "frame",
        "frames",
        "event",
        "events",
        "tick",
        "ticks",
        "bytes",
        "first",
        "last",
        "route",
        "response",
        "cost",
        "reader",
        "readers",
    )
)
"""What the narration stream of the demo owns, so "the stream's ending" is the product and
"the stream's TODO" is the private layer."""

POINTERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("the reference layer", re.compile(r"claude-context")),
    ("a stream path", re.compile(r"\bstreams[/\\]")),
    ("the handoffs folder", re.compile(r"\bhandoffs\b")),
    ("a session log", re.compile(r"SESSION_LOG|\bsession log\b", re.IGNORECASE)),
    ("a fix log", re.compile(r"FIXLOG|\bfix log\b", re.IGNORECASE)),
    ("a TODO file", re.compile(r"\bTODO\.md\b|\bthe (standing )?TODO\b")),
    ("a forks or rulings file", re.compile(r"\bm\d-(build|entry)\b|\b(forks|rulings) file")),
    ("a stream by name", re.compile(r"\b(platform|private|this) stream\b|\bplatform ticket")),
    ("a stream's possession", re.compile(rf"\bthe stream's (?!(?:{STREAM_NOUNS})\b)")),
    ("the whiteboard", re.compile(r"WHITEBOARD")),
    ("a workstation path", re.compile(r"C:\\Users|Desktop\\projects|Desktop/projects")),
    ("another project's ticket", re.compile(r"\bticket[- ][ABC5]\b")),
    ("a session number", re.compile(r"\bsession[- ]\d+\b|\(session \d+")),
)
"""What a pointer outside the tree looks like, each with the name the failure reports."""

MODEL_CONTEXTS = r"Haiku|Sonnet|Opus|\d|rows?\b|models?\b|and Nova"
"""The words after "Claude" that make it a model family and not a speaker."""

NAMES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("the author by name", re.compile(r"\bArda\b")),
    ("the assistant by name", re.compile(rf"\bClaude\b(?!['’]?s?\s+(?:{MODEL_CONTEXTS}))")),
)
"""What third-person narration looks like; the model's product names are not it."""

ALLOWED: dict[str, tuple[str, ...]] = {
    "LICENSE": ("the author by name",),
    "report/generate.py": ("the author by name",),
    ".gitignore": ("the whiteboard",),
    "tests/unit/test_disclosure_sweep.py": tuple(name for name, _ in POINTERS + NAMES),
    # A probe's recorded output, the script's docstring as it read on the day of the run;
    # a record is not rewritten after the fact.
    "probes/single-shot-query/results/selection-20261010T232446Z.md": ("a forks or rulings file",),
}
"""Files that hold a pattern for a reason: the copyright holder, the report's author
line, the ignore rule for the whiteboard, this test's own patterns, and one recorded
probe output."""

ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    "probes/captures/": ("the assistant by name", "the author by name"),
}
"""Verbatim captures: a vendor's pricing page names the model family in its own words, and
a captured job log carries the approver's login."""


def tracked_text_files() -> list[Path]:
    """Every tracked file git reads as text, as paths under the repository."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPOSITORY, check=True, capture_output=True
    ).stdout
    paths = [REPOSITORY / name for name in listing.decode("utf-8").split("\0") if name]
    return [path for path in paths if path.is_file() and _is_text(path)]


def _is_text(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\0" not in handle.read(8192)


def _allowed(relative: str) -> tuple[str, ...]:
    allowed = ALLOWED.get(relative, ())
    for prefix, names in ALLOWED_PREFIXES.items():
        if relative.startswith(prefix):
            allowed += names
    return allowed


def hits(path: Path) -> list[str]:
    """The lines of ``path`` that hold a pattern the file is not allowed, each reported
    as ``path:line: <what>``."""
    relative = path.relative_to(REPOSITORY).as_posix()
    allowed = _allowed(relative)
    found: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        for what, pattern in POINTERS + NAMES:
            if what not in allowed and pattern.search(line):
                found.append(f"{relative}:{number}: {what}")
    return found


def test_no_tracked_file_points_outside_the_tree_or_narrates_by_name() -> None:
    found = [hit for path in tracked_text_files() for hit in hits(path)]
    assert not found, "\n".join(["the sweep's structural predicates fail on:", *found])


def test_the_model_s_product_name_is_not_narration() -> None:
    _, assistant = NAMES[1]
    assert not assistant.search("one model, Claude Haiku 4.5, played every role")
    assert not assistant.search("a Claude Sonnet subagent per scenario")
    assert not assistant.search("legacy Claude 2/3 US SKUs")
    assert not assistant.search("All three Claude rows BLOCKED")
    assert not assistant.search("the current Claude and Nova model in Frankfurt")
    assert assistant.search("Claude's arithmetic said otherwise")
    assert assistant.search("Claude identified the gap")


def test_the_narration_stream_s_own_nouns_are_not_a_pointer() -> None:
    possession = dict(POINTERS)["a stream's possession"]
    assert not possession.search("the stream's ending is the closing frame")
    assert not possession.search("the stream's subscription bound")
    assert possession.search("carried in the stream's FIXLOG")
    assert possession.search("the stream's access note")


def test_a_jira_ticket_comment_is_not_another_project_s_ticket() -> None:
    ticket = dict(POINTERS)["another project's ticket"]
    assert not ticket.search("the ticket-comment register")
    assert not ticket.search("a ticket comment")
    assert ticket.search("the platform's ticket B landed")
    assert ticket.search("ticket 5 (Access)")
