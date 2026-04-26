"""
Contract test for Coherence span schema validation.
Ensures that only allowlisted attributes can be added to spans, preventing PII/data leakage.
"""
from __future__ import annotations

import pytest

from src.core.observability.coherence_tracing import _validate_attributes


def test_validate_attributes_passes_with_allowlisted_keys():
    """
    Given: A dictionary of attributes that are all in the allowlist.
    When: The attributes are validated.
    Then: The validation should pass without raising an exception.
    """
    valid_attributes = {
        "coherence.node_name": "test_node",
        "coherence.score_version": "v1",
        "coherence.findings_count": 5,
        "coherence.rule_ids": ["rule-1", "rule-2"],
        "coherence.tenant_id": "tenant-abc",
        "coherence.project_id": "project-123",
        "coherence.alert.rule_id": "alert-rule-1",
        "coherence.alert.severity": "high",
    }
    
    try:
        _validate_attributes(valid_attributes)
    except ValueError:
        pytest.fail("Validation unexpectedly failed for allowlisted attributes.")

def test_validate_attributes_fails_with_non_allowlisted_key():
    """
    Given: A dictionary containing an attribute key that is NOT in the allowlist.
    When: The attributes are validated.
    Then: A ValueError should be raised.
    """
    invalid_attributes = {
        "coherence.node_name": "test_node",
        "coherence.tenant_id": "tenant-abc",
        "coherence.pii_leak": "user@example.com",  # This key is not in the allowlist
    }
    
    with pytest.raises(ValueError, match="Attribute 'coherence.pii_leak' is not in the allowlisted schema."):
        _validate_attributes(invalid_attributes)

def test_validate_attributes_fails_with_slightly_different_key():
    """
    Given: A dictionary with a key that is similar but not identical to an allowlisted key.
    When: The attributes are validated.
    Then: A ValueError should be raised to enforce exact matching.
    """
    almost_valid_attributes = {
        "coherence.node-name": "test_node",  # Hyphen instead of underscore
    }
    
    with pytest.raises(ValueError, match="Attribute 'coherence.node-name' is not in the allowlisted schema."):
        _validate_attributes(almost_valid_attributes)

def test_validate_attributes_succeeds_with_empty_dict():
    """
    Given: An empty dictionary.
    When: The attributes are validated.
    Then: The validation should pass without raising an exception.
    """
    try:
        _validate_attributes({})
    except ValueError:
        pytest.fail("Validation unexpectedly failed for an empty attribute dictionary.")

def test_validate_attributes_succeeds_with_subset_of_keys():
    """
    Given: A dictionary containing a valid subset of allowlisted keys.
    When: The attributes are validated.
    Then: The validation should pass.
    """
    subset_attributes = {
        "coherence.node_name": "test_node",
        "coherence.tenant_id": "tenant-abc",
    }
    
    try:
        _validate_attributes(subset_attributes)
    except ValueError:
        pytest.fail("Validation unexpectedly failed for a subset of allowlisted attributes.")
