"""The event log's PostgreSQL module: the attempt row's lock, its counters, and the persistence
of what the transition function admits; the shared ledger; the publication records.

**One writer.** Every authoritative change (an admission, a claim, a worker's append, a
terminal event, an abandonment, an outside producer's append) locks the attempt row
``FOR UPDATE``, runs the transition function against the current state, inserts and
commits in one transaction (the event log step's ruling on one writer, part 2; the
lock-race probe in ``probes/FINDINGS.md`` showed a guarded insert without the lock
commits after a takeover it overlapped, and the row lock gives the two legal orders and
no third). Locks are taken in one order everywhere: the run row, the attempt row, the
ledger head (the ruling on admission, part 5). Every command runs in an explicit
transaction block on an autocommit connection, so no read leaves a transaction open.

**Legality is the transition's, identity is the index's.** ``next_state`` decides what a
log may hold next and this module writes nothing it refuses. The schema enforces identity
only: one event per position, one per identifier (``event_key_bytes``), one segment start
per claim nonce. A held identifier with the same content is the idempotent receipt the
transition gives; with other content it is a conflict raised here, before the transition,
as the ruling on closure says ("still raises").

**The state the transition runs against.** The attempt row holds counters (last position,
generation, segments, open or closed) and the log is append-only with dense positions, so
two states of one attempt with equal counters are one state. A caller passes the state it
holds; the store uses it when the counters agree and folds the log otherwise, or when no
state is given. The fold is recovery's path and an outside producer's, never a per-append
cost on the worker's.

**The timestamp** is the database's ``clock_timestamp()``, drawn from the locked
connection in the inserting transaction, one statement before the insert, the only order
in which the transition can see the event it judges (the ruling on the event, part 4). The
``clock`` seam defaults to that statement; the histories' replay supplies its own.

**The settlement** is computed where the lock is: a closing event arrives with no
settlement and leaves with the one ``settle`` gives over the state's account, at the
ledger revision the settled entry was written at, in the same transaction (the ruling on
admission, part 8). A repeated closure compares with the settlement masked and is a
receipt, so one closure and one settled entry exist however often it is retried.

**Admission** writes the ledger's reservation, the attempt row at generation 0 and the
admission event at position 1 in one transaction, after the run row's lock numbered the
attempt and the predecessor was read: closed, its export published (the ruling on an
export that will not construct, part 5), and its ending permitting a new attempt. A
refusal is recorded under the request's identity and committed before it is returned,
consuming no attempt number; a repeated request returns its recorded result.

**Faults.** ``LogStoreUnavailable`` is the driver's operational error on open or under a
statement: nothing durable happened and the attempt stays as it was (the ruling on
recovery, part 8). ``LogStoreInvariantBroken`` is a schema version that differs, a stored
log that will not fold, a counter disagreeing with its fold, or an integrity error under
the lock, which the lock should make impossible. ``LogStoreConflict`` is other content
under a held identifier, or another request for an attempt that exists with other inputs.
Messages name runs, attempts, positions, kinds and reasons, never content. The
``boundary`` seam names three points of every writing command (``locked``, ``decided``,
``before-commit``) so a two-connection test can hold one side where it chooses; it is a
no-op in production.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from importlib import resources
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from leaveimpact.agent import ledger
from leaveimpact.agent.ledger import LedgerEntry, LedgerHead
from leaveimpact.agent.log_ending import eligibility_ending_of
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    CapExhausted,
    ClosingEvent,
    CommitOverride,
    Completed,
    Envelope,
    Event,
    Failed,
    FrozenInputs,
    LoggedEvent,
    LoggedSettlement,
    Producer,
    SegmentStarted,
    WorkerStamp,
    decode_logged_event,
    encode_logged_event,
    event_bytes,
    event_digest,
    event_key_bytes,
    kind_of,
)
from leaveimpact.agent.log_transition import (
    Appended,
    AttemptState,
    Received,
    Refused,
    Rules,
    Transition,
    fold,
    next_state,
)
from leaveimpact.core.eligibility import new_attempt_eligibility
from leaveimpact.core.jsonshape import (
    JsonObject,
    as_object,
    expect_fields,
    field_of,
    integer_field,
    optional_string_field,
    string_field,
)
from leaveimpact.core.run_account import settle
from leaveimpact.core.run_record import FailureCategory
from leaveimpact.core.run_timing import HarnessRevision, require_commit
from leaveimpact.core.run_trace import require_integer, require_opaque_id
from leaveimpact.core.timeshape import decode_instant, encode_instant

SCHEMA_VERSION = 1
"""The schema this code writes and reads; a connection to another version is refused."""

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]
Clock = Callable[[Connection], datetime]
Boundary = Callable[[str], None]

_CONNECT_TIMEOUT_S = 10


# --- Faults ----------------------------------------------------------------------------------


class LogStoreUnavailable(Exception):
    """The database could not be reached or a statement failed on the wire; nothing durable
    happened in the command that raised it."""


class LogStoreInvariantBroken(Exception):
    """What is stored disagrees with what this code requires of it: the schema version, a
    log that will not fold, a counter against its fold, an integrity error under the lock."""


class LogStoreConflict(Exception):
    """A held identifier with other content, or an existing attempt asked for with other
    frozen inputs: the caller's bug, raised and recorded nowhere."""


# --- Results and records ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdmissionRequest:
    """What the admitter asks: the request identity it holds across retries, the frozen
    inputs (which name the run and the attempt number asked for), its own identity as the
    admission event's producer, the ledger to reserve against (given exactly when the
    inputs reserve) and the registered rules, used to fold the predecessor's log."""

    request_id: str
    inputs: FrozenInputs
    admitter: Producer
    ledger_id: str | None
    rules: Rules

    def __post_init__(self) -> None:
        require_opaque_id(self.request_id, "a request identity")
        if (self.ledger_id is None) == (self.inputs.reservation_pico_usd is not None):
            raise ValueError("a ledger is named exactly when the inputs reserve an amount")
        if self.ledger_id is not None:
            require_opaque_id(self.ledger_id, "a ledger id")


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    """The attempt exists with these inputs: when its admission was recorded, and the ledger
    revision its reservation was written at (none when nothing was reserved)."""

    run_id: str
    attempt: int
    recorded_at: datetime
    ledger_revision: int | None


@dataclass(frozen=True, slots=True)
class AdmissionRefusal:
    """The request was refused and the refusal recorded: why, and the ledger revision when
    the ledger refused (none when eligibility or publication did)."""

    run_id: str
    attempt: int
    reason: str
    ledger_revision: int | None


type AdmissionResult = AdmissionReceipt | AdmissionRefusal


@dataclass(frozen=True, slots=True)
class AttemptRef:
    """A run and one of its attempts."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class LedgerView:
    """A ledger as read in one transaction: its head and every entry in revision order."""

    head: LedgerHead
    entries: tuple[LedgerEntry, ...]


class PublicationState(StrEnum):
    """Where an attempt's publication stands; a member is the stored form."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    """The ruling on the job seam's part 4: one per attempt, apart from the log. The reader's
    commit and export format, the closed log's digest, the object's identity and digest, the
    state, the incident of the last failure and, when a pending record replaced a failed
    one under another reader, the commit it repaired."""

    run_id: str
    attempt: int
    state: PublicationState
    reader_commit: str
    export_format: int
    log_digest: str
    object_identity: str
    object_digest: str
    incident: str | None
    repaired_from_commit: str | None
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class _Row:
    """The attempt row as locked."""

    run_id: str
    attempt: int
    generation: int
    segments: int
    positions: int
    closed: bool
    log_format: int
    ledger_id: str | None


# --- SQL -------------------------------------------------------------------------------------

_LOCK_RUN = "SELECT attempts FROM run WHERE run_id = %s FOR UPDATE"
_INSERT_RUN = "INSERT INTO run (run_id) VALUES (%s) ON CONFLICT DO NOTHING"
_SET_RUN_ATTEMPTS = "UPDATE run SET attempts = %s WHERE run_id = %s"
_SELECT_ATTEMPT = """
    SELECT run_id, attempt, generation, segments, positions, closed, log_format, ledger_id
    FROM attempt WHERE run_id = %s AND attempt = %s
"""
_LOCK_ATTEMPT = _SELECT_ATTEMPT + " FOR UPDATE"
_INSERT_ATTEMPT = """
    INSERT INTO attempt (run_id, attempt, generation, segments, positions, closed, log_format,
                         ledger_id)
    VALUES (%s, %s, 0, 0, 0, FALSE, %s, %s)
"""
_UPDATE_ATTEMPT = """
    UPDATE attempt SET generation = %s, segments = %s, positions = %s, closed = %s
    WHERE run_id = %s AND attempt = %s
"""
_OPEN_ATTEMPTS = "SELECT run_id, attempt FROM attempt WHERE NOT closed ORDER BY run_id, attempt"
_INSERT_EVENT = """
    INSERT INTO event (run_id, attempt, position, kind, key, claim_nonce, recorded_at, digest,
                       record)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_SELECT_EVENTS = "SELECT record FROM event WHERE run_id = %s AND attempt = %s ORDER BY position"
_SELECT_HELD = (
    "SELECT record FROM event WHERE run_id = %s AND attempt = %s AND kind = %s AND key = %s"
)
_SELECT_BY_NONCE = (
    "SELECT record FROM event WHERE run_id = %s AND attempt = %s AND claim_nonce = %s"
)
_SELECT_LAST = "SELECT record FROM event WHERE run_id = %s AND attempt = %s AND position = %s"
_SELECT_REQUEST = "SELECT run_id, attempt, result FROM admission_request WHERE request_id = %s"
_INSERT_REQUEST = """
    INSERT INTO admission_request (request_id, run_id, attempt, outcome, result, recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s)
"""
_INSERT_HEAD = """
    INSERT INTO ledger_head (ledger_id, total_pico_usd, revision) VALUES (%s, 0, 0)
    ON CONFLICT DO NOTHING
"""
_SELECT_HEAD = (
    "SELECT total_pico_usd, revision, threshold_pico_usd FROM ledger_head WHERE ledger_id = %s"
)
_LOCK_HEAD = _SELECT_HEAD + " FOR UPDATE"
_UPDATE_HEAD = """
    UPDATE ledger_head SET total_pico_usd = %s, revision = %s, threshold_pico_usd = %s
    WHERE ledger_id = %s
"""
_INSERT_ENTRY = """
    INSERT INTO ledger_entry (ledger_id, revision, kind, run_id, attempt, amount_pico_usd,
                              total_after_pico_usd, authority, registration_commit, reason,
                              recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_SELECT_ENTRIES = """
    SELECT revision, kind, run_id, attempt, amount_pico_usd, total_after_pico_usd, authority,
           registration_commit, reason
    FROM ledger_entry WHERE ledger_id = %s ORDER BY revision
"""
_SELECT_PUBLICATION = """
    SELECT run_id, attempt, state, reader_commit, export_format, log_digest, object_identity,
           object_digest, incident, repaired_from_commit, recorded_at
    FROM publication WHERE run_id = %s AND attempt = %s
"""
_LOCK_PUBLICATION = _SELECT_PUBLICATION + " FOR UPDATE"
_UPSERT_PUBLICATION = """
    INSERT INTO publication (run_id, attempt, state, reader_commit, export_format, log_digest,
                             object_identity, object_digest, incident, repaired_from_commit,
                             recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (run_id, attempt) DO UPDATE SET
        state = EXCLUDED.state, reader_commit = EXCLUDED.reader_commit,
        export_format = EXCLUDED.export_format, log_digest = EXCLUDED.log_digest,
        object_identity = EXCLUDED.object_identity, object_digest = EXCLUDED.object_digest,
        incident = EXCLUDED.incident, repaired_from_commit = EXCLUDED.repaired_from_commit,
        recorded_at = EXCLUDED.recorded_at
"""
_SELECT_VERSION = "SELECT version FROM log_schema"
_INSERT_VERSION = "INSERT INTO log_schema (version) VALUES (%s) ON CONFLICT DO NOTHING"


def _connect(dsn: str) -> Connection:
    # Autocommit: every command opens its own transaction block, and no read leaves one open.
    return psycopg.connect(dsn, connect_timeout=_CONNECT_TIMEOUT_S, autocommit=True)


def _database_clock(conn: Connection) -> datetime:
    row = conn.execute("SELECT clock_timestamp()").fetchone()
    assert row is not None
    at = row[0]
    assert isinstance(at, datetime)
    return at


def _no_boundary(name: str) -> None:
    return None


# --- The store -------------------------------------------------------------------------------


class LogStore:
    """The event log over one PostgreSQL database; see the module. Construction does no I/O."""

    def __init__(
        self,
        *,
        dsn: str,
        connect: Connect = _connect,
        clock: Clock = _database_clock,
        boundary: Boundary = _no_boundary,
    ) -> None:
        self._dsn = dsn
        self._connect = connect
        self._clock = clock
        self._boundary = boundary
        self._connection: Connection | None = None

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # --- preparation -------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """The tables created where missing and the version row written where absent, then
        the version checked; never alters an existing table."""
        ddl = resources.files(__package__).joinpath("log_schema.sql").read_text(encoding="utf-8")
        with self._guarded(check_version=False) as conn:
            with conn.transaction():
                conn.execute(ddl.encode())
                conn.execute(_INSERT_VERSION, (SCHEMA_VERSION,))
            _check_version(conn)

    # --- admission ---------------------------------------------------------------------

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        """The ruling on admission: one transaction, the run row locked first, a recorded
        request returned as recorded, the predecessor read, the reservation made or refused,
        then the attempt row and the admission event at position 1."""
        inputs = request.inputs
        run_id, attempt = inputs.run_id, inputs.attempt
        with self._guarded() as conn, conn.transaction():
            conn.execute(_INSERT_RUN, (run_id,))
            run_row = conn.execute(_LOCK_RUN, (run_id,)).fetchone()
            assert run_row is not None
            admitted_so_far = int(run_row[0])
            self._boundary("locked")
            recorded = conn.execute(_SELECT_REQUEST, (request.request_id,)).fetchone()
            if recorded is not None:
                if (recorded[0], recorded[1]) != (run_id, attempt):
                    raise LogStoreConflict(
                        f"request {request.request_id} was recorded for run {recorded[0]} "
                        f"attempt {recorded[1]}, asked again for run {run_id} attempt {attempt}"
                    )
                return _decode_result(run_id, attempt, recorded[2])
            at = self._clock(conn)
            if attempt <= admitted_so_far:
                result: AdmissionResult = self._existing_admission(conn, run_id, attempt, inputs)
                self._record_request(conn, request, result, at)
                return result
            if attempt != admitted_so_far + 1:
                raise LogStoreConflict(
                    f"run {run_id} has {admitted_so_far} attempts; attempt {attempt} is not "
                    f"the next"
                )
            reason = self._predecessor_refusal(conn, run_id, attempt, inputs, request.rules)
            entry: LedgerEntry | None = None
            if reason is None and inputs.reservation_pico_usd is not None:
                assert request.ledger_id is not None
                reason, entry = self._reserve(
                    conn, request.ledger_id, run_id, attempt, inputs.reservation_pico_usd, at
                )
            revision = None if entry is None else entry.revision
            if reason is not None:
                result = AdmissionRefusal(run_id, attempt, reason, revision)
                self._record_request(conn, request, result, at)
                self._boundary("before-commit")
                return result
            logged = LoggedEvent(1, at, request.admitter, Admitted(inputs))
            transition = next_state(AttemptState(), logged, request.rules)
            if not isinstance(transition, Appended):
                raise LogStoreInvariantBroken(
                    f"the admission of run {run_id} attempt {attempt} was not admitted by the "
                    f"transition: {transition}"
                )
            conn.execute(
                _INSERT_ATTEMPT, (run_id, attempt, inputs.log_format_version, request.ledger_id)
            )
            self._insert(conn, transition.state, logged)
            conn.execute(_SET_RUN_ATTEMPTS, (attempt, run_id))
            result = AdmissionReceipt(run_id, attempt, at, revision)
            self._record_request(conn, request, result, at)
            self._boundary("before-commit")
            return result

    def _existing_admission(
        self, conn: Connection, run_id: str, attempt: int, inputs: FrozenInputs
    ) -> AdmissionReceipt:
        """The backstop of the ruling on the job seam, part 3: an attempt that exists gives
        its receipt to identical inputs and a conflict to other ones."""
        row = conn.execute(_SELECT_LAST, (run_id, attempt, 1)).fetchone()
        assert row is not None, "an admitted attempt holds its admission at position 1"
        held = decode_logged_event(row[0])
        if event_bytes(held.event) != event_bytes(Admitted(inputs)):
            raise LogStoreConflict(
                f"run {run_id} attempt {attempt} exists with other frozen inputs"
            )
        revision = self._reservation_revision(conn, run_id, attempt)
        return AdmissionReceipt(run_id, attempt, held.timestamp, revision)

    def _reservation_revision(self, conn: Connection, run_id: str, attempt: int) -> int | None:
        row = conn.execute(
            "SELECT revision FROM ledger_entry WHERE kind = %s AND run_id = %s AND attempt = %s",
            (ledger.EntryKind.ADMITTED.value, run_id, attempt),
        ).fetchone()
        return None if row is None else int(row[0])

    def _predecessor_refusal(
        self, conn: Connection, run_id: str, attempt: int, inputs: FrozenInputs, rules: Rules
    ) -> str | None:
        """Why attempt ``attempt`` may not follow its predecessor, or ``None``: the
        predecessor open, its export not published, or its ending permitting no new attempt."""
        if attempt == 1:
            return None
        before = attempt - 1
        row = self._lock(conn, run_id, before)
        if not row.closed:
            return f"attempt {before} is open"
        publication = self._publication(conn, run_id, before, lock=False)
        if publication is None or publication.state is not PublicationState.PUBLISHED:
            state = "absent" if publication is None else publication.state.value
            return f"attempt {before}'s export is not published (publication {state})"
        state = self._fold(conn, row, rules)
        stopped = state.stopped
        eligibility = new_attempt_eligibility(
            eligibility_ending_of(state, rules),
            recorded_defect=stopped is not None and stopped.category is FailureCategory.DEFECT,
            attempt=before,
            retry=inputs.retry,
        )
        if eligibility.permitted:
            return None
        return f"attempt {before}'s ending permits no new attempt ({eligibility.rule.value})"

    def _reserve(
        self,
        conn: Connection,
        ledger_id: str,
        run_id: str,
        attempt: int,
        amount_pico_usd: int,
        at: datetime,
    ) -> tuple[str | None, LedgerEntry | None]:
        """The reservation against the locked head: the admitted entry, or the refusal with
        the ledger's refused entry when a head exists to hold one."""
        head = self._lock_head(conn, ledger_id)
        if head is None:
            return f"ledger {ledger_id} has no head: no threshold is set on it", None
        refusal = ledger.reservation_refusal(head, amount_pico_usd)
        if refusal is not None:
            entry, after = ledger.refused(head, run_id, attempt, amount_pico_usd, reason=refusal)
            self._write_entry(conn, ledger_id, entry, after, at)
            return refusal, entry
        entry, after = ledger.admitted(head, run_id, attempt, amount_pico_usd)
        self._write_entry(conn, ledger_id, entry, after, at)
        return None, entry

    def _record_request(
        self, conn: Connection, request: AdmissionRequest, result: AdmissionResult, at: datetime
    ) -> None:
        outcome = "admitted" if isinstance(result, AdmissionReceipt) else "refused"
        conn.execute(
            _INSERT_REQUEST,
            (
                request.request_id,
                result.run_id,
                result.attempt,
                outcome,
                Jsonb(_encode_result(result)),
                at,
            ),
        )

    # --- the log's commands ------------------------------------------------------------

    def claim(
        self,
        run_id: str,
        attempt: int,
        *,
        harness: HarnessRevision,
        nonce: str,
        launch: str,
        rules: Rules,
        override: CommitOverride | None = None,
        state: AttemptState | None = None,
    ) -> Transition:
        """The ruling on one writer, part 3: the next segment under the next generation in
        one transaction; a retry under a held nonce gets its receipt back and opens nothing,
        unless a later claim fenced it."""
        event = SegmentStarted(harness, nonce, launch, override)
        with self._guarded() as conn, conn.transaction():
            row = self._lock(conn, run_id, attempt)
            self._boundary("locked")
            held = conn.execute(_SELECT_BY_NONCE, (run_id, attempt, nonce)).fetchone()
            if held is not None:
                earlier = decode_logged_event(held[0])
                stamp = earlier.stamp
                assert stamp is not None
                if stamp.generation == row.generation:
                    return Received(earlier.position)
                return Refused(
                    f"the claim under this nonce opened generation {stamp.generation}, fenced "
                    f"by generation {row.generation}"
                )
            at = self._clock(conn)
            number = row.segments + 1
            logged = LoggedEvent(row.positions + 1, at, WorkerStamp(number, number, 0), event)
            current = self._current_state(conn, row, state, rules)
            transition = next_state(current, logged, rules)
            self._boundary("decided")
            if isinstance(transition, Appended):
                self._insert(conn, transition.state, logged, claim_nonce=nonce)
            self._boundary("before-commit")
            return transition

    def append(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope,
        event: Event,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        """A worker's or an outside producer's event under the lock; the admission, a claim
        and a closing event have their own commands and are refused here by type."""
        if isinstance(
            event, Admitted | SegmentStarted | Completed | CapExhausted | Failed | Abandoned
        ):
            raise ValueError(
                f"{kind_of(event).value} is appended through its own command, not append"
            )
        with self._guarded() as conn, conn.transaction():
            row = self._lock(conn, run_id, attempt)
            self._boundary("locked")
            at = self._clock(conn)
            logged = LoggedEvent(row.positions + 1, at, envelope, event)
            received = self._receipt(conn, row, logged)
            if received is not None:
                return received
            current = self._current_state(conn, row, state, rules)
            transition = next_state(current, logged, rules)
            self._boundary("decided")
            if isinstance(transition, Appended):
                self._insert(conn, transition.state, logged)
            self._boundary("before-commit")
            return transition

    def close_attempt(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope,
        closing: ClosingEvent,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        """The closing event with the settlement the store computes under the lock and the
        ledger's settled entry in the same transaction (the ruling on admission, part 8);
        ``closing`` arrives with no settlement. A repeat on the closed attempt is the receipt."""
        if closing.settlement is not None:
            raise ValueError(
                "the store computes the settlement; pass the closing event without one"
            )
        with self._guarded() as conn, conn.transaction():
            row = self._lock(conn, run_id, attempt)
            self._boundary("locked")
            if row.closed:
                return self._closed_again(conn, row, closing)
            at = self._clock(conn)
            current = self._current_state(conn, row, state, rules)
            inputs = current.inputs
            assert inputs is not None
            written: tuple[str, LedgerEntry, LedgerHead] | None = None
            settlement: LoggedSettlement | None = None
            if inputs.reservation_pico_usd is not None:
                assert row.ledger_id is not None
                head = self._lock_head(conn, row.ledger_id)
                if head is None:
                    raise LogStoreInvariantBroken(
                        f"run {run_id} attempt {attempt} reserved against ledger "
                        f"{row.ledger_id}, which has no head"
                    )
                computed = settle(current.account)
                entry, after = ledger.settled(
                    head,
                    run_id,
                    attempt,
                    reservation_pico_usd=inputs.reservation_pico_usd,
                    charged_pico_usd=computed.charged_pico_usd,
                )
                settlement = LoggedSettlement(
                    computed.charged_pico_usd, computed.state, computed.kept_reason, entry.revision
                )
                written = (row.ledger_id, entry, after)
            filled: ClosingEvent = replace(closing, settlement=settlement)
            logged = LoggedEvent(row.positions + 1, at, envelope, filled)
            transition = next_state(current, logged, rules)
            self._boundary("decided")
            if isinstance(transition, Appended):
                if written is not None:
                    ledger_id, entry, after = written
                    self._write_entry(conn, ledger_id, entry, after, at)
                self._insert(conn, transition.state, logged)
            self._boundary("before-commit")
            return transition

    def _closed_again(self, conn: Connection, row: _Row, closing: ClosingEvent) -> Transition:
        held_row = conn.execute(_SELECT_LAST, (row.run_id, row.attempt, row.positions)).fetchone()
        assert held_row is not None, "a closed attempt's last event is its closing event"
        held = decode_logged_event(held_row[0])
        held_event = held.event
        if kind_of(held_event) is not kind_of(closing):
            return Refused(f"the attempt is closed at position {held.position}")
        assert isinstance(held_event, Completed | CapExhausted | Failed | Abandoned)
        masked: ClosingEvent = replace(held_event, settlement=None)
        if event_bytes(masked) == event_bytes(closing):
            return Received(held.position)
        raise LogStoreConflict(
            f"run {row.run_id} attempt {row.attempt} is closed at position {held.position} by "
            f"a {kind_of(closing).value} with other content"
        )

    # --- reading -----------------------------------------------------------------------

    def events(self, run_id: str, attempt: int) -> tuple[LoggedEvent, ...]:
        """The log in position order; ``ValueError`` for an attempt that does not exist."""
        with self._guarded() as conn, conn.transaction():
            row = self._row(conn, run_id, attempt)
            return self._events_of(conn, row)

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        """The state the log folds to under ``rules``, for a worker starting, recovery and
        the reader."""
        with self._guarded() as conn, conn.transaction():
            return self._fold(conn, self._row(conn, run_id, attempt), rules)

    def open_attempts(self) -> tuple[AttemptRef, ...]:
        """The ruling on admission, part 9: open attempts from the attempt rows alone."""
        with self._guarded() as conn, conn.transaction():
            rows = conn.execute(_OPEN_ATTEMPTS).fetchall()
        return tuple(AttemptRef(str(run_id), int(attempt)) for run_id, attempt in rows)

    # --- the ledger --------------------------------------------------------------------

    def set_threshold(
        self,
        ledger_id: str,
        amount_pico_usd: int,
        *,
        authority: str,
        registration_commit: str,
        limit_pico_usd: int,
    ) -> LedgerEntry:
        """The ruling on the ledger, part 10: the head created where absent, the threshold
        refused (``ValueError``) above the registered limit or below the committed total,
        else its entry."""
        require_opaque_id(ledger_id, "a ledger id")
        with self._guarded() as conn, conn.transaction():
            conn.execute(_INSERT_HEAD, (ledger_id,))
            head = self._lock_head(conn, ledger_id)
            assert head is not None
            self._boundary("locked")
            refusal = ledger.threshold_refusal(head, amount_pico_usd, limit_pico_usd=limit_pico_usd)
            if refusal is not None:
                raise ValueError(refusal)
            entry, after = ledger.threshold_set(
                head, amount_pico_usd, authority=authority, registration_commit=registration_commit
            )
            self._write_entry(conn, ledger_id, entry, after, self._clock(conn))
            self._boundary("before-commit")
            return entry

    def ledger_view(self, ledger_id: str) -> LedgerView:
        """The head and every entry in one transaction; the head must be what its entries
        fold to."""
        with self._guarded() as conn, conn.transaction():
            head_row = conn.execute(_SELECT_HEAD, (ledger_id,)).fetchone()
            if head_row is None:
                raise ValueError(f"ledger {ledger_id} has no head")
            head = _head_of(head_row)
            rows = conn.execute(_SELECT_ENTRIES, (ledger_id,)).fetchall()
        entries = tuple(_entry_of(row) for row in rows)
        if ledger.fold(entries) != head:
            raise LogStoreInvariantBroken(
                f"ledger {ledger_id}'s head at revision {head.revision} is not what its "
                f"{len(entries)} entries fold to"
            )
        return LedgerView(head, entries)

    # --- publication records -----------------------------------------------------------

    def publication_of(self, run_id: str, attempt: int) -> PublicationRecord | None:
        """The attempt's record, or ``None`` before a publication was begun."""
        with self._guarded() as conn, conn.transaction():
            return self._publication(conn, run_id, attempt, lock=False)

    def publication_pending(
        self,
        run_id: str,
        attempt: int,
        *,
        reader_commit: str,
        export_format: int,
        log_digest: str,
        object_identity: str,
        object_digest: str,
    ) -> PublicationRecord:
        """A publication begun for a closed attempt: a published record is returned as it
        stands, a pending or failed one under another reader is replaced and names the
        commit it repairs, and another digest of one closed log is a conflict."""
        require_commit(reader_commit, "the reader's commit")
        require_integer(export_format, "an export format", minimum=1)
        with self._guarded() as conn, conn.transaction():
            row = self._lock(conn, run_id, attempt)
            if not row.closed:
                raise ValueError(f"run {run_id} attempt {attempt} is open and has no export")
            self._boundary("locked")
            held = self._publication(conn, run_id, attempt, lock=True)
            if held is not None and held.state is PublicationState.PUBLISHED:
                return held
            repaired = None
            if held is not None:
                if held.log_digest != log_digest:
                    raise LogStoreConflict(
                        f"run {run_id} attempt {attempt}'s publication was begun over another "
                        f"log digest"
                    )
                if held.state is PublicationState.FAILED and held.reader_commit != reader_commit:
                    repaired = held.reader_commit
                elif held.repaired_from_commit is not None:
                    repaired = held.repaired_from_commit
            record = PublicationRecord(
                run_id,
                attempt,
                PublicationState.PENDING,
                reader_commit,
                export_format,
                log_digest,
                object_identity,
                object_digest,
                None if held is None else held.incident,
                repaired,
                self._clock(conn),
            )
            self._write_publication(conn, record)
            self._boundary("before-commit")
            return record

    def publication_published(
        self, run_id: str, attempt: int, *, object_identity: str, object_digest: str
    ) -> PublicationRecord:
        """The pending publication succeeded with this object; a repeat returns the record
        and another object under one record is a conflict (nothing overwrites)."""
        with self._guarded() as conn, conn.transaction():
            held = self._publication(conn, run_id, attempt, lock=True)
            if held is None:
                raise ValueError(f"run {run_id} attempt {attempt} has no publication to publish")
            self._boundary("locked")
            if (held.object_identity, held.object_digest) != (object_identity, object_digest):
                raise LogStoreConflict(
                    f"run {run_id} attempt {attempt}'s publication names another object"
                )
            if held.state is PublicationState.PUBLISHED:
                return held
            record = replace(held, state=PublicationState.PUBLISHED, recorded_at=self._clock(conn))
            self._write_publication(conn, record)
            self._boundary("before-commit")
            return record

    def publication_failed(self, run_id: str, attempt: int, *, incident: str) -> PublicationRecord:
        """The pending publication failed with ``incident``; a published record is never
        changed back and is returned as it stands."""
        with self._guarded() as conn, conn.transaction():
            held = self._publication(conn, run_id, attempt, lock=True)
            if held is None:
                raise ValueError(f"run {run_id} attempt {attempt} has no publication to fail")
            self._boundary("locked")
            if held.state is PublicationState.PUBLISHED:
                return held
            record = replace(
                held,
                state=PublicationState.FAILED,
                incident=incident,
                recorded_at=self._clock(conn),
            )
            self._write_publication(conn, record)
            self._boundary("before-commit")
            return record

    # --- the row, the state and the insert ---------------------------------------------

    def _row(self, conn: Connection, run_id: str, attempt: int) -> _Row:
        row = conn.execute(_SELECT_ATTEMPT, (run_id, attempt)).fetchone()
        if row is None:
            raise ValueError(f"run {run_id} has no attempt {attempt}")
        return _row_of(row)

    def _lock(self, conn: Connection, run_id: str, attempt: int) -> _Row:
        row = conn.execute(_LOCK_ATTEMPT, (run_id, attempt)).fetchone()
        if row is None:
            raise ValueError(f"run {run_id} has no attempt {attempt}")
        return _row_of(row)

    def _receipt(self, conn: Connection, row: _Row, logged: LoggedEvent) -> Received | None:
        """The held event under ``logged``'s identifier: a receipt for equal content, a
        conflict raised for other content, ``None`` when none is held."""
        key = event_key_bytes(logged).decode("utf-8")
        held_row = conn.execute(
            _SELECT_HELD, (row.run_id, row.attempt, kind_of(logged.event).value, key)
        ).fetchone()
        if held_row is None:
            return None
        held = decode_logged_event(held_row[0])
        if event_bytes(held.event) == event_bytes(logged.event):
            return Received(held.position)
        raise LogStoreConflict(
            f"run {row.run_id} attempt {row.attempt} holds another content under the identifier "
            f"of the {kind_of(logged.event).value} at position {held.position}"
        )

    def _events_of(self, conn: Connection, row: _Row) -> tuple[LoggedEvent, ...]:
        rows = conn.execute(_SELECT_EVENTS, (row.run_id, row.attempt)).fetchall()
        return tuple(decode_logged_event(record) for (record,) in rows)

    def _fold(self, conn: Connection, row: _Row, rules: Rules) -> AttemptState:
        try:
            state = fold(self._events_of(conn, row), rules)
        except ValueError as exc:
            raise LogStoreInvariantBroken(
                f"the log of run {row.run_id} attempt {row.attempt} does not fold: {exc}"
            ) from exc
        if not _matches(row, state):
            raise LogStoreInvariantBroken(
                f"the row of run {row.run_id} attempt {row.attempt} (position {row.positions}, "
                f"generation {row.generation}, {row.segments} segments, "
                f"{'closed' if row.closed else 'open'}) disagrees with its log's fold"
            )
        return state

    def _current_state(
        self, conn: Connection, row: _Row, state: AttemptState | None, rules: Rules
    ) -> AttemptState:
        if state is not None and _matches(row, state):
            return state
        return self._fold(conn, row, rules)

    def _insert(
        self,
        conn: Connection,
        after: AttemptState,
        logged: LoggedEvent,
        *,
        claim_nonce: str | None = None,
    ) -> None:
        """The event's row and the counters the state after it gives."""
        inputs = after.inputs
        assert inputs is not None
        conn.execute(
            _INSERT_EVENT,
            (
                inputs.run_id,
                inputs.attempt,
                logged.position,
                kind_of(logged.event).value,
                event_key_bytes(logged).decode("utf-8"),
                claim_nonce,
                logged.timestamp,
                event_digest(logged.event),
                Jsonb(encode_logged_event(logged)),
            ),
        )
        conn.execute(
            _UPDATE_ATTEMPT,
            (
                after.generation,
                len(after.segments),
                after.last_position,
                after.closed is not None,
                inputs.run_id,
                inputs.attempt,
            ),
        )

    # --- the ledger's rows -------------------------------------------------------------

    def _lock_head(self, conn: Connection, ledger_id: str) -> LedgerHead | None:
        row = conn.execute(_LOCK_HEAD, (ledger_id,)).fetchone()
        return None if row is None else _head_of(row)

    def _write_entry(
        self, conn: Connection, ledger_id: str, entry: LedgerEntry, after: LedgerHead, at: datetime
    ) -> None:
        conn.execute(
            _INSERT_ENTRY,
            (
                ledger_id,
                entry.revision,
                entry.kind.value,
                entry.run_id,
                entry.attempt,
                entry.amount_pico_usd,
                entry.total_after_pico_usd,
                entry.authority,
                entry.registration_commit,
                entry.reason,
                at,
            ),
        )
        conn.execute(
            _UPDATE_HEAD,
            (after.total_pico_usd, after.revision, after.threshold_pico_usd, ledger_id),
        )

    # --- the publication's row ---------------------------------------------------------

    def _publication(
        self, conn: Connection, run_id: str, attempt: int, *, lock: bool
    ) -> PublicationRecord | None:
        statement = _LOCK_PUBLICATION if lock else _SELECT_PUBLICATION
        row = conn.execute(statement, (run_id, attempt)).fetchone()
        return None if row is None else _publication_of(row)

    def _write_publication(self, conn: Connection, record: PublicationRecord) -> None:
        conn.execute(
            _UPSERT_PUBLICATION,
            (
                record.run_id,
                record.attempt,
                record.state.value,
                record.reader_commit,
                record.export_format,
                record.log_digest,
                record.object_identity,
                record.object_digest,
                record.incident,
                record.repaired_from_commit,
                record.recorded_at,
            ),
        )

    # --- the connection ----------------------------------------------------------------

    @contextmanager
    def _guarded(self, *, check_version: bool = True) -> Generator[Connection]:
        """The connection for one command: opened and its schema version checked if needed,
        a fault on the way out this module's."""
        if self._connection is None:
            try:
                self._connection = self._connect(self._dsn)
            except psycopg.OperationalError as exc:
                raise LogStoreUnavailable(f"connection refused: {type(exc).__name__}") from exc
            if check_version:
                try:
                    _check_version(self._connection)
                except psycopg.OperationalError as exc:
                    self._drop()
                    raise LogStoreUnavailable(f"statement failed: {type(exc).__name__}") from exc
        try:
            yield self._connection
        except psycopg.OperationalError as exc:
            self._drop()
            raise LogStoreUnavailable(f"statement failed: {type(exc).__name__}") from exc
        except psycopg.errors.IntegrityError as exc:
            raise LogStoreInvariantBroken(
                f"an integrity error under the lock: {type(exc).__name__}"
            ) from exc

    def _drop(self) -> None:
        if self._connection is not None:
            with suppress(psycopg.Error):
                self._connection.close()
            self._connection = None


# --- Rows to values --------------------------------------------------------------------------


def _check_version(conn: Connection) -> None:
    try:
        row = conn.execute(_SELECT_VERSION).fetchone()
    except psycopg.errors.UndefinedTable as exc:
        raise LogStoreInvariantBroken(
            "the log schema is not bootstrapped: no log_schema table; run ensure_schema"
        ) from exc
    if row is None:
        raise LogStoreInvariantBroken("the log schema has no version row; run ensure_schema")
    if int(row[0]) != SCHEMA_VERSION:
        raise LogStoreInvariantBroken(
            f"this code reads and writes log schema version {SCHEMA_VERSION}, the database "
            f"holds version {row[0]}"
        )


def _matches(row: _Row, state: AttemptState) -> bool:
    """Whether ``state`` is the state of ``row``'s log: the same attempt, and every counter
    equal (equal last positions on one append-only log are equal prefixes)."""
    inputs = state.inputs
    return (
        inputs is not None
        and (inputs.run_id, inputs.attempt) == (row.run_id, row.attempt)
        and state.last_position == row.positions
        and state.generation == row.generation
        and len(state.segments) == row.segments
        and (state.closed is not None) == row.closed
    )


def _row_of(row: tuple[Any, ...]) -> _Row:
    run_id, attempt, generation, segments, positions, closed, log_format, ledger_id = row
    return _Row(
        str(run_id),
        int(attempt),
        int(generation),
        int(segments),
        int(positions),
        bool(closed),
        int(log_format),
        None if ledger_id is None else str(ledger_id),
    )


def _head_of(row: tuple[Any, ...]) -> LedgerHead:
    total, revision, threshold = row
    return LedgerHead(int(total), int(revision), None if threshold is None else int(threshold))


def _entry_of(row: tuple[Any, ...]) -> LedgerEntry:
    revision, kind, run_id, attempt, amount, total_after, authority, commit, reason = row
    return LedgerEntry(
        int(revision),
        ledger.EntryKind(str(kind)),
        None if run_id is None else str(run_id),
        None if attempt is None else int(attempt),
        int(amount),
        int(total_after),
        authority=None if authority is None else str(authority),
        registration_commit=None if commit is None else str(commit),
        reason=None if reason is None else str(reason),
    )


def _publication_of(row: tuple[Any, ...]) -> PublicationRecord:
    (
        run_id,
        attempt,
        state,
        reader_commit,
        export_format,
        log_digest,
        object_identity,
        object_digest,
        incident,
        repaired,
        recorded_at,
    ) = row
    assert isinstance(recorded_at, datetime)
    return PublicationRecord(
        str(run_id),
        int(attempt),
        PublicationState(str(state)),
        str(reader_commit),
        int(export_format),
        str(log_digest),
        str(object_identity),
        str(object_digest),
        None if incident is None else str(incident),
        None if repaired is None else str(repaired),
        recorded_at,
    )


def _encode_result(result: AdmissionResult) -> JsonObject:
    if isinstance(result, AdmissionReceipt):
        return {
            "outcome": "admitted",
            "recorded_at": encode_instant(result.recorded_at),
            "ledger_revision": result.ledger_revision,
        }
    return {
        "outcome": "refused",
        "reason": result.reason,
        "ledger_revision": result.ledger_revision,
    }


def _decode_result(run_id: str, attempt: int, value: object) -> AdmissionResult:
    data = as_object(value, "a recorded admission result")
    outcome = string_field(data, "outcome")
    revision_value = field_of(data, "ledger_revision")
    revision = None if revision_value is None else integer_field(data, "ledger_revision")
    if outcome == "admitted":
        expect_fields(data, ("outcome", "recorded_at", "ledger_revision"), "an admission receipt")
        at = decode_instant(field_of(data, "recorded_at"), "recorded_at")
        return AdmissionReceipt(run_id, attempt, at, revision)
    if outcome == "refused":
        expect_fields(data, ("outcome", "reason", "ledger_revision"), "an admission refusal")
        reason = optional_string_field(data, "reason")
        assert reason is not None
        return AdmissionRefusal(run_id, attempt, reason, revision)
    raise LogStoreInvariantBroken(f"a recorded admission result has outcome {outcome!r}")


__all__ = [
    "SCHEMA_VERSION",
    "AdmissionReceipt",
    "AdmissionRefusal",
    "AdmissionRequest",
    "AdmissionResult",
    "AttemptRef",
    "Boundary",
    "Clock",
    "Connect",
    "LedgerView",
    "LogStore",
    "LogStoreConflict",
    "LogStoreInvariantBroken",
    "LogStoreUnavailable",
    "PublicationRecord",
    "PublicationState",
]
