"""
I11 - HITL Hexagonal Ports Contract (RED)
Test Suite ID: TS-I11-HITL-PORT-001
"""

from __future__ import annotations

import ast
from pathlib import Path


def _api_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_i11_ports_declares_review_queue_repository_protocol_in_ports_layer_red() -> None:
    """
    TS-I11-HITL-PORT-001:
    Review queue contract must exist as Protocol in a dedicated ports module.
    """
    module_path = _api_root() / "src" / "modules" / "hitl" / "ports" / "review_queue_repository.py"

    assert module_path.exists(), (
        "Expected dedicated port module at "
        "src/modules/hitl/ports/review_queue_repository.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IReviewQueueRepository"),
        None,
    )
    assert class_node is not None, "IReviewQueueRepository must exist in ports layer."
    assert any(
        isinstance(base, ast.Name) and base.id == "Protocol"
        for base in class_node.bases
    ), "IReviewQueueRepository must inherit from typing.Protocol."


def test_i11_ports_declares_notification_service_protocol_in_ports_layer_red() -> None:
    """
    TS-I11-HITL-PORT-001:
    Notification contract must exist as Protocol in a dedicated ports module.
    """
    module_path = _api_root() / "src" / "modules" / "hitl" / "ports" / "notification_service.py"

    assert module_path.exists(), (
        "Expected dedicated port module at "
        "src/modules/hitl/ports/notification_service.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "INotificationService"),
        None,
    )
    assert class_node is not None, "INotificationService must exist in ports layer."
    assert any(
        isinstance(base, ast.Name) and base.id == "Protocol"
        for base in class_node.bases
    ), "INotificationService must inherit from typing.Protocol."


def test_i11_ports_module_must_not_contain_concrete_hitl_service_red() -> None:
    """
    TS-I11-HITL-PORT-001:
    Ports module must not host concrete application services.
    """
    ports_module = _api_root() / "src" / "modules" / "hitl" / "application" / "ports.py"
    source = ports_module.read_text(encoding="utf-8")

    assert "class HumanInTheLoopService" not in source, (
        "HumanInTheLoopService must be implemented outside ports module."
    )
