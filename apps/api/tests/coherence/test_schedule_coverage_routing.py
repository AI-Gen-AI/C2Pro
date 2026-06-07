"""
BCK-064 regression tests — schedule evidence must mark TIME as assessed.

Root cause: DocumentType.SCHEDULE = "schedule" but the category registry
doc_type_priors uses key "schedule_gantt". Without the explicit mapping,
_seed_coverage_from_category_router() passes "schedule" to router.route()
which finds no prior floor, and schedule rows with task names/dates don't
have enough lexicon/structural signal to clear the threshold.

Suite ID: TS-UD-COH-SCH-001
"""

from __future__ import annotations

from src.coherence.graph.graph import _seed_coverage_from_category_router
from src.coherence.models import Clause

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schedule_clause(text: str = "Actividad: Firma del contrato | start: 2024-01-01 | end: 2024-01-31") -> Clause:
    return Clause(
        id="sch-001",
        text=text,
        data={"document_type": "schedule"},
    )


def _budget_clause(text: str = "Item: Excavación | quantity: 100 | unit_price: 50.0 | total: 5000") -> Clause:
    return Clause(
        id="bud-001",
        text=text,
        data={"document_type": "budget"},
    )


def _contract_clause(text: str = "Cláusula 1: Indemnización. El contratista responderá por daños y perjuicios.") -> Clause:
    return Clause(
        id="con-001",
        text=text,
        data={"document_type": "contract"},
    )


# ---------------------------------------------------------------------------
# TS-UD-COH-SCH-001 — BCK-064 schedule→TIME coverage
# ---------------------------------------------------------------------------


class TestScheduleCoverageRouting:
    """document_type='schedule' must map to TIME assessed in coverage_map."""

    def test_schedule_doc_type_marks_time_as_covered(self):
        """BCK-064: a clause with document_type='schedule' yields TIME=True."""
        clauses = [_schedule_clause()]
        coverage = _seed_coverage_from_category_router(clauses)
        assert coverage.get("TIME") is True, (
            f"TIME not in coverage — got {coverage}. "
            "Likely 'schedule' not mapped to 'schedule_gantt' registry priors."
        )

    def test_schedule_clause_with_minimal_text_still_covered(self):
        """Prior floor ensures coverage even when task text has no schedule keywords."""
        # Pure task description — no 'schedule', 'timeline', 'milestone' keyword
        clauses = [_schedule_clause("Instalación de transformador 100 MVA")]
        coverage = _seed_coverage_from_category_router(clauses)
        assert coverage.get("TIME") is True

    def test_budget_doc_type_marks_budget_as_covered(self):
        """Same class of bug: 'budget' must map to 'budget_boq' registry priors."""
        clauses = [_budget_clause()]
        coverage = _seed_coverage_from_category_router(clauses)
        assert coverage.get("BUDGET") is True, (
            f"BUDGET not in coverage — got {coverage}. "
            "Likely 'budget' not mapped to 'budget_boq' registry priors."
        )

    def test_contract_doc_type_marks_legal_as_covered(self):
        """Regression: existing 'contract' mapping must still work."""
        clauses = [_contract_clause()]
        coverage = _seed_coverage_from_category_router(clauses)
        assert coverage.get("LEGAL") is True

    def test_empty_clauses_returns_empty_coverage(self):
        """No clauses → empty coverage (no regression in boundary case)."""
        coverage = _seed_coverage_from_category_router([])
        assert coverage == {}

    def test_unknown_doc_type_does_not_crash(self):
        """Unmapped doc_type falls through gracefully — no prior, no crash."""
        clauses = [Clause(
            id="x-001",
            text="Some random document text",
            data={"document_type": "drawing"},
        )]
        coverage = _seed_coverage_from_category_router(clauses)
        # drawings have no priors — may or may not produce coverage based on text
        # the key assertion is: no exception is raised
        assert isinstance(coverage, dict)

    def test_schedule_and_contract_together_cover_time_and_legal(self):
        """Multi-document project: both TIME and LEGAL are assessed."""
        clauses = [
            _schedule_clause(),
            _contract_clause(),
        ]
        coverage = _seed_coverage_from_category_router(clauses)
        assert coverage.get("TIME") is True
        assert coverage.get("LEGAL") is True
