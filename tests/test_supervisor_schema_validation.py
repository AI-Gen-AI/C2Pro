"""
Test Suite for UNIFY-012: Schema Validation Integration in supervisor.py

Tests the 2-layer defense-in-depth validation in guardar_blackboard():
  Layer 1: Schema validation (schemas/{role}_output.json)
  Layer 2: Backlog ID validation (TASK-* pattern + existence in backlog)

Author: Claude (UNIFY-012)
Created: 2026-04-04
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.supervisor import (
    guardar_blackboard,
    validar_task_schemas,
    validar_backlog_ids,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def valid_task_backend():
    """Valid backend task that passes both schema and backlog_id validation."""
    return {
        "tarea_id": "T001",
        "backlog_id": "TASK-UNIFY-012",
        "tipo": "backend",
        "descripcion": "Integrate schema validation into supervisor.py",
        "asignado_a": "backend",
        "estado": "en_progreso",
        "resultado": {
            "exitoso": True,
            "mensaje": "Schema validation integrated successfully",
            "cambios_realizados": [
                "Added validar_task_schemas() function",
                "Modified guardar_blackboard() to validate schemas",
            ],
        },
        "codigo": {
            "archivos_modificados": ["core/supervisor.py"],
            "lineas_agregadas": 85,
            "lineas_eliminadas": 12,
        },
    }


@pytest.fixture
def valid_task_planner():
    """Valid planner task."""
    return {
        "tarea_id": "T002",
        "backlog_id": "TASK-UNIFY-013",
        "tipo": "planning",
        "descripcion": "Plan unified workflow testing",
        "asignado_a": "planner",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Planning not yet started",
        },
        "plan": {
            "fases": [
                {
                    "nombre": "Phase 1: Setup",
                    "descripcion": "Setup test environment",
                    "tareas": ["T002-1", "T002-2"],
                },
                {
                    "nombre": "Phase 2: Execute",
                    "descripcion": "Execute unified workflow tests",
                    "tareas": ["T002-3", "T002-4"],
                },
            ],
            "dependencias": ["TASK-UNIFY-012"],
        },
    }


@pytest.fixture
def invalid_schema_missing_required():
    """Task missing required fields (schema validation failure)."""
    return {
        "tarea_id": "T003",
        "backlog_id": "TASK-TEST-001",
        # Missing: tipo, descripcion, asignado_a, estado, resultado
    }


@pytest.fixture
def invalid_schema_wrong_type():
    """Task with wrong field types (schema validation failure)."""
    return {
        "tarea_id": "T004",
        "backlog_id": "TASK-TEST-002",
        "tipo": "backend",
        "descripcion": "Test task",
        "asignado_a": "backend",
        "estado": "en_progreso",
        "resultado": {
            "exitoso": "yes",  # Should be boolean, not string
            "mensaje": "Test",
        },
    }


@pytest.fixture
def invalid_backlog_id_missing():
    """Task missing backlog_id (backlog_id validation failure)."""
    return {
        "tarea_id": "T005",
        # Missing: backlog_id
        "tipo": "qa",
        "descripcion": "Test task without backlog_id",
        "asignado_a": "qa",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Not started",
        },
    }


@pytest.fixture
def invalid_backlog_id_wrong_pattern():
    """Task with invalid backlog_id pattern."""
    return {
        "tarea_id": "T006",
        "backlog_id": "invalid-pattern",  # Should be TASK-*
        "tipo": "frontend",
        "descripcion": "Test task with invalid backlog_id",
        "asignado_a": "frontend",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Not started",
        },
    }


@pytest.fixture
def blackboard_data_valid(valid_task_backend, valid_task_planner):
    """Valid blackboard data with 2 tasks."""
    return {
        "estado_actual": "iniciado",
        "tareas": [valid_task_backend, valid_task_planner],
    }


@pytest.fixture
def blackboard_data_schema_errors(
    valid_task_backend, invalid_schema_missing_required
):
    """Blackboard data with schema validation errors."""
    return {
        "estado_actual": "iniciado",
        "tareas": [valid_task_backend, invalid_schema_missing_required],
    }


@pytest.fixture
def blackboard_data_backlog_errors(valid_task_backend, invalid_backlog_id_missing):
    """Blackboard data with backlog_id validation errors."""
    return {
        "estado_actual": "iniciado",
        "tareas": [valid_task_backend, invalid_backlog_id_missing],
    }


@pytest.fixture
def blackboard_data_both_errors(
    invalid_schema_missing_required, invalid_backlog_id_missing
):
    """Blackboard data with both schema and backlog_id errors."""
    return {
        "estado_actual": "iniciado",
        "tareas": [invalid_schema_missing_required, invalid_backlog_id_missing],
    }


# ============================================================================
# Layer 1: Schema Validation Tests
# ============================================================================


class TestSchemaValidation:
    """Test validar_task_schemas() function (Layer 1)."""

    def test_valid_tasks_pass_schema_validation(
        self, valid_task_backend, valid_task_planner
    ):
        """Valid tasks should pass schema validation."""
        tareas = [valid_task_backend, valid_task_planner]
        errores = validar_task_schemas(tareas)

        assert errores == [], f"Expected no errors, got: {errores}"

    def test_missing_required_fields_fails(self, invalid_schema_missing_required):
        """Task missing required fields should fail schema validation."""
        tareas = [invalid_schema_missing_required]
        errores = validar_task_schemas(tareas)

        assert len(errores) > 0, "Expected schema validation errors"
        assert "T003" in errores[0], "Error should reference task T003"

    def test_wrong_field_type_fails(self, invalid_schema_wrong_type):
        """Task with wrong field types should fail schema validation."""
        tareas = [invalid_schema_wrong_type]
        errores = validar_task_schemas(tareas)

        assert len(errores) > 0, "Expected schema validation errors"
        assert "T004" in errores[0], "Error should reference task T004"
        # exitoso should be boolean
        assert "exitoso" in errores[0] or "boolean" in errores[0].lower()

    def test_missing_asignado_a_fails(self):
        """Task missing asignado_a field should fail."""
        tarea = {
            "tarea_id": "T999",
            "backlog_id": "TASK-TEST-999",
            "tipo": "backend",
            "descripcion": "Test",
            "estado": "pendiente",
            "resultado": {"exitoso": False, "mensaje": "Test"},
            # Missing: asignado_a
        }
        errores = validar_task_schemas([tarea])

        assert len(errores) > 0
        assert "asignado_a" in errores[0]
        assert "OBLIGATORIO" in errores[0]

    def test_invalid_role_fails(self):
        """Task with invalid role should fail."""
        tarea = {
            "tarea_id": "T998",
            "backlog_id": "TASK-TEST-998",
            "tipo": "backend",
            "descripcion": "Test",
            "asignado_a": "invalid_role",  # Invalid role
            "estado": "pendiente",
            "resultado": {"exitoso": False, "mensaje": "Test"},
        }
        errores = validar_task_schemas([tarea])

        assert len(errores) > 0
        assert "invalid_role" in errores[0]
        assert "invalido" in errores[0]

    def test_multiple_tasks_collects_all_errors(
        self, invalid_schema_missing_required, invalid_schema_wrong_type
    ):
        """Should collect errors from multiple invalid tasks."""
        tareas = [invalid_schema_missing_required, invalid_schema_wrong_type]
        errores = validar_task_schemas(tareas)

        # Should have errors from both tasks
        assert len(errores) >= 2
        task_ids = [err for err in errores if "T003" in err or "T004" in err]
        assert len(task_ids) >= 2, "Should report errors for both T003 and T004"


# ============================================================================
# Layer 2: Backlog ID Validation Tests
# ============================================================================


class TestBacklogIDValidation:
    """Test validar_backlog_ids() function (Layer 2)."""

    def test_missing_backlog_id_fails(self, invalid_backlog_id_missing):
        """Task missing backlog_id should fail."""
        tareas = [invalid_backlog_id_missing]
        errores = validar_backlog_ids(tareas)

        assert len(errores) > 0
        assert "T005" in errores[0]
        assert "backlog_id" in errores[0]

    def test_invalid_pattern_fails(self, invalid_backlog_id_wrong_pattern):
        """Task with invalid backlog_id pattern should fail."""
        tareas = [invalid_backlog_id_wrong_pattern]
        errores = validar_backlog_ids(tareas)

        assert len(errores) > 0
        assert "T006" in errores[0]
        assert "invalid-pattern" in errores[0]


# ============================================================================
# Integration Tests: guardar_blackboard() with Defense-in-Depth
# ============================================================================


class TestGuardarBlackboardIntegration:
    """Test guardar_blackboard() with 2-layer validation."""

    @patch("core.supervisor.guardar_json")
    def test_valid_data_saves_successfully(
        self, mock_guardar_json, blackboard_data_valid
    ):
        """Valid data should pass both layers and save successfully."""
        # Should not raise
        guardar_blackboard(blackboard_data_valid)

        # Should have called guardar_json to save
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert "updated_at" in saved_data

    def test_schema_errors_prevent_save(
        self, blackboard_data_schema_errors
    ):
        """Schema validation errors should prevent save (Layer 1)."""
        # Should raise ValueError with schema errors
        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard_data_schema_errors)

        error_msg = str(exc_info.value)
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg
        assert "T003" in error_msg

    def test_backlog_errors_prevent_save(
        self, blackboard_data_backlog_errors
    ):
        """Backlog ID validation errors should prevent save (Layer 2)."""
        # T005 is missing backlog_id, should fail Layer 2
        # Should raise ValueError with backlog_id errors
        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard_data_backlog_errors)

        error_msg = str(exc_info.value)
        assert "LAYER 2 - BACKLOG ID VALIDATION" in error_msg
        assert "T005" in error_msg

    def test_both_errors_collected_and_displayed(
        self, blackboard_data_both_errors
    ):
        """Should collect and display both schema and backlog_id errors."""
        # Should raise ValueError with both types of errors
        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard_data_both_errors)

        error_msg = str(exc_info.value)

        # Should show both layers
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg
        assert "LAYER 2 - BACKLOG ID VALIDATION" in error_msg

        # Should reference both tasks
        assert "T003" in error_msg
        assert "T005" in error_msg

    def test_error_message_format(
        self, blackboard_data_schema_errors
    ):
        """Error message should have correct format with reminders."""
        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard_data_schema_errors)

        error_msg = str(exc_info.value)

        # Check header
        assert "ERROR CRITICO: Validacion de Blackboard FALLO" in error_msg

        # Check reminder section
        assert "RECORDATORIO - Defense-in-Depth" in error_msg
        assert "Layer 1 - Schema Validation:" in error_msg
        assert "schemas/{role}_output.json" in error_msg
        assert "Layer 2 - Backlog ID Validation:" in error_msg
        assert "C2PRO_MASTER_BACKLOG.md" in error_msg

    @patch("core.supervisor.guardar_json")
    def test_empty_tareas_list_saves(self, mock_guardar_json):
        """Empty tareas list should save successfully (edge case)."""
        data = {"estado_actual": "iniciado", "tareas": []}

        guardar_blackboard(data)

        assert mock_guardar_json.called

    def test_role_specific_fields_validated(self):
        """Should validate role-specific fields correctly."""
        # Backend task with invalid codigo field
        tarea = {
            "tarea_id": "T010",
            "backlog_id": "TASK-TEST-010",
            "tipo": "backend",
            "descripcion": "Test backend task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
            "codigo": {
                "archivos_nuevos": "not-an-array",  # Should be array
                "lineas_agregadas": -10,  # Should be >= 0
            },
        }

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard({"estado_actual": "iniciado", "tareas": [tarea]})

        error_msg = str(exc_info.value)
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg
        # Should mention validation errors for codigo fields


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
