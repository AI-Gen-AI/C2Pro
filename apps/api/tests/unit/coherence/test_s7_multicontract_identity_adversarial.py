"""C1/C2 economic correlation is not independent without exact contract identity.

Pure FindingSignals below demonstrate a grouping defect, not a demonstrated
production path: production assemblers aggregate one maximum price per project.
"""

from __future__ import annotations

from src.coherence.cross_document.assembly import cross_document_signals
from src.coherence.economic_signal_dedup import (
    distinct_economic_impacts,
    economic_discrepancy_key,
)
from src.coherence.models import Clause, FindingSignal
from src.coherence.scoring import ScoringService


def _economic(rule: str, contract: str | None, revision: str = "rev-c1") -> FindingSignal:
    evidence = {
        "sources": [
            {
                "family": "budget",
                "document_id": "budget-doc",
                "revision_id": "budget-r1",
                "source_locator": "Presupuesto!5",
                "blob_sha256": "a" * 64,
            }
        ]
    }
    if contract is not None:
        evidence["contract_source"] = {
            "family": "contract",
            "document_id": contract,
            "revision_id": revision,
            "source_locator": f"{contract}!clause",
            "blob_sha256": "c" * 64,
        }
    return FindingSignal(
        rule_id=rule,
        clause_id=f"{contract or 'UNKNOWN'}:{rule}",
        source="deterministic",
        impact_score=0.83 if rule == "DET-CRS-CONBUD" else 1.0,
        confidence=1.0,
        severity="critical",
        category="BUDGET",
        raw_data={
            "contract_total": 1_000_000,
            "budget_total": 1_500_000,
            "delta": 500_000,
            "evidence": evidence,
        },
    )


def test_scenario_a_four_alerts_two_independent_contract_facts() -> None:
    signals = [
        _economic("DET-CRS-CONBUD", "C1"),
        _economic("DET-CRS-NEGMARGIN", "C1"),
        _economic("DET-CRS-CONBUD", "C2"),
        _economic("DET-CRS-NEGMARGIN", "C2"),
    ]
    assert len(distinct_economic_impacts(signals, lambda s: s.impact_score)) == 2
    assert economic_discrepancy_key(signals[0]) != economic_discrepancy_key(signals[2])


def test_scenario_b_cross_contract_partial_detectors_must_not_merge() -> None:
    signals = [
        _economic("DET-CRS-CONBUD", "C1"),
        _economic("DET-CRS-NEGMARGIN", "C2"),
    ]
    assert len(distinct_economic_impacts(signals, lambda s: s.impact_score)) == 2
    assert (
        ScoringService()
        .calculate_detailed(
            signals, 5, coverage_map=dict.fromkeys(ScoringService._ALL_CATEGORIES, True)
        )
        .total_findings
        == 2
    )


def test_scenario_c_different_contract_revisions_must_not_merge() -> None:
    signals = [
        _economic("DET-CRS-CONBUD", "C1", "r1"),
        _economic("DET-CRS-NEGMARGIN", "C1", "r2"),
    ]
    assert len(distinct_economic_impacts(signals, lambda s: s.impact_score)) == 2


def test_unknown_contract_identity_is_fail_closed_even_with_shared_budget() -> None:
    signals = [
        _economic("DET-CRS-CONBUD", None),
        _economic("DET-CRS-NEGMARGIN", None),
    ]
    assert all(economic_discrepancy_key(s) is None for s in signals)
    assert len(distinct_economic_impacts(signals, lambda s: s.impact_score)) == 2


def test_current_production_assembler_reduces_two_contract_totals_to_one_pair() -> None:
    # This is not proof that an independent second project contract has been
    # evaluated: the actual aggregator computes one maximum contract_total.
    sources = [
        Clause(
            id="C1",
            text="Contract C1: 1,000,000 EUR",
            data={"total_amount": 1_000_000, "document_id": "C1"},
        ),
        Clause(
            id="C2",
            text="Contract C2: 1,000,000 EUR",
            data={"total_amount": 1_000_000, "document_id": "C2"},
        ),
        Clause(
            id="BUD",
            text="Budget stated 1,500,000 EUR",
            data={
                "stated_total": 1_500_000,
                "stated_total_source": {
                    "family": "budget",
                    "document_id": "budget-doc",
                    "revision_id": "budget-r1",
                    "source_locator": "Presupuesto!5",
                },
            },
        ),
    ]
    signals = cross_document_signals(sources)
    assert {s.rule_id for s in signals} == {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"}
    assert len(signals) == 2  # one aggregate comparison, NOT two contract pairs


def _v2_independent_conflicts(signals: list[FindingSignal]) -> int:
    from uuid import uuid4

    from src.coherence.scoring import calculate_v2_from_signals
    from src.coherence.services.v2.evidence_service import EvidenceBundle

    categories = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
    bundles = {
        cat: EvidenceBundle(
            count=5,
            evidence_coverage=1.0,
            evidence_freshness=1.0,
            avg_technical_reliability=0.9,
            missing_required=[],
            references=["d1", "d2", "d3", "d4", "d5"],
        )
        for cat in categories
    }
    result = calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=bundles,
        applicability_map=dict.fromkeys(categories, (True, None)),
        project_id=uuid4(),
    )
    return len(next(c for c in result.categories if c.category == "BUDGET").detected_conflicts)


def _canary_independent_impacts(signals: list[FindingSignal]) -> int:
    from src.coherence.graph.nodes import _build_category_breakdown

    breakdown = _build_category_breakdown(
        signals,
        dict.fromkeys(ScoringService._ALL_CATEGORIES, True),
        {"BUDGET": 45.0},
    )
    return next(item for item in breakdown if item.category == "financial").alert_count


def test_multicontract_v1_v2_canary_agree_on_independent_impacts() -> None:
    scenarios = {
        "A": (
            [
                _economic("DET-CRS-CONBUD", "C1"),
                _economic("DET-CRS-NEGMARGIN", "C1"),
                _economic("DET-CRS-CONBUD", "C2"),
                _economic("DET-CRS-NEGMARGIN", "C2"),
            ],
            2,
        ),
        "B": (
            [
                _economic("DET-CRS-CONBUD", "C1"),
                _economic("DET-CRS-NEGMARGIN", "C2"),
            ],
            2,
        ),
        "C": (
            [
                _economic("DET-CRS-CONBUD", "C1", "r1"),
                _economic("DET-CRS-NEGMARGIN", "C1", "r2"),
            ],
            2,
        ),
        "one_contract": (
            [
                _economic("DET-CRS-CONBUD", "C1"),
                _economic("DET-CRS-NEGMARGIN", "C1"),
            ],
            1,
        ),
        "unknown": (
            [
                _economic("DET-CRS-CONBUD", None),
                _economic("DET-CRS-NEGMARGIN", None),
            ],
            2,
        ),
    }
    for name, (signals, expected) in scenarios.items():
        coverage = dict.fromkeys(ScoringService._ALL_CATEGORIES, True)
        assert (
            ScoringService().calculate_detailed(signals, 5, coverage_map=coverage).total_findings
            == expected
        ), name
        assert _v2_independent_conflicts(signals) == expected, name
        assert _canary_independent_impacts(signals) == expected, name
        # The two detector alert objects remain fully visible and distinct.
        from src.coherence.graph.nodes import _signal_to_alert

        assert len([_signal_to_alert(s) for s in signals]) == len(signals), name


async def test_canonical_contract_source_rejects_same_amount_from_two_documents() -> None:
    from uuid import uuid4

    from src.coherence.budget_clause_builder import load_contract_total_source

    class _Rows:
        def __init__(self, data):
            self.data = data

        def mappings(self):
            return self

        def all(self):
            return self.data

    class _Session:
        async def execute(self, *_args):
            return _Rows([
                {"document_id": str(uuid4()), "revision_id": str(uuid4()),
                 "blob_sha256": "a" * 64, "source_locator": str(uuid4())},
                {"document_id": str(uuid4()), "revision_id": str(uuid4()),
                 "blob_sha256": "b" * 64, "source_locator": str(uuid4())},
            ])

    source = await load_contract_total_source(_Session(), uuid4(), uuid4(), 1_000_000)
    assert source is None, "two contracts with the same price must be ambiguous"
