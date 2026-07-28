"""TS-SEC-PII-NER-002 (SEC-002).

Hardens the PII gate in src.core.privacy.anonymizer with Presidio NER
recognizers for PERSON/LOCATION/PHONE_NUMBER. Two test tiers:

1. Logic tests (always run, mock the analyzer): dynamic availability,
   lazy-load-once caching, graceful degradation on any Presidio failure,
   deterministic [TYPE_NNN] tokenization + rehydration.
2. Real-engine tests (skipped when the Spanish spaCy model isn't installed
   in this environment): prove genuine end-to-end PERSON + LOCATION
   detection, including through AnthropicWrapper's GATE 8 before the LLM
   transport receives the request.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

anonymizer_module = importlib.import_module("src.core.privacy.anonymizer")


def _reset_singleton(monkeypatch: pytest.MonkeyPatch, *, presidio_available: bool) -> None:
    monkeypatch.setattr(anonymizer_module, "PRESIDIO_AVAILABLE", presidio_available)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_instance", None)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_initialized", False)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_analyzer", None)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_analyzer_load_failed", False)


def _recognizer_result(entity_type: str, start: int, end: int, score: float = 0.85):
    from presidio_analyzer import RecognizerResult

    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


def _presidio_actually_available() -> bool:
    """True only if presidio + the Spanish spaCy model both load for real."""
    if not anonymizer_module.PRESIDIO_AVAILABLE:
        return False
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "es", "model_name": "es_core_news_md"}],
            }
        )
        AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["es"])
        return True
    except Exception:
        return False


_REAL_MODEL_AVAILABLE = _presidio_actually_available()
requires_real_presidio = pytest.mark.skipif(
    not _REAL_MODEL_AVAILABLE,
    reason="es_core_news_md spaCy model not installed in this environment",
)


# ---------------------------------------------------------------------------
# Tier 1: logic tests (mocked analyzer, always run)
# ---------------------------------------------------------------------------


class TestPresidioAvailabilityIsDynamic:
    def test_presidio_available_matches_real_import_state(self) -> None:
        """PRESIDIO_AVAILABLE must reflect whether presidio_analyzer actually imports,
        not a hardcoded constant (the SEC-002 bug)."""
        try:
            import presidio_analyzer  # noqa: F401

            expected = True
        except ImportError:
            expected = False
        assert anonymizer_module.PRESIDIO_AVAILABLE is expected

    def test_presidio_unavailable_uses_regex_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_singleton(monkeypatch, presidio_available=False)
        anonymizer = anonymizer_module.PiiAnonymizerService()

        result = anonymizer.anonymize_document("Contacto: Juan Perez, Madrid, juan@empresa.com")

        assert "<EMAIL_ADDRESS_1>" in result.anonymized_text
        assert "Juan Perez" in result.anonymized_text  # not caught without Presidio
        assert "Madrid" in result.anonymized_text


class TestAnalyzerLazyLoadedOnce:
    def test_analyzer_constructed_once_across_multiple_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)

        construction_calls = []

        class _FakeAnalyzer:
            def analyze(self, **kwargs):
                return []

        def _fake_provider(**kwargs):
            return SimpleNamespace(create_engine=lambda: object())

        def _fake_analyzer_engine(**kwargs):
            construction_calls.append(1)
            return _FakeAnalyzer()

        monkeypatch.setattr(anonymizer_module, "_NlpEngineProvider", _fake_provider)
        monkeypatch.setattr(anonymizer_module, "_AnalyzerEngine", _fake_analyzer_engine)

        anonymizer = anonymizer_module.PiiAnonymizerService()
        anonymizer.anonymize_document("first call")
        anonymizer.anonymize_document("second call")
        anonymizer.anonymize_document("third call")

        assert len(construction_calls) == 1

    def test_analyzer_construction_failure_falls_back_to_regex_and_does_not_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)

        attempt_count = []

        def _failing_provider(**kwargs):
            attempt_count.append(1)
            raise OSError("model not found: es_core_news_md")

        monkeypatch.setattr(anonymizer_module, "_NlpEngineProvider", _failing_provider)

        anonymizer = anonymizer_module.PiiAnonymizerService()

        result1 = anonymizer.anonymize_document("Juan Perez, juan@empresa.com")
        result2 = anonymizer.anonymize_document("Ana Garcia, ana@empresa.com")

        # Never raises; regex layer still protects email in both calls.
        assert "<EMAIL_ADDRESS_1>" in result1.anonymized_text
        assert "<EMAIL_ADDRESS_1>" in result2.anonymized_text
        # Load is attempted once, then cached as failed (no retry storm).
        assert len(attempt_count) == 1


class TestPresidioAnalysisFailureDegradesGracefully:
    def test_analyze_call_exception_falls_back_to_regex(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)

        class _RaisingAnalyzer:
            def analyze(self, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            anonymizer_module.PiiAnonymizerService,
            "_get_analyzer",
            classmethod(lambda cls: _RaisingAnalyzer()),
        )

        anonymizer = anonymizer_module.PiiAnonymizerService()
        result = anonymizer.anonymize_document("Juan Perez, juan@empresa.com")

        assert "<EMAIL_ADDRESS_1>" in result.anonymized_text
        assert "Juan Perez" in result.anonymized_text  # degraded, not crashed


class TestDeterministicTokenScheme:
    def test_person_and_location_use_bracketed_zero_padded_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        text = "Juan Perez vive en Madrid."

        class _FakeAnalyzer:
            def analyze(self, **kwargs):
                return [
                    _recognizer_result("PERSON", 0, 10),  # "Juan Perez"
                    _recognizer_result("LOCATION", 19, 25),  # "Madrid"
                ]

        monkeypatch.setattr(
            anonymizer_module.PiiAnonymizerService,
            "_get_analyzer",
            classmethod(lambda cls: _FakeAnalyzer()),
        )

        anonymizer = anonymizer_module.PiiAnonymizerService()
        result = anonymizer.anonymize_document(text)

        assert "[PERSON_001]" in result.anonymized_text
        assert "[LOCATION_001]" in result.anonymized_text
        assert result.mapping["[PERSON_001]"] == "Juan Perez"
        assert result.mapping["[LOCATION_001]"] == "Madrid"

    def test_repeated_entity_reuses_same_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        text = "Juan Perez firma. Juan Perez aprueba."
        first = text.index("Juan Perez")
        second = text.index("Juan Perez", first + 1)

        class _FakeAnalyzer:
            def analyze(self, **kwargs):
                return [
                    _recognizer_result("PERSON", first, first + len("Juan Perez")),
                    _recognizer_result("PERSON", second, second + len("Juan Perez")),
                ]

        monkeypatch.setattr(
            anonymizer_module.PiiAnonymizerService,
            "_get_analyzer",
            classmethod(lambda cls: _FakeAnalyzer()),
        )

        anonymizer = anonymizer_module.PiiAnonymizerService()
        result = anonymizer.anonymize_document(text)

        assert result.anonymized_text == "[PERSON_001] firma. [PERSON_001] aprueba."
        assert result.mapping == {"[PERSON_001]": "Juan Perez"}

    def test_distinct_entities_get_incrementing_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        text = "Juan Perez y Ana Garcia firman."

        class _FakeAnalyzer:
            def analyze(self, **kwargs):
                return [
                    _recognizer_result("PERSON", 0, 10),  # "Juan Perez"
                    _recognizer_result("PERSON", 13, 23),  # "Ana Garcia"
                ]

        monkeypatch.setattr(
            anonymizer_module.PiiAnonymizerService,
            "_get_analyzer",
            classmethod(lambda cls: _FakeAnalyzer()),
        )

        anonymizer = anonymizer_module.PiiAnonymizerService()
        result = anonymizer.anonymize_document(text)

        assert "[PERSON_001]" in result.anonymized_text
        assert "[PERSON_002]" in result.anonymized_text
        assert result.mapping["[PERSON_001]"] == "Juan Perez"
        assert result.mapping["[PERSON_002]"] == "Ana Garcia"

    def test_rehydration_restores_presidio_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        mapping = {"[PERSON_001]": "Juan Perez", "[LOCATION_001]": "Madrid"}
        text = "El responsable es [PERSON_001], con sede en [LOCATION_001]."

        restored = anonymizer_module.deanonymize_text_simple(text, mapping)

        assert restored == "El responsable es Juan Perez, con sede en Madrid."

    def test_email_already_tokenized_by_regex_is_not_reprocessed_by_presidio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regex runs first; Presidio only ever sees the post-regex text, so it
        cannot mistake an already-anonymized <EMAIL_ADDRESS_1> token for a new
        entity."""
        _reset_singleton(monkeypatch, presidio_available=True)

        seen_texts = []

        class _RecordingAnalyzer:
            def analyze(self, *, text, **kwargs):
                seen_texts.append(text)
                return []

        monkeypatch.setattr(
            anonymizer_module.PiiAnonymizerService,
            "_get_analyzer",
            classmethod(lambda cls: _RecordingAnalyzer()),
        )

        anonymizer = anonymizer_module.PiiAnonymizerService()
        anonymizer.anonymize_document("Contact juan@empresa.com now")

        assert len(seen_texts) == 1
        assert "juan@empresa.com" not in seen_texts[0]
        assert "<EMAIL_ADDRESS_1>" in seen_texts[0]


# ---------------------------------------------------------------------------
# Tier 2: real Presidio + spaCy engine (skipped if the model isn't installed)
# ---------------------------------------------------------------------------


@requires_real_presidio
class TestRealPresidioEndToEnd:
    def test_person_name_and_physical_address_both_tokenized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        anonymizer = anonymizer_module.PiiAnonymizerService()

        clause = (
            "El contrato es firmado por Juan Perez, con domicilio en "
            "Calle Mayor 10, Madrid, como representante del Cliente."
        )
        result = anonymizer.anonymize_document(clause)

        assert "Juan Perez" not in result.anonymized_text
        assert "Calle Mayor 10" not in result.anonymized_text
        assert "Madrid" not in result.anonymized_text
        assert any(k.startswith("[PERSON_") for k in result.mapping)
        assert any(k.startswith("[LOCATION_") for k in result.mapping)

        # Rehydration round-trips.
        restored = anonymizer_module.deanonymize_text_simple(
            result.anonymized_text, result.mapping
        )
        assert restored == clause

    def test_phone_number_tokenized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_singleton(monkeypatch, presidio_available=True)
        anonymizer = anonymizer_module.PiiAnonymizerService()

        result = anonymizer.anonymize_document("Contactar al telefono +34 600 123 456.")

        assert "+34 600 123 456" not in result.anonymized_text
        assert any(k.startswith("[PHONE_NUMBER_") for k in result.mapping)

    def test_organization_and_money_are_not_anonymized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guard against over-anonymization corrupting evaluations: only
        PERSON/LOCATION/PHONE_NUMBER are in scope — organizations, money, and
        dates (needed for coherence/budget analysis) must survive untouched."""
        _reset_singleton(monkeypatch, presidio_available=True)
        anonymizer = anonymizer_module.PiiAnonymizerService()

        clause = (
            "Constructora Iberica S.A. presupuesta 500.000 euros para el "
            "Anexo I, con plazo de 180 dias."
        )
        result = anonymizer.anonymize_document(clause)

        assert result.anonymized_text == clause
        assert result.mapping == {}


@requires_real_presidio
class TestRealPresidioThroughAnthropicWrapper:
    @pytest.mark.asyncio
    async def test_person_and_address_tokenized_before_llm_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SEC-002 acceptance test: a clause with a person name + physical
        address must have both tokenized before the wrapper's LLM call."""
        _reset_singleton(monkeypatch, presidio_available=True)

        from src.core.ai.anthropic_wrapper import AnthropicWrapper
        from src.core.ai.llm_client import LLMResponse
        from src.core.ai.model_router import ModelTier

        wrapper = object.__new__(AnthropicWrapper)
        wrapper.total_requests = 0
        wrapper.cache_hits = 0
        wrapper.cache_misses = 0
        wrapper.total_cost_usd = 0.0
        wrapper.max_tokens_limit = None
        wrapper.cache_service = None
        wrapper.anonymizer_service = anonymizer_module.PiiAnonymizerService()

        model = SimpleNamespace(name="claude-haiku-test", tier=ModelTier.FLASH)
        wrapper.model_router = MagicMock()
        wrapper.model_router.select_model_with_budget_mode.return_value = model
        wrapper.model_router.estimate_cost.return_value = 0.0
        wrapper.llm_client = MagicMock()
        wrapper.llm_client.generate = AsyncMock(
            return_value=LLMResponse(
                content="ok",
                model="claude-haiku-test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.0,
                request_id="test-request",
                execution_time_ms=1.0,
                retries=0,
            )
        )

        from src.coherence.extraction import clause_extractor

        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
        monkeypatch.setattr(clause_extractor, "get_anthropic_wrapper", lambda: wrapper)

        clause = (
            "Firmado por Juan Perez, con domicilio en Calle Mayor 10, Madrid."
        )
        # _call_llm swallows the (non-JSON) "ok" response internally and
        # returns {} — we only care what was transmitted to the LLM.
        await clause_extractor._call_llm(clause)

        wrapper.llm_client.generate.assert_awaited_once()
        sent_request = wrapper.llm_client.generate.await_args.args[0]
        sent_content = sent_request.messages[0]["content"]

        assert "Juan Perez" not in sent_content
        assert "Calle Mayor 10" not in sent_content
        assert "Madrid" not in sent_content
