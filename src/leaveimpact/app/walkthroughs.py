"""The introduced replays' walkthroughs: the operator's prose for the three examples the
listing shows first, one per tier of the served world, committed beside the page that
renders it (the demo milestone's replay step, its sixth fork).

A walkthrough says what to inspect on a replay's page and what to see there, the limitation
or the disagreement the example was chosen for; it is the operator's reading, written after
the offline grading of the replays, and the surface imports no grader to check it. The prose
lives in a committed JSON file keyed by public name, decoded once at the application's
creation through the same injected-reader shape as the results view, so it is reviewed with
the tree, versioned with the template, and needs no column and no schema move. A row is
introduced by its title, which the operator fixes at the publish; the file supplies the prose
for a titled row, a titled row without an entry renders its title alone, and an entry whose
public name has no row is unreachable, never an error, since the file may land before the
operator's session publishes the rows.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files

from leaveimpact.app.public import PublicAttempt, PublicId, public_id_of
from leaveimpact.core.jsonshape import array_field, as_object, expect_fields, string_field

WALKTHROUGHS_FORMAT = 1
WALKTHROUGHS = "walkthroughs.json"
TIERS = ("structured", "fragmented", "adversarial")
"""The served world's three scenario tiers as the surface names them; the surface never
imports the world package, so the names are spelled here and the test over the committed
file holds them to the three."""
_FIELDS = ("format_version", "walkthroughs")
_ENTRY_FIELDS = ("public_id", "tier", "inspect", "see")


@dataclass(frozen=True, slots=True)
class Walkthrough:
    """One introduced replay's prose: its public name, its tier, what to inspect on the
    page, and what to see there."""

    public_id: PublicId
    tier: str
    inspect: str
    see: str


@dataclass(frozen=True, slots=True)
class Introduced:
    """A listing entry shown first, with its walkthrough."""

    entry: PublicAttempt
    walkthrough: Walkthrough


@dataclass(frozen=True, slots=True)
class ListingView:
    """What the listing renders: the introduced entries in the file's order, then every
    published entry of the served world, the introduced ones among them."""

    introduced: tuple[Introduced, ...]
    entries: tuple[PublicAttempt, ...]


def decode_walkthroughs(content: bytes | str) -> tuple[Walkthrough, ...]:
    """The walkthroughs ``content`` states, in the file's order, or ``ValueError`` naming
    the first fault: a format other than this code's (refused first), a missing or unknown
    field, a public name the slug rule refuses, a tier not among the three, an empty text,
    or one public name twice.

    >>> decode_walkthroughs('{"format_version": 2, "walkthroughs": []}')
    Traceback (most recent call last):
    ...
    ValueError: the walkthroughs file is format 1, got 2
    """
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    data = as_object(json.loads(text), "the walkthroughs file")
    version = data.get("format_version")
    if version != WALKTHROUGHS_FORMAT:
        raise ValueError(f"the walkthroughs file is format {WALKTHROUGHS_FORMAT}, got {version!r}")
    expect_fields(data, _FIELDS, "the walkthroughs file")
    decoded: list[Walkthrough] = []
    for position, item in enumerate(array_field(data, "walkthroughs")):
        entry = as_object(item, f"walkthrough {position}")
        expect_fields(entry, _ENTRY_FIELDS, f"walkthrough {position}")
        public_id = public_id_of(string_field(entry, "public_id"))
        tier = string_field(entry, "tier")
        if tier not in TIERS:
            raise ValueError(f"walkthrough {public_id}: tier is one of {list(TIERS)}, got {tier!r}")
        inspect, see = string_field(entry, "inspect"), string_field(entry, "see")
        if not inspect.strip() or not see.strip():
            raise ValueError(f"walkthrough {public_id}: inspect and see are non-empty text")
        if any(earlier.public_id == public_id for earlier in decoded):
            raise ValueError(f"walkthrough {public_id} appears twice")
        decoded.append(Walkthrough(public_id, tier, inspect, see))
    return tuple(decoded)


def committed_walkthroughs_bytes(name: str = WALKTHROUGHS) -> bytes:
    """The committed file's bytes, read by package name so a built image finds it."""
    return files("leaveimpact.app").joinpath(name).read_bytes()


def committed_walkthroughs(name: str = WALKTHROUGHS) -> tuple[Walkthrough, ...]:
    """The committed walkthroughs, decoded; ``ValueError`` if the file is not of the declared
    shape, ``OSError`` if the packaging dropped it."""
    return decode_walkthroughs(committed_walkthroughs_bytes(name))


def walkthrough_for(
    walkthroughs: Iterable[Walkthrough], public_id: PublicId, title: str | None
) -> Walkthrough | None:
    """The walkthrough a page shows for the row ``public_id``: the file's entry when the row
    is introduced (it carries a title) and the file names it; ``None`` otherwise, so an
    untitled row never carries prose written for another publish of the name."""
    if title is None:
        return None
    return next((w for w in walkthroughs if w.public_id == public_id), None)


def listing_view(
    entries: Iterable[PublicAttempt], walkthroughs: Iterable[Walkthrough]
) -> ListingView:
    """The listing over the published ``entries``: the introduced ones first, in the file's
    order, each a titled row the file names; then every entry as the projection gives them.
    An entry the file names that has no titled row is left out of the introduction."""
    entries = tuple(entries)
    by_name = {entry.public_id: entry for entry in entries if entry.title is not None}
    introduced = tuple(
        Introduced(by_name[w.public_id], w) for w in walkthroughs if w.public_id in by_name
    )
    return ListingView(introduced, entries)
