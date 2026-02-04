"""
TS-UC-SEC-GAM-001: Anti-gaming detection tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.coherence.domain.anti_gaming import AlertEvent, AntiGamingDetector


class TestAntiGamingDetection:
    """Refers to Suite ID: TS-UC-SEC-GAM-001."""

    def test_001_mass_changes_11_in_hour_detected(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("change", user_id, f"sig-{idx}", now - timedelta(minutes=idx))
            for idx in range(11)
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.is_gaming is True
        assert "mass_changes" in result.violations

    def test_002_mass_changes_10_in_hour_allowed(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("change", user_id, f"sig-{idx}", now - timedelta(minutes=idx))
            for idx in range(10)
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.is_gaming is False

    def test_003_mass_changes_window_reset(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        old_events = [
            AlertEvent("change", user_id, f"sig-{idx}", now - timedelta(minutes=61 + idx))
            for idx in range(11)
        ]
        result = AntiGamingDetector().detect(old_events, now=now)
        assert result.is_gaming is False

    def test_004_resolve_reintroduce_3_times_detected(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        signature = "alert:scope:4.2"
        events = [
            AlertEvent("created", user_id, signature, now + timedelta(seconds=0)),
            AlertEvent("resolved", user_id, signature, now + timedelta(seconds=30)),
            AlertEvent("created", user_id, signature, now + timedelta(seconds=60)),
            AlertEvent("resolved", user_id, signature, now + timedelta(seconds=90)),
            AlertEvent("created", user_id, signature, now + timedelta(seconds=120)),
        ]
        result = AntiGamingDetector().detect(events, now=now + timedelta(seconds=121))
        assert result.is_gaming is True
        assert "resolve_reintroduce" in result.violations

    def test_005_resolve_reintroduce_2_times_allowed(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        signature = "alert:scope:4.2"
        events = [
            AlertEvent("created", user_id, signature, now),
            AlertEvent("resolved", user_id, signature, now + timedelta(seconds=30)),
            AlertEvent("created", user_id, signature, now + timedelta(seconds=60)),
        ]
        result = AntiGamingDetector().detect(events, now=now + timedelta(seconds=61))
        assert result.is_gaming is False

    def test_006_resolve_reintroduce_different_hash_allowed(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("created", user_id, "hash-a", now),
            AlertEvent("resolved", user_id, "hash-a", now + timedelta(seconds=30)),
            AlertEvent("created", user_id, "hash-b", now + timedelta(seconds=60)),
            AlertEvent("resolved", user_id, "hash-b", now + timedelta(seconds=90)),
            AlertEvent("created", user_id, "hash-c", now + timedelta(seconds=120)),
        ]
        result = AntiGamingDetector().detect(events, now=now + timedelta(seconds=121))
        assert result.is_gaming is False

    def test_007_high_score_few_docs_detected(self) -> None:
        result = AntiGamingDetector().detect(
            [],
            score=95.0,
            document_count=3,
            now=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc),
        )
        assert result.is_gaming is True
        assert "suspicious_high_score" in result.violations

    def test_008_high_score_many_docs_allowed(self) -> None:
        result = AntiGamingDetector().detect(
            [],
            score=95.0,
            document_count=8,
            now=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc),
        )
        assert result.is_gaming is False

    def test_009_high_score_threshold_boundary(self) -> None:
        result = AntiGamingDetector().detect(
            [],
            score=90.0,
            document_count=4,
            now=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc),
        )
        assert result.is_gaming is False

    def test_010_weight_change_25_percent_detected(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("weight_changed", user_id, "weights", now, weight_change_percent=25.0),
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.is_gaming is True
        assert "weight_manipulation" in result.violations

    def test_011_weight_change_15_percent_allowed(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("weight_changed", user_id, "weights", now, weight_change_percent=15.0),
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.is_gaming is False

    def test_012_weight_change_tracking_24h_window(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent(
                "weight_changed",
                user_id,
                "weights",
                now - timedelta(hours=25),
                weight_change_percent=30.0,
            ),
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.is_gaming is False

    def test_edge_001_multiple_violations_combined(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        signature = "alert:scope:4.2"
        events = [
            AlertEvent("created", user_id, signature, now + timedelta(seconds=0)),
            AlertEvent("resolved", user_id, signature, now + timedelta(seconds=30)),
            AlertEvent("created", user_id, signature, now + timedelta(seconds=60)),
            AlertEvent("resolved", user_id, signature, now + timedelta(seconds=90)),
            AlertEvent("created", user_id, signature, now + timedelta(seconds=120)),
            AlertEvent("weight_changed", user_id, "weights", now, weight_change_percent=25.0),
        ]
        result = AntiGamingDetector().detect(
            events,
            score=95.0,
            document_count=3,
            now=now + timedelta(seconds=121),
        )
        assert result.is_gaming is True
        assert len(result.violations) >= 2
        assert result.reason == "multiple_violations"

    def test_edge_002_violation_penalty_application(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("change", user_id, f"sig-{idx}", now - timedelta(minutes=idx))
            for idx in range(11)
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert result.penalty_points == 5

    def test_edge_003_violation_audit_logging(self) -> None:
        now = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("change", user_id, f"sig-{idx}", now - timedelta(minutes=idx))
            for idx in range(11)
        ]
        result = AntiGamingDetector().detect(events, now=now)
        assert len(result.audit_logs) >= 1
        assert "mass_changes" in result.audit_logs[0]
