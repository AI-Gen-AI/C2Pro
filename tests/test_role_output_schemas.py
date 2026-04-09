"""Tests for UNIFY-011: Role output schema validation.

Tests the schema validator and all 9 role output schemas to ensure
they properly validate role outputs and extend base_output.json correctly.
"""
import pytest
from pathlib import Path
import json
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from schemas.validator import (
    validate_role_output,
    validate_role_output_raises,
    load_schema,
    load_base_schema,
    get_role_schema_path,
    list_available_schemas,
    VALID_ROLES,
)
from jsonschema import ValidationError


# ============================================================================
# Base Schema Tests
# ============================================================================


class TestBaseSchema:
    """Tests for base_output.json schema."""

    def test_base_schema_exists(self):
        """Base schema file should exist."""
        base_schema = load_base_schema()
        assert base_schema is not None
        assert "$schema" in base_schema
        assert base_schema["$schema"] == "http://json-schema.org/draft-07/schema#"

    def test_base_schema_has_required_fields(self):
        """Base schema should define all required fields."""
        base_schema = load_base_schema()
        required_fields = base_schema.get("required", [])

        expected_required = [
            "tarea_id",
            "backlog_id",
            "tipo",
            "descripcion",
            "asignado_a",
            "estado",
            "resultado",
        ]

        for field in expected_required:
            assert field in required_fields, f"Base schema missing required field: {field}"

    def test_base_schema_has_properties(self):
        """Base schema should define all required properties."""
        base_schema = load_base_schema()
        properties = base_schema.get("properties", {})

        expected_properties = [
            "tarea_id",
            "backlog_id",
            "tipo",
            "descripcion",
            "asignado_a",
            "estado",
            "resultado",
            "criterio_done",
            "archivos_afectados",
            "timestamps",
        ]

        for prop in expected_properties:
            assert prop in properties, f"Base schema missing property: {prop}"

    def test_backlog_id_pattern(self):
        """backlog_id should have correct pattern."""
        base_schema = load_base_schema()
        backlog_id_schema = base_schema["properties"]["backlog_id"]

        assert "pattern" in backlog_id_schema
        assert backlog_id_schema["pattern"] == "^TASK-[A-Z0-9-]+$"


# ============================================================================
# Role Schema Loading Tests
# ============================================================================


class TestSchemaLoading:
    """Tests for schema loading functions."""

    def test_load_all_role_schemas(self):
        """All role schemas should load successfully."""
        for role in VALID_ROLES:
            schema = load_schema(role)
            assert schema is not None
            assert "$schema" in schema

    def test_load_invalid_role_raises(self):
        """Loading invalid role should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            load_schema("invalid_role")

    def test_all_role_schemas_extend_base(self):
        """All role schemas should extend base_output.json."""
        for role in VALID_ROLES:
            schema = load_schema(role)

            # Schema should use allOf to extend base
            assert "allOf" in schema, f"{role} schema doesn't use allOf pattern"

            # First item in allOf should be $ref to base_output.json
            assert len(schema["allOf"]) >= 1
            first_item = schema["allOf"][0]
            assert "$ref" in first_item
            assert first_item["$ref"] == "base_output.json"

    def test_list_available_schemas(self):
        """list_available_schemas should return all valid roles."""
        available = list_available_schemas()

        # All VALID_ROLES should have schemas
        for role in VALID_ROLES:
            assert role in available, f"Schema not found for role: {role}"

    def test_get_role_schema_path(self):
        """get_role_schema_path should return correct path."""
        for role in VALID_ROLES:
            path = get_role_schema_path(role)
            assert path.exists(), f"Schema file not found: {path}"
            assert path.name == f"{role}_output.json"


# ============================================================================
# Validation Tests - Valid Outputs
# ============================================================================


class TestValidOutputs:
    """Tests with valid role outputs."""

    def test_valid_planner_output(self):
        """Valid planner output should pass validation."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "tipo": "planning",
            "descripcion": "Plan implementation for RLS feature",
            "asignado_a": "planner",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "Planning completed successfully",
                "cambios_realizados": ["Created implementation plan"],
            },
        }

        is_valid, errors = validate_role_output("planner", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_valid_backend_output(self):
        """Valid backend output should pass validation."""
        output = {
            "tarea_id": "T002",
            "backlog_id": "TASK-BCK-018",
            "tipo": "backend",
            "descripcion": "Implement RLS policies",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "RLS policies implemented",
                "cambios_realizados": ["Added RLS policies", "Created migration"],
            },
            "codigo": {
                "archivos_nuevos": ["alembic/versions/20260404_rls.py"],
                "archivos_modificados": ["apps/api/models/user.py"],
                "lineas_agregadas": 150,
                "lineas_eliminadas": 10,
            },
            "tests": {
                "tests_ejecutados": 25,
                "tests_pasados": 25,
                "tests_fallidos": 0,
                "cobertura": 92.5,
            },
        }

        is_valid, errors = validate_role_output("backend", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_valid_ai_output(self):
        """Valid AI output should pass validation."""
        output = {
            "tarea_id": "T003",
            "backlog_id": "TASK-AI-042",
            "tipo": "ai",
            "descripcion": "Generate documentation with LLM",
            "asignado_a": "ai",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "Documentation generated successfully",
            },
            "modelo": {
                "nombre": "gpt-4",
                "proveedor": "OpenAI",
                "version": "gpt-4-0613",
                "temperatura": 0.7,
            },
            "uso": {
                "tokens_entrada": 1500,
                "tokens_salida": 3000,
                "tokens_totales": 4500,
                "costo_usd": 0.135,
                "duracion_segundos": 12.5,
            },
            "observabilidad": {
                "langsmith_trace_url": "https://smith.langchain.com/public/trace123",
                "langsmith_run_id": "run-abc123",
                "langsmith_project": "c2pro-development",
            },
        }

        is_valid, errors = validate_role_output("ai", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_valid_qa_output(self):
        """Valid QA output should pass validation."""
        output = {
            "tarea_id": "T004",
            "backlog_id": "TASK-QA-015",
            "tipo": "qa",
            "descripcion": "Test RLS implementation",
            "asignado_a": "qa",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "All tests passed",
            },
            "tests": {
                "tests_unitarios": {
                    "ejecutados": 50,
                    "pasados": 50,
                    "fallidos": 0,
                    "cobertura": 95.0,
                },
                "tests_integracion": {
                    "ejecutados": 20,
                    "pasados": 20,
                    "fallidos": 0,
                },
            },
            "cobertura": {
                "lineas": 95.0,
                "ramas": 92.0,
                "funciones": 98.0,
            },
        }

        is_valid, errors = validate_role_output("qa", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_valid_security_output(self):
        """Valid security output should pass validation."""
        output = {
            "tarea_id": "T005",
            "backlog_id": "TASK-SEC-008",
            "tipo": "security",
            "descripcion": "Security audit of RLS implementation",
            "asignado_a": "security",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "No critical vulnerabilities found",
            },
            "analisis": {
                "tipo_analisis": ["SAST", "dependencias", "permisos"],
                "herramientas": ["bandit", "safety"],
                "archivos_analizados": ["apps/api/models/user.py"],
            },
            "vulnerabilidades": {
                "criticas": 0,
                "altas": 0,
                "medias": 1,
                "bajas": 2,
            },
        }

        is_valid, errors = validate_role_output("security", output)
        assert is_valid, f"Validation failed: {errors}"


# ============================================================================
# Validation Tests - Invalid Outputs
# ============================================================================


class TestInvalidOutputs:
    """Tests with invalid role outputs."""

    def test_missing_required_field_tarea_id(self):
        """Output missing tarea_id should fail validation."""
        output = {
            # Missing tarea_id
            "backlog_id": "TASK-1490",
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("tarea_id" in err for err in errors)

    def test_missing_required_field_backlog_id(self):
        """Output missing backlog_id should fail validation."""
        output = {
            "tarea_id": "T001",
            # Missing backlog_id
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("backlog_id" in err for err in errors)

    def test_invalid_backlog_id_pattern(self):
        """backlog_id with invalid pattern should fail."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "invalid-format",  # Doesn't match ^TASK-[A-Z0-9-]+$
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("pattern" in err.lower() or "backlog_id" in err for err in errors)

    def test_invalid_tarea_id_pattern(self):
        """tarea_id with invalid pattern should fail."""
        output = {
            "tarea_id": "invalid",  # Doesn't match ^T\\d{3,}$
            "backlog_id": "TASK-1490",
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Done"},
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("pattern" in err.lower() or "tarea_id" in err for err in errors)

    def test_invalid_estado_enum(self):
        """Invalid estado value should fail validation."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "invalid_estado",  # Not in enum
            "resultado": {"exitoso": True, "mensaje": "Done"},
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("estado" in err for err in errors)

    def test_missing_resultado_required_fields(self):
        """resultado missing required fields should fail."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                # Missing 'mensaje' (required)
            },
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("mensaje" in err for err in errors)

    def test_resultado_mensaje_too_short(self):
        """resultado.mensaje less than minLength should fail."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "tipo": "backend",
            "descripcion": "Test task",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {
                "exitoso": True,
                "mensaje": "Done",  # Less than 10 characters (minLength: 10)
            },
        }

        is_valid, errors = validate_role_output("backend", output)
        assert not is_valid
        assert any("mensaje" in err and ("length" in err.lower() or "short" in err.lower()) for err in errors)


# ============================================================================
# Role-Specific Field Tests
# ============================================================================


class TestRoleSpecificFields:
    """Tests for role-specific schema fields."""

    def test_planner_plan_field(self):
        """Planner schema should allow plan field."""
        output = {
            "tarea_id": "T001",
            "backlog_id": "TASK-1490",
            "tipo": "planning",
            "descripcion": "Plan implementation",
            "asignado_a": "planner",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Planning completed"},
            "plan": {
                "subtareas": [
                    {
                        "id": "T001-1",
                        "descripcion": "First subtask",
                        "asignado_a": "backend",
                    }
                ],
                "riesgos": [
                    {
                        "descripcion": "Potential database migration issue",
                        "severidad": "media",
                        "mitigacion": "Test on staging first",
                    }
                ],
            },
        }

        is_valid, errors = validate_role_output("planner", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_backend_tests_field(self):
        """Backend schema should allow tests field."""
        output = {
            "tarea_id": "T002",
            "backlog_id": "TASK-BCK-018",
            "tipo": "backend",
            "descripcion": "Implement feature",
            "asignado_a": "backend",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Implementation completed"},
            "tests": {
                "tests_ejecutados": 10,
                "tests_pasados": 10,
                "tests_fallidos": 0,
                "cobertura": 85.5,
            },
        }

        is_valid, errors = validate_role_output("backend", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_ai_modelo_field(self):
        """AI schema should allow modelo field."""
        output = {
            "tarea_id": "T003",
            "backlog_id": "TASK-AI-042",
            "tipo": "ai",
            "descripcion": "Generate content",
            "asignado_a": "ai",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Content generated"},
            "modelo": {
                "nombre": "claude-3-sonnet",
                "proveedor": "Anthropic",
                "temperatura": 0.7,
            },
            "uso": {
                "tokens_entrada": 500,
                "tokens_salida": 1000,
                "tokens_totales": 1500,
            },
        }

        is_valid, errors = validate_role_output("ai", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_infra_recursos_field(self):
        """Infra schema should allow recursos field."""
        output = {
            "tarea_id": "T004",
            "backlog_id": "TASK-INF-012",
            "tipo": "infra",
            "descripcion": "Provision resources",
            "asignado_a": "infra",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Resources provisioned"},
            "recursos": {
                "recursos_creados": [
                    {
                        "tipo": "EC2",
                        "nombre": "c2pro-backend-server",
                        "region": "us-east-1",
                    }
                ]
            },
        }

        is_valid, errors = validate_role_output("infra", output)
        assert is_valid, f"Validation failed: {errors}"

    def test_devops_pipeline_field(self):
        """DevOps schema should allow pipeline field."""
        output = {
            "tarea_id": "T005",
            "backlog_id": "TASK-DEV-007",
            "tipo": "devops",
            "descripcion": "Deploy to production",
            "asignado_a": "devops",
            "estado": "completado",
            "resultado": {"exitoso": True, "mensaje": "Deployed successfully"},
            "pipeline": {
                "herramienta": "github_actions",
                "jobs": [
                    {"nombre": "build", "estado": "exitoso", "duracion_segundos": 120},
                    {"nombre": "deploy", "estado": "exitoso", "duracion_segundos": 180},
                ],
            },
        }

        is_valid, errors = validate_role_output("devops", output)
        assert is_valid, f"Validation failed: {errors}"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling and validation messages."""

    def test_validate_raises_on_invalid(self):
        """validate_role_output_raises should raise on invalid data."""
        output = {
            "tarea_id": "T001",
            # Missing required fields
        }

        with pytest.raises(ValidationError):
            validate_role_output_raises("backend", output)

    def test_strict_mode_collects_all_errors(self):
        """Strict mode should collect all validation errors."""
        output = {
            # Missing multiple required fields
            "tarea_id": "invalid",  # Invalid pattern
            # Missing backlog_id, tipo, descripcion, asignado_a, estado, resultado
        }

        is_valid, errors = validate_role_output("backend", output, strict=True)
        assert not is_valid

        # Should have multiple errors (at least for missing required fields)
        assert len(errors) > 1

    def test_non_strict_mode_stops_at_first_error(self):
        """Non-strict mode should stop at first error."""
        output = {
            # Missing multiple required fields
        }

        is_valid, errors = validate_role_output("backend", output, strict=False)
        assert not is_valid

        # Should have exactly one error (stopped at first)
        assert len(errors) == 1


# ============================================================================
# Integration Tests
# ============================================================================


def test_integration_all_roles_validate():
    """Integration test: Validate a minimal valid output for each role."""
    base_output = {
        "tarea_id": "T001",
        "backlog_id": "TASK-TEST-001",
        "descripcion": "Integration test task",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Integration test completed successfully",
        },
    }

    # Map role to tipo (some differ)
    role_to_tipo = {
        "planner": "planning",
        "backend": "backend",
        "frontend": "frontend",
        "ai": "ai",
        "infra": "infra",
        "qa": "qa",
        "reviewer": "review",
        "security": "security",
        "devops": "devops",
    }

    for role in VALID_ROLES:
        # Create role-specific output
        output = base_output.copy()
        output["tipo"] = role_to_tipo[role]
        output["asignado_a"] = role

        # Validate
        is_valid, errors = validate_role_output(role, output)
        assert is_valid, f"Integration test failed for role '{role}': {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
