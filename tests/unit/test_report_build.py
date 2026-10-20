"""The report builds from its committed chapters with every pin resolved, and refuses a
chapter that names a pin or a figure the build cannot find, by chapter name."""

from __future__ import annotations

from pathlib import Path

import pytest

from report.generate import CHAPTERS, FIGURES, REPOSITORY, build
from report.pins import load_pins


def test_the_committed_chapters_build_to_a_pdf_with_every_pin_resolved(tmp_path: Path) -> None:
    output = tmp_path / "report.pdf"
    report = build(CHAPTERS, FIGURES, output, load_pins(REPOSITORY))
    assert report.output == output and output.read_bytes().startswith(b"%PDF")
    assert report.chapters[0] == "00-front-matter.md"


def test_an_unknown_pin_refuses_with_the_chapter_named(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01-a.md").write_text("# A\n\nIt was {{pin:nope}}.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="01-a.md: unknown pin 'nope'"):
        build(chapters, tmp_path, tmp_path / "out.pdf", {})


def test_a_missing_figure_refuses_with_the_chapter_named(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01-a.md").write_text("# A\n\n![Caption.](absent.png)\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="01-a.md: figure absent.png"):
        build(chapters, tmp_path, tmp_path / "out.pdf", {})


def test_an_empty_chapters_directory_refuses(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no chapters under"):
        build(tmp_path, tmp_path, tmp_path / "out.pdf", {})
