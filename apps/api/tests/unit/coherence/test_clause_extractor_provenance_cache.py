"""#713: coherence cache enrichment must never erase evidence provenance."""

from src.coherence.extraction.clause_extractor import _merge_cache_payload


def test_merge_cache_payload_preserves_evidence_location() -> None:
    evidence_location = {
        "revision_id": "11111111-1111-1111-1111-111111111111",
        "page_number": 3,
        "page_numbers": [3],
        "bbox": [10.0, 20.0, 30.0, 40.0],
        "normalized": True,
    }
    existing = {
        "evidence_location": evidence_location,
        "legacy_field": "keep-me",
        "payment_term_days": 15,
    }

    merged = _merge_cache_payload(
        existing,
        {
            "payment_term_days": 30,
            "warranty_months": 24,
            # An LLM must never be able to overwrite parser-owned provenance.
            "evidence_location": {"page_number": 999},
            "unexpected_model_field": "drop-me",
        },
    )

    assert merged["evidence_location"] == evidence_location
    assert merged["legacy_field"] == "keep-me"
    assert merged["payment_term_days"] == 30
    assert merged["warranty_months"] == 24
    assert "unexpected_model_field" not in merged
    assert existing["payment_term_days"] == 15


def test_merge_cache_payload_handles_empty_existing_payload() -> None:
    assert _merge_cache_payload(None, {"warranty_months": 12}) == {
        "warranty_months": 12
    }
