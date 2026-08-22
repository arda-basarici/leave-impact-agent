"""Regenerate the API reference with pdoc. Output is generated, never hand-edited.

Run: ``python scripts/regen_docs.py``. The rendered reference lands in ``docs/api``
(git-ignored) and is rebuilt from the docstrings — the single source of truth for the
caller's contract. Committed as a scaffold at bootstrap; the package name below is a
placeholder until the first code lands (rename here is the one touch-point).
"""

from __future__ import annotations

import subprocess
import sys

_PACKAGE = "leaveimpact"  # placeholder — finalize when the package is created
_OUTPUT_DIR = "docs/api"


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "pdoc", _PACKAGE, "-o", _OUTPUT_DIR],
        check=True,
    )


if __name__ == "__main__":
    main()
