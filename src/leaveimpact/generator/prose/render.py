"""The pure render from a brief to the two model requests: what the writer is told, what the
checker is told, and how a fact reads as a line of instruction.

Prompt policy is the generator's (the step 14 rulings in DESIGN, "Truth before prose"): the
brief's required facts become lines the writer must state, its allowed facts lines it may
mention, its namespace the only names, dates and numbers it may use, its register the voice;
the rules the guards enforce are told to the model in the system text so the gate is not a
surprise. A fact is rendered as a plain phrase — "Deniz Kaya has experience with Kafka" —
never as a sentence the text must contain, which would turn the benchmark into paraphrase
detection. The checker's message carries the text, the entity list of the brief's namespace
with ids and display forms, and the value form of every predicate; it never carries the
brief's facts, which is the independence claim of the extraction check.

Everything here is a function of the brief and the assets, so the rendered request is
digested per target for the record: brief, exact request, exact accepted text — the
provenance chain closes without storing another copy of the prompt.
"""

from __future__ import annotations

from datetime import datetime

from leaveimpact.adapters.prose.seam import (
    CheckerRequest,
    InferenceConfiguration,
    ToolSpec,
    WriterRequest,
)
from leaveimpact.core.enums import EmploymentType
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import SkillId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import EmploymentTypeCriterion, Requirement, SkillCriterion
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.generator.prose.assets import CHECKER_SYSTEM, WRITER_SYSTEM, PromptAssets
from leaveimpact.generator.prose.schema import (
    TOOL_NAME,
    UNKNOWN_SUBJECT,
    tool_schema,
    value_forms,
)
from leaveimpact.world.briefs import Brief, CommentTarget, Register, SectionTarget
from leaveimpact.world.prose import CARRIER_KINDS, Lexicon

WRITER_INFERENCE = InferenceConfiguration(temperature=0.7, max_tokens=400)
"""Sampling above zero so fresh attempts differ; a ceiling a short text never reaches."""

CHECKER_INFERENCE = InferenceConfiguration(temperature=0.0, max_tokens=1200)
"""Variability minimized, so a re-check of one text is as repeatable as the model allows."""

LENGTH_BY_REGISTER: dict[Register, str] = {
    Register.TICKET_COMMENT: "one to three sentences",
    Register.RUNBOOK: "one short paragraph of two to four sentences",
    # One fact and no allowed context: a longer note is padding the checker files as other
    # claims (five of six section probes, 2026-09-15).
    Register.CLIENT_NOTE: "one or two sentences",
    Register.PROCEDURE: "one or two sentences",
    Register.POLICY: "one or two sentences",
}


def writer_request(brief: Brief, lexicon: Lexicon, assets: PromptAssets) -> WriterRequest:
    """The writer's request for ``brief``: the system text and the brief laid out as a message.

    A comment's writer is told who they are and on which ticket; a section's writer is
    told which document the section belongs to, the same structural line the checker
    gets, and nothing about the facts: a section has no author for a first-person
    statement to bind to, so the register and this line keep the text in the third
    person (the 15.2 rulings).
    """
    namespace = brief.namespace
    lines = [f"Kind of text: {assets.register(brief.register).strip()}"]
    match brief.target:
        case CommentTarget(author_id=author_id, work_item_id=work_item_id):
            author = namespace.form_of("employee", author_id)
            ticket = namespace.form_of("work_item", work_item_id)
            lines.append(f'You are {author}, commenting on the ticket "{ticket}".')
        case SectionTarget():
            lines.append(_carrier_line(brief))
    lines.append("")
    lines.append("Facts the text must state:")
    lines.extend(f"- {describe_fact(required.fact, lexicon)}" for required in brief.required)
    lines.append("")
    lines.append("Context the text may mention, and nothing else of this kind:")
    lines.extend(f"- {describe_fact(fact, lexicon)}" for fact in brief.allowed)
    if not brief.allowed:
        lines.append("- (none)")
    lines.append("")
    lines.append("Names you may use, spelled exactly so:")
    lines.extend(f"- {form.form} ({form.kind.replace('_', ' ')})" for form in namespace.forms)
    lines.append("")
    lines.append(
        "Dates you may write (as YYYY-MM-DD): "
        + (", ".join(d.isoformat() for d in namespace.dates) or "none")
    )
    lines.append(
        "Numbers you may write: " + (", ".join(str(n) for n in namespace.numbers) or "none")
    )
    lines.append("")
    lines.append(f"Length: {LENGTH_BY_REGISTER[brief.register]}.")
    return WriterRequest(assets.text(WRITER_SYSTEM), "\n".join(lines), WRITER_INFERENCE)


def checker_request(text: str, brief: Brief, assets: PromptAssets) -> CheckerRequest:
    """The checker's request over ``text``: what the text is, the entity list and the value forms,
    never the facts.

    What the text is — a comment by a named person on a ticket, a section of a named
    document — is the carrier's identity and not the brief's facts: without it a first-person
    comment has no subject the checker can name (the first measurement world, 2026-09-14).
    """
    lines = [_carrier_line(brief), ""]
    lines.append("Entity list (id: display form, kind):")
    lines.extend(
        f"- {form.id}: {form.form} ({form.kind.replace('_', ' ')})"
        for form in brief.namespace.forms
    )
    lines.append(f"- {UNKNOWN_SUBJECT}: any person or thing the text names that is not listed")
    lines.append("")
    lines.append("Predicates and the value form each takes:")
    lines.extend(value_forms())
    lines.append("")
    lines.append("The text:")
    lines.append(text)
    tool = ToolSpec(
        TOOL_NAME,
        "Record every proposition the text makes about the listed entities, and every "
        "other claim it asserts that no predicate can express.",
        tool_schema(),
    )
    return CheckerRequest(assets.text(CHECKER_SYSTEM), "\n".join(lines), tool, CHECKER_INFERENCE)


def _carrier_line(brief: Brief) -> str:
    namespace = brief.namespace
    match brief.target:
        case CommentTarget(author_id=author_id, work_item_id=work_item_id):
            author = namespace.form_of("employee", author_id)
            ticket = namespace.form_of("work_item", work_item_id)
            return (
                f"The text is a comment written by {author} ({author_id}) on the ticket "
                f'"{ticket}"; a first-person statement in it is about {author}.'
            )
        case SectionTarget(document_id=document_id):
            title = namespace.form_of("document", document_id)
            return f'The text is a section of the document "{title}".'


def describe_fact(fact: Fact, lexicon: Lexicon) -> str:
    """``fact`` as a plain phrase the writer reads: names by display form, values in words."""
    subject = _name(fact.subject, lexicon)
    value = fact.value
    match fact.predicate:
        case PredicateName.HAS_SKILL:
            assert isinstance(value, str)
            return f"{subject} has experience with {lexicon.skill(SkillId(value)).form}"
        case PredicateName.MEMBER_OF_COMPONENT:
            assert isinstance(value, EntityRef)
            return f"{subject} works on the {_name(value, lexicon)} component"
        case PredicateName.OWNS_WORK_ITEM:
            assert isinstance(value, EntityRef)
            return f'{_name(value, lexicon)} owns the ticket "{subject}"'
        case PredicateName.REQUIRES:
            assert isinstance(value, Requirement)
            return f"the activity requires {_requirement(value, lexicon)}"
        case PredicateName.NAMES_RESPONSIBLE:
            assert isinstance(value, EntityRef)
            # Domain content the writer can realize, not the benchmark's view of the fact.
            contact = _name(value, lexicon)
            return f"{contact} is the contact responsible for the account this note covers"
        case PredicateName.MEMBER_OF_TEAM:
            assert isinstance(value, EntityRef)
            return f"{subject} is on the {_name(value, lexicon)} team"
        case PredicateName.REPORTS_TO:
            assert isinstance(value, EntityRef)
            return f"{subject} reports to {_name(value, lexicon)}"
        case PredicateName.ATTENDS_EVENT:
            assert isinstance(value, EntityRef)
            return f'{_name(value, lexicon)} attends "{subject}"'
        case PredicateName.IN_COMPONENT:
            assert isinstance(value, EntityRef)
            return f'the ticket "{subject}" belongs to the {_name(value, lexicon)} component'
        case _:
            return f"{subject}: {fact.predicate.value.replace('_', ' ')} {_plain(value)}"


def _requirement(requirement: Requirement, lexicon: Lexicon) -> str:
    parts = [f"at least {requirement.count} {'person' if requirement.count == 1 else 'people'}"]
    for criterion in requirement.criteria:
        match criterion:
            case SkillCriterion():
                parts.append(f"each with experience with {lexicon.skill(criterion.skill).form}")
            case EmploymentTypeCriterion():
                parts.append(f"each employed as {_employment(criterion.employment_type)}")
    return ", ".join(parts)


def _employment(kind: EmploymentType) -> str:
    return "an employee (not a contractor)" if kind is EmploymentType.EMPLOYEE else "a contractor"


def _name(ref: EntityRef, lexicon: Lexicon) -> str:
    if ref.kind in CARRIER_KINDS:
        return "this text"
    return lexicon.form_of(ref).form


def _plain(value: object) -> str:
    match value:
        case EntityRef():
            return value.id
        case DateSpan():
            return f"from {value.start.isoformat()} to {value.end.isoformat()}"
        case InstantSpan():
            return f"from {value.start.isoformat()} to {value.end.isoformat()}"
        case datetime():
            return value.isoformat()
        case _:
            return str(value)


__all__ = [
    "CHECKER_INFERENCE",
    "LENGTH_BY_REGISTER",
    "WRITER_INFERENCE",
    "checker_request",
    "describe_fact",
    "writer_request",
]
