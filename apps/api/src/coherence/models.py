from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.coherence.application.dtos.coherence_v2_dtos import CoherenceV2Payload

# Canonical six-value risk / alert taxonomy — see
# src.analysis.domain.risk_categories for the authoritative enum. The
# legacy lowercase / "financial" / "general" values are accepted so
# pre-existing payloads keep validating while clients migrate.
AlertCategory = Literal[
    # Canonical
    "LEGAL",
    "SCHEDULE",
    "QUALITY",
    "SCOPE",
    "TECHNICAL",
    "BUDGET",
    # Legacy — normalized at the persistence boundary
    "legal",
    "financial",
    "technical",
    "schedule",
    "scope",
    "quality",
    "general",
]

# Severity levels for continuous scoring (TASK-504: strict 5-level taxonomy)
SeverityLevel = Literal["critical", "high", "medium", "low", "info"]

# Source of finding (deterministic rules vs LLM semantic analysis)
FindingSource = Literal["deterministic", "llm"]

# The 6 coherence categories + cross-dimensional
CoherenceCategory = Literal["BUDGET", "TIME", "LEGAL", "SCOPE", "TECHNICAL", "QUALITY", "CROSS"]


def impact_to_severity(impact: float) -> SeverityLevel:
    """
    Convert continuous impact score (0.0-1.0) to categorical severity.

    TASK-504: Strict 5-level severity taxonomy enforcement.

    Thresholds:
        >= 0.85 → critical
        >= 0.60 → high
        >= 0.35 → medium
        >= 0.15 → low
        <  0.15 → info
    """
    if impact >= 0.85:
        return "critical"
    elif impact >= 0.60:
        return "high"
    elif impact >= 0.35:
        return "medium"
    elif impact >= 0.15:
        return "low"
    else:
        return "info"


class FindingSignal(BaseModel):
    """
    Unified signal format for the Scoring Arbiter (Agent C).

    Replaces binary rule_violated with continuous impact_score (0.0-1.0).
    Used by both deterministic evaluators (Agent A) and LLM evaluators (Agent B).

    Attributes:
        rule_id: Identifier of the rule that generated this signal (e.g., DET-BUD-OVERRUN)
        clause_id: ID of the clause that was evaluated
        source: Whether this came from deterministic rules or LLM analysis
        impact_score: Continuous severity from 0.0 (no issue) to 1.0 (catastrophic)
        confidence: How certain the evaluator is (1.0 for deterministic, 0.0-1.0 for LLM)
        severity: Categorical severity for backward compatibility
        category: Which of the 6 coherence categories this belongs to
        evidence_summary: One-sentence explanation of the finding
        quote: Exact text from the clause that triggered the rule
        raw_data: Structured data relevant to the finding (for diagnostics)
    """

    rule_id: str = Field(..., description="Rule identifier (e.g., DET-BUD-OVERRUN)")
    clause_id: str = Field(..., description="ID of the evaluated clause")
    source: FindingSource = Field(default="deterministic", description="deterministic or llm")

    # Continuous scoring (the key v0.3 improvement)
    impact_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Continuous severity: 0.0 = no issue, 1.0 = catastrophic"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Evaluator confidence: 1.0 = certain, 0.5 = borderline"
    )

    # Categorical (backward compat)
    severity: SeverityLevel = Field(
        default="medium",
        description="Categorical severity for backward compatibility"
    )
    category: CoherenceCategory = Field(
        default="SCOPE",
        description="One of the 6 coherence categories"
    )

    # Evidence
    evidence_summary: str = Field(
        default="",
        description="One-sentence explanation of the finding"
    )
    quote: str = Field(
        default="",
        description="Exact text from clause that triggered the rule"
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data for diagnostics"
    )


class Clause(BaseModel):
    """
    Represents a specific clause or segment of a document.
    """

    id: str = Field(..., description="Unique identifier for the clause.")
    text: str = Field(..., description="The textual content of the clause.")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data extracted from or associated with the clause (e.g., budget figures, dates, status).",
    )


class ProjectContext(BaseModel):
    """
    Represents the full context of a project to be evaluated, now with structured clauses.
    """

    id: str = Field(..., description="Unique identifier for the project.")
    clauses: list[Clause] = Field(
        default_factory=list,
        description="List of structured clauses from documents relevant to the project.",
    )


class Evidence(BaseModel):
    """
    Represents the specific evidence supporting an alert.
    """

    source_clause_id: str = Field(
        ..., description="The ID of the clause that serves as direct evidence."
    )
    claim: str = Field(..., description="A concise claim or summary derived from the evidence.")
    quote: str = Field(
        ..., description="The direct quote from the clause text that serves as evidence."
    )
    # Additional fields can be added here in future iterations, e.g., confidence, page_number.


class Alert(BaseModel):
    """
    Represents an alert generated by a rule.
    """

    rule_id: str = Field(..., description="The ID of the rule that triggered this alert.")
    severity: str = Field(
        ..., description="The severity of the triggered alert (e.g., critical, high, medium, low)."
    )
    category: AlertCategory = Field(
        default="general", description="The category of the alert (legal, financial, technical, schedule, scope)."
    )
    message: str = Field(..., description="A descriptive message for the alert.")
    evidence: Evidence = Field(..., description="Structured evidence supporting the alert.")


class SeverityCount(BaseModel):
    """
    Represents the count of alerts by severity level.

    TASK-504: Strict 5-level severity taxonomy (Critical, High, Medium, Low, Info).
    """

    critical: int = Field(default=0, description="Number of critical alerts.")
    high: int = Field(default=0, description="Number of high severity alerts.")
    medium: int = Field(default=0, description="Number of medium severity alerts.")
    low: int = Field(default=0, description="Number of low severity alerts.")
    info: int = Field(default=0, description="Number of info severity alerts.")


class CategoryBreakdown(BaseModel):
    """
    Represents the coherence score breakdown for a specific category.
    """

    category: AlertCategory = Field(..., description="The alert category.")
    score: float | None = Field(
        None, description="Category score (null when UNASSESSED)."
    )
    alert_count: int = Field(..., description="Total number of alerts in this category.")
    severity_breakdown: SeverityCount = Field(
        ..., description="Breakdown of alerts by severity within this category."
    )
    impact_percentage: float = Field(
        ..., description="Percentage of impact this category has on the overall score."
    )
    state: str = Field(
        "assessed_findings",
        description="unassessed | assessed_clean | assessed_findings",
    )
    baseline_estimated: bool = Field(
        False, description="True when score is the inherent-risk baseline (clean)."
    )


class CoherenceResult(BaseModel):
    """
    Represents the complete result of a coherence evaluation, including alerts and the final score.
    """

    overall_score: float | None = Field(
        ...,
        description="The overall calculated coherence score for the project, or null when evidence is insufficient.",
    )
    alerts: list[Alert] = Field(..., description="List of alerts generated during the evaluation.")
    category_breakdown: list[CategoryBreakdown] = Field(
        default_factory=list,
        description="Breakdown of the score by alert category."
    )
    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the score was calculated."
    )
    score_version: str = Field(
        default="v0_flag_based",
        description="Immutable scoring algorithm version used for this result.",
    )
    score_reason: str | None = Field(
        default=None,
        description="Machine-readable reason when a score is unavailable or version-specific handling applies.",
    )
    score_missing_dimensions: list[str] | None = Field(
        default=None,
        description="Dimensions that prevented a complete score, when applicable.",
    )


class EnrichedCoherenceResult(BaseModel):
    """
    Extended coherence result with diagnostic fields for v0.3 scoring.

    CoherenceResult remains the public API shape; this adds internal diagnostics
    for debugging, dashboards, and score curve validation.
    """

    # Core result (same as CoherenceResult)
    overall_score: float | None = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="The granular coherence score (5.0-97.0 typical range), or null when evidence is insufficient"
    )
    alerts: list[Alert] = Field(
        default_factory=list,
        description="List of alerts (backward compat)"
    )
    category_breakdown: list[CategoryBreakdown] = Field(
        default_factory=list,
        description="Breakdown by alert category"
    )
    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of calculation"
    )
    score_version: str = Field(
        default="v0_flag_based",
        description="Immutable scoring algorithm version used for this result.",
    )
    score_reason: str | None = Field(
        default=None,
        description="Machine-readable reason when a score is unavailable or version-specific handling applies.",
    )
    score_missing_dimensions: list[str] | None = Field(
        default=None,
        description="Dimensions that prevented a complete score, when applicable.",
    )

    # v0.3 diagnostic fields
    finding_signals: list[FindingSignal] = Field(
        default_factory=list,
        description="Raw signals from all evaluators (det + llm)"
    )
    deterministic_findings_count: int = Field(
        default=0,
        description="Number of findings from deterministic rules"
    )
    llm_findings_count: int = Field(
        default=0,
        description="Number of findings from LLM analysis"
    )
    scope_factor: float = Field(
        default=1.0,
        description="Scope normalization factor used in scoring"
    )
    penalty_density: float = Field(
        default=0.0,
        description="Raw weighted penalty density before decay"
    )
    avg_impact: float = Field(
        default=0.0,
        description="Average impact_score across all findings"
    )
    avg_confidence: float = Field(
        default=0.0,
        description="Average confidence across all findings"
    )
    llm_cost_usd: float = Field(
        default=0.0,
        description="Total LLM cost for this evaluation"
    )
    evaluation_mode: str = Field(
        default="standard",
        description="low_budget_mode or standard"
    )


class DashboardSummary(BaseModel):
    """
    Consolidated view of project coherence for the dashboard.

    ECOA v2 (ADR-009 §7.2 step 1): the optional `categories_v2` field carries
    the locked v2 contract. Defaults to None so v1 clients are unaffected.
    """
    project_id: str
    tenant_id: str
    global_score: float | None
    coherence_score: float | None
    sub_scores: dict[str, float | None]
    weights_used: dict[str, float]
    alert_count: int
    document_count: int
    methodology_version: str = "3.0"
    score_version: str | None = None
    score_reason: str | None = None
    score_missing_dimensions: list[str] | None = None
    last_updated: datetime
    categories_v2: "CoherenceV2Payload | None" = None

