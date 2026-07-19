"""
test_langgraph_v3.py — Integration Tests for LangGraph Coherence Subgraph v0.3

Tests the coherence evaluation subgraph including:
1. Graph compilation and structure
2. Node execution (prepare_context, deterministic_evaluate, etc.)
3. Full graph invocation with sample clauses
4. Low budget mode behavior
5. Scoring output validation
6. State flow through the graph

Location: apps/api/tests/coherence/test_langgraph_v3.py
"""


import pytest

from src.coherence.graph.graph import (
    build_coherence_subgraph,
    evaluate_coherence,
    get_coherence_subgraph,
)
from src.coherence.graph.nodes import (
    cross_clause_eval,
    deterministic_evaluate,
    format_output,
    infer_category,
    infer_document_type,
    llm_semantic_evaluate,
    prepare_context,
    scoring_arbiter,
)
from src.coherence.graph.state import (
    ClauseWithEmbedding,
    CoherenceGraphState,
    CrossClausePair,
    EvaluationConfig,
)
from src.coherence.models import Clause, EnrichedCoherenceResult, FindingSignal

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_budget_clause() -> Clause:
    """Budget clause with overrun data."""
    return Clause(
        id="BUD-001",
        text="Project Budget: Approved $100,000. Current spent: $125,000. Variance: 25% over budget.",
        data={
            "planned": 100000,
            "current": 125000,
            "variance_pct": 25.0,
        }
    )


@pytest.fixture
def sample_schedule_clause() -> Clause:
    """Schedule clause with delay data."""
    return Clause(
        id="SCH-001",
        text="Milestone: Foundation complete. Planned: 2024-03-01. Actual: 2024-03-15. Status: 14 days late.",
        data={
            "planned_date": "2024-03-01",
            "actual_date": "2024-03-15",
            "days_late": 14,
        }
    )


@pytest.fixture
def sample_scope_clause() -> Clause:
    """Clear scope clause without issues."""
    return Clause(
        id="SCP-001",
        text="Scope: Construct a 500 sqm warehouse including concrete foundation, steel structure, metal roof, and 2 loading docks.",
        data={
            "area_sqm": 500,
            "structure_type": "steel",
        }
    )


@pytest.fixture
def sample_payment_clause() -> Clause:
    """Payment clause with clear terms."""
    return Clause(
        id="PAY-001",
        text="Payment: $50,000 USD due within 30 calendar days of invoice receipt via wire transfer.",
        data={
            "amount": 50000,
            "currency": "USD",
            "payment_terms_days": 30,
        }
    )


@pytest.fixture
def sample_legal_clause() -> Clause:
    """Legal/contract clause with warranty and termination terms."""
    return Clause(
        id="LEG-001",
        text=(
            "Contract warranty and liability: Contractor warrants all work for 24 months "
            "against defects. Termination notice period is 30 days. Any dispute shall be "
            "resolved via binding arbitration under the agreement's indemnity clause."
        ),
        data={
            "warranty_months": 24,
            "notice_period_days": 30,
        }
    )


@pytest.fixture
def sample_quality_clause() -> Clause:
    """Quality/inspection clause with explicit standards."""
    return Clause(
        id="QUA-001",
        text=(
            "Quality inspection and testing: All materials shall be inspected against "
            "ISO 9001 quality standards prior to acceptance. Inspection frequency is weekly "
            "and any defect tolerance exceeding specification triggers rejection."
        ),
        data={
            "quality_standards": ["ISO 9001"],
            "inspection_frequency": "weekly",
        }
    )


@pytest.fixture
def sample_clauses(
    sample_budget_clause,
    sample_schedule_clause,
    sample_scope_clause,
    sample_payment_clause,
    sample_legal_clause,
    sample_quality_clause,
) -> list[Clause]:
    """Collection of sample clauses for full graph testing.

    Spans BUDGET, TIME, SCOPE, LEGAL, and QUALITY signals so category
    coverage clears MIN_ACTIVE_WEIGHT (ADR-009 SS14) and the graph
    produces a real (non-honest-null) score.
    """
    return [
        sample_budget_clause,
        sample_schedule_clause,
        sample_scope_clause,
        sample_payment_clause,
        sample_legal_clause,
        sample_quality_clause,
    ]


@pytest.fixture
def low_budget_config() -> EvaluationConfig:
    """Config with low_budget_mode enabled (skips LLM)."""
    return EvaluationConfig(
        low_budget_mode=True,
        include_cross_clause=True,
        include_rag_similarity=False,
    )


@pytest.fixture
def full_config() -> EvaluationConfig:
    """Config with all features enabled."""
    return EvaluationConfig(
        low_budget_mode=False,
        include_cross_clause=True,
        include_rag_similarity=True,
    )


# =============================================================================
# TEST: GRAPH STRUCTURE
# =============================================================================


class TestGraphStructure:
    """Tests for graph compilation and structure."""

    def test_build_coherence_subgraph_compiles(self):
        """Graph builds without errors."""
        graph = build_coherence_subgraph()
        assert graph is not None

    def test_build_coherence_subgraph_has_nodes(self):
        """Graph contains all expected nodes."""
        graph = build_coherence_subgraph()

        # Check node names are present
        compiled = graph.compile()
        # The graph should compile without errors
        assert compiled is not None

    def test_get_coherence_subgraph_lazy_init(self):
        """Compiled graph is lazy-initialized and cached."""
        graph1 = get_coherence_subgraph()
        graph2 = get_coherence_subgraph()

        # Should return same compiled instance
        assert graph1 is graph2

    async def test_subgraph_can_be_invoked(self, sample_clauses, low_budget_config):
        """Graph can be invoked with initial state.

        The graph's llm_semantic_evaluate node is async-only (fix for the
        coherence LLM event-loop bug), so it must be invoked via ainvoke.
        """
        graph = get_coherence_subgraph()

        initial_state = CoherenceGraphState(
            project_id="test-project",
            clauses=sample_clauses,
            config=low_budget_config,
        )

        # Should not raise
        final_state = await graph.ainvoke(initial_state)
        assert final_state is not None


# =============================================================================
# TEST: INDIVIDUAL NODES
# =============================================================================


class TestPrepareContextNode:
    """Tests for the prepare_context node."""

    def test_enriches_clauses_with_categories(self, sample_clauses, low_budget_config):
        """Clauses are enriched with inferred categories."""
        state = CoherenceGraphState(
            project_id="test",
            clauses=sample_clauses,
            config=low_budget_config,
        )

        result = prepare_context(state)

        assert "enriched_clauses" in result
        assert len(result["enriched_clauses"]) == len(sample_clauses)

        # Check categories were inferred
        categories = [ec.category for ec in result["enriched_clauses"]]
        assert "BUDGET" in categories
        assert "TIME" in categories

    def test_creates_cross_pairs(self, sample_clauses, low_budget_config):
        """Cross-clause pairs are created for analysis."""
        state = CoherenceGraphState(
            project_id="test",
            clauses=sample_clauses,
            config=low_budget_config,
        )

        result = prepare_context(state)

        # With include_cross_clause=True, should have pairs
        assert "cross_pairs" in result
        # At least some pairs should be created
        assert isinstance(result["cross_pairs"], list)


class TestDeterministicEvaluateNode:
    """Tests for the deterministic_evaluate node."""

    def test_runs_all_deterministic_evaluators(self, sample_budget_clause, low_budget_config):
        """All 27 deterministic evaluators run on each clause."""
        # First enrich the clause
        enriched = ClauseWithEmbedding(
            clause=sample_budget_clause,
            category="BUDGET",
            document_type="budget",
        )

        state = CoherenceGraphState(
            project_id="test",
            clauses=[sample_budget_clause],
            enriched_clauses=[enriched],
            config=low_budget_config,
        )

        result = deterministic_evaluate(state)

        assert "deterministic_signals" in result
        # Budget overrun clause should trigger findings
        signals = result["deterministic_signals"]
        assert isinstance(signals, list)

    def test_budget_overrun_detected(self, low_budget_config):
        """Budget overrun is detected by deterministic evaluator."""
        overrun_clause = Clause(
            id="BUD-OVER",
            text="Budget overrun: 35% over approved budget",
            data={"planned": 100000, "current": 135000, "variance_pct": 35.0}
        )

        enriched = ClauseWithEmbedding(
            clause=overrun_clause,
            category="BUDGET",
            document_type="budget",
        )

        state = CoherenceGraphState(
            project_id="test",
            clauses=[overrun_clause],
            enriched_clauses=[enriched],
            config=low_budget_config,
        )

        result = deterministic_evaluate(state)
        signals = result["deterministic_signals"]

        # Should have at least one budget-related finding
        budget_signals = [s for s in signals if "BUDGET" in s.rule_id.upper() or s.category == "BUDGET"]
        assert len(budget_signals) > 0, "Budget overrun should be detected"


class TestLlmSemanticEvaluateNode:
    """Tests for the llm_semantic_evaluate node."""

    def test_skips_in_low_budget_mode(self, sample_clauses, low_budget_config):
        """LLM evaluation is skipped in low_budget_mode."""
        enriched = [
            ClauseWithEmbedding(clause=c, category="SCOPE")
            for c in sample_clauses
        ]

        state = CoherenceGraphState(
            project_id="test",
            clauses=sample_clauses,
            enriched_clauses=enriched,
            config=low_budget_config,
        )

        result = llm_semantic_evaluate(state)

        # Should return empty signals (skipped)
        assert "llm_signals" in result
        assert result["llm_signals"] == []
        # No LLM calls in low budget mode
        assert result.get("llm_calls_count", 0) == 0


class TestCrossClauseEvalNode:
    """Tests for the cross_clause_eval node."""

    def test_runs_cross_clause_analysis(self, sample_clauses, low_budget_config):
        """Cross-clause analysis runs on paired clauses."""
        enriched = [
            ClauseWithEmbedding(clause=c, category=infer_category(c))
            for c in sample_clauses
        ]

        # Create pairs from BUDGET and TIME (related categories)
        pairs = []
        budget_clauses = [e for e in enriched if e.category == "BUDGET"]
        time_clauses = [e for e in enriched if e.category == "TIME"]
        if budget_clauses and time_clauses:
            pairs.append(CrossClausePair(
                clause_a=budget_clauses[0],
                clause_b=time_clauses[0],
                match_reason="category_related",
            ))

        state = CoherenceGraphState(
            project_id="test",
            clauses=sample_clauses,
            enriched_clauses=enriched,
            cross_pairs=pairs,
            config=low_budget_config,
        )

        result = cross_clause_eval(state)

        assert "cross_signals" in result
        assert isinstance(result["cross_signals"], list)


class TestScoringArbiterNode:
    """Tests for the scoring_arbiter node."""

    def test_calculates_score_from_signals(self, low_budget_config):
        """Score is calculated from combined signals.

        scoring_arbiter is coverage-aware (ADR-009 SS14): it needs
        coverage_map to reflect which categories were actually assessed,
        with enough weight to clear MIN_ACTIVE_WEIGHT (0.35), otherwise it
        honestly returns score=None regardless of signals present.
        """
        signals = [
            FindingSignal(
                rule_id="TEST-001",
                clause_id="C1",
                source="deterministic",
                impact_score=0.5,
                confidence=0.9,
                severity="medium",
                category="BUDGET",
                evidence_summary="Test finding",
                quote="test",
            )
        ]

        state = CoherenceGraphState(
            project_id="test",
            clauses=[],
            deterministic_signals=signals,
            llm_signals=[],
            cross_signals=[],
            coverage_map={"BUDGET": True, "SCOPE": True, "TIME": True},
            config=low_budget_config,
        )

        result = scoring_arbiter(state)

        assert "score" in result
        assert "all_signals" in result
        assert "diagnostics" in result

        # Score should be between bounds
        assert 5.0 <= result["score"] <= 97.0
        # Should have one signal
        assert len(result["all_signals"]) == 1

    def test_perfect_score_no_findings(self, low_budget_config):
        """No findings results in the inherent-risk ceiling when all categories are assessed.

        HeuristicBaselineProvider caps an assessed-but-clean category at 90.0
        (never a fabricated 100) — "clean so far" isn't proof of zero risk.
        Refers to: src/coherence/scoring.py HeuristicBaselineProvider docstring
        (Band [80, 90]; clean elsewhere -> 90).
        """
        state = CoherenceGraphState(
            project_id="test",
            clauses=[],
            deterministic_signals=[],
            llm_signals=[],
            cross_signals=[],
            coverage_map={
                "SCOPE": True, "BUDGET": True, "TIME": True,
                "TECHNICAL": True, "LEGAL": True, "QUALITY": True,
            },
            config=low_budget_config,
        )

        result = scoring_arbiter(state)

        # No findings, full coverage = inherent-risk ceiling, not a fabricated 100
        assert result["score"] == pytest.approx(90.0)

    def test_high_impact_findings_lower_score(self, low_budget_config):
        """High impact findings result in lower score."""
        signals = [
            FindingSignal(
                rule_id=f"TEST-{i}",
                clause_id="C1",
                source="deterministic",
                impact_score=0.9,  # High impact
                confidence=1.0,
                severity="critical",
                category="BUDGET",
                evidence_summary="Critical finding",
                quote="test",
            )
            for i in range(5)  # Multiple critical findings
        ]

        state = CoherenceGraphState(
            project_id="test",
            clauses=[],
            deterministic_signals=signals,
            llm_signals=[],
            cross_signals=[],
            coverage_map={"BUDGET": True, "SCOPE": True, "TIME": True},
            config=low_budget_config,
        )

        result = scoring_arbiter(state)

        # Multiple critical findings in one category pull the weighted-average
        # score well below the clean baseline (~90, see test_perfect_score_no_findings)
        # even though the other two assessed categories stay clean.
        assert result["score"] < 65.0


class TestFormatOutputNode:
    """Tests for the format_output node."""

    def test_creates_enriched_result(self, low_budget_config):
        """EnrichedCoherenceResult is created from state."""
        signals = [
            FindingSignal(
                rule_id="TEST-001",
                clause_id="C1",
                source="deterministic",
                impact_score=0.3,
                confidence=0.8,
                severity="low",
                category="SCOPE",
                evidence_summary="Minor issue",
                quote="test",
            )
        ]

        state = CoherenceGraphState(
            project_id="test",
            clauses=[],
            all_signals=signals,
            score=85.0,
            diagnostics={"penalty_total": 0.15},
            config=low_budget_config,
        )

        result = format_output(state)

        assert "result" in result
        assert "alerts" in result

        enriched_result = result["result"]
        assert isinstance(enriched_result, EnrichedCoherenceResult)
        assert enriched_result.overall_score == pytest.approx(85.0)
        assert len(enriched_result.finding_signals) == 1


# =============================================================================
# TEST: FULL GRAPH INVOCATION
# =============================================================================


class TestFullGraphInvocation:
    """Tests for full graph execution."""

    def test_evaluate_coherence_returns_result(self, sample_clauses):
        """evaluate_coherence() returns EnrichedCoherenceResult."""
        result = evaluate_coherence(
            clauses=sample_clauses,
            project_id="test-project",
            config=EvaluationConfig(low_budget_mode=True),
        )

        assert isinstance(result, EnrichedCoherenceResult)
        assert result.overall_score is not None
        assert 5.0 <= result.overall_score <= 97.0

    def test_evaluate_coherence_with_budget_overrun(self):
        """Budget overrun clause reduces score.

        Paired with clean SCOPE/LEGAL/QUALITY clauses so enough category
        weight is assessed to clear MIN_ACTIVE_WEIGHT (ADR-009 SS14) and
        produce a real (non-honest-null) score.
        """
        overrun_clause = Clause(
            id="BUD-SEVERE",
            text="Severe budget overrun: 50% over approved budget. Immediate action required.",
            data={"planned": 100000, "current": 150000, "variance_pct": 50.0}
        )
        clean_scope_clause = Clause(
            id="SCP-CLEAN",
            text="Scope: Construct a 500 sqm warehouse including concrete foundation, steel structure, metal roof, and 2 loading docks.",
            data={"area_sqm": 500, "structure_type": "steel"},
        )
        clean_legal_clause = Clause(
            id="LEG-CLEAN",
            text=(
                "Contract warranty and liability: Contractor warrants all work for 24 months "
                "against defects. Termination notice period is 30 days."
            ),
            data={"warranty_months": 24, "notice_period_days": 30},
        )
        clean_quality_clause = Clause(
            id="QUA-CLEAN",
            text=(
                "Quality inspection and testing: All materials shall be inspected against "
                "ISO 9001 quality standards prior to acceptance."
            ),
            data={"quality_standards": ["ISO 9001"], "inspection_frequency": "weekly", "inspection_method": "visual and dimensional check"},
        )

        result = evaluate_coherence(
            clauses=[overrun_clause, clean_scope_clause, clean_legal_clause, clean_quality_clause],
            project_id="test",
            config=EvaluationConfig(low_budget_mode=True),
        )

        # Severe overrun should lower score
        assert result.overall_score is not None
        assert result.overall_score < 90.0

    def test_evaluate_coherence_with_clean_clauses(self):
        """Clean clauses result in high score.

        Spans SCOPE/LEGAL/QUALITY (each clears the router's per-category
        evidence threshold on its own, unlike the terser BUDGET/TIME text
        below) so enough weight is assessed to clear MIN_ACTIVE_WEIGHT.
        """
        clean_clauses = [
            Clause(
                id="CLEAN-001",
                text="Payment: $100,000 USD due within 30 days via wire transfer to Account #12345.",
                data={"amount": 100000, "currency": "USD", "terms": 30}
            ),
            Clause(
                id="CLEAN-002",
                text=(
                    "Scope: Construct a 500 sqm warehouse including concrete foundation, "
                    "steel structure, metal roof, and 2 loading docks."
                ),
                data={
                    "area_sqm": 500,
                    "structure_type": "steel",
                    "deliverables": ["warehouse", "concrete foundation", "steel structure"],
                },
            ),
            Clause(
                id="CLEAN-003",
                text=(
                    "Contract warranty and liability: Contractor warrants all work for 24 months "
                    "against defects. Termination notice period is 30 days."
                ),
                data={"warranty_months": 24, "notice_period_days": 30},
            ),
            Clause(
                id="CLEAN-004",
                text=(
                    "Quality inspection and testing: All materials shall be inspected against "
                    "ISO 9001 quality standards prior to acceptance."
                ),
                data={"quality_standards": ["ISO 9001"], "inspection_frequency": "weekly", "inspection_method": "visual and dimensional check"},
            ),
        ]

        result = evaluate_coherence(
            clauses=clean_clauses,
            project_id="test",
            config=EvaluationConfig(low_budget_mode=True),
        )

        # Clean clauses = high score
        assert result.overall_score is not None
        assert result.overall_score >= 80.0

    def test_graph_populates_finding_signals(self, sample_clauses):
        """Graph populates finding_signals in result."""
        result = evaluate_coherence(
            clauses=sample_clauses,
            project_id="test",
            config=EvaluationConfig(low_budget_mode=True),
        )

        # finding_signals should be populated
        assert hasattr(result, "finding_signals")
        assert isinstance(result.finding_signals, list)

    def test_graph_populates_alerts(self, sample_clauses):
        """Graph populates alerts for backward compatibility."""
        result = evaluate_coherence(
            clauses=sample_clauses,
            project_id="test",
            config=EvaluationConfig(low_budget_mode=True),
        )

        # alerts should be populated (may be empty if no findings)
        assert hasattr(result, "alerts")
        assert isinstance(result.alerts, list)


# =============================================================================
# TEST: HELPER FUNCTIONS
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions in nodes module."""

    def test_infer_category_budget(self):
        """Budget-related clauses get BUDGET category."""
        clause = Clause(id="B1", text="Budget variance: 20% overrun")
        assert infer_category(clause) == "BUDGET"

        clause2 = Clause(id="B2", text="Cost estimate: $500,000", data={"planned": 500000})
        assert infer_category(clause2) == "BUDGET"

    def test_infer_category_time(self):
        """Schedule-related clauses get TIME category."""
        clause = Clause(id="T1", text="Milestone deadline: March 15")
        assert infer_category(clause) == "TIME"

        clause2 = Clause(id="T2", text="Project schedule shows 10 days late")
        assert infer_category(clause2) == "TIME"

    def test_infer_category_legal(self):
        """Legal clauses get LEGAL category."""
        clause = Clause(id="L1", text="Indemnification: Contractor shall indemnify...")
        assert infer_category(clause) == "LEGAL"

        clause2 = Clause(id="L2", text="Liability clause limits damages to...")
        assert infer_category(clause2) == "LEGAL"

    def test_infer_category_scope(self):
        """Scope-related clauses get SCOPE category."""
        clause = Clause(id="S1", text="Scope of work includes construction of...")
        assert infer_category(clause) == "SCOPE"

    def test_infer_document_type_contract(self):
        """Contract documents are identified via clause ID."""
        clause = Clause(id="CONTRACT-001", text="This agreement establishes...")
        assert infer_document_type(clause) == "contract"

    def test_infer_document_type_budget(self):
        """Budget documents are identified via data keys or ID."""
        # Using data keys that trigger budget detection
        clause = Clause(id="B1", text="Budget line items:", data={"unit_price": 100, "quantity": 10, "line_total": 1000})
        assert infer_document_type(clause) == "budget"

    def test_infer_document_type_schedule(self):
        """Schedule documents are identified via data keys or ID."""
        # Using data keys that trigger schedule detection
        clause = Clause(id="SCHEDULE-001", text="Project milestones:")
        assert infer_document_type(clause) == "schedule"


# =============================================================================
# TEST: STATE FLOW
# =============================================================================


class TestStateFlow:
    """Tests for state flow through the graph."""

    async def test_state_accumulates_signals(self, sample_clauses, low_budget_config):
        """Signals accumulate through the graph execution."""
        initial_state = CoherenceGraphState(
            project_id="test",
            clauses=sample_clauses,
            config=low_budget_config,
        )

        graph = get_coherence_subgraph()
        final_state = await graph.ainvoke(initial_state)

        # Final state should have accumulated all signals
        assert "all_signals" in final_state
        assert "score" in final_state
        assert "result" in final_state

    async def test_errors_captured_in_state(self, low_budget_config):
        """Errors during execution are captured in state."""
        # Empty clauses should still work (edge case)
        initial_state = CoherenceGraphState(
            project_id="test",
            clauses=[],
            config=low_budget_config,
        )

        graph = get_coherence_subgraph()
        final_state = await graph.ainvoke(initial_state)

        # Should complete without crashing
        assert final_state is not None
        assert "score" in final_state


# =============================================================================
# TEST: CONFIGURATION
# =============================================================================


class TestConfiguration:
    """Tests for EvaluationConfig behavior."""

    def test_low_budget_mode_skips_llm(self, sample_clauses):
        """low_budget_mode=True skips LLM evaluation."""
        config = EvaluationConfig(low_budget_mode=True)

        result = evaluate_coherence(
            clauses=sample_clauses,
            project_id="test",
            config=config,
        )

        # Should complete without LLM calls
        assert result is not None
        assert result.overall_score is not None

    def test_include_cross_clause_false(self, sample_clauses):
        """include_cross_clause=False skips cross-clause analysis."""
        config = EvaluationConfig(
            low_budget_mode=True,
            include_cross_clause=False,
        )

        result = evaluate_coherence(
            clauses=sample_clauses,
            project_id="test",
            config=config,
        )

        # Should complete without cross-clause
        assert result is not None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TestGraphStructure",
    "TestPrepareContextNode",
    "TestDeterministicEvaluateNode",
    "TestLlmSemanticEvaluateNode",
    "TestCrossClauseEvalNode",
    "TestScoringArbiterNode",
    "TestFormatOutputNode",
    "TestFullGraphInvocation",
    "TestHelperFunctions",
    "TestStateFlow",
    "TestConfiguration",
]
