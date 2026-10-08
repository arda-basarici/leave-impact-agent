"""The corpus reader an attempt reads through, built from what the attempt was admitted with.

The served world version and the corpus level are the run's configuration (the cache step's
ruling, forwarded to the registry step): the cache loads every admitted version and chooses
nothing, the adapter takes the level as its own argument, and neither value comes from a model
argument or a newest-version lookup. Both are frozen inputs of the admission, so this is the
one place that turns them into the reader, and it runs the adapter's serving check before
handing it over: a version the cache does not serve or a level the world never sealed fails
the attempt here, before any read is made, rather than at the first search (fork 7). The
composition root that calls it is the graph step's.
"""

from __future__ import annotations

from leaveimpact.adapters.corpus.adapter import Connect, CorpusAdapter, CorpusConfig
from leaveimpact.agent.log_events import FrozenInputs


def corpus_reader_for(
    inputs: FrozenInputs, *, dsn: str, connect: Connect | None = None
) -> CorpusAdapter:
    """The reader over the admitted world version at the admitted level, its serving check
    passed; ``UnservedCorpus`` when the cache serves no such level of that version."""
    config = CorpusConfig(inputs.context.world_version)
    level = inputs.corpus_level
    adapter = (
        CorpusAdapter(dsn=dsn, config=config, level=level)
        if connect is None
        else CorpusAdapter(dsn=dsn, config=config, level=level, connect=connect)
    )
    try:
        adapter.serving_check()
    except Exception:
        # The check opened the connection; a refusal here hands the caller no adapter to
        # close, so the connection is closed before the refusal leaves (the close's review).
        adapter.close()
        raise
    return adapter
