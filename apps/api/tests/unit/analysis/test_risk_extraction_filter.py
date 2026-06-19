"""Unit tests for the risk_extraction filter — multilingual + tunable.

Refers to Suite ID: TS-UA-ANA-GRAPH-001.

Diagnosis behind these tests (scripts/diagnose_chunks.py):

* On English EPC contracts the previous Spanish-only filter matched zero
  paragraphs and fell through to "use all paragraphs", then truncated to
  15000 chars — dropping ~37% of even modestly-sized docs and silently
  starving the extractor of LEGAL clauses.
* Fix: include keywords cover EN + ES; truncation cap raised to 40000
  by default and made env-configurable via ``RISK_EXTRACTION_MAX_CHARS``.
"""
from __future__ import annotations

import pytest

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    _EXCLUDE_KEYWORDS,
    _INCLUDE_KEYWORDS,
    _INCLUDE_KEYWORDS_EN,
    _INCLUDE_KEYWORDS_ES,
    RiskExtractionTool,
    _resolve_max_chars,
)

# ---------------------------------------------------------------------------
# Sample text fixtures
# ---------------------------------------------------------------------------


_EPC_EN_PARAGRAPHS = [
    "CONTRACT AGREEMENT BETWEEN HARYANA VIDYUT PRASARAN NIGAM LIMITED",
    (
        "any default or breach under the 'Second Contract' shall automatically be "
        "deemed as a default or breach of this 'First Contract' also and vice-versa "
        "and any such breach or occurrence or default giving the Employer a right "
        "to terminate the 'Second Contract' either in full or in part, and/or "
        "recover damages there under that Contract"
    ),
    (
        "The Effective Date from which the Time for Completion of the Facilities "
        "shall be counted is the date when all of the following conditions have "
        "been fulfilled"
    ),
    "Manufacturer's / suppliers warranty certificate.",
    "Bill of Materials — Schedule No. 1: Plant and Equipment Supplied from Abroad",
    "Page 12 of 87",
]


_EPC_ES_PARAGRAPHS = [
    "Memoria tecnica del proyecto: subestaciones 220KV",
    (
        "El contratista respondera por garantia y multa de hasta el 10% del "
        "valor del contrato en caso de incumplimiento de los plazos pactados."
    ),
    "Cronograma de obra y ruta critica",
    "Tabla de precios unitarios para suministro",
    "Subtotal Schedule No. 2",
]


@pytest.fixture
def tool() -> RiskExtractionTool:
    return RiskExtractionTool()


# ---------------------------------------------------------------------------
# Keyword coverage
# ---------------------------------------------------------------------------


class TestKeywordRegistry:
    def test_includes_contain_english_legal_terms(self) -> None:
        assert "default" in _INCLUDE_KEYWORDS_EN
        assert "breach" in _INCLUDE_KEYWORDS_EN
        assert "terminate" in _INCLUDE_KEYWORDS_EN
        assert "liability" in _INCLUDE_KEYWORDS_EN
        assert "warranty" in _INCLUDE_KEYWORDS_EN
        assert "force majeure" in _INCLUDE_KEYWORDS_EN

    def test_includes_contain_english_schedule_terms(self) -> None:
        assert "delay" in _INCLUDE_KEYWORDS_EN
        assert "completion" in _INCLUDE_KEYWORDS_EN
        assert "milestone" in _INCLUDE_KEYWORDS_EN
        assert "schedule" in _INCLUDE_KEYWORDS_EN

    def test_spanish_keywords_preserved(self) -> None:
        assert "garantia" in _INCLUDE_KEYWORDS_ES
        assert "cronograma" in _INCLUDE_KEYWORDS_ES
        assert "alcance" in _INCLUDE_KEYWORDS_ES

    def test_combined_includes_dedup_friendly(self) -> None:
        # Both languages are merged; "schedule" appears once in EN, never in ES.
        combined = _INCLUDE_KEYWORDS
        assert combined.count("schedule") == 1
        assert combined.count("garantia") == 1

    def test_exclude_keywords_cover_price_tables(self) -> None:
        assert "tabla de precios" in _EXCLUDE_KEYWORDS
        assert "price schedule" in _EXCLUDE_KEYWORDS
        assert "bill of materials" in _EXCLUDE_KEYWORDS
        assert "bom" in _EXCLUDE_KEYWORDS


# ---------------------------------------------------------------------------
# Filter behavior — English documents
# ---------------------------------------------------------------------------


class TestExtractInputAppliesFilter:
    """Critical regression guard: the filter must run in
    ``extract_input_from_state`` so the LLM receives the filtered text.

    Historically the filter ran inside ``_execute_impl`` (post-LLM) on a
    local copy that was discarded — the LLM always saw the unfiltered
    document. This test ensures that mistake cannot return silently.
    """

    def test_filter_runs_before_llm(self, tool: RiskExtractionTool) -> None:
        en_text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        state = {"document_text": en_text}
        input_data = tool.extract_input_from_state(state)  # type: ignore[arg-type]

        # BOM paragraph must have been stripped — confirms filter actually ran.
        assert "Bill of Materials" not in input_data.document_text
        # LEGAL paragraph must survive.
        assert "default or breach" in input_data.document_text

    def test_augmentation_suffixes_appended_after_filter(
        self, tool: RiskExtractionTool
    ) -> None:
        en_text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        state = {
            "document_text": en_text,
            "critique_notes": "previous critique feedback",
            "human_feedback": "human guidance",
        }
        input_data = tool.extract_input_from_state(state)  # type: ignore[arg-type]

        # Suffixes are never stripped even though they don't match any filter keyword.
        assert "CRITIQUE: previous critique feedback" in input_data.document_text
        assert "FEEDBACK: human guidance" in input_data.document_text

    def test_filter_emits_input_prepared_log(
        self, tool: RiskExtractionTool, caplog: pytest.LogCaptureFixture
    ) -> None:
        en_text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        with caplog.at_level("INFO"):
            tool.extract_input_from_state({"document_text": en_text})  # type: ignore[arg-type]
        events = [
            r for r in caplog.records if r.message == "risk_extraction_input_prepared"
        ]
        assert len(events) == 1


class TestFilterEnglish:
    """English EPC contracts must surface LEGAL/SCHEDULE clauses."""

    def test_english_legal_clause_kept(self, tool: RiskExtractionTool) -> None:
        text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        out = tool._filter_relevant_text(text)
        assert "default or breach" in out
        assert "Effective Date" in out
        assert "warranty certificate" in out

    def test_english_bom_paragraph_excluded(self, tool: RiskExtractionTool) -> None:
        text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        out = tool._filter_relevant_text(text)
        # Excluded by "bill of materials"
        assert "Bill of Materials" not in out

    def test_english_filter_does_not_fall_through(
        self, tool: RiskExtractionTool, caplog: pytest.LogCaptureFixture
    ) -> None:
        text = "\n\n".join(_EPC_EN_PARAGRAPHS)
        with caplog.at_level("INFO"):
            tool._filter_relevant_text(text)
        # Fall-through is the bug we're fixing — must NOT fire for English contracts.
        assert not any(
            r.message == "risk_extraction_filter_fellthrough" for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Filter behavior — Spanish documents (regression guard)
# ---------------------------------------------------------------------------


class TestFilterSpanish:
    def test_spanish_legal_clause_kept(self, tool: RiskExtractionTool) -> None:
        text = "\n\n".join(_EPC_ES_PARAGRAPHS)
        out = tool._filter_relevant_text(text)
        assert "garantia y multa" in out
        assert "ruta critica" in out

    def test_spanish_price_table_excluded(
        self, tool: RiskExtractionTool
    ) -> None:
        text = "\n\n".join(_EPC_ES_PARAGRAPHS)
        out = tool._filter_relevant_text(text)
        assert "Tabla de precios" not in out


# ---------------------------------------------------------------------------
# Fall-through path — observable, not silent
# ---------------------------------------------------------------------------


class TestFilterFallthroughObservability:
    def test_fallthrough_emits_structured_log(
        self, tool: RiskExtractionTool, caplog: pytest.LogCaptureFixture
    ) -> None:
        text = "\n\nIrrelevant boilerplate paragraph one.\n\nIrrelevant boilerplate paragraph two.\n\n"
        with caplog.at_level("INFO"):
            tool._filter_relevant_text(text)
        events = [r for r in caplog.records if r.message == "risk_extraction_filter_fellthrough"]
        assert len(events) == 1

    def test_fallthrough_still_returns_text(
        self, tool: RiskExtractionTool
    ) -> None:
        text = "boilerplate alpha\n\nboilerplate bravo"
        out = tool._filter_relevant_text(text)
        assert "boilerplate alpha" in out
        assert "boilerplate bravo" in out


# ---------------------------------------------------------------------------
# Truncation cap — configurable via env
# ---------------------------------------------------------------------------


class TestMaxCharsResolution:
    def test_default_is_40000(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RISK_EXTRACTION_MAX_CHARS", raising=False)
        assert _resolve_max_chars() == 40_000

    def test_env_var_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_EXTRACTION_MAX_CHARS", "25000")
        assert _resolve_max_chars() == 25_000

    def test_env_var_clamped_to_floor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_EXTRACTION_MAX_CHARS", "100")
        assert _resolve_max_chars() == 5_000

    def test_env_var_clamped_to_ceiling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RISK_EXTRACTION_MAX_CHARS", "999999")
        assert _resolve_max_chars() == 200_000

    def test_invalid_env_var_falls_back(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("RISK_EXTRACTION_MAX_CHARS", "not-a-number")
        with caplog.at_level("WARNING"):
            value = _resolve_max_chars()
        assert value == 40_000
        assert any(
            r.message == "risk_extraction_max_chars_invalid" for r in caplog.records
        )


class TestTruncationBehavior:
    """The new default 40k cap should keep modest contracts intact."""

    def test_24k_contract_not_truncated_at_default(
        self,
        tool: RiskExtractionTool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("RISK_EXTRACTION_MAX_CHARS", raising=False)
        # Build a 24k-char doc full of English LEGAL keywords so the include
        # filter does NOT fall through. Each paragraph is ~250 chars.
        body = (
            "any default or breach by the Contractor under this First Contract "
            "shall give the Employer an absolute right to terminate this Contract "
            "at the Contractor's risk, cost and responsibility. Liquidated damages "
            "shall apply per the schedule below. "
        )
        paragraphs = [body + f" Paragraph {i}." for i in range(80)]
        text = "\n\n".join(paragraphs)
        assert 20_000 < len(text) < 30_000
        out = tool._filter_relevant_text(text)
        # No truncation should have occurred at the 40k default.
        assert len(out) >= len(text) - 10  # allow tiny join overhead

    def test_env_var_can_cap_smaller(
        self,
        tool: RiskExtractionTool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("RISK_EXTRACTION_MAX_CHARS", "5000")
        body = "default breach terminate liability " * 50  # ~1750 chars
        paragraphs = [body + f" Paragraph {i}." for i in range(10)]
        text = "\n\n".join(paragraphs)
        out = tool._filter_relevant_text(text)
        assert len(out) <= 5_000


# ---------------------------------------------------------------------------
# Smoke: real EPC fragment (live diagnostic data)
# ---------------------------------------------------------------------------


class TestRealEPCFragment:
    """Smoke test on the exact fragment from the live diagnostic run.

    Mirrors the contract content the user is uploading. With the fix,
    the LEGAL clause must survive the filter (the bug was that it didn't
    because the filter discarded everything and then truncated arbitrarily).
    """

    LEGAL_FRAGMENT = (
        "It is expressly understood and agreed by the Contractor that any default "
        "or breach under the 'Second Contract' shall automatically be deemed as a "
        "default or breach of this 'First Contract' also and vice-versa and any "
        "such breach or occurrence or default giving the Employer a right to "
        "terminate the 'Second Contract' either in full or in part, and/or recover "
        "damages there under that Contract, shall give the Employer an absolute "
        "right to terminate this Contract at the Contractor's risk, cost and "
        "responsibility."
    )

    def test_cross_contamination_clause_kept(
        self, tool: RiskExtractionTool
    ) -> None:
        text = (
            "Header boilerplate paragraph that does not match.\n\n"
            f"{self.LEGAL_FRAGMENT}\n\n"
            "Footer page reference."
        )
        out = tool._filter_relevant_text(text)
        assert "default or breach" in out
        assert "terminate this Contract" in out
