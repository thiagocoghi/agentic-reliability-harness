import re
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, field_validator
from .mock_payment_api import MockPaymentGatewayAPI


class GetInvoiceInput(BaseModel):
    invoice_id: str = Field(
        ...,
        description="Standardized invoice identifier, e.g. INV-2026-001",
        examples=["INV-2026-001"],
    )

    @field_validator("invoice_id")
    def validate_invoice_format(cls, v: str) -> str:
        clean = v.strip().upper()
        if not re.match(r"^INV-\d{4}-\d{3}$", clean):
            raise ValueError(
                f"Invalid invoice format '{v}'. Must match pattern INV-YYYY-NNN (e.g., INV-2026-001)."
            )
        return clean


class QueryTransactionsInput(BaseModel):
    invoice_id: str = Field(..., description="Invoice ID to query ledger transactions for")

    @field_validator("invoice_id")
    def validate_invoice_format(cls, v: str) -> str:
        clean = v.strip().upper()
        if not re.match(r"^INV-\d{4}-\d{3}$", clean):
            raise ValueError(
                f"Invalid invoice format '{v}'. Must match pattern INV-YYYY-NNN."
            )
        return clean


class FlagDiscrepancyInput(BaseModel):
    invoice_id: str = Field(..., description="Invoice ID where discrepancy was detected")
    billed_amount: float = Field(..., ge=0.0, description="Amount stated in the invoice")
    captured_amount: float = Field(..., ge=0.0, description="Actual amount settled in ledger")
    discrepancy_amount: float = Field(..., ge=0.0, description="Absolute difference between billed and captured")
    notes: str = Field(..., min_length=10, description="Detailed explanation of the findings")


class BillingToolkit:
    """Toolkit equipped with Pydantic schema validation and gateway connector."""

    def __init__(self, api: MockPaymentGatewayAPI | None = None):
        self.api = api or MockPaymentGatewayAPI()

    def get_invoice(self, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Fetches invoice details after strict schema validation."""
        try:
            validated = GetInvoiceInput(**arguments)
        except Exception as e:
            return {"error": f"Schema validation failed: {str(e)}"}, 400

        res = self.api.get_invoice(validated.invoice_id)
        return res, res.get("status_code", 200)

    def query_transactions(self, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Queries ledger transactions after strict schema validation."""
        try:
            validated = QueryTransactionsInput(**arguments)
        except Exception as e:
            return {"error": f"Schema validation failed: {str(e)}"}, 400

        res = self.api.query_transactions(validated.invoice_id)
        return res, res.get("status_code", 200)

    def flag_discrepancy(self, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Flags verified financial discrepancy."""
        try:
            validated = FlagDiscrepancyInput(**arguments)
        except Exception as e:
            return {"error": f"Schema validation failed: {str(e)}"}, 400

        return {
            "status": "FLAGGED",
            "invoice_id": validated.invoice_id,
            "discrepancy_amount": validated.discrepancy_amount,
            "message": "Discrepancy logged to audit ledger with forensic trail.",
        }, 201
