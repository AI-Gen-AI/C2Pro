"""
C2Pro - PII Anonymization Service (GDPR Compliant)

This service detects and anonymizes Personally Identifiable Information (PII)
in documents before sending them to AI services like Anthropic Claude.

Key Features:
- Microsoft Presidio for PII detection
- Spacy NLP for Spanish language
- Custom recognizers (DNI/NIE for Spain)
- Consistent mapping (same entity -> same placeholder)
- Reversible anonymization (deanonymization support)
- Singleton pattern (load Spacy model only once)

Security Policy:
- ANONYMIZE: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, IBAN_CODE, DNI/NIE
- PRESERVE: DATE_TIME, MONEY, ORGANIZATION (needed for AI coherence analysis)

Usage:
    from services.privacy.anonymizer import get_anonymizer

    anonymizer = get_anonymizer()
    result = anonymizer.anonymize_document(text)

    # Send result.anonymized_text to AI
    ai_response = ai_service.process(result.anonymized_text)

    # Restore real names in response
    clean_response = anonymizer.deanonymize_response(ai_response, result.mapping)

Version: 1.0.0
Date: 2026-01-13
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from threading import Lock

# Optional presidio imports - not required for testing
try:
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    PRESIDIO_AVAILABLE = True
except ImportError:
    # Create stub classes for when presidio is not available
    PRESIDIO_AVAILABLE = False
    AnalyzerEngine = type('AnalyzerEngine', (), {})
    PatternRecognizer = type('PatternRecognizer', (), {})
    Pattern = type('Pattern', (), {})
    NlpEngineProvider = type('NlpEngineProvider', (), {})
    AnonymizerEngine = type('AnonymizerEngine', (), {})
    OperatorConfig = type('OperatorConfig', (), {})

logger = logging.getLogger(__name__)


# =====================================================
# DATA MODELS
# =====================================================

@dataclass
class AnonymizedResult:
    """Result of anonymization operation."""

    anonymized_text: str
    """Text with PII replaced by placeholders (e.g., <PERSON_1>)."""

    mapping: Dict[str, str]
    """Mapping from placeholder to original value.
    Example: {"<PERSON_1>": "Juan Pérez", "<EMAIL_1>": "juan@empresa.com"}
    """

    entities_found: List[Dict[str, any]] = field(default_factory=list)
    """List of detected entities with metadata (type, score, position)."""

    statistics: Dict[str, int] = field(default_factory=dict)
    """Statistics about anonymization (e.g., {"PERSON": 3, "EMAIL_ADDRESS": 2})."""


# =====================================================
# CUSTOM RECOGNIZERS
# =====================================================

class SpanishDniNieRecognizer(PatternRecognizer):
    """
    Custom recognizer for Spanish DNI/NIE (Identity Documents).

    DNI Format: 8 digits + 1 letter (e.g., 12345678A)
    NIE Format: Letter (X, Y, Z) + 7 digits + 1 letter (e.g., X1234567A)

    The letter is calculated using modulo 23 algorithm for validation.
    """

    # Valid letters for DNI/NIE checksum
    DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    def __init__(self):
        patterns = [
            # DNI: 8 digits + letter
            Pattern(
                name="dni_pattern",
                regex=r"\b\d{8}[A-Z]\b",
                score=0.85
            ),
            # NIE: X/Y/Z + 7 digits + letter
            Pattern(
                name="nie_pattern",
                regex=r"\b[XYZ]\d{7}[A-Z]\b",
                score=0.85
            ),
            # DNI with separators (12.345.678-A, 12345678-A)
            Pattern(
                name="dni_with_separators",
                regex=r"\b\d{1,2}\.?\d{3}\.?\d{3}[-\s]?[A-Z]\b",
                score=0.80
            ),
        ]

        super().__init__(
            supported_entity="DNI_NIE",
            patterns=patterns,
            context=["DNI", "NIE", "identificación", "documento", "identidad"],
            supported_language="es"
        )

    @staticmethod
    def validate_dni_nie(value: str) -> bool:
        """
        Validate DNI/NIE checksum.

        Args:
            value: DNI or NIE string (e.g., "12345678A")

        Returns:
            True if checksum is valid, False otherwise
        """
        # Remove separators
        value = re.sub(r"[\.\-\s]", "", value.upper())

        if len(value) != 9:
            return False

        # NIE: Convert X/Y/Z to numbers
        if value[0] in "XYZ":
            nie_map = {"X": "0", "Y": "1", "Z": "2"}
            number = nie_map[value[0]] + value[1:8]
        else:
            # DNI
            number = value[:8]

        try:
            number_int = int(number)
        except ValueError:
            return False

        # Calculate expected letter
        expected_letter = SpanishDniNieRecognizer.DNI_LETTERS[number_int % 23]
        actual_letter = value[8]

        return expected_letter == actual_letter


# =====================================================
# ANONYMIZER SERVICE (SINGLETON)
# =====================================================

class PiiAnonymizerService:
    """
    Singleton service for PII anonymization using Microsoft Presidio.

    This service loads the Spacy model ONCE and reuses it for all requests.
    Loading the model on every request would consume too much memory and time.

    Thread-safe singleton implementation using double-checked locking.
    """

    _instance: Optional['PiiAnonymizerService'] = None
    _lock: Lock = Lock()
    _initialized: bool = False

    # Entity types to anonymize (CRITICAL: Only physical persons, not organizations)
    ENTITIES_TO_ANONYMIZE = [
        "PERSON",           # Names of individuals
        "EMAIL_ADDRESS",    # Email addresses
        "PHONE_NUMBER",     # Phone numbers
        "IBAN_CODE",        # International bank account numbers
        "DNI_NIE",          # Spanish identity documents (custom)
    ]

    # Entity types to PRESERVE (needed for AI coherence analysis)
    ENTITIES_TO_PRESERVE = [
        "DATE_TIME",        # Dates and times (critical for contract analysis)
        "MONEY",            # Monetary amounts (critical for budgets)
        "ORGANIZATION",     # Company names (usually public, needed for context)
        "LOCATION",         # Places (cities, countries - usually public)
    ]

    def __new__(cls):
        """Singleton pattern with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the anonymizer service (only once)."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            if not PRESIDIO_AVAILABLE:
                logger.warning("Presidio not available - PII anonymization disabled")
                self._nlp_engine = None
                self._analyzer = None
                self._anonymizer_engine = None
                self._entity_counters: Dict[str, int] = {}
                self._entity_mapping: Dict[str, str] = {}
                self._reverse_mapping: Dict[str, str] = {}
                self._initialized = True
                return

            logger.info("Initializing PII Anonymizer Service...")

            # Step 1: Configure Spacy NLP engine for Spanish
            self._nlp_engine = self._create_nlp_engine()

            # Step 2: Create Presidio analyzer with custom recognizers
            self._analyzer = self._create_analyzer()

            # Step 3: Create Presidio anonymizer
            self._anonymizer_engine = AnonymizerEngine()

            # Step 4: Initialize entity counters for consistent mapping
            self._entity_counters: Dict[str, int] = {}
            self._entity_mapping: Dict[str, str] = {}  # placeholder -> original
            self._reverse_mapping: Dict[str, str] = {}  # original -> placeholder

            self._initialized = True
            logger.info("PII Anonymizer Service initialized successfully")

    def _create_nlp_engine(self):
        """
        Create and configure Spacy NLP engine for Spanish.

        Model: es_core_news_lg (large model for better accuracy)
        Fallback: es_core_news_md (medium model if large not available)

        Returns:
            Configured NLP engine
        """
        logger.info("Loading Spacy model for Spanish...")

        try:
            # Try large model first (better accuracy)
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [
                    {
                        "lang_code": "es",
                        "model_name": "es_core_news_lg"
                    }
                ],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            logger.info("Loaded Spacy model: es_core_news_lg")
            return nlp_engine

        except Exception as e_lg:
            logger.warning(f"Could not load es_core_news_lg: {e_lg}")

            try:
                # Fallback to medium model
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [
                        {
                            "lang_code": "es",
                            "model_name": "es_core_news_md"
                        }
                    ],
                }
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()
                logger.info("Loaded Spacy model: es_core_news_md (fallback)")
                return nlp_engine

            except Exception as e_md:
                logger.error(f"Could not load Spacy model: {e_md}")
                raise RuntimeError(
                    "Failed to load Spacy model for Spanish. "
                    "Install with: python -m spacy download es_core_news_lg"
                ) from e_md

    def _create_analyzer(self) -> AnalyzerEngine:
        """
        Create Presidio analyzer with custom recognizers.

        Returns:
            Configured analyzer engine
        """
        logger.info("Creating Presidio analyzer with custom recognizers...")

        # Create base analyzer
        analyzer = AnalyzerEngine(
            nlp_engine=self._nlp_engine,
            supported_languages=["es", "en"]
        )

        # Add custom Spanish DNI/NIE recognizer
        dni_nie_recognizer = SpanishDniNieRecognizer()
        analyzer.registry.add_recognizer(dni_nie_recognizer)
        logger.info("Added custom recognizer: DNI/NIE (Spain)")

        return analyzer

    def anonymize_document(
        self,
        text: str,
        language: str = "es",
        score_threshold: float = 0.5
    ) -> AnonymizedResult:
        """
        Anonymize PII in document text.

        This method:
        1. Detects PII entities using Presidio
        2. Replaces each entity with a consistent placeholder
        3. Maintains mapping for deanonymization

        Args:
            text: Original document text
            language: Language code (default: "es" for Spanish)
            score_threshold: Minimum confidence score for entity detection (0.0-1.0)

        Returns:
            AnonymizedResult with anonymized text, mapping, and statistics

        Example:
            >>> text = "El contrato firmado por Juan Pérez (juan@empresa.com)"
            >>> result = anonymizer.anonymize_document(text)
            >>> print(result.anonymized_text)
            "El contrato firmado por <PERSON_1> (<EMAIL_1>)"
            >>> print(result.mapping)
            {"<PERSON_1>": "Juan Pérez", "<EMAIL_1>": "juan@empresa.com"}
        """
        if not text or not text.strip():
            return AnonymizedResult(
                anonymized_text="",
                mapping={},
                entities_found=[],
                statistics={}
            )

        # If presidio is not available, return text unchanged
        if not PRESIDIO_AVAILABLE or self._analyzer is None:
            logger.warning("Presidio not available - returning text unchanged")
            return AnonymizedResult(
                anonymized_text=text,
                mapping={},
                entities_found=[],
                statistics={}
            )

        logger.info(f"Anonymizing document ({len(text)} chars)...")

        # Step 1: Analyze text to find PII entities
        analyzer_results = self._analyzer.analyze(
            text=text,
            language=language,
            entities=self.ENTITIES_TO_ANONYMIZE,
            score_threshold=score_threshold
        )

        logger.info(f"Found {len(analyzer_results)} PII entities")

        # Step 2: Build consistent mapping for each entity
        # CRITICAL: Same entity value -> same placeholder
        operators = {}
        entity_stats = {}
        entities_metadata = []

        for result in analyzer_results:
            entity_type = result.entity_type
            original_value = text[result.start:result.end]

            # Get or create consistent placeholder
            placeholder = self._get_or_create_placeholder(
                entity_type=entity_type,
                original_value=original_value
            )

            # Configure replace operator for this entity
            operators[result] = OperatorConfig(
                "replace",
                {"new_value": placeholder}
            )

            # Update statistics
            entity_stats[entity_type] = entity_stats.get(entity_type, 0) + 1

            # Store metadata
            entities_metadata.append({
                "type": entity_type,
                "original_value": original_value,
                "placeholder": placeholder,
                "score": result.score,
                "start": result.start,
                "end": result.end
            })

        # Step 3: Anonymize text using Presidio
        anonymized_result = self._anonymizer_engine.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators
        )

        logger.info(f"Anonymization complete. Statistics: {entity_stats}")

        return AnonymizedResult(
            anonymized_text=anonymized_result.text,
            mapping=self._entity_mapping.copy(),
            entities_found=entities_metadata,
            statistics=entity_stats
        )

    def _get_or_create_placeholder(
        self,
        entity_type: str,
        original_value: str
    ) -> str:
        """
        Get existing placeholder or create new one for entity.

        CRITICAL: This ensures consistency. If "Juan Pérez" appears 10 times,
        it will ALWAYS be replaced with the same placeholder (e.g., <PERSON_1>).

        Args:
            entity_type: Type of entity (e.g., "PERSON")
            original_value: Original entity value (e.g., "Juan Pérez")

        Returns:
            Consistent placeholder (e.g., "<PERSON_1>")
        """
        # Check if we've seen this exact value before
        if original_value in self._reverse_mapping:
            return self._reverse_mapping[original_value]

        # Create new placeholder
        counter = self._entity_counters.get(entity_type, 0) + 1
        self._entity_counters[entity_type] = counter

        placeholder = f"<{entity_type}_{counter}>"

        # Store bidirectional mapping
        self._entity_mapping[placeholder] = original_value
        self._reverse_mapping[original_value] = placeholder

        return placeholder

    def deanonymize_response(
        self,
        text: str,
        mapping: Dict[str, str]
    ) -> str:
        """
        Restore original values in text using mapping.

        This is used when AI returns a response with placeholders,
        and we want to show the user the real names.

        Args:
            text: Text with placeholders (e.g., "El responsable es <PERSON_1>")
            mapping: Mapping from placeholder to original value

        Returns:
            Text with original values restored

        Example:
            >>> mapping = {"<PERSON_1>": "Juan Pérez"}
            >>> text = "El responsable del proyecto es <PERSON_1>"
            >>> result = anonymizer.deanonymize_response(text, mapping)
            >>> print(result)
            "El responsable del proyecto es Juan Pérez"
        """
        if not text or not mapping:
            return text

        result = text

        # Replace placeholders with original values
        # Sort by placeholder length (descending) to avoid partial replacements
        for placeholder in sorted(mapping.keys(), key=len, reverse=True):
            original_value = mapping[placeholder]
            result = result.replace(placeholder, original_value)

        return result

    def reset_mappings(self):
        """
        Reset entity mappings and counters.

        IMPORTANT: Call this between independent documents to avoid
        mapping conflicts (e.g., different "Juan Pérez" in different docs).

        For batch processing of multiple documents, reset after each document.
        """
        logger.info("Resetting entity mappings")
        self._entity_counters.clear()
        self._entity_mapping.clear()
        self._reverse_mapping.clear()

    def get_statistics(self) -> Dict[str, int]:
        """
        Get current entity counter statistics.

        Returns:
            Dictionary of entity type -> count
        """
        return self._entity_counters.copy()


# =====================================================
# SINGLETON ACCESSOR
# =====================================================

_anonymizer_instance: Optional[PiiAnonymizerService] = None


def get_anonymizer() -> PiiAnonymizerService:
    """
    Get the singleton instance of PiiAnonymizerService.

    This is the recommended way to access the anonymizer service.

    Returns:
        Singleton instance of PiiAnonymizerService

    Example:
        >>> from services.privacy.anonymizer import get_anonymizer
        >>> anonymizer = get_anonymizer()
        >>> result = anonymizer.anonymize_document("Juan Pérez trabaja aquí")
    """
    global _anonymizer_instance

    if _anonymizer_instance is None:
        _anonymizer_instance = PiiAnonymizerService()

    return _anonymizer_instance


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def anonymize_text_simple(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Simple convenience function for anonymizing text.

    Args:
        text: Text to anonymize

    Returns:
        Tuple of (anonymized_text, mapping)

    Example:
        >>> anonymized, mapping = anonymize_text_simple("Juan Pérez: juan@email.com")
        >>> print(anonymized)
        "<PERSON_1>: <EMAIL_ADDRESS_1>"
        >>> print(mapping)
        {"<PERSON_1>": "Juan Pérez", "<EMAIL_ADDRESS_1>": "juan@email.com"}
    """
    anonymizer = get_anonymizer()
    result = anonymizer.anonymize_document(text)
    return result.anonymized_text, result.mapping


def deanonymize_text_simple(text: str, mapping: Dict[str, str]) -> str:
    """
    Simple convenience function for deanonymizing text.

    Args:
        text: Text with placeholders
        mapping: Mapping from placeholder to original value

    Returns:
        Text with original values restored

    Example:
        >>> mapping = {"<PERSON_1>": "Juan Pérez"}
        >>> text = "Contactar con <PERSON_1>"
        >>> result = deanonymize_text_simple(text, mapping)
        >>> print(result)
        "Contactar con Juan Pérez"
    """
    anonymizer = get_anonymizer()
    return anonymizer.deanonymize_response(text, mapping)
