"""The hostname half of the disclosure sweep, pure: which public pages a crawl reads, and
what one fetched body shows against the sweep's two predicates.

The sweep's offline half reads the tree at a commit for the embargoed world's digests and
its structural half is a unit test over the tracked files; neither reads what the edge
serves, and the served page is what a public reader gets: the templates render golden-world
content, the proxy and the edge may add to the body, and a page is the only place the
rendering and the content meet. After the public switch every page is fetched through the
hostname and read with both predicates (the demo milestone's exit step, its third ruling).
This module holds the two decisions a crawl makes with no network: the page list derived
from the listing's own links, so a published attempt is never missed by a hand-kept list,
and the reading of one body, which names the kind of embargoed digest found and never its
value, since the crawl's output is pasted into a public record. The structural patterns are
given to it, not owned: their one home is the gate test, and a second copy would drift.

The external hosts a body references are reported as a fact and not a finding: the pages
link the portfolio site by design, and the edge once injected an analytics script that no
template names, which this reading is what showed.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

__all__ = ["GLOBAL_PATHS", "PageFindings", "crawl_paths", "page_findings", "views_of"]

GLOBAL_PATHS: tuple[str, ...] = ("/", "/results", "/replays", "/ready")
"""The public routes that name no attempt, in the order the crawl reads them."""

ATTEMPT_PATHS: tuple[str, ...] = ("", "/trail", "/timeline", "/events?after=0")
"""An attempt's four surfaces as suffixes of its replay path; the stream from cursor 0, so
a closed attempt's whole narration is one fetched body."""

_LISTED = re.compile(r'href="/replays/([^"/]+)"')

Pattern = tuple[str, re.Pattern[str]]
"""A structural predicate: the name a hit is reported under and the pattern that finds it."""


@dataclass(frozen=True, slots=True)
class PageFindings:
    """What one body showed: the kinds of embargoed digest it holds (named, never valued),
    the structural hits as ``line: what``, and the external hosts its links and sources
    name. A body is clean when the first two are empty."""

    embargoed: tuple[str, ...]
    structural: tuple[str, ...]
    external_hosts: frozenset[str]

    @property
    def clean(self) -> bool:
        return not self.embargoed and not self.structural


def crawl_paths(listing_html: str) -> tuple[str, ...]:
    """Every public path a crawl reads, from the replay listing's own links: the global
    routes, then each listed attempt's four surfaces in listing order, duplicates dropped.

    >>> paths = crawl_paths('<a href="/replays/s-2">x</a> <a href="/replays/s-1">y</a>')
    >>> paths[:4] == GLOBAL_PATHS, len(paths)
    (True, 12)
    >>> paths[4:8]
    ('/replays/s-2', '/replays/s-2/trail', '/replays/s-2/timeline', '/replays/s-2/events?after=0')
    """
    listed = tuple(dict.fromkeys(_LISTED.findall(listing_html)))
    return GLOBAL_PATHS + tuple(
        f"/replays/{public_id}{suffix}" for public_id in listed for suffix in ATTEMPT_PATHS
    )


_FRAME_DATA = re.compile(r"^data: (.*)$", re.MULTILINE)


def _strings_in(value: object) -> list[str]:
    """Every string a decoded JSON value holds, keys included, in document order."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items = cast(dict[str, object], value)
        return [text for key, item in items.items() for text in (key, *_strings_in(item))]
    if isinstance(value, list):
        return [text for item in cast(list[object], value) for text in _strings_in(item)]
    return []


def views_of(body: str) -> tuple[tuple[str, str], ...]:
    """The texts a reader of ``body`` may see, each named: the raw body; its HTML-decoded
    form when entities change it (a template escapes an apostrophe to ``&#39;``, so a
    possessive pattern misses the raw text); and, when the body carries server-sent frames,
    the strings of every ``data:`` payload decoded from JSON, one line per frame (the frame
    encoder writes the ellipsis a cited digest ends in as ``\\u2026``, so the raw text holds
    no cited form). Found by the first external read of the crawl: the raw scan alone passed
    bodies the real encoders had made.

    >>> [name for name, _ in views_of("plain")]
    ['raw']
    >>> dict(views_of("a &#39;b&#39;"))["html-decoded"]
    "a 'b'"
    >>> dict(views_of('id: 1\\nevent: line\\ndata: {"text": "x\\\\u2026"}\\n\\n'))["frame data"]
    'text\\nx…'
    """
    views = [("raw", body)]
    decoded = html.unescape(body)
    if decoded != body:
        views.append(("html-decoded", decoded))
    frames: list[str] = []
    for payload in _FRAME_DATA.findall(body):
        try:
            frames.append("\n".join(_strings_in(json.loads(payload))))
        except ValueError:
            frames.append(payload)
    if frames:
        views.append(("frame data", "\n".join(frames)))
    return tuple(views)


def page_findings(
    body: str, *, embargoed: Mapping[str, Sequence[str]], patterns: Sequence[Pattern]
) -> PageFindings:
    """Read one fetched ``body`` in every view ``views_of`` gives: ``embargoed`` maps the kind
    of digest to the literals that would publish it (the whole value and its cited forms),
    and a kind is reported when any literal occurs in any view; ``patterns`` are the
    structural predicates, applied per line of each view and reported as ``line: what`` for
    the raw body and ``view line: what`` for a decoded one; the external hosts are the
    ``https?://host`` of every ``href`` and ``src`` attribute of the raw body.

    >>> found = page_findings(
    ...     'a <a href="https://example.org/x">b</a>\\nMARKER here',
    ...     embargoed={"semantic digest": ("abcd…",)},
    ...     patterns=(("a marker", re.compile(r"MARKER")),),
    ... )
    >>> found.embargoed, found.structural, sorted(found.external_hosts)
    ((), ('2: a marker',), ['https://example.org'])
    """
    views = views_of(body)
    kinds = tuple(
        kind
        for kind, forms in embargoed.items()
        if any(form in text for _, text in views for form in forms)
    )
    structural = tuple(
        f"{number}: {what}" if name == "raw" else f"{name} {number}: {what}"
        for name, text in views
        for number, line in enumerate(text.splitlines(), start=1)
        for what, pattern in patterns
        if pattern.search(line)
    )
    hosts = frozenset(re.findall(r'(?:href|src)="(https?://[^"/]+)', body))
    return PageFindings(kinds, structural, hosts)
