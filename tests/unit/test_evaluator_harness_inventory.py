"""The harness's inventory as the evaluator reads it: named by digest and verified against
the name, of this world or refused; a stored key's standing decided from the key alone
(current, unfinished, superseded, orphan, unlisted); a published object absent or holding
other bytes found by name; the scope by the registration bytes at an attempt's commit; the
attempts with no export, each with its ending, its record's status and its figures; and the
whole's coverage with the four things reported apart in one place."""

import traceback

import pytest

from leaveimpact.adapters.object_store.layout import (
    inventory_key,
    inventory_prefix,
    run_export_key,
    run_prefix,
)
from leaveimpact.core import PublicationStatus, inventory_bytes, inventory_digest
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.harness_inventory import (
    ObjectStanding,
    UnexportedStatus,
    attempts_of_world,
    coverage_of,
    in_scope,
    is_inventory_object,
    missing_publications,
    open_attempts,
    read_inventory,
    scoped_attempts,
    standing_of,
    unexported_attempts,
    unexported_by_run,
)
from tests.unit.inventory_fixture import (
    COMMIT,
    FIGURES,
    READER,
    closed_without_export,
    digest_of,
    listed,
    open_attempt,
    published,
    superseded_object,
)

VERSION = WorldVersion("1" * 64)
OTHER_VERSION = WorldVersion("2" * 64)
OTHER_COMMIT = "c" * 40
EARLIER_READER = "a" * 40
REGISTRATION = b'{"registration": 1}'
OTHER_REGISTRATION = b'{"registration": 2}'
AT = {COMMIT: REGISTRATION, OTHER_COMMIT: OTHER_REGISTRATION}
EXPORT = b'{"export": "run-1/1"}'


# --- The named inventory -----------------------------------------------------------------------


def test_the_inventory_is_read_by_its_name_and_the_name_is_checked_against_the_bytes() -> None:
    inventory = listed(VERSION, published(VERSION, "run-1", 1, EXPORT))
    content = inventory_bytes(inventory)
    digest = inventory_digest(content)
    decoded, read = read_inventory(VERSION, digest, content)
    assert decoded == inventory
    assert (read.key, read.digest) == (inventory_key(VERSION, digest), digest)
    assert (read.format_version, read.schema_version, read.taken_at) == (
        1,
        4,
        inventory.snapshot.taken_at,
    )
    assert (read.world_version, read.registration_commit, read.ledger_id) == (
        VERSION,
        COMMIT,
        "ledger-1",
    )
    assert (read.attempts, read.refused) == (1, 0)
    with pytest.raises(ValueError, match="does not digest to its name"):
        read_inventory(VERSION, "0" * 64, content)


def test_bytes_that_are_no_inventory_refuse_by_the_key_and_never_by_content() -> None:
    # The decoder's own message quotes the value it refused (a status that is no member of
    # its enumeration, here); the reader drops it whole, and its traceback carries nothing
    # of the object either.
    valid = inventory_bytes(listed(VERSION, published(VERSION, "run-1", 1, EXPORT)))
    for content in (
        b'{"format_version": 1, "scope": "SECRET-MARKER"}',
        valid.replace(b'"published"', b'"SECRET-MARKER"'),
        b"not json SECRET-MARKER",
    ):
        with pytest.raises(ValueError) as refused:
            read_inventory(VERSION, inventory_digest(content), content)
        assert str(refused.value) == (
            f"the object at {inventory_key(VERSION, inventory_digest(content))} does not decode "
            "as an inventory"
        )
        printed = "".join(traceback.format_exception(refused.value))
        assert "SECRET-MARKER" not in printed and refused.value.__cause__ is None


def test_an_inventory_of_another_world_is_refused_by_the_key_and_never_by_its_version() -> None:
    # The stored version is the object's own text, so a marker put there must not reach
    # the printable refusal or its traceback (the close's review, carried finding).
    marker = WorldVersion("PRIVATE-MARKER-WORLD")
    content = inventory_bytes(listed(marker))
    with pytest.raises(ValueError, match="of another world") as refused:
        read_inventory(VERSION, inventory_digest(content), content)
    printed = "".join(traceback.format_exception(refused.value))
    assert "PRIVATE-MARKER" not in printed and VERSION in str(refused.value)
    other = inventory_bytes(listed(OTHER_VERSION))
    with pytest.raises(ValueError, match="of another world"):
        read_inventory(VERSION, inventory_digest(other), other)


def test_the_inventory_prefix_is_told_from_the_runs_under_it() -> None:
    assert is_inventory_object(VERSION, inventory_key(VERSION, "9" * 64))
    assert is_inventory_object(VERSION, inventory_prefix(VERSION))
    assert not is_inventory_object(VERSION, run_export_key(VERSION, "inventory", 1, READER))
    assert not is_inventory_object(VERSION, run_prefix(VERSION, "run-1", 1) + "export.json")


# --- The standing of a stored key --------------------------------------------------------------


def test_a_keys_standing_is_decided_from_the_inventory_and_the_key_alone() -> None:
    earlier = superseded_object(VERSION, "run-1", 1, b"earlier", reader_commit=EARLIER_READER)
    inventory = listed(
        VERSION,
        published(VERSION, "run-1", 1, EXPORT, superseded=(earlier,)),
        published(VERSION, "run-2", 1, EXPORT, status=PublicationStatus.PENDING),
        closed_without_export(VERSION, "run-3", 1),
    )
    current = run_export_key(VERSION, "run-1", 1, READER)
    assert standing_of(inventory, VERSION, current) is ObjectStanding.CURRENT
    assert standing_of(inventory, VERSION, earlier.object_identity) is ObjectStanding.SUPERSEDED
    pending = run_export_key(VERSION, "run-2", 1, READER)
    assert standing_of(inventory, VERSION, pending) is ObjectStanding.UNFINISHED
    for orphan in (
        run_export_key(VERSION, "run-1", 1, "9" * 40),
        run_prefix(VERSION, "run-3", 1) + "export.json",
        run_prefix(VERSION, "run-1", 1) + "notes.txt",
    ):
        assert standing_of(inventory, VERSION, orphan) is ObjectStanding.ORPHAN, orphan
    for unlisted in (
        run_export_key(VERSION, "run-4", 1, READER),
        run_export_key(VERSION, "run-1", 2, READER),
        run_prefix(VERSION, "run-1", 10) + "export.json",
    ):
        assert standing_of(inventory, VERSION, unlisted) is ObjectStanding.UNLISTED, unlisted


def test_a_failed_record_that_still_names_an_object_makes_it_unfinished() -> None:
    inventory = listed(
        VERSION, published(VERSION, "run-1", 1, EXPORT, status=PublicationStatus.FAILED)
    )
    key = run_export_key(VERSION, "run-1", 1, READER)
    assert standing_of(inventory, VERSION, key) is ObjectStanding.UNFINISHED


# --- The store against the snapshot ------------------------------------------------------------


def test_every_published_object_is_present_with_its_digest_or_named_as_missing() -> None:
    other = b'{"export": "run-2/1"}'
    inventory = listed(
        VERSION,
        published(VERSION, "run-1", 1, EXPORT),
        published(VERSION, "run-2", 1, other),
        published(VERSION, "run-3", 1, EXPORT, status=PublicationStatus.PENDING),
        closed_without_export(VERSION, "run-4", 1, incident=True),
    )
    first, second = (run_export_key(VERSION, run, 1, READER) for run in ("run-1", "run-2"))
    held = {first: digest_of(EXPORT), second: digest_of(other)}
    assert missing_publications(inventory, VERSION, held) == ()
    found = missing_publications(inventory, VERSION, {first: digest_of(b"changed")})
    assert [(each.run_id, each.key, each.absent) for each in found] == [
        ("run-1", first, False),
        ("run-2", second, True),
    ]
    assert found[0].reason == "holds other bytes than recorded"
    assert found[1].reason == "is not in the listing"


# --- The evaluation's attempts -----------------------------------------------------------------


def test_an_attempt_is_in_scope_when_its_commit_resolves_to_the_evaluations_registration() -> None:
    own = open_attempt(VERSION, "run-1", 1)
    other = open_attempt(VERSION, "run-2", 1, registration_commit=OTHER_COMMIT)
    unresolved = open_attempt(VERSION, "run-3", 1, registration_commit="9" * 40)
    assert in_scope(own, AT, REGISTRATION)
    assert not in_scope(other, AT, REGISTRATION)
    assert not in_scope(unresolved, AT, REGISTRATION)
    assert in_scope(other, AT, OTHER_REGISTRATION)
    inventory = listed(VERSION, own, other, unresolved)
    assert scoped_attempts(inventory, VERSION, AT, REGISTRATION) == (own,)
    assert open_attempts(inventory.attempts) == (own, other, unresolved)
    assert open_attempts(scoped_attempts(inventory, VERSION, AT, OTHER_REGISTRATION)) == (other,)


def test_the_inventory_lists_every_world_and_an_evaluation_is_held_to_its_own() -> None:
    # The store holds the deployment's every attempt; the evaluation lists one world's prefix,
    # so the other world's publication is never in its listing and refuses nothing, and a
    # foreign open attempt under the same registration is neither admitted nor open here.
    mine = published(VERSION, "run-1", 1, EXPORT)
    theirs = published(OTHER_VERSION, "run-9", 1, b"theirs")
    foreign_open = open_attempt(OTHER_VERSION, "run-8", 1)
    inventory = listed(VERSION, mine, theirs, foreign_open)
    assert attempts_of_world(inventory, VERSION) == (mine,)
    assert attempts_of_world(inventory, OTHER_VERSION) == (foreign_open, theirs)
    listing = {run_export_key(VERSION, "run-1", 1, READER): digest_of(EXPORT)}
    assert missing_publications(inventory, VERSION, listing) == ()
    assert [m.run_id for m in missing_publications(inventory, OTHER_VERSION, {})] == ["run-9"]
    scoped = scoped_attempts(inventory, VERSION, AT, REGISTRATION)
    assert scoped == (mine,)
    coverage = coverage_of(scoped, intended=1, failed_by_defect=0, failed_by_infrastructure=0)
    assert (coverage.admitted, coverage.open) == (1, 0)


def test_the_attempts_with_no_export_carry_their_status_ending_record_and_figures() -> None:
    inventory = listed(
        VERSION,
        published(VERSION, "run-1", 1, EXPORT),
        published(VERSION, "run-1", 2, EXPORT, status=PublicationStatus.PENDING),
        open_attempt(VERSION, "run-2", 1),
        closed_without_export(VERSION, "run-3", 1, incident=True),
        closed_without_export(VERSION, "run-3", 2),
        closed_without_export(VERSION, "run-4", 1, folded=False),
    )
    held = unexported_attempts(inventory.attempts)
    assert [(each.run_id, each.attempt, each.status) for each in held] == [
        ("run-1", 2, UnexportedStatus.CLOSED_WITHOUT_EXPORT),
        ("run-2", 1, UnexportedStatus.OPEN),
        ("run-3", 1, UnexportedStatus.CLOSED_WITHOUT_EXPORT),
        ("run-3", 2, UnexportedStatus.CLOSED_WITHOUT_EXPORT),
        ("run-4", 1, UnexportedStatus.CLOSED_WITHOUT_EXPORT),
    ]
    pending, opened, failed, unbegun, unfolded = held
    assert (pending.publication, pending.incident) == (PublicationStatus.PENDING, False)
    assert (opened.ending, opened.publication, opened.figures) == (None, None, FIGURES)
    assert (failed.publication, failed.incident) == (PublicationStatus.FAILED, True)
    assert failed.ending is not None and failed.ending.status.value == "completed"
    assert (unbegun.publication, unbegun.incident) == (None, False)
    assert (unfolded.ending, unfolded.figures) == (None, None)
    by_run = unexported_by_run(held)
    assert list(by_run) == ["run-1", "run-2", "run-3", "run-4"]
    assert [each.attempt for each in by_run["run-3"]] == [1, 2]
    assert unexported_by_run(()) == {}


# --- The whole's coverage ----------------------------------------------------------------------


def test_coverage_counts_the_runs_against_the_intended_and_the_attempts_by_what_they_lack() -> None:
    inventory = listed(
        VERSION,
        published(VERSION, "run-1", 1, EXPORT),
        published(VERSION, "run-2", 1, EXPORT),
        published(VERSION, "run-2", 2, EXPORT, status=PublicationStatus.PENDING),
        open_attempt(VERSION, "run-3", 1),
        closed_without_export(VERSION, "run-4", 1, incident=True),
        open_attempt(VERSION, "run-9", 1, registration_commit=OTHER_COMMIT),
    )
    scoped = scoped_attempts(inventory, VERSION, AT, REGISTRATION)
    coverage = coverage_of(scoped, intended=6, failed_by_defect=1, failed_by_infrastructure=0)
    assert (coverage.intended, coverage.admitted) == (6, 4)
    assert (coverage.never_admitted, coverage.admitted_beyond_intended) == (2, 0)
    assert (coverage.attempts, coverage.exported) == (5, 2)
    assert (coverage.open, coverage.closed_without_export) == (1, 2)
    assert coverage.publication_incidents == 1
    assert (coverage.failed_by_defect, coverage.failed_by_infrastructure) == (1, 0)
    assert [(each.run_id, each.attempt) for each in coverage.unexported] == [
        ("run-2", 2),
        ("run-3", 1),
        ("run-4", 1),
    ]
    surplus = coverage_of(scoped, intended=3, failed_by_defect=0, failed_by_infrastructure=0)
    assert (surplus.never_admitted, surplus.admitted_beyond_intended) == (0, 1)
    empty = coverage_of((), intended=0, failed_by_defect=0, failed_by_infrastructure=0)
    assert (empty.admitted, empty.attempts, empty.unexported) == (0, 0, ())
