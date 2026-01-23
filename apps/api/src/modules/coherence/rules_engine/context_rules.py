
from abc import ABC, abstractmethod
from typing import List, Any
from pydantic import BaseModel

class CoherenceRuleResult(BaseModel):
    rule_id: str
    is_violated: bool
    evidence: dict[str, Any] | None = None

class CoherenceRule(ABC):
    def __init__(self, project_context: Any):
        self.project_context = project_context

    @abstractmethod
    def check(self) -> CoherenceRuleResult:
        raise NotImplementedError
