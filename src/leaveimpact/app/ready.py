"""The readiness read: whether this process can serve the demo now, from the store and the
deployed revision and nothing else.

The deploy script reads it as its second named check beside the image's identity line
(the entry's HTTP-shell ruling), and the platform's monitor reads it once the proxy
upstream flips to the application. It answers two questions, is the store reachable and
does the cache mark the served world ready, and consults no vendor and no model, so a
Frappe, Jira or Bedrock outage never makes the replay surface unavailable; it never loads,
repairs or bootstraps anything, since the cache job and the log bootstrap run before the
application in the deploy and a read that mended state would hide a deploy that skipped
them. The store is reached through a fresh connection per read under the loader's connect
timeout, so a process that answered "unreachable" during an outage answers "ready" again
by itself when the store returns.

``readiness`` is pure over the callable that lists the ready versions; the composition root
binds it to the loader's read over the deployed database. The answer names states, never a
cause: the exception an unreachable store raised stays with the process's log, and the
body a monitor or a deploy log shows holds the revision, the served version and two
booleans, nothing a connection string or a driver message could leak through.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.app.config import DemoConfiguration
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.ports.errors import SourceUnreachable

ReadyVersions = Callable[[], frozenset[WorldVersion]]
"""The versions the cache serves now; ``SourceUnreachable`` when the store does not answer."""


@dataclass(frozen=True, slots=True)
class Readiness:
    """One readiness read. ``store_reachable`` false means the store did not answer, and
    then ``served_world_ready`` is false by construction, never a guess."""

    code_version: str
    served_world_version: WorldVersion
    store_reachable: bool
    served_world_ready: bool

    @property
    def ready(self) -> bool:
        """The deploy's and the monitor's one bit: the store answers and the cache serves the
        allowlisted world."""
        return self.store_reachable and self.served_world_ready

    def as_json(self) -> JsonObject:
        return {
            "ready": self.ready,
            "code_version": self.code_version,
            "served_world_version": self.served_world_version,
            "store_reachable": self.store_reachable,
            "served_world_ready": self.served_world_ready,
        }


def readiness(
    code_version: str, configuration: DemoConfiguration, ready_versions: ReadyVersions
) -> Readiness:
    """Read the store once and say whether the served world can be served; an unreachable
    store is a state of the answer, not an exception of the caller's."""
    try:
        versions = ready_versions()
    except SourceUnreachable:
        return Readiness(code_version, configuration.served_world_version, False, False)
    return Readiness(
        code_version,
        configuration.served_world_version,
        store_reachable=True,
        served_world_ready=configuration.served_world_version in versions,
    )
