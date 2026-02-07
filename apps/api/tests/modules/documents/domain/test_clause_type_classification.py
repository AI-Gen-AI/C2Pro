"""
TS-UD-DOC-CLS-002: Clause Types & Classification tests.
"""

import pytest

from src.documents.domain.models import ClauseType
from src.documents.domain.services.clause_classification import classify_clause_type


class TestClauseTypeClassification:
    """Refers to Suite ID: TS-UD-DOC-CLS-002"""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Payment terms: the buyer will pay within 30 days.", ClauseType.PAYMENT),
            ("Penalty for late delivery applies at 2% per week.", ClauseType.PENALTY),
            ("Scope of work includes excavation and foundation.", ClauseType.SCOPE),
            ("Warranty period is 24 months from acceptance.", ClauseType.WARRANTY),
            ("Termination may occur for material breach.", ClauseType.TERMINATION),
            ("General information without contractual meaning.", ClauseType.OTHER),
        ],
    )
    def test_clause_type_classification(self, text, expected):
        """Classifies clause types from text content."""
        assert classify_clause_type(text) == expected
