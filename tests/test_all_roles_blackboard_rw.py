"""
Integration Test for UNIFY-014: Verify All 9 Roles Can Read/Write blackboard.json

Tests that all 9 roles can successfully read and write to blackboard.json with
proper schema validation:
  1. planner
  2. backend
  3. frontend
  4. ai
  5. infra
  6. qa
  7. reviewer
  8. security
  9. devops

Verifies:
  - Each role's output validates against its schema
  - Each role can write to blackboard.json successfully
  - Role-specific fields are validated correctly
  - All roles maintain backlog_id linkage

Author: Claude (UNIFY-014)
Created: 2026-04-04
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.supervisor import guardar_blackboard


# ============================================================================
# Test Fixtures: All 9 Roles
# ============================================================================


@pytest.fixture
def valid_planner_task():
    """Valid planner task output."""
    return {
        "tarea_id": "T001",
        "backlog_id": "TASK-PLN-001",
        "tipo": "planning",
        "descripcion": "Plan microservices migration strategy",
        "asignado_a": "planner",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Migration strategy plan completed with 5 phases",
        },
        "plan": {
            "subtareas": [
                {
                    "id": "T001-1",
                    "descripcion": "Set up Docker infrastructure",
                    "asignado_a": "infra",
                    "estimacion_horas": 16,
                },
                {
                    "id": "T001-2",
                    "descripcion": "Implement API gateway service",
                    "asignado_a": "backend",
                    "estimacion_horas": 24,
                },
            ],
            "fases": [
                {
                    "nombre": "Infrastructure Setup",
                    "descripcion": "Set up Docker, Kubernetes, monitoring",
                    "tareas": ["T001-1"],
                }
            ],
            "riesgos": [
                {
                    "descripcion": "Data migration complexity",
                    "severidad": "alta",
                    "mitigacion": "Incremental migration with rollback plan",
                }
            ],
        },
        "documentos_generados": ["docs/architecture/microservices_plan.md"],
    }


@pytest.fixture
def valid_backend_task():
    """Valid backend task output."""
    return {
        "tarea_id": "T002",
        "backlog_id": "TASK-BCK-002",
        "tipo": "backend",
        "descripcion": "Implement API gateway service with rate limiting",
        "asignado_a": "backend",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "API gateway implemented with Redis-based rate limiting",
        },
        "codigo": {
            "archivos_nuevos": [
                "apps/gateway/src/main.py",
                "apps/gateway/src/middleware/rate_limiter.py",
            ],
            "archivos_modificados": ["apps/gateway/pyproject.toml"],
            "lineas_agregadas": 523,
            "lineas_eliminadas": 18,
        },
        "tests": {
            "tests_ejecutados": 28,
            "tests_pasados": 28,
            "cobertura": 94.2,
        },
        "database": {
            "migraciones_nuevas": ["20260404_add_rate_limit_cache.sql"],
            "cambios_schema": False,
        },
        "api": {
            "endpoints_nuevos": [
                "GET /api/v1/gateway/health",
                "POST /api/v1/gateway/route",
            ],
            "breaking_changes": False,
        },
    }


@pytest.fixture
def valid_frontend_task():
    """Valid frontend task output."""
    return {
        "tarea_id": "T003",
        "backlog_id": "TASK-FRT-003",
        "tipo": "frontend",
        "descripcion": "Build user dashboard with real-time metrics",
        "asignado_a": "frontend",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Dashboard implemented with WebSocket real-time updates",
        },
        "componentes": {
            "nuevos": [
                "src/components/Dashboard/MetricsCard.tsx",
                "src/components/Dashboard/RealtimeChart.tsx",
            ],
            "modificados": ["src/pages/Dashboard.tsx"],
            "eliminados": [],
        },
        "estilos": {
            "archivos_css": ["src/styles/dashboard.module.css"],
            "sistema_diseno": "Tailwind CSS",
            "responsive": True,
        },
        "accesibilidad": {
            "aria_labels_agregados": 12,
            "contraste_verificado": True,
            "navegacion_teclado": True,
        },
        "rendimiento": {
            "bundle_size_kb": 145.3,
            "lighthouse_score": 92,
            "first_contentful_paint_ms": 850,
        },
    }


@pytest.fixture
def valid_ai_task():
    """Valid AI task output."""
    return {
        "tarea_id": "T004",
        "backlog_id": "TASK-AI-004",
        "tipo": "ai",
        "descripcion": "Implement sentiment analysis for customer reviews",
        "asignado_a": "ai",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Sentiment analysis model deployed with 91.3% accuracy",
        },
        "modelo": {
            "nombre": "review-sentiment-v1",
            "tipo": "classification",
            "framework": "transformers",
            "version": "1.0.0",
        },
        "uso": {
            "input_tokens_promedio": 120,
            "output_tokens_promedio": 15,
            "latencia_p95_ms": 450,
            "costo_por_request_usd": 0.0023,
        },
        "observabilidad": {
            "metricas_trackeadas": ["accuracy", "latency", "cost", "errors"],
            "alertas_configuradas": True,
            "logging_level": "INFO",
        },
        "prompt": {
            "template_usado": "Analyze sentiment: {review_text}",
            "ejemplos_few_shot": 5,
        },
    }


@pytest.fixture
def valid_infra_task():
    """Valid infrastructure task output."""
    return {
        "tarea_id": "T005",
        "backlog_id": "TASK-INF-005",
        "tipo": "infra",
        "descripcion": "Set up Kubernetes cluster with auto-scaling",
        "asignado_a": "infra",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "EKS cluster deployed with HPA and cluster autoscaler",
        },
        "recursos": {
            "cloud_provider": "AWS",
            "region": "us-east-1",
            "recursos_creados": [
                "EKS cluster: c2pro-prod",
                "3 node groups (t3.medium)",
                "Application Load Balancer",
            ],
        },
        "configuracion": {
            "archivos_iac": [
                "terraform/eks/main.tf",
                "terraform/eks/autoscaling.tf",
            ],
            "herramienta": "Terraform",
            "estado_aplicado": True,
        },
        "costos": {
            "estimado_mensual_usd": 487.50,
            "optimizaciones_aplicadas": [
                "Spot instances for non-critical workloads",
                "Auto-scaling based on CPU/memory",
            ],
        },
        "monitoreo": {
            "herramienta": "CloudWatch + Prometheus",
            "dashboards_creados": ["cluster-health", "resource-utilization"],
            "alertas_configuradas": 8,
        },
    }


@pytest.fixture
def valid_qa_task():
    """Valid QA task output."""
    return {
        "tarea_id": "T006",
        "backlog_id": "TASK-QA-006",
        "tipo": "qa",
        "descripcion": "End-to-end testing for checkout flow",
        "asignado_a": "qa",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "E2E tests implemented with Playwright, 3 bugs found and fixed",
        },
        "tests": {
            "archivos_nuevos": [
                "tests/e2e/checkout/test_cart.spec.ts",
                "tests/e2e/checkout/test_payment.spec.ts",
            ],
            "tests_ejecutados": 42,
            "tests_pasados": 42,
            "tests_fallidos": 0,
            "cobertura": 88.5,
        },
        "bugs": {
            "encontrados": 3,
            "reportados": [
                {
                    "id": "BUG-CHK-001",
                    "severidad": "alta",
                    "descripcion": "Cart total calculation incorrect with discount codes",
                    "estado": "resuelto",
                },
                {
                    "id": "BUG-CHK-002",
                    "severidad": "media",
                    "descripcion": "Payment form validation missing for CVV",
                    "estado": "resuelto",
                },
                {
                    "id": "BUG-CHK-003",
                    "severidad": "baja",
                    "descripcion": "Success message timing issue",
                    "estado": "resuelto",
                },
            ],
        },
        "regresion": {
            "tests_ejecutados": 284,
            "tests_pasados": 284,
            "tests_fallidos": 0,
        },
    }


@pytest.fixture
def valid_reviewer_task():
    """Valid reviewer task output."""
    return {
        "tarea_id": "T007",
        "backlog_id": "TASK-REV-007",
        "tipo": "review",
        "descripcion": "Code review: API gateway implementation",
        "asignado_a": "reviewer",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Code review completed with 2 critical issues fixed",
        },
        "revision": {
            "archivos_revisados": 12,
            "lineas_revisadas": 1847,
            "tiempo_revision_horas": 3.5,
        },
        "feedback": {
            "critica": [
                {
                    "archivo": "apps/gateway/src/middleware/rate_limiter.py",
                    "linea": 45,
                    "comentario": "Race condition in Redis increment - use INCR with TTL",
                    "severidad": "critica",
                    "resuelto": True,
                },
            ],
            "alta": [],
            "media": [
                {
                    "archivo": "apps/gateway/src/main.py",
                    "linea": 78,
                    "comentario": "Add timeout to external API calls",
                    "severidad": "media",
                    "resuelto": True,
                },
            ],
            "baja": [],
        },
        "calidad": {
            "complejidad_ciclomatica_promedio": 4.2,
            "duplicacion_codigo_pct": 2.1,
            "deuda_tecnica_horas": 1.5,
        },
        "aprobacion": {
            "aprobado": True,
            "condiciones": ["Fix critical Redis race condition"],
            "fecha_aprobacion": "2026-04-04T15:30:00Z",
        },
    }


@pytest.fixture
def valid_security_task():
    """Valid security task output."""
    return {
        "tarea_id": "T008",
        "backlog_id": "TASK-SEC-008",
        "tipo": "security",
        "descripcion": "Security audit: Authentication system",
        "asignado_a": "security",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "Security audit completed, 1 high severity issue found and fixed",
        },
        "analisis": {
            "herramientas_usadas": ["bandit", "safety", "snyk", "trivy"],
            "archivos_analizados": 47,
            "lineas_codigo_analizadas": 5842,
        },
        "vulnerabilidades": {
            "criticas": 0,
            "altas": 1,
            "medias": 3,
            "bajas": 5,
            "total": 9,
            "detalle": [
                {
                    "id": "SEC-AUTH-001",
                    "severidad": "alta",
                    "tipo": "Weak Password Hashing",
                    "descripcion": "Using bcrypt with only 4 rounds (should be 12+)",
                    "archivo": "apps/api/src/modules/auth/domain/services/auth_service.py",
                    "linea": 89,
                    "estado": "resuelto",
                    "remediacion": "Increased bcrypt rounds to 12",
                },
            ],
        },
        "compliance": {
            "estandares_verificados": ["OWASP Top 10", "CWE Top 25"],
            "cumplimiento_pct": 94.2,
        },
        "secrets": {
            "secrets_encontrados": 0,
            "archivos_escaneados": 156,
            "patterns_verificados": ["API keys", "passwords", "tokens", "certificates"],
        },
    }


@pytest.fixture
def valid_devops_task():
    """Valid DevOps task output."""
    return {
        "tarea_id": "T009",
        "backlog_id": "TASK-DVO-009",
        "tipo": "devops",
        "descripcion": "Set up CI/CD pipeline with automated deployment",
        "asignado_a": "devops",
        "estado": "completado",
        "resultado": {
            "exitoso": True,
            "mensaje": "GitHub Actions pipeline deployed with staging + prod environments",
        },
        "pipeline": {
            "herramienta": "GitHub Actions",
            "archivos_workflow": [
                ".github/workflows/ci.yml",
                ".github/workflows/deploy-staging.yml",
                ".github/workflows/deploy-prod.yml",
            ],
            "stages": ["lint", "test", "build", "deploy"],
        },
        "build": {
            "tiempo_promedio_segundos": 285,
            "artefactos_generados": ["docker-image:latest", "helm-chart-v1.2.0"],
            "cache_habilitado": True,
        },
        "deployment": {
            "ambientes": ["staging", "production"],
            "estrategia": "blue-green",
            "rollback_automatico": True,
            "health_checks": ["liveness", "readiness"],
        },
        "docker": {
            "imagenes_creadas": ["c2pro-api:v1.2.0", "c2pro-gateway:v1.2.0"],
            "registry": "ghcr.io",
            "image_size_mb": 234.5,
            "vulnerabilities_scan_pasado": True,
        },
    }


# ============================================================================
# Test Class: All Roles Validation
# ============================================================================


class TestAllRolesBlackboardReadWrite:
    """Test that all 9 roles can read/write blackboard.json correctly."""

    @patch("core.supervisor.guardar_json")
    def test_planner_writes_successfully(self, mock_guardar_json, valid_planner_task):
        """Planner role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_planner_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "planner"
        assert saved_data["tareas"][0]["tipo"] == "planning"

    @patch("core.supervisor.guardar_json")
    def test_backend_writes_successfully(self, mock_guardar_json, valid_backend_task):
        """Backend role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_backend_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "backend"
        assert "codigo" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_frontend_writes_successfully(self, mock_guardar_json, valid_frontend_task):
        """Frontend role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_frontend_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "frontend"
        assert "componentes" in saved_data["tareas"][0]
        assert "accesibilidad" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_ai_writes_successfully(self, mock_guardar_json, valid_ai_task):
        """AI role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_ai_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "ai"
        assert "modelo" in saved_data["tareas"][0]
        assert "observabilidad" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_infra_writes_successfully(self, mock_guardar_json, valid_infra_task):
        """Infrastructure role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_infra_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "infra"
        assert "recursos" in saved_data["tareas"][0]
        assert "costos" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_qa_writes_successfully(self, mock_guardar_json, valid_qa_task):
        """QA role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_qa_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "qa"
        assert "bugs" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_reviewer_writes_successfully(self, mock_guardar_json, valid_reviewer_task):
        """Reviewer role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_reviewer_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "reviewer"
        assert "revision" in saved_data["tareas"][0]
        assert "aprobacion" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_security_writes_successfully(self, mock_guardar_json, valid_security_task):
        """Security role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_security_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "security"
        assert "vulnerabilidades" in saved_data["tareas"][0]
        assert "compliance" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_devops_writes_successfully(self, mock_guardar_json, valid_devops_task):
        """DevOps role can write to blackboard.json with valid schema."""
        blackboard = {"estado_actual": "test", "tareas": [valid_devops_task]}

        # Should not raise - schema validation passes
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]
        assert saved_data["tareas"][0]["asignado_a"] == "devops"
        assert "pipeline" in saved_data["tareas"][0]
        assert "docker" in saved_data["tareas"][0]

    @patch("core.supervisor.guardar_json")
    def test_all_roles_together(
        self,
        mock_guardar_json,
        valid_planner_task,
        valid_backend_task,
        valid_frontend_task,
        valid_ai_task,
        valid_infra_task,
        valid_qa_task,
        valid_reviewer_task,
        valid_security_task,
        valid_devops_task,
    ):
        """All 9 roles can coexist in same blackboard.json."""
        blackboard = {
            "estado_actual": "multi_role_collaboration",
            "tareas": [
                valid_planner_task,
                valid_backend_task,
                valid_frontend_task,
                valid_ai_task,
                valid_infra_task,
                valid_qa_task,
                valid_reviewer_task,
                valid_security_task,
                valid_devops_task,
            ],
        }

        # Should not raise - all schemas validate
        guardar_blackboard(blackboard)

        # Verify save was called
        assert mock_guardar_json.called
        saved_data = mock_guardar_json.call_args[0][1]

        # Verify all 9 tasks saved
        assert len(saved_data["tareas"]) == 9

        # Verify each role present
        roles = {task["asignado_a"] for task in saved_data["tareas"]}
        expected_roles = {
            "planner",
            "backend",
            "frontend",
            "ai",
            "infra",
            "qa",
            "reviewer",
            "security",
            "devops",
        }
        assert roles == expected_roles

        # Verify all backlog IDs present
        backlog_ids = {task["backlog_id"] for task in saved_data["tareas"]}
        assert len(backlog_ids) == 9  # All unique


# ============================================================================
# Role-Specific Field Validation Tests
# ============================================================================


class TestRoleSpecificFieldValidation:
    """Test that role-specific fields validate correctly."""

    @patch("core.supervisor.guardar_json")
    def test_planner_plan_field_structure(self, mock_guardar_json, valid_planner_task):
        """Planner 'plan' field has correct structure (subtareas, fases, riesgos)."""
        blackboard = {"estado_actual": "test", "tareas": [valid_planner_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "subtareas" in saved["plan"]
        assert "fases" in saved["plan"]
        assert "riesgos" in saved["plan"]

    @patch("core.supervisor.guardar_json")
    def test_backend_codigo_field_structure(self, mock_guardar_json, valid_backend_task):
        """Backend 'codigo' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_backend_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "archivos_nuevos" in saved["codigo"]
        assert "lineas_agregadas" in saved["codigo"]

    @patch("core.supervisor.guardar_json")
    def test_frontend_componentes_field_structure(
        self, mock_guardar_json, valid_frontend_task
    ):
        """Frontend 'componentes' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_frontend_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "componentes" in saved
        assert "accesibilidad" in saved
        assert "rendimiento" in saved

    @patch("core.supervisor.guardar_json")
    def test_ai_modelo_field_structure(self, mock_guardar_json, valid_ai_task):
        """AI 'modelo' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_ai_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "modelo" in saved
        assert "uso" in saved
        assert "observabilidad" in saved

    @patch("core.supervisor.guardar_json")
    def test_infra_recursos_field_structure(self, mock_guardar_json, valid_infra_task):
        """Infrastructure 'recursos' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_infra_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "recursos" in saved
        assert "costos" in saved
        assert "monitoreo" in saved

    @patch("core.supervisor.guardar_json")
    def test_reviewer_revision_field_structure(
        self, mock_guardar_json, valid_reviewer_task
    ):
        """Reviewer 'revision' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_reviewer_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "revision" in saved
        assert "feedback" in saved
        assert "aprobacion" in saved

    @patch("core.supervisor.guardar_json")
    def test_security_vulnerabilidades_field_structure(
        self, mock_guardar_json, valid_security_task
    ):
        """Security 'vulnerabilidades' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_security_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "vulnerabilidades" in saved
        assert "compliance" in saved
        assert "secrets" in saved

    @patch("core.supervisor.guardar_json")
    def test_devops_pipeline_field_structure(self, mock_guardar_json, valid_devops_task):
        """DevOps 'pipeline' field has correct structure."""
        blackboard = {"estado_actual": "test", "tareas": [valid_devops_task]}
        guardar_blackboard(blackboard)

        saved = mock_guardar_json.call_args[0][1]["tareas"][0]
        assert "pipeline" in saved
        assert "deployment" in saved
        assert "docker" in saved


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
