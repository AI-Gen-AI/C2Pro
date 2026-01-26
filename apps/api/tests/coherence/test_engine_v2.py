"""
Tests for CoherenceEngineV2 (CE-26)

Tests the integrated engine that supports both deterministic and LLM-based rules.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.coherence.engine_v2 import (
    CoherenceEngineV2,
    EngineConfig,
    ExecutionMode,
    LLMResultCache,
    create_engine_v2,
)
from src.modules.coherence.models import Clause, ProjectContext
from src.modules.coherence.rules import Rule
from src.modules.coherence.rules_engine.base import Finding


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def sample_clauses():
    """Sample clauses for testing."""
    return [
        Clause(
            id="clause-budget-001",
            text="Current project spend is 250,000 against a planned budget of 200,000.",
            data={"planned": 200000, "current": 250000},
        ),
        Clause(
            id="clause-schedule-001",
            text="The project schedule is currently delayed due to supply chain issues.",
            data={"status": "delayed"},
        ),
        Clause(
            id="clause-scope-001",
            text="The contractor shall perform additional work as deemed necessary by the client.",
            data={},
        ),
    ]


@pytest.fixture
def sample_project(sample_clauses):
    """Sample project context for testing."""
    return ProjectContext(
        id="test-project-001",
        clauses=sample_clauses,
    )


@pytest.fixture
def deterministic_rules():
    """Rules that have deterministic evaluators."""
    return [
        Rule(id="project-budget-overrun-10", description="Budget overrun detection", severity="high"),
        Rule(id="project-schedule-delayed", description="Schedule delay detection", severity="medium"),
    ]


@pytest.fixture
def llm_rules():
    """Rules that require LLM evaluation."""
    return [
        Rule(id="R-SCOPE-CLARITY-01", description="Scope clarity check", severity="high"),
        Rule(id="R-PAYMENT-CLARITY-01", description="Payment terms clarity", severity="high"),
    ]


@pytest.fixture
def all_rules(deterministic_rules, llm_rules):
    """Combined rules list."""
    return deterministic_rules + llm_rules


@pytest.fixture
def default_config():
    """Default engine configuration."""
    return EngineConfig(
        execution_mode=ExecutionMode.DETERMINISTIC_FIRST,
        enable_llm_rules=False,  # Disable LLM for most tests
        enable_cache=False,
    )


# ===========================================
# ENGINE INITIALIZATION TESTS
# ===========================================


class TestEngineInitialization:
    """Tests for engine initialization."""

    def test_engine_creation_with_default_config(self, deterministic_rules):
        """Test engine creation with default configuration."""
        engine = CoherenceEngineV2(
            rules=deterministic_rules,
            config=EngineConfig(enable_llm_rules=False),
        )

        assert engine is not None
        assert len(engine._deterministic_rules) == 2
        assert len(engine._llm_rules) == 0

    def test_engine_creation_with_custom_config(self, deterministic_rules):
        """Test engine creation with custom configuration."""
        config = EngineConfig(
            execution_mode=ExecutionMode.PARALLEL,
            max_concurrent_llm_calls=10,
            enable_cache=True,
            cache_ttl_seconds=7200,
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=config)

        assert engine.config.execution_mode == ExecutionMode.PARALLEL
        assert engine.config.max_concurrent_llm_calls == 10
        assert engine.config.cache_ttl_seconds == 7200

    def test_engine_filters_disabled_rules(self, deterministic_rules):
        """Test that disabled rules are filtered out."""
        config = EngineConfig(
            disabled_rule_ids=["project-schedule-delayed"],
            enable_llm_rules=False,
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=config)

        assert len(engine._deterministic_rules) == 1
        assert engine._deterministic_rules[0].id == "project-budget-overrun-10"

    def test_engine_filters_enabled_rules_only(self, deterministic_rules):
        """Test that only enabled rules are included."""
        config = EngineConfig(
            enabled_rule_ids=["project-budget-overrun-10"],
            enable_llm_rules=False,
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=config)

        assert len(engine._deterministic_rules) == 1
        assert engine._deterministic_rules[0].id == "project-budget-overrun-10"


# ===========================================
# DETERMINISTIC EVALUATION TESTS
# ===========================================


class TestDeterministicEvaluation:
    """Tests for deterministic rule evaluation."""

    def test_evaluate_detects_budget_overrun(self, deterministic_rules, sample_project, default_config):
        """Test that budget overrun is detected."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        result = engine.evaluate(sample_project)

        # Should find budget overrun alert
        budget_alerts = [a for a in result.alerts if "budget" in a.rule_id.lower()]
        assert len(budget_alerts) >= 1

    def test_evaluate_detects_schedule_delay(self, deterministic_rules, sample_project, default_config):
        """Test that schedule delay is detected."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        result = engine.evaluate(sample_project)

        # Should find schedule delay alert
        schedule_alerts = [a for a in result.alerts if "schedule" in a.rule_id.lower()]
        assert len(schedule_alerts) >= 1

    def test_evaluate_returns_score(self, deterministic_rules, sample_project, default_config):
        """Test that evaluation returns a score."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        result = engine.evaluate(sample_project)

        assert result.score is not None
        assert 0 <= result.score <= 100

    def test_evaluate_clean_project(self, deterministic_rules, default_config):
        """Test evaluation of a clean project."""
        clean_project = ProjectContext(
            id="clean-project",
            clauses=[
                Clause(
                    id="clause-ok-001",
                    text="Project is on track.",
                    data={"planned": 100000, "current": 95000, "status": "on-track"},
                ),
            ],
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        result = engine.evaluate(clean_project)

        # Should have high score with no alerts
        assert result.score >= 80


# ===========================================
# ASYNC EVALUATION TESTS
# ===========================================


class TestAsyncEvaluation:
    """Tests for async evaluation with LLM rules."""

    @pytest.mark.asyncio
    async def test_evaluate_async_deterministic_only(self, deterministic_rules, sample_project, default_config):
        """Test async evaluation with deterministic rules only."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        result = await engine.evaluate_async(sample_project)

        assert result is not None
        assert len(result.alerts) > 0

    @pytest.mark.asyncio
    async def test_evaluate_async_parallel_mode(self, deterministic_rules, sample_project):
        """Test async evaluation in parallel mode."""
        config = EngineConfig(
            execution_mode=ExecutionMode.PARALLEL,
            enable_llm_rules=False,
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=config)
        result = await engine.evaluate_async(sample_project)

        assert result is not None

    @pytest.mark.asyncio
    async def test_evaluate_async_sequential_mode(self, deterministic_rules, sample_project):
        """Test async evaluation in sequential mode."""
        config = EngineConfig(
            execution_mode=ExecutionMode.SEQUENTIAL,
            enable_llm_rules=False,
        )

        engine = CoherenceEngineV2(rules=deterministic_rules, config=config)
        result = await engine.evaluate_async(sample_project)

        assert result is not None


# ===========================================
# CACHE TESTS
# ===========================================


class TestLLMResultCache:
    """Tests for LLM result caching."""

    @pytest.fixture
    def cache(self):
        """Create a cache instance."""
        return LLMResultCache(ttl_seconds=60)

    @pytest.fixture
    def sample_finding(self, sample_clauses):
        """Create a sample finding."""
        return Finding(
            triggered_clause=sample_clauses[0],
            raw_data={"rule_id": "test-rule", "severity": "high"},
        )

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache):
        """Test that cache miss returns None."""
        result = await cache.get("rule-1", "clause-1", "some text")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache, sample_finding):
        """Test setting and getting cached results."""
        await cache.set("rule-1", "clause-1", "some text", sample_finding)
        result = await cache.get("rule-1", "clause-1", "some text")

        assert result is not None
        assert result.triggered_clause.id == sample_finding.triggered_clause.id

    @pytest.mark.asyncio
    async def test_cache_key_uniqueness(self, cache, sample_finding):
        """Test that different inputs produce different cache entries."""
        await cache.set("rule-1", "clause-1", "text A", sample_finding)
        await cache.set("rule-1", "clause-1", "text B", None)

        result_a = await cache.get("rule-1", "clause-1", "text A")
        result_b = await cache.get("rule-1", "clause-1", "text B")

        assert result_a is not None
        # result_b should be None (cached as no finding)

    def test_cache_clear(self, cache):
        """Test cache clearing."""
        cache._memory_cache["test-key"] = (0, {"is_none": True})
        cache.clear()
        assert len(cache._memory_cache) == 0


# ===========================================
# STATISTICS TESTS
# ===========================================


class TestStatistics:
    """Tests for engine statistics."""

    def test_statistics_tracking(self, deterministic_rules, sample_project, default_config):
        """Test that statistics are tracked correctly."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)

        # Initial stats
        stats = engine.get_statistics()
        assert stats["evaluations"] == 0

        # After evaluation
        engine.evaluate(sample_project)
        stats = engine.get_statistics()

        assert stats["evaluations"] == 1
        assert stats["deterministic_findings"] > 0

    def test_statistics_reset(self, deterministic_rules, sample_project, default_config):
        """Test statistics reset."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)
        engine.evaluate(sample_project)

        engine.reset_statistics()
        stats = engine.get_statistics()

        assert stats["evaluations"] == 0
        assert stats["deterministic_findings"] == 0


# ===========================================
# FACTORY FUNCTION TESTS
# ===========================================


class TestFactoryFunction:
    """Tests for the create_engine_v2 factory function."""

    def test_create_engine_v2_default(self):
        """Test creating engine with default settings."""
        with patch.dict("os.environ", {"C2PRO_SKIP_RULE_AUTOLOAD": "1"}):
            engine = create_engine_v2(load_llm_rules=False)
            assert engine is not None

    def test_create_engine_v2_with_config(self):
        """Test creating engine with custom config."""
        config = EngineConfig(
            execution_mode=ExecutionMode.PARALLEL,
            enable_llm_rules=False,
        )

        with patch.dict("os.environ", {"C2PRO_SKIP_RULE_AUTOLOAD": "1"}):
            engine = create_engine_v2(config=config, load_llm_rules=False)
            assert engine.config.execution_mode == ExecutionMode.PARALLEL


# ===========================================
# EXECUTION MODE TESTS
# ===========================================


class TestExecutionModes:
    """Tests for different execution modes."""

    def test_execution_mode_enum(self):
        """Test ExecutionMode enum values."""
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.DETERMINISTIC_FIRST.value == "deterministic_first"

    def test_config_accepts_all_modes(self):
        """Test that EngineConfig accepts all execution modes."""
        for mode in ExecutionMode:
            config = EngineConfig(execution_mode=mode)
            assert config.execution_mode == mode


# ===========================================
# INTEGRATION TESTS (MOCKED LLM)
# ===========================================


class TestLLMIntegration:
    """Integration tests with mocked LLM evaluators."""

    @pytest.mark.asyncio
    async def test_llm_evaluation_with_mock(self, sample_clauses):
        """Test LLM evaluation with mocked evaluator."""
        # Create a mock LLM evaluator
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_async = AsyncMock(return_value=Finding(
            triggered_clause=sample_clauses[2],
            raw_data={
                "rule_id": "R-SCOPE-CLARITY-01",
                "severity": "high",
                "evidence": {"explanation": "Ambiguous scope detected"},
            },
        ))
        mock_evaluator.get_statistics = MagicMock(return_value={})

        # Create engine with mocked evaluator
        rules = [Rule(id="R-SCOPE-CLARITY-01", description="Test", severity="high")]
        config = EngineConfig(enable_llm_rules=True, enable_cache=False)

        engine = CoherenceEngineV2(rules=rules, config=config)
        engine._llm_rules = rules
        engine._llm_evaluators = {"R-SCOPE-CLARITY-01": mock_evaluator}

        project = ProjectContext(id="test", clauses=sample_clauses)
        result = await engine.evaluate_async(project)

        # Verify LLM was called
        assert mock_evaluator.evaluate_async.called

    @pytest.mark.asyncio
    async def test_llm_timeout_handling(self, sample_clauses):
        """Test that LLM timeouts are handled gracefully."""
        # Create a mock that times out
        async def slow_evaluate(clause):
            await asyncio.sleep(10)  # Will timeout
            return None

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_async = slow_evaluate
        mock_evaluator.get_statistics = MagicMock(return_value={})

        rules = [Rule(id="R-SCOPE-CLARITY-01", description="Test", severity="high")]
        config = EngineConfig(
            enable_llm_rules=True,
            enable_cache=False,
            llm_timeout_seconds=0.1,  # Very short timeout
        )

        engine = CoherenceEngineV2(rules=rules, config=config)
        engine._llm_rules = rules
        engine._llm_evaluators = {"R-SCOPE-CLARITY-01": mock_evaluator}

        project = ProjectContext(id="test", clauses=[sample_clauses[0]])
        result = await engine.evaluate_async(project)

        # Should complete without error, timeout should be logged
        assert result is not None
        assert engine._stats["llm_errors"] > 0


# ===========================================
# CLAIM GENERATION TESTS
# ===========================================


class TestClaimGeneration:
    """Tests for claim generation from findings."""

    def test_generate_claim_budget_overrun(self, deterministic_rules, default_config):
        """Test claim generation for budget overrun."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)

        rule = Rule(id="project-budget-overrun-10", description="Budget check", severity="high")
        finding = Finding(
            triggered_clause=Clause(id="c1", text="Budget text"),
            raw_data={"current": 250000, "planned": 200000, "overrun_percentage": 25.0},
        )

        claim = engine._generate_claim(rule, finding)
        assert "250000" in claim or "250,000" in claim
        assert "200000" in claim or "200,000" in claim

    def test_generate_claim_llm_evidence(self, deterministic_rules, default_config):
        """Test claim generation from LLM evidence."""
        engine = CoherenceEngineV2(rules=deterministic_rules, config=default_config)

        rule = Rule(id="R-SCOPE-CLARITY-01", description="Scope check", severity="high")
        finding = Finding(
            triggered_clause=Clause(id="c1", text="Some scope text"),
            raw_data={
                "evidence": {
                    "explanation": "The scope contains ambiguous terms like 'as needed'",
                    "quote": "as needed",
                },
            },
        )

        claim = engine._generate_claim(rule, finding)
        assert "ambiguous" in claim.lower()
