"""The milestone report: committed Markdown chapters rendered to one PDF, every figure the
prose states read from the record that holds it at build time.

The tree: ``chapters/`` holds the prose, one file per chapter in file order; ``figures/``
holds the scripts that mint each figure from the committed results and the images they
render; ``markup`` parses a chapter's deliberately small Markdown subset; ``pins`` reads
every figure a chapter may state from the committed results file, the bound registration
and the recorded FINDINGS rows; ``generate`` is the build. The package sits outside
``src`` on purpose: it is not the product, the image never carries it, and its
dependencies live in the ``report`` group alone. The rulings behind the shape are
the demo milestone's second step's, made 2026-10-20.
"""
