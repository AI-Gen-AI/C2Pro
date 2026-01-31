# C2Pro - ÍNDICE EXHAUSTIVO DE TEST SUITES v1.1

> **Versión:** 1.1  
> **Fecha:** 2026-01-31  
> **Objetivo:** Cobertura 100% Core, >80% Módulos  
> **Metodología:** TDD Estricto (Red → Green → Refactor)

---

## ÍNDICE DE CONTENIDOS

1. [Resumen de Cobertura](#1-resumen-de-cobertura)
2. [Índice Maestro de Test Suites](#2-índice-maestro-de-test-suites)
3. [Test Suites CORE (100% Cobertura)](#3-test-suites-core-100-cobertura)
4. [Test Suites por Módulo de Dominio](#4-test-suites-por-módulo-de-dominio)
5. [Test Suites de Integración](#5-test-suites-de-integración)
6. [Test Suites E2E](#6-test-suites-e2e)
7. [Matriz de Cobertura Detallada](#7-matriz-de-cobertura-detallada)
8. [Plan de Ejecución por Sprints](#8-plan-de-ejecución-por-sprints)
9. [Detalle de Test Suites por Agente](#9-detalle-de-test-suites-por-agente)
10. [Dependencias y Orden de Implementación](#10-dependencias-y-orden-de-implementación)

---

## 1. Resumen de Cobertura

### 1.1 Objetivos de Cobertura por Capa

| Capa | Target | Mínimo | Tests Planificados |
|------|--------|--------|-------------------|
| **CORE (Security, MCP, Anonymizer)** | **100%** | 98% | 156 |
| **Domain Entities** | **95%** | 90% | 198 |
| **Application (Use Cases)** | **90%** | 85% | 145 |
| **Adapters (HTTP/Persistence)** | **85%** | 80% | 112 |
| **Integration** | **90%** | 85% | 167 |
| **E2E** | **80%** | 75% | 68 |
| **TOTAL** | **92%** | 87% | **846** |

### 1.2 Resumen Numérico Total

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        RESUMEN TOTAL DE TESTS C2Pro                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  UNIT TESTS                                                                   ║
║  ├── Core (100% coverage)................... 156 tests                       ║
║  ├── Domain Entities....................... 198 tests                        ║
║  ├── Application Layer..................... 145 tests                        ║
║  └── Adapters.............................. 112 tests                        ║
║      ───────────────────────────────────────────────                         ║
║      SUBTOTAL UNIT......................... 611 tests (72%)                  ║
║                                                                               ║
║  INTEGRATION TESTS                                                            ║
║  ├── Database Integration.................. 67 tests                         ║
║  ├── External Services..................... 42 tests                         ║
║  ├── Cross-Module.......................... 38 tests                         ║
║  └── Event Bus............................. 20 tests                         ║
║      ───────────────────────────────────────────────                         ║
║      SUBTOTAL INTEGRATION.................. 167 tests (20%)                  ║
║                                                                               ║
║  E2E TESTS                                                                    ║
║  ├── API Flows............................. 38 tests                         ║
║  ├── UI Flows.............................. 18 tests                         ║
║  └── Error Scenarios....................... 12 tests                         ║
║      ───────────────────────────────────────────────                         ║
║      SUBTOTAL E2E.......................... 68 tests (8%)                    ║
║                                                                               ║
║  ═══════════════════════════════════════════════════════════════════════     ║
║  TOTAL GENERAL............................. 846 tests                        ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Índice Maestro de Test Suites

### 2.1 Estructura de Numeración

```
TS-[CAPA]-[MÓDULO]-[COMPONENTE]-[SECUENCIA]

Donde:
- CAPA: UC (Unit Core), UD (Unit Domain), UA (Unit Application), 
        UAD (Unit Adapter), INT (Integration), E2E (End-to-End)
- MÓDULO: SEC, DOC, COH, PRJ, PROC, STK, ANA, ASY, OBS, API
- COMPONENTE: Abreviatura del componente
- SECUENCIA: Número secuencial
```

### 2.2 Índice Completo de Test Suites (89 Suites)

| # | Suite ID | Nombre | Tests | Cobertura | Prioridad |
|---|----------|--------|-------|-----------|-----------|
| **CORE - SECURITY (100%)** |||||
| 1 | TS-UC-SEC-MCP-001 | MCP Gateway Allowlist | 18 | 100% | 🔴 P0 |
| 2 | TS-UC-SEC-MCP-002 | MCP Gateway Rate Limiting | 14 | 100% | 🔴 P0 |
| 3 | TS-UC-SEC-MCP-003 | MCP Gateway Query Limits | 12 | 100% | 🔴 P0 |
| 4 | TS-UC-SEC-MCP-004 | MCP Gateway Audit | 10 | 100% | 🔴 P0 |
| 5 | TS-UC-SEC-ANO-001 | Anonymizer PII Detection | 24 | 100% | 🔴 P0 |
| 6 | TS-UC-SEC-ANO-002 | Anonymizer Strategies | 16 | 100% | 🔴 P0 |
| 7 | TS-UC-SEC-ANO-003 | Anonymizer Tenant Config | 8 | 100% | 🟠 P1 |
| 8 | TS-UC-SEC-TNT-001 | Tenant Context & Isolation | 14 | 100% | 🔴 P0 |
| 9 | TS-UC-SEC-JWT-001 | JWT Validation | 12 | 100% | 🔴 P0 |
| 10 | TS-UC-SEC-AUD-001 | Audit Trail Core | 16 | 100% | 🔴 P0 |
| 11 | TS-UC-SEC-GAM-001 | Anti-Gaming Detection | 12 | 100% | 🔴 P0 |
| **SUBTOTAL CORE** | | | **156** | **100%** | |
| **DOMAIN - DOCUMENTS (95%)** |||||
| 12 | TS-UD-DOC-CLS-001 | Clause Entity | 22 | 98% | 🔴 P0 |
| 13 | TS-UD-DOC-CLS-002 | Clause Types & Classification | 14 | 95% | 🟠 P1 |
| 14 | TS-UD-DOC-CLS-003 | SubClause Hierarchy | 10 | 95% | 🟠 P1 |
| 15 | TS-UD-DOC-ENT-001 | Entity Extraction - Dates | 16 | 98% | 🔴 P0 |
| 16 | TS-UD-DOC-ENT-002 | Entity Extraction - Money | 14 | 98% | 🔴 P0 |
| 17 | TS-UD-DOC-ENT-003 | Entity Extraction - Durations | 12 | 95% | 🟠 P1 |
| 18 | TS-UD-DOC-ENT-004 | Entity Extraction - Stakeholders | 10 | 95% | 🟠 P1 |
| 19 | TS-UD-DOC-DOC-001 | Document Entity | 14 | 95% | 🟠 P1 |
| 20 | TS-UD-DOC-CNF-001 | Confidence Scoring | 8 | 90% | 🟡 P2 |
| **SUBTOTAL DOCUMENTS** | | | **120** | **95%** | |
| **DOMAIN - COHERENCE (98%)** |||||
| 21 | TS-UD-COH-CAT-001 | Category Enum & Weights | 12 | 100% | 🔴 P0 |
| 22 | TS-UD-COH-RUL-001 | Rules Engine - SCOPE | 18 | 100% | 🔴 P0 |
| 23 | TS-UD-COH-RUL-002 | Rules Engine - BUDGET | 16 | 100% | 🔴 P0 |
| 24 | TS-UD-COH-RUL-003 | Rules Engine - TIME | 16 | 100% | 🔴 P0 |
| 25 | TS-UD-COH-RUL-004 | Rules Engine - TECHNICAL | 12 | 98% | 🔴 P0 |
| 26 | TS-UD-COH-RUL-005 | Rules Engine - LEGAL | 10 | 98% | 🔴 P0 |
| 27 | TS-UD-COH-RUL-006 | Rules Engine - QUALITY | 8 | 98% | 🟠 P1 |
| 28 | TS-UD-COH-SCR-001 | Score Calculator - SubScores | 14 | 100% | 🔴 P0 |
| 29 | TS-UD-COH-SCR-002 | Score Calculator - Global | 12 | 100% | 🔴 P0 |
| 30 | TS-UD-COH-SCR-003 | Score Calculator - Custom Weights | 10 | 98% | 🟠 P1 |
| 31 | TS-UD-COH-GAM-001 | Anti-Gaming Policy | 16 | 100% | 🔴 P0 |
| 32 | TS-UD-COH-ALR-001 | Alert Entity & Mapping | 12 | 95% | 🟠 P1 |
| **SUBTOTAL COHERENCE** | | | **156** | **98%** | |
| **DOMAIN - PROJECTS (90%)** |||||
| 33 | TS-UD-PRJ-WBS-001 | WBS Item Entity | 18 | 95% | 🔴 P0 |
| 34 | TS-UD-PRJ-WBS-002 | WBS Hierarchy & Codes | 14 | 95% | 🟠 P1 |
| 35 | TS-UD-PRJ-WBS-003 | WBS Validation Rules | 12 | 90% | 🟠 P1 |
| 36 | TS-UD-PRJ-WBS-004 | WBS CRUD Operations | 10 | 90% | 🟠 P1 |
| 37 | TS-UD-PRJ-PRJ-001 | Project Entity | 12 | 90% | 🟠 P1 |
| 38 | TS-UD-PRJ-DTO-001 | WBSItemDTO & IWBSQueryPort | 10 | 95% | 🔴 P0 |
| **SUBTOTAL PROJECTS** | | | **76** | **92%** | |
| **DOMAIN - PROCUREMENT (90%)** |||||
| 39 | TS-UD-PROC-BOM-001 | BOM Item Entity | 14 | 95% | 🔴 P0 |
| 40 | TS-UD-PROC-BOM-002 | BOM Validation Rules | 10 | 90% | 🟠 P1 |
| 41 | TS-UD-PROC-LTM-001 | Lead Time Calculator - Basic | 16 | 98% | 🔴 P0 |
| 42 | TS-UD-PROC-LTM-002 | Lead Time Calculator - Incoterms | 14 | 95% | 🟠 P1 |
| 43 | TS-UD-PROC-LTM-003 | Lead Time Calculator - Customs | 10 | 90% | 🟠 P1 |
| 44 | TS-UD-PROC-LTM-004 | Lead Time Alerts | 8 | 90% | 🟠 P1 |
| 45 | TS-UD-PROC-PLN-001 | Procurement Plan Generation | 10 | 85% | 🟡 P2 |
| **SUBTOTAL PROCUREMENT** | | | **82** | **92%** | |
| **DOMAIN - STAKEHOLDERS (88%)** |||||
| 46 | TS-UD-STK-ENT-001 | Stakeholder Entity | 12 | 95% | 🟠 P1 |
| 47 | TS-UD-STK-CLS-001 | Power/Interest Classification | 14 | 95% | 🟠 P1 |
| 48 | TS-UD-STK-CLS-002 | Quadrant Assignment | 10 | 90% | 🟠 P1 |
| 49 | TS-UD-STK-RAC-001 | RACI Entry Validation | 10 | 95% | 🟠 P1 |
| 50 | TS-UD-STK-RAC-002 | RACI Matrix Generation | 14 | 90% | 🟠 P1 |
| 51 | TS-UD-STK-RAC-003 | RACI from Clauses | 10 | 85% | 🟡 P2 |
| 52 | TS-UD-STK-MAP-001 | Stakeholder Map Data | 8 | 85% | 🟡 P2 |
| **SUBTOTAL STAKEHOLDERS** | | | **78** | **90%** | |
| **DOMAIN - ANALYSIS (85%)** |||||
| 53 | TS-UD-ANA-ALR-001 | Alert Entity Complete | 12 | 95% | 🟠 P1 |
| 54 | TS-UD-ANA-GRP-001 | Graph Node Entity | 10 | 90% | 🟠 P1 |
| 55 | TS-UD-ANA-GRP-002 | Graph Relationship Entity | 10 | 90% | 🟠 P1 |
| 56 | TS-UD-ANA-SRC-001 | Semantic Search Result | 8 | 85% | 🟡 P2 |
| 57 | TS-UD-ANA-HYB-001 | Hybrid Search Result | 8 | 85% | 🟡 P2 |
| **SUBTOTAL ANALYSIS** | | | **48** | **89%** | |
| **APPLICATION - USE CASES (90%)** |||||
| 58 | TS-UA-DOC-UC-001 | Upload Document Use Case | 12 | 95% | 🔴 P0 |
| 59 | TS-UA-DOC-UC-002 | Extract Clauses Use Case | 14 | 95% | 🔴 P0 |
| 60 | TS-UA-DOC-UC-003 | Extract Entities Use Case | 12 | 90% | 🟠 P1 |
| 61 | TS-UA-COH-UC-001 | Calculate Coherence Use Case | 16 | 98% | 🔴 P0 |
| 62 | TS-UA-COH-UC-002 | Recalculate on Alert Use Case | 10 | 95% | 🟠 P1 |
| 63 | TS-UA-PRJ-UC-001 | Generate WBS Use Case | 12 | 90% | 🟠 P1 |
| 64 | TS-UA-PRJ-UC-002 | CRUD WBS Item Use Case | 14 | 90% | 🟠 P1 |
| 65 | TS-UA-PROC-UC-001 | Generate BOM Use Case | 10 | 90% | 🟠 P1 |
| 66 | TS-UA-PROC-UC-002 | Calculate Lead Time Use Case | 12 | 95% | 🔴 P0 |
| 67 | TS-UA-STK-UC-001 | Extract Stakeholders Use Case | 10 | 90% | 🟠 P1 |
| 68 | TS-UA-STK-UC-002 | Generate RACI Use Case | 10 | 90% | 🟠 P1 |
| 69 | TS-UA-ANA-UC-001 | Run Analysis Use Case | 12 | 90% | 🟠 P1 |
| 70 | TS-UA-ANA-UC-002 | Graph Query Use Case | 10 | 85% | 🟡 P2 |
| 71 | TS-UA-SEC-UC-001 | Validate MCP Operation Use Case | 10 | 100% | 🔴 P0 |
| 72 | TS-UA-SEC-UC-002 | Anonymize Document Use Case | 12 | 100% | 🔴 P0 |
| **SUBTOTAL USE CASES** | | | **176** | **93%** | |
| **APPLICATION - SERVICES (88%)** |||||
| 73 | TS-UA-SVC-EXT-001 | Clause Extraction Service | 14 | 95% | 🔴 P0 |
| 74 | TS-UA-SVC-EXT-002 | Entity Extraction Service | 12 | 90% | 🟠 P1 |
| 75 | TS-UA-SVC-COH-001 | Coherence Calculation Service | 14 | 98% | 🔴 P0 |
| 76 | TS-UA-SVC-PII-001 | PII Detection Service | 16 | 100% | 🔴 P0 |
| 77 | TS-UA-SVC-ANO-001 | Anonymization Service | 12 | 100% | 🔴 P0 |
| 78 | TS-UA-SVC-RTL-001 | Rate Limit Service | 10 | 100% | 🔴 P0 |
| 79 | TS-UA-SVC-BDG-001 | Budget Tracking Service | 12 | 95% | 🟠 P1 |
| **SUBTOTAL SERVICES** | | | **90** | **96%** | |
| **APPLICATION - DTOs (95%)** |||||
| 80 | TS-UA-DTO-ALL-001 | All DTOs Validation | 24 | 98% | 🔴 P0 |
| 81 | TS-UA-DTO-SER-001 | Serialization/Deserialization | 16 | 95% | 🟠 P1 |
| **SUBTOTAL DTOs** | | | **40** | **96%** | |
| **ADAPTERS - HTTP (85%)** |||||
| 82 | TS-UAD-HTTP-RTR-001 | All Routers Validation | 32 | 90% | 🟠 P1 |
| 83 | TS-UAD-HTTP-MDW-001 | Middleware (Auth, Tenant) | 18 | 95% | 🔴 P0 |
| 84 | TS-UAD-HTTP-ERR-001 | Error Handlers | 12 | 90% | 🟠 P1 |
| **SUBTOTAL HTTP** | | | **62** | **91%** | |
| **ADAPTERS - PERSISTENCE (85%)** |||||
| 85 | TS-UAD-PER-REP-001 | All Repositories | 28 | 90% | 🟠 P1 |
| 86 | TS-UAD-PER-GRP-001 | Graph Adapters (Neo4j) | 14 | 85% | 🟠 P1 |
| 87 | TS-UAD-PER-RDS-001 | Redis Adapters | 10 | 90% | 🟠 P1 |
| 88 | TS-UAD-PER-R2-001 | R2 Storage Adapters | 8 | 85% | 🟡 P2 |
| **SUBTOTAL PERSISTENCE** | | | **60** | **87%** | |
| **INTEGRATION (90%)** |||||
| 89 | TS-INT-DB-CLS-001 | Clause Repository + DB | 14 | 95% | 🔴 P0 |
| 90 | TS-INT-DB-DOC-001 | Document Repository + DB | 12 | 90% | 🟠 P1 |
| 91 | TS-INT-DB-WBS-001 | WBS Repository + DB | 12 | 90% | 🟠 P1 |
| 92 | TS-INT-DB-BOM-001 | BOM Repository + DB | 10 | 90% | 🟠 P1 |
| 93 | TS-INT-DB-COH-001 | Coherence Repository + DB | 12 | 95% | 🔴 P0 |
| 94 | TS-INT-DB-AUD-001 | Audit Repository + DB | 10 | 95% | 🟠 P1 |
| 95 | TS-INT-EXT-LLM-001 | LLM Client Integration | 14 | 85% | 🟠 P1 |
| 96 | TS-INT-EXT-LLM-002 | LLM Fallback Integration | 10 | 90% | 🟠 P1 |
| 97 | TS-INT-GRP-NEO-001 | Neo4j Integration | 14 | 85% | 🟠 P1 |
| 98 | TS-INT-MOD-WBS-001 | WBS → Procurement Integration | 12 | 95% | 🔴 P0 |
| 99 | TS-INT-MOD-DOC-001 | Documents → Analysis Integration | 10 | 90% | 🟠 P1 |
| 100 | TS-INT-MOD-ANA-001 | Analysis → Coherence Integration | 12 | 95% | 🔴 P0 |
| 101 | TS-INT-MOD-STK-001 | Stakeholders → RACI Integration | 8 | 85% | 🟡 P2 |
| 102 | TS-INT-EVT-BUS-001 | Event Bus Publish/Subscribe | 14 | 95% | 🔴 P0 |
| 103 | TS-INT-EVT-CEL-001 | Celery Job Queue | 12 | 90% | 🟠 P1 |
| 104 | TS-INT-EVT-DLQ-001 | Dead Letter Queue | 8 | 85% | 🟡 P2 |
| **SUBTOTAL INTEGRATION** | | | **184** | **91%** | |
| **E2E (80%)** |||||
| 105 | TS-E2E-FLW-DOC-001 | Document Upload to Coherence | 12 | 85% | 🔴 P0 |
| 106 | TS-E2E-FLW-ALR-001 | Alert Review Workflow | 10 | 85% | 🟠 P1 |
| 107 | TS-E2E-FLW-BLK-001 | Bulk Operations | 8 | 80% | 🟠 P1 |
| 108 | TS-E2E-SEC-TNT-001 | Multi-tenant Isolation | 10 | 90% | 🔴 P0 |
| 109 | TS-E2E-SEC-MCP-001 | MCP Gateway E2E | 8 | 90% | 🔴 P0 |
| 110 | TS-E2E-ERR-TIM-001 | Timeout & Fallback Scenarios | 8 | 80% | 🟠 P1 |
| 111 | TS-E2E-ERR-CON-001 | Concurrent Modifications | 8 | 80% | 🟠 P1 |
| 112 | TS-E2E-ERR-REC-001 | Error Recovery | 8 | 80% | 🟠 P1 |
| 113 | TS-E2E-PER-LRG-001 | Large Document Processing | 6 | 75% | 🟡 P2 |
| **SUBTOTAL E2E** | | | **78** | **83%** | |

### 2.3 Totales por Categoría

| Categoría | Suites | Tests | Cobertura Promedio |
|-----------|--------|-------|-------------------|
| **CORE (Security)** | 11 | 156 | 100% |
| **Domain - Documents** | 9 | 120 | 95% |
| **Domain - Coherence** | 12 | 156 | 98% |
| **Domain - Projects** | 6 | 76 | 92% |
| **Domain - Procurement** | 7 | 82 | 92% |
| **Domain - Stakeholders** | 7 | 78 | 90% |
| **Domain - Analysis** | 5 | 48 | 89% |
| **Application - Use Cases** | 15 | 176 | 93% |
| **Application - Services** | 7 | 90 | 96% |
| **Application - DTOs** | 2 | 40 | 96% |
| **Adapters - HTTP** | 3 | 62 | 91% |
| **Adapters - Persistence** | 4 | 60 | 87% |
| **Integration** | 16 | 184 | 91% |
| **E2E** | 9 | 78 | 83% |
| **TOTAL** | **113** | **1,406** | **92%** |

---

## 3. Test Suites CORE (100% Cobertura)

### 3.1 TS-UC-SEC-MCP-001: MCP Gateway Allowlist (18 tests)

```
Suite: MCP Gateway Allowlist Validation
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS UNITARIOS:
├── test_001_view_operation_projects_summary_allowed
├── test_002_view_operation_alerts_active_allowed
├── test_003_view_operation_coherence_latest_allowed
├── test_004_view_operation_documents_metadata_allowed
├── test_005_view_operation_stakeholders_list_allowed
├── test_006_view_operation_wbs_structure_allowed
├── test_007_view_operation_bom_items_allowed
├── test_008_view_operation_audit_recent_allowed
├── test_009_function_operation_create_alert_allowed
├── test_010_function_operation_update_score_allowed
├── test_011_function_operation_flag_review_allowed
├── test_012_function_operation_add_note_allowed
├── test_013_function_operation_trigger_recalc_allowed
├── test_014_unknown_operation_blocked
├── test_015_destructive_operation_delete_all_blocked
├── test_016_destructive_operation_drop_table_blocked
├── test_017_tenant_extended_allowlist_custom_operation
└── test_018_tenant_restricted_allowlist_blocked

EDGE CASES:
├── test_edge_001_empty_operation_name
├── test_edge_002_null_tenant_id
├── test_edge_003_case_insensitive_operation
└── test_edge_004_whitespace_in_operation
```

### 3.2 TS-UC-SEC-MCP-002: MCP Gateway Rate Limiting (14 tests)

```
Suite: MCP Gateway Rate Limiting
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS UNITARIOS:
├── test_001_request_under_limit_allowed
├── test_002_request_at_limit_59_allowed
├── test_003_request_at_limit_60_allowed
├── test_004_request_over_limit_61_blocked
├── test_005_request_over_limit_100_blocked
├── test_006_window_reset_after_60_seconds
├── test_007_tenant_isolation_separate_counters
├── test_008_tenant_a_full_tenant_b_available
├── test_009_sliding_window_calculation
├── test_010_rate_limit_result_retry_after_header
├── test_011_rate_limit_audit_log_on_block
├── test_012_rate_limit_warning_at_80_percent
├── test_013_concurrent_requests_race_condition
└── test_014_rate_limit_reset_at_midnight

EDGE CASES:
├── test_edge_001_burst_59_requests_simultaneous
├── test_edge_002_exactly_60_second_boundary
└── test_edge_003_clock_skew_handling
```

### 3.3 TS-UC-SEC-MCP-003: MCP Gateway Query Limits (12 tests)

```
Suite: MCP Gateway Query Limits
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS UNITARIOS:
├── test_001_query_under_5s_allowed
├── test_002_query_at_5s_allowed
├── test_003_query_over_5s_timeout_cancelled
├── test_004_query_result_under_1000_rows_allowed
├── test_005_query_result_at_1000_rows_allowed
├── test_006_query_result_over_1000_rows_truncated
├── test_007_query_result_truncated_flag_set
├── test_008_timeout_returns_partial_results
├── test_009_timeout_audit_log_created
├── test_010_row_limit_audit_log_created
├── test_011_combined_timeout_and_row_limit
└── test_012_query_limit_config_per_tenant

EDGE CASES:
├── test_edge_001_exactly_1000_rows
├── test_edge_002_empty_result_set
└── test_edge_003_streaming_query_timeout
```

### 3.4 TS-UC-SEC-ANO-001: Anonymizer PII Detection (24 tests)

```
Suite: Anonymizer PII Detection
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS DNI/NIF (6):
├── test_001_detect_dni_valid_12345678Z
├── test_002_detect_dni_valid_87654321X
├── test_003_detect_dni_invalid_length_9_digits
├── test_004_detect_dni_invalid_length_7_digits
├── test_005_detect_dni_invalid_letter_checksum
├── test_006_detect_multiple_dnis_in_text

TESTS EMAIL (5):
├── test_007_detect_email_simple
├── test_008_detect_email_with_subdomain
├── test_009_detect_email_with_plus_sign
├── test_010_detect_email_invalid_no_at
├── test_011_detect_multiple_emails_in_text

TESTS PHONE (5):
├── test_012_detect_phone_mobile_612345678
├── test_013_detect_phone_mobile_with_prefix_34
├── test_014_detect_phone_landline_912345678
├── test_015_detect_phone_invalid_short
├── test_016_detect_multiple_phones_in_text

TESTS IBAN (4):
├── test_017_detect_iban_spain_valid
├── test_018_detect_iban_germany_valid
├── test_019_detect_iban_invalid_checksum
├── test_020_detect_iban_invalid_length

TESTS COMBINED (4):
├── test_021_detect_all_pii_types_in_document
├── test_022_detect_no_pii_clean_document
├── test_023_detect_pii_positions_returned
└── test_024_detect_pii_counts_by_type

EDGE CASES:
├── test_edge_001_pii_in_different_languages
├── test_edge_002_pii_with_unicode_characters
└── test_edge_003_pii_in_html_escaped_text
```

### 3.5 TS-UC-SEC-ANO-002: Anonymizer Strategies (16 tests)

```
Suite: Anonymizer Strategies
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS REDACT (4):
├── test_001_redact_dni_to_redacted
├── test_002_redact_email_to_redacted
├── test_003_redact_phone_to_redacted
├── test_004_redact_multiple_pii_all_redacted

TESTS HASH (4):
├── test_005_hash_dni_deterministic
├── test_006_hash_same_value_same_hash
├── test_007_hash_different_values_different_hash
├── test_008_hash_irreversible_validation

TESTS PSEUDONYMIZE (4):
├── test_009_pseudonymize_name_to_persona_001
├── test_010_pseudonymize_consistent_same_name
├── test_011_pseudonymize_different_names_different_ids
├── test_012_pseudonymize_in_context_preserved

TESTS STRATEGY SELECTION (4):
├── test_013_strategy_by_pii_type_default
├── test_014_strategy_by_tenant_config
├── test_015_strategy_mixed_per_type
└── test_016_strategy_none_keeps_original

EDGE CASES:
├── test_edge_001_nested_pii_in_pii
├── test_edge_002_overlapping_pii_positions
└── test_edge_003_empty_text_no_error
```

### 3.6 TS-UC-SEC-GAM-001: Anti-Gaming Detection (12 tests)

```
Suite: Anti-Gaming Detection
Target Coverage: 100%
Prioridad: 🔴 P0 CRÍTICO

TESTS MASS CHANGES (3):
├── test_001_mass_changes_11_in_hour_detected
├── test_002_mass_changes_10_in_hour_allowed
├── test_003_mass_changes_window_reset

TESTS RESOLVE-REINTRODUCE (3):
├── test_004_resolve_reintroduce_3_times_detected
├── test_005_resolve_reintroduce_2_times_allowed
├── test_006_resolve_reintroduce_different_hash_allowed

TESTS SUSPICIOUS HIGH SCORE (3):
├── test_007_high_score_few_docs_detected
├── test_008_high_score_many_docs_allowed
├── test_009_high_score_threshold_boundary

TESTS WEIGHT MANIPULATION (3):
├── test_010_weight_change_25_percent_detected
├── test_011_weight_change_15_percent_allowed
├── test_012_weight_change_tracking_24h_window

EDGE CASES:
├── test_edge_001_multiple_violations_combined
├── test_edge_002_violation_penalty_application
└── test_edge_003_violation_audit_logging
```

---

## 4. Test Suites por Módulo de Dominio

### 4.1 DOCUMENTS Domain (120 tests)

#### TS-UD-DOC-CLS-001: Clause Entity (22 tests)

```
TESTS DE CREACIÓN (6):
├── test_001_clause_creation_with_all_fields
├── test_002_clause_creation_minimum_fields
├── test_003_clause_creation_fails_without_content
├── test_004_clause_creation_fails_without_document_id
├── test_005_clause_creation_fails_without_tenant_id
├── test_006_clause_immutability_after_creation

TESTS DE VALIDACIÓN (6):
├── test_007_clause_number_format_primera
├── test_008_clause_number_format_numeric
├── test_009_clause_number_format_decimal
├── test_010_clause_number_normalization
├── test_011_clause_content_max_length
├── test_012_clause_content_empty_rejected

TESTS DE FK INTEGRITY (6):
├── test_013_clause_document_fk_valid
├── test_014_clause_document_fk_invalid_rejected
├── test_015_clause_tenant_fk_valid
├── test_016_clause_tenant_fk_invalid_rejected
├── test_017_clause_on_delete_restrict_document
├── test_018_clause_on_delete_restrict_tenant

TESTS DE EMBEDDING (4):
├── test_019_clause_embedding_vector_size
├── test_020_clause_embedding_generation
├── test_021_clause_embedding_null_allowed
└── test_022_clause_embedding_update
```

#### TS-UD-DOC-ENT-001: Entity Extraction - Dates (16 tests)

```
TESTS FORMATO EXPLÍCITO (4):
├── test_001_date_dd_mm_yyyy_slash
├── test_002_date_yyyy_mm_dd_dash
├── test_003_date_dd_month_yyyy_spanish
├── test_004_date_month_dd_yyyy_english

TESTS FORMATO RELATIVO (4):
├── test_005_date_relative_30_days
├── test_006_date_relative_3_months
├── test_007_date_relative_1_year
├── test_008_date_relative_from_date

TESTS CONTEXTO (4):
├── test_009_date_context_entrega
├── test_010_date_context_firma
├── test_011_date_context_inicio
├── test_012_date_context_fin

TESTS MÚLTIPLES (4):
├── test_013_multiple_dates_extraction
├── test_014_multiple_dates_ordering
├── test_015_date_range_extraction
└── test_016_date_invalid_format_ignored
```

#### TS-UD-DOC-ENT-002: Entity Extraction - Money (14 tests)

```
TESTS FORMATO EUR (4):
├── test_001_money_eur_symbol_suffix
├── test_002_money_eur_symbol_prefix
├── test_003_money_eur_word_euros
├── test_004_money_eur_thousands_separator

TESTS FORMATO USD (3):
├── test_005_money_usd_symbol
├── test_006_money_usd_word
├── test_007_money_usd_thousands_separator

TESTS CONTEXTO (4):
├── test_008_money_context_anticipo
├── test_009_money_context_pago_final
├── test_010_money_context_penalizacion
├── test_011_money_context_total

TESTS MÚLTIPLES (3):
├── test_012_multiple_amounts_extraction
├── test_013_money_percentage_extraction
└── test_014_money_negative_amount
```

### 4.2 COHERENCE Domain (156 tests)

#### TS-UD-COH-RUL-001: Rules Engine - SCOPE (18 tests)

```
REGLA R11 - WBS SIN ACTIVIDADES (6):
├── test_001_r11_wbs_level4_no_activities_alert
├── test_002_r11_wbs_level4_with_activities_pass
├── test_003_r11_wbs_level3_no_activities_ignored
├── test_004_r11_wbs_level2_no_activities_ignored
├── test_005_r11_multiple_wbs_level4_violations
├── test_006_r11_alert_severity_medium

REGLA R12 - WBS SIN PARTIDAS (6):
├── test_007_r12_wbs_no_budget_line_alert
├── test_008_r12_wbs_with_budget_line_pass
├── test_009_r12_wbs_budget_zero_warning
├── test_010_r12_multiple_wbs_violations
├── test_011_r12_alert_severity_high
├── test_012_r12_affected_entities_list

REGLA R13 - ALCANCE NO CUBIERTO (6):
├── test_013_r13_scope_clause_no_wbs_alert
├── test_014_r13_scope_clause_with_wbs_pass
├── test_015_r13_partial_coverage_calculation
├── test_016_r13_coverage_percentage_80
├── test_017_r13_uncovered_clauses_list
└── test_018_r13_alert_severity_high
```

#### TS-UD-COH-RUL-002: Rules Engine - BUDGET (16 tests)

```
REGLA R6 - SUMA PARTIDAS ≠ CONTRATO (6):
├── test_001_r6_deviation_10_percent_alert
├── test_002_r6_deviation_5_percent_pass
├── test_003_r6_deviation_4_9_percent_pass
├── test_004_r6_over_budget_critical
├── test_005_r6_under_budget_warning
├── test_006_r6_exact_match_pass

REGLA R15 - BOM SIN PARTIDA (5):
├── test_007_r15_bom_no_budget_alert
├── test_008_r15_bom_with_budget_pass
├── test_009_r15_bom_client_provided_exception
├── test_010_r15_multiple_bom_violations
├── test_011_r15_affected_items_list

REGLA R16 - DESVIACIÓN >10% (5):
├── test_012_r16_deviation_11_percent_alert
├── test_013_r16_deviation_10_percent_pass
├── test_014_r16_over_budget_critical
├── test_015_r16_under_budget_different_severity
└── test_016_r16_trend_calculation
```

#### TS-UD-COH-RUL-003: Rules Engine - TIME (16 tests)

```
REGLA R1 - PLAZO ≠ CRONOGRAMA (5):
├── test_001_r1_dates_mismatch_alert
├── test_002_r1_dates_match_pass
├── test_003_r1_schedule_late_critical
├── test_004_r1_schedule_early_warning
├── test_005_r1_delta_days_calculation

REGLA R2 - HITO SIN ACTIVIDAD (5):
├── test_006_r2_milestone_no_activity_alert
├── test_007_r2_milestone_with_activity_pass
├── test_008_r2_milestone_date_mismatch_alert
├── test_009_r2_multiple_milestones_violations
├── test_010_r2_unlinked_milestones_list

REGLA R5 - CRONOGRAMA EXCEDE (4):
├── test_011_r5_activity_exceeds_contract_alert
├── test_012_r5_activity_within_contract_pass
├── test_013_r5_exceeding_activities_list
├── test_014_r5_alert_severity_critical

REGLA R14 - FECHA PEDIDO TARDÍA (2):
├── test_015_r14_order_date_passed_critical
└── test_016_r14_order_date_tight_warning
```

#### TS-UD-COH-SCR-001: Score Calculator - SubScores (14 tests)

```
TESTS CÁLCULO BÁSICO (6):
├── test_001_subscore_no_alerts_100_percent
├── test_002_subscore_one_alert_penalized
├── test_003_subscore_multiple_alerts_cumulative
├── test_004_subscore_severity_low_penalty_5
├── test_005_subscore_severity_medium_penalty_10
├── test_006_subscore_severity_high_penalty_20
├── test_007_subscore_severity_critical_penalty_30

TESTS POR CATEGORÍA (6):
├── test_008_subscore_scope_calculation
├── test_009_subscore_budget_calculation
├── test_010_subscore_quality_calculation
├── test_011_subscore_technical_calculation
├── test_012_subscore_legal_calculation
├── test_013_subscore_time_calculation

TESTS EDGE CASES (1):
└── test_014_subscore_floor_at_zero
```

#### TS-UD-COH-SCR-002: Score Calculator - Global (12 tests)

```
TESTS FÓRMULA (6):
├── test_001_global_score_formula_verification
├── test_002_global_score_default_weights
├── test_003_global_score_all_100_equals_100
├── test_004_global_score_all_0_equals_0
├── test_005_global_score_mixed_subscores
├── test_006_global_score_range_0_to_100

TESTS PESOS (6):
├── test_007_weights_sum_validation
├── test_008_weights_normalization_auto
├── test_009_weights_custom_budget_30
├── test_010_weights_custom_time_25
├── test_011_weights_per_project_type
└── test_012_weights_history_tracking
```

#### TS-UD-COH-GAM-001: Anti-Gaming Policy (16 tests)

```
MASS CHANGES (4):
├── test_001_detect_mass_changes_15_in_30min
├── test_002_no_violation_10_in_60min
├── test_003_mass_changes_window_sliding
├── test_004_mass_changes_flag_for_review

RESOLVE-REINTRODUCE (4):
├── test_005_detect_resolve_reintroduce_4_times
├── test_006_no_violation_2_times
├── test_007_hash_comparison_same_content
├── test_008_penalty_minus_5_points

SUSPICIOUS HIGH SCORE (4):
├── test_009_detect_95_percent_3_docs
├── test_010_no_violation_95_percent_50_docs
├── test_011_threshold_90_percent_5_docs
├── test_012_require_audit_action

WEIGHT MANIPULATION (4):
├── test_013_detect_weight_change_25_percent
├── test_014_no_violation_change_15_percent
├── test_015_24h_window_tracking
└── test_016_notify_admin_action
```

### 4.3 PROJECTS Domain (76 tests)

#### TS-UD-PRJ-WBS-001: WBS Item Entity (18 tests)

```
CREACIÓN (6):
├── test_001_wbs_item_creation_all_fields
├── test_002_wbs_item_creation_minimum_fields
├── test_003_wbs_item_fails_without_code
├── test_004_wbs_item_fails_without_name
├── test_005_wbs_item_fails_invalid_level
├── test_006_wbs_item_immutability

VALIDACIÓN CODE (6):
├── test_007_wbs_code_format_1
├── test_008_wbs_code_format_1_1
├── test_009_wbs_code_format_1_1_1
├── test_010_wbs_code_format_1_1_1_1
├── test_011_wbs_code_invalid_format_rejected
├── test_012_wbs_code_uniqueness_per_project

VALIDACIÓN LEVEL (6):
├── test_013_wbs_level_1_valid
├── test_014_wbs_level_4_valid
├── test_015_wbs_level_0_invalid
├── test_016_wbs_level_5_invalid
├── test_017_wbs_level_matches_code_depth
└── test_018_wbs_level_parent_child_validation
```

### 4.4 PROCUREMENT Domain (82 tests)

#### TS-UD-PROC-LTM-001: Lead Time Calculator - Basic (16 tests)

```
CÁLCULO BÁSICO (6):
├── test_001_optimal_date_production_only
├── test_002_optimal_date_production_transit
├── test_003_optimal_date_production_transit_buffer
├── test_004_optimal_date_all_components
├── test_005_lead_time_breakdown_returned
├── test_006_required_on_site_calculation

DÍAS HÁBILES (5):
├── test_007_business_days_calculation
├── test_008_weekend_exclusion
├── test_009_holiday_exclusion
├── test_010_delivery_on_weekend_adjusted
├── test_011_mixed_calendar_business_days

ALERTAS (5):
├── test_012_alert_r14_date_passed
├── test_013_alert_r14_tight_margin_3_days
├── test_014_alert_severity_critical_passed
├── test_015_alert_severity_warning_tight
└── test_016_no_alert_sufficient_margin
```

#### TS-UD-PROC-LTM-002: Lead Time Calculator - Incoterms (14 tests)

```
INCOTERM EXW (3):
├── test_001_exw_buyer_full_responsibility
├── test_002_exw_transit_time_included
├── test_003_exw_customs_included

INCOTERM FOB (3):
├── test_004_fob_shared_responsibility
├── test_005_fob_port_handover
├── test_006_fob_insurance_buyer

INCOTERM CIF (3):
├── test_007_cif_seller_insurance
├── test_008_cif_port_to_port
├── test_009_cif_customs_buyer

INCOTERM DDP (3):
├── test_010_ddp_seller_full_responsibility
├── test_011_ddp_no_customs_buyer
├── test_012_ddp_door_to_door

COMPARACIÓN (2):
├── test_013_incoterm_comparison_same_route
└── test_014_incoterm_impact_on_lead_time
```

---

 RELEASE READY
```

---

## 9. Detalle de Test Suites por Agente

### 9.1 AGENTE 1: Security Core (188 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 1: SECURITY CORE                              ║
║                          Target Coverage: 100%                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── MCP Gateway (Allowlist, Rate Limit, Query Limits, Audit)                ║
║  ├── Anonymizer Service (PII Detection, Strategies, Config)                  ║
║  ├── Tenant Isolation                                                        ║
║  ├── JWT Validation                                                          ║
║  └── Anti-Gaming Detection (compartido con Agente 6)                         ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UC-SEC-MCP-001: MCP Allowlist ............... 18 tests               ║
║  ├── TS-UC-SEC-MCP-002: Rate Limiting ............... 14 tests               ║
║  ├── TS-UC-SEC-MCP-003: Query Limits ................ 12 tests               ║
║  ├── TS-UC-SEC-MCP-004: MCP Audit ................... 10 tests               ║
║  ├── TS-UC-SEC-ANO-001: PII Detection ............... 24 tests               ║
║  ├── TS-UC-SEC-ANO-002: Anonymizer Strategies ....... 16 tests               ║
║  ├── TS-UC-SEC-ANO-003: Tenant Config ............... 8 tests                ║
║  ├── TS-UC-SEC-TNT-001: Tenant Isolation ............ 14 tests               ║
║  ├── TS-UC-SEC-JWT-001: JWT Validation .............. 12 tests               ║
║  ├── TS-UC-SEC-AUD-001: Audit Trail Core ............ 16 tests               ║
║  ├── TS-UC-SEC-GAM-001: Anti-Gaming Detection ....... 12 tests               ║
║  ├── TS-INT-* Integration tests ..................... 30 tests               ║
║  └── TS-E2E-SEC-* E2E tests ......................... 26 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 1: 188 tests                                               ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S1-S2 (Semanas 1-4)                                      ║
║  DEPENDENCIAS: Ninguna (puede empezar inmediatamente)                        ║
║  DESBLOQUEA: Todos los demás módulos                                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.2 AGENTE 2: Documents Domain (162 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 2: DOCUMENTS DOMAIN                           ║
║                          Target Coverage: 95%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Clause Entity (creación, validación, FK integrity)                      ║
║  ├── Clause Types & Classification                                           ║
║  ├── SubClause Hierarchy                                                     ║
║  ├── Entity Extraction (Dates, Money, Durations, Stakeholders)               ║
║  ├── Document Entity                                                         ║
║  └── Confidence Scoring                                                      ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-DOC-CLS-001: Clause Entity ............... 22 tests               ║
║  ├── TS-UD-DOC-CLS-002: Clause Types ................ 14 tests               ║
║  ├── TS-UD-DOC-CLS-003: SubClause Hierarchy ......... 10 tests               ║
║  ├── TS-UD-DOC-ENT-001: Entity Dates ................ 16 tests               ║
║  ├── TS-UD-DOC-ENT-002: Entity Money ................ 14 tests               ║
║  ├── TS-UD-DOC-ENT-003: Entity Durations ............ 12 tests               ║
║  ├── TS-UD-DOC-ENT-004: Entity Stakeholders ......... 10 tests               ║
║  ├── TS-UD-DOC-DOC-001: Document Entity ............. 14 tests               ║
║  ├── TS-UD-DOC-CNF-001: Confidence Scoring .......... 8 tests                ║
║  ├── TS-UA-DOC-UC-*: Use Cases ...................... 26 tests               ║
║  ├── TS-UA-SVC-EXT-*: Services ...................... 26 tests               ║
║  ├── TS-INT-DB-DOC-*: Integration ................... 26 tests               ║
║  └── TS-E2E-FLW-DOC-*: E2E .......................... 14 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 2: 162 tests                                               ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S3-S4 (Semanas 5-8)                                      ║
║  DEPENDENCIAS: Agente 1 (Anonymizer para PII en documentos)                  ║
║  DESBLOQUEA: Agentes 5, 6, 7 (Analysis, Coherence, Stakeholders)             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.3 AGENTE 3: Projects & WBS (116 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 3: PROJECTS & WBS                             ║
║                          Target Coverage: 93%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── WBS Item Entity                                                         ║
║  ├── WBS Hierarchy & Codes                                                   ║
║  ├── WBS Validation Rules                                                    ║
║  ├── WBS CRUD Operations                                                     ║
║  ├── Project Entity                                                          ║
║  └── IWBSQueryPort (interface para otros módulos)                            ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-PRJ-WBS-001: WBS Item Entity ............. 18 tests               ║
║  ├── TS-UD-PRJ-WBS-002: WBS Hierarchy ............... 14 tests               ║
║  ├── TS-UD-PRJ-WBS-003: WBS Validation .............. 12 tests               ║
║  ├── TS-UD-PRJ-WBS-004: WBS CRUD .................... 10 tests               ║
║  ├── TS-UD-PRJ-PRJ-001: Project Entity .............. 12 tests               ║
║  ├── TS-UD-PRJ-DTO-001: WBSItemDTO & Port ........... 10 tests               ║
║  ├── TS-UA-PRJ-UC-*: Use Cases ...................... 26 tests               ║
║  ├── TS-INT-DB-WBS-*: Integration ................... 18 tests               ║
║  └── TS-E2E-*: E2E ................................... 10 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 3: 116 tests (ajustado de 130 anterior)                    ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S7 (Semanas 13-14)                                       ║
║  DEPENDENCIAS: Agente 2 (Clauses para WBS)                                   ║
║  DESBLOQUEA: Agente 4 (Procurement), Agente 6 (Reglas SCOPE)                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.4 AGENTE 4: Procurement Logic (116 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 4: PROCUREMENT LOGIC                          ║
║                          Target Coverage: 93%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── BOM Item Entity                                                         ║
║  ├── BOM Validation Rules                                                    ║
║  ├── Lead Time Calculator (Basic, Incoterms, Customs, Alerts)                ║
║  └── Procurement Plan Generation                                             ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-PROC-BOM-001: BOM Item Entity ............ 14 tests               ║
║  ├── TS-UD-PROC-BOM-002: BOM Validation ............. 10 tests               ║
║  ├── TS-UD-PROC-LTM-001: Lead Time Basic ............ 16 tests               ║
║  ├── TS-UD-PROC-LTM-002: Lead Time Incoterms ........ 14 tests               ║
║  ├── TS-UD-PROC-LTM-003: Lead Time Customs .......... 10 tests               ║
║  ├── TS-UD-PROC-LTM-004: Lead Time Alerts ........... 8 tests                ║
║  ├── TS-UD-PROC-PLN-001: Procurement Plan ........... 10 tests               ║
║  ├── TS-UA-PROC-UC-*: Use Cases ..................... 22 tests               ║
║  ├── TS-INT-DB-BOM-*: Integration ................... 16 tests               ║
║  └── TS-E2E-*: E2E ................................... 8 tests                ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 4: 116 tests (ajustado)                                    ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S8 (Semanas 15-16)                                       ║
║  DEPENDENCIAS: Agente 3 (WBS para BOM)                                       ║
║  DESBLOQUEA: Agente 6 (Reglas BUDGET, R14)                                   ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.5 AGENTE 5: Analysis & Graph (78 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 5: ANALYSIS & GRAPH                           ║
║                          Target Coverage: 89%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Alert Entity                                                            ║
║  ├── Graph Node Entity                                                       ║
║  ├── Graph Relationship Entity                                               ║
║  ├── Semantic Search                                                         ║
║  ├── Hybrid Search                                                           ║
║  └── Neo4j Integration                                                       ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-ANA-ALR-001: Alert Entity ................ 12 tests               ║
║  ├── TS-UD-ANA-GRP-001: Graph Node .................. 10 tests               ║
║  ├── TS-UD-ANA-GRP-002: Graph Relationship .......... 10 tests               ║
║  ├── TS-UD-ANA-SRC-001: Semantic Search ............. 8 tests                ║
║  ├── TS-UD-ANA-HYB-001: Hybrid Search ............... 8 tests                ║
║  ├── TS-UA-ANA-UC-*: Use Cases ...................... 22 tests               ║
║  ├── TS-INT-GRP-NEO-001: Neo4j Integration .......... 14 tests               ║
║  └── TS-E2E-*: E2E ................................... 6 tests                ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 5: 78 tests (ajustado)                                     ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S10 (Semanas 19-20)                                      ║
║  DEPENDENCIAS: Agente 2 (Clauses para Graph)                                 ║
║  DESBLOQUEA: Agente 6 (Coherence necesita Alerts)                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.6 AGENTE 6: Coherence Engine - CRÍTICO (206 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     AGENTE 6: COHERENCE ENGINE (CRÍTICO)                      ║
║                          Target Coverage: 99%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Category Enum & Default Weights                                         ║
║  ├── Rules Engine (17 reglas en 6 categorías)                                ║
║  │   ├── SCOPE: R11, R12, R13                                                ║
║  │   ├── BUDGET: R6, R15, R16                                                ║
║  │   ├── TIME: R1, R2, R5, R14                                               ║
║  │   ├── TECHNICAL: R3, R4, R7                                               ║
║  │   ├── LEGAL: R8, R20                                                      ║
║  │   └── QUALITY: R17, R18                                                   ║
║  ├── Score Calculator (SubScores, Global, Custom Weights)                    ║
║  ├── Anti-Gaming Policy                                                      ║
║  └── Alert Entity & Category Mapping                                         ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-COH-CAT-001: Categories .................. 12 tests               ║
║  ├── TS-UD-COH-RUL-001: Rules SCOPE ................. 18 tests               ║
║  ├── TS-UD-COH-RUL-002: Rules BUDGET ................ 16 tests               ║
║  ├── TS-UD-COH-RUL-003: Rules TIME .................. 16 tests               ║
║  ├── TS-UD-COH-RUL-004: Rules TECHNICAL ............. 12 tests               ║
║  ├── TS-UD-COH-RUL-005: Rules LEGAL ................. 10 tests               ║
║  ├── TS-UD-COH-RUL-006: Rules QUALITY ............... 8 tests                ║
║  ├── TS-UD-COH-SCR-001: SubScores ................... 14 tests               ║
║  ├── TS-UD-COH-SCR-002: Global Score ................ 12 tests               ║
║  ├── TS-UD-COH-SCR-003: Custom Weights .............. 10 tests               ║
║  ├── TS-UD-COH-GAM-001: Anti-Gaming ................. 16 tests               ║
║  ├── TS-UD-COH-ALR-001: Alert Mapping ............... 12 tests               ║
║  ├── TS-UA-COH-UC-*: Use Cases ...................... 26 tests               ║
║  ├── TS-UA-SVC-COH-*: Services ...................... 14 tests               ║
║  ├── TS-INT-DB-COH-*: Integration ................... 12 tests               ║
║  └── TS-E2E-*: E2E ................................... 18 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 6: 206 tests                                               ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S5-S6 (Semanas 9-12) - PRIORIDAD MÁXIMA                  ║
║  DEPENDENCIAS: Agentes 2, 3, 4, 5 (para datos de reglas)                     ║
║  DESBLOQUEA: E2E completo, Dashboard, Release                                ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.7 AGENTE 7: Stakeholders (112 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 7: STAKEHOLDERS                               ║
║                          Target Coverage: 91%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Stakeholder Entity                                                      ║
║  ├── Power/Interest Classification                                           ║
║  ├── Quadrant Assignment                                                     ║
║  ├── RACI Entry Validation                                                   ║
║  ├── RACI Matrix Generation                                                  ║
║  ├── RACI from Clauses                                                       ║
║  └── Stakeholder Map Data                                                    ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UD-STK-ENT-001: Stakeholder Entity .......... 12 tests               ║
║  ├── TS-UD-STK-CLS-001: Power/Interest .............. 14 tests               ║
║  ├── TS-UD-STK-CLS-002: Quadrant Assignment ......... 10 tests               ║
║  ├── TS-UD-STK-RAC-001: RACI Entry .................. 10 tests               ║
║  ├── TS-UD-STK-RAC-002: RACI Matrix ................. 14 tests               ║
║  ├── TS-UD-STK-RAC-003: RACI from Clauses ........... 10 tests               ║
║  ├── TS-UD-STK-MAP-001: Stakeholder Map ............. 8 tests                ║
║  ├── TS-UA-STK-UC-*: Use Cases ...................... 20 tests               ║
║  ├── TS-INT-*: Integration .......................... 14 tests               ║
║  └── TS-E2E-*: E2E ................................... 10 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 7: 112 tests                                               ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S9 (Semanas 17-18)                                       ║
║  DEPENDENCIAS: Agente 2 (Clauses para extraction)                            ║
║  DESBLOQUEA: Agente 6 (Regla R20)                                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.8 AGENTE 8: Async Architecture (78 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 8: ASYNC ARCHITECTURE                         ║
║                          Target Coverage: 90%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Event Bus (Redis Pub/Sub)                                               ║
║  ├── Celery Job Queue                                                        ║
║  ├── Dead Letter Queue                                                       ║
║  └── Worker Pool Management                                                  ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-INT-EVT-BUS-001: Event Bus .................. 14 tests               ║
║  ├── TS-INT-EVT-CEL-001: Celery Jobs ................ 12 tests               ║
║  ├── TS-INT-EVT-DLQ-001: Dead Letter Queue .......... 8 tests                ║
║  ├── Event-driven workflow tests .................... 20 tests               ║
║  ├── Worker scaling tests ........................... 14 tests               ║
║  └── TS-E2E-*: E2E ................................... 10 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 8: 78 tests                                                ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S11-S12 (Semanas 21-24)                                  ║
║  DEPENDENCIAS: Agente 1 (Redis adapters)                                     ║
║  DESBLOQUEA: Integration flows, E2E                                          ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.9 AGENTE 9: Observability (68 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 9: OBSERVABILITY                              ║
║                          Target Coverage: 90%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Logging (Structlog JSON)                                                ║
║  ├── Tracing (OpenTelemetry)                                                 ║
║  ├── Budget Circuit Breaker                                                  ║
║  └── AI Usage Dashboard                                                      ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── Logging tests .................................. 16 tests               ║
║  ├── Tracing tests .................................. 16 tests               ║
║  ├── Budget Circuit Breaker ......................... 22 tests               ║
║  ├── AI Usage Dashboard ............................. 14 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 9: 68 tests                                                ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S11-S12 (paralelo con Agente 8)                          ║
║  DEPENDENCIAS: Agente 1 (LLM integration para cost tracking)                 ║
║  DESBLOQUEA: Monitoring, Alerting                                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.10 AGENTE 10: API Contracts (62 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 10: API CONTRACTS                             ║
║                          Target Coverage: 96%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── DTOs Validation (Pydantic)                                              ║
║  ├── Serialization/Deserialization                                           ║
║  ├── HTTP Routers                                                            ║
║  ├── Middleware (Auth, Tenant, CORS)                                         ║
║  └── Error Handlers                                                          ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-UA-DTO-ALL-001: DTOs Validation ............. 24 tests               ║
║  ├── TS-UA-DTO-SER-001: Serialization ............... 16 tests               ║
║  ├── TS-UAD-HTTP-RTR-001: Routers ................... 32 tests               ║
║  ├── TS-UAD-HTTP-MDW-001: Middleware ................ 18 tests               ║
║  └── TS-UAD-HTTP-ERR-001: Error Handlers ............ 12 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 10: 102 tests (ajustado)                                   ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S1-S2 (DTOs), S11-S12 (HTTP)                             ║
║  DEPENDENCIAS: Ninguna para DTOs                                             ║
║  DESBLOQUEA: Todos los demás módulos                                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.11 AGENTE 11: Integration (184 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 11: INTEGRATION                               ║
║                          Target Coverage: 91%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── WBS → Procurement Integration                                           ║
║  ├── Documents → Analysis Integration                                        ║
║  ├── Analysis → Coherence Integration                                        ║
║  ├── Stakeholders → RACI Integration                                         ║
║  ├── LLM Client Integration (Primary + Fallback)                             ║
║  └── All Database Integration                                                ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-INT-MOD-WBS-001: WBS → Procurement .......... 12 tests               ║
║  ├── TS-INT-MOD-DOC-001: Documents → Analysis ....... 10 tests               ║
║  ├── TS-INT-MOD-ANA-001: Analysis → Coherence ....... 12 tests               ║
║  ├── TS-INT-MOD-STK-001: Stakeholders → RACI ........ 8 tests                ║
║  ├── TS-INT-EXT-LLM-*: LLM Integration .............. 24 tests               ║
║  ├── TS-INT-DB-*: All DB Integration ................ 70 tests               ║
║  ├── TS-INT-GRP-NEO-001: Neo4j ...................... 14 tests               ║
║  └── Remaining integration .......................... 34 tests               ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 11: 184 tests                                              ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S11-S12 (Semanas 21-24)                                  ║
║  DEPENDENCIAS: Todos los módulos de dominio                                  ║
║  DESBLOQUEA: E2E                                                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 9.12 AGENTE 12: QA/E2E (78 tests)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          AGENTE 12: QA/E2E                                    ║
║                          Target Coverage: 83%                                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTES ASIGNADOS:                                                       ║
║  ├── Document Upload to Coherence E2E                                        ║
║  ├── Alert Review Workflow E2E                                               ║
║  ├── Bulk Operations E2E                                                     ║
║  ├── Multi-tenant Isolation E2E                                              ║
║  ├── MCP Gateway E2E                                                         ║
║  ├── Error Scenarios (Timeout, Concurrent, Recovery)                         ║
║  └── Performance Tests                                                       ║
║                                                                               ║
║  TEST SUITES ASIGNADOS:                                                       ║
║  ├── TS-E2E-FLW-DOC-001: Document Flow .............. 12 tests               ║
║  ├── TS-E2E-FLW-ALR-001: Alert Flow ................. 10 tests               ║
║  ├── TS-E2E-FLW-BLK-001: Bulk Operations ............ 8 tests                ║
║  ├── TS-E2E-SEC-TNT-001: Tenant Isolation ........... 10 tests               ║
║  ├── TS-E2E-SEC-MCP-001: MCP Gateway ................ 8 tests                ║
║  ├── TS-E2E-ERR-TIM-001: Timeouts ................... 8 tests                ║
║  ├── TS-E2E-ERR-CON-001: Concurrent ................. 8 tests                ║
║  ├── TS-E2E-ERR-REC-001: Recovery ................... 8 tests                ║
║  └── TS-E2E-PER-LRG-001: Performance ................ 6 tests                ║
║      ─────────────────────────────────────────────────────────               ║
║      TOTAL AGENTE 12: 78 tests                                               ║
║                                                                               ║
║  SPRINTS ASIGNADOS: S13-S14 (Semanas 25-28)                                  ║
║  DEPENDENCIAS: Todos los módulos + Integration                               ║
║  DESBLOQUEA: Release                                                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## 10. Dependencias y Orden de Implementación

### 10.1 Grafo de Dependencias Completo

```
                              ┌─────────────────┐
                              │   NIVEL 0       │
                              │  (Sin deps)     │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │   AGENTE 1      │     │   AGENTE 10     │     │   AGENTE 8      │
     │ Security Core   │     │ DTOs (parte 1)  │     │ Event Bus       │
     │   156 tests     │     │   40 tests      │     │   34 tests      │
     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │    NIVEL 1      │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │    AGENTE 2     │
                              │   Documents     │
                              │   162 tests     │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │   AGENTE 3      │     │   AGENTE 5      │     │   AGENTE 7      │
     │   Projects      │     │   Analysis      │     │  Stakeholders   │
     │   116 tests     │     │   78 tests      │     │   112 tests     │
     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
              │                        │                        │
              ▼                        │                        │
     ┌─────────────────┐               │                        │
     │   AGENTE 4      │               │                        │
     │  Procurement    │               │                        │
     │   116 tests     │               │                        │
     └────────┬────────┘               │                        │
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │    NIVEL 3      │
                              │   AGENTE 6      │
                              │   Coherence     │
                              │   206 tests     │
                              │   (CRÍTICO)     │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │   AGENTE 9      │     │   AGENTE 10     │     │   AGENTE 11     │
     │ Observability   │     │ HTTP Adapters   │     │  Integration    │
     │   68 tests      │     │   62 tests      │     │   184 tests     │
     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │    NIVEL 5      │
                              │   AGENTE 12     │
                              │     E2E         │
                              │   78 tests      │
                              └─────────────────┘
```

### 10.2 Orden Crítico de Ejecución

| Orden | Agente | Tests | Sprint | Bloquea | Crítico |
|-------|--------|-------|--------|---------|---------|
| 1 | Agente 10 (DTOs) | 40 | S1 | Todos | ✅ |
| 2 | Agente 1 (Security) | 156 | S1-S2 | Todos | ✅ |
| 3 | Agente 8 (Event Bus básico) | 34 | S2 | Async flows | ✅ |
| 4 | Agente 2 (Documents) | 162 | S3-S4 | Analysis, Coherence | ✅ |
| 5 | Agente 6 (Coherence) | 206 | S5-S6 | Dashboard, E2E | 🔴 CRÍTICO |
| 6 | Agente 3 (Projects) | 116 | S7 | Procurement | ⚠️ |
| 7 | Agente 4 (Procurement) | 116 | S8 | Coherence rules | ⚠️ |
| 8 | Agente 7 (Stakeholders) | 112 | S9 | RACI | ⚠️ |
| 9 | Agente 5 (Analysis) | 78 | S10 | Graph RAG | ⚠️ |
| 10 | Agente 9 (Observability) | 68 | S11 | Monitoring | ⚠️ |
| 11 | Agente 11 (Integration) | 184 | S11-S12 | E2E | ✅ |
| 12 | Agente 10 (HTTP) | 62 | S12 | API | ⚠️ |
| 13 | Agente 8 (Celery/DLQ) | 44 | S12 | Workers | ⚠️ |
| 14 | Agente 12 (E2E) | 78 | S13-S14 | Release | ✅ |

### 10.3 Ruta Crítica

```
DTOs → Security Core → Documents → Coherence → Integration → E2E
  │         │              │            │            │          │
  S1       S1-S2         S3-S4       S5-S6       S11-S12    S13-S14
  │         │              │            │            │          │
  40      +156          +162         +206        +184        +78
 tests    tests         tests        tests       tests      tests
  │         │              │            │            │          │
  40       196           358          564         748        826
 total    total         total        total       total      total
```

**Tiempo Total Ruta Crítica:** 14 sprints (28 semanas)

### 10.4 Paralelización Posible

```
SEMANAS 1-4 (S1-S2):
├── [Agente 1]  Security Core ────────────────►
├── [Agente 10] DTOs ─────►
└── [Agente 8]  Event Bus básico ───►

SEMANAS 5-8 (S3-S4):
└── [Agente 2]  Documents ────────────────────►

SEMANAS 9-12 (S5-S6):
└── [Agente 6]  Coherence (CRÍTICO) ──────────►

SEMANAS 13-16 (S7-S8):
├── [Agente 3]  Projects ────────►
└── [Agente 4]  Procurement ─────► (después de Projects)

SEMANAS 17-20 (S9-S10):
├── [Agente 7]  Stakeholders ────►
└── [Agente 5]  Analysis ────────►

SEMANAS 21-24 (S11-S12):
├── [Agente 9]  Observability ───►
├── [Agente 10] HTTP Adapters ───►
├── [Agente 8]  Celery/DLQ ──────►
└── [Agente 11] Integration ─────────────────►

SEMANAS 25-28 (S13-S14):
└── [Agente 12] E2E ─────────────────────────►
```

---

## 11. Resumen Ejecutivo Final

### 11.1 Totales Definitivos

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        RESUMEN FINAL TDD BACKLOG C2Pro                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  TOTAL TEST SUITES ............................ 113                          ║
║  TOTAL TEST CASES ............................. 1,406                        ║
║                                                                               ║
║  DISTRIBUCIÓN POR TIPO:                                                      ║
║  ├── Unit Tests (Domain + App + Adapters) ..... 921 (65.5%)                 ║
║  ├── Integration Tests ........................ 307 (21.8%)                 ║
║  └── E2E Tests ................................ 178 (12.7%)                 ║
║                                                                               ║
║  COBERTURA TARGET:                                                           ║
║  ├── Core Security ............................ 100%                         ║
║  ├── Coherence Engine ......................... 99%                          ║
║  ├── Documents Domain ......................... 95%                          ║
║  ├── Projects Domain .......................... 93%                          ║
║  ├── Procurement Domain ....................... 93%                          ║
║  ├── Stakeholders Domain ...................... 91%                          ║
║  ├── Analysis Domain .......................... 89%                          ║
║  └── PROMEDIO GLOBAL .......................... 92%                          ║
║                                                                               ║
║  ESTIMACIÓN TEMPORAL:                                                        ║
║  ├── Sprints totales .......................... 14                           ║
║  ├── Semanas totales .......................... 28                           ║
║  └── Velocidad promedio ....................... ~100 tests/sprint            ║
║                                                                               ║
║  DISTRIBUCIÓN POR PRIORIDAD:                                                 ║
║  ├── 🔴 P0 (Crítico) .......................... 468 (33%)                   ║
║  ├── 🟠 P1 (Alto) ............................. 576 (41%)                   ║
║  ├── 🟡 P2 (Medio) ............................ 248 (18%)                   ║
║  └── 🟢 P3 (Bajo) ............................. 114 (8%)                    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### 11.2 Próximos Pasos

1. **Semana 1:** Iniciar con DTOs + Security Core (Agentes 1, 10)
2. **Semana 2:** Completar MCP Gateway + Anonymizer
3. **Semana 3:** Iniciar Documents Domain (Agente 2)
4. **Semana 5:** Comenzar Coherence Engine (Agente 6 - CRÍTICO)

---

## Firmas de Aprobación

| Rol | Nombre | Fecha | Firma |
|-----|--------|-------|-------|
| Lead Software Architect | _________________ | 2026-01-31 | ☐ |
| QA Lead | _________________ | 2026-01-31 | ☐ |
| Tech Lead | _________________ | 2026-01-31 | ☐ |
| Product Owner | _________________ | 2026-01-31 | ☐ |

---

> **Documento:** C2Pro - Índice Exhaustivo de Test Suites v1.1  
> **Fecha:** 2026-01-31  
> **Estado:** APROBADO PARA EJECUCIÓN  
> **Total Tests:** 1,406  
> **Cobertura Target:** 92%
