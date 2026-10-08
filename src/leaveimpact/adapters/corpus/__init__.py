"""The document corpus over PostgreSQL: the project's own fourth system, so document
search is a port like the other three. The canonical documents are sealed objects in the
world bucket; this package serves a cache of them, one world version per row set, filtered
by the corpus level a run is assigned, with full-text search over the sections. Whether
search becomes vector is the investigator milestone's decision, and this package is the one
place it changes.

``records`` holds the pure translation between table rows and domain entities, both
directions; ``adapter`` holds the reading connection, the version and level scope and the
read SQL; ``loader`` holds the loading transaction and the schema bootstrap, gated by the
import law to the adapters and the cache shell; ``schema.sql`` beside them is the
idempotent DDL. The loader is not re-exported here on purpose: a package that named it
would put it behind an import the law reads as the package.
"""

from leaveimpact.adapters.corpus.adapter import CorpusAdapter, CorpusConfig, UnservedCorpus

__all__ = ["CorpusAdapter", "CorpusConfig", "UnservedCorpus"]
