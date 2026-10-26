"""The live attempt's names: the key's form, the one digest every server-side name derives
from with the key itself in none of them, the row's decision invariant and the
capability check by hash."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from leaveimpact.app.live import (
    Decision,
    LiveRow,
    StartKey,
    key_digest_of,
    public_id_for,
    run_id_for,
    start_key_of,
)
from leaveimpact.app.public import PublicId, public_id_of

KEY = StartKey("0123456789abcdef0123456789abcdef")
AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0123456789abcdef0123456789abcde",
        "0123456789abcdef0123456789abcdef0",
        "g" * 32,
        "A" * 32,
    ],
)
def test_a_key_is_exactly_thirty_two_lowercase_hex_digits(value: str) -> None:
    with pytest.raises(ValueError, match="32 lowercase hex digits"):
        start_key_of(value)


def test_every_server_side_name_is_of_the_digest_and_none_carries_the_key() -> None:
    """The request identity, the run id and the public id all derive from the SHA-256 of
    the key and never contain the key: the key is the capability (fork 3), so a run id in
    the log's tables or a slug in a URL that carried it would hand it to every reader."""
    digest = key_digest_of(KEY)
    assert digest == hashlib.sha256(KEY.encode()).hexdigest()
    run_id, public_id = run_id_for(digest), public_id_for(digest)
    assert run_id == f"demo-{digest}" and public_id == f"live-{digest[:32]}"
    assert KEY not in run_id and KEY not in public_id
    assert public_id_of(public_id) == public_id


def test_a_row_records_a_decision_and_its_instant_together_and_checks_a_key_by_hash() -> None:
    digest = key_digest_of(KEY)
    row = LiveRow(PublicId("live-x"), "demo-x", 1, digest, AT, None, None)
    assert row.holds(KEY) and not row.holds(StartKey("f" * 32))
    decided = LiveRow(PublicId("live-x"), "demo-x", 1, digest, AT, Decision.APPROVED, AT)
    assert decided.decision is Decision.APPROVED
    with pytest.raises(ValueError, match="recorded together"):
        LiveRow(PublicId("live-x"), "demo-x", 1, digest, AT, Decision.DECLINED, None)
    with pytest.raises(ValueError, match="recorded together"):
        LiveRow(PublicId("live-x"), "demo-x", 1, digest, AT, None, AT)
