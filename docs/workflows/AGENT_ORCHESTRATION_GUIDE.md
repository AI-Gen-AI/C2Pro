# Agent Orchestration Guide

**Version**: 1.0.0
**Last Updated**: 2026-04-04
**Status**: Production-Ready ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [The 9 Agent Roles](#the-9-agent-roles)
4. [Blackboard.json Structure](#blackboardjson-structure)
5. [Defense-in-Depth Validation](#defense-in-depth-validation)
6. [Multi-Role Collaboration Patterns](#multi-role-collaboration-patterns)
7. [Common Workflow Scenarios](#common-workflow-scenarios)
8. [Schema Reference](#schema-reference)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Quick Reference](#quick-reference)

---

## Overview

The C2PRO Agent Orchestration System is a **role-based, multi-agent architecture** that coordinates specialized AI agents to collaboratively complete complex software development tasks. The system uses a unified **blackboard.json** structure for ephemeral session state management and enforces complete traceability through mandatory **backlog_id** linking.

### Key Principles

1. **Role-Based Architecture**: 9 specialized roles (planner, backend, frontend, ai, infra, qa, reviewer, security, devops)
2. **Unified State Management**: Single `blackboard.json` file for all agent collaboration
3. **Defense-in-Depth Validation**: 4-layer validation strategy ensures data integrity
4. **Complete Traceability**: Mandatory `backlog_id` linking between ephemeral tasks and permanent backlog
5. **Schema-Driven**: JSON Schema Draft-07 validation for all role outputs

### System Components

```
C2PRO Agent Orchestration System
│
├── blackboard.json          # Ephemeral session state (shared by all agents)
├── C2PRO_MASTER_BACKLOG.md  # Permanent task register (source of truth)
├── backlogs/*.md            # Category-specific backlogs (domain segregation)
├── schemas/*.json           # Role output schemas (validation rules)
├── roles/*.md               # Role profiles (agent instructions)
└── core/supervisor.py       # Orchestration engine (task execution + validation)
```

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Request                                 │
│           "Add user authentication to API"                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  core/supervisor.py                              │
│  • Creates task with unique backlog_id (TASK-AUTH-001)          │
│  • Validates backlog_id exists in backlog files                  │
│  • Assigns task to appropriate role (planner)                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  blackboard.json                                 │
│  {                                                               │
│    "estado_actual": "planificacion",                            │
│    "tareas": [                                                   │
│      {                                                           │
│        "tarea_id": "T001",                                       │
│        "backlog_id": "TASK-AUTH-001",  ← Mandatory link         │
│        "tipo": "planning",                                       │
│        "asignado_a": "planner",                                  │
│        "estado": "pendiente"                                     │
│      }                                                           │
│    ]                                                             │
│  }                                                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│             Agent Execution (Planner)                            │
│  • Reads task from blackboard.json                               │
│  • Creates implementation plan with subtasks                     │
│  • Writes output back to blackboard.json                         │
│  • Updates backlog_id status in permanent backlog                │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          Defense-in-Depth Validation                             │
│  Layer 1: Schema Validation (schemas/{role}_output.json)         │
│  Layer 2: Runtime Validation (backlog_id pattern check)          │
│  Layer 3: Pre-Exec Validation (backlog_id exists in files)       │
│  Layer 4: Post-Exec Validation (backlog updated after completion)│
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          Subtasks Created & Assigned                             │
│  • Backend: Implement auth endpoints → TASK-AUTH-001-SUB1       │
│  • QA: Write integration tests → TASK-AUTH-001-SUB2             │
│  • DevOps: Update CI/CD pipeline → TASK-AUTH-001-SUB3           │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Permanent       │      │  Ephemeral       │      │  Role Output     │
│  Backlog         │◄────►│  Blackboard      │◄────►│  Schemas         │
│                  │ sync │                  │ valid│                  │
│ TASK-XXX-YYY     │      │ tarea_id: T001   │      │ planner.json     │
│ [x] Completed    │      │ backlog_id: ...  │      │ backend.json     │
│ [ ] Pending      │      │ estado: ...      │      │ frontend.json    │
└──────────────────┘      └──────────────────┘      └──────────────────┘
         ▲                         ▲                         ▲
         │                         │                         │
         │                  ┌──────┴──────┐                  │
         │                  │             │                  │
         └──────────────────┤ supervisor  │──────────────────┘
                            │             │
                            └──────┬──────┘
                                   │
                            ┌──────▼──────┐
                            │  4-Layer    │
                            │  Validation │
                            └─────────────┘
```

---

## The 9 Agent Roles

### 1. Planner (`role_planner.md`)

**Responsibility**: Strategic planning and task decomposition

**When to Use**:
- Breaking down large features into implementable subtasks
- Creating project roadmaps and migration plans
- Risk analysis and dependency mapping
- Resource estimation and timeline planning

**Key Outputs**:
- `plan.subtareas`: Array of implementation subtasks with assignments
- `plan.fases`: Execution phases with task groupings
- `plan.riesgos`: Risk assessment with mitigation strategies
- `plan.estimacion_total_horas`: Aggregate time estimation

**Example Task**:
```json
{
  "tarea_id": "T001",
  "backlog_id": "TASK-PLAN-001",
  "tipo": "planning",
  "asignado_a": "planner",
  "estado": "completado",
  "plan": {
    "subtareas": [
      {
        "id": "T001-1",
        "descripcion": "Implement user authentication endpoints",
        "asignado_a": "backend",
        "estimacion_horas": 8
      }
    ],
    "fases": [
      {
        "nombre": "Phase 1: Core Authentication",
        "descripcion": "Implement login, logout, register endpoints",
        "tareas": ["T001-1"]
      }
    ]
  }
}
```

**Schema**: `schemas/planner_output.json`

---

### 2. Backend (`role_backend.md`)

**Responsibility**: API and server-side implementation

**When to Use**:

- Building REST/GraphQL APIs
- Database schema design and migrations
- Business logic implementation
- Server-side data processing

**Key Outputs**:

- `codigo.archivos_modificados`: List of modified source files
- `codigo.dependencias_nuevas`: New package dependencies added
- `codigo.tests_unitarios`: Unit test coverage
- `codigo.api.endpoints`: API endpoint specifications

**Example Task**:

```json
{
  "tarea_id": "T002",
  "backlog_id": "TASK-BCK-002",
  "tipo": "backend",
  "asignado_a": "backend",
  "estado": "completado",
  "codigo": {
    "archivos_modificados": [
      "src/auth/endpoints.py",
      "src/auth/models.py",
      "tests/test_auth.py"
    ],
    "dependencias_nuevas": ["pyjwt==2.8.0", "bcrypt==4.1.2"],
    "tests_unitarios": {
      "total": 24,
      "pasados": 24,
      "cobertura_pct": 94.5
    },
    "api": {
      "endpoints": [
        {
          "path": "/api/auth/login",
          "method": "POST",
          "descripcion": "Authenticate user and return JWT token"
        }
      ]
    }
  }
}
```

**Schema**: `schemas/backend_output.json`

---

### 3. Frontend (`role_frontend.md`)

**Responsibility**: UI/UX component development

**When to Use**:

- Building React/Vue/Angular components
- Implementing responsive layouts
- Creating interactive user experiences
- State management and data binding

**Key Outputs**:
- `componentes.jerarquia`: Component tree structure
- `componentes.estado_compartido`: Global state stores
- `componentes.accesibilidad`: WCAG compliance details
- `componentes.rendimiento`: Performance metrics

**Example Task**:
```json
{
  "tarea_id": "T003",
  "backlog_id": "TASK-FRT-003",
  "tipo": "frontend",
  "asignado_a": "frontend",
  "estado": "completado",
  "componentes": {
    "jerarquia": [
      {
        "nombre": "LoginForm",
        "ruta": "src/components/auth/LoginForm.tsx",
        "hijos": ["EmailInput", "PasswordInput", "SubmitButton"]
      }
    ],
    "estado_compartido": [
      {
        "nombre": "authStore",
        "tipo": "zustand",
        "campos": ["user", "token", "isAuthenticated"]
      }
    ],
    "accesibilidad": {
      "wcag_nivel": "AA",
      "aria_labels": true,
      "keyboard_navigation": true
    }
  }
}
```

**Schema**: `schemas/frontend_output.json`

---

### 4. AI (`role_ai.md`)

**Responsibility**: AI/ML model development and deployment

**When to Use**:
- Training machine learning models
- Deploying AI services (LLMs, embeddings, classification)
- Optimizing model performance
- Implementing AI-powered features

**Key Outputs**:
- `modelo.nombre`: Model identifier
- `modelo.framework`: ML framework used (transformers, tensorflow, pytorch)
- `uso.latencia_p95_ms`: 95th percentile latency
- `uso.costo_por_request_usd`: Cost per inference
- `observabilidad.metricas_trackeadas`: Monitored metrics

**Example Task**:
```json
{
  "tarea_id": "T004",
  "backlog_id": "TASK-AI-004",
  "tipo": "ai",
  "asignado_a": "ai",
  "estado": "completado",
  "modelo": {
    "nombre": "sentiment-analyzer-v1",
    "tipo": "classification",
    "framework": "transformers",
    "version": "1.0.0"
  },
  "uso": {
    "input_tokens_promedio": 120,
    "output_tokens_promedio": 15,
    "latencia_p95_ms": 450,
    "costo_por_request_usd": 0.0023
  },
  "observabilidad": {
    "metricas_trackeadas": ["accuracy", "latency", "cost", "errors"],
    "alertas_configuradas": true
  }
}
```

**Schema**: `schemas/ai_output.json`

---

### 5. Infra (`role_infra.md`)

**Responsibility**: Infrastructure provisioning and configuration

**When to Use**:
- Provisioning cloud resources (AWS, GCP, Azure)
- Setting up Kubernetes clusters
- Configuring databases and caches
- Managing infrastructure as code

**Key Outputs**:
- `recursos.provisionados`: List of provisioned resources
- `recursos.configuracion`: Configuration details
- `recursos.costos`: Cost estimation
- `recursos.monitoreo`: Monitoring setup

**Example Task**:
```json
{
  "tarea_id": "T005",
  "backlog_id": "TASK-INF-005",
  "tipo": "infra",
  "asignado_a": "infra",
  "estado": "completado",
  "recursos": {
    "provisionados": [
      {
        "tipo": "kubernetes_cluster",
        "nombre": "c2pro-prod-eks",
        "proveedor": "AWS EKS",
        "configuracion": {
          "region": "us-east-1",
          "node_count": 3,
          "instance_type": "t3.medium",
          "auto_scaling": {"min": 3, "max": 10}
        }
      }
    ],
    "costos": {
      "estimacion_mensual_usd": 450.00,
      "breakdown": [
        {"servicio": "EKS cluster", "costo": 73.00},
        {"servicio": "EC2 instances (3x t3.medium)", "costo": 377.00}
      ]
    }
  }
}
```

**Schema**: `schemas/infra_output.json`

---

### 6. QA (`role_qa.md`)

**Responsibility**: Quality assurance and testing

**When to Use**:
- Writing unit, integration, and E2E tests
- Validating feature implementations
- Finding and reporting bugs
- Measuring test coverage

**Key Outputs**:
- `casos_prueba.total`: Total test count
- `casos_prueba.pasados`: Passing test count
- `casos_prueba.detalle`: Individual test results
- `bugs.encontrados`: Bugs discovered during testing

**Example Task**:
```json
{
  "tarea_id": "T006",
  "backlog_id": "TASK-QA-006",
  "tipo": "qa",
  "asignado_a": "qa",
  "estado": "completado",
  "casos_prueba": {
    "total": 24,
    "pasados": 22,
    "fallados": 2,
    "detalle": [
      {
        "nombre": "test_login_valid_credentials",
        "resultado": "pasado",
        "duracion_ms": 145
      },
      {
        "nombre": "test_login_invalid_password",
        "resultado": "fallado",
        "error": "Expected 401, got 500",
        "duracion_ms": 98
      }
    ]
  },
  "bugs": {
    "encontrados": 2,
    "criticos": 0,
    "altos": 1,
    "medios": 1
  }
}
```

**Schema**: `schemas/qa_output.json`

---

### 7. Reviewer (`role_reviewer.md`)

**Responsibility**: Code review and quality feedback

**When to Use**:
- Reviewing code changes before merge
- Providing architectural feedback
- Ensuring code quality standards
- Identifying potential issues

**Key Outputs**:
- `revision.issues`: Array of identified issues
- `revision.archivos_revisados`: Files reviewed
- `revision.aprobacion`: Approval decision
- `revision.metricas.calidad_codigo`: Code quality score

**Example Task**:
```json
{
  "tarea_id": "T007",
  "backlog_id": "TASK-REV-007",
  "tipo": "reviewer",
  "asignado_a": "reviewer",
  "estado": "completado",
  "revision": {
    "issues": [
      {
        "id": "REV-001",
        "severidad": "critica",
        "tipo": "Security",
        "descripcion": "Passwords logged in plain text on line 42",
        "archivo": "src/auth/login.py",
        "linea": 42,
        "recomendacion": "Remove password from log statement"
      }
    ],
    "archivos_revisados": 4,
    "aprobacion": {
      "decision": "cambios_requeridos",
      "razon": "Critical security issue must be fixed before merge"
    },
    "metricas": {
      "calidad_codigo": 7.5,
      "complejidad_ciclomatica": 8
    }
  }
}
```

**Schema**: `schemas/reviewer_output.json`

---

### 8. Security (`role_security.md`)

**Responsibility**: Security audits and vulnerability analysis

**When to Use**:
- Performing security audits
- Scanning for vulnerabilities
- Compliance verification (OWASP, CWE)
- Secret detection and remediation

**Key Outputs**:
- `vulnerabilidades.criticas`: Critical vulnerability count
- `vulnerabilidades.detalle`: Vulnerability details with remediation
- `compliance.estandares_verificados`: Compliance standards checked
- `compliance.cumplimiento_pct`: Compliance percentage

**Example Task**:
```json
{
  "tarea_id": "T008",
  "backlog_id": "TASK-SEC-008",
  "tipo": "security",
  "asignado_a": "security",
  "estado": "completado",
  "vulnerabilidades": {
    "criticas": 0,
    "altas": 1,
    "medias": 3,
    "bajas": 5,
    "detalle": [
      {
        "id": "SEC-AUTH-001",
        "severidad": "alta",
        "tipo": "Weak Password Hashing",
        "descripcion": "Using bcrypt with only 4 rounds (should be 12+)",
        "archivo": "src/auth/hash.py",
        "remediacion": "Increase bcrypt rounds to 12",
        "estado": "resuelto"
      }
    ]
  },
  "compliance": {
    "estandares_verificados": ["OWASP Top 10", "CWE Top 25"],
    "cumplimiento_pct": 94.2
  }
}
```

**Schema**: `schemas/security_output.json`

---

### 9. DevOps (`role_devops.md`)

**Responsibility**: CI/CD pipeline and deployment automation

**When to Use**:
- Setting up CI/CD pipelines
- Configuring automated testing and builds
- Managing deployment workflows
- Implementing release automation

**Key Outputs**:
- `pipeline.stages`: Pipeline stages (test, build, deploy)
- `pipeline.triggers`: Pipeline triggers (push, PR, schedule)
- `deployment.estrategia`: Deployment strategy (blue-green, rolling)
- `rollback.procedimiento`: Rollback procedure

**Example Task**:
```json
{
  "tarea_id": "T009",
  "backlog_id": "TASK-DEV-009",
  "tipo": "devops",
  "asignado_a": "devops",
  "estado": "completado",
  "pipeline": {
    "plataforma": "GitHub Actions",
    "archivo_config": ".github/workflows/ci.yml",
    "stages": [
      {
        "nombre": "test",
        "comandos": ["pytest --cov=src --cov-report=xml"],
        "duracion_estimada_min": 5
      },
      {
        "nombre": "security-scan",
        "herramientas": ["snyk", "trivy"],
        "duracion_estimada_min": 3
      },
      {
        "nombre": "deploy",
        "objetivo": "production",
        "duracion_estimada_min": 10
      }
    ],
    "triggers": ["push", "pull_request"]
  },
  "deployment": {
    "estrategia": "rolling",
    "rollback_automatico": true
  }
}
```

**Schema**: `schemas/devops_output.json`

---

## Blackboard.json Structure

### Overview

`blackboard.json` is the **ephemeral session state** file that all agents read from and write to. It contains all active tasks for the current work session and is validated against `schemas/blackboard_schema.json`.

### Structure

```json
{
  "$schema": "file:///schemas/blackboard_schema.json",
  "estado_actual": "string",
  "tareas": [
    {
      "tarea_id": "string (unique, e.g., T001)",
      "backlog_id": "string (TASK-XXX-YYY, mandatory)",
      "tipo": "string (planning|backend|frontend|ai|infra|qa|reviewer|security|devops)",
      "descripcion": "string",
      "asignado_a": "string (role name)",
      "estado": "string (pendiente|en_progreso|completado|fallido)",
      "prioridad": "string (optional: alta|media|baja)",
      "dependencias": ["array of tarea_ids (optional)"],
      "creado": "ISO8601 timestamp",
      "actualizado": "ISO8601 timestamp",
      "resultado": {
        "exitoso": "boolean",
        "mensaje": "string",
        "errores": ["array (optional)"]
      },
      "... role-specific fields ..."
    }
  ]
}
```

### Mandatory Fields

Every task MUST include:

1. **tarea_id**: Unique session identifier (e.g., `T001`, `T002`)
2. **backlog_id**: Link to permanent backlog (pattern: `^TASK-[A-Z0-9-]+$`)
3. **tipo**: Task type matching role
4. **descripcion**: Human-readable task description
5. **asignado_a**: Role responsible for execution
6. **estado**: Current task state
7. **resultado**: Execution outcome (after completion)

### Role-Specific Fields

Each role extends the base structure with specialized fields:

| Role | Key Fields |
|------|------------|
| **planner** | `plan` (subtareas, fases, riesgos) |
| **backend** | `codigo` (archivos_modificados, dependencias_nuevas, tests, api) |
| **frontend** | `componentes` (jerarquia, estado_compartido, estilos, accesibilidad) |
| **ai** | `modelo` (nombre, framework), `uso` (latencia, costo), `observabilidad` |
| **infra** | `recursos` (provisionados, configuracion, costos, monitoreo) |
| **qa** | `casos_prueba` (total, pasados, detalle), `bugs`, `cobertura` |
| **reviewer** | `revision` (issues, archivos_revisados, aprobacion, metricas) |
| **security** | `vulnerabilidades` (detalle, severidad), `compliance`, `secrets` |
| **devops** | `pipeline` (stages, triggers), `deployment`, `rollback` |

### Example: Complete Multi-Role Session

```json
{
  "$schema": "file:///schemas/blackboard_schema.json",
  "estado_actual": "implementacion_completada",
  "tareas": [
    {
      "tarea_id": "T001",
      "backlog_id": "TASK-AUTH-001",
      "tipo": "planning",
      "descripcion": "Plan user authentication feature",
      "asignado_a": "planner",
      "estado": "completado",
      "creado": "2026-04-04T10:00:00Z",
      "actualizado": "2026-04-04T10:30:00Z",
      "resultado": {
        "exitoso": true,
        "mensaje": "Authentication feature plan created with 3 subtasks"
      },
      "plan": {
        "subtareas": [
          {
            "id": "T001-1",
            "descripcion": "Implement auth endpoints",
            "asignado_a": "backend"
          }
        ]
      }
    },
    {
      "tarea_id": "T002",
      "backlog_id": "TASK-AUTH-001-SUB1",
      "tipo": "backend",
      "descripcion": "Implement authentication endpoints",
      "asignado_a": "backend",
      "estado": "completado",
      "dependencias": ["T001"],
      "creado": "2026-04-04T10:30:00Z",
      "actualizado": "2026-04-04T12:00:00Z",
      "resultado": {
        "exitoso": true,
        "mensaje": "Auth endpoints implemented with JWT + bcrypt"
      },
      "codigo": {
        "archivos_modificados": [
          "src/auth/endpoints.py",
          "src/auth/models.py"
        ],
        "dependencias_nuevas": ["pyjwt==2.8.0", "bcrypt==4.1.2"]
      }
    }
  ]
}
```

---

## Defense-in-Depth Validation

The C2PRO system enforces a **4-layer validation strategy** to prevent data corruption, ensure traceability, and maintain data integrity.

### Validation Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Post-Execution Validation                              │
│ • Verify backlog updated after task completion                  │
│ • Check for [x] marker in backlog files                         │
│ • Log warnings if backlog not updated                           │
│ • Function: validar_tarea_post_ejecucion()                      │
└─────────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Pre-Execution Validation                               │
│ • Verify backlog_id exists in actual files                      │
│ • Block execution of orphaned tasks                             │
│ • Prevent work without traceability                             │
│ • Function: validar_tarea_antes_ejecucion()                     │
└─────────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Runtime Validation                                     │
│ • Pattern validation: ^TASK-[A-Z0-9-]+$                         │
│ • Non-empty backlog_id check                                    │
│ • Mandatory field presence check                                │
│ • Function: validar_backlog_ids()                               │
└─────────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Schema Validation                                      │
│ • JSON Schema Draft-07 validation                               │
│ • Role-specific field validation                                │
│ • Type checking and required field enforcement                  │
│ • Function: validar_task_schemas()                              │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1: Schema Validation

**Purpose**: Validate task structure against role-specific JSON schemas

**Implementation**: `core/supervisor.py::validar_task_schemas()`

**When Executed**: Before saving to `blackboard.json`

**What It Checks**:

- Role-specific required fields present
- Field types match schema definitions
- Role-specific field structures are valid
- Base fields (tarea_id, backlog_id, tipo, etc.) present

**Schemas Used**:

- `schemas/base_output.json` - Base fields for all tasks
- `schemas/{role}_output.json` - Role-specific extensions (9 roles)

**Error Example**:
```
Schema Validation Error:
  Role: backend
  Task: T002
  Error: 'codigo' is a required property
  Schema: schemas/backend_output.json
```

### Layer 2: Runtime Validation

**Purpose**: Validate backlog_id pattern and presence

**Implementation**: `core/supervisor.py::validar_backlog_ids()`

**When Executed**: Before saving to `blackboard.json`

**What It Checks**:

- `backlog_id` field exists in task
- `backlog_id` is non-empty string
- `backlog_id` matches pattern `^TASK-[A-Z0-9-]+$`

**Valid Patterns**:

- `TASK-AUTH-001` ✅
- `TASK-BCK-123` ✅
- `TASK-FRT-456-SUB1` ✅

**Invalid Patterns**:

- `task-001` ❌ (lowercase)
- `T001` ❌ (missing TASK prefix)
- `TASK_AUTH_001` ❌ (underscores instead of hyphens)

**Error Example**:
```
Backlog ID Validation Error:
  Task: T002
  Invalid backlog_id: "task-auth-001"
  Expected pattern: ^TASK-[A-Z0-9-]+$
  Fix: Use uppercase TASK- prefix with hyphens
```

### Layer 3: Pre-Execution Validation

**Purpose**: Verify backlog_id exists in permanent backlog files before task execution

**Implementation**: `core/supervisor.py::validar_tarea_antes_ejecucion()`

**When Executed**: Before executing task (in `_ejecutar_secuencial()`)

**What It Checks**:
- All Layer 2 checks (pattern, presence, non-empty)
- `backlog_id` exists in `C2PRO_MASTER_BACKLOG.md`
- `backlog_id` exists in category backlogs (`backlogs/*.md`)

**Search Pattern**:
```python
# Searches for line matching: | [ ] | ... | `TASK-XXX-YYY` | ...
# or: | [x] | ... | `TASK-XXX-YYY` | ...
```

**Error Example**:
```
Pre-Execution Validation Error:
  Task: T002
  backlog_id: TASK-AUTH-001
  Error: backlog_id not found in any backlog files
  Searched files:
    - C2PRO_MASTER_BACKLOG.md
    - backlogs/BACKEND_BACKLOG.md
    - backlogs/FRONTEND_BACKLOG.md
    - ... (all category backlogs)
  Fix: Add task to appropriate backlog before execution
```

### Layer 4: Post-Execution Validation

**Purpose**: Verify backlog was updated after task completion

**Implementation**: `core/supervisor.py::validar_tarea_post_ejecucion()`

**When Executed**: After task execution completes successfully

**What It Checks**:
- Task completed successfully (`estado == "completado"`)
- `backlog_id` marked as `[x]` in backlog files
- Completion timestamp present

**Warning Example** (non-blocking):
```
WARNING: Post-Execution Validation Failed
  Task: T002 completed successfully
  backlog_id: TASK-AUTH-001
  Issue: Backlog not updated after task completion
  Expected: | [x] | ... | `TASK-AUTH-001` | ...
  Found: | [ ] | ... | `TASK-AUTH-001` | ...
  Severity: media (warning, not error)
  Action Required: Manually update backlog to mark task complete
```

### Validation Flow in supervisor.py

```python
def guardar_blackboard(data: dict) -> None:
    """
    Save blackboard.json with 2-layer validation.

    Layer 1: Schema validation (validar_task_schemas)
    Layer 2: Backlog ID validation (validar_backlog_ids)
    """
    # Layer 1: Schema validation
    validar_task_schemas(data["tareas"])

    # Layer 2: Runtime validation
    validar_backlog_ids(data["tareas"])

    # Save to file
    guardar_json(BLACKBOARD_PATH, data)


def _ejecutar_secuencial(tareas: list) -> list:
    """
    Execute tasks with pre/post validation.

    Layer 3: Pre-execution validation (before execution)
    Layer 4: Post-execution validation (after completion)
    """
    for tarea in tareas:
        # Layer 3: Pre-execution validation
        validar_tarea_antes_ejecucion(tarea)

        # Execute task
        resultado = ejecutar_agente(tarea)

        # Update task with result
        tarea["estado"] = "completado"
        tarea["resultado"] = resultado

        # Layer 4: Post-execution validation (warning only)
        try:
            validar_tarea_post_ejecucion(tarea)
        except ValueError as e:
            logger.warning(f"Post-execution validation failed: {e}")
```

---

## Multi-Role Collaboration Patterns

### Pattern 1: Sequential Workflow (Planner → Backend → QA)

**Use Case**: Feature implementation with testing

**Flow**:
1. **Planner** creates implementation plan with subtasks
2. **Backend** implements feature based on plan
3. **QA** tests implementation and reports bugs
4. **Backend** fixes bugs (if found)
5. **QA** re-validates fixes

**Example**: User Authentication Feature

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Planner  │────►│ Backend  │────►│   QA     │
│          │     │          │     │          │
│ Plan:    │     │ Impl:    │     │ Test:    │
│ • Login  │     │ • JWT    │     │ • 24     │
│ • Logout │     │ • bcrypt │     │   tests  │
│ • Reg... │     │ • API    │     │ • 2 bugs │
└──────────┘     └──────────┘     └────┬─────┘
                                        │
                                        ▼
                                 ┌──────────┐
                                 │ Backend  │
                                 │ (fixes)  │
                                 └────┬─────┘
                                      │
                                      ▼
                                 ┌──────────┐
                                 │   QA     │
                                 │(re-test) │
                                 └──────────┘
```

**Blackboard States**:

**State 1: Planning**
```json
{
  "estado_actual": "planificacion",
  "tareas": [
    {
      "tarea_id": "T001",
      "backlog_id": "TASK-AUTH-001",
      "tipo": "planning",
      "asignado_a": "planner",
      "estado": "en_progreso"
    }
  ]
}
```

**State 2: Implementation**
```json
{
  "estado_actual": "implementacion",
  "tareas": [
    {
      "tarea_id": "T001",
      "asignado_a": "planner",
      "estado": "completado",
      "plan": { "subtareas": [...] }
    },
    {
      "tarea_id": "T002",
      "backlog_id": "TASK-AUTH-001-SUB1",
      "tipo": "backend",
      "asignado_a": "backend",
      "estado": "en_progreso",
      "dependencias": ["T001"]
    }
  ]
}
```

**State 3: Testing**
```json
{
  "estado_actual": "validacion",
  "tareas": [
    {...planner completado...},
    {...backend completado...},
    {
      "tarea_id": "T003",
      "backlog_id": "TASK-AUTH-001-SUB2",
      "tipo": "qa",
      "asignado_a": "qa",
      "estado": "en_progreso",
      "dependencias": ["T002"]
    }
  ]
}
```

---

### Pattern 2: Parallel Workflow (Frontend + Backend + Infra)

**Use Case**: Parallel development of independent components

**Flow**:
1. **Planner** creates plan with parallel subtasks
2. **Backend**, **Frontend**, **Infra** work simultaneously
3. **QA** tests integration after all complete

**Example**: Real-Time Dashboard

```
                    ┌──────────┐
                    │ Planner  │
                    │          │
                    │ Creates  │
                    │ 3 tasks  │
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐  ┌──────────┐
    │ Backend  │   │ Frontend │  │  Infra   │
    │          │   │          │  │          │
    │ API      │   │ Dashboard│  │ WebSocket│
    │ endpoints│   │ UI       │  │ server   │
    └────┬─────┘   └────┬─────┘  └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                   ┌──────────┐
                   │   QA     │
                   │          │
                   │ E2E      │
                   │ tests    │
                   └──────────┘
```

**Blackboard State (Parallel Execution)**:
```json
{
  "estado_actual": "implementacion_paralela",
  "tareas": [
    {
      "tarea_id": "T001",
      "asignado_a": "planner",
      "estado": "completado"
    },
    {
      "tarea_id": "T002",
      "backlog_id": "TASK-DASH-002",
      "tipo": "backend",
      "asignado_a": "backend",
      "estado": "en_progreso",
      "dependencias": ["T001"]
    },
    {
      "tarea_id": "T003",
      "backlog_id": "TASK-DASH-003",
      "tipo": "frontend",
      "asignado_a": "frontend",
      "estado": "en_progreso",
      "dependencias": ["T001"]
    },
    {
      "tarea_id": "T004",
      "backlog_id": "TASK-DASH-004",
      "tipo": "infra",
      "asignado_a": "infra",
      "estado": "en_progreso",
      "dependencias": ["T001"]
    }
  ]
}
```

---

### Pattern 3: Review & Security Cycle

**Use Case**: Code review with security audit

**Flow**:
1. **Backend** implements feature
2. **Reviewer** reviews code quality
3. **Security** audits for vulnerabilities
4. **Backend** fixes issues (if found)
5. **Reviewer** + **Security** re-validate

**Example**: Payment Processing

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Backend  │────►│ Reviewer │────►│ Security │
│          │     │          │     │          │
│ Payment  │     │ Review:  │     │ Audit:   │
│ API      │     │ • 3      │     │ • 1 alta │
│          │     │   issues │     │ • PCI    │
└──────────┘     └──────────┘     └────┬─────┘
                                        │
                                        ▼
                                 ┌──────────┐
                                 │ Backend  │
                                 │ (fixes)  │
                                 └────┬─────┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                   ┌──────────┐            ┌──────────┐
                   │ Reviewer │            │ Security │
                   │(re-check)│            │(re-audit)│
                   └──────────┘            └──────────┘
```

---

### Pattern 4: Full Deployment Pipeline

**Use Case**: End-to-end feature deployment

**Flow**:
1. **Planner** creates deployment plan
2. **Backend** implements feature
3. **Reviewer** reviews code
4. **Security** audits security
5. **QA** runs tests
6. **DevOps** deploys to staging
7. **QA** validates in staging
8. **DevOps** deploys to production

**Example**: Multi-Tenant SaaS Feature

```
Planner → Backend → Reviewer → Security → QA → DevOps (staging) → QA (staging validation) → DevOps (prod)
```

**Roles Involved**: All except AI, Frontend, Infra (in this scenario)

---

## Common Workflow Scenarios

### Scenario 1: Adding a New API Endpoint

**Roles**: Planner, Backend, QA, Reviewer, Security, DevOps

**Steps**:

1. **Planner** (`T001`):
   - Creates implementation plan
   - Defines subtasks for backend, qa, reviewer, security, devops
   - Estimates timeline: 16 hours

2. **Backend** (`T002`):
   - Implements API endpoint (`POST /api/users`)
   - Adds input validation (Pydantic schemas)
   - Writes unit tests (15 tests, 92% coverage)

3. **Reviewer** (`T003`):
   - Reviews code quality
   - Finds 2 medium issues (missing error handling)
   - Requests changes

4. **Backend** (`T004`):
   - Fixes issues from review
   - Adds comprehensive error handling

5. **Security** (`T005`):
   - Audits endpoint for OWASP Top 10
   - Finds 1 high issue (SQL injection risk)
   - Provides remediation guidance

6. **Backend** (`T006`):
   - Fixes security issue (use parameterized queries)

7. **QA** (`T007`):
   - Runs integration tests (24 tests, all passing)
   - Validates API contract matches spec

8. **DevOps** (`T008`):
   - Updates CI/CD pipeline
   - Deploys to staging
   - Monitors deployment

**Total Tasks**: 8
**Roles Used**: 5
**Timeline**: ~2 days

---

### Scenario 2: Microservices Migration

**Roles**: Planner, Backend, Infra, QA, DevOps

**Steps**:

1. **Planner** (`T001`):
   - Creates migration roadmap
   - Phase 1: Auth service extraction
   - Phase 2: Data migration
   - Phase 3: Gradual rollout

2. **Infra** (`T002`):
   - Provisions Kubernetes cluster (EKS)
   - Sets up service mesh (Istio)
   - Configures auto-scaling (3-10 nodes)

3. **Backend** (`T003`):
   - Extracts auth service from monolith
   - Implements gRPC interface
   - Adds backward compatibility layer

4. **QA** (`T004`):
   - Tests auth service independently
   - Validates monolith still works
   - Runs load tests (1000 RPS)

5. **DevOps** (`T005`):
   - Creates deployment pipeline
   - Implements blue-green deployment
   - Sets up monitoring (Prometheus + Grafana)

6. **Backend** (`T006`):
   - Implements data migration scripts
   - Validates data consistency

7. **QA** (`T007`):
   - Validates data migration
   - Runs regression tests on monolith

8. **DevOps** (`T008`):
   - Executes gradual rollout (10% → 50% → 100% traffic)
   - Monitors error rates and latency

**Total Tasks**: 8
**Roles Used**: 4
**Timeline**: ~2 weeks

---

### Scenario 3: AI-Powered Feature Implementation

**Roles**: Planner, AI, Backend, Frontend, Infra, QA

**Steps**:

1. **Planner** (`T001`):
   - Plans sentiment analysis feature
   - Defines integration points with existing system

2. **AI** (`T002`):
   - Trains sentiment analysis model
   - Framework: transformers (BERT-based)
   - Accuracy: 91.3%
   - Latency P95: 450ms

3. **Infra** (`T003`):
   - Provisions GPU instances for inference
   - Sets up model serving (TensorFlow Serving)

4. **Backend** (`T004`):
   - Creates API endpoint for sentiment analysis
   - Implements caching layer (Redis)
   - Adds rate limiting (100 requests/min)

5. **Frontend** (`T005`):
   - Builds sentiment display component
   - Real-time sentiment visualization
   - Integrates with backend API

6. **QA** (`T006`):
   - Tests model accuracy on test set
   - Validates API response times
   - Checks caching behavior

**Total Tasks**: 6
**Roles Used**: 6
**Timeline**: ~1 week

---

## Schema Reference

### Base Schema (All Roles)

**File**: `schemas/base_output.json`

**Required Fields**:
```json
{
  "tarea_id": "string",
  "backlog_id": "string (pattern: ^TASK-[A-Z0-9-]+$)",
  "tipo": "string (enum)",
  "descripcion": "string",
  "asignado_a": "string (enum: 9 roles)",
  "estado": "string (enum: pendiente|en_progreso|completado|fallido)",
  "resultado": {
    "exitoso": "boolean",
    "mensaje": "string",
    "errores": ["array (optional)"]
  }
}
```

---

### Role-Specific Schemas

#### Planner (`schemas/planner_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "plan": {
    "subtareas": [
      {
        "id": "string",
        "descripcion": "string",
        "asignado_a": "string",
        "dependencias": ["array (optional)"],
        "estimacion_horas": "number"
      }
    ],
    "fases": [
      {
        "nombre": "string",
        "descripcion": "string",
        "tareas": ["array of subtask IDs"]
      }
    ],
    "riesgos": ["array (optional)"],
    "estimacion_total_horas": "number"
  }
}
```

---

#### Backend (`schemas/backend_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "codigo": {
    "archivos_modificados": ["array of file paths"],
    "dependencias_nuevas": ["array of package@version"],
    "tests_unitarios": {
      "total": "number",
      "pasados": "number",
      "cobertura_pct": "number"
    },
    "database": {
      "migraciones": ["array (optional)"],
      "queries_optimizadas": ["array (optional)"]
    },
    "api": {
      "endpoints": [
        {
          "path": "string",
          "method": "string",
          "descripcion": "string"
        }
      ]
    }
  }
}
```

---

#### Frontend (`schemas/frontend_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "componentes": {
    "jerarquia": [
      {
        "nombre": "string",
        "ruta": "string",
        "hijos": ["array (optional)"]
      }
    ],
    "estado_compartido": [
      {
        "nombre": "string",
        "tipo": "string",
        "campos": ["array"]
      }
    ],
    "estilos": {
      "framework": "string",
      "archivos": ["array"]
    },
    "accesibilidad": {
      "wcag_nivel": "string",
      "aria_labels": "boolean",
      "keyboard_navigation": "boolean"
    },
    "rendimiento": {
      "lighthouse_score": "number (optional)",
      "bundle_size_kb": "number (optional)"
    }
  }
}
```

---

#### AI (`schemas/ai_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "modelo": {
    "nombre": "string",
    "tipo": "string",
    "framework": "string",
    "version": "string"
  },
  "uso": {
    "input_tokens_promedio": "number",
    "output_tokens_promedio": "number",
    "latencia_p95_ms": "number",
    "costo_por_request_usd": "number"
  },
  "observabilidad": {
    "metricas_trackeadas": ["array"],
    "alertas_configuradas": "boolean",
    "logging_level": "string"
  }
}
```

---

#### Infra (`schemas/infra_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "recursos": {
    "provisionados": [
      {
        "tipo": "string",
        "nombre": "string",
        "proveedor": "string",
        "configuracion": "object"
      }
    ],
    "costos": {
      "estimacion_mensual_usd": "number",
      "breakdown": ["array (optional)"]
    },
    "monitoreo": {
      "herramientas": ["array"],
      "dashboards": ["array (optional)"]
    }
  }
}
```

---

#### QA (`schemas/qa_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "casos_prueba": {
    "total": "number",
    "pasados": "number",
    "fallados": "number",
    "detalle": [
      {
        "nombre": "string",
        "resultado": "string",
        "duracion_ms": "number",
        "error": "string (optional)"
      }
    ]
  },
  "bugs": {
    "encontrados": "number",
    "criticos": "number",
    "altos": "number",
    "medios": "number",
    "bajas": "number (optional)"
  },
  "cobertura": {
    "lineas_pct": "number (optional)",
    "ramas_pct": "number (optional)"
  }
}
```

---

#### Reviewer (`schemas/reviewer_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "revision": {
    "issues": [
      {
        "id": "string",
        "severidad": "string",
        "tipo": "string",
        "descripcion": "string",
        "archivo": "string",
        "linea": "number (optional)",
        "recomendacion": "string"
      }
    ],
    "archivos_revisados": "number",
    "tiempo_revision_horas": "number (optional)",
    "aprobacion": {
      "decision": "string (enum: aprobado|cambios_requeridos|rechazado)",
      "razon": "string"
    },
    "metricas": {
      "calidad_codigo": "number",
      "complejidad_ciclomatica": "number (optional)"
    }
  }
}
```

---

#### Security (`schemas/security_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "vulnerabilidades": {
    "criticas": "number",
    "altas": "number",
    "medias": "number",
    "bajas": "number",
    "detalle": [
      {
        "id": "string",
        "severidad": "string",
        "tipo": "string",
        "descripcion": "string",
        "archivo": "string (optional)",
        "remediacion": "string",
        "estado": "string"
      }
    ]
  },
  "compliance": {
    "estandares_verificados": ["array"],
    "cumplimiento_pct": "number"
  },
  "secrets": {
    "encontrados": "number (optional)",
    "tipos": ["array (optional)"]
  }
}
```

---

#### DevOps (`schemas/devops_output.json`)

**Extends**: `base_output.json`

**Additional Required Fields**:
```json
{
  "pipeline": {
    "plataforma": "string",
    "archivo_config": "string",
    "stages": [
      {
        "nombre": "string",
        "comandos": ["array (optional)"],
        "herramientas": ["array (optional)"],
        "duracion_estimada_min": "number"
      }
    ],
    "triggers": ["array"]
  },
  "deployment": {
    "estrategia": "string",
    "rollback_automatico": "boolean (optional)"
  },
  "rollback": {
    "procedimiento": "string (optional)",
    "tiempo_estimado_min": "number (optional)"
  }
}
```

---

## Best Practices

### 1. Always Link to Backlog

**Rule**: Every task MUST have a valid `backlog_id` before execution

**Why**: Ensures complete traceability between ephemeral sessions and permanent backlog

**Example**:
```json
// ❌ BAD - No backlog_id
{
  "tarea_id": "T001",
  "tipo": "backend",
  "descripcion": "Implement login endpoint"
}

// ✅ GOOD - Valid backlog_id
{
  "tarea_id": "T001",
  "backlog_id": "TASK-AUTH-001",
  "tipo": "backend",
  "descripcion": "Implement login endpoint"
}
```

---

### 2. Use Descriptive Task IDs

**Rule**: Use semantic backlog_id patterns that indicate category and purpose

**Patterns**:
- `TASK-AUTH-001` - Authentication-related tasks
- `TASK-BCK-123` - Backend tasks
- `TASK-FRT-456` - Frontend tasks
- `TASK-INFRA-789` - Infrastructure tasks

**Why**: Makes task relationships clear and enables category-based filtering

---

### 3. Document Dependencies

**Rule**: Always specify task dependencies when tasks must execute in order

**Example**:
```json
{
  "tarea_id": "T002",
  "backlog_id": "TASK-AUTH-001-SUB1",
  "tipo": "qa",
  "descripcion": "Test login endpoint",
  "dependencias": ["T001"],  // ← Must wait for T001 (backend implementation)
  "estado": "pendiente"
}
```

**Why**: Prevents premature execution and ensures correct workflow sequencing

---

### 4. Update Backlog After Completion

**Rule**: Mark tasks as `[x]` in backlog files immediately after completion

**Before**:
```markdown
| [ ] | P1 | `TASK-AUTH-001` | Backend | Implement login endpoint | ... |
```

**After**:
```markdown
| [x] | P1 | `TASK-AUTH-001` | Backend | Implement login endpoint @2026-04-04 (JWT auth with bcrypt, 24 tests passing, 92% coverage) | ... |
```

**Why**: Post-execution validation (Layer 4) will warn if backlog not updated

---

### 5. Write Comprehensive Result Messages

**Rule**: Include detailed outcome information in `resultado.mensaje`

**Example**:
```json
{
  "resultado": {
    "exitoso": true,
    "mensaje": "Authentication endpoints implemented: login (POST /api/auth/login), logout (POST /api/auth/logout), register (POST /api/auth/register). JWT tokens with 24-hour expiry. bcrypt password hashing (12 rounds). 24 unit tests passing. 92% code coverage. API documentation updated."
  }
}
```

**Why**: Enables future agents to understand what was accomplished without reading code

---

### 6. Validate Early and Often

**Rule**: Run schema validation before saving to blackboard.json

**Code**:
```python
from schemas.validator import validate_role_output

# Validate before saving
validate_role_output(task, role="backend")  # Raises error if invalid
guardar_blackboard(blackboard_data)
```

**Why**: Catches structural errors early before they propagate to other agents

---

### 7. Use Realistic Test Data in Development

**Rule**: When creating test fixtures, use realistic scenarios that reflect production workloads

**Example**:
```python
# ❌ BAD - Minimal test data
{
  "tarea_id": "T001",
  "backlog_id": "TASK-001",
  "tipo": "backend",
  "codigo": {"archivos_modificados": ["file.py"]}
}

# ✅ GOOD - Realistic test data
{
  "tarea_id": "T001",
  "backlog_id": "TASK-AUTH-001",
  "tipo": "backend",
  "descripcion": "Implement authentication endpoints with JWT and bcrypt",
  "codigo": {
    "archivos_modificados": [
      "src/auth/endpoints.py",
      "src/auth/models.py",
      "src/auth/hash.py",
      "tests/test_auth_endpoints.py"
    ],
    "dependencias_nuevas": ["pyjwt==2.8.0", "bcrypt==4.1.2"],
    "tests_unitarios": {
      "total": 24,
      "pasados": 24,
      "cobertura_pct": 92.5
    }
  }
}
```

**Why**: Realistic tests catch edge cases that minimal tests miss

---

### 8. Maintain Session Context

**Rule**: Use descriptive `estado_actual` to track workflow progress

**Example States**:
- `planificacion` - Planning phase
- `implementacion` - Implementation in progress
- `validacion` - QA testing in progress
- `revision` - Code review in progress
- `despliegue` - Deployment in progress
- `completado` - All tasks complete

**Why**: Enables workflow resumption and provides high-level progress visibility

---

### 9. Clean Up Old Sessions

**Rule**: Archive or delete old `blackboard.json` files after tasks are complete and backlog is updated

**Script**:
```bash
# Archive completed sessions
mkdir -p archive/$(date +%Y-%m)
cp blackboard.json archive/$(date +%Y-%m)/blackboard-$(date +%Y-%m-%d).json
rm blackboard.json
```

**Why**: Prevents confusion between old and new sessions

---

### 10. Monitor Validation Warnings

**Rule**: Regularly check logs for post-execution validation warnings

**Command**:
```bash
grep "Post-execution validation failed" logs/supervisor.log
```

**Why**: Identifies tasks that completed but didn't update backlog

---

## Troubleshooting

### Error: "Schema Validation Error: 'plan' is a required property"

**Cause**: Task marked as `tipo: "planning"` but missing `plan` field

**Fix**:
```json
{
  "tipo": "planning",
  "asignado_a": "planner",
  "plan": {  // ← Add this field
    "subtareas": [...],
    "fases": [...]
  }
}
```

**Prevention**: Always validate against schema before saving

---

### Error: "Backlog ID Validation Error: Invalid pattern"

**Cause**: `backlog_id` doesn't match `^TASK-[A-Z0-9-]+$` pattern

**Fix**:
```json
// ❌ WRONG
"backlog_id": "task-auth-001"  // lowercase
"backlog_id": "T001"  // missing TASK- prefix
"backlog_id": "TASK_AUTH_001"  // underscores

// ✅ CORRECT
"backlog_id": "TASK-AUTH-001"
"backlog_id": "TASK-BCK-123"
"backlog_id": "TASK-FRT-456-SUB1"
```

**Prevention**: Use uppercase TASK- prefix with hyphens only

---

### Error: "Pre-Execution Validation Error: backlog_id not found"

**Cause**: Task has valid `backlog_id` pattern but ID doesn't exist in any backlog file

**Fix**:
1. Add task to appropriate backlog file:
   ```markdown
   | [ ] | P1 | `TASK-AUTH-001` | Backend | Implement login endpoint | ... |
   ```

2. Or use existing backlog_id that's already registered

**Prevention**: Always create backlog entry before creating task in blackboard.json

---

### Warning: "Post-Execution Validation Failed: Backlog not updated"

**Cause**: Task completed successfully but backlog still shows `[ ]` instead of `[x]`

**Fix**:
1. Manually update backlog:
   ```markdown
   | [x] | P1 | `TASK-AUTH-001` | Backend | Implement login @2026-04-04 (details...) | ... |
   ```

2. Or use sync script:
   ```bash
   python -m core.sync_backlog_to_blackboard push
   ```

**Prevention**: Update backlog immediately after task completion

---

### Error: "TypeError: 'NoneType' object is not iterable"

**Cause**: Trying to iterate over `data["tareas"]` when `tareas` is `None` or missing

**Fix**:
```python
# ❌ WRONG
for tarea in data["tareas"]:  # Crashes if tareas is None

# ✅ CORRECT
for tarea in data.get("tareas", []):  # Defaults to empty list
```

**Prevention**: Always use `.get()` with default values when accessing optional fields

---

### Error: "FileNotFoundError: blackboard.json not found"

**Cause**: Trying to read `blackboard.json` when file doesn't exist

**Fix**:
```python
# Create empty blackboard if doesn't exist
if not os.path.exists("blackboard.json"):
    data = {
        "estado_actual": "inicial",
        "tareas": []
    }
    guardar_blackboard(data)
```

**Prevention**: Initialize blackboard.json before first use

---

## Quick Reference

### Validation Command

```bash
# Validate blackboard.json against schemas
python -m schemas.validator blackboard.json
```

### Sync Commands

```bash
# Pull pending tasks from backlog → blackboard
python -m core.sync_backlog_to_blackboard pull

# Push completed tasks from blackboard → backlog
python -m core.sync_backlog_to_blackboard push

# Bidirectional sync (pull + push)
python -m core.sync_backlog_to_blackboard sync

# Show sync status
python -m core.sync_backlog_to_blackboard status
```

### Schema Validation (Python)

```python
from schemas.validator import validate_role_output

task = {
    "tarea_id": "T001",
    "backlog_id": "TASK-AUTH-001",
    "tipo": "backend",
    "asignado_a": "backend",
    # ... other fields
}

# Validate task
try:
    validate_role_output(task, role="backend")
    print("✅ Task is valid")
except ValueError as e:
    print(f"❌ Validation error: {e}")
```

### Backlog ID Pattern

```regex
^TASK-[A-Z0-9-]+$
```

**Valid Examples**:
- `TASK-AUTH-001`
- `TASK-BCK-123`
- `TASK-FRT-456-SUB1`

**Invalid Examples**:
- `task-auth-001` (lowercase)
- `T001` (missing TASK- prefix)
- `TASK_AUTH_001` (underscores)

### Task States

- `pendiente` - Not started
- `en_progreso` - In progress
- `completado` - Successfully completed
- `fallido` - Failed with errors

### Workflow Phases (estado_actual)

- `planificacion` - Planning phase
- `implementacion` - Implementation in progress
- `validacion` - QA testing
- `revision` - Code review
- `seguridad` - Security audit
- `despliegue` - Deployment
- `completado` - All done

### Role Types (asignado_a)

- `planner` - Strategic planning
- `backend` - API/server implementation
- `frontend` - UI/UX development
- `ai` - AI/ML development
- `infra` - Infrastructure provisioning
- `qa` - Quality assurance
- `reviewer` - Code review
- `security` - Security audits
- `devops` - CI/CD & deployment

---

## Summary

The C2PRO Agent Orchestration System provides a **robust, validated, and traceable** framework for multi-agent collaboration. By enforcing mandatory `backlog_id` linking, 4-layer validation, and role-specific schemas, the system ensures:

1. ✅ **Complete Traceability**: Every task linked to permanent backlog
2. ✅ **Data Integrity**: 4-layer validation prevents corruption
3. ✅ **Role Clarity**: 9 specialized roles with clear responsibilities
4. ✅ **Workflow Flexibility**: Support for sequential, parallel, and complex workflows
5. ✅ **Production-Ready**: Comprehensive testing with 100% validation coverage

**Key Files**:
- `blackboard.json` - Ephemeral session state
- `C2PRO_MASTER_BACKLOG.md` - Permanent task register
- `schemas/*.json` - Validation schemas
- `core/supervisor.py` - Orchestration engine

**Key Principles**:
- Defense-in-depth validation (4 layers)
- Mandatory backlog_id linking
- Schema-driven validation
- Role-based architecture

For questions or issues, refer to:
- `AGENT_STRUCTURE_UNIFICATION_ANALYSIS.md` - Implementation details
- `UNIFY-013_COMPLETION_SUMMARY.md` - Integration testing
- `UNIFY-014_COMPLETION_SUMMARY.md` - Role validation testing

---

**Version**: 1.0.0
**Last Updated**: 2026-04-04
**Status**: Production-Ready ✅
