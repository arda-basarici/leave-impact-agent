"""The two wrappers the crash check puts around the run: the saver with a seam before and after
each of its writes, and the ports with every dispatch witnessed.

``SeamedSaver`` is the accepted workaround's shape (the acceptance spike's ruling 6): public
API only, a subclass that overrides ``put`` and ``put_writes`` and calls the parent, in one
module. ``put_writes`` keeps its ``task_path`` parameter because the framework inspects the
signature for it. Both methods run on the framework's background thread, so these seams fire
there. ``sync`` durability waits for the checkpoint and not for a task's pending writes,
which is why each method has its own seams.

A write is named by what it holds, since checkpoint and task ids are minted from the clock
and differ between runs. A checkpoint is named by its step number. A task's pending writes
are named by the result positions they carry, or by the control channel when they carry an
interrupt or a resume, or else by their channels.

``counted`` wraps the four readers so that each call that reaches a port leaves a line in
the injector's record. The log holds one result per logical read whatever happened, so only
this record can say a read was dispatched twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.postgres import PostgresSaver
from seams import cross, witness

from leaveimpact.agent.execution import ReadPorts


class SeamedSaver(PostgresSaver):
    """The synchronous saver with a seam before and after each write."""

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        operation = f"checkpoint/step={metadata.get('step')}"
        cross(operation, "put:before")
        stored = super().put(config, checkpoint, metadata, new_versions)
        cross(operation, "put:after")
        return stored

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        operation = f"writes/{written(writes)}"
        cross(operation, "put_writes:before")
        super().put_writes(config, writes, task_id, task_path)
        cross(operation, "put_writes:after")


def written(writes: Sequence[tuple[str, Any]]) -> str:
    """The name of a task's pending writes: the result positions they carry, else the control
    channel, else the channels.

    >>> written([("turn", 1), ("results", {"mc-1": "ab"})])
    'mc-1'
    >>> written([("__interrupt__", object())])
    '__interrupt__'
    """
    for channel, value in writes:
        if channel == "results" and isinstance(value, dict) and value:
            return ",".join(sorted(cast("dict[str, str]", value)))
    channels = [channel for channel, _ in writes]
    for control in ("__interrupt__", "__resume__", "__error__"):
        if control in channels:
            return control
    return "+".join(sorted(set(channels))) or "nothing"


class _Counted:
    """A reader whose every method call is witnessed before it is made."""

    def __init__(self, port: object) -> None:
        self._port = port

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._port, name)
        if not callable(attribute):
            return attribute

        def dispatched(*arguments: Any, **named: Any) -> Any:
            witness("tool_dispatch", method=name, arguments=repr((arguments, named)))
            return attribute(*arguments, **named)

        return dispatched


def counted(ports: ReadPorts) -> ReadPorts:
    """``ports`` with every dispatch to a reader witnessed in the injector's record."""
    return ReadPorts(
        cast("Any", _Counted(ports.people)),
        cast("Any", _Counted(ports.work)),
        cast("Any", _Counted(ports.calendar)),
        cast("Any", _Counted(ports.documents)),
    )
