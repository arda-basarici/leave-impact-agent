"""The modifiers: orthogonal tags that plant a near-miss or press on the candidates, on any class.

A modifier is written once and composes with any class (the modifier ruling at the
scenario-framework step). It has a class's shape minus an outcome: ``admissible`` returns
the amendments the draft affords, in canonical order, and is empty when the draft lacks
the structure it works on; a chosen amendment plants more owned entities and declares
its effect — distractors named with their reason, verdicts amended for a candidate —
and never touches the class's declared outcome, which the framework re-checks after
composition.

This module holds ``already_resolved``, pulled forward with the first class as the
proof that the modifier machinery composes; the others join at the Tier 1 step.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from random import Random

from leaveimpact.core.entities import WorkItem
from leaveimpact.core.enums import WorkItemStatus
from leaveimpact.core.refs import work_item_ref
from leaveimpact.world.construction import Amendment, Draft, Frame
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    DistractorReason,
    ModifierEffect,
    ModifierName,
    NamedDistractor,
    OwnedEntities,
    Planted,
)

RESOLVED_TITLE_SUFFIX = ", phase one"


class AlreadyResolved:
    """A look-alike ticket the leaver already closed: same component, due during the leave, done.

    The near-miss reads as an impact to anyone who filters by owner and due date without
    checking status, and the key names it with the reason so that false positive lands in
    the already-resolved bucket. Admissible over every open ticket the leaver owns in the
    draft, in draft order — a ticket someone else owns is not the leaver's work and would
    make a weak near-miss — so a draft without such a ticket affords nothing.
    """

    name = ModifierName.ALREADY_RESOLVED
    affordance = "an open ticket owned by the leaver"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        leaver = next(
            planted.entity.employee_id
            for planted in draft.owned.leaves
            if planted.entity.id == draft.investigated
        )
        return tuple(
            _amendment(planted.entity)
            for planted in draft.owned.work_items
            if planted.entity.resolved_on is None and planted.entity.owner_id == leaver
        )


def _amendment(open_ticket: WorkItem) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        visible = frame.window.start
        # Resolved before the run's day, so the status and the resolution date agree and
        # no reading of ``now`` inside the stable interval can make it open again. The
        # frame guarantees a day of slice history before now; a frame without one is a
        # placement bug and fails here by name.
        history = (frame.today - visible).days
        if history < 1:
            raise ValueError(
                f"an already-resolved ticket needs a day before now, today is {frame.today}"
            )
        resolved_on = visible + timedelta(days=rng.randrange(history))
        done = replace(
            open_ticket,
            id=frame.ids.work_item(),
            title=open_ticket.title + RESOLVED_TITLE_SUFFIX,
            status=WorkItemStatus.DONE,
            resolved_on=resolved_on,
            due_on=frame.leave.start + timedelta(days=rng.randrange(frame.leave.days)),
            comments=(),
        )
        # Observable from the day it was resolved, not from the slice start: derivation
        # stamps every fact of a record, the status included, with the record's date, and
        # a "done" visible before its own resolution would contradict the world. The
        # earlier open state is not modelled — a state transition is more machinery than
        # this near-miss needs — so the record enters the world already closed.
        planted = OwnedEntities(work_items=(Planted(done, resolved_on),))
        near_miss = NamedDistractor(work_item_ref(done.id), DistractorReason.ALREADY_RESOLVED)
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend
