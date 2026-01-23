"""
C2Pro - PII Anonymizer Service (Presidio Implementation)

This module provides a robust service to detect and anonymize PII using
Microsoft Presidio and SpaCy, ensuring data privacy before processing by
external services like Large Language Models (LLMs).

It implements a Singleton pattern to ensure the heavy NLP models are loaded only once.
"""

import logging
import re
from typing import List, Dict, NamedTuple, Optional, Callable
from collections import defaultdict

# Presidio and Spacy imports
import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerResult, EntityRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine, OperatorResult
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.operators import Operator, OperatorType

from src.core.exceptions import SecurityException

# --- Custom Recognizer for Spanish DNI/NIE ---

class AnonymizedPayload(NamedTuple):
    """
    Defines the output structure for the anonymization service.
    
    - text: The anonymized text safe to send to third parties.
    - deanonymization_map: A dictionary to restore the original PII.
    """
    text: str
    deanonymization_map: Dict[str, str]


class EsNifRecognizer(EntityRecognizer):
    """
    Custom Presidio recognizer for Spanish DNI (Documento Nacional de Identidad)
    and NIE (Número de Identificación de Extranjero).

    This recognizer uses a combination of regex for pattern matching and a
    checksum validation for accuracy.
    """
    ENTITIES = ["ES_NIF"]
    # Regex to find potential DNI/NIE formats
    # Covers: 8N+L, X/Y/Z + 7N+L
    NIF_REGEX = re.compile(r"\b([XYZxyz]?\d{7,8}[A-Za-z])\b")
    CHECKSUM_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    def load(self) -> None:
        """No models to load for this recognizer."""
        pass

    def analyze(self, text: str, entities: List[str], nlp_artifacts) -> List[RecognizerResult]:
        results = []
        for match in self.NIF_REGEX.finditer(text):
            nif_value = match.group(0).upper()
            if self._is_valid_nif(nif_value):
                result = RecognizerResult(
                    entity_type="ES_NIF",
                    start=match.start(),
                    end=match.end(),
                    score=0.95  # High confidence due to checksum validation
                )
                results.append(result)
        return results

    def _is_valid_nif(self, nif: str) -> bool:
        """Validates a DNI or NIE using the checksum algorithm."""
        nif = nif.upper()
        if len(nif) != 9:
            return False
        
        letter = nif[-1]
        number_part = nif[:-1]

        if nif.startswith(('X', 'Y', 'Z')):
            # For NIE, replace leading letter with a number
            if nif.startswith('Y'):
                number_part = '1' + number_part[1:]
            elif nif.startswith('Z'):
                number_part = '2' + number_part[1:]
            else: # X
                number_part = '0' + number_part[1:]

        try:
            dni_number = int(number_part)
            return self.CHECKSUM_LETTERS[dni_number % 23] == letter
        except (ValueError, IndexError):
            return False

# --- Custom Anonymizer Operator ---

def create_custom_replace_operator() -> Callable:
    """
    Factory to create a stateful custom replace operator.
    This ensures consistent tokenization within a single `anonymize` call.
    """
    # State for a single anonymization call
    pii_map: Dict[str, str] = {} # Maps original PII value to its token
    counters: Dict[str, int] = defaultdict(int)

    def custom_replace(text: str, params: Dict[str, any]) -> str:
        entity_type = params.get("entity_type")
        
        # If we've seen this exact PII value before, return its token
        if text in pii_map:
            return pii_map[text]
        
        # If it's a new PII value, create a new token
        counters[entity_type] += 1
        new_token = f"<{entity_type}_{counters[entity_type]}>"
        pii_map[text] = new_token
        return new_token
        
    return custom_replace


class CustomReplaceOperator(Operator):
    """
    Custom Presidio operator using a stateful callable set per anonymize call.
    """

    _operator_logic: Optional[Callable[[str, Dict[str, any]], str]] = None

    @classmethod
    def set_operator_logic(cls, logic: Optional[Callable[[str, Dict[str, any]], str]]) -> None:
        cls._operator_logic = logic

    def operate(self, text: str, params: Dict = None) -> str:
        if not self._operator_logic:
            return text
        return self._operator_logic(text, params or {})

    def validate(self, params: Dict = None) -> None:
        return None

    def operator_name(self) -> str:
        return "custom_replace"

    def operator_type(self) -> OperatorType:
        return OperatorType.Anonymize


# --- Singleton PII Anonymizer Service ---

class PiiAnonymizerService:
    """
    A singleton service that loads Presidio and its NLP model only once.
    """
    _instance: Optional['PiiAnonymizerService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PiiAnonymizerService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """
        Initializes the Presidio Analyzer and Anonymizer engines.
        This is a heavy operation and should only be run once.
        """
        logging.info("Initializing PiiAnonymizerService singleton...")
        try:
            # 1. Create a Spacy NLP engine for Spanish
            nlp_config = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "es", "model_name": "es_core_news_md"}],
            }
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()
            
            # 2. Add our custom NIF recognizer to the registry
            nif_recognizer = EsNifRecognizer(supported_entities=["ES_NIF"])
            
            # 3. Create the AnalyzerEngine
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["es"],
                registry=None
            )
            self.analyzer.registry.add_recognizer(nif_recognizer)
            self.analyzer.registry.load_predefined_recognizers(
                languages=["es"],
                nlp_engine=nlp_engine,
            )

            # 4. Create the AnonymizerEngine and register our custom operator
            self.anonymizer = AnonymizerEngine()
            self.anonymizer.add_anonymizer(CustomReplaceOperator)
            
            logging.info("PiiAnonymizerService initialized successfully.")

        except OSError as e:
            logging.error(f"Failed to load NLP model for PiiAnonymizerService: {e}")
            raise SecurityException(
                message="PII anonymization model is not available. "
                        "Please install 'es_core_news_md' for spaCy.",
                component="PiiAnonymizerService"
            )
        except Exception as e:
            logging.error(f"A critical error occurred during PiiAnonymizerService initialization: {e}")
            raise SecurityException(
                message="A critical error occurred initializing the PII anonymizer.",
                component="PiiAnonymizerService"
            )

    def anonymize(self, text: str) -> AnonymizedPayload:
        """
        Analyzes and anonymizes PII in a given text with consistent, reversible tokens.
        """
        if not text:
            return AnonymizedPayload(text="", deanonymization_map={})

        try:
            analyzer_results = self.analyzer.analyze(
                text=text,
                entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE", "ES_NIF"],
                language="es"
            )

            # Create a new stateful operator for this specific call
            custom_operator_logic = create_custom_replace_operator()
            
            anonymizer_config = {
                "DEFAULT": OperatorConfig("custom_replace")
            }
            
            # Temporarily update the operator logic for this call
            CustomReplaceOperator.set_operator_logic(custom_operator_logic)

            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results,
                operators=anonymizer_config
            )

            # Build the deanonymization map from the tokens and original values
            deanonymization_map = {}
            for original_item, anonymized_item in zip(analyzer_results, anonymized_result.items):
                original_value = text[original_item.start:original_item.end]
                token = anonymized_item.text
                # The map should be token -> original_value
                if token not in deanonymization_map:
                    deanonymization_map[token] = original_value
            
            # Clean up operator logic reference
            CustomReplaceOperator.set_operator_logic(None)

            return AnonymizedPayload(
                text=anonymized_result.text,
                deanonymization_map=deanonymization_map
            )
        except Exception as e:
            logging.error(f"Anonymization process failed: {e}")
            raise SecurityException(
                message="An error occurred during the PII anonymization process.",
                component="PiiAnonymizerService"
            )

def get_pii_anonymizer_service() -> PiiAnonymizerService:
    """Returns the singleton instance of the PiiAnonymizerService."""
    return PiiAnonymizerService()
