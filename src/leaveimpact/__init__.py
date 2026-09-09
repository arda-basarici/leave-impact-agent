"""Leave Impact Agent — investigates the operational impact of employee leave across an
organization's tools and drafts evidence-backed coverage plans for a human to approve.

The package is laid out along the import law in DESIGN's "Package boundaries and the
import law" and ARCHITECTURE's design shape: ``core`` (the domain, pure) below ``world``
(the benchmark, pure) below ``adapters`` (one external boundary each) below the shells
that compose them — ``generator`` and ``validator`` now, ``evaluator`` and ``agent`` at
the investigator milestone, ``app`` at the demo. ``tests/unit/test_import_law.py`` is
the law as a test; a package that breaks it is a red build.
"""
