"""Composition: the semantic world with its model-written parts placed, a pure function of the
accepted prose.

Materialization is the one stage of generation that is not a function of the seed, and it
runs whole before any byte of the world is fixed (the step 14 rulings in DESIGN,
"Materialization"). Its output is plain data — one body of text per pending target and the
record of how each was accepted — and ``compose`` is what turns that data and the semantic
world into a ``WorldSpec``: each comment target becomes a ``Comment`` whose text is the
canonical prefix, rendered from the target's own date and author, joined to the body the
model wrote; each section target becomes a ``DocumentSection`` holding the body; each part
lands at its target's position in the parent's order, the parts the class wrote itself
filling the other slots in their order. The model never writes an id, a date or an author,
so none of those can become a prose failure.

The contract this stage owns is the bijection between brief, prose result, record and
composed part: a body for every brief and a brief for every body, nothing unconsumed, no
blank text, every body the very bytes its target's record accepted, and the record naming
exactly the targets that were pending. The digest binding is checked here because this is
the one boundary where the body and the record meet; what the record says the checker
read into that body is the materialization gate's claim, not composition's. The stronger invariant
— every target now present under its parent, every prose-authored fact resolving to a part
— is the composed world's own and holds for any ``WorldSpec`` however built. A world with
no pending prose composes with an empty prose set and no record, into the same entities it
was assembled with; ``assemble_world`` is that path in one call, and refuses a world that
needed a model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

from leaveimpact.core.comments import comment_text
from leaveimpact.core.entities import Comment, Document, DocumentSection, WorkItem
from leaveimpact.world.artifacts import digest, semantic_digest
from leaveimpact.world.assembly import SemanticWorld, WorldSpec, assemble_semantic_world
from leaveimpact.world.briefs import (
    Brief,
    CommentTarget,
    ProseContractError,
    SectionTarget,
    parent_id,
)
from leaveimpact.world.org import OrgParams
from leaveimpact.world.prose import MaterializationRecord
from leaveimpact.world.scenario import Planted, Scenario


def compose(
    semantic: SemanticWorld,
    prose: Mapping[str, str],
    materialization: MaterializationRecord | None,
) -> WorldSpec:
    """``semantic`` with every pending part written from ``prose``, keyed by target id.

    Raises ``ProseContractError`` when a brief has no body, a body has no brief, a body
    is blank, a body's digest differs from the one its record accepted, or the record
    names other targets than the briefs do.
    """
    pending = semantic.pending_ids
    given = frozenset(prose)
    if given != pending:
        raise ProseContractError(
            f"prose is composed for exactly the pending targets; missing "
            f"{sorted(pending - given)}, unexpected {sorted(given - pending)}"
        )
    blank = sorted(target for target, body in prose.items() if not body.strip())
    if blank:
        raise ProseContractError(f"a composed body is not blank, got blank for {blank}")
    if materialization is not None:
        # The record's accepted body and the body composed here are the same bytes, or the
        # sealed provenance would describe a text the world does not contain.
        on_record = {t.target_id: t.accepted_body_digest for t in materialization.targets}
        differing = sorted(
            target
            for target, body in prose.items()
            if target in on_record and digest(body.encode("utf-8")) != on_record[target]
        )
        if differing:
            raise ProseContractError(
                f"the accepted body on record differs from the composed body for {differing}"
            )
    names: dict[str, str] = {employee.id: employee.name for employee in semantic.org.employees}
    return WorldSpec(
        seed=semantic.seed,
        world_start=semantic.world_start,
        org=semantic.org,
        slices=semantic.slices,
        plan=semantic.plan,
        plan_name=semantic.plan_name,
        scenarios=tuple(_composed(scenario, prose, names) for scenario in semantic.scenarios),
        facts=semantic.facts,
        generator_version=semantic.generator_version,
        interpreter=semantic.interpreter,
        vocabulary_digest=semantic.vocabulary_digest,
        semantic_digest=semantic_digest(semantic),
        materialization=materialization,
    )


def assemble_world(
    seed: int,
    params: OrgParams,
    world_start: date,
    plan_name: str = "tier1",
) -> WorldSpec:
    """The composed world of a seed that needs no model: assembled, then composed with no prose.

    Raises what ``assemble_semantic_world`` raises, and ``ProseContractError`` when the
    world left a part pending — a world with briefs is composed from materialized prose,
    never from nothing.
    """
    return compose(assemble_semantic_world(seed, params, world_start, plan_name), {}, None)


def _composed(scenario: Scenario, prose: Mapping[str, str], names: Mapping[str, str]) -> Scenario:
    """``scenario`` with its briefed parts placed; a scenario without briefs is returned as is."""
    if not scenario.briefs:
        return scenario
    comments = _by_parent(scenario.briefs, CommentTarget)
    sections = _by_parent(scenario.briefs, SectionTarget)
    work_items = tuple(
        _with_comments(planted, comments.get(planted.entity.id, ()), prose, names)
        for planted in scenario.owned.work_items
    )
    documents = tuple(
        _with_sections(planted, sections.get(planted.entity.id, ()), prose)
        for planted in scenario.owned.documents
    )
    owned = replace(scenario.owned, work_items=work_items, documents=documents)
    return replace(scenario, owned=owned)


def _by_parent[T: CommentTarget | SectionTarget](
    briefs: Sequence[Brief], kind: type[T]
) -> dict[str, tuple[T, ...]]:
    grouped: dict[str, list[T]] = {}
    for brief in briefs:
        if isinstance(brief.target, kind):
            grouped.setdefault(parent_id(brief.target), []).append(brief.target)
    return {parent: tuple(targets) for parent, targets in grouped.items()}


def _with_comments(
    planted: Planted[WorkItem],
    targets: Sequence[CommentTarget],
    prose: Mapping[str, str],
    names: Mapping[str, str],
) -> Planted[WorkItem]:
    if not targets:
        return planted
    written = [
        (
            target.position,
            Comment(
                target.id,
                target.world_date,
                target.author_id,
                comment_text(
                    target.id,
                    target.world_date,
                    target.author_id,
                    names[target.author_id],
                    prose[target.id],
                ),
            ),
        )
        for target in targets
    ]
    item = replace(planted.entity, comments=_placed(planted.entity.comments, written))
    return Planted(item, planted.observable_from)


def _with_sections(
    planted: Planted[Document], targets: Sequence[SectionTarget], prose: Mapping[str, str]
) -> Planted[Document]:
    if not targets:
        return planted
    written = [
        (target.position, DocumentSection(target.id, prose[target.id])) for target in targets
    ]
    document = replace(planted.entity, sections=_placed(planted.entity.sections, written))
    return Planted(document, planted.observable_from)


def _placed[T](existing: Sequence[T], written: Sequence[tuple[int, T]]) -> tuple[T, ...]:
    """``written`` at their positions, ``existing`` filling the remaining slots in order."""
    slots: list[T | None] = [None] * (len(existing) + len(written))
    for position, part in written:
        slots[position] = part
    remaining = iter(existing)
    return tuple(part if part is not None else next(remaining) for part in slots)


__all__ = ["assemble_world", "compose"]
