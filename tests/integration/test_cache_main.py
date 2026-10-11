"""The cache job end to end: a development world sealed to a local twin, the entry point run
over it against the real PostgreSQL, the documents read back through the adapter.

What the generator's unprojected sealing leaves under a root is what the instance's job
reads under a bucket, key for key, so the laptop path is the production path with the
store swapped (the M2 step 9 design, the loader run locally over a development world).
The test holds the whole chain: the job admits the manifest-less world as a development
world, loads its documents and its levels object, reports the version, exits zero; a
second run finds it ready; the adapter at the base level reads every sealed document; and
a configuration the job cannot start from exits 2 before any store is touched. A version
the rule stops serving between two runs is demoted, so the adapter's serving check refuses
it, and readmitted when the rule serves it again (the first live run's step, fork 11).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig, UnservedCorpus
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.cache.__main__ import main
from leaveimpact.generator.projection import world_entities
from leaveimpact.generator.sealing import seal_unprojected
from leaveimpact.world import DEFAULT_PARAMS, assemble_world, bundle
from tests.integration.corpus_support import database_url, drop_world

pytestmark = pytest.mark.integration


@pytest.fixture
def url() -> str:
    return database_url()


@pytest.fixture
def development_root(tmp_path: Path, url: str) -> Iterator[tuple[Path, str]]:
    world = assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))
    sealed = bundle(world)
    root = tmp_path / "store"
    seal_unprojected(
        world, sealed, LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    )
    try:
        yield root, sealed.world_version
    finally:
        drop_world(url, sealed.world_version)


def test_the_job_loads_a_sealed_development_world_and_the_adapter_reads_it_back(
    development_root: tuple[Path, str], url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    root, version = development_root
    env = {"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(root), "DATABASE_URL": url}
    assert main(env=env) == 0
    lines = capsys.readouterr().out.splitlines()
    sealed_documents = world_entities(assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))).documents
    assert lines[0] == f"store=local:{root}"
    assert lines[1] == (
        f"loaded={version} projection=unprojected documents={len(sealed_documents)} levels=base"
    )
    assert lines[-1].startswith("loaded=1 already_ready=0 readmitted=0 declined=0 demoted=0")

    assert main(env=env) == 0
    assert f"already_ready={version} " in capsys.readouterr().out

    adapter = CorpusAdapter(dsn=url, config=CorpusConfig(version))  # type: ignore[arg-type]
    try:
        assert adapter.held_document_ids() == {document.id for document in sealed_documents}
        for document in sealed_documents:
            found = adapter.document(document.id)
            assert found is not None and found.value == document
    finally:
        adapter.close()


def test_a_version_the_rule_stops_serving_is_demoted_and_readmitted_when_served_again(
    development_root: tuple[Path, str], url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The levels object is what admits a development world; with it gone the rule declines
    the version the first run loaded, the second run flips it not ready and the adapter's
    serving check refuses it; with it back the third run readmits it and the adapter reads."""
    root, version = development_root
    env = {"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(root), "DATABASE_URL": url}
    assert main(env=env) == 0
    capsys.readouterr()
    levels = root / "world" / layout.levels_key(version)  # type: ignore[arg-type]
    held = levels.read_bytes()
    levels.unlink()
    assert main(env=env) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith(f"declined={version} reason=no levels object")
    assert any(line.startswith(f"demoted={version} reason=no levels object") for line in lines)
    assert lines[-1].startswith("loaded=0 already_ready=0 readmitted=0 declined=1 demoted=1")
    adapter = CorpusAdapter(dsn=url, config=CorpusConfig(version), level="base")  # type: ignore[arg-type]
    try:
        with pytest.raises(UnservedCorpus):
            adapter.serving_check()
    finally:
        adapter.close()
    levels.write_bytes(held)
    assert main(env=env) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith(f"readmitted={version} projection=unprojected ")
    assert lines[-1].startswith("loaded=0 already_ready=0 readmitted=1 declined=0 demoted=0")
    adapter = CorpusAdapter(dsn=url, config=CorpusConfig(version), level="base")  # type: ignore[arg-type]
    try:
        assert adapter.serving_check() == 0
    finally:
        adapter.close()


def test_a_configuration_the_job_cannot_start_from_exits_two(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert main(env={"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(tmp_path)}) == 2
    assert "DATABASE_URL is not set" in capsys.readouterr().err
    assert main(env={"DATABASE_URL": "postgresql://x@localhost/x"}) == 2
    assert "WORLD_BUCKET is not set" in capsys.readouterr().err
