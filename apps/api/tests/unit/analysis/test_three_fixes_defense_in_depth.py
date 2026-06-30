"""Defense-in-depth tests for the three coordinated fixes that unblock
the N4 → N8 → bridge path on contracts where the LLM extractor struggles.

Refers to Suite ID: TS-UA-ANA-GRAPH-001.

Three fixes:

1. English risk-extraction prompt + 8192 max_tokens default — Claude no
   longer produces Spanish prose that overruns 4096 output tokens.
2. Deterministic fallback emits multi-sentence ``source_quote`` excerpts
   (≥80 chars) — the critique no longer rejects them as untraceable.
3. ``C2PRO_SKIP_HITL`` env override routes the workflow past
   human_interrupt so N8 + N17 always run, even when extraction quality
   is low.
"""
from __future__ import annotations

import pytest

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.analysis.domain.ai_extraction import (
    DeterministicRiskRulesService,
    _source_sentence_for,
)
from src.config import settings

# ---------------------------------------------------------------------------
# Fix 1: prompt in English, max_tokens default 8192
# ---------------------------------------------------------------------------


class TestPromptEnglish:
    def test_system_prompt_is_english(self) -> None:
        tool = RiskExtractionTool()
        user, system = tool._build_default_prompt(
            RiskExtractionInput(document_text="any contract text"),
            is_retry=False,
        )
        assert system is not None
        # Hallmarks of the new English prompt
        assert "senior project risk analyst" in system
        assert "EPC" in system
        # Must NOT contain the old Spanish first line
        assert "analista senior" not in system

    def test_critical_output_rules_present(self) -> None:
        tool = RiskExtractionTool()
        _, system = tool._build_default_prompt(
            RiskExtractionInput(document_text="x"), is_retry=False
        )
        assert "CRITICAL OUTPUT RULES" in (system or "")
        assert '{"risks": [' in (system or "")
        # ≥80 char source_quote requirement is part of the prompt
        assert "80 char" in (system or "")

    def test_prompt_uses_canonical_six_categories_only(self) -> None:
        """TS-UA-ANA-GRAPH-001: N4 prompt must not ask Claude for legacy categories."""
        tool = RiskExtractionTool()
        _, system = tool._build_default_prompt(
            RiskExtractionInput(document_text="x"), is_retry=False
        )
        assert system is not None
        assert '"category": "LEGAL|SCHEDULE|QUALITY|SCOPE|TECHNICAL|BUDGET"' in system
        assert "FINANCIAL" not in system
        assert "HSE" not in system

    def test_retry_appendix_is_english(self) -> None:
        tool = RiskExtractionTool()
        user, _ = tool._build_default_prompt(
            RiskExtractionInput(document_text="contract body"), is_retry=True
        )
        assert "Respond with ONLY valid JSON" in user
        assert "Markdown" not in user.split("REMINDER")[0]  # no leftover Spanish


class TestMaxTokensDefaultRaised:
    def test_field_default_is_8192(self) -> None:
        # The standard tier in model_routing.yaml is 8192; the global
        # clamp used to be 4096, silently truncating Claude mid-JSON.
        # Verify the FIELD DEFAULT (env-independent) is now 8192.
        from src.config import Settings

        field = Settings.model_fields["ai_max_tokens_output"]
        assert field.default == 8192

    def test_env_value_is_at_least_8192(self) -> None:
        """The deployed .env must not silently clamp below the field default.

        We loaded the contract from .env and have to keep it in sync with
        the new default, otherwise the model_routing.yaml's 8192 gets
        truncated again at the wrapper boundary.
        """
        assert settings.ai_max_tokens_output >= 8192


# ---------------------------------------------------------------------------
# Fix 2: deterministic fallback emits multi-sentence quotes ≥80 chars
# ---------------------------------------------------------------------------


_REAL_CONTRACT_FRAGMENT = (
    "Article 1. Contract Documents (Reference GC Clause 2).\n\n"
    "The following documents shall constitute the Contract between the "
    "Employer and the Contractor, and each shall be read and construed "
    "as an integral part of the Contract: (a) This Contract Agreement "
    "and the Appendices hereto. (b) Letter of Bid and Price Schedules "
    "submitted by the Contractor. (c) Particular Conditions. "
    "(d) General Conditions. (e) Specification.\n\n"
    "Article 2. Payment. The Employer hereby agrees to pay to the "
    "Contractor the Contract Price in consideration of the performance "
    "by the Contractor of its obligations hereunder, within thirty (30) "
    "days of certified milestone completion.\n\n"
    "v) Manufacturer's / suppliers warranty certificate must be provided "
    "for every Plant and Equipment item, valid for a minimum of twelve "
    "months from Operational Acceptance.\n"
)


class TestSourceSentenceForContext:
    def test_returns_min_80_chars_even_when_match_is_short(self) -> None:
        text = "Page 1.\n\nPayment.\n\nThe Employer shall reimburse the Contractor within 30 days of certified milestone."
        quote = _source_sentence_for(text, ("payment", "pago"))
        assert len(quote) >= 80
        assert "payment" in quote.casefold() or "Employer" in quote

    def test_returns_neighbor_context(self) -> None:
        text = (
            "Article 7. Payment Schedule.\n\n"
            "Ten percent (10%) of the EXW amount as advance payment "
            "against an irrevocable bank guarantee.\n\n"
            "Seventy two and half percent (72.5%) upon CIP delivery.\n"
        )
        quote = _source_sentence_for(text, ("payment", "pago"))
        # Must include the neighboring schedule context, not just one word.
        assert len(quote) >= 80
        assert "Payment" in quote


class TestDeterministicFallbackQuality:
    def test_all_risks_have_source_quote_min_80_chars(self) -> None:
        service = DeterministicRiskRulesService()
        risks = service.extract(_REAL_CONTRACT_FRAGMENT)
        assert risks, "fixture should yield at least one risk"
        for r in risks:
            assert len(r["source_quote"]) >= 80, (
                f"risk {r['category']!r} has too-short source_quote: "
                f"{r['source_quote']!r}"
            )

    def test_risks_categorized_for_bridge(self) -> None:
        """The bridge's category map is the contract: the fallback must
        emit at least one risk in a category the bridge maps to a
        coherence category (LEGAL/SCHEDULE/QUALITY/etc.)."""
        service = DeterministicRiskRulesService()
        risks = service.extract(_REAL_CONTRACT_FRAGMENT)
        emitted_categories = {r["category"] for r in risks}
        # Payment / 30 days → BUDGET; warranty → QUALITY
        assert emitted_categories & {"BUDGET", "QUALITY", "SCHEDULE", "LEGAL", "TECHNICAL", "SCOPE"}

    def test_english_contract_default_breach_terms_emit_legal(self) -> None:
        """TS-UA-ANA-GRAPH-001: fallback LEGAL follows the category registry lexicon."""
        text = (
            "The Contractor acknowledges that any default or breach under the "
            "Second Contract shall automatically be deemed a default or breach "
            "under this First Contract. Such breach gives the Employer the "
            "right to terminate this Contract and recover costs from the "
            "Contractor, subject to the indemnification and liability provisions."
        )
        risks = DeterministicRiskRulesService().extract(text)
        legal = [risk for risk in risks if risk["category"] == "LEGAL"]
        assert legal
        assert len(legal[0]["source_quote"]) >= 80


# ---------------------------------------------------------------------------
# Fix 3: C2PRO_SKIP_HITL bypasses human_interrupt routing
# ---------------------------------------------------------------------------


class TestSkipHitlEnvVar:
    """The conditional edge must route past human_interrupt when
    ``C2PRO_SKIP_HITL=1`` so coherence_scorer + save_to_db actually run."""

    def test_skip_hitl_env_preserves_retry_routing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Lazy import to pick up the monkeypatched env at module level.
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        state = {
            "human_approval_required": True,
            "critique_notes": "low confidence",
            "retry_count": 1,
            "doc_type": "contract",
        }
        next_step = _next_after_critique_v2(state)  # type: ignore[arg-type]
        # skip_hitl bypasses only the human_interrupt pause; it must not
        # suppress automated retry routing when retry conditions are present.
        assert next_step == "risk_extractor"

    def test_default_still_routes_to_human_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        monkeypatch.delenv("C2PRO_SKIP_HITL", raising=False)
        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        state = {
            "human_approval_required": True,
            "critique_notes": "low confidence",
            "retry_count": 1,
            "doc_type": "contract",
        }
        next_step = _next_after_critique_v2(state)  # type: ignore[arg-type]
        assert next_step == "human_interrupt"

    def test_ai_mock_env_also_skips_hitl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        monkeypatch.delenv("C2PRO_SKIP_HITL", raising=False)
        monkeypatch.setenv("C2PRO_AI_MOCK", "1")

        state = {
            "human_approval_required": True,
            "critique_notes": "",
            "retry_count": 0,
            "doc_type": "contract",
        }
        next_step = _next_after_critique_v2(state)  # type: ignore[arg-type]
        assert next_step == "stakeholder_extractor"
