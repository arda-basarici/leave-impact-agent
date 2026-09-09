"""The materializer's models over Bedrock: the writer that turns a brief into text and
the independent checker — a different model family and prompt — that extracts the
text's propositions for the containment gate. Behind a renderer seam so the unit
level runs a fake and the real call carries the ``live`` marker.
"""
