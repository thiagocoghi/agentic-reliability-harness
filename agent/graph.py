import re
from typing import Dict, Any, Literal, Tuple
from .state import AgentState, ExecutionStatus, ToolCallRecord
from .circuit_breaker import CircuitBreakerGuardrail
from .tools.billing_tools import BillingToolkit


class AgenticHarnessRunner:
    """Orchestrates state transitions and guardrail enforcement."""

    def __init__(
        self,
        toolkit: BillingToolkit | None = None,
        guardrail: CircuitBreakerGuardrail | None = None,
    ):
        self.toolkit = toolkit or BillingToolkit()
        self.guardrail = guardrail or CircuitBreakerGuardrail()

    def plan_next_step(self, state: AgentState) -> AgentState:
        """Determines the next action based on query intent and current execution state."""
        state.iteration_count += 1
        state.estimated_tokens_used += 350  # Simulates token consumption per step

        # Extract invoice ID from query if present
        match = re.search(r"INV-\d{4}-\d{3}", state.query, re.IGNORECASE)
        target_invoice = match.group(0).upper() if match else None

        # Check what has been executed so far
        executed_tools = [rec.tool_name for rec in state.tool_history]

        if not target_invoice:
            state.pending_tool_call = None
            state.status = ExecutionStatus.FAILED
            state.investigation_summary = "No valid invoice identifier found in query."
            state.recommendation = "Please specify an invoice ID in format INV-YYYY-NNN."
            return state

        # Step 1: If invoice not fetched, fetch invoice
        if "get_invoice" not in executed_tools:
            state.pending_tool_call = {
                "name": "get_invoice",
                "args": {"invoice_id": target_invoice},
            }
            return state

        # Step 2: If transactions not queried, query transactions
        if "query_transactions" not in executed_tools:
            # Check if invoice had rate limit or error
            last_record = state.tool_history[-1]
            if last_record.status_code == 429:
                # API rate limited! Attempt single retry
                retry_count = sum(1 for r in state.tool_history if r.tool_name == "get_invoice")
                if retry_count < 2:
                    state.pending_tool_call = {
                        "name": "get_invoice",
                        "args": {"invoice_id": target_invoice},
                    }
                    return state
                else:
                    state.pending_tool_call = None
                    state.status = ExecutionStatus.CIRCUIT_TRIPPED
                    state.investigation_summary = (
                        "Rate limit persistence: Downstream payment provider returned 429."
                    )
                    state.recommendation = "Wait for provider cooldown window before retry."
                    return state

            state.pending_tool_call = {
                "name": "query_transactions",
                "args": {"invoice_id": target_invoice},
            }
            return state

        # Step 3: Analyze discrepancy
        invoice_data = None
        txns_data = None
        for rec in state.tool_history:
            if rec.tool_name == "get_invoice" and rec.status_code == 200:
                invoice_data = rec.output.get("data")
            if rec.tool_name == "query_transactions" and rec.status_code == 200:
                txns_data = rec.output.get("data")

        if invoice_data and txns_data:
            billed = float(invoice_data.get("billed_amount", 0.0))
            captured = sum(float(t.get("captured_amount", 0.0)) for t in txns_data)
            diff = round(abs(billed - captured), 2)

            if diff > 0.01 and "flag_discrepancy" not in executed_tools:
                state.discrepancy_found = True
                state.discrepancy_amount = diff
                state.pending_tool_call = {
                    "name": "flag_discrepancy",
                    "args": {
                        "invoice_id": target_invoice,
                        "billed_amount": billed,
                        "captured_amount": captured,
                        "discrepancy_amount": diff,
                        "notes": f"Discrepancy of ${diff:.2f} detected between invoice and payment gateway ledger.",
                    },
                }
                return state

        # All necessary steps completed
        state.pending_tool_call = None
        state.status = ExecutionStatus.COMPLETED
        return state

    def check_guardrails(self, state: AgentState) -> Tuple[bool, str | None]:
        """Runs the circuit breaker check."""
        return self.guardrail.evaluate(state)

    def execute_tool(self, state: AgentState) -> AgentState:
        """Executes the pending tool under schema validation."""
        if not state.pending_tool_call:
            return state

        name = state.pending_tool_call["name"]
        args = state.pending_tool_call["args"]

        if name == "get_invoice":
            out, status_code = self.toolkit.get_invoice(args)
        elif name == "query_transactions":
            out, status_code = self.toolkit.query_transactions(args)
        elif name == "flag_discrepancy":
            out, status_code = self.toolkit.flag_discrepancy(args)
        else:
            out, status_code = {"error": f"Unknown tool: {name}"}, 400

        record = ToolCallRecord(
            tool_name=name,
            arguments=args,
            output=out,
            status_code=status_code,
        )
        state.tool_history.append(record)
        state.pending_tool_call = None
        return state

    def synthesize_response(self, state: AgentState) -> AgentState:
        """Synthesizes final deterministic report."""
        if state.status == ExecutionStatus.COMPLETED:
            if state.discrepancy_found:
                state.investigation_summary = (
                    f"AUDIT COMPLETE: Discrepancy confirmed. Invoice billed amount differs by "
                    f"${state.discrepancy_amount:.2f} from captured transactions."
                )
                state.recommendation = (
                    "Reconciliation flag logged in ledger. Initiate customer billing dispute review."
                )
            else:
                state.investigation_summary = (
                    "AUDIT COMPLETE: All invoice charges match gateway captured transactions perfectly."
                )
                state.recommendation = "No financial discrepancy. Account in good standing."

        return state

    def run(self, initial_query: str, max_iterations: int = 6, token_budget_cap: int = 4000) -> AgentState:
        """Executes the full agent loop with continuous circuit-breaker checks."""
        state = AgentState(
            query=initial_query,
            max_iterations=max_iterations,
            token_budget_cap=token_budget_cap,
        )

        while state.status == ExecutionStatus.IN_PROGRESS:
            # 1. Plan next step
            state = self.plan_next_step(state)

            if state.status != ExecutionStatus.IN_PROGRESS:
                break

            # 2. Guardrail Check
            tripped, reason = self.check_guardrails(state)
            if tripped:
                state = self.guardrail.apply_graceful_degradation(state, reason or "Guardrail triggered")
                break

            # 3. Tool Execution
            if state.pending_tool_call:
                state = self.execute_tool(state)

        # 4. Synthesize final state
        return self.synthesize_response(state)


def build_reliability_graph(
    toolkit: BillingToolkit | None = None,
    guardrail: CircuitBreakerGuardrail | None = None,
) -> AgenticHarnessRunner:
    """Factory creating configured harness runner."""
    return AgenticHarnessRunner(toolkit=toolkit, guardrail=guardrail)
