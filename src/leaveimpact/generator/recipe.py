"""The world recipe: what defines a world, plus the two run controls of the prose stage.

Plain data that both shells of a fresh run read, the job and the audit sheet's throwaway
mode, and that the fresh stage consumes. It lives apart from the configuration boundary
that parses it so that the stage depends on a record and not on the boundary, whose
module opens the object-store writers and the Bedrock client; a stage that knows nothing
of a bucket should not load one on import (the step 17 review).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from leaveimpact.core.ids import WorldVersion
from leaveimpact.world.org import OrgParams

__all__ = ["DEFAULT_ATTEMPT_CAP", "WorldRecipe"]

DEFAULT_ATTEMPT_CAP = 8
"""Fresh attempts per target before the target fails. Four until the first measurement
world (2026-09-15): its hardest target passed on attempt three, which justifies no cap,
since exhaustion compounds across a world's targets while an exhausted run costs only a
re-dispatch of sealing, before any vendor write. Eight is a robustness margin, not a
measured need; a target accepted above attempt four is read as a struggling brief."""


@dataclass(frozen=True, slots=True)
class WorldRecipe:
    """What defines the world, plus the two run controls of the prose stage.

    ``plan_name`` is the rule the world is planned under, a semantic input recorded in
    the world's provenance (the step 15 rulings); ``attempt_cap`` bounds the materializer
    and is recorded in the world's provenance;
    ``resume`` names a sealed realization to continue instead of generating a fresh one
    (the step 14 rulings: before sealing a restart regenerates, after it resumes).
    """

    seed: int
    params: OrgParams
    world_start: date
    attempt_cap: int = DEFAULT_ATTEMPT_CAP
    resume: WorldVersion | None = None
    plan_name: str = "tier1"
