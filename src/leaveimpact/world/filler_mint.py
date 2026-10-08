"""The filler pool minted after the whole assembly: documents shaped like the planted kinds, titled
over a fictional name book, each section a brief that admits decoys and nothing of the world.

Filler is the corpus a run must read past, and it is built to be read past honestly (the
generator step's rulings 2 and 3). Every filler document is a *requirement* document: shaped
like the planted runbooks, policies, notes and procedures, about a fictional release or a
fictional client, and allowed to state what that artifact requires of whoever does its work.
A near miss is what a retrieval has to tell apart from the clause that answers the question.
Ruling 2 planned a second composition beside it, handbook prose about the organization's
practice that names nothing; four probe rounds on 2026-10-08 found the checker reading such a
text as one that names nobody as responsible and recording that as a proposition it cannot
resolve, on ten of ten texts and still on seven of nine under an amended checker prompt, so
no section of it could pass the gate inside the attempt cap. The composition was dropped on
that measurement and the handbook texts stay in the record for the day the checker is
revisited. Requirement documents alternate a release and a client, and the templates cycle,
so the seed decides the names and nothing else is left to chance.

The pool is minted last, from the world's own id book and a generator derived from the
world's after its final draw, so every planted id and record is what the seed produces
without filler and the stripped world equals the pool-less one field for field (ruling 6).
The name book is the vocabulary's, disjoint from every planted table by a static test, and
this module holds the third guard anyway: every fictional form and every filler title is
checked against the world's lexicon, as a form and as a substring of or around a titled
form, and a hit is a construction error. The static test makes the guard unreachable; the
guard is the structural statement that no filler can name the world. A fictional release
gets a work-item id from a range the minting book never reaches, so the checker's entity
list resolves it and no planted record can share it; a fictional client is a client form
alone, since a client is a name and nothing more in this world.

Capacity is the products' size, release names by release templates and client names by
client templates; a plan past it fails loud through the book, as a ticket context does when
its titles run out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from random import Random

from leaveimpact.core.anchors import SKILL_KIND, SurfaceForm
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import DocumentKind, EntityKind
from leaveimpact.core.ids import work_item_id
from leaveimpact.core.skills import SKILLS
from leaveimpact.world.briefs import (
    FICTIONAL_ID_BASE,
    FillerBrief,
    Register,
    client_id,
    filler_brief_for,
    lexicon_of,
)
from leaveimpact.world.construction import ConstructionError, Minting
from leaveimpact.world.levels import BASE_LEVELS, FillerPlan, SealedLevel
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.prose import CLIENT_KIND
from leaveimpact.world.scenario import Planted, Scenario
from leaveimpact.world.vocabulary import (
    CLIENT_TITLES,
    FICTIONAL_CLIENTS,
    FICTIONAL_RELEASES,
    RELEASE_TITLES,
)

SKILLS_PER_BRIEF = 3
"""How many of the world's skills a requirement brief admits: a short draw, since the writer
handed the whole list wrote a person holding every one (the group 0 containment probe)."""


class FillerExhausted(ConstructionError):
    """The plan asks for more filler documents than one book can title."""


class FillerNamesTheWorld(ConstructionError):
    """A fictional form or a filler title equals, contains or sits inside a form of the world."""


@dataclass(frozen=True, slots=True)
class MintedFiller:
    """What the mint hands the assembly: the pool in rank order, its briefs, the sealed levels."""

    filler: tuple[Planted[Document], ...]
    briefs: tuple[FillerBrief, ...]
    levels: tuple[SealedLevel, ...]


def mint_filler(
    ids: Minting,
    rng: Random,
    plan: FillerPlan,
    org: OrgSpec,
    scenarios: Sequence[Scenario],
    world_start: date,
) -> MintedFiller:
    """The pool ``plan`` asks for, minted from ``ids`` after every planted record and drawn
    with ``rng``, the generator derived for the pool alone; every document is observable from
    ``world_start``. ``FillerExhausted`` when a book runs out, ``FillerNamesTheWorld`` when a
    fictional form or a title meets the world's lexicon."""
    levels = (*BASE_LEVELS, *plan.levels)
    if plan.documents == 0:
        return MintedFiller((), (), levels)
    world_forms = lexicon_of(
        org,
        [p.entity for s in scenarios for p in s.owned.work_items],
        [p.entity for s in scenarios for p in s.owned.documents],
        [p.entity for s in scenarios for p in s.owned.events],
    ).forms()
    skills = [SurfaceForm(SKILL_KIND, s.id, s.name) for s in SKILLS if s.id in org.skills]
    releases = _Book("release", FICTIONAL_RELEASES, RELEASE_TITLES, rng)
    clients = _Book("client", FICTIONAL_CLIENTS, CLIENT_TITLES, rng)
    pool: list[Planted[Document]] = []
    briefs: list[FillerBrief] = []
    for position in range(plan.documents):
        book = releases if position % 2 == 0 else clients
        name, kind, title = book.take()
        fictional = _fictional_forms(book, name)
        _refuse_world_names(title, fictional, world_forms)
        document = Document(ids.document(), title, kind, world_start, ())
        drawn = tuple(rng.sample(skills, min(SKILLS_PER_BRIEF, len(skills))))
        for index in range(plan.sections_per_document):
            briefs.append(
                filler_brief_for(
                    document, ids.clause(), index, Register.FILLER_REQUIREMENT, fictional, drawn
                )
            )
        pool.append(Planted(document, world_start))
    return MintedFiller(tuple(pool), tuple(briefs), levels)


class _Book:
    """One name book's supply of (name, kind, title) rows, shuffled once by the pool's generator
    and handed out without replacement."""

    def __init__(
        self,
        label: str,
        names: tuple[str, ...],
        templates: tuple[tuple[str, str], ...],
        rng: Random,
    ) -> None:
        self.label = label
        self.names = names
        rows = [
            (name, DocumentKind(kind), template.format(name=name))
            for kind, template in templates
            for name in names
        ]
        rng.shuffle(rows)
        self._rows = rows
        self.capacity = len(rows)

    def take(self) -> tuple[str, DocumentKind, str]:
        if not self._rows:
            raise FillerExhausted(
                f"the {self.label} book is exhausted after {self.capacity} filler titles"
            )
        return self._rows.pop()


def _fictional_forms(book: _Book, name: str) -> tuple[SurfaceForm, ...]:
    """The forms a document about ``name`` may use: a release as a work item outside the world's
    id space, a client as a client name."""
    if book.label == "release":
        number = FICTIONAL_ID_BASE + book.names.index(name)
        return (SurfaceForm(EntityKind.WORK_ITEM.value, work_item_id(number), f"{name} release"),)
    return (SurfaceForm(CLIENT_KIND, client_id(name), name),)


def _refuse_world_names(
    title: str, fictional: Sequence[SurfaceForm], world_forms: Sequence[SurfaceForm]
) -> None:
    titled = {EntityKind.WORK_ITEM.value, EntityKind.EVENT.value, EntityKind.DOCUMENT.value}
    problems: list[str] = []
    own = [("title", title.casefold()), *(("form", form.form.casefold()) for form in fictional)]
    for form in world_forms:
        spelled = form.form.casefold()
        for label, text in own:
            if text == spelled:
                problems.append(f"the filler {label} {text!r} is the {form.kind} {form.id}")
            elif label == "title" and form.kind in titled and (text in spelled or spelled in text):
                problems.append(
                    f"the filler title {text!r} and the {form.kind} {form.id} contain one another"
                )
    if problems:
        raise FillerNamesTheWorld("; ".join(problems))


__all__ = [
    "SKILLS_PER_BRIEF",
    "FillerExhausted",
    "FillerNamesTheWorld",
    "MintedFiller",
    "mint_filler",
]
