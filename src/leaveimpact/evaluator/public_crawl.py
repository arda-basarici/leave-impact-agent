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

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = ["GLOBAL_PATHS", "PageFindings", "crawl_paths", "page_findings"]

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


def page_findings(
    body: str, *, embargoed: Mapping[str, Sequence[str]], patterns: Sequence[Pattern]
) -> PageFindings:
    """Read one fetched ``body``: ``embargoed`` maps the kind of digest to the literals that
    would publish it (the whole value and its cited forms), and a kind is reported when any
    literal occurs; ``patterns`` are the structural predicates, applied per line and reported
    as ``line: what``; the external hosts are the ``https?://host`` of every ``href`` and
    ``src`` attribute.

    >>> found = page_findings(
    ...     'a <a href="https://example.org/x">b</a>\\nMARKER here',
    ...     embargoed={"semantic digest": ("abcd…",)},
    ...     patterns=(("a marker", re.compile(r"MARKER")),),
    ... )
    >>> found.embargoed, found.structural, sorted(found.external_hosts)
    ((), ('2: a marker',), ['https://example.org'])
    """
    kinds = tuple(kind for kind, forms in embargoed.items() if any(form in body for form in forms))
    structural = tuple(
        f"{number}: {what}"
        for number, line in enumerate(body.splitlines(), start=1)
        for what, pattern in patterns
        if pattern.search(line)
    )
    hosts = frozenset(re.findall(r'(?:href|src)="(https?://[^"/]+)', body))
    return PageFindings(kinds, structural, hosts)
