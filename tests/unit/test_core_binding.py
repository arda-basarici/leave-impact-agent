"""The span binding on the six cases its ruling names: equality over the distinct titles a run
read, the conservative guard on a longer read title, and the wrong binding the contract
leaves to the model."""

import pytest

from leaveimpact.core import document_ref, event_ref
from leaveimpact.core.binding import bind_span, titled_artifacts
from leaveimpact.core.stated import PlacementState, SpanPlacement
from tests.unit import stated_fixture as f

PLAIN = (f.TICKET_REF, f.TITLE)
REGIONAL = (f.REGIONAL_REF, f.REGIONAL_TITLE)
MEETING = (event_ref(f.MEETING.id), f.MEETING.title)
NAMES_THE_REGIONAL = f"The {f.REGIONAL_TITLE} release needs a Go engineer."
NAMES_THE_PLAIN = f"The {f.TITLE} release needs a Go engineer."


def placed(artifact: object) -> SpanPlacement:
    return SpanPlacement(PlacementState.PLACED, artifact=artifact)  # type: ignore[arg-type]


def ambiguous(*among: object) -> SpanPlacement:
    return SpanPlacement(PlacementState.AMBIGUOUS, among=among)  # type: ignore[arg-type]


UNPLACED = SpanPlacement(PlacementState.UNPLACED)


def test_nested_titles_with_the_longer_one_read_bind_the_whole_title() -> None:
    assert bind_span(f.REGIONAL_TITLE, NAMES_THE_REGIONAL, (PLAIN, REGIONAL)) == placed(
        f.REGIONAL_REF
    )


def test_a_shortened_span_is_ambiguous_when_the_longer_title_was_read() -> None:
    assert bind_span(f.TITLE, NAMES_THE_REGIONAL, (PLAIN, REGIONAL)) == ambiguous(f.REGIONAL_REF)


def test_nested_titles_with_the_longer_one_unread() -> None:
    # The whole title names a ticket the run never read: nothing to bind to.
    assert bind_span(f.REGIONAL_TITLE, NAMES_THE_REGIONAL, (PLAIN,)) == UNPLACED
    # Cut short, the span equals the plain title and binds it. A wrong binding, and the
    # model's: no record the run read says where the title ends.
    assert bind_span(f.TITLE, NAMES_THE_REGIONAL, (PLAIN,)) == placed(f.TICKET_REF)


def test_one_title_on_two_kinds_of_artifact_is_ambiguous_among_both() -> None:
    twin = (event_ref(f.MEETING.id), f.TITLE)
    assert bind_span(f.TITLE, NAMES_THE_PLAIN, (PLAIN, twin)) == ambiguous(twin[0], f.TICKET_REF)


def test_a_target_the_run_never_read_is_unplaced() -> None:
    assert bind_span(f.TITLE, NAMES_THE_PLAIN, (MEETING,)) == UNPLACED
    assert bind_span(f.TITLE, NAMES_THE_PLAIN, ()) == UNPLACED


def test_a_rightful_short_title_beside_a_longer_one() -> None:
    # The longer title was read and the passage does not mention it: the short one binds.
    assert bind_span(f.TITLE, NAMES_THE_PLAIN, (PLAIN, REGIONAL)) == placed(f.TICKET_REF)
    # The passage mentions the longer title on its own: the guard's stated cost.
    both = f"{NAMES_THE_PLAIN} See also {f.REGIONAL_TITLE}."
    assert bind_span(f.TITLE, both, (PLAIN, REGIONAL)) == ambiguous(f.REGIONAL_REF)


def test_a_target_read_only_later_binds_at_the_later_composition() -> None:
    before = titled_artifacts(f.reads_of(work_items=()))
    after = titled_artifacts(f.reads_of())
    assert bind_span(f.TITLE, f.CLAUSE_TEXT, before) == UNPLACED
    assert bind_span(f.TITLE, f.CLAUSE_TEXT, after) == placed(f.TICKET_REF)


def test_a_span_one_word_past_its_title_is_unplaced_though_the_target_was_read() -> None:
    assert bind_span(f"{f.TITLE} release", NAMES_THE_PLAIN, (PLAIN,)) == UNPLACED


def test_equality_is_exact() -> None:
    assert bind_span(f.TITLE.lower(), NAMES_THE_PLAIN, (PLAIN,)) == UNPLACED
    assert bind_span(f"{f.TITLE} ", NAMES_THE_PLAIN, (PLAIN,)) == UNPLACED
    with pytest.raises(ValueError, match="a target span is not empty"):
        bind_span("", NAMES_THE_PLAIN, (PLAIN,))


def test_the_titled_artifacts_are_the_distinct_tickets_meetings_and_documents_read() -> None:
    reads = f.reads_of(work_items=(f.TICKET, f.REGIONAL))
    assert titled_artifacts(reads) == (
        PLAIN,
        REGIONAL,
        (document_ref(f.RUNBOOK.id), f.RUNBOOK.title),
    )
    # The same artifact returned by two reads is one artifact.
    assert bind_span(f.TITLE, f.CLAUSE_TEXT, (PLAIN, PLAIN)) == placed(f.TICKET_REF)


def test_one_artifact_given_two_titles_is_the_callers_error() -> None:
    with pytest.raises(ValueError, match="ticket_042 is given two titles"):
        bind_span(f.TITLE, NAMES_THE_PLAIN, (PLAIN, (f.TICKET_REF, f.REGIONAL_TITLE)))
