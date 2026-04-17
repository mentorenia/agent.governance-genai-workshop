"""
Gate 1: Data Contracts (Pydantic)
==================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

Validates agent output BEFORE it reaches downstream systems.
If the output doesn't match the contract, it's rejected and logged.
The LLM doesn't choose the shape — the contract does.

This catches:
  - Hallucinated fields
  - Values out of business-rule range
  - Wrong types
  - Missing required fields
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import datetime
import json


# ============================================================
# CONTRACTS
# ============================================================

class TicketSummary(BaseModel):
    """What the agent should return when summarizing a ticket."""

    ticket_id: str = Field(pattern=r"^TK-\d{4}$", description="Ticket ID format: TK-XXXX")
    customer_name: str = Field(min_length=2, max_length=100)
    issue: str = Field(min_length=10, max_length=500, description="Brief description of the issue")
    priority: Literal["low", "medium", "high", "critical"]
    recommended_action: Literal["refund", "replacement", "escalate", "close", "contact_customer"]


class RefundProposal(BaseModel):
    """What the agent should return when proposing a refund.
    This is the data contract — if the agent's output doesn't
    match this exactly, it's rejected."""

    ticket_id: str = Field(pattern=r"^TK-\d{4}$")
    customer_id: str = Field(pattern=r"^C-\d{3}$")
    amount: float = Field(gt=0, le=500, description="Max $500 per policy")
    reason: str = Field(min_length=10, max_length=200)
    confidence: float = Field(ge=0, le=1, description="Agent's confidence 0-1")

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: float) -> float:
        """Ensure amount has at most 2 decimal places."""
        return round(v, 2)


class CustomerResponse(BaseModel):
    """What the agent should return when drafting a customer email."""

    ticket_id: str = Field(pattern=r"^TK-\d{4}$")
    tone: Literal["empathetic", "professional", "apologetic"]
    subject: str = Field(min_length=5, max_length=100)
    body: str = Field(min_length=20, max_length=1000)
    includes_apology: bool
    offers_compensation: bool


# ============================================================
# VALIDATION ENGINE
# ============================================================

class ValidationResult:
    """Result of validating agent output against a contract."""

    def __init__(self, success: bool, data=None, error: str = None, raw: str = None):
        self.success = success
        self.data = data
        self.error = error
        self.raw = raw
        self.timestamp = datetime.now().isoformat()

    def __repr__(self):
        if self.success:
            return f"VALID: {self.data}"
        return f"REJECTED: {self.error}"


# Rejection log — every failed validation is recorded
rejection_log: list[dict] = []


def validate_output(raw_text: str, contract: type[BaseModel]) -> ValidationResult:
    """Validate agent output against a Pydantic contract.

    Args:
        raw_text: The raw text/JSON from the LLM
        contract: The Pydantic model class to validate against

    Returns:
        ValidationResult with either parsed data or error details
    """

    # Step 1: Try to parse as JSON
    try:
        # Handle case where LLM wraps JSON in markdown code blocks
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            # Remove markdown fences
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        error = f"Invalid JSON: {str(e)[:100]}"
        rejection_log.append({
            "timestamp": datetime.now().isoformat(),
            "contract": contract.__name__,
            "error": error,
            "raw_preview": raw_text[:200],
        })
        return ValidationResult(success=False, error=error, raw=raw_text)

    # Step 2: Validate against the contract
    try:
        validated = contract(**data)
        return ValidationResult(success=True, data=validated, raw=raw_text)
    except Exception as e:
        error = f"Contract violation: {str(e)[:200]}"
        rejection_log.append({
            "timestamp": datetime.now().isoformat(),
            "contract": contract.__name__,
            "error": error,
            "raw_preview": raw_text[:200],
            "parsed_json": data,
        })
        return ValidationResult(success=False, error=error, raw=raw_text)


def get_rejection_log() -> list[dict]:
    """Return all rejections for audit."""
    return rejection_log


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Pydantic Data Contracts — Demo")
    print("=" * 60)

    # Test 1: Valid refund proposal
    print("\n  Test 1: Valid refund proposal")
    valid_json = json.dumps({
        "ticket_id": "TK-1001",
        "customer_id": "C-200",
        "amount": 149.99,
        "reason": "Product arrived damaged and non-functional",
        "confidence": 0.95,
    })
    result = validate_output(valid_json, RefundProposal)
    print(f"  {result}")

    # Test 2: Amount exceeds policy ($500 max)
    print("\n  Test 2: Amount exceeds $500 policy")
    over_limit = json.dumps({
        "ticket_id": "TK-1001",
        "customer_id": "C-200",
        "amount": 9000,
        "reason": "Customer is very upset and deserves a large refund",
        "confidence": 0.80,
    })
    result = validate_output(over_limit, RefundProposal)
    print(f"  {result}")

    # Test 3: Invalid ticket ID format
    print("\n  Test 3: Invalid ticket ID format")
    bad_id = json.dumps({
        "ticket_id": "TICKET-1001",
        "customer_id": "C-200",
        "amount": 50.00,
        "reason": "Wrong item shipped to customer",
        "confidence": 0.90,
    })
    result = validate_output(bad_id, RefundProposal)
    print(f"  {result}")

    # Test 4: Not even JSON
    print("\n  Test 4: Free text (not JSON)")
    free_text = "I think we should refund the customer about $150 because the product was damaged."
    result = validate_output(free_text, RefundProposal)
    print(f"  {result}")

    # Test 5: JSON wrapped in markdown (common LLM output)
    print("\n  Test 5: JSON in markdown code block")
    markdown_json = """```json
{
    "ticket_id": "TK-1002",
    "customer_id": "C-201",
    "amount": 29.99,
    "reason": "Wrong item received, customer wants refund",
    "confidence": 0.92
}
```"""
    result = validate_output(markdown_json, RefundProposal)
    print(f"  {result}")

    # Show rejection log
    print(f"\n  --- Rejection Log ({len(rejection_log)} entries) ---")
    for entry in rejection_log:
        print(f"  [{entry['timestamp'][:19]}] {entry['contract']}: {entry['error'][:80]}")