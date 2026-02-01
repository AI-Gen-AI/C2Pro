"""
Anti-Gaming Detection Tests (TDD - RED Phase)

Refers to Suite ID: TS-UC-SEC-GAM-001.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.coherence.domain.anti_gaming import AlertEvent, AntiGamingDetector


class TestAntiGamingDetection:
    """Refers to Suite ID: TS-UC-SEC-GAM-001."""

    def test_detect_resolve_reintroduce_pattern(self):
        """
        Detect resolve-reintroduce gaming: same alert created/resolved 3x in 5 minutes.
        """
        now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        alert_signature = "alert:missing_clause:clause_4_2"

        events = [
            AlertEvent(type="created", user_id=user_id, signature=alert_signature, timestamp=now),
            AlertEvent(
                type="resolved",
                user_id=user_id,
                signature=alert_signature,
                timestamp=now + timedelta(minutes=1),
            ),
            AlertEvent(
                type="created",
                user_id=user_id,
                signature=alert_signature,
                timestamp=now + timedelta(minutes=2),
            ),
            AlertEvent(
                type="resolved",
                user_id=user_id,
                signature=alert_signature,
                timestamp=now + timedelta(minutes=3),
            ),
            AlertEvent(
                type="created",
                user_id=user_id,
                signature=alert_signature,
                timestamp=now + timedelta(minutes=4),
            ),
        ]

        detector = AntiGamingDetector(window_minutes=5, repeat_threshold=3)
        result = detector.detect(events)

        assert result.is_gaming is True
        assert result.reason == "resolve_reintroduce"
