"""Tests for G1 Single-Writer Control Plane transition and verification."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from core.result_parser import (
    validate_result,
)
from core.supervisor import (
    es_nuevo_control_work_id,
    validar_tarea_antes_ejecucion,
    validar_tarea_post_ejecucion,
)

ROOT = Path(__file__).resolve().parents[1]


def test_es_nuevo_control_work_id():
    """Verify that es_nuevo_control_work_id correctly identifies new-control work IDs."""
    assert es_nuevo_control_work_id("C2PRO-DEV-02") is True
    assert es_nuevo_control_work_id("C2PRO-DEV-99") is True
    assert es_nuevo_control_work_id("TASK-1490") is False
    assert es_nuevo_control_work_id("UNIFY-009") is False
    assert es_nuevo_control_work_id("") is False


def test_new_control_worker_no_legacy_write(monkeypatch, tmp_path):
    """Test that new-control tasks succeed pre/post exec validation without legacy writes."""
    # Mock legacy-compatibility to return dual_read_single_write_new_control
    monkeypatch.setattr(
        "core.supervisor.cargar_legacy_compatibility",
        lambda: {"transition_mode": "dual_read_single_write_new_control"},
    )

    # Mock es_nuevo_control_work_id to return True for C2PRO-DEV-02
    monkeypatch.setattr(
        "core.supervisor.es_nuevo_control_work_id",
        lambda x: x == "C2PRO-DEV-02",
    )

    # Create the correct folder structures
    control_dir = tmp_path / ".c2pro" / "control"
    work_dir = tmp_path / ".c2pro" / "work"
    control_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. PRE-EXEC validation
    # Create a mock work-queue.yaml
    wq_file = control_dir / "work-queue.yaml"
    wq_data = {
        "schema": "c2pro-work-queue-v1",
        "items": [
            {
                "work_id": "C2PRO-DEV-02",
                "status": "in_progress",
                "work_ref": ".c2pro/work/C2PRO-DEV-02.yaml",
            }
        ]
    }
    with open(wq_file, "w", encoding="utf-8") as f:
        yaml.dump(wq_data, f)

    # Create a mock envelope
    env_file = work_dir / "C2PRO-DEV-02.yaml"
    env_data = {
        "schema": "c2pro-work-envelope-v1",
        "work_id": "C2PRO-DEV-02",
    }
    with open(env_file, "w", encoding="utf-8") as f:
        yaml.dump(env_data, f)

    # Point BASE_DIR in core.supervisor to our tmp_path to find mock files
    monkeypatch.setattr("core.supervisor.BASE_DIR", tmp_path)

    # Test pre-exec validation
    tarea = {
        "tarea_id": "T001",
        "backlog_id": "C2PRO-DEV-02",
        "estado": "pendiente",
    }
    valido, mensaje = validar_tarea_antes_ejecucion(tarea)
    assert valido is True, f"Pre-exec validation failed: {mensaje}"
    assert "verificado en .c2pro/control/work-queue.yaml" in mensaje

    # 2. POST-EXEC validation
    tarea_completa = {
        "tarea_id": "T001",
        "backlog_id": "C2PRO-DEV-02",
        "estado": "completado",
    }
    valido_post, mensaje_post = validar_tarea_post_ejecucion(tarea_completa)
    assert valido_post is True, f"Post-exec validation failed: {mensaje_post}"
    assert "validado exitosamente contra el plano de control canonical" in mensaje_post


def test_legacy_compatibility_behavior(monkeypatch, tmp_path):
    """Test that genuinely legacy tasks still require legacy Markdown validation."""
    monkeypatch.setattr(
        "core.supervisor.cargar_legacy_compatibility",
        lambda: {"transition_mode": "dual_read_single_write_new_control"},
    )
    monkeypatch.setattr(
        "core.supervisor.es_nuevo_control_work_id",
        lambda x: False,  # Truly legacy
    )
    monkeypatch.setattr("core.supervisor.BASE_DIR", tmp_path)

    # Pre-exec validation fails for non-existent legacy task
    tarea = {
        "tarea_id": "T002",
        "backlog_id": "TASK-MISSING-999",
        "estado": "pendiente",
    }
    valido, mensaje = validar_tarea_antes_ejecucion(tarea)
    assert valido is False
    assert "no encontrado en ningun backlog" in mensaje

    # Post-exec validation fails if not marked as complete in legacy backlogs
    tarea_completa = {
        "tarea_id": "T002",
        "backlog_id": "TASK-MISSING-999",
        "estado": "completado",
    }
    valido_post, mensaje_post = validar_tarea_post_ejecucion(tarea_completa)
    assert valido_post is False
    assert "NO esta marcado como completo [x] en los archivos" in mensaje_post


def test_structured_result_schema_validation():
    """Verify that validate_result accepts valid and rejects invalid result payloads."""
    valid_data = {
        "schema": "c2pro-implementation-result-v1",
        "work_id": "C2PRO-DEV-02",
        "base_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "head_sha": "f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2",
        "branch": "feat/something",
        "files_changed": ["src/core/supervisor.py"],
        "tests": [
            {"name": "test_something", "status": "PASS"}
        ],
        "ci_status": "success",
        "findings": ["Everything is fine"],
        "residual_risks": [],
        "recommendation": "approve",
        "pr_url": None,
    }

    # Should validate successfully
    validate_result(valid_data)

    # Should fail if schema is wrong
    bad_schema = valid_data.copy()
    bad_schema["schema"] = "invalid-schema"
    with pytest.raises(ValueError, match="Invalid schema"):
        validate_result(bad_schema)

    # Should fail if work_id is wrong
    bad_work_id = valid_data.copy()
    bad_work_id["work_id"] = "TASK-123"
    with pytest.raises(ValueError, match="Invalid work_id"):
        validate_result(bad_work_id)

    # Should fail if base_sha is wrong length/format
    bad_sha = valid_data.copy()
    bad_sha["base_sha"] = "shortsha"
    with pytest.raises(ValueError, match="Invalid base_sha"):
        validate_result(bad_sha)

    # Should fail if recommendation is not in enum
    bad_rec = valid_data.copy()
    bad_rec["recommendation"] = "invalid_enum_val"
    with pytest.raises(ValueError, match="Invalid recommendation"):
        validate_result(bad_rec)


def test_head_sha_mismatch():
    """Verify that expected_head_sha check correctly rejects mismatched head SHAs."""
    data = {
        "schema": "c2pro-implementation-result-v1",
        "work_id": "C2PRO-DEV-02",
        "base_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "head_sha": "f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2",
        "branch": "feat/something",
        "files_changed": [],
        "tests": [],
        "ci_status": "success",
        "findings": [],
        "residual_risks": [],
        "recommendation": "approve",
        "pr_url": None,
    }

    # Matches expected
    validate_result(data, expected_head_sha="f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2")

    # Mismatched expected SHA should fail
    with pytest.raises(ValueError, match="head_sha mismatch"):
        validate_result(data, expected_head_sha="0000000000000000000000000000000000000000")


def test_worker_cannot_be_instructed_to_mutate_legacy_files():
    """Assert that agents.md boundaries instruct ordinary workers to treat legacy files as read-only."""
    agents_path = ROOT / "agents.md"
    assert agents_path.exists()
    content = agents_path.read_text(encoding="utf-8")

    # Assert boundaries contain read-only statements
    assert "ALWAYS treat blackboard.json and C2PRO_MASTER_BACKLOG.md as READ-ONLY cold references" in content
    assert "ALWAYS provide structured worker evidence (fenced YAML result block matching c2pro-implementation-result-v1)" in content


def test_planner_master_retains_canonical_write_authority():
    """Assert that CRITICAL_BACKLOG_REQUIREMENT.md declares Planner/Master as sole canonical write authority."""
    req_path = ROOT / ".claude" / "rules" / "CRITICAL_BACKLOG_REQUIREMENT.md"
    assert req_path.exists()
    content = req_path.read_text(encoding="utf-8")

    assert "Only the **Planner / Master Orchestrator** has write authority to mutate the canonical planning state" in content


def test_workspace_lifecycle_owner_is_orchestrator():
    """Assert that the workspace lifecycle is owned exclusively by the orchestrator."""
    policy_path = ROOT / ".c2pro" / "control" / "workspace-policy.yaml"
    assert policy_path.exists()
    with open(policy_path, encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    assert policy.get("lifecycle_owner") == "orchestrator"


def test_max_active_writer_tasks():
    """Assert that a workspace has at most one active writer task."""
    policy_path = ROOT / ".c2pro" / "control" / "workspace-policy.yaml"
    assert policy_path.exists()
    with open(policy_path, encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    assert policy.get("max_active_writer_tasks_per_workspace") == 1


def test_worker_cannot_be_instructed_to_create_remove_reset_clean_worktrees():
    """Assert that workers are forbidden from independently managing workspace lifecycles."""
    policy_path = ROOT / ".c2pro" / "control" / "workspace-policy.yaml"
    assert policy_path.exists()
    with open(policy_path, encoding="utf-8") as f:
        policy = yaml.safe_load(f)

    worker_perms = policy.get("worker_permissions", {})
    assert worker_perms.get("create_workspace") is False
    assert worker_perms.get("remove_workspace") is False
    assert worker_perms.get("reset_workspace") is False
    assert worker_perms.get("clean_workspace") is False
    assert worker_perms.get("repurpose_workspace") is False
    assert worker_perms.get("validate_workspace") is True


def test_no_local_filesystem_paths_in_canonical_state():
    """Assert that no absolute/local machine paths exist in any .yaml control config."""
    control_dir = ROOT / ".c2pro" / "control"
    assert control_dir.is_dir()

    path_pattern = re.compile(r"(?:[a-zA-Z]:\\|/home/|/Users/)")

    for yaml_path in control_dir.glob("*.yaml"):
        content = yaml_path.read_text(encoding="utf-8")
        assert not path_pattern.search(content), f"Local path detected in canonical state file: {yaml_path.name}"


def test_workspace_guard_failure_mismatch_outcome():
    """Assert that WORKSPACE_GUARD_FAILURE is the required mismatch outcome and action is stop."""
    policy_path = ROOT / ".c2pro" / "control" / "workspace-policy.yaml"
    assert policy_path.exists()
    with open(policy_path, encoding="utf-8") as f:
        policy = yaml.safe_load(f)

    guard_fail = policy.get("guard_failure", {})
    assert guard_fail.get("code") == "WORKSPACE_GUARD_FAILURE"
    assert guard_fail.get("action") == "stop"
