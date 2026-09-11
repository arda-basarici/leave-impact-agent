"""The bracketed prefix a comment's text opens with: id, world date and speaker, both ways.

A tracker's own author and timestamp on a comment are vendor operational facts (every
write is the service account's, at generation time), so the comment's world date and
speaker live in a fixed prefix of the text the generator writes — DESIGN's "History is
planted only where it can be planted honestly" — and the comment's id joins them there,
because an evidence reference needs a stable target and the tracker's comment id is
vendor identity. The shape is ``[comment_005, 2026-09-12, emp_023 — Bob Kaya] the
remark``: the speaker's display name is for a human reading the board and is not read
back, the id is. Rendering and parsing sit in ``core`` because the generator renders
and the adapter parses, and neither may import the other; both are pure.

An adapter reads the prefix the way it reads a custom field — a format translation, not
an interpretation of the prose — and a text without a well-formed prefix is
untranslatable: ``parse_comment`` raises ``ValueError`` naming what is wrong, which the
adapter turns into ``MalformedRecord`` with the comment's locator. The text stays whole,
prefix included, in the entity.
"""

from __future__ import annotations

import re
from datetime import date

from leaveimpact.core.entities import Comment
from leaveimpact.core.ids import NUMBERED_ID, CommentId, EmployeeId

_PREFIX = re.compile(
    r"^\[(?P<id>comment_[0-9]{3,}), (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}), "
    r"(?P<author>emp_[0-9]{3,}) — (?P<name>[^\]]*)\] ?"
)


def comment_text(
    id: CommentId, world_date: date, author_id: EmployeeId, author_name: str, remark: str
) -> str:
    """The whole text of a comment: the prefix the adapters parse, then the remark.

    >>> from leaveimpact.core.ids import comment_id, employee_id
    >>> comment_text(comment_id(5), date(2026, 9, 12), employee_id(23), "Bob Kaya", "blocked")
    '[comment_005, 2026-09-12, emp_023 — Bob Kaya] blocked'
    """
    if not NUMBERED_ID.match(id) or not NUMBERED_ID.match(author_id):
        raise ValueError(f"a comment prefix needs numbered ids, got {id!r} by {author_id!r}")
    if "]" in author_name:
        raise ValueError(f"a speaker's name cannot close the prefix: {author_name!r}")
    return f"[{id}, {world_date.isoformat()}, {author_id} — {author_name}] {remark}"


def parse_comment(text: str) -> Comment:
    """The comment a whole text describes, its id, date and speaker read from the prefix.

    >>> parsed = parse_comment("[comment_005, 2026-09-12, emp_023 — Bob Kaya] blocked")
    >>> parsed.id, parsed.world_date, parsed.author_id
    ('comment_005', datetime.date(2026, 9, 12), 'emp_023')
    >>> parsed.text
    '[comment_005, 2026-09-12, emp_023 — Bob Kaya] blocked'
    >>> parse_comment("blocked on the vendor")
    Traceback (most recent call last):
    ...
    ValueError: no comment prefix: 'blocked on the vendor'
    """
    match = _PREFIX.match(text)
    if match is None:
        raise ValueError(f"no comment prefix: {text[:60]!r}")
    try:
        world_date = date.fromisoformat(match["date"])
    except ValueError as exc:
        raise ValueError(f"comment prefix date {match['date']!r} is not a date") from exc
    return Comment(CommentId(match["id"]), world_date, EmployeeId(match["author"]), text)
