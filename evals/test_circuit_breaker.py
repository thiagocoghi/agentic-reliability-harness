import pytest
from agent.state import AgentState, ExecutionStatus, ToolCallRecord
from agent.circuit_breaker import CircuitBreakerGuardrail


def test_circuit_breaker_trips_on_max_iterations():
    guardrail = CircuitBreakerGuardrail(max_iterations=5)
    state = AgentState(query="Test query", iteration_count=5, max_iterations=5)

    tripped, reason = guardrail.evaluate(state)
    assert tripped is True
    assert "Maximum iterations limit reached" in reason

    degraded_state = guardrail.apply_graceful_degradation(state, reason)
    assert degraded_state.circuit_breaker_tripped is True
    assert degraded_state.status == ExecutionStatus.CIRCUIT_TRIPPED
    assert "[DEGRADED EXECUTION - GUARDRAIL ACTIVE]" in degraded_state.investigation_summary


def test_circuit_breaker_trips_on_token_budget_overrun():
    guardrail = CircuitBreakerGuardrail(token_budget_cap=2000)
    state = AgentState(query="Test query", token_budget_cap=2000, estimated_tokens_used=2100)

    tripped, reason = guardrail.evaluate(state)
    assert tripped is True
    assert "Token budget exceeded" in reason


def test_circuit_breaker_detects_infinite_tool_loop():
    guardrail = CircuitBreakerGuardrail(duplicate_call_threshold=2)
    state = AgentState(query="Test loop")

    # Add 2 identical past tool calls
    state.tool_history.append(
        ToolCallRecord(
            tool_name="get_invoice",
            arguments={"invoice_id": "INV-2026-001"},
            status_code=200,
        )
    )
    state.tool_history.append(
        ToolCallRecord(
            tool_name="get_invoice",
            arguments={"invoice_id": "INV-2026-001"},
            status_code=200,
        )
    )

    # Next pending tool call is identical
    state.pending_tool_call = {
        "name": "get_invoice",
        "args": {"invoice_id": "INV-2026-001"},
    }

    tripped, reason = guardrail.evaluate(state)
    assert tripped is True
    assert "Infinite loop detected" in reason
    assert "invoked 3 times" in reason


def test_circuit_breaker_passes_for_healthy_execution():
    guardrail = CircuitBreakerGuardrail(max_iterations=10, token_budget_cap=5000)
    state = AgentState(
        query="Healthy query",
        iteration_count=2,
        estimated_tokens_used=700,
        pending_tool_call={"name": "query_transactions", "args": {"invoice_id": "INV-2026-001"}},
    )

    tripped, reason = guardrail.evaluate(state)
    assert tripped is False
    assert reason is None
