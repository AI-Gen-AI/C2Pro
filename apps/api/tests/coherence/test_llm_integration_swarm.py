"""
C2Pro - CoherenceLLMService Unit Tests (Swarm)

Tests for the key logic in src/coherence/llm_integration.py:

- _calculate_risk_level: all 5 severity-based branching paths (empty, critical,
  high>=2, high>=1 or medium>=3, else low)
- _parse_json_response: plain valid JSON, markdown-fenced JSON (```json and ```),
  and JSONDecodeError fallback
- analyze_multi_clause_coherence: early-return for <2 clauses, full LLM path with
  wrapper.generate call
- analyze_project_context: analyze_individual=False path, analyze_cross_clause=False
  path, and both-True path
- Singleton: get_coherence_llm_service / reset_coherence_llm_service

The AnthropicWrapper is NEVER instantiated for real — every test injects a
MagicMock() as the `wrapper` argument so get_anthropic_wrapper() is never invoked
and no environment variables are required.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal domain-object factories (no real model imports needed)
# ---------------------------------------------------------------------------


def _make_ai_response(
    content: str | dict,
    *,
    total_tokens: int = 100,
    cost_usd: float = 0.001,
    cached: bool = False,
    model_used: str = "claude-sonnet",
) -> SimpleNamespace:
    """Return a lightweight AIResponse-compatible SimpleNamespace."""
    if isinstance(content, dict):
        content = json.dumps(content)
    return SimpleNamespace(
        content=content,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        cached=cached,
        model_used=model_used,
    )


def _make_clause(text: str = "Some clause text.", data: dict | None = None) -> SimpleNamespace:
    """Return a minimal Clause-compatible object with a fresh UUID id."""
    return SimpleNamespace(id=str(uuid.uuid4()), text=text, data=data)


def _make_project_context(clauses: list) -> SimpleNamespace:
    """Return a minimal ProjectContext-compatible object with a fresh UUID id."""
    return SimpleNamespace(id=str(uuid.uuid4()), clauses=clauses)


def _make_service(wrapper: MagicMock | None = None):
    """Instantiate CoherenceLLMService with an injected MagicMock wrapper."""
    from src.coherence.llm_integration import CoherenceLLMService  # type: ignore[import]

    if wrapper is None:
        wrapper = MagicMock()
    return CoherenceLLMService(wrapper=wrapper)


# ===========================================================================
# TestCalculateRiskLevel
# ===========================================================================


class TestCalculateRiskLevel:
    """Unit tests for CoherenceLLMService._calculate_risk_level."""

    @pytest.mark.red_phase
    def test_empty_findings_returns_low(self):
        """Branch 1: empty findings list → 'low'."""
        service = _make_service()
        assert service._calculate_risk_level([]) == "low"

    @pytest.mark.red_phase
    def test_one_critical_finding_returns_critical(self):
        """Branch 2: a single critical finding → 'critical'."""
        service = _make_service()
        assert service._calculate_risk_level([{"severity": "critical"}]) == "critical"

    @pytest.mark.red_phase
    def test_critical_dominates_over_multiple_high(self):
        """Branch 2: critical present alongside multiple highs → still 'critical'."""
        service = _make_service()
        findings = [
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "high"},
        ]
        assert service._calculate_risk_level(findings) == "critical"

    @pytest.mark.red_phase
    def test_two_high_findings_returns_high(self):
        """Branch 3: high >= 2, no critical → 'high'."""
        service = _make_service()
        findings = [{"severity": "high"}, {"severity": "high"}]
        assert service._calculate_risk_level(findings) == "high"

    @pytest.mark.red_phase
    def test_three_high_findings_returns_high(self):
        """Branch 3: high >= 2 still applies with three highs → 'high'."""
        service = _make_service()
        findings = [{"severity": "high"}, {"severity": "high"}, {"severity": "high"}]
        assert service._calculate_risk_level(findings) == "high"

    @pytest.mark.red_phase
    def test_one_high_finding_returns_medium(self):
        """Branch 4: high == 1 (< 2), no critical → 'medium'."""
        service = _make_service()
        assert service._calculate_risk_level([{"severity": "high"}]) == "medium"

    @pytest.mark.red_phase
    def test_three_medium_findings_returns_medium(self):
        """Branch 4: medium >= 3, zero high/critical → 'medium'."""
        service = _make_service()
        findings = [{"severity": "medium"}, {"severity": "medium"}, {"severity": "medium"}]
        assert service._calculate_risk_level(findings) == "medium"

    @pytest.mark.red_phase
    def test_one_high_and_three_medium_returns_medium(self):
        """Branch 4: high == 1 OR medium >= 3 satisfied simultaneously → 'medium'."""
        service = _make_service()
        findings = [
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "medium"},
        ]
        assert service._calculate_risk_level(findings) == "medium"

    @pytest.mark.red_phase
    def test_two_medium_no_high_returns_low(self):
        """Branch 5: medium == 2 (< 3), no high/critical → 'low'."""
        service = _make_service()
        findings = [{"severity": "medium"}, {"severity": "medium"}]
        assert service._calculate_risk_level(findings) == "low"

    @pytest.mark.red_phase
    def test_only_low_severity_findings_returns_low(self):
        """Branch 5: multiple low findings, nothing else → 'low'."""
        service = _make_service()
        findings = [{"severity": "low"}, {"severity": "low"}, {"severity": "low"}]
        assert service._calculate_risk_level(findings) == "low"

    @pytest.mark.red_phase
    def test_missing_severity_key_treated_as_low(self):
        """Findings without a 'severity' key default to 'low' via dict.get fallback."""
        service = _make_service()
        findings = [{"type": "gap"}]  # no severity key
        assert service._calculate_risk_level(findings) == "low"


# ===========================================================================
# TestParseJsonResponse
# ===========================================================================


class TestParseJsonResponse:
    """Unit tests for CoherenceLLMService._parse_json_response."""

    @pytest.mark.red_phase
    def test_valid_plain_json_is_parsed_and_returned(self):
        """Branch 1: valid, undecorated JSON string is parsed correctly."""
        service = _make_service()
        data = {"has_issues": True, "confidence": 0.9}
        result = service._parse_json_response(json.dumps(data))
        assert result == data

    @pytest.mark.red_phase
    def test_valid_json_with_surrounding_whitespace_is_parsed(self):
        """Branch 1: leading/trailing whitespace is stripped before parsing."""
        service = _make_service()
        data = {"score": 42}
        result = service._parse_json_response(f"  {json.dumps(data)}  \n")
        assert result == data

    @pytest.mark.red_phase
    def test_json_in_backtick_json_fence_is_stripped_and_parsed(self):
        """Branch 2: content wrapped in ```json ... ``` fences is unwrapped."""
        service = _make_service()
        inner = {"rule_violated": False, "severity": "low"}
        fenced = f"```json\n{json.dumps(inner)}\n```"
        result = service._parse_json_response(fenced)
        assert result == inner

    @pytest.mark.red_phase
    def test_json_in_plain_backtick_fence_is_stripped_and_parsed(self):
        """Branch 2: content in plain ``` ... ``` (no 'json' tag) is also unwrapped."""
        service = _make_service()
        inner = {"overall_coherence_score": 75}
        fenced = f"```\n{json.dumps(inner)}\n```"
        result = service._parse_json_response(fenced)
        assert result == inner

    @pytest.mark.red_phase
    def test_invalid_json_returns_dict_with_parse_error_key(self):
        """Branch 3: JSONDecodeError → result dict contains 'parse_error' key."""
        service = _make_service()
        result = service._parse_json_response("this is { not json")
        assert "parse_error" in result

    @pytest.mark.red_phase
    def test_invalid_json_returns_dict_with_raw_content_key(self):
        """Branch 3: JSONDecodeError → result dict contains 'raw_content' key."""
        service = _make_service()
        result = service._parse_json_response("bad content")
        assert "raw_content" in result

    @pytest.mark.red_phase
    def test_invalid_json_raw_content_equals_stripped_input(self):
        """Branch 3: raw_content in the error dict matches the stripped original string."""
        service = _make_service()
        raw = "  not valid json  "
        result = service._parse_json_response(raw)
        assert result["raw_content"] == raw.strip()

    @pytest.mark.red_phase
    def test_empty_string_triggers_parse_error_path(self):
        """Branch 3: empty string is not valid JSON → returns error dict."""
        service = _make_service()
        result = service._parse_json_response("")
        assert "parse_error" in result


# ===========================================================================
# TestAnalyzeMultiClauseCoherence
# ===========================================================================


class TestAnalyzeMultiClauseCoherence:
    """Unit tests for CoherenceLLMService.analyze_multi_clause_coherence."""

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_single_clause_returns_early_dict(self):
        """len(clauses) == 1 < 2 → early return without calling wrapper.generate."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        service = _make_service(wrapper)

        result = await service.analyze_multi_clause_coherence([_make_clause()])

        wrapper.generate.assert_not_called()
        assert result["overall_coherence_score"] == 100
        assert result["cross_clause_issues"] == []

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_empty_clauses_list_returns_early_dict(self):
        """len(clauses) == 0 < 2 → same early-return path as single clause."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        service = _make_service(wrapper)

        result = await service.analyze_multi_clause_coherence([])

        wrapper.generate.assert_not_called()
        assert result["overall_coherence_score"] == 100

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_early_return_dict_contains_summary_key(self):
        """Early-return dict includes the 'summary' key."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        service = _make_service(wrapper)

        result = await service.analyze_multi_clause_coherence([_make_clause()])
        assert "summary" in result

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_two_clauses_calls_wrapper_generate_exactly_once(self):
        """len(clauses) >= 2 → wrapper.generate is called exactly once."""
        llm_payload = {"cross_clause_issues": [], "overall_coherence_score": 95, "summary": "OK"}
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=_make_ai_response(llm_payload))
        service = _make_service(wrapper)

        await service.analyze_multi_clause_coherence([_make_clause("A"), _make_clause("B")])

        wrapper.generate.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_two_clauses_result_reflects_llm_payload(self):
        """Result dict carries the values from the parsed LLM JSON payload."""
        llm_payload = {
            "cross_clause_issues": [
                {
                    "type": "inconsistency",
                    "severity": "high",
                    "affected_clauses": ["c1", "c2"],
                    "description": "Date conflict.",
                    "evidence": "Clause 1 references March; Clause 2 references April.",
                }
            ],
            "overall_coherence_score": 60,
            "summary": "One inconsistency found.",
        }
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=_make_ai_response(llm_payload))
        service = _make_service(wrapper)

        result = await service.analyze_multi_clause_coherence(
            [_make_clause("A"), _make_clause("B")]
        )

        assert result["overall_coherence_score"] == 60
        assert len(result["cross_clause_issues"]) == 1
        assert result["cross_clause_issues"][0]["severity"] == "high"

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_result_includes_clauses_analyzed_list(self):
        """Returned dict contains 'clauses_analyzed' with every clause id."""
        llm_payload = {"cross_clause_issues": [], "overall_coherence_score": 80, "summary": ""}
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=_make_ai_response(llm_payload))
        service = _make_service(wrapper)

        c1 = _make_clause("Clause 1")
        c2 = _make_clause("Clause 2")
        result = await service.analyze_multi_clause_coherence([c1, c2])

        assert set(result["clauses_analyzed"]) == {c1.id, c2.id}

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_result_includes_model_used_from_response(self):
        """Returned dict carries 'model_used' taken from the AIResponse object."""
        llm_payload = {"cross_clause_issues": [], "overall_coherence_score": 70, "summary": ""}
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            return_value=_make_ai_response(llm_payload, model_used="claude-haiku-test")
        )
        service = _make_service(wrapper)

        result = await service.analyze_multi_clause_coherence(
            [_make_clause("A"), _make_clause("B")]
        )
        assert result["model_used"] == "claude-haiku-test"

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_total_tokens_accumulate_after_call(self):
        """service.total_tokens increases by the response's total_tokens value."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            return_value=_make_ai_response(
                {"cross_clause_issues": [], "overall_coherence_score": 90, "summary": ""},
                total_tokens=250,
            )
        )
        service = _make_service(wrapper)

        assert service.total_tokens == 0
        await service.analyze_multi_clause_coherence([_make_clause("A"), _make_clause("B")])
        assert service.total_tokens == 250


# ===========================================================================
# TestAnalyzeProjectContext
# ===========================================================================


class TestAnalyzeProjectContext:
    """Unit tests for CoherenceLLMService.analyze_project_context."""

    # ------------------------------------------------------------------
    # Private helpers for building mock responses
    # ------------------------------------------------------------------

    def _clause_analysis_response(self, has_issues: bool = False) -> SimpleNamespace:
        """Build a fake AIResponse for per-clause analysis."""
        payload: dict = {
            "has_issues": has_issues,
            "issues": (
                [
                    {
                        "type": "ambiguity",
                        "severity": "medium",
                        "description": "Vague term.",
                        "quote": "q",
                        "recommendation": "r",
                    }
                ]
                if has_issues
                else []
            ),
            "confidence": 0.9,
            "reasoning": "test reasoning",
        }
        return _make_ai_response(payload, total_tokens=100, cost_usd=0.001)

    def _cross_clause_response(self) -> SimpleNamespace:
        """Build a fake AIResponse for cross-clause analysis."""
        payload = {
            "cross_clause_issues": [],
            "overall_coherence_score": 90,
            "summary": "No cross-clause issues.",
        }
        return _make_ai_response(payload, total_tokens=150, cost_usd=0.002)

    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_individual_false_no_per_clause_api_call(self):
        """analyze_individual=False → wrapper.generate not called for individual clauses."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=self._cross_clause_response())
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A"), _make_clause("B")])
        await service.analyze_project_context(
            ctx, analyze_individual=False, analyze_cross_clause=True
        )

        # Only 1 call for cross-clause; none for individual
        assert wrapper.generate.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_individual_false_result_has_no_individual_findings(self):
        """analyze_individual=False → findings from individual analysis are absent."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=self._cross_clause_response())
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=False, analyze_cross_clause=False
        )

        assert result.findings == []

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_cross_clause_false_only_individual_calls_made(self):
        """analyze_cross_clause=False → wrapper.generate called once per clause only."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            side_effect=[
                self._clause_analysis_response(has_issues=False),
                self._clause_analysis_response(has_issues=False),
            ]
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A"), _make_clause("B")])
        await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=False
        )

        assert wrapper.generate.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_both_true_runs_individual_then_cross_clause(self):
        """Both flags True with 2 clauses → 2 individual calls + 1 cross-clause call."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            side_effect=[
                self._clause_analysis_response(has_issues=False),
                self._clause_analysis_response(has_issues=False),
                self._cross_clause_response(),
            ]
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A"), _make_clause("B")])
        await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=True
        )

        assert wrapper.generate.call_count == 3

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_result_project_id_matches_context_id(self):
        """CoherenceAnalysisResult.project_id reflects the input context id."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=self._clause_analysis_response())
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("One clause")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=False
        )

        assert result.project_id == ctx.id

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_total_clauses_analyzed_equals_context_clause_count(self):
        """total_clauses_analyzed == len(context.clauses)."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            side_effect=[self._clause_analysis_response() for _ in range(3)]
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause() for _ in range(3)])
        result = await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=False
        )

        assert result.total_clauses_analyzed == 3

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_clauses_with_issues_counted_accurately(self):
        """clauses_with_issues reflects only clauses whose analysis had issues."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            side_effect=[
                self._clause_analysis_response(has_issues=True),
                self._clause_analysis_response(has_issues=False),
                self._cross_clause_response(),
            ]
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A"), _make_clause("B")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=True
        )

        assert result.clauses_with_issues == 1

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_individual_findings_tagged_with_source(self):
        """Findings from per-clause analysis have source='individual_analysis'."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            return_value=self._clause_analysis_response(has_issues=True)
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("One clause")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=False
        )

        assert all(f["source"] == "individual_analysis" for f in result.findings)

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_risk_level_elevated_when_high_severity_issues_found(self):
        """High-severity findings in per-clause analysis drive risk_level above 'low'."""
        high_issue_payload = {
            "has_issues": True,
            "issues": [
                {
                    "type": "risk",
                    "severity": "high",
                    "description": "Risky clause.",
                    "quote": "Q",
                    "recommendation": "R",
                }
            ],
            "confidence": 0.85,
            "reasoning": "risky",
        }
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=_make_ai_response(high_issue_payload))
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("risky clause")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=False
        )

        assert result.risk_level in {"medium", "high", "critical"}

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_both_false_zero_api_calls_and_empty_findings(self):
        """Both flags False → no API calls, empty findings, risk_level='low'."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("A"), _make_clause("B")])
        result = await service.analyze_project_context(
            ctx, analyze_individual=False, analyze_cross_clause=False
        )

        wrapper.generate.assert_not_called()
        assert result.findings == []
        assert result.risk_level == "low"

    @pytest.mark.asyncio
    @pytest.mark.red_phase
    async def test_cross_clause_skipped_when_only_one_clause_even_if_flag_true(self):
        """Cross-clause analysis is skipped when len(clauses) < 2 even if flag is True."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(
            return_value=self._clause_analysis_response(has_issues=False)
        )
        service = _make_service(wrapper)

        ctx = _make_project_context([_make_clause("Single")])
        await service.analyze_project_context(
            ctx, analyze_individual=True, analyze_cross_clause=True
        )

        # Only 1 call: the individual clause; no cross-clause call
        assert wrapper.generate.call_count == 1


# ===========================================================================
# TestSingleton
# ===========================================================================


class TestSingleton:
    """Unit tests for get_coherence_llm_service / reset_coherence_llm_service."""

    @pytest.mark.red_phase
    def test_get_returns_coherence_llm_service_instance(self):
        """get_coherence_llm_service() returns a CoherenceLLMService object."""
        from src.coherence.llm_integration import (  # type: ignore[import]
            CoherenceLLMService,
            get_coherence_llm_service,
            reset_coherence_llm_service,
        )

        reset_coherence_llm_service()
        with patch(
            "src.coherence.llm_integration.get_anthropic_wrapper",
            return_value=MagicMock(),
        ):
            service = get_coherence_llm_service()

        assert isinstance(service, CoherenceLLMService)
        reset_coherence_llm_service()

    @pytest.mark.red_phase
    def test_get_returns_same_instance_on_repeated_calls(self):
        """Two consecutive calls return the identical singleton object."""
        from src.coherence.llm_integration import (  # type: ignore[import]
            get_coherence_llm_service,
            reset_coherence_llm_service,
        )

        reset_coherence_llm_service()
        with patch(
            "src.coherence.llm_integration.get_anthropic_wrapper",
            return_value=MagicMock(),
        ):
            svc1 = get_coherence_llm_service()
            svc2 = get_coherence_llm_service()

        assert svc1 is svc2
        reset_coherence_llm_service()

    @pytest.mark.red_phase
    def test_reset_forces_new_instance_on_next_call(self):
        """After reset, get_coherence_llm_service returns a fresh (different) instance."""
        from src.coherence.llm_integration import (  # type: ignore[import]
            get_coherence_llm_service,
            reset_coherence_llm_service,
        )

        with patch(
            "src.coherence.llm_integration.get_anthropic_wrapper",
            return_value=MagicMock(),
        ):
            reset_coherence_llm_service()
            svc1 = get_coherence_llm_service()
            reset_coherence_llm_service()
            svc2 = get_coherence_llm_service()

        assert svc1 is not svc2
        reset_coherence_llm_service()

    @pytest.mark.red_phase
    def test_reset_sets_module_level_service_to_none(self):
        """reset_coherence_llm_service sets the module-level _service variable to None."""
        import src.coherence.llm_integration as llm_mod  # type: ignore[import]
        from src.coherence.llm_integration import (
            reset_coherence_llm_service,  # type: ignore[import]
        )

        with patch(
            "src.coherence.llm_integration.get_anthropic_wrapper",
            return_value=MagicMock(),
        ):
            llm_mod.get_coherence_llm_service()  # populate singleton

        reset_coherence_llm_service()
        assert llm_mod._service is None
