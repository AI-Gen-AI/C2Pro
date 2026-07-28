"""Test Suite ID: TS-SEC-PII-FALLBACK-001, TS-SEC-PII-NER-002.

Compatibility privacy anonymizer used by ``AnthropicWrapper`` (GATE 8) to
strip PII from prompts before they reach the LLM transport, and to rehydrate
tokens back to their original values in the LLM's response.

Two detection layers:

1. **Regex fallback** (``_EMAIL_RE`` / ``_SPANISH_ID_RE``) — always runs,
   deterministic, zero startup cost. Tokens: ``<EMAIL_ADDRESS_N>`` /
   ``<SPANISH_ID_N>`` (unchanged from the pre-SEC-002 contract — pinned by
   ``tests/unit/core/test_privacy_anonymizer_fallback.py``).
2. **Presidio NER** (SEC-002) — best-effort, only active when
   ``PRESIDIO_AVAILABLE`` and the Spanish spaCy model load successfully.
   Adds PERSON / LOCATION / PHONE_NUMBER detection that regex cannot catch
   (names, addresses, non-Spanish phone formats). Tokens:
   ``[PERSON_001]`` / ``[LOCATION_001]`` / ``[PHONE_NUMBER_001]`` —
   zero-padded, per-entity-type counters, same value always maps to the
   same token (deterministic + rehydratable).

Presidio runs on the text *after* the regex pass, on the intermediate,
already-tokenized text — this avoids Presidio re-flagging an already-
anonymized email/DNI token as a false-positive LOCATION/PERSON.

Any Presidio failure (missing package, missing NLP model, analyzer error)
degrades to regex-only for that call and is logged — it never raises past
this module and never causes PII to pass through unredacted. The regex
layer is therefore a hard floor, not just a default.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)

try:
    from presidio_analyzer import AnalyzerEngine as _AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider as _NlpEngineProvider

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

# Spanish is the only spaCy model this deployment provisions today (see
# apps/api/install_spacy_model.py). English-document NER coverage is a known
# gap tracked separately — regex EMAIL/SPANISH_ID detection is language-
# agnostic and still applies to English documents.
_PRESIDIO_LANGUAGE = "es"
_PRESIDIO_MODEL = "es_core_news_md"
_PRESIDIO_ENTITIES = ("PERSON", "LOCATION", "PHONE_NUMBER")
# Empirically measured against Presidio's default recognizers: PERSON/LOCATION
# NER hits score ~0.85; the built-in PhoneRecognizer scores international/
# Spanish mobile formats at ~0.4 without corroborating context keywords.
# 0.35 catches phone numbers without introducing false positives on a
# realistic contract clause sample (organizations, dates, money, addresses,
# clause references were all correctly left untouched in manual verification).
_PRESIDIO_SCORE_THRESHOLD = 0.35


@dataclass(frozen=True)
class AnonymizedResult:
    """Anonymized text plus token-to-original mapping."""

    anonymized_text: str
    mapping: dict[str, str]


class PiiAnonymizerService:
    """Small singleton-compatible anonymizer used by legacy privacy imports."""

    _instance: PiiAnonymizerService | None = None
    _initialized = False

    _EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _SPANISH_ID_RE = re.compile(r"\b\d{8}[A-Za-z]\b")

    # Lazy-loaded once per process (class-level, shared by all instances via
    # the singleton) — the spaCy NLP model is ~100-500MB and takes seconds to
    # load; loading it per-call or per-instance would be a severe latency and
    # memory regression.
    _analyzer: AnalyzerEngine | None = None
    _analyzer_load_failed = False
    _analyzer_lock = threading.Lock()

    def __new__(cls) -> PiiAnonymizerService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def anonymize_document(self, text: str) -> AnonymizedResult:
        """Replace supported PII with stable placeholder tokens."""
        mapping: dict[str, str] = {}
        anonymized = text

        for index, match in enumerate(self._EMAIL_RE.findall(text), start=1):
            token = f"<EMAIL_ADDRESS_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)

        for index, match in enumerate(self._SPANISH_ID_RE.findall(text), start=1):
            token = f"<SPANISH_ID_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)

        anonymized = self._apply_presidio(anonymized, mapping)

        return AnonymizedResult(anonymized_text=anonymized, mapping=mapping)

    def _apply_presidio(self, text: str, mapping: dict[str, str]) -> str:
        """Best-effort PERSON/LOCATION/PHONE_NUMBER pass. Never raises."""
        analyzer = self._get_analyzer()
        if analyzer is None:
            return text

        try:
            results = analyzer.analyze(
                text=text,
                language=_PRESIDIO_LANGUAGE,
                entities=list(_PRESIDIO_ENTITIES),
                score_threshold=_PRESIDIO_SCORE_THRESHOLD,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning("presidio_analysis_failed_fallback_to_regex", exc_info=exc)
            return text

        if not results:
            return text

        counters: dict[str, int] = {}
        token_by_value: dict[tuple[str, str], str] = {}
        replacements: list[tuple[int, int, str]] = []

        for result in sorted(results, key=lambda r: r.start):
            value = text[result.start : result.end]
            key = (result.entity_type, value)
            token = token_by_value.get(key)
            if token is None:
                counters[result.entity_type] = counters.get(result.entity_type, 0) + 1
                token = f"[{result.entity_type}_{counters[result.entity_type]:03d}]"
                token_by_value[key] = token
                mapping[token] = value
            replacements.append((result.start, result.end, token))

        # Apply right-to-left so earlier offsets stay valid.
        for start, end, token in sorted(replacements, key=lambda r: r[0], reverse=True):
            text = text[:start] + token + text[end:]
        return text

    @classmethod
    def _get_analyzer(cls) -> AnalyzerEngine | None:
        """Lazily construct the Presidio AnalyzerEngine exactly once."""
        if not PRESIDIO_AVAILABLE or cls._analyzer_load_failed:
            return None
        if cls._analyzer is not None:
            return cls._analyzer

        with cls._analyzer_lock:
            if cls._analyzer is not None or cls._analyzer_load_failed:
                return cls._analyzer
            try:
                provider = _NlpEngineProvider(
                    nlp_configuration={
                        "nlp_engine_name": "spacy",
                        "models": [
                            {"lang_code": _PRESIDIO_LANGUAGE, "model_name": _PRESIDIO_MODEL}
                        ],
                    }
                )
                nlp_engine = provider.create_engine()
                cls._analyzer = _AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    supported_languages=[_PRESIDIO_LANGUAGE],
                )
            except Exception as exc:  # pragma: no cover - defensive runtime fallback
                logger.warning(
                    "presidio_nlp_model_unavailable_fallback_to_regex", exc_info=exc
                )
                cls._analyzer_load_failed = True
                cls._analyzer = None
        return cls._analyzer


def get_anonymizer() -> PiiAnonymizerService:
    """Return the privacy anonymizer service."""
    return PiiAnonymizerService()


def anonymize_text_simple(text: str) -> str:
    """Anonymize text and return only the anonymized payload."""
    return get_anonymizer().anonymize_document(text).anonymized_text


def deanonymize_text_simple(text: str, mapping: dict[str, str] | None = None) -> str:
    """Restore placeholders using a caller-provided mapping."""
    restored = text
    for token, original in (mapping or {}).items():
        restored = restored.replace(token, original)
    return restored
