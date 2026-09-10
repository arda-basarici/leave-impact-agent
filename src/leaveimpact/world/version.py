"""The generator version, and the vocabulary fingerprint recorded beside it.

Semantic generation is identified by three inputs — the seed, the parameters and the
generator version (DESIGN, "The generator: pure specification, materialized prose,
frozen world"). The first two are a caller's; the third is this code's own, stamped onto
every specification it produces, because a version a caller could pass would be
provenance a caller could forge. The rule the version exists for: any change that can
alter the organization a seed produces — the drawing algorithm, a default, a table in
``vocabulary`` — bumps it, so "same seed, same params, same version" stays a true
sentence across the project's history.

The vocabulary half of that rule is enforced, not only stated. ``VOCABULARY_DIGEST`` is
the fingerprint of the tables at the current version; a test recomputes it, so editing a
name or a city fails the suite until this file is touched — and a reviewer seeing the
digest re-recorded without a version bump has the whole bug in one diff. The algorithm
half stays convention until the frozen bundle exists: its content hash for a reference
seed becomes the recorded snapshot that catches an unbumped change of any kind.
"""

from __future__ import annotations

from typing import NewType

GeneratorVersion = NewType("GeneratorVersion", str)

GENERATOR_VERSION = GeneratorVersion("1")

VOCABULARY_DIGEST = "68b08d9999816b391fc0bb809facd30d4201bf0bb17844b5026c9ad5da9e4cff"
