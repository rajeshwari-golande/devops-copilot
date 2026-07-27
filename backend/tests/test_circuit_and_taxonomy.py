"""Circuit breaker + taxonomy unit tests."""

from app.services import circuit_breaker
from app.taxonomy import normalize_classification


def setup_function():
    circuit_breaker.reset_for_tests()


def test_normalize_aliases():
    assert normalize_classification("network_timeout") == "transient_network"
    assert normalize_classification("oom") == "resource_exhaustion"
    assert normalize_classification("flaky") == "flaky_test"
    assert normalize_classification("not_a_real_label") == "unknown"


def test_circuit_breaker_trips_after_limit():
    circuit_breaker.reset_for_tests()
    assert circuit_breaker.circuit_open("demo/app", "ci") is False
    circuit_breaker.record_attempt("demo/app", "ci")
    circuit_breaker.record_attempt("demo/app", "ci")
    # default max 2
    assert circuit_breaker.circuit_open("demo/app", "ci") is True
    assert circuit_breaker.remaining_quota("demo/app", "ci") == 0
