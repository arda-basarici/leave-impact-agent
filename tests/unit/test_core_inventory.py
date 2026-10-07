"""The inventory codec: a full inventory with an open attempt, a failed and abandoned one and a
published one round-trips to an equal tree and to the same bytes, its identity is the digest
of those bytes, a failure's reason text never enters it, and a wrong format, a surplus
field, a publication on an open attempt, attempts out of order and a ledger that is not the
scope's all refuse naming what was wrong."""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import (
    INVENTORY_FORMAT_VERSION,
    AttemptEnding,
    AttemptStatus,
    Inventory,
    InventoryAttempt,
    InventoryLedger,
    InventoryLedgerEntry,
    InventoryScope,
    InventorySnapshot,
    PublicationObserved,
    PublicationStatus,
    RefusedAdmission,
    SupersededObject,
    decode_inventory,
    decode_inventory_bytes,
    encode_inventory,
    inventory_bytes,
    inventory_digest,
)
from leaveimpact.core.run_account import AccountFigures
from leaveimpact.core.run_ending import (
    Abandonment,
    AbandonmentReason,
    ApprovalState,
    HarnessSite,
    HarnessSiteName,
    SegmentStatus,
)
from leaveimpact.core.run_record import FailureCategory, TerminalStatus

VERSION = WorldVersion("ab" * 32)
COMMIT = "c" * 40
BUILDER = "d" * 40
READER = "e" * 40
DIGEST = "f" * 64
AT = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
SCOPE = InventoryScope(VERSION, COMMIT, "ledger-1")
SNAPSHOT = InventorySnapshot(2, BUILDER, AT)
FIGURES = AccountFigures(297_000_000, 17_457_000_000, 17_754_000_000)


def entry(
    revision: int, kind: str, amount: int, total: int, **fields: object
) -> InventoryLedgerEntry:
    run = fields.get("run_id")
    return InventoryLedgerEntry(
        revision,
        kind,
        None if run is None else str(run),
        None if run is None else 1,
        amount,
        total,
        str(fields["authority"]) if "authority" in fields else None,
        COMMIT if "authority" in fields else None,
        str(fields["reason"]) if "reason" in fields else None,
        AT,
    )


LEDGER = InventoryLedger(
    "ledger-1",
    17_754_000_000,
    3,
    50_000_000_000,
    (
        entry(1, "threshold_set", 50_000_000_000, 0, authority="operator:test"),
        entry(2, "admitted", 20_000_000_000, 20_000_000_000, run_id="run-a"),
        entry(3, "settled", 17_754_000_000, 17_754_000_000, run_id="run-a"),
    ),
)
OPEN = AttemptStatus(None, SegmentStatus.OPEN, ApprovalState.NOT_REQUESTED)
FAILED = AttemptStatus(
    AttemptEnding(
        TerminalStatus.FAILED,
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        Abandonment("operator:test", 2, AbandonmentReason.INTERRUPTED),
    ),
    SegmentStatus.STOPPED,
    ApprovalState.NOT_REQUESTED,
)
COMPLETED = AttemptStatus(
    AttemptEnding(TerminalStatus.COMPLETED, None, None, None),
    SegmentStatus.STOPPED,
    ApprovalState.APPROVED,
)
PUBLISHED = PublicationObserved(
    PublicationStatus.PUBLISHED,
    READER,
    3,
    DIGEST,
    f"runs/{VERSION}/run-b-1/export-{READER}.json",
    DIGEST,
    None,
    None,
    AT,
)
INVENTORY = Inventory(
    INVENTORY_FORMAT_VERSION,
    SCOPE,
    SNAPSHOT,
    LEDGER,
    (
        InventoryAttempt(
            "run-a", 1, VERSION, COMMIT, "ledger-1", True, FAILED, 7, DIGEST, FIGURES, None, ()
        ),
        InventoryAttempt(
            "run-a", 2, VERSION, COMMIT, "ledger-1", False, OPEN, 3, DIGEST, FIGURES, None, ()
        ),
        InventoryAttempt(
            "run-b",
            1,
            VERSION,
            COMMIT,
            None,
            True,
            COMPLETED,
            40,
            DIGEST,
            AccountFigures(0, 0, 0),
            PUBLISHED,
            (
                SupersededObject(
                    "9" * 40, f"runs/{VERSION}/run-b-1/export-{'9' * 40}.json", DIGEST, AT
                ),
            ),
        ),
    ),
    (RefusedAdmission("req-9", "run-c", 1, "the ledger has no room for 20000000000", AT),),
)
FOREIGN = InventoryAttempt(
    "run-z", 1, VERSION, "9" * 40, None, False, None, 2, DIGEST, None, None, ()
)
"""An attempt admitted under another registration: the row's closed value and nothing folded."""


def test_a_full_inventory_round_trips_to_an_equal_tree_and_the_same_bytes() -> None:
    content = inventory_bytes(INVENTORY)
    assert decode_inventory_bytes(content) == INVENTORY
    assert inventory_bytes(decode_inventory_bytes(content)) == content
    assert inventory_digest(content) == inventory_digest(inventory_bytes(INVENTORY))


def test_the_identity_is_the_digest_of_the_bytes_and_changes_with_the_content() -> None:
    content = inventory_bytes(INVENTORY)
    other = Inventory(
        INVENTORY_FORMAT_VERSION, SCOPE, SNAPSHOT, LEDGER, INVENTORY.attempts[:2], INVENTORY.refused
    )
    assert len(inventory_digest(content)) == 64
    assert inventory_digest(content) != inventory_digest(inventory_bytes(other))


def test_a_failure_carries_its_category_and_site_and_no_reason_text() -> None:
    ending = _nested(_attempt(_thawed(encode_inventory(INVENTORY)), 0), "status", "ending")
    assert set(ending) == {"status", "failure_category", "failure_site", "abandonment"}
    assert ending["failure_site"] == {"kind": "harness", "site": "abandoned"}


def test_an_attempt_the_builder_could_not_fold_carries_its_row_and_no_status() -> None:
    listed = Inventory(
        INVENTORY_FORMAT_VERSION, SCOPE, SNAPSHOT, LEDGER, (*INVENTORY.attempts, FOREIGN), ()
    )
    tree = encode_inventory(listed)
    attempts = tree["attempts"]
    assert isinstance(attempts, list)
    assert attempts[3]["status"] is None and attempts[3]["figures"] is None
    assert attempts[3]["closed"] is False
    assert decode_inventory(tree) == listed


def test_a_superseded_object_is_carried_with_its_reader_and_digest() -> None:
    tree = _thawed(encode_inventory(INVENTORY))
    listed = cast(list[Tree], _attempt(tree, 2)["superseded"])
    assert len(listed) == 1
    assert listed[0]["reader_commit"] == "9" * 40 and listed[0]["object_digest"] == DIGEST
    assert _attempt(tree, 0)["superseded"] == []


def test_attempt_of_finds_a_listed_attempt_and_none_otherwise() -> None:
    assert INVENTORY.attempt_of("run-a", 2) is INVENTORY.attempts[1]
    assert INVENTORY.attempt_of("run-a", 3) is None


def test_absent_and_empty_stay_distinct_through_the_codec() -> None:
    bare = Inventory(INVENTORY_FORMAT_VERSION, SCOPE, SNAPSHOT, None, (), ())
    tree = encode_inventory(bare)
    assert tree["ledger"] is None and tree["attempts"] == [] and tree["refused"] == []
    assert decode_inventory(tree) == bare


Tree = dict[str, Any]
Mutation = Callable[[Tree], object]


def _attempt(tree: Tree, index: int) -> Tree:
    attempts = cast(list[object], tree["attempts"])
    found = attempts[index]
    assert isinstance(found, dict)
    return cast(Tree, found)


def _nested(tree: Tree, *keys: str) -> Tree:
    found: Any = tree
    for key in keys:
        found = found[key]
    assert isinstance(found, dict)
    return cast(Tree, found)


def _reverse_attempts(tree: Tree) -> None:
    attempts = tree["attempts"]
    assert isinstance(attempts, list)
    attempts.reverse()


MALFORMED: list[tuple[Mutation, str]] = [
    (lambda tree: tree.update(format_version=2), "the inventory format is 1, got 2"),
    (lambda tree: tree.update(extra=1), "surplus ['extra']"),
    (lambda tree: _nested(tree, "scope").pop("ledger_id"), "missing ['ledger_id']"),
    (
        lambda tree: _attempt(tree, 1).update(publication=_attempt(tree, 2)["publication"]),
        "an open attempt has no publication record",
    ),
    (_reverse_attempts, "the attempts are listed once each in run and attempt order"),
    (
        lambda tree: _nested(tree, "ledger").update(ledger_id="ledger-2"),
        "the ledger listed is the scope's",
    ),
    (
        lambda tree: _nested(_attempt(tree, 0), "status", "ending").update(failure_category=None),
        "a failure's category and site are given together or neither",
    ),
    (
        lambda tree: _attempt(tree, 0).update(figures=None),
        "the status and the figures are the fold's and absent together",
    ),
    (lambda tree: _attempt(tree, 0).update(closed=False), "the row's closed value is the fold's"),
    (lambda tree: _attempt(tree, 0).update(closed="yes"), "closed is a boolean, got str"),
    (
        lambda tree: _nested(tree, "ledger").update(revision=2),
        "the head is at revision 2 and 3 entries",
    ),
]


@pytest.mark.parametrize(("mutate", "message"), MALFORMED)
def test_a_malformed_inventory_refuses_naming_what_was_wrong(
    mutate: Mutation, message: str
) -> None:
    tree = _thawed(encode_inventory(INVENTORY))
    mutate(tree)
    with pytest.raises(ValueError, match=re.escape(message)):
        decode_inventory(tree)


def test_bytes_that_are_not_json_refuse_as_such() -> None:
    with pytest.raises(ValueError, match="an inventory is JSON"):
        decode_inventory_bytes(b"{not json")


def _thawed(tree: object) -> Tree:
    thawed = json.loads(json.dumps(tree))
    assert isinstance(thawed, dict)
    return cast(Tree, thawed)
