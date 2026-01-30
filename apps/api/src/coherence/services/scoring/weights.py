from __future__ import annotations

from src.analysis.domain.enums import AlertSeverity

SEVERITY_WEIGHTS: dict[AlertSeverity, int] = {
    AlertSeverity.CRITICAL: 25,
    AlertSeverity.HIGH: 10,
    AlertSeverity.MEDIUM: 5,
    AlertSeverity.LOW: 1,
}

DEFAULT_SENSITIVITY = 50
