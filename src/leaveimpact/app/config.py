"""The demo's own configuration: the one world the surface serves, the registered system
it runs for a visitor, the money and time it may spend, and the flag that keeps live runs
off; a committed file of this package, read by package name, and its strict decoder.

The entry's visitor-run ruling made the demo's configuration its own file so that the
investigator milestone's bound files are never edited for the demo, and the amendment to
the world's admission made the served world an allowlist of one named here by version,
since the sealed disclosure mark lives in an object the instance cannot read. The values
are the rulings' values: the golden world, the registered investigator at the base level
under the frozen registration named by its digest, the region its model is called in
and priced under, the demo's own ledger apart from the measurement's, five admissions a
UTC day, a fifteen-minute approval wait, a wall-clock bound on a running attempt beside
the registered caps, and live runs off.

The region is the cell's third coordinate beside the system and the level (format 2,
the live-path commands step): the planner prices a visitor's run under the table's rates
for it and the worker calls the model there, one value for both, as the operator's
lifecycle passes one ``REGION`` to its plan and its work. It is not read from the
object store's region name, which the store wiring forbids beside a local twin's root,
so a laptop serving from the twin would have had no region to plan under.

**Off means no new public admissions and nothing else.** With ``live_runs`` false the start
command admits no visitor's attempt; replay pages, the results page, the narration of
recorded attempts, publication and the sweeper's reconciliation of attempts already
admitted all keep working, since a flag that silenced them would hide the state the
operator needs to see while the live path is being proven. The commands of the live path
enforce the contract; this module states it. Flipping the flag is a commit and a deploy
through the production gate, so every flip is a recorded act with the image's provenance.

The decoder refuses a field it does not know, a missing one, a value of the wrong JSON type
and a value that is well-typed and meaningless (a digest that is not 64 hex characters, a
count or a bound below one, a system the evaluator does not grade); the test over the
committed file holds what the decoder cannot know alone, that the digest names the
committed registration, that the system and level form one of its cells, and that the
served world is not the measurement world.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files

from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import (
    JsonObject,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    integer_field,
    string_field,
)
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id

DEMO_CONFIGURATION_FORMAT = 2
DEMO = "demo.json"
_FIELDS = (
    "format_version",
    "served_world_version",
    "frappe_base_url",
    "system",
    "level",
    "region",
    "registration_digest",
    "ledger_id",
    "daily_admissions",
    "approval_wait_seconds",
    "attempt_wall_seconds",
    "live_runs",
)


@dataclass(frozen=True, slots=True)
class DemoConfiguration:
    """What the demo serves and spends, as the committed file states it.

    ``served_world_version`` is the allowlist of one: the surface serves this version when
    the cache marks it ready and no other. ``frappe_base_url`` is the HR site of that world
    (the tracker site serves every world and is the platform contract's). ``system`` and
    ``level`` name the registered cell a visitor's run is admitted to under the
    registration ``registration_digest`` names, and ``region`` is where its model is called
    and priced. ``ledger_id`` is the demo's ledger, never
    the measurement's. ``daily_admissions`` bounds public starts per UTC day;
    ``approval_wait_seconds`` is how long an attempt waits at the approval before the
    sweeper closes it; ``attempt_wall_seconds`` bounds a running attempt's wall clock beside
    the registered call and token caps. ``live_runs`` false admits no visitor's attempt.
    """

    served_world_version: WorldVersion
    frappe_base_url: str
    system: SystemKind
    level: str
    region: str
    registration_digest: str
    ledger_id: str
    daily_admissions: int
    approval_wait_seconds: int
    attempt_wall_seconds: int
    live_runs: bool

    def __post_init__(self) -> None:
        require_digest(self.served_world_version, "the served world version")
        require_digest(self.registration_digest, "the registration digest")
        require_opaque_id(self.ledger_id, "the demo's ledger id")
        require_opaque_id(self.level, "the registered level")
        require_opaque_id(self.region, "the region")
        require_integer(self.daily_admissions, "the daily admissions", minimum=1)
        require_integer(self.approval_wait_seconds, "the approval wait", minimum=1)
        require_integer(self.attempt_wall_seconds, "the attempt's wall bound", minimum=1)
        if not self.frappe_base_url.startswith("https://") or self.frappe_base_url.endswith("/"):
            raise ValueError(
                "the HR site is an https URL without a trailing slash, "
                f"got {self.frappe_base_url!r}"
            )


def encode_demo_configuration(configuration: DemoConfiguration) -> JsonObject:
    """The configuration as JSON data in the file's field order."""
    return {
        "format_version": DEMO_CONFIGURATION_FORMAT,
        "served_world_version": configuration.served_world_version,
        "frappe_base_url": configuration.frappe_base_url,
        "system": configuration.system.value,
        "level": configuration.level,
        "region": configuration.region,
        "registration_digest": configuration.registration_digest,
        "ledger_id": configuration.ledger_id,
        "daily_admissions": configuration.daily_admissions,
        "approval_wait_seconds": configuration.approval_wait_seconds,
        "attempt_wall_seconds": configuration.attempt_wall_seconds,
        "live_runs": configuration.live_runs,
    }


def demo_configuration_bytes(configuration: DemoConfiguration) -> bytes:
    """The one written form: canonical bytes of the encoding, what the committed file holds."""
    return canonical_bytes(encode_demo_configuration(configuration))


def decode_demo_configuration(content: bytes | str) -> DemoConfiguration:
    """The configuration ``content`` states, or ``ValueError`` naming the first field that is
    missing, unknown, of the wrong type or meaningless; a format other than this code's is
    refused first.

    >>> decode_demo_configuration('{"format_version": 1}')
    Traceback (most recent call last):
    ...
    ValueError: the demo configuration is format 2, got 1
    """
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    data = as_object(json.loads(text), "the demo configuration")
    version = data.get("format_version")
    if version != DEMO_CONFIGURATION_FORMAT:
        raise ValueError(
            f"the demo configuration is format {DEMO_CONFIGURATION_FORMAT}, got {version!r}"
        )
    expect_fields(data, _FIELDS, "the demo configuration")
    system = string_field(data, "system")
    if system not in {kind.value for kind in SystemKind}:
        raise ValueError(f"system is one of {[kind.value for kind in SystemKind]}, got {system!r}")
    live = field_of(data, "live_runs")
    if not isinstance(live, bool):
        raise ValueError(f"live_runs is a boolean, got {type(live).__name__}")
    return DemoConfiguration(
        served_world_version=WorldVersion(string_field(data, "served_world_version")),
        frappe_base_url=string_field(data, "frappe_base_url"),
        system=SystemKind(system),
        level=string_field(data, "level"),
        region=string_field(data, "region"),
        registration_digest=string_field(data, "registration_digest"),
        ledger_id=string_field(data, "ledger_id"),
        daily_admissions=integer_field(data, "daily_admissions"),
        approval_wait_seconds=integer_field(data, "approval_wait_seconds"),
        attempt_wall_seconds=integer_field(data, "attempt_wall_seconds"),
        live_runs=live,
    )


def committed_configuration_bytes(name: str = DEMO) -> bytes:
    """The committed file's bytes, read by package name so a built image finds it wherever
    it runs."""
    return files("leaveimpact.app").joinpath(name).read_bytes()


def committed_configuration(name: str = DEMO) -> DemoConfiguration:
    """The committed configuration, decoded; ``ValueError`` if the file is not of the
    declared shape, ``OSError`` if the packaging dropped it."""
    return decode_demo_configuration(committed_configuration_bytes(name))
