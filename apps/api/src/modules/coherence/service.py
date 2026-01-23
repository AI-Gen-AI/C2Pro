"""
C2Pro - Coherence Service (Mock Implementation)

This module provides a service to calculate or retrieve the coherence score
for a project.

This is a MOCK implementation for dependency injection purposes. The real
implementation would involve complex business logic and database queries.
"""

from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional, Dict, Any

# Mocking the response object structure for the service layer
class CoherenceScore:
    def __init__(self, project_id: UUID, score: int, breakdown: Dict[str, int], top_drivers: list[str]):
        self.project_id = project_id
        self.score = score
        self.breakdown = breakdown
        self.top_drivers = top_drivers
        self.calculated_at = datetime.utcnow()

# Mocking a database of projects and scores
# In a real app, this would be queried from a database.
MOCK_PROJECT_DB = {
    # This project will have a score
    "00000000-0000-0000-0000-000000000001": {"name": "Project with Score"},
    # This project exists but has no score yet
    "00000000-0000-0000-0000-000000000002": {"name": "Project Pending Score"},
}

MOCK_SCORE_DB = {
    "00000000-0000-0000-0000-000000000001": CoherenceScore(
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        score=85,
        breakdown={"critical": 1, "high": 3, "medium": 5, "low": 2},
        top_drivers=[
            "Missing budget information for WBS item 1.2.3",
            "Schedule dates conflict with contract milestones",
            "Ambiguous liability clause in contract section 8.4"
        ]
    )
}

class CoherenceService:
    """
    A mock service to manage project coherence scores.
    """
    def project_exists(self, project_id: UUID) -> bool:
        """Simulates checking if a project exists in the database."""
        return str(project_id) in MOCK_PROJECT_DB

    def get_latest_score_for_project(self, project_id: UUID) -> Optional[CoherenceScore]:
        """
        Simulates retrieving the latest calculated coherence score for a project.

        Returns:
            A CoherenceScore object if a score exists, otherwise None.
        """
        # This deterministic mock will return a score for a known UUID,
        # and None for another known UUID to test the 'pending' state.
        return MOCK_SCORE_DB.get(str(project_id))

# --- Dependency Injection ---
# In a real FastAPI app, you'd have a more robust dependency management system.
_coherence_service_instance = None

def get_coherence_service() -> CoherenceService:
    """Singleton factory for the CoherenceService."""
    global _coherence_service_instance
    if _coherence_service_instance is None:
        _coherence_service_instance = CoherenceService()
    return _coherence_service_instance
