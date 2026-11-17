from typing import Dict, Any, Optional


class MockPaymentGatewayAPI:
    """Deterministic Mock Payment Gateway API for testing agent reliability."""

    def __init__(self):
        self.invoices_db = {
            "INV-2026-001": {
                "invoice_id": "INV-2026-001",
                "customer_id": "CUST-9901",
                "billed_amount": 1250.00,
                "currency": "USD",
                "status": "PAID",
                "created_at": "2026-10-15T10:00:00Z",
                "description": "Enterprise AI Copilot Tier - 50 Seats",
            },
            "INV-2026-002": {
                "invoice_id": "INV-2026-002",
                "customer_id": "CUST-8812",
                "billed_amount": 499.00,
                "currency": "USD",
                "status": "PAID",
                "created_at": "2026-10-20T14:30:00Z",
                "description": "Starter Developer Package",
            },
        }

        self.transactions_db = {
            "INV-2026-001": [
                {
                    "txn_id": "TXN-88712",
                    "invoice_id": "INV-2026-001",
                    "captured_amount": 950.00,  # Intentional $300.00 discrepancy!
                    "gateway_status": "SETTLED",
                    "payment_method": "stripe_card_4242",
                    "timestamp": "2026-10-15T10:05:00Z",
                }
            ],
            "INV-2026-002": [
                {
                    "txn_id": "TXN-55421",
                    "invoice_id": "INV-2026-002",
                    "captured_amount": 499.00,
                    "gateway_status": "SETTLED",
                    "payment_method": "stripe_card_1111",
                    "timestamp": "2026-10-20T14:31:00Z",
                }
            ],
        }

        self.simulate_rate_limit: bool = False
        self.simulate_server_error: bool = False

    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        if self.simulate_rate_limit:
            return {
                "error": "Rate limit exceeded (HTTP 429). Too many requests to Payment Gateway.",
                "status_code": 429,
                "retry_after_seconds": 3,
            }
        if self.simulate_server_error:
            return {
                "error": "Gateway Timeout (HTTP 504). Downstream payment provider unresponsive.",
                "status_code": 504,
            }

        invoice = self.invoices_db.get(invoice_id)
        if not invoice:
            return {"error": f"Invoice '{invoice_id}' not found.", "status_code": 404}
        return {"data": invoice, "status_code": 200}

    def query_transactions(self, invoice_id: str) -> Dict[str, Any]:
        if self.simulate_rate_limit:
            return {
                "error": "Rate limit exceeded (HTTP 429).",
                "status_code": 429,
                "retry_after_seconds": 3,
            }

        txns = self.transactions_db.get(invoice_id)
        if txns is None:
            return {
                "error": f"No ledger transactions found for invoice '{invoice_id}'.",
                "status_code": 404,
            }
        return {"data": txns, "status_code": 200}
