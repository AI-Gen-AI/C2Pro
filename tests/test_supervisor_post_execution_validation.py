"""Tests for UNIFY-010: Post-execution validation hook in supervisor.py.

Tests the validar_tarea_post_ejecucion() function that validates tasks
AFTER execution to ensure backlog was updated correctly.
"""
import pytest
import tempfile
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.supervisor import (
    verificar_backlog_actualizado,
    validar_tarea_post_ejecucion,
    MASTER_BACKLOG_PATH,
    CATEGORY_BACKLOGS_DIR,
)


class TestVerificarBacklogActualizado:
    """Tests for verificar_backlog_actualizado() function."""

    def test_encuentra_tarea_completada_master_backlog(self, tmp_path, monkeypatch):
        """Should find completed task [x] in master backlog."""
        # Create master backlog with completed task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [x] | P1 | `TASK-1490` | None | Enable RLS | [x] Implemented @2026-04-04 |
| [ ] | P0 | `TASK-1491` | None | Add indexes | Infrastructure |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", tmp_path / "backlogs")

        # Test - should find completed task
        actualizado, archivo = verificar_backlog_actualizado("TASK-1490")
        assert actualizado is True
        assert "C2PRO_MASTER_BACKLOG.md" in archivo

    def test_encuentra_tarea_completada_category_backlog(self, tmp_path, monkeypatch):
        """Should find completed task [x] in category backlog."""
        # Create category backlog with completed task
        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        backend_backlog = backlogs_dir / "BCK_BACKEND.md"
        backend_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [x] | P1 | `TASK-BCK-018` | Security | Remove fallback | [x] Implemented @2026-04-04 |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", tmp_path / "master.md")
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Test
        actualizado, archivo = verificar_backlog_actualizado("TASK-BCK-018")
        assert actualizado is True
        assert "BCK_BACKEND.md" in archivo

    def test_no_encuentra_tarea_pendiente(self, tmp_path, monkeypatch):
        """Should return False for pending task [ ] (not completed)."""
        # Create master backlog with pending task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P1 | `TASK-PENDING-001` | None | Not completed yet | Backlog |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", tmp_path / "backlogs")

        # Test - should NOT find it (not marked [x])
        actualizado, mensaje = verificar_backlog_actualizado("TASK-PENDING-001")
        assert actualizado is False
        assert "no esta marcado como completo" in mensaje

    def test_no_encuentra_tarea_inexistente(self, tmp_path, monkeypatch):
        """Should return False for non-existent task."""
        # Create empty backlog
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text("# Empty\n", encoding="utf-8")

        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Test
        actualizado, mensaje = verificar_backlog_actualizado("TASK-NONEXISTENT-999")
        assert actualizado is False
        assert "no esta marcado como completo" in mensaje


class TestValidarTareaPostEjecucion:
    """Tests for validar_tarea_post_ejecucion() post-execution validation hook."""

    def test_skip_validacion_tarea_pendiente(self):
        """Should skip validation for pending tasks."""
        tarea = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "estado": "pendiente",
            "descripcion": "Pending task",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is True
        assert "POST-EXEC VALIDATION SKIPPED" in mensaje
        assert "solo para tareas completadas" in mensaje

    def test_skip_validacion_tarea_en_progreso(self):
        """Should skip validation for in-progress tasks."""
        tarea = {
            "tarea_id": "T002",
            "backlog_id": "TASK-1490",
            "estado": "en_progreso",
            "descripcion": "In progress task",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is True
        assert "POST-EXEC VALIDATION SKIPPED" in mensaje

    def test_skip_validacion_tarea_fallida(self):
        """Should skip validation for failed tasks."""
        tarea = {
            "tarea_id": "T003",
            "backlog_id": "TASK-1490",
            "estado": "fallido",
            "descripcion": "Failed task",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is True
        assert "POST-EXEC VALIDATION SKIPPED" in mensaje

    def test_rechaza_tarea_completada_sin_backlog_id(self):
        """Should reject completed task without backlog_id."""
        tarea = {
            "tarea_id": "T004",
            "estado": "completado",
            "descripcion": "Completed task without backlog_id",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is False
        assert "POST-EXEC VALIDATION FAILED" in mensaje
        assert "sin backlog_id" in mensaje

    def test_rechaza_tarea_completada_backlog_no_actualizado(self, tmp_path, monkeypatch):
        """Should reject completed task when backlog is still pending [ ]."""
        # Create backlog with pending (not completed) task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P1 | `TASK-NOT-UPDATED` | None | Still pending | Backlog |
""",
            encoding="utf-8",
        )

        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Task marked complete in blackboard but NOT in backlog
        tarea = {
            "tarea_id": "T005",
            "backlog_id": "TASK-NOT-UPDATED",
            "estado": "completado",
            "descripcion": "Completed in blackboard but not in backlog",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is False
        assert "POST-EXEC VALIDATION FAILED" in mensaje
        assert "NO esta marcado como completo [x]" in mensaje
        assert "ACCION REQUERIDA" in mensaje

    def test_acepta_tarea_completada_backlog_actualizado_master(self, tmp_path, monkeypatch):
        """Should accept completed task when backlog is marked [x] in master backlog."""
        # Create master backlog with completed task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [x] | P1 | `TASK-COMPLETED-001` | None | Properly completed | [x] Implemented @2026-04-04 |
""",
            encoding="utf-8",
        )

        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Task completed in both blackboard and backlog
        tarea = {
            "tarea_id": "T006",
            "backlog_id": "TASK-COMPLETED-001",
            "estado": "completado",
            "descripcion": "Properly completed task",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is True
        assert "POST-EXEC VALIDATION OK" in mensaje
        assert "marcado [x]" in mensaje
        assert "C2PRO_MASTER_BACKLOG.md" in mensaje

    def test_acepta_tarea_completada_backlog_actualizado_category(self, tmp_path, monkeypatch):
        """Should accept completed task when backlog is marked [x] in category backlog."""
        # Create category backlog with completed task
        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        qa_backlog = backlogs_dir / "QA_QUALITY_ASSURANCE.md"
        qa_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [x] | P2 | `TASK-QA-042` | None | Tests written | [x] Verified @2026-04-04 |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", tmp_path / "master.md")
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Task completed in both blackboard and backlog
        tarea = {
            "tarea_id": "T007",
            "backlog_id": "TASK-QA-042",
            "estado": "completado",
            "descripcion": "Tests completed",
        }

        valido, mensaje = validar_tarea_post_ejecucion(tarea)
        assert valido is True
        assert "POST-EXEC VALIDATION OK" in mensaje
        assert "marcado [x]" in mensaje
        assert "QA_QUALITY_ASSURANCE.md" in mensaje


def test_integration_post_execution_validation():
    """Integration test: Post-execution validation workflow.

    This test simulates the full workflow:
    1. Task completes in blackboard (estado: completado)
    2. Post-execution validation checks backlog
    3. Validation fails if backlog not updated
    4. Validation passes if backlog marked [x]
    """
    # Scenario 1: Task completed but backlog not updated
    tarea_sin_actualizar = {
        "tarea_id": "T999",
        "backlog_id": "TASK-FAKE-999",
        "estado": "completado",
        "descripcion": "Task completed but backlog not updated",
    }

    valido, mensaje = validar_tarea_post_ejecucion(tarea_sin_actualizar)
    assert valido is False
    assert "POST-EXEC VALIDATION FAILED" in mensaje

    # Scenario 2: Task not yet completed - validation skipped
    tarea_pendiente = {
        "tarea_id": "T998",
        "backlog_id": "TASK-FAKE-998",
        "estado": "pendiente",
        "descripcion": "Pending task - validation should be skipped",
    }

    valido, mensaje = validar_tarea_post_ejecucion(tarea_pendiente)
    assert valido is True
    assert "SKIPPED" in mensaje


def test_validation_error_message_provides_guidance():
    """Error messages should provide clear guidance on how to fix the issue."""
    tarea = {
        "tarea_id": "T777",
        "backlog_id": "TASK-MISSING-777",
        "estado": "completado",
        "descripcion": "Completed task with missing backlog update",
    }

    valido, mensaje = validar_tarea_post_ejecucion(tarea)
    assert valido is False

    # Check that message provides actionable guidance
    assert "ACCION REQUERIDA" in mensaje
    assert "Marca manualmente" in mensaje
    assert "TASK-MISSING-777" in mensaje
    assert "[x]" in mensaje


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
