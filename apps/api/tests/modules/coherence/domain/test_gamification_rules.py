
import pytest
from typing import List, NamedTuple, Dict
from enum import Enum, auto
from datetime import datetime, timedelta

# This import will fail as the modules do not exist yet.
from apps.api.src.coherence.domain.gamification_rules import (
    MassChangeRule,
    ResolveReintroduceRule,
    HighScoreLowDocsRule,
    WeightChangeRule,
    GamificationViolation,
    RecommendedAction,
    # Input DTOs
    UserEvent,
    GamificationRuleInput,
)

# --- Temporary definitions for test development ---
class TempRecommendedAction(Enum):
    FLAG_FOR_REVIEW = auto()
    REQUIRE_AUDIT = auto()
    NOTIFY_ADMIN = auto()

class TempGamificationViolation(NamedTuple):
    rule_id: str
    message: str
    recommended_action: TempRecommendedAction
    penalty_points: int

class TempUserEvent(NamedTuple):
    timestamp: datetime
    type: str
    hash: str = ""
    old_weight: float = 0.0
    new_weight: float = 0.0

class TempGamificationRuleInput(NamedTuple):
    user_id: str
    events: List[TempUserEvent]
    current_score: float = 0.0
    document_count: int = 0


# --- Test Cases ---
@pytest.mark.asyncio
class TestGamificationRules:
    """Refers to Suite ID: TS-UD-COH-GAM-001"""

    # --- Mass Changes Rule (test_001-004) ---
    async def test_001_detect_mass_changes_15_in_30min(self):
        rule = MassChangeRule(max_events=10, window_seconds=1800) # 10 events in 30 mins
        now = datetime.now()
        events = [UserEvent(timestamp=now - timedelta(minutes=i), type="edit") for i in range(15)]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        
        violations = await rule.evaluate(input_data)
        assert len(violations) == 1
        assert violations[0].recommended_action == RecommendedAction.FLAG_FOR_REVIEW

    async def test_002_no_violation_10_in_60min(self):
        rule = MassChangeRule(max_events=10, window_seconds=3600)
        now = datetime.now()
        events = [UserEvent(timestamp=now - timedelta(minutes=i*5), type="edit") for i in range(10)]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0

    async def test_003_mass_changes_window_sliding(self):
        rule = MassChangeRule(max_events=5, window_seconds=60)
        now = datetime.now()
        # 4 events inside the window, 6 outside
        events = [
            UserEvent(timestamp=now - timedelta(seconds=i*10), type="edit") for i in range(4)
        ] + [
            UserEvent(timestamp=now - timedelta(seconds=i*10+70), type="edit") for i in range(6)
        ]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0 # Should only count the 4 recent events

    # --- Resolve/Re-introduce Rule (test_005-008) ---
    async def test_005_detect_resolve_reintroduce_4_times(self):
        rule = ResolveReintroduceRule(threshold=3)
        issue_hash = "abcde"
        events = [
            UserEvent(timestamp=datetime.now(), type="resolve", hash=issue_hash),
            UserEvent(timestamp=datetime.now(), type="resolve", hash=issue_hash),
            UserEvent(timestamp=datetime.now(), type="resolve", hash=issue_hash),
            UserEvent(timestamp=datetime.now(), type="resolve", hash=issue_hash),
        ]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 1

    async def test_007_008_hash_comparison_and_penalty(self):
        rule = ResolveReintroduceRule(threshold=2, penalty_points=-5)
        events = [
            UserEvent(timestamp=datetime.now(), type="resolve", hash="hash1"),
            UserEvent(timestamp=datetime.now(), type="resolve", hash="hash2"),
            UserEvent(timestamp=datetime.now(), type="resolve", hash="hash1"),
            UserEvent(timestamp=datetime.now(), type="resolve", hash="hash1"),
        ]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 1
        assert violations[0].message == "Issue with content hash 'hash1' was resolved and re-introduced 3 times."
        assert violations[0].penalty_points == -5

    # --- High Score / Low Docs Rule (test_009-012) ---
    async def test_009_detect_95_percent_3_docs(self):
        rule = HighScoreLowDocsRule(score_threshold=90.0, doc_count_threshold=5)
        input_data = GamificationRuleInput(user_id="u1", events=[], current_score=95.0, document_count=3)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 1
        assert violations[0].recommended_action == RecommendedAction.REQUIRE_AUDIT

    async def test_010_no_violation_95_percent_50_docs(self):
        rule = HighScoreLowDocsRule(score_threshold=90.0, doc_count_threshold=5)
        input_data = GamificationRuleInput(user_id="u1", events=[], current_score=95.0, document_count=50)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0

    async def test_011_threshold_90_percent_5_docs(self):
        rule = HighScoreLowDocsRule(score_threshold=90.0, doc_count_threshold=5)
        # At the threshold, should not violate
        input_data = GamificationRuleInput(user_id="u1", events=[], current_score=90.0, document_count=5)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0

    # --- Weight Change Rule (test_013-016) ---
    async def test_013_detect_weight_change_25_percent(self):
        rule = WeightChangeRule(change_threshold_percent=0.25, window_seconds=86400)
        events = [UserEvent(timestamp=datetime.now(), type="weight_change", old_weight=1.0, new_weight=1.25)]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 1
        assert violations[0].recommended_action == RecommendedAction.NOTIFY_ADMIN

    async def test_014_no_violation_change_15_percent(self):
        rule = WeightChangeRule(change_threshold_percent=0.25, window_seconds=86400)
        events = [UserEvent(timestamp=datetime.now(), type="weight_change", old_weight=1.0, new_weight=1.15)]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0

    async def test_015_24h_window_tracking(self):
        rule = WeightChangeRule(change_threshold_percent=0.25, window_seconds=86400)
        now = datetime.now()
        events = [
            # This change is outside the 24h window and should be ignored
            UserEvent(timestamp=now - timedelta(hours=25), type="weight_change", old_weight=1.0, new_weight=1.30),
            # This change is inside the window but below the threshold
            UserEvent(timestamp=now - timedelta(hours=1), type="weight_change", old_weight=1.0, new_weight=1.10)
        ]
        input_data = GamificationRuleInput(user_id="u1", events=events)
        violations = await rule.evaluate(input_data)
        assert len(violations) == 0
