"""The driver that brings a run attempt to its terminal state from wherever the two stores
stand: a fresh attempt, one a killed process left behind, or one already complete.

A first execution and a recovery are the same procedure, since a process cannot know which
it is except by reading the stores. The driver reads the checkpoint store and the graph's
state, takes one step, and reads again:

- *No checkpoint exists:* the graph is run from its start. Whatever the log already holds
  is replayed by the nodes, not executed again.
- *A checkpoint exists and nothing is next:* one of two states, and "nothing next" alone
  does not tell them apart, since the framework lists as next only the tasks that have no
  saved writes.
  The run is complete when the checkpoint's state holds the terminal event's digest, and the
  driver requires the log to hold that event; a checkpoint that says complete without it
  is a failed invariant, not a state to repair.
  Or the step's tasks all have their pending writes saved and the checkpoint that would
  apply them was never written, which is where a kill before a checkpoint's write leaves a
  run: the snapshot still has tasks, and the graph is continued, which applies the writes
  and writes the checkpoint. This is asked before completeness, because the snapshot's
  values already show the saved writes applied: after a kill before the last checkpoint
  they show the terminal digest while no durable checkpoint holds it. A kill between the
  input's checkpoint and the next one, with the input's writes saved, is this state too.
- *An interrupt is outstanding:* it must be the approval's, alone. When the log already
  holds the approval event the graph is resumed with it and nothing is appended, which is
  what one approval event per run means after a crash between the event's commit and the
  resume; otherwise the approval is delivered.
- *Anything else is next:* the graph is continued from its checkpoint. That includes the
  approval node being next with no interrupt outstanding, which means the process died
  before the node reached its interrupt: no approval is delivered to a graph that has not
  asked for one.

Whether a checkpoint exists is asked of the saver, apart from what is next, since an empty
``next`` is also what a thread with no checkpoint shows.
"""

from __future__ import annotations

from typing import Any

from eventlog import APPROVAL, RUN_TERMINAL, EventLog
from graph import DURABILITY, deliver_approval, resume_with, run_to_interrupt
from langgraph.checkpoint.postgres import PostgresSaver

STEP_CEILING = 12
"""A driver that keeps finding something to do stops here; a healthy recovery takes three."""


def drive(graph: Any, log: EventLog, saver: PostgresSaver, thread: str) -> list[str]:
    """Bring the attempt on ``thread`` to its terminal state; the steps taken, in order.

    Raises ``RuntimeError`` when a complete checkpoint disagrees with the log, when an
    interrupt other than the one approval is outstanding, or when the ceiling is reached.
    """
    config = {"configurable": {"thread_id": thread}}
    taken: list[str] = []
    for _ in range(STEP_CEILING):
        if saver.get_tuple(config) is None:  # type: ignore[arg-type]
            taken.append("ran from the start")
            run_to_interrupt(graph, thread)
            continue
        state = graph.get_state(config)
        if not state.next:
            terminal = log.find(RUN_TERMINAL, "1")
            checkpointed = state.values.get("results", {}).get(RUN_TERMINAL)
            if state.tasks:
                taken.append("continued from a step whose writes were saved, its checkpoint not")
                graph.invoke(None, config, durability=DURABILITY)
                continue
            if terminal is None or terminal.digest != checkpointed:
                raise RuntimeError(
                    f"the checkpoint is complete with terminal digest {checkpointed}, the log "
                    f"holds {None if terminal is None else terminal.digest}"
                )
            taken.append("found complete")
            return taken
        if state.interrupts:
            if state.next != ("approval",) or len(state.interrupts) != 1:
                raise RuntimeError(
                    f"{len(state.interrupts)} interrupts outstanding with {state.next} next; "
                    "the run has one, the approval's"
                )
            approval = log.find(APPROVAL, "1")
            if approval is None:
                taken.append("delivered the approval")
                deliver_approval(graph, log, thread)
            else:
                taken.append("resumed with the logged approval")
                resume_with(graph, approval.event_id, thread)
            continue
        taken.append(f"continued from the checkpoint before {','.join(state.next)}")
        graph.invoke(None, config, durability=DURABILITY)
    raise RuntimeError(f"the driver took {STEP_CEILING} steps without reaching the end: {taken}")
