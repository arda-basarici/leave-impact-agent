"""The readiness read: whether this process can serve the demo now, from the store and the
deployed revision and nothing else.

The deploy script reads it as its second named check beside the image's identity line
(the entry's HTTP-shell ruling), and the platform's monitor reads it once the proxy
upstream flips to the application. It answers three questions, is the store reachable, does
the cache mark the served world ready, and does the database hold the app schema at this
code's version, and consults no vendor and no model, so a Frappe, Jira or Bedrock outage
never makes the replay surface unavailable; it never loads, repairs or bootstraps anything,
since the cache job, the log bootstrap and the app bootstrap run before the application in
the deploy and a read that mended state would hide a deploy that skipped them. The third
bit is why a skipped app bootstrap fails the deploy at its readiness check instead of
serving errors on the replay pages, and why a database at an older app layout is unready
rather than misread. The store is reached through a fresh connection per read, bounded on
the connect and the statement, so a process that answered "unreachable" during an outage
answers "ready" again by itself when the store returns.

``readiness`` is pure over the two callables, the cache's ready versions and the app
schema's support; the composition root binds them to the corpus adapter's read and the app
store over the deployed database. Two reads on two connections: the route's own worst case
is their bounds summed, twelve seconds, and the probes' eight-second client patience ends
first, which reads as unhealthy exactly as a 503 does and costs one thread until the second
read's bound. The answer names states, never a cause: the exception an unreachable store
raised stays with the process's log, and the body a monitor or a deploy log shows holds the
revision, the served version and three booleans, nothing a connection string or a driver
message could leak through.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.store import AppStoreUnavailable
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.ports.errors import SourceUnreachable

ReadyVersions = Callable[[], frozenset[WorldVersion]]
"""The versions the cache serves now; ``SourceUnreachable`` when the store does not answer."""

AppSchema = Callable[[], bool]
"""Whether the database holds the app schema at this code's version; ``AppStoreUnavailable``
when the store does not answer."""


@dataclass(frozen=True, slots=True)
class Readiness:
    """One readiness read. ``store_reachable`` false means the store did not answer one of
    the two reads, and then ``served_world_ready`` and ``app_schema`` are false by
    construction, never a guess."""

    code_version: str
    served_world_version: WorldVersion
    store_reachable: bool
    served_world_ready: bool
    app_schema: bool

    @property
    def ready(self) -> bool:
        """The deploy's and the monitor's one bit: the store answers, the cache serves the
        allowlisted world and the app schema is at this code's version."""
        return self.store_reachable and self.served_world_ready and self.app_schema

    def as_json(self) -> JsonObject:
        return {
            "ready": self.ready,
            "code_version": self.code_version,
            "served_world_version": self.served_world_version,
            "store_reachable": self.store_reachable,
            "served_world_ready": self.served_world_ready,
            "app_schema": self.app_schema,
        }


def readiness(
    code_version: str,
    configuration: DemoConfiguration,
    ready_versions: ReadyVersions,
    app_schema: AppSchema,
) -> Readiness:
    """Read the store twice and say whether the served world can be served; an unreachable
    store is a state of the answer, not an exception of the caller's."""
    unreachable = Readiness(code_version, configuration.served_world_version, False, False, False)
    try:
        versions = ready_versions()
        supported = app_schema()
    except (SourceUnreachable, AppStoreUnavailable):
        return unreachable
    return Readiness(
        code_version,
        configuration.served_world_version,
        store_reachable=True,
        served_world_ready=configuration.served_world_version in versions,
        app_schema=supported,
    )
