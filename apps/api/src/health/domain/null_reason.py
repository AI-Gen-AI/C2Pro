"""Why a Health value is null (ADR-018 honest-null discipline).

Extracted into its own leaf module so the Health domain forms an acyclic graph:
``health_vector`` -> ``single_document_coverage`` -> ``category_coverage`` -> ``null_reason``.
``health_vector`` re-exports :class:`HealthNullReason` for backwards compatibility, so
existing imports keep working unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class HealthNullReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    BUDGET_EXHAUSTED = "budget_exhausted"


__all__ = ["HealthNullReason"]
