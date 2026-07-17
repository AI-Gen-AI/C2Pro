"""
Search domain entities for Analysis module.

Refers to Suite ID: TS-UD-ANA-HYB-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.core.json_types import JsonDict


@dataclass(frozen=True)
class HybridSearchResult:
    """Refers to Suite ID: TS-UD-ANA-HYB-001."""

    document_id: UUID
    clause_id: UUID | None
    text: str
    semantic_score: float
    keyword_score: float
    fusion_weight: float
    rank: int
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("text is required")
        if not (0.0 <= self.semantic_score <= 1.0):
            raise ValueError("semantic_score must be between 0.0 and 1.0")
        if not (0.0 <= self.keyword_score <= 1.0):
            raise ValueError("keyword_score must be between 0.0 and 1.0")
        if not (0.0 <= self.fusion_weight <= 1.0):
            raise ValueError("fusion_weight must be between 0.0 and 1.0")
        if self.rank <= 0:
            raise ValueError("rank must be greater than 0")

    @property
    def hybrid_score(self) -> float:
        return (self.fusion_weight * self.semantic_score) + (
            (1.0 - self.fusion_weight) * self.keyword_score
        )
