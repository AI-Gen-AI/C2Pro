"""
Decision Intelligence domain entities.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FinalDecisionPackage:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""

    coherence_score: int
    risks: list[dict[str, str]]
    evidence_links: list[str]
    citations: list[str]
    approved_by: str | None = None
    approved_at: str | None = None

