import datetime

import pytest
from pydantic import ValidationError

from src.coherence.category_registry import (
    CanonicalCategory,
    CategoryRegistry,
    load_category_registry,
)


def test_load_category_registry_success():
    """Verify that we can load and parse the live category_registry.yaml successfully."""
    registry = load_category_registry()
    assert isinstance(registry, CategoryRegistry)
    assert registry.version.registry_version == "1.0.0"
    assert registry.version.score_version == 7
    assert registry.version.embedding_model == "text-embedding-3-small"
    assert isinstance(registry.version.cutoff_date, datetime.date)
    assert registry.version.cutoff_date.isoformat() == "2026-06-01"

    # Check default weights
    assert abs(registry.defaults.weights.embedding - 0.60) < 1e-5
    assert abs(registry.defaults.weights.structural - 0.25) < 1e-5
    assert abs(registry.defaults.weights.lexicon - 0.15) < 1e-5

    # Check defaults thresholds
    assert registry.defaults.thresholds.escalate_low == 0.35
    assert registry.defaults.thresholds.escalate_high == 0.65
    assert registry.defaults.thresholds.insufficient_evidence == 0.20

    # Verify categories
    assert CanonicalCategory.LEGAL in registry.categories
    assert CanonicalCategory.SCOPE in registry.categories
    assert CanonicalCategory.BUDGET in registry.categories
    assert CanonicalCategory.SCHEDULE in registry.categories
    assert CanonicalCategory.TECHNICAL in registry.categories
    assert CanonicalCategory.QUALITY in registry.categories

    legal = registry.categories[CanonicalCategory.LEGAL]
    assert legal.enum == CanonicalCategory.LEGAL
    assert "es" in legal.prototypes
    assert "en" in legal.prototypes
    assert len(legal.prototypes["es"]) > 0
    assert len(legal.structural_signals.patterns) > 0

    # Verify doc type priors
    assert "contract" in registry.doc_type_priors
    assert registry.doc_type_priors["contract"][CanonicalCategory.LEGAL] == 0.70
    assert registry.doc_type_priors["contract"][CanonicalCategory.SCOPE] == 0.55


def test_missing_canonical_category():
    """Verify that CategoryRegistry raises ValidationError if any canonical category is missing."""
    registry_data = {
        "version": {
            "registry_version": "1.0.0",
            "score_version": 7,
            "embedding_model": "text-embedding-3-small",
            "cutoff_date": "2026-06-01",
            "languages": ["es", "en"],
        },
        "defaults": {
            "weights": {"embedding": 0.60, "structural": 0.25, "lexicon": 0.15},
            "thresholds": {
                "escalate_low": 0.35,
                "escalate_high": 0.65,
                "insufficient_evidence": 0.20,
            },
        },
        "categories": {
            # Missing LEGAL on purpose!
            "SCOPE": {
                "enum": "SCOPE",
                "prototypes": {"es": ["Alcance"], "en": ["Scope"]},
                "structural_signals": {
                    "section_titles": {"es": ["alcance"], "en": ["scope"]},
                    "patterns": [],
                },
                "lexicon": {"es": ["alcance"], "en": ["scope"]},
            },
            "BUDGET": {
                "enum": "BUDGET",
                "prototypes": {"es": ["Presupuesto"], "en": ["Budget"]},
                "structural_signals": {
                    "section_titles": {"es": ["presupuesto"], "en": ["budget"]},
                    "patterns": [],
                },
                "lexicon": {"es": ["presupuesto"], "en": ["budget"]},
            },
            "SCHEDULE": {
                "enum": "SCHEDULE",
                "prototypes": {"es": ["Cronograma"], "en": ["Schedule"]},
                "structural_signals": {
                    "section_titles": {"es": ["cronograma"], "en": ["schedule"]},
                    "patterns": [],
                },
                "lexicon": {"es": ["cronograma"], "en": ["schedule"]},
            },
            "TECHNICAL": {
                "enum": "TECHNICAL",
                "prototypes": {"es": ["Especificación"], "en": ["Specification"]},
                "structural_signals": {
                    "section_titles": {"es": ["especificación"], "en": ["specification"]},
                    "patterns": [],
                },
                "lexicon": {"es": ["especificación"], "en": ["specification"]},
            },
            "QUALITY": {
                "enum": "QUALITY",
                "prototypes": {"es": ["Calidad"], "en": ["Quality"]},
                "structural_signals": {
                    "section_titles": {"es": ["calidad"], "en": ["quality"]},
                    "patterns": [],
                },
                "lexicon": {"es": ["calidad"], "en": ["quality"]},
            },
        },
        "doc_type_priors": {},
        "ingestion": {
            "segmentation": {
                "monolith_strategy": "structural_markers",
                "fallback": "single_segment_declared_type",
                "markers": {"es": ["anexo"], "en": ["annex"]},
            }
        },
        "aggregation": {
            "chunk_combiner": "weighted_mean",
            "doc_method": "top_k_saturating",
            "top_k": 3,
            "doc_relevance": "max(prior_floor, aggregated_chunk_relevance)",
            "keep_evidence_pointers": True,
        },
    }
    with pytest.raises(
        ValidationError, match="The registry must contain exactly the six canonical categories"
    ):
        CategoryRegistry.model_validate(registry_data)


def test_invalid_weight_sum():
    """Verify that weights must sum to exactly 1.0 (with float tolerance)."""
    registry_data = load_category_registry().model_dump()
    registry_data["defaults"]["weights"] = {
        "embedding": 0.50,
        "structural": 0.20,
        "lexicon": 0.10,
    }  # Sum = 0.80
    with pytest.raises(ValidationError, match="Weights must sum to 1.0"):
        CategoryRegistry.model_validate(registry_data)


def test_invalid_threshold_order_low_high():
    """Verify that escalate_low must be less than escalate_high."""
    registry_data = load_category_registry().model_dump()
    registry_data["defaults"]["thresholds"]["escalate_low"] = 0.70
    registry_data["defaults"]["thresholds"]["escalate_high"] = 0.60
    with pytest.raises(ValidationError, match="escalate_low must be less than escalate_high"):
        CategoryRegistry.model_validate(registry_data)


def test_invalid_threshold_order_insufficient_evidence():
    """Verify that insufficient_evidence must be less than or equal to escalate_low."""
    registry_data = load_category_registry().model_dump()
    registry_data["defaults"]["thresholds"]["escalate_low"] = 0.35
    registry_data["defaults"]["thresholds"]["insufficient_evidence"] = 0.40
    with pytest.raises(
        ValidationError, match="insufficient_evidence must be less than or equal to escalate_low"
    ):
        CategoryRegistry.model_validate(registry_data)


def test_invalid_regex_pattern():
    """Verify that we check and raise ValueError for invalid/uncompilable regex patterns."""
    registry_data = load_category_registry().model_dump()
    # Add an invalid pattern that can't compile
    registry_data["categories"]["LEGAL"]["structural_signals"]["patterns"].append(
        "[invalid(pattern"
    )
    with pytest.raises(ValidationError, match="Invalid regex pattern"):
        CategoryRegistry.model_validate(registry_data)


def test_prior_out_of_bounds():
    """Verify that priors must be between 0.0 and 1.0."""
    registry_data = load_category_registry().model_dump()
    registry_data["doc_type_priors"]["contract"]["LEGAL"] = 1.25
    with pytest.raises(
        ValidationError, match="Prior value for contract / LEGAL must be between 0.0 and 1.0"
    ):
        CategoryRegistry.model_validate(registry_data)


def test_invalid_cutoff_date():
    """Verify that cutoff_date must be a valid ISO format date."""
    registry_data = load_category_registry().model_dump()
    registry_data["version"]["cutoff_date"] = "not-a-date"
    with pytest.raises(ValidationError, match="Input should be a valid date"):
        CategoryRegistry.model_validate(registry_data)


def test_robust_path_fallback():
    """Verify that load_category_registry can automatically resolve files with path fallback."""
    registry = load_category_registry()
    assert registry is not None
    assert isinstance(registry, CategoryRegistry)
