"""The report's pins hold the figures FINDINGS ``phase-c`` cites, each from the record
that holds it, and refuse a declared FINDINGS row the file no longer carries."""

from __future__ import annotations

import pytest

from report.generate import REPOSITORY
from report.pins import FINDINGS_ROWS, SOURCES, findings_pins, load_pins


def test_the_pins_hold_the_figures_findings_cites_from_their_sources() -> None:
    pins = load_pins(REPOSITORY)
    expected = {
        "whole.agent.base": ("24", "results"),
        "whole.agent.padded": ("24", "results"),
        "whole.full_context.base": ("30", "results"),
        "whole.full_context.padded": ("14", "results"),
        "whole.single_shot.base": ("22", "results"),
        "whole.single_shot.padded": ("10", "results"),
        "whole.rules_only.base": ("10", "results"),
        "whole.rules_only.padded": ("10", "results"),
        "whole.agent.padded.interval": ("0.63 to 0.90", "results"),
        "difference.agent.full_context.padded": ("0.20 to 0.47", "results"),
        "difference.agent.full_context.padded.two_by_two": ("14, 10, 0, 6", "results"),
        "mechanism.agent.padded.stages": ("31, 26, 26, 25", "results"),
        "mechanism.full_context.padded.stages": ("31, 6, 6, 6", "results"),
        "mechanism.agent.padded.denominator": ("31", "results"),
        "cost.total_usd": ("$9.9594", "results"),
        "cost.agent.base.usd": ("$2.2125", "results"),
        "cost.agent.base.per_run_usd": ("$0.0738", "results"),
        "cost.rules_only.base.usd": ("$0", "results"),
        "runs.total": ("240", "results"),
        "scenarios.per_arm": ("30", "results"),
        "headroom.base": ("20 of 30", "results"),
        "level.base.full_context_input_tokens": ("10,359 to 10,611", "registration"),
        "level.padded.filler_documents": ("160", "registration"),
        "caps.agent.calls": ("14", "registration"),
        "caps.agent.tokens": ("200,000", "registration"),
        "caps.full_context.tokens": ("191,808", "registration"),
        "budget.ceiling_usd": ("$90", "registration"),
        "statistics.confidence_percent": ("95", "registration"),
        "stopped.full_context.padded": ("24 of 30", "findings"),
        "stopped.single_shot.padded": ("25 of 30", "findings"),
        "observed_input_tokens.full_context.base": ("10,517 to 10,877", "findings"),
        "calls_per_run.agent.base": ("4 to 12", "findings"),
    }
    assert {name: (pins[name].text, pins[name].source) for name in expected} == expected
    assert all(pin.source in SOURCES and pin.note for pin in pins.values())


def test_the_level_and_descriptive_contrasts_state_the_base_level_loss() -> None:
    """At base the investigator is behind full context, a figure FINDINGS prose does not
    state and the report must; the agent's level contrast is a tie on the same six."""
    pins = load_pins(REPOSITORY)
    assert pins["level_contrast.agent.two_by_two"].text == "24, 0, 0, 6"
    base = pins["descriptive.agent.full_context.base"]
    assert base.text.startswith("-") and base.text.endswith("-0.10")


def test_a_declared_findings_row_absent_from_the_file_refuses_by_pin_name() -> None:
    first = FINDINGS_ROWS[0]
    section = "\n## phase-c\n\n| other row |\n\n## next\n"
    with pytest.raises(ValueError, match=f"findings pin '{first.name}'.*occurs 0 times"):
        findings_pins(section)
    with pytest.raises(ValueError, match="no phase-c section"):
        findings_pins("## something else\n")
