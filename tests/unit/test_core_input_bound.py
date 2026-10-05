"""The input bound: one registered method at one version; a request holding a field the
method does not cover is refused a bound; a bound is reused only for the request,
identifier and method it was established for; a configuration with no output limit has no
worst case; the money worst case prices input at the dearest input-side rate; and counting
again is bounded on a count that an unresolved request consumes."""

from datetime import date

import pytest

from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.input_bound import (
    INPUT_BOUND_METHODS,
    MAX_OUTPUT_SETTING,
    PROVIDER_COUNT,
    CountDecision,
    CountResult,
    EstablishedBound,
    RegisteredInputBound,
    count_decision,
    counted_projection,
    output_maximum,
    result_of_error,
    worst_case_tokens,
)
from leaveimpact.core.model_calls import ClientErrorKind
from leaveimpact.core.pricing import worst_case_cost
from leaveimpact.core.run_record import PricingBasis, PricingRow, PricingSelection

METHOD = RegisteredInputBound(PROVIDER_COUNT, 1)
BASE_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
DIGEST = "a" * 64
COUNTED, FAILED, REFUSED, UNCLASSIFIED, UNRESOLVED = (
    CountResult.COUNTED,
    CountResult.FAILED,
    CountResult.REFUSED,
    CountResult.UNCLASSIFIED,
    CountResult.UNRESOLVED,
)


def bound(
    tokens: int = 2_066, digest: str = DIGEST, identifier: str = BASE_MODEL
) -> EstablishedBound:
    return EstablishedBound(METHOD, identifier, digest, tokens, "count_001")


# --- The registry --------------------------------------------------------------------------


def test_the_registry_holds_the_provider_count_and_nothing_else() -> None:
    assert list(INPUT_BOUND_METHODS) == [PROVIDER_COUNT]
    specification = INPUT_BOUND_METHODS[PROVIDER_COUNT]
    assert (specification.name, specification.version) == (PROVIDER_COUNT, 1)


def test_the_registry_cannot_be_changed_by_a_caller() -> None:
    with pytest.raises(TypeError):
        INPUT_BOUND_METHODS["request_bytes"] = INPUT_BOUND_METHODS[PROVIDER_COUNT]  # type: ignore[index]


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        ("request_bytes", 1, "an input-bound method is a registered one"),
        (PROVIDER_COUNT, 2, "provider_count is registered at version 1, got 2"),
        (PROVIDER_COUNT, True, "provider_count is registered at version 1, got True"),
    ],
)
def test_a_method_is_named_only_as_the_registry_holds_it(
    name: str, version: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RegisteredInputBound(name, version)


# --- The projection ------------------------------------------------------------------------


def test_the_projection_is_the_four_counted_fields_in_the_specifications_order() -> None:
    request: dict[str, object] = {
        "toolConfig": {"tools": []},
        "inferenceConfig": {"maxTokens": 256, "temperature": 0},
        "system": [{"text": "s"}],
        "messages": [{"role": "user", "content": [{"text": "m"}]}],
        "additionalModelRequestFields": {"k": 1},
    }
    projected = counted_projection(METHOD, request)
    assert list(projected) == ["messages", "system", "toolConfig", "additionalModelRequestFields"]
    assert all(projected[name] is request[name] for name in projected)


def test_the_inference_configuration_is_tolerated_and_left_out() -> None:
    assert counted_projection(METHOD, {"inferenceConfig": {"maxTokens": 16}}) == {}


@pytest.mark.parametrize(
    "field", ["guardrailConfig", "promptVariables", "requestMetadata", "performanceConfig"]
)
def test_a_request_holding_a_field_outside_the_specification_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=f"bounds no request holding {field}"):
        counted_projection(METHOD, {"messages": [], field: {}})


# --- The bound and its reuse ---------------------------------------------------------------


def test_a_bound_covers_its_own_request_identifier_and_method() -> None:
    assert bound().covers(METHOD, BASE_MODEL, DIGEST)


def test_a_bound_is_not_reused_for_another_request_or_another_identifier() -> None:
    assert not bound().covers(METHOD, BASE_MODEL, "b" * 64)
    assert not bound().covers(METHOD, "eu." + BASE_MODEL, DIGEST)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"input_tokens": -1}, "an input bound in tokens is at least 0"),
        ({"request_digest": "abc"}, "the bounded request's digest"),
        ({"counting_identifier": ""}, "the counting identifier"),
        ({"evidence": " count"}, "the counting operation's id"),
    ],
)
def test_a_bound_is_refused_without_what_it_rests_on(
    fields: dict[str, object], message: str
) -> None:
    held: dict[str, object] = {
        "method": METHOD,
        "counting_identifier": BASE_MODEL,
        "request_digest": DIGEST,
        "input_tokens": 10,
        "evidence": "count_001",
    }
    with pytest.raises(ValueError, match=message):
        EstablishedBound(**{**held, **fields})  # type: ignore[arg-type]


# --- The worst case ------------------------------------------------------------------------


def test_the_output_maximum_is_the_configurations_limit() -> None:
    configured = CallConfiguration(
        "eu.model", (CallSetting("temperature", 0), CallSetting(MAX_OUTPUT_SETTING, 1024))
    )
    assert output_maximum(configured) == 1024


@pytest.mark.parametrize("value", [0, -5, True, 1.5, "1024", None])
def test_an_output_limit_that_is_no_positive_integer_is_refused(value: object) -> None:
    configured = CallConfiguration("eu.model", (CallSetting(MAX_OUTPUT_SETTING, value),))
    with pytest.raises(ValueError, match="max_tokens of eu.model is a positive integer"):
        output_maximum(configured)


def test_an_integer_valued_float_limit_is_the_integer_a_setting_normalizes_it_to() -> None:
    configured = CallConfiguration("eu.model", (CallSetting(MAX_OUTPUT_SETTING, 1024.0),))
    assert output_maximum(configured) == 1024


def test_a_configuration_with_no_output_limit_has_no_worst_case() -> None:
    with pytest.raises(ValueError, match="sets no max_tokens"):
        output_maximum(CallConfiguration("eu.model", ()))


def test_the_token_worst_case_is_the_bound_and_the_output_maximum() -> None:
    assert worst_case_tokens(bound(2_066), 256) == 2_322
    with pytest.raises(ValueError, match="an output maximum is at least 1"):
        worst_case_tokens(bound(), 0)


def _basis(*classes: tuple[str, int]) -> PricingBasis:
    rows = tuple(
        PricingRow("model-a", "eu-central-1", "on_demand", name, rate) for name, rate in classes
    )
    return PricingBasis("0" * 64, "USD", date(2026, 9, 1), rows)


SELECTION = PricingSelection("model-a", "eu-central-1", "on_demand")


def test_the_money_worst_case_prices_input_at_the_dearest_input_side_rate() -> None:
    basis = _basis(
        ("input_tokens", 1_000_000),
        ("output_tokens", 5_000_000),
        ("cache_read_input_tokens", 100_000),
        ("cache_write_input_tokens", 1_250_000),
    )
    assert worst_case_cost(1_000, 100, SELECTION, basis) == 1_000 * 1_250_000 + 100 * 5_000_000


ALL_RATES = (
    ("input_tokens", 1_000_000),
    ("output_tokens", 5_000_000),
    ("cache_read_input_tokens", 100_000),
    ("cache_write_input_tokens", 1_250_000),
)


@pytest.mark.parametrize("missing", [name for name, _ in ALL_RATES])
def test_a_basis_that_leaves_any_class_unpriced_prices_no_worst_case(missing: str) -> None:
    """A missing rate is no evidence the class cannot be billed. Without a cache-write rate
    the plain input rate would pass for the dearest, and the outcome that reported a cache
    write could not be priced at all."""
    basis = _basis(*(held for held in ALL_RATES if held[0] != missing))
    with pytest.raises(ValueError, match=f"no rate for {missing} .*no worst case can be priced"):
        worst_case_cost(1_000, 100, SELECTION, basis)


def test_every_unpriced_class_is_named() -> None:
    basis = _basis(("input_tokens", 1_000_000), ("output_tokens", 5_000_000))
    with pytest.raises(
        ValueError, match="no rate for cache_read_input_tokens, cache_write_input_tokens"
    ):
        worst_case_cost(1_000, 1, SELECTION, basis)


def test_the_dearest_input_side_rate_need_not_be_the_cache_write() -> None:
    basis = _basis(
        ("input_tokens", 3_000_000),
        ("output_tokens", 5_000_000),
        ("cache_read_input_tokens", 100_000),
        ("cache_write_input_tokens", 1_250_000),
    )
    assert worst_case_cost(1_000, 100, SELECTION, basis) == 1_000 * 3_000_000 + 100 * 5_000_000


def test_a_worst_case_is_never_priced_below_what_the_usage_could_cost() -> None:
    """Every split of the bounded input over the three input-side classes costs at most the
    worst case: the property the allocation exists for."""
    from leaveimpact.core.pricing import cost_of
    from leaveimpact.core.run_trace import Usage

    basis = _basis(
        ("input_tokens", 1_000_000),
        ("output_tokens", 5_000_000),
        ("cache_read_input_tokens", 100_000),
        ("cache_write_input_tokens", 1_250_000),
    )
    worst = worst_case_cost(30, 7, SELECTION, basis)
    for plain in range(0, 31, 5):
        for read in range(0, 31 - plain, 5):
            usage = Usage(
                (
                    ("input_tokens", plain),
                    ("output_tokens", 7),
                    ("cache_read_input_tokens", read),
                    ("cache_write_input_tokens", 30 - plain - read),
                )
            )
            assert cost_of(usage, SELECTION, basis).pico_usd <= worst


# --- Counting again ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("ThrottlingException", FAILED),
        ("ServiceUnavailableException", FAILED),
        ("InternalServerException", FAILED),
        ("ValidationException", REFUSED),
        ("AccessDeniedException", REFUSED),
        ("ResourceNotFoundException", REFUSED),
        ("ModelStreamErrorException", UNCLASSIFIED),
        ("SomethingNobodyDeclared", UNCLASSIFIED),
    ],
)
def test_a_service_error_is_read_by_the_methods_two_lists_and_by_nothing_else(
    code: str, expected: CountResult
) -> None:
    assert result_of_error(METHOD, code=code) is expected


def test_the_two_lists_are_the_errors_the_counting_call_declares() -> None:
    """The six errors the locked SDK's service model declares for the counting call, each
    in exactly one list; held here as literals so the test needs no client."""
    specification = INPUT_BOUND_METHODS[PROVIDER_COUNT]
    declared = {
        "AccessDeniedException",
        "ResourceNotFoundException",
        "ThrottlingException",
        "InternalServerException",
        "ServiceUnavailableException",
        "ValidationException",
    }
    transient, configuration = specification.transient_codes, specification.configuration_codes
    assert set(transient) | set(configuration) == declared
    assert not set(transient) & set(configuration)


@pytest.mark.parametrize("kind", list(ClientErrorKind))
def test_a_timeout_and_a_lost_connection_are_transient(kind: ClientErrorKind) -> None:
    assert result_of_error(METHOD, client_error=kind) is FAILED


def test_a_local_failure_that_is_neither_is_not_read_as_a_network_fault() -> None:
    assert result_of_error(METHOD) is UNCLASSIFIED


def test_a_service_code_decides_before_how_the_client_failed() -> None:
    read = result_of_error(
        METHOD, code="AccessDeniedException", client_error=ClientErrorKind.TIMEOUT
    )
    assert read is REFUSED


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([], CountDecision.COUNT),
        ([FAILED], CountDecision.COUNT),
        ([FAILED, UNRESOLVED], CountDecision.COUNT),
        ([FAILED, FAILED, FAILED], CountDecision.EXHAUSTED),
        ([UNRESOLVED, UNRESOLVED, UNRESOLVED], CountDecision.EXHAUSTED),
        ([FAILED, UNRESOLVED, COUNTED], CountDecision.USE),
        ([COUNTED], CountDecision.USE),
        ([REFUSED], CountDecision.DEFECT),
        ([FAILED, REFUSED], CountDecision.DEFECT),
        ([REFUSED, COUNTED], CountDecision.DEFECT),
        ([UNCLASSIFIED], CountDecision.UNCLASSIFIED),
        ([FAILED, UNCLASSIFIED], CountDecision.UNCLASSIFIED),
        ([UNCLASSIFIED, COUNTED], CountDecision.UNCLASSIFIED),
        ([UNCLASSIFIED, REFUSED], CountDecision.DEFECT),
    ],
)
def test_what_follows_from_the_counting_requests_logged(
    results: list[CountResult], expected: CountDecision
) -> None:
    assert count_decision(results, 3) is expected


def test_a_denied_count_is_a_defect_at_once_and_never_an_exhaustion() -> None:
    """The reviewed defect: three denials read as transient exhausted the maximum, and the
    exhaustion permitted a new attempt that the same missing grant would fail again."""
    denied = result_of_error(METHOD, code="AccessDeniedException")
    assert count_decision([denied], 3) is CountDecision.DEFECT
    assert count_decision([denied] * 3, 3) is CountDecision.DEFECT


def test_a_count_made_on_the_last_permitted_request_is_used() -> None:
    assert count_decision([FAILED, FAILED, COUNTED], 3) is CountDecision.USE


def test_under_a_maximum_of_one_a_single_failure_exhausts() -> None:
    assert count_decision([UNRESOLVED], 1) is CountDecision.EXHAUSTED
    with pytest.raises(ValueError, match="the most counting requests is at least 1"):
        count_decision([], 0)
