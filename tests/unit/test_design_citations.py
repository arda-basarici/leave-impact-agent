"""Every quoted citation of a DESIGN passage names a passage DESIGN still holds.

Docstrings and documents across the tree point a reader at DESIGN by the title of a
section or by the name a decision's paragraph opens with: ``(DESIGN, "Truth before
prose")``. Nothing reads those pointers but a person, so a title that a rewrite removed
leaves its citations standing, and it has: two in ARCHITECTURE stood seven weeks, and
more in module docstrings were found only when the citations were first enumerated. A
cited title is a string DESIGN either holds or does not, which a test can ask of every
tracked file.

What is held: the quoted forms. ``DESIGN, "X"``, ``DESIGN's "X"``, a short lower-case
lead-in between the two (``DESIGN, the closed-world rule in "X"``), and a further
``and "Y"`` after any of them. A citation resolves when its words are a title's words, or
at least three of them in a row inside one title, so a long decision name may be cited by
its opening clause. The titles are DESIGN's section and subsection headings and every
phrase it sets in bold. Quotation marks, backticks and case are ignored on both sides,
since a title that quotes a word cannot be quoted whole inside a docstring's own quotes.

What is not held: a reference with no quoted title ("the import law in DESIGN"), which no
pattern can tell from prose, and whether the cited passage still says what the citing
sentence claims of it. The append-only records are not scanned, because a citation in a
dated entry was true on its date.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]

DESIGN_DOCUMENTS: tuple[str, ...] = ("DESIGN.md",)
"""The documents a citation of DESIGN may resolve in."""

UNSCANNED: dict[str, str] = {
    "DESIGN.md": "the cited document itself",
    "REPORT_NOTES.md": "append-only, each entry true on its date",
    "probes/FINDINGS.md": "append-only, each entry true on its date",
    "VISION.md": "the founding snapshot, frozen before DESIGN had sections",
    "tests/unit/test_design_citations.py": "this test's own cases",
}
"""Tracked files whose citations are not held, each with its reason."""

CITATION = re.compile(
    r"DESIGN(?:\.md)?(?:'s|,)?\s+"
    r"(?:[a-z][\w-]*\s+){0,6}"
    r'"(?P<first>[^"]+)"'
    r'(?P<more>(?:\s+and\s+"[^"]+")*)'
)
"""A quoted citation: the document's name, an optional short lead-in, the quoted title,
and any further titles joined to it by "and"."""

COMMENT_LEADER = re.compile(r"^\s*(?:#+|//|>)\s?")
"""What a wrapped comment or quotation puts at the start of a continuation line, removed
so a title that wraps inside one is read whole."""

MARKS = re.compile(r"[\"“”'’`*]")
"""Characters a title and its citation may differ in."""

FEWEST_WORDS_OF_A_PART = 3
"""A citation shorter than a whole title must be at least this many words of it."""


def words(text: str) -> tuple[str, ...]:
    """The words of ``text`` as a citation and a title are compared: lower-case, without
    quotation marks, backticks or punctuation."""
    return tuple(re.findall(r"[\w-]+", MARKS.sub("", text.lower())))


def titles(document: str) -> frozenset[tuple[str, ...]]:
    """What ``document`` offers to be cited by: its second and third level headings and
    every phrase it sets in bold, each as its words."""
    headings: list[str] = re.findall(r"^#{2,3} +(.+?)\s*$", document, flags=re.MULTILINE)
    bold: list[str] = re.findall(r"\*\*(.+?)\*\*", " ".join(document.split()))
    return frozenset(words(title) for title in (*headings, *bold) if words(title))


def citations(text: str) -> list[str]:
    """The titles ``text`` cites DESIGN by, in the order written, read across line wraps."""
    flat = " ".join(" ".join(COMMENT_LEADER.sub("", line) for line in text.splitlines()).split())
    found: list[str] = []
    for match in CITATION.finditer(flat):
        found.append(match.group("first"))
        found.extend(re.findall(r'"([^"]+)"', match.group("more")))
    return found


def resolves(citation: str, known: frozenset[tuple[str, ...]]) -> bool:
    """Whether ``citation`` is one of the ``known`` titles, or a run of at least three
    words inside one."""
    cited = words(citation)
    if cited in known:
        return True
    if len(cited) < FEWEST_WORDS_OF_A_PART:
        return False
    return any(_holds(title, cited) for title in known)


def _holds(title: tuple[str, ...], run: tuple[str, ...]) -> bool:
    length = len(run)
    return any(title[start : start + length] == run for start in range(len(title) - length + 1))


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


def design_titles() -> frozenset[tuple[str, ...]]:
    """The titles of every document a citation of DESIGN may resolve in."""
    known: frozenset[tuple[str, ...]] = frozenset()
    for name in DESIGN_DOCUMENTS:
        known |= titles((REPOSITORY / name).read_text(encoding="utf-8"))
    return known


def test_every_quoted_citation_of_design_names_a_passage_design_holds() -> None:
    known = design_titles()
    unresolved: list[str] = []
    for path in tracked_text_files():
        relative = path.relative_to(REPOSITORY).as_posix()
        if relative in UNSCANNED:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        unresolved.extend(
            f'{relative}: "{citation}"'
            for citation in citations(text)
            if not resolves(citation, known)
        )
    assert not unresolved, "\n".join(
        ["DESIGN holds no passage by the title cited in:", *unresolved]
    )


def test_the_gate_finds_citations_to_hold() -> None:
    # A pattern that matched nothing would pass every tree; the tree cites DESIGN by
    # section title from many modules, so a count far below that is a broken pattern.
    found = [
        citation
        for path in tracked_text_files()
        if path.relative_to(REPOSITORY).as_posix() not in UNSCANNED
        for citation in citations(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert len(found) >= 40


def test_a_citation_is_read_in_each_form_it_is_written_in() -> None:
    assert citations('one vocabulary (DESIGN, "What a valid answer is").') == [
        "What a valid answer is"
    ]
    assert citations('laid out along DESIGN\'s "Ranks give the default" and') == [
        "Ranks give the default"
    ]
    assert citations('(DESIGN, the closed-world rule in "Absence is a record of its own")') == [
        "Absence is a record of its own"
    ]
    assert citations('(DESIGN, "Truth before prose" and "Verification")') == [
        "Truth before prose",
        "Verification",
    ]
    assert citations('see DESIGN.md, "Sealing and the audit"') == ["Sealing and the audit"]


def test_a_citation_is_read_across_a_wrapped_comment() -> None:
    wrapped = '# the subnet row (DESIGN, "The application\n# host") is a constant'
    assert citations(wrapped) == ["The application host"]
    quoted = '> as DESIGN, "Time is world\n> state" rules'
    assert citations(quoted) == ["Time is world state"]


def test_prose_about_design_is_not_a_citation() -> None:
    assert citations("the import law in DESIGN says why") == []
    assert citations('DESIGN is the living record; "golden" is defined elsewhere') == []


def test_a_citation_resolves_as_a_title_or_as_three_words_in_a_row_of_one() -> None:
    known = titles(
        "## Truth before prose\n\n"
        "**Time is world state, never the machine's clock.** A run reads `now`.\n\n"
        '**Two audit depths make "golden" an honest\nword.** Every scenario is read.\n'
    )
    assert resolves("Truth before prose", known)
    assert resolves("Time is world state", known)
    assert resolves("never the machine's clock", known)
    assert resolves("Two audit depths make golden an honest word", known)
    assert not resolves("world state", known)
    assert not resolves("Time is machine state", known)
    assert not resolves("The answer-key contract", known)


def test_titles_are_the_headings_and_the_bold_phrases() -> None:
    known = titles("# DESIGN\n\n## A section\n\n### A decision, named\n\nProse with **a term**.\n")
    assert known == {("a", "section"), ("a", "decision", "named"), ("a", "term")}
