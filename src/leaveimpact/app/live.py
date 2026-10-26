"""The live attempt's names and row, pure: what a public start derives from the key the
browser holds, and what the app-owned table of live attempts records about it.

A public start arrives with one secret, a 128-bit key the index page minted into its
form (the live-path commands step, forks 2 and 3): the browser sends it on every submit of
that form and holds it afterwards as the attempt's capability. Nothing on the server
keeps the key itself. Its SHA-256 is the one name the server works with: the request
identity the log records the admission under, so a repeat under the same key is answered
as recorded; the run id, ``demo-`` and the digest, so a repeat rebuilds the same frozen
inputs and the log answers by identity with no lookup table on the app side; the public
id, ``live-`` and the digest's first thirty-two hex digits, the slug the replay page is
addressed by; and the live row's ``key_digest``, which the decision route compares with
the hash of the key its cookie carries. Fork 2 derived the run id from the key in plain;
fork 3 then made the key the credential, and a run id in the log's tables and the export
that carried the secret would have handed it to every reader of those; so every derived
name is of the digest and the key stays in the browser.

``LiveDraft`` is what the start asks the store to write beside the publishable row;
``LiveRow`` the row as the store reads it back, the decision columns written later by
the decision command and ``None`` until then. The deadline is not a column: it derives
from the ``ApprovalRequested`` event's instant and the configured wait, read off the fold
under the row's lock (fork 4), so the log stays the authority and every column here is a
cache repaired under that lock.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from leaveimpact.app.public import PublicId, public_id_of
from leaveimpact.core.run_trace import require_digest

StartKey = NewType("StartKey", str)
"""The browser's key: thirty-two lowercase hex digits, made by ``start_key_of``."""

KEY_HEX_DIGITS = 32
_KEY = re.compile(rf"^[0-9a-f]{{{KEY_HEX_DIGITS}}}$")
PUBLIC_ID_DIGITS = 32
"""How much of the digest the public id carries: a hundred and twenty-eight bits, so two
keys never share a slug in practice and the table's primary key is what proves it."""


def start_key_of(value: str) -> StartKey:
    """``value`` as a start key; ``ValueError`` naming the rule otherwise.

    >>> start_key_of("0123456789abcdef0123456789abcdef")
    '0123456789abcdef0123456789abcdef'
    >>> start_key_of("0123456789ABCDEF0123456789abcdef")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: a start key is 32 lowercase hex digits, got '0123456789ABCDEF...'
    """
    if not _KEY.match(value):
        raise ValueError(f"a start key is {KEY_HEX_DIGITS} lowercase hex digits, got {value!r}")
    return StartKey(value)


def key_digest_of(key: StartKey) -> str:
    """The SHA-256 of the key's text, in hex: the request identity, the capability's hash
    and the root of every derived name.

    >>> key_digest_of(StartKey("0" * 32))[:16]
    '84e0c0eafaa95a34'
    """
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def run_id_for(key_digest: str) -> str:
    """The run a start under the key asks for: ``demo-`` and the whole digest.

    >>> run_id_for("f" * 64)
    'demo-ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    """
    require_digest(key_digest, "a key digest")
    return f"demo-{key_digest}"


def public_id_for(key_digest: str) -> PublicId:
    """The slug the attempt's replay is addressed by: ``live-`` and the digest's first
    thirty-two hex digits, a public id by the slug rule.

    >>> public_id_for("f" * 64)
    'live-ffffffffffffffffffffffffffffffff'
    """
    require_digest(key_digest, "a key digest")
    return public_id_of(f"live-{key_digest[:PUBLIC_ID_DIGITS]}")


class Decision(StrEnum):
    """The decision the row records, as the log holds it."""

    APPROVED = "approved"
    DECLINED = "declined"


@dataclass(frozen=True, slots=True)
class LiveDraft:
    """What the start asks the store to write: the row without its decision, which the
    decision command records later. ``started_at`` is the log's instant of the admission,
    so the row and the admission event carry one timestamp."""

    public_id: PublicId
    run_id: str
    attempt: int
    key_digest: str
    started_at: datetime

    def __post_init__(self) -> None:
        require_digest(self.key_digest, "the key digest")


@dataclass(frozen=True, slots=True)
class LiveRow:
    """One row of the live table as the store reads it back; the decision and its instant
    are ``None`` together until a decision is recorded."""

    public_id: PublicId
    run_id: str
    attempt: int
    key_digest: str
    started_at: datetime
    decision: Decision | None
    decided_at: datetime | None

    def __post_init__(self) -> None:
        if (self.decision is None) != (self.decided_at is None):
            raise ValueError("a decision and its instant are recorded together")

    def holds(self, key: StartKey) -> bool:
        """Whether ``key`` is the capability this row was started under: the decision
        route's check, a hash comparison and nothing stored in plain."""
        return key_digest_of(key) == self.key_digest


__all__ = [
    "Decision",
    "LiveDraft",
    "LiveRow",
    "StartKey",
    "key_digest_of",
    "public_id_for",
    "run_id_for",
    "start_key_of",
]
