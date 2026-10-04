"""#714 trusted-state candidate persistence contract — RED first."""
from sqlalchemy import CheckConstraint

from src.analysis.adapters.persistence.models import DocumentArtifactORM


def test_document_artifact_schema_carries_version_hash_and_trust_state() -> None:
    """Persisted artifacts need an envelope distinct from their frozen payload."""
    columns = set(DocumentArtifactORM.__table__.columns.keys())

    assert {"artifact_version", "artifact_hash", "trust_state"} <= columns


def test_document_artifact_trust_state_constraint_supports_required_states() -> None:
    """The durable trust state must support the #706 HITL boundary."""
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in DocumentArtifactORM.__table__.constraints
        if isinstance(constraint, CheckConstraint) and getattr(constraint, "name", None)
    }

    trust_check = checks.get("ck_document_artifacts_trust_state", "")
    for expected in ("proposed", "trusted", "rejected", "superseded"):
        assert expected in trust_check.lower()
