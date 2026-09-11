"""The document corpus over PostgreSQL: the project's own fourth system, so document
search is a port like the other three. The canonical documents live in the world
bundle; this adapter projects and serves them, one world version per row set, with
full-text search over the sections. Whether search becomes vector is the investigator
milestone's decision, and this package is the one place it changes.

``records`` holds the pure translation between table rows and domain entities;
``adapter`` holds the connection, the world-version scope, the SQL and the schema
bootstrap; ``schema.sql`` beside them is the idempotent DDL.
"""

from leaveimpact.adapters.corpus.adapter import CorpusAdapter, CorpusConfig

__all__ = ["CorpusAdapter", "CorpusConfig"]
