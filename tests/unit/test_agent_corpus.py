"""The corpus reader is built from the admitted version and level alone, its serving check run
before it is handed over: an unserved level fails before any read, a served one yields the
adapter scoped exactly as admitted."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from leaveimpact.adapters.corpus import UnservedCorpus
from leaveimpact.agent.corpus import corpus_reader_for
from tests.unit import log_histories as histories
from tests.unit.test_corpus_adapter import Serving, Unserving


def test_the_reader_is_scoped_to_the_admitted_version_and_level_after_its_check() -> None:
    inputs = replace(histories.inputs(reservation=1_000_000), corpus_level="padded")
    made: Any = Serving(filler_count=7)
    reader = corpus_reader_for(
        inputs, dsn="postgresql://nobody@localhost/none", connect=lambda dsn: made
    )
    assert reader.config.world_version == inputs.context.world_version
    assert reader.level == "padded"
    assert len(made.statements) == 1 and "FROM level JOIN world" in made.statements[0]


def test_an_unserved_level_fails_before_any_read() -> None:
    inputs = histories.inputs(reservation=1_000_000)
    unserved: Any = Unserving()
    with pytest.raises(UnservedCorpus) as refused:
        corpus_reader_for(
            inputs, dsn="postgresql://nobody@localhost/none", connect=lambda dsn: unserved
        )
    assert refused.value.world_version == inputs.context.world_version
    assert refused.value.level == "base"
