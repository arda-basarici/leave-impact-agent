"""The sealed documents' writer: the reader plus ``add_document``, gated by the import law.

The generator's document projector finds, verifies and adds through this class exactly as
it did through the corpus adapter: ``document`` is the find, the projector's equality the
verify, and ``add_document`` the add — a conditional put of the document's canonical
bytes at its content-addressed key, so a restart that finds the object already sealed
takes the present-and-equal path and a differing object is the frozen-bytes rule broken,
surfaced as the conflict it is. The locator a receipt records is the object key.
"""

from __future__ import annotations

from leaveimpact.adapters.object_store.documents import SealedDocumentReader
from leaveimpact.adapters.object_store.layout import document_key
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.core.entities import Document
from leaveimpact.core.ids import WorldVersion
from leaveimpact.world.artifacts import document_bytes


class SealedDocumentWriter(SealedDocumentReader):
    """``DocumentSystem`` for the generator's projector, over an ``ObjectWriter``."""

    def __init__(self, store: ObjectWriter, version: WorldVersion) -> None:
        super().__init__(store, version)
        self._writer = store

    def add_document(self, document: Document) -> str:
        """Seal ``document`` at its key once; the key is the locator."""
        key = document_key(self._version, document.id)
        receipt = self._writer.put_if_absent(key, document_bytes(document))
        self._versions[document.id] = receipt.version_id
        return key
