"""Every built scenario class by name — the registry the world plan constructs from.

One mapping across the tiers, so the plan rules can name any built class and a class module
stays about its tier: ``structured`` holds the three structured classes, ``fragmented`` the
fragmented ones as they land, and this module only joins them. A name in the vocabulary
with no class here is a class not yet built, which ``PlanRules`` refuses by name.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from leaveimpact.world.construction import ScenarioClass
from leaveimpact.world.fragmented import FRAGMENTED_CLASSES
from leaveimpact.world.scenario import ScenarioClassName
from leaveimpact.world.structured import STRUCTURED_CLASSES

SCENARIO_CLASSES: Mapping[ScenarioClassName, ScenarioClass] = MappingProxyType(
    {**STRUCTURED_CLASSES, **FRAGMENTED_CLASSES}
)
"""Every built class by name, the instances the world plan constructs from."""

__all__ = ["SCENARIO_CLASSES"]
