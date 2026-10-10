"""The prompt assets per role: the investigator's three texts are the prompt check's, byte for
byte, pinned by the digests the check recorded; the reader's three differ from them on every
name; both openings take exactly the leave id and the stamp; the default load is the
investigator's; and the reader's surface digest is the fact tool alone."""

from leaveimpact.agent.assets import ASSET_NAMES, OPENING_PARAMETERS, load_prompt_assets
from leaveimpact.agent.surface import surface_digest
from leaveimpact.core.tools import Role

INVESTIGATOR_DIGESTS = {
    "finalization": "d495fefbc1ae90107c3219075ca08144cefd287f3c7a2648c81c6fb3f79785cb",
    "opening": "a414b4112d86682b7d2d2ed879c00a7632536bf34f2753c193ad78ddfa8af60a",
    "system": "24b7414476ab01ba7f622605098d77a362853e375dfe24c99004ee8666bd3e9b",
}
"""The prompt check's final set (FINDINGS, prompt-check), the texts moved into the role's
directory unchanged at the baselines step."""

READER_SURFACE_DIGEST = "1269562f1353b5ff4b2816d7500426bfc5011ddc57df0c435aa4c1114b81923f"


def test_the_investigators_texts_moved_byte_for_byte() -> None:
    assert dict(load_prompt_assets(Role.INVESTIGATOR).digests()) == INVESTIGATOR_DIGESTS
    assert load_prompt_assets().digests() == load_prompt_assets(Role.INVESTIGATOR).digests()


def test_the_readers_texts_are_its_own_and_take_the_same_parameters() -> None:
    reader = load_prompt_assets(Role.READER)
    assert tuple(name for name, _ in reader.digests()) == tuple(sorted(ASSET_NAMES))
    for name, digest in reader.digests():
        assert digest != INVESTIGATOR_DIGESTS[name], name
    opening = reader.opening(leave_id="leave_001", now='{"at": "x", "timezone": null}')
    assert "leave_001" in opening and "$" not in opening
    assert {"leave_id", "now"} == OPENING_PARAMETERS
    # The loop's sentences are gone and the one-call framing is stated.
    system = reader.text("system")
    assert "through the tools you are given" not in system
    assert "You have no tool to read more" in system
    assert "state_facts" in reader.text("finalization")


def test_the_readers_surface_is_the_fact_tool_alone() -> None:
    assert surface_digest(Role.READER) == READER_SURFACE_DIGEST
    assert surface_digest(Role.READER) != surface_digest(Role.INVESTIGATOR)
