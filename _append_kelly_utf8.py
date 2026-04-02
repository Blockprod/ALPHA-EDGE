#!/usr/bin/env python
"""Append Kelly function to backtest_stats.py with proper UTF-8 encoding."""

kelly_code = """

# ------------------------------------------------------------------
# Kelly Criterion Validation
# ------------------------------------------------------------------
def validate_kelly_compliance(
    risk_pct: float,
    wr: float,
    pf: float,
    tolerance_factor: float = 4.0,
) -> dict[str, float | bool]:
    \"\"\"Validate if active risk_pct complies with Kelly Criterion.

    Kelly Criterion: f* = (WR * RR - (1 - WR)) / RR
    ALPHAEDGE uses 1/4-Kelly as conservative threshold.
    \"\"\"
    rr = pf if pf > 1.0 else (1.0 / pf) if pf > 0 else 1.0
    numerator = wr * rr - (1.0 - wr)
    kelly_fraction = numerator / rr if rr > 0 else 0.0
    kelly_fraction = max(0.0, kelly_fraction)
    kelly_fractional = kelly_fraction / tolerance_factor
    is_compliant = risk_pct <= kelly_fractional * 100.0
    margin_pct = (kelly_fractional * 100.0) - risk_pct
    return {
        "kelly_fraction": round(kelly_fraction, 4),
        "kelly_fractional": round(kelly_fractional, 4),
        "risk_pct": round(risk_pct, 4),
        "is_compliant": is_compliant,
        "margin_pct": round(margin_pct, 2),
    }
"""

with open("alphaedge/engine/backtest_stats.py", "a", encoding="utf-8") as f:
    f.write(kelly_code)

print("✅ Kelly function appended with proper UTF-8 encoding")
