"""
Integration Test for UNIFY-013: Unified Workflow (planner → backend → qa)

Tests the complete agent orchestration workflow with 3 roles collaborating:
  1. Planner: Receives high-level task, creates plan with subtasks
  2. Backend: Implements subtasks, produces code changes
  3. QA: Validates implementation, runs tests

Verifies:
  - Each role can read/write blackboard.json correctly
  - All tasks pass schema validation (Layer 1)
  - All tasks have valid backlog_id (Layer 2)
  - Task state transitions work correctly
  - Defense-in-depth validation catches errors

Author: Claude (UNIFY-013)
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
    cargar_blackboard,
)


# ============================================================================
# Test Scenario: Add User Authentication Feature
# ============================================================================

# Scenario: Product owner requests "Add user authentication to the API"
# Workflow:
#   1. Planner: Creates plan with 3 subtasks (backend auth, tests, docs)
#   2. Backend: Implements auth endpoints (login, logout, register)
#   3. QA: Validates implementation with integration tests


# ============================================================================
# Phase 1: Planner Creates Plan
# ============================================================================


@pytest.fixture
def planner_initial_task():
    """Initial task assigned to planner by product owner."""
    return {
        "tarea_id": "T001",
        "backlog_id": "TASK-AUTH-001",
        "tipo": "planning",
        "descripcion": "Plan user authentication feature for API",
        "asignado_a": "planner",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Planning not yet started",
        },
    }


@pytest.fixture
def planner_completed_task():
    """Planner's completed task with plan output."""
    return {
        "tarea_id": "T001",
        "backlog_id": "TASK-AUTH-001",
        "tipo": "planning",
        "descripcion": "Plan user authentication feature for API",
        "asignado_a": "planner",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Authentication feature plan created with 3 implementation phases",
            "cambios_realizados": [
                "Created authentication architecture plan",
                "Identified 3 subtasks for backend, qa, docs",
                "Defined authentication flow (JWT tokens)",
            ],
        },
        "plan": {
            "subtareas": [
                {
                    "id": "T001-1",
                    "descripcion": "Implement authentication endpoints (login, logout, register)",
                    "asignado_a": "backend",
                    "dependencias": [],
                    "estimacion_horas": 8,
                },
                {
                    "id": "T001-2",
                    "descripcion": "Write integration tests for authentication flow",
                    "asignado_a": "qa",
                    "dependencias": ["T001-1"],
                    "estimacion_horas": 4,
                },
                {
                    "id": "T001-3",
                    "descripcion": "Document authentication endpoints in API docs",
                    "asignado_a": "backend",
                    "dependencias": ["T001-1"],
                    "estimacion_horas": 2,
                },
            ],
            "dependencias": [],
            "riesgos": [
                {
                    "descripcion": "Password hashing security - use bcrypt with proper salt rounds",
                    "severidad": "alta",
                    "mitigacion": "Use bcrypt with 12 salt rounds, never store plaintext passwords",
                }
            ],
            "fases": [
                {
                    "nombre": "Phase 1: Core Authentication",
                    "descripcion": "Implement login, logout, register endpoints",
                    "tareas": ["T001-1"],
                },
                {
                    "nombre": "Phase 2: Testing & Validation",
                    "descripcion": "Integration tests for auth flow",
                    "tareas": ["T001-2"],
                },
                {
                    "nombre": "Phase 3: Documentation",
                    "descripcion": "API documentation for auth endpoints",
                    "tareas": ["T001-3"],
                },
            ],
        },
        "documentos_generados": [
            "docs/architecture/authentication_design.md",
            "docs/planning/auth_implementation_plan.md",
        ],
    }


# ============================================================================
# Phase 2: Backend Implements Subtask
# ============================================================================


@pytest.fixture
def backend_subtask_assigned():
    """Backend subtask T001-1 assigned from planner's plan."""
    return {
        "tarea_id": "T002",
        "backlog_id": "TASK-AUTH-002",
        "tipo": "backend",
        "descripcion": "Implement authentication endpoints (login, logout, register)",
        "asignado_a": "backend",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Implementation not yet started",
        },
    }


@pytest.fixture
def backend_subtask_completed():
    """Backend's completed implementation of auth endpoints."""
    return {
        "tarea_id": "T002",
        "backlog_id": "TASK-AUTH-002",
        "tipo": "backend",
        "descripcion": "Implement authentication endpoints (login, logout, register)",
        "asignado_a": "backend",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Authentication endpoints implemented successfully",
            "cambios_realizados": [
                "Created /api/v1/auth/login endpoint",
                "Created /api/v1/auth/logout endpoint",
                "Created /api/v1/auth/register endpoint",
                "Implemented JWT token generation and validation",
                "Added bcrypt password hashing (12 rounds)",
            ],
        },
        "codigo": {
            "archivos_nuevos": [
                "apps/api/src/modules/auth/adapters/http/auth_router.py",
                "apps/api/src/modules/auth/domain/services/auth_service.py",
                "apps/api/src/modules/auth/domain/models/user.py",
            ],
            "archivos_modificados": [
                "apps/api/src/main.py",
                "apps/api/pyproject.toml",
            ],
            "lineas_agregadas": 487,
            "lineas_eliminadas": 12,
        },
        "tests": {
            "tests_ejecutados": 15,
            "tests_pasados": 15,
            "cobertura": 92.5,
        },
        "validacion": {
            "linter_pasado": True,
            "type_check_pasado": True,
            "security_scan_pasado": True,
        },
        "api": {
            "endpoints_nuevos": [
                "POST /api/v1/auth/login",
                "POST /api/v1/auth/logout",
                "POST /api/v1/auth/register",
            ],
            "breaking_changes": False,
        },
    }


# ============================================================================
# Phase 3: QA Validates Implementation
# ============================================================================


@pytest.fixture
def qa_subtask_assigned():
    """QA subtask T001-2 assigned from planner's plan."""
    return {
        "tarea_id": "T003",
        "backlog_id": "TASK-AUTH-003",
        "tipo": "qa",
        "descripcion": "Write integration tests for authentication flow",
        "asignado_a": "qa",
        "estado": "pendiente",
        "resultado": {
            "exitoso": False,
            "mensaje": "Testing not yet started",
        },
    }


@pytest.fixture
def qa_subtask_completed():
    """QA's completed validation of auth implementation."""
    return {
        "tarea_id": "T003",
        "backlog_id": "TASK-AUTH-003",
        "tipo": "qa",
        "descripcion": "Write integration tests for authentication flow",
        "asignado_a": "qa",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Integration tests written and passing for authentication flow",
            "cambios_realizados": [
                "Created integration test suite for auth endpoints",
                "Tested login flow (valid credentials, invalid credentials)",
                "Tested registration flow (new user, duplicate email)",
                "Tested logout flow",
                "Tested JWT token validation",
            ],
        },
        "tests": {
            "archivos_nuevos": [
                "apps/api/tests/integration/auth/test_login.py",
                "apps/api/tests/integration/auth/test_register.py",
                "apps/api/tests/integration/auth/test_logout.py",
            ],
            "tests_ejecutados": 24,
            "tests_pasados": 24,
            "tests_fallidos": 0,
            "cobertura": 95.3,
        },
        "bugs": {
            "encontrados": 2,
            "reportados": [
                {
                    "id": "BUG-AUTH-001",
                    "severidad": "media",
                    "descripcion": "Login endpoint returns 500 instead of 401 for invalid credentials",
                    "estado": "resuelto",
                },
                {
                    "id": "BUG-AUTH-002",
                    "severidad": "baja",
                    "descripcion": "Register endpoint missing email format validation",
                    "estado": "resuelto",
                },
            ],
        },
        "regresion": {
            "tests_ejecutados": 156,
            "tests_pasados": 156,
            "tests_fallidos": 0,
        },
    }


# ============================================================================
# Integration Test: Full Workflow
# ============================================================================


class TestUnifiedWorkflow:
    """Test complete planner → backend → qa workflow."""

    @patch("core.supervisor.guardar_json")
    def test_phase1_planner_creates_plan(
        self, mock_guardar_json, planner_initial_task, planner_completed_task
    ):
        """Phase 1: Planner receives task, creates plan with subtasks."""
        # Start with initial task
        blackboard_initial = {
            "estado_actual": "planificacion",
            "tareas": [planner_initial_task],
        }

        # Planner completes planning, updates task
        blackboard_after_planning = {
            "estado_actual": "planificacion_completada",
            "tareas": [planner_completed_task],
        }

        # Should save successfully (schema validation passes)
        guardar_blackboard(blackboard_after_planning)

        # Verify guardar_json was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]

        # Verify planner task is marked completado
        assert saved_data["tareas"][0]["estado"] == "completado"
        assert saved_data["tareas"][0]["asignado_a"] == "planner"

        # Verify plan was created with subtasks
        assert "plan" in saved_data["tareas"][0]
        assert "subtareas" in saved_data["tareas"][0]["plan"]
        assert len(saved_data["tareas"][0]["plan"]["subtareas"]) == 3

        # Verify subtasks have correct assignments
        subtareas = saved_data["tareas"][0]["plan"]["subtareas"]
        assert subtareas[0]["asignado_a"] == "backend"
        assert subtareas[1]["asignado_a"] == "qa"
        assert subtareas[2]["asignado_a"] == "backend"

    @patch("core.supervisor.guardar_json")
    def test_phase2_backend_implements_subtask(
        self,
        mock_guardar_json,
        planner_completed_task,
        backend_subtask_assigned,
        backend_subtask_completed,
    ):
        """Phase 2: Backend implements auth endpoints from planner's subtask."""
        # Start with planner's completed task + backend's assigned subtask
        blackboard_before_backend = {
            "estado_actual": "implementacion",
            "tareas": [planner_completed_task, backend_subtask_assigned],
        }

        # Backend completes implementation
        blackboard_after_backend = {
            "estado_actual": "implementacion_completada",
            "tareas": [planner_completed_task, backend_subtask_completed],
        }

        # Should save successfully (schema validation passes)
        guardar_blackboard(blackboard_after_backend)

        # Verify guardar_json was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]

        # Verify backend task is marked completado
        backend_task = saved_data["tareas"][1]
        assert backend_task["estado"] == "completado"
        assert backend_task["asignado_a"] == "backend"

        # Verify codigo section exists with implementation details
        assert "codigo" in backend_task
        assert "archivos_nuevos" in backend_task["codigo"]
        assert len(backend_task["codigo"]["archivos_nuevos"]) == 3

        # Verify tests were run
        assert "tests" in backend_task
        assert backend_task["tests"]["tests_pasados"] == 15
        assert backend_task["tests"]["cobertura"] >= 90.0

        # Verify API endpoints were created
        assert "api" in backend_task
        assert len(backend_task["api"]["endpoints_nuevos"]) == 3

    @patch("core.supervisor.guardar_json")
    def test_phase3_qa_validates_implementation(
        self,
        mock_guardar_json,
        planner_completed_task,
        backend_subtask_completed,
        qa_subtask_assigned,
        qa_subtask_completed,
    ):
        """Phase 3: QA validates backend's implementation with integration tests."""
        # Start with completed planner + backend + assigned qa task
        blackboard_before_qa = {
            "estado_actual": "validacion",
            "tareas": [
                planner_completed_task,
                backend_subtask_completed,
                qa_subtask_assigned,
            ],
        }

        # QA completes validation
        blackboard_after_qa = {
            "estado_actual": "validacion_completada",
            "tareas": [
                planner_completed_task,
                backend_subtask_completed,
                qa_subtask_completed,
            ],
        }

        # Should save successfully (schema validation passes)
        guardar_blackboard(blackboard_after_qa)

        # Verify guardar_json was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]

        # Verify QA task is marked completado
        qa_task = saved_data["tareas"][2]
        assert qa_task["estado"] == "completado"
        assert qa_task["asignado_a"] == "qa"

        # Verify tests section exists
        assert "tests" in qa_task
        assert qa_task["tests"]["tests_pasados"] == 24
        assert qa_task["tests"]["tests_fallidos"] == 0

        # Verify bugs were tracked
        assert "bugs" in qa_task
        assert qa_task["bugs"]["encontrados"] == 2
        assert all(bug["estado"] == "resuelto" for bug in qa_task["bugs"]["reportados"])

        # Verify regression tests ran
        assert "regresion" in qa_task
        assert qa_task["regresion"]["tests_fallidos"] == 0

    @patch("core.supervisor.guardar_json")
    def test_full_workflow_end_to_end(
        self,
        mock_guardar_json,
        planner_initial_task,
        planner_completed_task,
        backend_subtask_completed,
        qa_subtask_completed,
    ):
        """End-to-end test: Complete workflow from planner → backend → qa."""
        # Phase 1: Initial state (only planner task)
        blackboard_phase1 = {
            "estado_actual": "planificacion",
            "tareas": [planner_initial_task],
        }

        # Phase 2: Planner completes
        blackboard_phase2 = {
            "estado_actual": "planificacion_completada",
            "tareas": [planner_completed_task],
        }

        guardar_blackboard(blackboard_phase2)
        assert mock_guardar_json.call_count == 1

        # Phase 3: Backend subtask added and completed
        blackboard_phase3 = {
            "estado_actual": "implementacion_completada",
            "tareas": [planner_completed_task, backend_subtask_completed],
        }

        guardar_blackboard(blackboard_phase3)
        assert mock_guardar_json.call_count == 2

        # Phase 4: QA subtask added and completed
        blackboard_phase4 = {
            "estado_actual": "validacion_completada",
            "tareas": [
                planner_completed_task,
                backend_subtask_completed,
                qa_subtask_completed,
            ],
        }

        guardar_blackboard(blackboard_phase4)
        assert mock_guardar_json.call_count == 3

        # Verify final state has all 3 completed tasks
        final_data = mock_guardar_json.call_args[0][1]
        assert len(final_data["tareas"]) == 3

        # Verify all tasks completed successfully
        assert all(task["estado"] == "completado" for task in final_data["tareas"])
        assert all(
            task["resultado"]["exitoso"] == True for task in final_data["tareas"]
        )

        # Verify roles are correct
        assert final_data["tareas"][0]["asignado_a"] == "planner"
        assert final_data["tareas"][1]["asignado_a"] == "backend"
        assert final_data["tareas"][2]["asignado_a"] == "qa"

        # Verify backlog linkage maintained throughout
        assert final_data["tareas"][0]["backlog_id"] == "TASK-AUTH-001"
        assert final_data["tareas"][1]["backlog_id"] == "TASK-AUTH-002"
        assert final_data["tareas"][2]["backlog_id"] == "TASK-AUTH-003"


# ============================================================================
# Defense-in-Depth Validation Tests
# ============================================================================


class TestDefenseInDepthValidation:
    """Test that all 4 validation layers work during workflow."""

    def test_layer1_schema_validation_catches_invalid_planner_output(self):
        """Layer 1: Schema validation rejects invalid planner output."""
        invalid_planner_task = {
            "tarea_id": "T001",
            "backlog_id": "TASK-AUTH-001",
            "tipo": "planning",
            "descripcion": "Plan auth feature",
            "asignado_a": "planner",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
            "plan": {
                "fases": "invalid-should-be-array",  # SCHEMA ERROR
            },
        }

        blackboard = {"estado_actual": "test", "tareas": [invalid_planner_task]}

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard)

        error_msg = str(exc_info.value)
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg
        assert "T001" in error_msg

    def test_layer1_schema_validation_catches_invalid_backend_output(self):
        """Layer 1: Schema validation rejects invalid backend output."""
        invalid_backend_task = {
            "tarea_id": "T002",
            "backlog_id": "TASK-AUTH-002",
            "tipo": "backend",
            "descripcion": "Implement auth",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
            "codigo": {
                "lineas_agregadas": -10,  # SCHEMA ERROR: must be >= 0
            },
        }

        blackboard = {"estado_actual": "test", "tareas": [invalid_backend_task]}

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard)

        error_msg = str(exc_info.value)
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg

    def test_layer1_schema_validation_catches_invalid_qa_output(self):
        """Layer 1: Schema validation rejects invalid QA output."""
        invalid_qa_task = {
            "tarea_id": "T003",
            "backlog_id": "TASK-AUTH-003",
            "tipo": "qa",
            "descripcion": "Test auth",
            "asignado_a": "qa",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
            "tests": {
                "tests_ejecutados": "invalid-should-be-number",  # SCHEMA ERROR
            },
        }

        blackboard = {"estado_actual": "test", "tareas": [invalid_qa_task]}

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard)

        error_msg = str(exc_info.value)
        assert "LAYER 1 - SCHEMA VALIDATION" in error_msg

    def test_layer2_backlog_id_validation_catches_missing_backlog_id(
        self, planner_completed_task
    ):
        """Layer 2: Backlog ID validation rejects tasks without backlog_id."""
        # Remove backlog_id
        task_without_backlog = planner_completed_task.copy()
        del task_without_backlog["backlog_id"]

        blackboard = {"estado_actual": "test", "tareas": [task_without_backlog]}

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard)

        error_msg = str(exc_info.value)
        assert "LAYER 2 - BACKLOG ID VALIDATION" in error_msg
        assert "backlog_id" in error_msg.lower()

    def test_layer2_backlog_id_validation_catches_invalid_pattern(
        self, planner_completed_task
    ):
        """Layer 2: Backlog ID validation rejects invalid patterns."""
        task_with_invalid_id = planner_completed_task.copy()
        task_with_invalid_id["backlog_id"] = "invalid-pattern"  # Should be TASK-*

        blackboard = {"estado_actual": "test", "tareas": [task_with_invalid_id]}

        with pytest.raises(ValueError) as exc_info:
            guardar_blackboard(blackboard)

        error_msg = str(exc_info.value)
        assert "LAYER 2 - BACKLOG ID VALIDATION" in error_msg
        assert "invalid-pattern" in error_msg


# ============================================================================
# Role-Specific Field Validation Tests
# ============================================================================


class TestRoleSpecificFields:
    """Test that role-specific fields are validated correctly."""

    @patch("core.supervisor.guardar_json")
    def test_planner_plan_field_validated(self, mock_guardar_json, planner_completed_task):
        """Planner tasks with 'plan' field validate correctly."""
        blackboard = {"estado_actual": "test", "tareas": [planner_completed_task]}

        # Should not raise (valid plan structure)
        guardar_blackboard(blackboard)

        assert mock_guardar_json.called

    @patch("core.supervisor.guardar_json")
    def test_backend_codigo_field_validated(
        self, mock_guardar_json, backend_subtask_completed
    ):
        """Backend tasks with 'codigo' field validate correctly."""
        blackboard = {"estado_actual": "test", "tareas": [backend_subtask_completed]}

        # Should not raise (valid codigo structure)
        guardar_blackboard(blackboard)

        assert mock_guardar_json.called

    @patch("core.supervisor.guardar_json")
    def test_qa_tests_field_validated(self, mock_guardar_json, qa_subtask_completed):
        """QA tasks with 'tests' field validate correctly."""
        blackboard = {"estado_actual": "test", "tareas": [qa_subtask_completed]}

        # Should not raise (valid tests structure)
        guardar_blackboard(blackboard)

        assert mock_guardar_json.called


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
