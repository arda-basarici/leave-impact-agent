"""The wiring of the composition root to the real adapters: hosts in, prepared systems out.

``AdapterPreparation`` is the production ``Preparation``: it opens the four adapters on the
hosts it is given, runs the site preparation that needs no checkpoint — Frappe's naming
rule, custom fields, company and skill masters; Jira's project, its mark, the four fields
and the owner options; the corpus schema — and hands the root the configuration that came
out of it. What the root then drives through it is the interleaved part: one calendar per
call against the principal, the four systems on the final calendar map, and the two site
inspections. Every name a world takes here is derived from its version by the root's own
rules, so the entry point supplies hosts and credentials and nothing else.

This module is exercised live, at the first world's projection, and not by unit tests: it
composes adapter calls the wire tests already cover, in the order their docstrings state,
and a fake of it would test the fake. Credentials pass through to the adapters and are never
recorded; the hosts' names reach the manifest as ``observed_sites``, for diagnosis only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

from leaveimpact.adapters.calendar.adapter import (
    CalendarAdapter,
    CalendarConfig,
    CalendarCredential,
    CalendarPrincipal,
)
from leaveimpact.adapters.corpus.adapter import CorpusAdapter, CorpusConfig
from leaveimpact.adapters.frappe.adapter import FrappeAdapter, FrappeCredential
from leaveimpact.adapters.jira.adapter import JiraAdapter, JiraConfig, JiraCredential, JiraSite
from leaveimpact.core.entities import Employee
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId, WorkItemId, WorldVersion
from leaveimpact.generator.projection import Systems
from leaveimpact.generator.realize import (
    Prepared,
    frappe_company,
    jira_project_name,
    world_key,
)
from leaveimpact.world.assembly import WorldSpec


@dataclass(frozen=True, slots=True)
class Hosts:
    """Where the four systems are and how to enter them; the entry point builds it from env."""

    frappe_base_url: str
    frappe_credential: FrappeCredential
    jira_base_url: str
    jira_credential: JiraCredential
    calendar_credential: CalendarCredential
    corpus_dsn: str


class AdapterPreparation:
    """The production preparation: real adapters on real hosts, closed when the run ends."""

    def __init__(self, hosts: Hosts, world: WorldSpec, version: WorldVersion) -> None:
        self._hosts = hosts
        self._world = world
        self._version = version
        self._key = world_key(version)
        self._frappe = FrappeAdapter(
            base_url=hosts.frappe_base_url,
            credential=hosts.frappe_credential,
            config=frappe_company(version),
        )
        self._site = JiraSite(base_url=hosts.jira_base_url, credential=hosts.jira_credential)
        self._principal = CalendarPrincipal(credential=hosts.calendar_credential)
        self._corpus = CorpusAdapter(dsn=hosts.corpus_dsn, config=CorpusConfig(version))
        self._jira: JiraAdapter | None = None
        self._calendar: CalendarAdapter | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        for adapter in (
            self._frappe,
            self._site,
            self._principal,
            self._corpus,
            self._jira,
            self._calendar,
        ):
            if adapter is not None:
                adapter.close()

    def prepare(self) -> Prepared:
        """The site preparation that needs no checkpoint, in the order each system needs."""
        org = self._world.org
        self._frappe.ensure_site_schema()
        self._frappe.ensure_company()
        self._frappe.ensure_skills(org.skills)
        key = self._key
        self._site.ensure_project(
            key, jira_project_name(self._version), world_version=self._version
        )
        self._site.mark_project(key, self._version)
        fields = self._site.ensure_fields(key)
        self._site.ensure_owner_options(
            fields, key, [(employee.id, employee.name) for employee in org.employees]
        )
        jira = JiraConfig(key, fields)
        self._jira = JiraAdapter(
            base_url=self._hosts.jira_base_url, credential=self._hosts.jira_credential, config=jira
        )
        self._corpus.ensure_schema()
        return Prepared(
            frappe=self._frappe.config,
            jira=jira,
            observed_sites={
                Source.FRAPPE: urlsplit(self._hosts.frappe_base_url).hostname or "",
                Source.JIRA: urlsplit(self._hosts.jira_base_url).hostname or "",
            },
        )

    def ensure_calendar(self, employee: Employee, known: str | None) -> str:
        remembered = {} if known is None else {employee.id: known}
        made = self._principal.ensure_calendars([employee], naming=self._key, known=remembered)
        return made[employee.id]

    def systems(self, calendars: CalendarConfig) -> Systems:
        if self._jira is None:
            raise LookupError("prepare() runs before systems()")
        self._calendar = CalendarAdapter(
            credential=self._hosts.calendar_credential, config=calendars
        )
        return Systems(self._frappe, self._jira, self._calendar, self._corpus)

    def held_employee_numbers(self, world_ids: Iterable[EmployeeId]) -> frozenset[EmployeeId]:
        return self._frappe.held_employee_numbers(world_ids)

    def held_markers(self) -> frozenset[WorkItemId]:
        if self._jira is None:
            raise LookupError("prepare() runs before held_markers()")
        return self._site.held_markers(self._key, self._jira.config.fields)
