"""Regenerate the API reference with pdoc. Output is generated, never hand-edited.

Run: ``python scripts/regen_docs.py``. The rendered reference lands in ``docs/api``
(git-ignored) and is rebuilt from the docstrings — the single source of truth for the
caller's contract. CI runs the same build, so a module that fails to import fails
the push; doctests are what catch a broken example (DESIGN: "Verification").
"""

from __future__ import annotations

import subprocess
import sys

_PACKAGE = "leaveimpact"
_OUTPUT_DIR = "docs/api"


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "pdoc", _PACKAGE, "-o", _OUTPUT_DIR],
        check=True,
    )


if __name__ == "__main__":
    main()
