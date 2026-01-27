"""
Data Transfer Objects (DTOs) for the Analysis module.
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class CoherenceScoreResponse(BaseModel):
    """
    Response model for a project's coherence score.
    Represents the data needed by frontend dashboard widgets.
    """
    project_id: UUID
    score: int | None = Field(None, ge=0, le=100, description="Coherence score from 0 to 100.")
    status: str = Field(..., description="Calculation status (e.g., 'CALCULATED', 'PENDING', 'NOT_FOUND')")
    calculated_at: datetime | None = Field(None, description="Timestamp of the last calculation.")
    
    breakdown: dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
        description="Dictionary with the count of alerts by severity."
    )
    top_drivers: list[str] = Field(
        default_factory=list,
        description="Top 3 reasons or rules that most impacted the score."
    )

    model_config = ConfigDict(from_attributes=True)
