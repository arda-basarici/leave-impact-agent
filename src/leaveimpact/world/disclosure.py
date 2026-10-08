"""The disclosure a world is sealed under: open, or embargoed until its measurements are done.

A measurement world's seed and recipe stay unpublished through the last confirmatory
measurement on it, because the scenario-specs digest and the semantic digest are functions
of the seed and public code alone, so a published digest makes a small seed enumerable
(the arms interview's disclosure rulings, the generator step's ruling 5). The mark is
sealed into the world spec's provenance so that every reader of the sealed world, the
proving command, the evaluation job, the audit sheet, learns from the world itself what it
may print, and not from a flag an operator remembers to pass. It is not what the seed
determines, so it has no place in the semantic encoding: one seed has one semantic digest
whether its world is embargoed or open.

Its own module because the world's assembly carries it on the composed world and the
artifacts module encodes it, and the artifacts module imports the assembly.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Disclosure"]


class Disclosure(StrEnum):
    """``OPEN``, what every world sealed before the mark existed is; ``EMBARGOED``, a world
    whose enumerable digests and retrieval-target counts no public output may carry."""

    OPEN = "open"
    EMBARGOED = "embargoed"
