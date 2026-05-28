"""Workflow guard for operator-only real document flow execution.

Suite ID: TASK-OPS-DOCFLOW-012
"""

from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[4]
    / ".github"
    / "workflows"
    / "real-document-operability.yml"
)


def test_real_document_operability_workflow_is_operator_dispatch_only() -> None:
    """Real-document flow must not run as a required PR or push gate."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    trigger_block = workflow.split("permissions:", maxsplit=1)[0]

    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "push:" not in trigger_block


def test_real_document_pytest_gate_requires_explicit_operator_input() -> None:
    """The real-document pytest step must be guarded by operator confirmation."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run_real_document_flow" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "inputs.run_real_document_flow == 'true'" in workflow
    assert "Real Document Flow | Needs real fixtures + env | No (operator)" in workflow
