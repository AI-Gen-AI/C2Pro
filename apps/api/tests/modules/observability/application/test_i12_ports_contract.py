"""
I12 - Observability Hexagonal Ports Contract (RED)
Test Suite ID: TS-I12-OBS-PORT-001
"""

from __future__ import annotations

import ast
from pathlib import Path


def _api_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_i12_ports_declares_langsmith_gateway_protocol_in_ports_layer_red() -> None:
    """
    TS-I12-OBS-PORT-001:
    LangSmith gateway must exist as Protocol in a dedicated ports module.
    """
    module_path = _api_root() / "src" / "modules" / "observability" / "ports" / "langsmith_gateway.py"

    assert module_path.exists(), (
        "Expected dedicated port module at "
        "src/modules/observability/ports/langsmith_gateway.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ILangSmithGateway"),
        None,
    )
    assert class_node is not None, "ILangSmithGateway must exist in ports layer."
    assert any(isinstance(base, ast.Name) and base.id == "Protocol" for base in class_node.bases), (
        "ILangSmithGateway must inherit from typing.Protocol."
    )


def test_i12_ports_declares_alert_notifier_protocol_in_ports_layer_red() -> None:
    """
    TS-I12-OBS-PORT-001:
    Alert notifier contract must exist as Protocol in a dedicated ports module.
    """
    module_path = _api_root() / "src" / "modules" / "observability" / "ports" / "alert_notifier.py"

    assert module_path.exists(), (
        "Expected dedicated port module at "
        "src/modules/observability/ports/alert_notifier.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IAlertNotifier"),
        None,
    )
    assert class_node is not None, "IAlertNotifier must exist in ports layer."
    assert any(isinstance(base, ast.Name) and base.id == "Protocol" for base in class_node.bases), (
        "IAlertNotifier must inherit from typing.Protocol."
    )


def test_i12_application_ports_module_must_not_contain_concrete_runtime_services_red() -> None:
    """
    TS-I12-OBS-PORT-001:
    ports module must not host concrete adapter/service implementations.
    """
    ports_module = _api_root() / "src" / "modules" / "observability" / "application" / "ports.py"
    source = ports_module.read_text(encoding="utf-8")

    assert "class LangSmithAdapter" not in source, "LangSmithAdapter must be implemented outside ports module."
    assert "class EvaluationHarness" not in source, "EvaluationHarness must be implemented outside ports module."
