import pytest
from agent.graph import build_reliability_graph
from agent.tools import BillingToolkit, MockPaymentGatewayAPI
from agent.state import ExecutionStatus


def test_golden_dataset_case_01_discrepancy():
    """CASE-01: Discrepancy is audited, calculated, and flagged accurately."""
    api = MockPaymentGatewayAPI()
    toolkit = BillingToolkit(api=api)
    runner = build_reliability_graph(toolkit=toolkit)

    result = runner.run(
        "Please investigate billing discrepancy and ledger transactions for invoice INV-2026-001."
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.discrepancy_found is True
    assert result.discrepancy_amount == 300.00

    executed_tools = [r.tool_name for r in result.tool_history]
    assert executed_tools == ["get_invoice", "query_transactions", "flag_discrepancy"]
    assert "Discrepancy confirmed" in (result.investigation_summary or "")
    assert result.circuit_breaker_tripped is False


def test_golden_dataset_case_02_clean_reconciliation():
    """CASE-02: Clean invoice reconciliation without false-positive discrepancy."""
    api = MockPaymentGatewayAPI()
    toolkit = BillingToolkit(api=api)
    runner = build_reliability_graph(toolkit=toolkit)

    result = runner.run(
        "Reconcile payment status and transactions for invoice INV-2026-002."
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.discrepancy_found is False
    assert result.discrepancy_amount == 0.0

    executed_tools = [r.tool_name for r in result.tool_history]
    assert executed_tools == ["get_invoice", "query_transactions"]
    assert "All invoice charges match" in (result.investigation_summary or "")


def test_golden_dataset_case_03_invalid_schema():
    """CASE-03: Malformed invoice format is caught before executing tools."""
    runner = build_reliability_graph()
    result = runner.run("Audit transactions for invoice INV-XYZ-999999")

    assert result.status == ExecutionStatus.FAILED
    assert len(result.tool_history) == 0
    assert "No valid invoice identifier found" in (result.investigation_summary or "")


def test_golden_dataset_case_04_rate_limit_resilience():
    """CASE-04: Graceful degradation and bounded retry when downstream API returns 429."""
    api = MockPaymentGatewayAPI()
    api.simulate_rate_limit = True  # Inject failure
    toolkit = BillingToolkit(api=api)
    runner = build_reliability_graph(toolkit=toolkit)

    result = runner.run(
        "Investigate invoice INV-2026-001 under payment gateway heavy load."
    )

    assert result.status == ExecutionStatus.CIRCUIT_TRIPPED
    # Assert retry attempts were bounded (did not loop forever)
    assert len(result.tool_history) <= 2
    for record in result.tool_history:
        assert record.status_code == 429
    assert "Rate limit persistence" in (result.investigation_summary or "")


def test_adversarial_infinite_loop_containment():
    """CASE-05: Adversarial loop test - ensures execution halts under max iteration cap."""
    runner = build_reliability_graph()
    # Force max iterations = 2
    result = runner.run(
        "Investigate invoice INV-2026-001",
        max_iterations=2,
    )

    assert result.circuit_breaker_tripped is True
    assert result.status == ExecutionStatus.CIRCUIT_TRIPPED
    assert "Maximum iterations limit reached" in (result.breaker_reason or "")
