"""The prose checkpoint's file contract: kept entries come back whole, the last line for a
brief wins, no file is nothing, and a line that is not an entry refuses the file by number."""

from __future__ import annotations

from pathlib import Path

import pytest

from leaveimpact.generator.checkpoint import CheckpointUnreadable, ProseCheckpoint
from leaveimpact.world import TargetRecord
from leaveimpact.world.artifacts import digest


def record_of(target_id: str, body: str) -> TargetRecord:
    return TargetRecord(target_id, 1, (), "a" * 64, digest(body.encode("utf-8")), ())


def test_no_file_loads_as_nothing_and_kept_entries_come_back_whole(tmp_path: Path) -> None:
    checkpoint = ProseCheckpoint.under(tmp_path / "store", 7)
    assert checkpoint.path == tmp_path / "store" / "prose-checkpoints" / "seed-7.jsonl"
    assert checkpoint.load() == {}
    checkpoint.keep("One body.", record_of("clause_001", "One body."))
    checkpoint.keep(
        "Ünïcode body — kept as written.",
        record_of("clause_002", "Ünïcode body — kept as written."),
    )
    kept = checkpoint.load()
    assert set(kept) == {"clause_001", "clause_002"}
    assert kept["clause_002"].body == "Ünïcode body — kept as written."
    assert kept["clause_001"].record == record_of("clause_001", "One body.")


def test_the_last_line_for_a_brief_wins(tmp_path: Path) -> None:
    checkpoint = ProseCheckpoint(tmp_path / "seed-7.jsonl")
    checkpoint.keep("First.", record_of("clause_001", "First."))
    checkpoint.keep("Second.", record_of("clause_001", "Second."))
    assert checkpoint.load()["clause_001"].body == "Second."


def test_a_line_that_is_not_an_entry_refuses_the_file_by_line(tmp_path: Path) -> None:
    checkpoint = ProseCheckpoint(tmp_path / "seed-7.jsonl")
    checkpoint.keep("Fine.", record_of("clause_001", "Fine."))
    with checkpoint.path.open("a", encoding="utf-8") as out:
        out.write('{"target_id": "clause_002", "body": "no record"}\n')
    with pytest.raises(CheckpointUnreadable, match="line 2"):
        checkpoint.load()
