"""A private checkpoint of the prose stage: the bodies a seed's briefs were accepted with,
kept as each passes, so a rerun of the same seed pays only for the briefs that have not.

The stage keeps nothing until every brief is accepted, on purpose: a world is sealed whole
or not at all. The second development world's first full draw (seed 103, 2026-10-14)
accepted 1,732 of 1,740 briefs, failed on eight, and the rerun would have paid for the
whole pool again, about $5 and half an hour of calls. This file is the middle ground, and
it lives beside a local store root and nowhere else: a development world is generated
locally, the measurement world by a job whose root is a bucket and whose log is public, and
a body must reach neither.

One JSON line per accepted brief, appended under a lock as the brief passes, so an abort or
a failed stage keeps every acceptance before it; loaded whole at the start of a run, the
last line for a brief winning. Whether an entry is reused is the materializer's call, on
its own terms: the same request digest, so the brief, the lexicon's rendering and the
prompt assets are what they were; the body's digest the recorded one; and the free guards
passing on the body again, since a guard may have changed between the runs (the
exact-spelling rule is why seed 103 ran twice). The record kept beside a body is the one
its acceptance made, attempts and refusals included, so the sealed provenance of a reused
body is the provenance of the run that wrote it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from leaveimpact.core.jsonshape import JsonObject, as_object, expect_fields, string_field
from leaveimpact.world import TargetRecord, encode_target_record
from leaveimpact.world.truth_decoder import decode_target_record

__all__ = ["CheckpointUnreadable", "Checkpointed", "ProseCheckpoint"]


@dataclass(frozen=True, slots=True)
class Checkpointed:
    """One accepted body with the record its acceptance made."""

    body: str
    record: TargetRecord


class CheckpointUnreadable(Exception):
    """A line of the checkpoint is not an entry; the file is refused whole, by line."""

    def __init__(self, path: Path, line: int) -> None:
        super().__init__(f"the prose checkpoint {path} is not readable at line {line}")
        self.path = path
        self.line = line


class ProseCheckpoint:
    """One seed's file of accepted bodies, JSON lines under a local store root."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    @classmethod
    def under(cls, root: Path, seed: int) -> ProseCheckpoint:
        """The checkpoint of ``seed`` beside the root's ``truth`` and ``world`` stores."""
        return cls(root / "prose-checkpoints" / f"seed-{seed}.jsonl")

    def load(self) -> dict[str, Checkpointed]:
        """Every kept brief by target id, the last line for an id winning; nothing for no file.
        A line that is not an entry refuses the whole file by its number, since a checkpoint
        that cannot be read whole is not one to trust in part."""
        if not self.path.exists():
            return {}
        kept: dict[str, Checkpointed] = {}
        with self.path.open(encoding="utf-8") as lines:
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    entry = as_object(json.loads(line), "a checkpoint entry")
                    expect_fields(entry, ("target_id", "body", "record"), "a checkpoint entry")
                    record = decode_target_record(entry["record"])
                    kept[string_field(entry, "target_id")] = Checkpointed(
                        string_field(entry, "body"), record
                    )
                except (ValueError, TypeError, KeyError) as error:
                    raise CheckpointUnreadable(self.path, number) from error
        return kept

    def keep(self, body: str, record: TargetRecord) -> None:
        """Appends one accepted body with its record, creating the file on the first."""
        line: JsonObject = {
            "target_id": record.target_id,
            "body": body,
            "record": encode_target_record(record),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
