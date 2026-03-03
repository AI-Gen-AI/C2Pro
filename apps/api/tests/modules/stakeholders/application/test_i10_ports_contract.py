"""
I10 - Hexagonal Ports Contract (Application, RED)
Test Suite ID: TS-I10-STK-PORT-001
"""

from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_i10_port_contract_declares_raci_inference_port_in_ports_layer_red() -> None:
    """
    TS-I10-STK-PORT-001:
    I10 inference gateway must be declared as a dedicated Protocol in ports layer.
    """
    module_path = (
        _repo_root()
        / "src"
        / "stakeholders"
        / "ports"
        / "raci_inference_service.py"
    )

    assert module_path.exists(), (
        "Expected I10 port module at "
        "src/stakeholders/ports/raci_inference_service.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    port_class = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "IRaciInferenceService"
        ),
        None,
    )
    assert port_class is not None, "IRaciInferenceService Protocol must exist in ports layer."
    assert any(
        isinstance(base, ast.Name) and base.id == "Protocol"
        for base in port_class.bases
    ), "IRaciInferenceService must inherit from typing.Protocol."


def test_i10_port_contract_keeps_protocol_out_of_service_implementation_file_red() -> None:
    """
    TS-I10-STK-PORT-001:
    service implementation modules must not define port contracts.
    """
    service_path = (
        _repo_root()
        / "src"
        / "stakeholders"
        / "application"
        / "services"
        / "raci_generation_service.py"
    )
    tree = ast.parse(service_path.read_text(encoding="utf-8"))
    class_names = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }

    assert "IRaciInferenceService" not in class_names, (
        "IRaciInferenceService must be declared in ports layer, "
        "not in application service implementation module."
    )


def test_i10_port_contract_forbids_concrete_service_in_ports_module_red() -> None:
    """
    TS-I10-STK-PORT-001:
    ports modules must not contain concrete application services.
    """
    legacy_ports_path = (
        _repo_root()
        / "src"
        / "modules"
        / "stakeholders"
        / "application"
        / "ports.py"
    )
    source = legacy_ports_path.read_text(encoding="utf-8")

    assert "class RACIInferenceService" not in source, (
        "Ports module must only expose contracts; concrete RACIInferenceService "
        "belongs in a service implementation module."
    )
