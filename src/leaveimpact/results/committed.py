"""The committed public results, read by package name so a built image finds them wherever
it runs.

A results file is committed beside this module and ships in the package as the prompt
assets do, so the page that renders it and the smoke that proves the image carries it read
it through the package's resources and never through a path relative to a checkout. The
one file today is the investigator milestone's reported measurement; a later measurement
is a second file beside it, named here, never a rewrite.
"""

from __future__ import annotations

from importlib.resources import files

from leaveimpact.results.codec import decode_public_results
from leaveimpact.results.public import PublicResults

__all__ = ["M2_REPORTED", "committed_results", "committed_results_bytes"]

M2_REPORTED = "m2-reported.json"
"""The investigator milestone's reported measurement: 240 runs over the measurement world."""


def committed_results_bytes(name: str = M2_REPORTED) -> bytes:
    """The bytes of the committed file ``name``, as they are compared by the acceptance
    command; ``FileNotFoundError`` when the package carries no such file."""
    return files("leaveimpact.results").joinpath(name).read_bytes()


def committed_results(name: str = M2_REPORTED) -> PublicResults:
    """The committed results ``name`` holds; ``ValueError`` when the file is not of the
    declared types, which the suite rules out for every committed file."""
    return decode_public_results(committed_results_bytes(name))
