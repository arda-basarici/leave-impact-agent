"""The byte primitive under every local artifact: absent is distinct from empty, a replacement
is whole or not at all with no temporary left behind, a stale temporary from an interrupted
attempt is overwritten rather than adopted — and the persistence protocol in order, the
temporary synced before the rename and the directory synced after it where the platform can,
a failing directory sync raising rather than reporting a barrier that did not complete."""

import os
import stat
from pathlib import Path

import pytest

from leaveimpact.adapters import filestore
from leaveimpact.adapters.filestore import SYNCS_DIRECTORIES, read_if_present, replace_atomically


def test_absent_is_none_and_empty_is_empty(tmp_path: Path) -> None:
    target = tmp_path / "artifact.json"
    assert read_if_present(target) is None
    replace_atomically(target, b"")
    assert read_if_present(target) == b""


def test_a_replacement_is_whole_and_leaves_no_temporary(tmp_path: Path) -> None:
    target = tmp_path / "artifact.json"
    replace_atomically(target, b'{"stage":"preparing"}')
    replace_atomically(target, b'{"stage":"projected"}')
    assert read_if_present(target) == b'{"stage":"projected"}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["artifact.json"]


def test_a_stale_temporary_is_overwritten_not_adopted(tmp_path: Path) -> None:
    target = tmp_path / "artifact.json"
    replace_atomically(target, b"first")
    (tmp_path / "artifact.json.tmp").write_bytes(b"half-written by a dead process")
    assert read_if_present(target) == b"first", "the target is untouched by the debris"
    replace_atomically(target, b"second")
    assert read_if_present(target) == b"second"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["artifact.json"]


def test_the_persistence_protocol_runs_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The protocol, not a power loss: the temporary's contents reach the device before the
    # rename makes them visible, and the directory entry reaches the device after, where
    # the platform can sync one.
    target = tmp_path / "artifact.json"
    events: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def recording_fsync(descriptor: int) -> None:
        events.append("sync-directory" if _is_directory(descriptor) else "sync-file")
        real_fsync(descriptor)

    def recording_replace(source: Path, destination: Path) -> None:
        events.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(filestore.os, "fsync", recording_fsync)
    monkeypatch.setattr(filestore.os, "replace", recording_replace)
    replace_atomically(target, b"content")
    expected = ["sync-file", "replace"] + (["sync-directory"] if SYNCS_DIRECTORIES else [])
    assert events == expected


@pytest.mark.skipif(not SYNCS_DIRECTORIES, reason="the durability barrier exists on POSIX only")
def test_a_failing_directory_sync_raises_rather_than_claiming_the_barrier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "artifact.json"
    real_fsync = os.fsync

    def failing_directory_sync(descriptor: int) -> None:
        if _is_directory(descriptor):
            raise OSError("the device went away")
        real_fsync(descriptor)

    monkeypatch.setattr(filestore.os, "fsync", failing_directory_sync)
    with pytest.raises(OSError, match="the device went away"):
        replace_atomically(target, b"content")
    # The rename may already be visible; what is refused is the claim of durability.
    assert read_if_present(target) == b"content"


def _is_directory(descriptor: int) -> bool:
    return stat.S_ISDIR(os.fstat(descriptor).st_mode)
