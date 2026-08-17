"""
Load an expert/golden corpus (JSON) into `GoldenProject` objects (ADR-009 §G).

Tolerant parser for the golden JSON the Abengoa investigation produces: one object per
project with `project_id`, `expert_score`, optional `per_category_scores` / `totals`, and
`findings[]`. Only the fields the calibration gate needs (expert score + labelled
findings) are required; malformed findings are dropped rather than raising, so a partially
imperfect LLM extraction still yields a usable corpus.

Refers to Suite ID: TS-UA-COH-CALIB-GOLDEN-LOADER-001.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from src.coherence.calibration.golden import GoldenFinding, GoldenProject

_VALID_CATEGORIES = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _opt_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _finding(raw: dict[str, Any]) -> GoldenFinding | None:
    category = str(raw.get("category", "")).strip().upper()
    if category not in _VALID_CATEGORIES:
        return None
    severity = str(raw.get("severity", "medium")).strip().lower()
    if severity not in _VALID_SEVERITIES:
        severity = "medium"
    return GoldenFinding(
        category=category,
        severity=severity,
        is_true_positive=bool(raw.get("is_true_positive", True)),
    )


def parse_golden(data: Iterable[Any]) -> list[GoldenProject]:
    """Map already-decoded project objects into GoldenProjects (dropping malformed findings)."""
    projects: list[GoldenProject] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        findings = tuple(
            finding
            for raw in obj.get("findings", [])
            if isinstance(raw, dict) and (finding := _finding(raw)) is not None
        )
        projects.append(
            GoldenProject(
                project_id=str(obj.get("project_id", "")),
                expert_score=_opt_float(obj.get("expert_score")),
                findings=findings,
            )
        )
    return projects


def load_golden(json_text: str) -> list[GoldenProject]:
    """Parse golden-corpus JSON text into GoldenProjects.

    Accepts a JSON array of project objects, a single project object, or an object with a
    ``"projects"`` array.
    """
    data = json.loads(json_text)
    if isinstance(data, dict):
        data = data.get("projects", [data])
    if not isinstance(data, list):
        raise ValueError("golden corpus must be a JSON array of project objects")
    return parse_golden(data)


__all__ = ["load_golden", "parse_golden"]
