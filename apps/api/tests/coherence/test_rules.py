# apps/api/tests/coherence/test_rules.py

import pytest
import yaml
from apps.api.src.modules.coherence.rules import Rule, load_rules
from pydantic import ValidationError


@pytest.fixture
def valid_rules_yaml(tmp_path):
    """Fixture for a valid rules YAML file."""
    content = """
- id: test-rule-1
  description: A valid test rule
  inputs: ["project.data.field1"]
  detection_logic: "field1 > 10"
  severity: high
  evidence_fields: ["project.data.field1"]
- id: test-rule-2
  description: Another valid test rule
  inputs: ["project.data.field2"]
  detection_logic: "field2 == 'status_ok'"
  severity: low
  evidence_fields: ["project.data.field2"]
"""
    file_path = tmp_path / "valid_rules.yaml"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def invalid_rules_yaml_malformed(tmp_path):
    """Fixture for a malformed rules YAML file."""
    content = """
- id: test-rule-3
  description: Missing inputs field
  detection_logic: "some_logic"
  severity: medium
  evidence_fields: ["some_field"]
- id: test-rule-4
  description: Another rule
  inputs: ["field_x"]
  severity: critical
  evidence_fields: ["field_x"]
"""  # Inputs is missing for rule 3, but this will fail Pydantic
    file_path = tmp_path / "invalid_rules_malformed.yaml"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def invalid_rules_yaml_bad_severity(tmp_path):
    """Fixture for a rules YAML file with invalid severity."""
    content = """
- id: test-rule-5
  description: Rule with bad severity
  inputs: ["project.data.field3"]
  detection_logic: "field3 < 0"
  severity: unknown_severity
  evidence_fields: ["project.data.field3"]
"""
    file_path = tmp_path / "invalid_rules_bad_severity.yaml"
    file_path.write_text(content)
    return str(file_path)


def test_load_rules_valid(valid_rules_yaml):
    """Test that load_rules successfully loads and validates valid rules."""
    rules = load_rules(valid_rules_yaml)
    assert len(rules) == 2
    assert all(isinstance(rule, Rule) for rule in rules)
    assert rules[0].id == "test-rule-1"
    assert rules[1].severity == "low"


def test_load_rules_malformed_yaml(tmp_path):
    """Test that load_rules raises an error for malformed YAML."""
    file_path = tmp_path / "malformed.yaml"
    file_path.write_text("id: rule1\n  - description: desc")  # Malformed structure
    with pytest.raises(yaml.YAMLError):
        load_rules(str(file_path))


def test_load_rules_missing_required_field(invalid_rules_yaml_malformed):
    """Test that load_rules raises ValidationError for missing required fields."""
    with pytest.raises(ValidationError) as excinfo:
        load_rules(invalid_rules_yaml_malformed)
    assert "Field required" in str(excinfo.value)
    assert "inputs" in str(excinfo.value)  # Expecting inputs to be missing from first rule


def test_load_rules_invalid_severity(invalid_rules_yaml_bad_severity):
    """Test that load_rules raises ValidationError for invalid severity enum."""
    with pytest.raises(ValidationError) as excinfo:
        load_rules(invalid_rules_yaml_bad_severity)
    assert "Input should be 'critical', 'high', 'medium' or 'low'" in str(excinfo.value)
    assert "'unknown_severity'" in str(excinfo.value)
