"""
Coherence anti-gaming policy tests (TDD - RED phase).

Refers to Suite ID: TS-UD-COH-GAM-001.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.coherence.domain.anti_gaming import AlertEvent, AntiGamingDetector


class TestAntiGamingPolicy:
    """Refers to Suite ID: TS-UD-COH-GAM-001"""

    def test_001_detect_mass_changes_15_in_30min(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("updated", user_id, f"sig-{i}", now - timedelta(minutes=i))
            for i in range(15)
        ]
        detector = AntiGamingDetector(mass_changes_threshold=10, mass_changes_window_minutes=30)

        result = detector.detect(events, now=now)

        assert result.is_gaming is True
        assert "mass_changes" in result.violations

    def test_002_no_violation_10_in_60min(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("updated", user_id, f"sig-{i}", now - timedelta(minutes=i))
            for i in range(10)
        ]

        result = AntiGamingDetector().detect(events, now=now)

        assert result.is_gaming is False

    def test_003_mass_changes_window_sliding(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("updated", user_id, f"sig-old-{i}", now - timedelta(minutes=35 + i))
            for i in range(20)
        ]
        detector = AntiGamingDetector(mass_changes_threshold=10, mass_changes_window_minutes=30)

        result = detector.detect(events, now=now)

        assert result.is_gaming is False

    def test_004_mass_changes_flag_for_review(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("updated", user_id, f"sig-{i}", now - timedelta(minutes=i))
            for i in range(11)
        ]

        result = AntiGamingDetector().detect(events, now=now)

        assert any("mass_changes" in log for log in result.audit_logs)

    def test_005_detect_resolve_reintroduce_4_times(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        sig = "alert:budget:overrun"
        events = [
            AlertEvent("created", user_id, sig, now + timedelta(seconds=0)),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=10)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=20)),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=30)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=40)),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=50)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=60)),
        ]

        result = AntiGamingDetector(repeat_threshold=4).detect(events, now=now + timedelta(seconds=61))

        assert result.is_gaming is True
        assert "resolve_reintroduce" in result.violations

    def test_006_no_violation_2_times(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        sig = "alert:budget:overrun"
        events = [
            AlertEvent("created", user_id, sig, now),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=10)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=20)),
        ]

        result = AntiGamingDetector(repeat_threshold=3).detect(events, now=now + timedelta(seconds=21))

        assert result.is_gaming is False

    def test_007_hash_comparison_same_content(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        sig = "alert:scope:same-hash"
        events = [
            AlertEvent("created", user_id, sig, now + timedelta(seconds=0)),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=10)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=20)),
            AlertEvent("resolved", user_id, sig, now + timedelta(seconds=30)),
            AlertEvent("created", user_id, sig, now + timedelta(seconds=40)),
        ]

        result = AntiGamingDetector(repeat_threshold=3).detect(events, now=now + timedelta(seconds=41))

        assert result.is_gaming is True
        assert "resolve_reintroduce" in result.violations

    def test_008_penalty_minus_5_points(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        events = [
            AlertEvent("updated", user_id, f"sig-{i}", now - timedelta(minutes=i))
            for i in range(11)
        ]

        result = AntiGamingDetector(penalty_per_violation=5).detect(events, now=now)

        assert result.penalty_points == 5

    def test_009_detect_95_percent_3_docs(self) -> None:
        result = AntiGamingDetector().detect(
            events=[],
            score=95.0,
            document_count=3,
            now=datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc),
        )

        assert result.is_gaming is True
        assert "suspicious_high_score" in result.violations

    def test_010_no_violation_95_percent_50_docs(self) -> None:
        result = AntiGamingDetector().detect(
            events=[],
            score=95.0,
            document_count=50,
            now=datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc),
        )

        assert result.is_gaming is False

    def test_011_threshold_90_percent_5_docs(self) -> None:
        result = AntiGamingDetector().detect(
            events=[],
            score=90.0,
            document_count=5,
            now=datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc),
        )

        assert result.is_gaming is True
        assert "suspicious_high_score" in result.violations

    def test_012_require_audit_action(self) -> None:
        result = AntiGamingDetector().detect(
            events=[],
            score=95.0,
            document_count=3,
            now=datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc),
        )

        assert any("suspicious_high_score" in log for log in result.audit_logs)

    def test_013_detect_weight_change_25_percent(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        event = AlertEvent(
            "weight_changed",
            uuid4(),
            "weights:v1",
            now,
            weight_change_percent=25.0,
        )

        result = AntiGamingDetector().detect([event], now=now)

        assert result.is_gaming is True
        assert "weight_manipulation" in result.violations

    def test_014_no_violation_change_15_percent(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        event = AlertEvent(
            "weight_changed",
            uuid4(),
            "weights:v1",
            now,
            weight_change_percent=15.0,
        )

        result = AntiGamingDetector().detect([event], now=now)

        assert result.is_gaming is False

    def test_015_24h_window_tracking(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        outside_window = AlertEvent(
            "weight_changed",
            uuid4(),
            "weights:old",
            now - timedelta(hours=25),
            weight_change_percent=30.0,
        )

        result = AntiGamingDetector().detect([outside_window], now=now)

        assert result.is_gaming is False

    def test_016_notify_admin_action(self) -> None:
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        event = AlertEvent(
            "weight_changed",
            uuid4(),
            "weights:v1",
            now,
            weight_change_percent=30.0,
        )

        result = AntiGamingDetector().detect([event], now=now)

        assert any("weight_manipulation" in log for log in result.audit_logs)

    def test_017_resolve_reference_time_from_empty_events(self) -> None:
        """When no events provided, use current UTC time."""
        result = AntiGamingDetector().detect(events=[], now=None)
        # Should not raise error and should use current time
        assert result.is_gaming is False

    def test_018_resolve_reference_time_with_explicit_now(self) -> None:
        """When explicit 'now' provided, use it instead of deriving from events."""
        past_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        event = AlertEvent("created", user_id, "sig", past_time)

        # Provide explicit 'now' far in the future
        explicit_now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)

        result = AntiGamingDetector(mass_changes_threshold=0).detect([event], now=explicit_now)
        # Event is outside the window, so no mass_changes violation
        assert result.is_gaming is False

    def test_019_resolve_reference_time_from_aware_timestamp(self) -> None:
        """When event has aware timestamp, convert to UTC."""
        aware_time = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        event = AlertEvent("created", user_id, "sig", aware_time)

        result = AntiGamingDetector().detect([event], now=None)
        # Should handle aware timestamp without error
        assert result.is_gaming is False

    def test_020_multiple_violations_reason(self) -> None:
        """When multiple violations occur, reason is 'multiple_violations'."""
        now = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
        user_id = uuid4()

        # Create mass changes
        mass_events = [
            AlertEvent("updated", user_id, f"sig-{i}", now - timedelta(minutes=i))
            for i in range(15)
        ]

        # Add weight manipulation
        weight_event = AlertEvent(
            "weight_changed", user_id, "weights:v1", now, weight_change_percent=25.0
        )

        all_events = mass_events + [weight_event]

        result = AntiGamingDetector(mass_changes_threshold=10).detect(
            all_events, score=95.0, document_count=3, now=now
        )

        assert result.is_gaming is True
        assert len(result.violations) >= 2
        assert result.reason == "multiple_violations"
