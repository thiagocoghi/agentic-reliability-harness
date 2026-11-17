import json
from typing import Dict, Any, Tuple
from .state import AgentState, ExecutionStatus, ToolCallRecord


class CircuitBreakerGuardrail:
    """Deterministic circuit breaker guardrail for autonomous AI agent workflows.
    
    Prevents runaway loops, token budget overruns, and cascading API failures.
    """

    def __init__(
        self,
        max_iterations: int = 6,
        token_budget_cap: int = 4000,
        duplicate_call_threshold: int = 2,
    ):
        self.max_iterations = max_iterations
        self.token_budget_cap = token_budget_cap
        self.duplicate_call_threshold = duplicate_call_threshold

    def evaluate(self, state: AgentState) -> Tuple[bool, str | None]:
        """Evaluates whether the agent execution should be terminated by circuit breaker."""
        # 1. Max iteration guard
        if state.iteration_count >= state.max_iterations:
            return (
                True,
                f"Circuit Breaker Tripped: Maximum iterations limit reached ({state.iteration_count}/{state.max_iterations}). Halting runaway trajectory.",
            )

        # 2. Token budget guard
        if state.estimated_tokens_used >= state.token_budget_cap:
            return (
                True,
                f"Circuit Breaker Tripped: Token budget exceeded ({state.estimated_tokens_used} >= {state.token_budget_cap} tokens). Cost protection active.",
            )

        # 3. Duplicate call loop detection
        if state.pending_tool_call:
            tool_name = state.pending_tool_call.get("name")
            tool_args = state.pending_tool_call.get("args", {})
            args_str = json.dumps(tool_args, sort_keys=True)

            matching_calls = 0
            for record in state.tool_history:
                if (
                    record.tool_name == tool_name
                    and json.dumps(record.arguments, sort_keys=True) == args_str
                ):
                    matching_calls += 1

            if matching_calls >= self.duplicate_call_threshold:
                return (
                    True,
                    f"Circuit Breaker Tripped: Infinite loop detected. Tool '{tool_name}' invoked {matching_calls + 1} times with identical arguments.",
                )

        return False, None

    def apply_graceful_degradation(self, state: AgentState, reason: str) -> AgentState:
        """Applies safe fallback state when circuit breaker is tripped."""
        state.circuit_breaker_tripped = True
        state.breaker_reason = reason
        state.status = ExecutionStatus.CIRCUIT_TRIPPED
        state.investigation_summary = (
            f"[DEGRADED EXECUTION - GUARDRAIL ACTIVE] {reason}"
        )
        state.recommendation = (
            "Escalated to human operator with current trajectory telemetry. No unverified actions executed."
        )
        return state
