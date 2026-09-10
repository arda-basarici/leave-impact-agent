"""The generator version, the interpreter it was recorded under, and the vocabulary fingerprint.

Semantic generation is identified by three inputs — the seed, the parameters and the
generator version (DESIGN, "The generator: pure specification, materialized prose,
frozen world"). The first two are a caller's; the third is this code's own, stamped onto
every specification it produces, because a version a caller could pass would be
provenance a caller could forge. The rule the version exists for: any change that can
alter the organization a seed produces — the drawing algorithm, a default, a table in
``vocabulary``, the interpreter — bumps it, so "same seed, same params, same version"
stays a true sentence across the project's history.

The interpreter is on that list because the generator draws through ``random``'s
higher-level operations (``sample``, ``shuffle``, ``choices``), and Python guarantees
only the raw ``random()`` stream across versions; the algorithms above it may change
between minor releases. ``GENERATOR_PYTHON`` names the minor version the current
generator version was recorded under, and a test compares it with the running
interpreter, so a Python upgrade fails the suite until someone inspects what the
generator now produces, bumps the version, and re-cuts the frozen worlds — the same
sequence a code change follows, instead of a silent re-cut.

The vocabulary half of the rule has the same visibility. ``VOCABULARY_DIGEST`` is the
fingerprint of the tables at the current version; a test recomputes it, so editing a
name or a city fails the suite until this file is touched, and the diff then shows
whether the version moved with the digest. Neither check can prove a bump happened —
that stays with review until the frozen bundle exists, whose content hash for a
reference seed becomes the recorded snapshot that catches an unbumped change of any
kind.
"""

from __future__ import annotations

from typing import NewType

GeneratorVersion = NewType("GeneratorVersion", str)

GENERATOR_VERSION = GeneratorVersion("1")

GENERATOR_PYTHON = (3, 13)

VOCABULARY_DIGEST = "68b08d9999816b391fc0bb809facd30d4201bf0bb17844b5026c9ad5da9e4cff"
