"""The byte primitive under every local artifact: absent is distinct from empty, a replacement
is whole or not at all with no temporary left behind, and a stale temporary from an interrupted
attempt is overwritten rather than adopted."""

from pathlib import Path

from leaveimpact.adapters.filestore import read_if_present, replace_atomically


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
