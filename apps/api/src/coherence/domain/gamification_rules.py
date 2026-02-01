
import abc
from typing import List, NamedTuple, Dict
from enum import Enum, auto
from datetime import datetime, timedelta
from collections import Counter

# --- DTOs and Enums ---

class RecommendedAction(Enum):
    """Enumerates the actions to be taken when a violation is detected."""
    FLAG_FOR_REVIEW = auto()
    REQUIRE_AUDIT = auto()
    NOTIFY_ADMIN = auto()

class GamificationViolation(NamedTuple):
    """Represents a single detected violation of a gamification rule."""
    rule_id: str
    message: str
    recommended_action: RecommendedAction
    penalty_points: int = 0

class UserEvent(NamedTuple):
    """Represents a single user event to be evaluated."""
    timestamp: datetime
    type: str
    hash: str = ""
    old_weight: float = 0.0
    new_weight: float = 0.0

class GamificationRuleInput(NamedTuple):
    """Wraps all necessary data for a rule evaluation."""
    user_id: str
    events: List[UserEvent]
    current_score: float = 0.0
    document_count: int = 0

# --- Rule Definition ---

class GamificationRule(abc.ABC):
    """Abstract base class for a gamification anti-abuse rule."""
    @abc.abstractmethod
    async def evaluate(self, input_data: GamificationRuleInput) -> List[GamificationViolation]:
        pass

# --- Concrete Rule Implementations ---

class MassChangeRule(GamificationRule):
    """Detects if a user makes too many changes in a given time window."""
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.rule_id = f"MASS_CHANGE_{max_events}_{window_seconds}"

    async def evaluate(self, input_data: GamificationRuleInput) -> List[GamificationViolation]:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        recent_events = [
            event for event in input_data.events 
            if event.type == "edit" and event.timestamp >= window_start
        ]
        
        if len(recent_events) > self.max_events:
            return [GamificationViolation(
                rule_id=self.rule_id,
                message=f"User made {len(recent_events)} edits in the last {self.window_seconds / 60:.0f} minutes.",
                recommended_action=RecommendedAction.FLAG_FOR_REVIEW
            )]
        return []

class ResolveReintroduceRule(GamificationRule):
    """Detects if a user repeatedly resolves and re-introduces the same issue."""
    def __init__(self, threshold: int, penalty_points: int = 0):
        self.threshold = threshold
        self.penalty_points = penalty_points
        self.rule_id = "RESOLVE_REINTRODUCE"
        
    async def evaluate(self, input_data: GamificationRuleInput) -> List[GamificationViolation]:
        violations = []
        resolve_events = [e for e in input_data.events if e.type == "resolve" and e.hash]
        hash_counts = Counter(e.hash for e in resolve_events)
        
        for issue_hash, count in hash_counts.items():
            if count > self.threshold:
                violations.append(GamificationViolation(
                    rule_id=self.rule_id,
                    message=f"Issue with content hash '{issue_hash}' was resolved and re-introduced {count} times.",
                    recommended_action=RecommendedAction.FLAG_FOR_REVIEW,
                    penalty_points=self.penalty_points
                ))
        return violations

class HighScoreLowDocsRule(GamificationRule):
    """Detects if a user achieves a high score with very few documents."""
    def __init__(self, score_threshold: float, doc_count_threshold: int):
        self.score_threshold = score_threshold
        self.doc_count_threshold = doc_count_threshold
        self.rule_id = "HIGH_SCORE_LOW_DOCS"
        
    async def evaluate(self, input_data: GamificationRuleInput) -> List[GamificationViolation]:
        if input_data.current_score > self.score_threshold and input_data.document_count < self.doc_count_threshold:
            return [GamificationViolation(
                rule_id=self.rule_id,
                message=f"User has a high score ({input_data.current_score}) with only {input_data.document_count} documents.",
                recommended_action=RecommendedAction.REQUIRE_AUDIT
            )]
        return []

class WeightChangeRule(GamificationRule):
    """Detects if a user makes a large weight change in a given time window."""
    def __init__(self, change_threshold_percent: float, window_seconds: int):
        self.change_threshold = change_threshold_percent
        self.window_seconds = window_seconds
        self.rule_id = "LARGE_WEIGHT_CHANGE"

    async def evaluate(self, input_data: GamificationRuleInput) -> List[GamificationViolation]:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        recent_changes = [
            event for event in input_data.events
            if event.type == "weight_change" and event.timestamp >= window_start
        ]
        
        for event in recent_changes:
            if event.old_weight > 0:
                change = abs(event.new_weight - event.old_weight) / event.old_weight
                if change >= self.change_threshold:
                    return [GamificationViolation(
                        rule_id=self.rule_id,
                        message=f"A weight was changed by {change:.1%}, exceeding the {self.change_threshold:.1%} threshold.",
                        recommended_action=RecommendedAction.NOTIFY_ADMIN
                    )]
        return []
