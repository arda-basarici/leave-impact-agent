"""The three code guards of semantic containment, as pure functions over a text and its brief.

Containment is ``required(brief) ⊆ claims(text) ⊆ allowed(brief)``, harmless prose permitted,
and no single check is that guarantee (the step 14 rulings in DESIGN, "Materialization").
Three guards run in order, the paid one last, each returning its findings — a tuple whose
length is what a log line and a refusal may carry and whose text stays private, since a
finding can quote what the text should not have said.

The *namespace scanner* is deterministic and free. One pass over the world's surface forms,
longest match first at word boundaries, matches allowed and foreign forms together in one
longest-first pass, so the winner at any span is the longest form that fits there and an
allowed short form cannot erase a longer foreign one it sits inside; an allowed form matches
case-insensitively, so "kafka" for Kafka costs no retry, and every other world name is
refused, case-insensitively too, since a mention that makes no claim
("thanks selin") is invisible to the extraction check and the scanner is the guard that must
see it. The one exception is a form of three characters or fewer, matched in exact spelling:
"go" is in most sentences and the skill Go would otherwise refuse them all, and a false
refusal costs an attempt while a missed identity costs the benchmark, so the cut sits where
the cost flips. Employees are matched by full name and by given name alike, so a colleague
named in passing is seen. Dates and digit sequences are then checked outside the recognized
spans, so a
permitted title such as "Release 2" keeps its digit: an ISO date must be one the brief
lists, any other date spelling is refused as unlisted, and a digit sequence must be a listed
number. Number words are left to the extraction check, since "three engineers" is a
cardinality claim and not a token. Capitalization is not used to guess invented proper
nouns; that heuristic false-positives on sentence starts.

The *required-fact check* is lexical: every anchor group of every required fact must appear,
one of its spellings, case-insensitively at word boundaries. It proves no relation and exists
so a fact that vanished in the writing fails before a checker is paid. A comment's author is
its first person, so a fact about the author is anchored on its value alone.

The *containment check* compares the checker's reading with the brief on canonical statements
— subject, predicate, value; evidence and date ignored. The eligible set is the affirmed,
asserted propositions with a known subject; it must contain every required statement and
nothing outside the required and allowed ones; any negated, hedged or unknown-subject
proposition and any other claim refuses on its own.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from leaveimpact.core.refs import employee_ref
from leaveimpact.generator.prose.schema import Extraction
from leaveimpact.world.briefs import Brief, CommentTarget
from leaveimpact.world.prose import (
    AssertionMode,
    Lexicon,
    Polarity,
    Statement,
    SurfaceForm,
    lexical_anchors,
    statement_of,
)

ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")

MONTHS = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    "sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
OTHER_DATE_SPELLINGS = (
    re.compile(r"(?<!\d)\d{1,2}[/.]\d{1,2}[/.]\d{2,4}(?!\d)"),
    re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b", re.IGNORECASE),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\.?(?:,?\s+\d{{4}})?\b", re.IGNORECASE),
)
DIGITS = re.compile(r"(?<![\w.])\d+(?![\w.]|\.\d)")


def namespace_findings(
    text: str, brief: Brief, world_forms: Sequence[SurfaceForm]
) -> tuple[str, ...]:
    """Every name, date or number in ``text`` that the brief's namespace does not admit."""
    allowed = {(form.kind, form.id) for form in brief.namespace.forms}
    allowed_spellings = {form.form.casefold() for form in brief.namespace.forms}
    findings: list[str] = []
    masked = text
    # One global pass, longest form first, allowed and foreign together: the winning match
    # at a span is the longest form that fits there, and allow or deny is decided on that
    # winner. Two passes would let a short allowed form ("Deniz") erase the longer foreign
    # one it sits inside ("Deniz Kowalski") before the foreign form could match.
    for form in _longest_first(tuple(brief.namespace.forms) + tuple(world_forms)):
        admitted = (form.kind, form.id) in allowed or form.form.casefold() in allowed_spellings
        pattern = _word(form.form, re.IGNORECASE if admitted else _disallowed_flags(form.form))
        hits = len(pattern.findall(masked))
        if not hits:
            continue
        if not admitted:
            findings.append(f"names {form.kind} {form.id} outside the brief ({hits})")
        masked = _mask(masked, pattern)
    listed_dates = {day.isoformat() for day in brief.namespace.dates}
    for found in ISO_DATE.findall(masked):
        if found not in listed_dates:
            findings.append(f"date {found} not listed")
    masked = _mask(masked, ISO_DATE)
    for spelling in OTHER_DATE_SPELLINGS:
        for found in spelling.findall(masked):
            findings.append(f"date spelled other than YYYY-MM-DD: {found}")
        masked = _mask(masked, spelling)
    listed_numbers = set(brief.namespace.numbers)
    for found in DIGITS.findall(masked):
        if int(found) not in listed_numbers:
            findings.append(f"number {found} not listed")
    return tuple(findings)


def required_fact_findings(text: str, brief: Brief, lexicon: Lexicon) -> tuple[str, ...]:
    """Every anchor group of a required fact that no spelling of appears in ``text``."""
    findings: list[str] = []
    speaker = (
        employee_ref(brief.target.author_id)
        if isinstance(brief.target, CommentTarget)
        else None
    )
    for required in brief.required:
        for group in lexical_anchors(required.fact, lexicon, first_person=speaker):
            if not any(_word(spelling, re.IGNORECASE).search(text) for spelling in group):
                findings.append(
                    f"{required.fact.predicate.value} of {required.fact.subject.id}: "
                    f"none of {group} appears"
                )
    return tuple(findings)


def containment_findings(brief: Brief, extraction: Extraction) -> tuple[str, ...]:
    """Every way the checker's reading of a text departs from the brief's containment."""
    required = {statement_of(fact) for fact in brief.required_facts}
    permitted = required | {statement_of(fact) for fact in brief.allowed}
    findings: list[str] = []
    eligible: set[Statement] = set()
    for read in extraction.propositions:
        statement = read.statement
        if statement is None:
            findings.append(f"{read.predicate.value}: subject not in the entity list")
        elif read.polarity is Polarity.NEGATED:
            findings.append(f"{read.predicate.value} of {statement[0].id}: negated")
        elif read.assertion_mode is AssertionMode.HEDGED:
            findings.append(f"{read.predicate.value} of {statement[0].id}: hedged")
        elif statement not in permitted:
            findings.append(
                f"{read.predicate.value} of {statement[0].id}: not a required or allowed fact"
            )
        else:
            eligible.add(statement)
    for subject, name, _ in sorted(required - eligible, key=lambda s: (s[1].value, s[0].id)):
        findings.append(f"{name.value} of {subject.id}: required and not read as asserted")
    findings.extend(f"other claim: {claim}" for claim in extraction.other_claims)
    return tuple(findings)


SHORT_FORM = 3
"""Forms this short ("Go", "AWS") match only in exact spelling: common words in another case."""


def _disallowed_flags(spelling: str) -> int:
    return 0 if len(spelling) <= SHORT_FORM else re.IGNORECASE


def _longest_first(forms: Sequence[SurfaceForm]) -> list[SurfaceForm]:
    return sorted(forms, key=lambda form: (-len(form.form), form.kind, form.id))


def _word(spelling: str, flags: int) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(spelling)}(?!\w)", flags)


def _mask(text: str, pattern: re.Pattern[str]) -> str:
    """``text`` with every match of ``pattern`` blanked, lengths kept so spans stay honest."""
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


__all__ = ["containment_findings", "namespace_findings", "required_fact_findings"]
