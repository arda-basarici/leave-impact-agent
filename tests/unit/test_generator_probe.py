"""The probe: one call per model reported as numbers and outcomes, never text; a faulting model
reported by its fault's class with the run failed."""

from leaveimpact.adapters.prose import (
    CheckerRequest,
    ModelAccessRefused,
    ToolCall,
    Usage,
    WriterRequest,
    WrittenText,
)
from leaveimpact.generator.probe import probe


class Writer:
    model_id = "writer-model"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def write(self, request: WriterRequest) -> WrittenText:
        if self.fail:
            raise ModelAccessRefused(self.model_id, "no grant")
        return WrittenText("The migration is on track.", Usage(30, 9, 640))


class Checker:
    model_id = "checker-model"

    def __init__(self, filled: object = ["The", "Deniz"]) -> None:
        self.filled = filled

    def extract(self, request: CheckerRequest) -> ToolCall:
        payload: dict[str, object] = {} if self.filled is None else {"words": self.filled}
        return ToolCall(payload, Usage(80, 12, 410))


def test_both_models_answering_is_reported_by_numbers_and_never_by_text() -> None:
    lines: list[str] = []
    assert probe(Writer(), Checker(), lines.append)
    assert lines == [
        "writer_model=writer-model",
        "writer_outcome=ok",
        "writer_latency_ms=640",
        "writer_input_tokens=30",
        "writer_output_tokens=9",
        "checker_model=checker-model",
        "checker_outcome=ok",
        "checker_latency_ms=410",
        "checker_input_tokens=80",
        "checker_output_tokens=12",
        "checker_tool_filled=True",
    ]
    assert not any("migration" in line or "Deniz" in line for line in lines)


def test_a_faulting_model_is_reported_by_its_fault_and_fails_the_probe() -> None:
    lines: list[str] = []
    assert not probe(Writer(fail=True), Checker(), lines.append)
    assert "writer_outcome=ModelAccessRefused" in lines
    assert "checker_outcome=ok" in lines


def test_a_checker_that_answers_without_filling_the_tool_fails_the_probe() -> None:
    for unfilled in (None, "not a list", [1, 2]):
        lines: list[str] = []
        assert not probe(Writer(), Checker(filled=unfilled), lines.append)
        assert "checker_outcome=ok" in lines and "checker_tool_filled=False" in lines
