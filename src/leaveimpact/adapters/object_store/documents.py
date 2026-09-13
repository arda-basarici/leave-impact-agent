"""The sealed documents of a world, read from the world bucket: by id, and enumerated for exactness.

Under the corpus ruling of the step 12 interview the canonical documents leave the
generator as objects, one per document under the world's ``documents/`` prefix, and the
application's PostgreSQL becomes a cache the instance fills from them; so the validator
reads the documents here, where they are sealed, and never the database. What it needs
is narrower than the domain's document port: a document by id, and the enumeration of
every id held under the version — the exactness claim needs a closed set, which a
listing gives and a search never could. There is no search here on purpose: full-text
relevance is the cache's job, for the investigator, and an object store has no such
notion.

A document object that decodes but names another id than its key, or a key under the
prefix that is not a document's, is ``MalformedRecord`` with the key as locator: the
store answered, and what it holds is not this world's document. The source is the
corpus, since these bytes are what the corpus is filled from and the validator's
comparison keys evidence by source.

The reader remembers the version id of every object it read, keyed by document id, so the
sealing step can record what the manifest vouches for without a second round of reads;
the writer in ``documents_write`` adds what it created to the same map.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from leaveimpact.adapters.object_store.layout import document_id_of, document_key, documents_prefix
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.core.ports.errors import MalformedRecord
from leaveimpact.core.ports.observed import Observed
from leaveimpact.world.decoders import decode_document


class SealedDocumentReader:
    """The documents of ``version`` in ``store``; no write method exists on it."""

    def __init__(self, store: ObjectReader, version: WorldVersion) -> None:
        self._store = store
        self._version = version
        self._versions: dict[DocumentId, str] = {}

    @property
    def world_version(self) -> WorldVersion:
        return self._version

    @property
    def object_versions(self) -> Mapping[DocumentId, str]:
        """The store's version id of every document this instance read or wrote."""
        return MappingProxyType(self._versions)

    def document(self, id: DocumentId) -> Observed[Document] | None:
        key = document_key(self._version, id)
        stored = self._store.get(key)
        if stored is None:
            return None
        try:
            document = decode_document(stored.content)
        except ValueError as error:
            raise MalformedRecord(Source.CORPUS, key, str(error)) from error
        if document.id != id:
            raise MalformedRecord(
                Source.CORPUS, key, f"the object names document {document.id}, the key says {id}"
            )
        self._versions[id] = stored.version_id
        return Observed(document, Source.CORPUS)

    def held_document_ids(self) -> frozenset[DocumentId]:
        """Every document id under the version, a foreign key under the prefix refused."""
        held: set[DocumentId] = set()
        for key in self._store.list_keys(documents_prefix(self._version)):
            id = document_id_of(self._version, key)
            if id is None:
                raise MalformedRecord(Source.CORPUS, key, "not a document key under the prefix")
            held.add(id)
        return frozenset(held)
