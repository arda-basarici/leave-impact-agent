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
that stays with review, backed by the snapshot pair: a reference seed's *semantic digest*
recorded beside the generator version, which catches an unbumped change of any kind to
what the seed determines. The realized bundle's hash is not the pinned value, since the
prose step made it non-deterministic by design; the semantic digest is what two runs of
one seed share (the step 14 rulings).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import NewType

GeneratorVersion = NewType("GeneratorVersion", str)

GENERATOR_VERSION = GeneratorVersion("5")

GENERATOR_PYTHON = (3, 13)

VOCABULARY_DIGEST = "68b08d9999816b391fc0bb809facd30d4201bf0bb17844b5026c9ad5da9e4cff"

_PROMPT_DIGESTS = {
    "checker_system": "7c6855a92edacf09904b05cc13cf5e76863c0d9086f5cea8150f90f89493ff04",
    "register_client_note": "68526a6a012e822668d839ea35d3f6d25950f5ff9cca680ffbe4ba1ed2b51a52",
    "register_policy": "da31a905c3e09788d68c317082d03161ccaa1fbe29fb666eb1c1048128f07367",
    "register_procedure": "0393d97754189a1edeba0430662bb33e0b29d3575debabb210336994cb48b1ed",
    "register_runbook": "a5b63408d2804cd8af514d685de7bdbe20ce1309bffde005ca3e0066df28a4e8",
    "register_ticket_comment": "7a96a63d0320c238c61a519a259324eba7c00023bded910f904458d2077e6c1f",
    "writer_system": "82a29a3b8db4d0d70623433ee98f6a1d24d0cee43ae4f7c59d38212b0fdc0196",
}

PROMPT_DIGESTS: Mapping[str, str] = MappingProxyType(_PROMPT_DIGESTS)
"""The prompt assets worlds are written under, by name. An identity-bearing prompt change
re-pins these deliberately (the step 14 rulings); the assets ship with the generator, whose
test computes their digests against this table."""
