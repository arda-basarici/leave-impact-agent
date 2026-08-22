"""The baseline's only test: the package imports and carries its contract docstring.

It exists so every gate in CI — lint, types, tests, doctests, docs — runs against
something real from the first commit, instead of passing vacuously on an empty tree.
"""

import leaveimpact


def test_package_imports_with_docstring() -> None:
    assert leaveimpact.__doc__ is not None
    assert "coverage plans" in leaveimpact.__doc__
