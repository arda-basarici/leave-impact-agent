"""The write side: what the generator's projectors need to realize a world in the four systems.

One production consumer, the projectors, and still a port rather than a seam inside
the generator: declared here, the writers are the type the least-privilege split is
enforced on (the import law lets only ``adapters`` and ``generator`` import this
module) and the shape the in-memory implementation under ``tests`` conforms to, so a
projector is tested against a fake and never against a sandbox. Neither reason is
hexagonal symmetry, which DESIGN rejects.

A writer adds; it never finds. Find-or-create is the projector's — read through the
reader by domain id, add through the writer what is missing — because a writer that
also looked things up would blur the two sides this module exists to separate.
Every ``add_*`` returns the record's locator in the source, an opaque string the
generator records in the world manifest as the receipt of the world it realized;
``core`` never interprets one. Vendor ids otherwise stay inside the adapter, which
keeps the identity map from domain id to vendor key.

What an add does when the source already holds the identity depends on what the
system can promise. Where the vendor mints the key — Jira — or refuses a duplicate name —
Frappe, the corpus — a second add of an existing identity is the projector's bug, and the
projector finds before it adds. The calendar is the exception by construction: its vendor
event id is derived from the domain id, so ``add_event`` is the ensure — an existing copy
equal to the intended event is verified and its locator returned, one that differs raises
``IdentityConflict`` (``errors``) — and the projector inserts without a find.
"""

from __future__ import annotations

from typing import Protocol

from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Leave,
    Team,
    WorkItem,
)


class PeopleWriter(Protocol):
    """Adds people, teams and leaves to the HR system."""

    def add_team(self, team: Team) -> str:
        """Creates the team; returns its locator in the source."""
        ...

    def add_employee(self, employee: Employee) -> str:
        """Creates the employee; the team and the manager exist already. Returns the locator."""
        ...

    def add_leave(self, leave: Leave) -> str:
        """Creates the leave for an existing employee; returns the locator."""
        ...


class WorkWriter(Protocol):
    """Adds components and work items, comments included, to the issue tracker."""

    def add_component(self, component: Component) -> str:
        """Creates the component with its members; returns the locator."""
        ...

    def add_work_item(self, work_item: WorkItem) -> str:
        """Creates the work item with its comments under an existing component.

        Returns the locator.
        """
        ...


class CalendarWriter(Protocol):
    """Adds events to the calendar."""

    def add_event(self, event: CalendarEvent) -> str:
        """One copy on each attendee's calendar, restartable on its own; returns the locator.

        A copy that exists equal to ``event`` is verified, not rewritten; one that differs
        raises ``IdentityConflict``. The locator is the derived vendor id every copy shares.
        """
        ...


class DocumentWriter(Protocol):
    """Adds documents, sections included, to the corpus."""

    def add_document(self, document: Document) -> str:
        """Creates the document with its sections; returns the locator."""
        ...
