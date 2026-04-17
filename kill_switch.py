"""
Gate 3: Kill-Switch (BudgetGuard)
==================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

A deterministic circuit breaker that lives OUTSIDE the agent.
Counts cost per session and physically cuts the connection
when the budget threshold is exceeded.

The agent cannot negotiate, persuade, or bypass this.
It's not a prompt instruction — it's a wall.

Usage:
    guard = BudgetGuard(limit=10.00)
    guard.track(input_tokens=3000, output_tokens=1500)
    guard.check()  # raises CircuitOpenError if over budget
"""

from dataclasses import dataclass, field
from datetime import datetime


# ============================================================
# CIRCUIT BREAKER ERROR
# ============================================================

class CircuitOpenError(Exception):
    """Raised when the budget limit is exceeded.
    This physically stops the agent loop."""

    def __init__(self, cost: float, limit: float, loops: int):
        self.cost = cost
        self.limit = limit
        self.loops = loops
        super().__init__(
            f"CIRCUIT BREAKER: Budget ${limit:.2f} exceeded "
            f"(spent ${cost:.4f} in {loops} loops)"
        )


# ============================================================
# BUDGET GUARD
# ============================================================

# Default pricing: Claude Opus 4.6
DEFAULT_INPUT_PRICE = 5.00 / 1_000_000    # $5 per million input tokens
DEFAULT_OUTPUT_PRICE = 25.00 / 1_000_000   # $25 per million output tokens


@dataclass
class BudgetGuard:
    """Deterministic budget supervisor for AI agent sessions.

    Lives OUTSIDE the agent. Counts tokens and cost per session.
    When the limit is hit, raises CircuitOpenError — the agent
    loop must catch this and terminate.

    Attributes:
        limit: Maximum allowed cost per session in USD
        input_price: Cost per input token (default: Opus 4.6)
        output_price: Cost per output token (default: Opus 4.6)
    """

    limit: float = 10.00
    input_price: float = DEFAULT_INPUT_PRICE
    output_price: float = DEFAULT_OUTPUT_PRICE

    # Session state
    total_cost: float = field(default=0.0, init=False)
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)
    loops: int = field(default=0, init=False)
    history: list = field(default_factory=list, init=False)
    started_at: str = field(default="", init=False)
    terminated: bool = field(default=False, init=False)

    def __post_init__(self):
        self.started_at = datetime.now().isoformat()

    def track(self, input_tokens: int, output_tokens: int) -> float:
        """Record token usage from an API call. Returns the cost of this call."""
        call_cost = (input_tokens * self.input_price) + (output_tokens * self.output_price)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += call_cost
        self.loops += 1

        self.history.append({
            "loop": self.loops,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "call_cost": round(call_cost, 6),
            "cumulative_cost": round(self.total_cost, 6),
            "timestamp": datetime.now().isoformat(),
        })

        return call_cost

    def check(self) -> None:
        """Check if budget is exceeded. Call this BEFORE each API call.

        Raises:
            CircuitOpenError: If total cost >= limit
        """
        if self.total_cost >= self.limit:
            self.terminated = True
            raise CircuitOpenError(
                cost=self.total_cost,
                limit=self.limit,
                loops=self.loops,
            )

    def remaining(self) -> float:
        """How much budget is left."""
        return max(0, self.limit - self.total_cost)

    def usage_pct(self) -> float:
        """Percentage of budget used (0-100+)."""
        if self.limit == 0:
            return 100.0
        return (self.total_cost / self.limit) * 100

    def summary(self) -> dict:
        """Return a summary of the session for logging/display."""
        return {
            "budget_limit": self.limit,
            "total_cost": round(self.total_cost, 4),
            "remaining": round(self.remaining(), 4),
            "usage_pct": round(self.usage_pct(), 1),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "loops": self.loops,
            "terminated": self.terminated,
            "started_at": self.started_at,
        }

    def status_line(self) -> str:
        """One-line status for terminal display."""
        bar_len = 20
        filled = int(min(self.usage_pct(), 100) / 100 * bar_len)
        bar = "#" * filled + "-" * (bar_len - filled)
        return (
            f"  Budget: [{bar}] ${self.total_cost:.4f} / ${self.limit:.2f} "
            f"({self.usage_pct():.1f}%) | {self.loops} loops"
        )


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Kill-Switch Demo")
    print("=" * 60)
    print()

    guard = BudgetGuard(limit=0.50)  # Low limit for demo

    # Simulate agent loops with growing context
    try:
        for i in range(100):
            # Simulate growing context (realistic: history accumulates)
            input_tokens = 3000 + (i * 800)
            output_tokens = 1500

            # CHECK BEFORE the call (this is the key pattern)
            guard.check()

            # Track the call
            cost = guard.track(input_tokens, output_tokens)
            print(f"  Loop {guard.loops}: +{input_tokens + output_tokens} tokens, "
                  f"+${cost:.4f}")
            print(guard.status_line())
            print()

    except CircuitOpenError as e:
        print()
        print("  !!! " + str(e))
        print()

    # Show summary
    import json
    print("  Session summary:")
    print(json.dumps(guard.summary(), indent=4))