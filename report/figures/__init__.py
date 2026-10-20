"""The report's figures: scripts that mint each image from the committed results, and the
images they render, committed beside them so a build needs no plotting run.

``mint`` draws every figure from the committed public results file through the
package's own reader, with one data function per figure returning plain tuples and one
drawing function beside it, so what a chart shows can be asserted without rendering.
The instrument diagram is the one figure drawn from no data. Rendered with::

    uv run --group report python -m report.figures.mint
"""
