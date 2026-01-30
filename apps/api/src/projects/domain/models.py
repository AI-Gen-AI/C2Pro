"""
Domain models for the Project bounded context.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class ProjectStatus(str, Enum):
    """Possible states of a project in its lifecycle."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectType(str, Enum):
    """Types of projects supported by the system."""
    CONSTRUCTION = "construction"
    ENGINEERING = "engineering"
    INDUSTRIAL = "industrial"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


@dataclass
class Project:
    """
    Represents a Project as a pure domain entity and Aggregate Root.
    A project groups all related documents, analyses, and artifacts.
    """
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    code: str | None
    project_type: ProjectType
    status: ProjectStatus
    estimated_budget: float | None
    currency: str
    start_date: datetime | None
    end_date: datetime | None
    
    # Analysis results are part of the project's state
    coherence_score: int | None
    last_analysis_at: datetime | None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime

    # The list of documents is part of the project aggregate,
    # but we might only load IDs or lightweight objects to avoid fetching everything.
    # For now, we'll keep it simple and assume the use case layer will populate this.
    # In a full DDD model, this would be a list of Document entities.
    _document_types: list[str] = field(default_factory=list)

    def is_ready_for_analysis(self) -> bool:
        """
        Business rule: A project is ready for analysis if it has a contract.
        This logic now lives within the domain entity.
        """
        return "contract" in self._document_types

    def update_document_list(self, document_types: list[str]):
        """A method to update the internal state used by business rules."""
        self._document_types = document_types

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status.value}')>"
