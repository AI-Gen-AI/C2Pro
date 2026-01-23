from __future__ import annotations

SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 25,
    "high": 10,
    "medium": 5,
    "low": 1,
}

SENSITIVITY = 50

RULE_SEVERITY: dict[str, str] = {
    "R14": "critical",
    "R12": "critical",
    "R2": "high",
    "R02": "high",
    "R15": "high",
    "R20": "medium",
    "R6": "medium",
}
