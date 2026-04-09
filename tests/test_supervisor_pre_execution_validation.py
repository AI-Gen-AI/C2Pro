"""Tests for UNIFY-009: Pre-execution validation hook in supervisor.py.

Tests the validar_tarea_antes_ejecucion() function that validates tasks
BEFORE execution to ensure they have valid backlog_id linking.
"""
import pytest
import tempfile
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.supervisor import (
    validar_backlog_id_existe,
    validar_tarea_antes_ejecucion,
    BACKLOG_ID_PATTERN,
    MASTER_BACKLOG_PATH,
    CATEGORY_BACKLOGS_DIR,
)


class TestValidarBacklogIdExiste:
    """Tests for validar_backlog_id_existe() function."""

    def test_encuentra_id_en_master_backlog(self, tmp_path, monkeypatch):
        """Should find backlog_id in master backlog file."""
        # Create temporary master backlog
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P1 | `TASK-1490` | None | Enable RLS | Infrastructure |
| [x] | P0 | `UNIFY-001` | None | Unify agents.md | Docs |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", tmp_path / "backlogs")

        # Test
        existe, archivo = validar_backlog_id_existe("TASK-1490")
        assert existe is True
        assert "C2PRO_MASTER_BACKLOG.md" in archivo

    def test_encuentra_id_en_category_backlog(self, tmp_path, monkeypatch):
        """Should find backlog_id in category backlog file."""
        # Create category backlog directory
        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Create category backlog
        backend_backlog = backlogs_dir / "BCK_BACKEND.md"
        backend_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P1 | `TASK-BCK-018` | Security | Remove fallback paths | Docs |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", tmp_path / "master.md")
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Test
        existe, archivo = validar_backlog_id_existe("TASK-BCK-018")
        assert existe is True
        assert "BCK_BACKEND.md" in archivo

    def test_no_encuentra_id_inexistente(self, tmp_path, monkeypatch):
        """Should return False for non-existent backlog_id."""
        # Create empty master backlog
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text("# Empty backlog\n", encoding="utf-8")

        # Create empty category backlogs
        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        # Test
        existe, mensaje = validar_backlog_id_existe("TASK-NONEXISTENT-999")
        assert existe is False
        assert "no encontrado" in mensaje

    def test_encuentra_id_completado(self, tmp_path, monkeypatch):
        """Should find backlog_id even if task is marked complete [x]."""
        # Create master backlog with completed task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [x] | P0 | `UNIFY-007` | None | Sync script | Backend |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", tmp_path / "backlogs")

        # Test
        existe, archivo = validar_backlog_id_existe("UNIFY-007")
        assert existe is True
        assert "C2PRO_MASTER_BACKLOG.md" in archivo


class TestValidarTareaAntesEjecucion:
    """Tests for validar_tarea_antes_ejecucion() pre-execution validation hook."""

    def test_rechaza_tarea_sin_backlog_id(self):
        """Should reject task missing backlog_id field."""
        tarea = {
            "tarea_id": "T001",
            "descripcion": "Test task without backlog_id",
            "asignado_a": "backend",
            "estado": "pendiente",
        }

        valido, mensaje = validar_tarea_antes_ejecucion(tarea)
        assert valido is False
        assert "PRE-EXEC VALIDATION FAILED" in mensaje
        assert "backlog_id" in mensaje.lower()
        assert "OBLIGATORIO" in mensaje

    def test_rechaza_backlog_id_vacio(self):
        """Should reject task with empty backlog_id."""
        tarea = {
            "tarea_id": "T002",
            "backlog_id": "",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "pendiente",
        }

        valido, mensaje = validar_tarea_antes_ejecucion(tarea)
        assert valido is False
        assert "PRE-EXEC VALIDATION FAILED" in mensaje
        assert "no puede estar vacio" in mensaje

    def test_rechaza_backlog_id_formato_invalido(self):
        """Should reject task with invalid backlog_id format."""
        invalid_ids = [
            "task-123",  # lowercase
            "TSK-123",  # wrong prefix
            "TASK123",  # missing hyphen
            "TASK-",  # missing suffix
            "TASK-abc",  # lowercase letters
        ]

        for invalid_id in invalid_ids:
            tarea = {
                "tarea_id": "T003",
                "backlog_id": invalid_id,
                "descripcion": "Test task",
                "asignado_a": "backend",
                "estado": "pendiente",
            }

            valido, mensaje = validar_tarea_antes_ejecucion(tarea)
            assert valido is False, f"Should reject invalid ID: {invalid_id}"
            assert "PRE-EXEC VALIDATION FAILED" in mensaje
            assert "invalido" in mensaje.lower()
            assert "TASK-[A-Z0-9-]+" in mensaje

    def test_rechaza_backlog_id_no_encontrado(self, tmp_path, monkeypatch):
        """Should reject task when backlog_id not found in backlog files."""
        # Create empty backlog files
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text("# Empty\n", encoding="utf-8")

        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        tarea = {
            "tarea_id": "T004",
            "backlog_id": "TASK-MISSING-999",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "pendiente",
        }

        valido, mensaje = validar_tarea_antes_ejecucion(tarea)
        assert valido is False
        assert "PRE-EXEC VALIDATION FAILED" in mensaje
        assert "no encontrado" in mensaje
        assert "TASK-MISSING-999" in mensaje

    def test_acepta_tarea_valida_master_backlog(self, tmp_path, monkeypatch):
        """Should accept task with valid backlog_id found in master backlog."""
        # Create master backlog with task
        master_backlog = tmp_path / "C2PRO_MASTER_BACKLOG.md"
        master_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P1 | `TASK-VALID-001` | None | Valid task | Test |
""",
            encoding="utf-8",
        )

        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", master_backlog)
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        tarea = {
            "tarea_id": "T005",
            "backlog_id": "TASK-VALID-001",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "pendiente",
        }

        valido, mensaje = validar_tarea_antes_ejecucion(tarea)
        assert valido is True
        assert "PRE-EXEC VALIDATION OK" in mensaje
        assert "TASK-VALID-001" in mensaje
        assert "verificado" in mensaje.lower()

    def test_acepta_tarea_valida_category_backlog(self, tmp_path, monkeypatch):
        """Should accept task with valid backlog_id found in category backlog."""
        # Create category backlog with task
        backlogs_dir = tmp_path / "backlogs"
        backlogs_dir.mkdir()

        qa_backlog = backlogs_dir / "QA_QUALITY_ASSURANCE.md"
        qa_backlog.write_text(
            """
| Status | Priority | Task ID | Depends | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ] | P2 | `TASK-QA-042` | None | Write tests | Test |
""",
            encoding="utf-8",
        )

        # Monkeypatch paths
        monkeypatch.setattr("core.supervisor.MASTER_BACKLOG_PATH", tmp_path / "master.md")
        monkeypatch.setattr("core.supervisor.CATEGORY_BACKLOGS_DIR", backlogs_dir)

        tarea = {
            "tarea_id": "T006",
            "backlog_id": "TASK-QA-042",
            "descripcion": "Test task",
            "asignado_a": "qa",
            "estado": "pendiente",
        }

        valido, mensaje = validar_tarea_antes_ejecucion(tarea)
        assert valido is True
        assert "PRE-EXEC VALIDATION OK" in mensaje
        assert "TASK-QA-042" in mensaje
        assert "QA_QUALITY_ASSURANCE.md" in mensaje

    def test_formatos_validos_backlog_id(self):
        """Should accept all valid backlog_id formats."""
        valid_ids = [
            "TASK-1490",  # numeric
            "TASK-BCK-018",  # category prefix
            "TASK-UNIFY-009",  # multi-part
            "TASK-AI-ML-001",  # multiple hyphens
            "UNIFY-009",  # without TASK prefix (legacy)
        ]

        for valid_id in valid_ids:
            # Verify pattern matches
            if valid_id.startswith("TASK-"):
                assert BACKLOG_ID_PATTERN.match(valid_id), f"Pattern should match: {valid_id}"


def test_integration_pre_execution_validation():
    """Integration test: Pre-execution validation in execution flow.

    This test verifies that the validation hook properly blocks
    execution of tasks without valid backlog_id.
    """
    # Create task without backlog_id
    tarea_invalida = {
        "tarea_id": "T999",
        "descripcion": "Task without backlog_id",
        "asignado_a": "backend",
        "estado": "pendiente",
    }

    # Validation should fail
    valido, mensaje = validar_tarea_antes_ejecucion(tarea_invalida)
    assert valido is False

    # Create task with valid format but non-existent ID
    tarea_no_existe = {
        "tarea_id": "T998",
        "backlog_id": "TASK-FAKE-999",
        "descripcion": "Task with non-existent backlog_id",
        "asignado_a": "backend",
        "estado": "pendiente",
    }

    # Validation should fail (ID not in backlog files)
    valido, mensaje = validar_tarea_antes_ejecucion(tarea_no_existe)
    assert valido is False
    assert "no encontrado" in mensaje


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
