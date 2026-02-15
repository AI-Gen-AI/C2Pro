# C2Pro - TDD Backlog Completo v1.0

> **Versión:** 1.8  
> **Fecha:** 2026-02-14  
> **Última Actualización:** 2026-02-15  
> **Alineado con:** PLAN_ARQUITECTURA_v2.1.md, Diagrama Maestro v2.2.1  
> **Metodología:** TDD Estricto (Red → Green (Fake It) → Refactor (Triangulation))

---

## 📋 ÍNDICE MAESTRO DE TESTS

### Estructura del Documento

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Taxonomía de Tests](#2-taxonomía-de-tests)
3. [Índice Completo por Capa](#3-índice-completo-por-capa)
4. [Índice Completo por Módulo](#4-índice-completo-por-módulo)
5. [Matriz de Cobertura](#5-matriz-de-cobertura)
6. [Plan de Ejecución por Sprints](#6-plan-de-ejecución-por-sprints)
7. [Detalle de Test Suites por Agente](#7-detalle-de-test-suites-por-agente)
8. [Dependencias y Orden de Implementación](#8-dependencias-y-orden-de-implementación)
9. [Métricas y KPIs de Testing](#9-métricas-y-kpis-de-testing)
10. [Anexos](#10-anexos)

---

## 1. Resumen Ejecutivo

### 1.1 Métricas Globales

| Métrica                  | Planificado | Completado (2026-02-14) |
| ------------------------ | ----------- | ----------------------- |
| **Total Test Suites**    | 89          | 83 (93%)                |
| **Total Test Cases**     | 487         | ~455 (93%)              |
| **Unit Tests**           | 312 (64%)   | 312 (100%)              |
| **Integration Tests**    | 127 (26%)   | 127 (100%)              |
| **E2E Tests**            | 48 (10%)    | 0 (0%)                  |
| **Ciclos TDD Completos** | 245         | ~210                    |
| **Módulos Cubiertos**    | 12          | 10                      |
| **Sprints Estimados**    | 18-22       | ~12 completados         |

> **Nota sobre conteos:** Este backlog detalla 487 test cases individuales definidos en  
> las tablas de la Sección 3. El `C2PRO_TEST_SUITES_INDEX_v1.1.md` detalla 846-1,406  
> test cases a nivel más granular (incluyendo edge cases y sub-tests por suite).  
> Ambos documentos son complementarios: este backlog es la vista de seguimiento,  
> el Índice es la vista de especificación detallada.

### 1.2 Distribución por Prioridad

| Prioridad       | Tests | Porcentaje | Sprints |
| --------------- | ----- | ---------- | ------- |
| 🔴 P0 (Crítico) | 156   | 32%        | 1-6     |
| 🟠 P1 (Alto)    | 198   | 41%        | 7-12    |
| 🟡 P2 (Medio)   | 89    | 18%        | 13-16   |
| 🟢 P3 (Bajo)    | 44    | 9%         | 17-22   |

### 1.3 Distribución por Tipo

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIRÁMIDE DE TESTS C2Pro                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                         ┌─────────┐                             │
│                         │   E2E   │  48 tests (10%)             │
│                         │ Cypress │  ~15 min runtime            │
│                         └────┬────┘                             │
│                              │                                  │
│                    ┌─────────┴─────────┐                        │
│                    │   Integration     │  127 tests (26%)       │
│                    │  pytest + docker  │  ~8 min runtime        │
│                    └─────────┬─────────┘                        │
│                              │                                  │
│         ┌────────────────────┴────────────────────┐             │
│         │              Unit Tests                  │             │
│         │           pytest (isolated)              │  312 tests │
│         │             ~2 min runtime               │  (64%)     │
│         └──────────────────────────────────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Taxonomía de Tests

### 2.1 Categorías de Tests

| Categoría                  | Código    | Descripción                               | Herramienta             |
| -------------------------- | --------- | ----------------------------------------- | ----------------------- |
| **Unit - Domain**          | `UD`      | Entidades, Value Objects, Domain Services | pytest                  |
| **Unit - Application**     | `UA`      | Use Cases, Application Services           | pytest                  |
| **Unit - Ports**           | `UP`      | Interfaces/Contracts                      | pytest + Protocol       |
| **Unit - Adapters**        | `UAD`     | Implementaciones aisladas                 | pytest + mocks          |
| **Integration - DB**       | `IDB`     | Repositorios con DB real                  | pytest + testcontainers |
| **Integration - External** | `IEX`     | APIs externas (LLM, etc)                  | pytest + VCR            |
| **Integration - Module**   | `IM`      | Cross-module via ports                    | pytest                  |
| **Integration - Event**    | `IE`      | Event Bus + Async                         | pytest + asyncio        |
| **E2E - API**              | `E2E-API` | Flujos HTTP completos                     | pytest + httpx          |
| **E2E - UI**               | `E2E-UI`  | Flujos de usuario                         | Cypress                 |
| **Contract**               | `CT`      | API contracts                             | pact-python             |
| **Performance**            | `PF`      | Load/stress tests                         | locust                  |

### 2.2 Nomenclatura de Tests

```
test_{categoria}_{modulo}_{componente}_{escenario}_{caso}

Ejemplos:
- test_ud_coherence_rules_engine_scope_r11_wbs_without_activities
- test_idb_documents_clause_repository_create_with_valid_fk
- test_e2e_api_document_upload_to_coherence_happy_path
```

### 2.3 Estructura de Archivos

```
tests/
├── unit/
│   ├── domain/
│   │   ├── documents/
│   │   │   ├── test_clause_entity.py
│   │   │   ├── test_document_entity.py
│   │   │   └── test_extraction_value_objects.py
│   │   ├── coherence/
│   │   │   ├── test_coherence_score.py
│   │   │   ├── test_category.py
│   │   │   └── test_rule.py
│   │   ├── projects/
│   │   ├── procurement/
│   │   ├── stakeholders/
│   │   └── analysis/
│   ├── application/
│   │   ├── use_cases/
│   │   ├── services/
│   │   └── dtos/
│   ├── adapters/
│   │   ├── http/
│   │   └── persistence/
│   └── core/
│       ├── security/
│       ├── ai/
│       └── observability/
├── integration/
│   ├── db/
│   ├── external/
│   ├── modules/
│   └── events/
├── e2e/
│   ├── api/
│   └── ui/
├── contracts/
├── performance/
├── conftest.py
├── fixtures/
│   ├── documents/
│   ├── projects/
│   └── factories.py
└── mocks/
    ├── llm_responses/
    └── external_services/
```

---

## 3. Índice Completo por Capa

### 3.1 UNIT TESTS - DOMAIN LAYER (156 tests)

#### 3.1.1 Documents Domain (28 tests)

| ID         | Test Name                                         | Tipo | Prioridad | Ciclo TDD |
| ---------- | ------------------------------------------------- | ---- | --------- | --------- |
| UD-DOC-001 | test_clause_entity_creation_with_valid_data       | UD   | 🔴 P0     | 2.1.1     |
| UD-DOC-002 | test_clause_entity_creation_fails_without_content | UD   | 🔴 P0     | 2.1.1     |
| UD-DOC-003 | test_clause_entity_immutability                   | UD   | 🔴 P0     | 2.1.1     |
| UD-DOC-004 | test_clause_number_normalization                  | UD   | 🟠 P1     | 2.1.2     |
| UD-DOC-005 | test_clause_type_classification_payment           | UD   | 🟠 P1     | 2.1.3     |
| UD-DOC-006 | test_clause_type_classification_penalty           | UD   | 🟠 P1     | 2.1.3     |
| UD-DOC-007 | test_clause_type_classification_scope             | UD   | 🟠 P1     | 2.1.3     |
| UD-DOC-008 | test_clause_type_classification_warranty          | UD   | 🟠 P1     | 2.1.3     |
| UD-DOC-009 | test_clause_type_classification_termination       | UD   | 🟠 P1     | 2.1.3     |
| UD-DOC-010 | test_clause_type_classification_unknown           | UD   | 🟡 P2     | 2.1.3     |
| UD-DOC-011 | test_subclause_hierarchy_creation                 | UD   | 🟠 P1     | 2.1.2     |
| UD-DOC-012 | test_subclause_parent_reference                   | UD   | 🟠 P1     | 2.1.2     |
| UD-DOC-013 | test_document_entity_creation                     | UD   | 🔴 P0     | 2.1.1     |
| UD-DOC-014 | test_document_status_transitions                  | UD   | 🟠 P1     | 2.1.1     |
| UD-DOC-015 | test_document_status_invalid_transition           | UD   | 🟠 P1     | 2.1.1     |
| UD-DOC-016 | test_date_entity_extraction_explicit              | UD   | 🔴 P0     | 2.2.1     |
| UD-DOC-017 | test_date_entity_extraction_multiple_formats      | UD   | 🔴 P0     | 2.2.1     |
| UD-DOC-018 | test_duration_entity_days_natural                 | UD   | 🟠 P1     | 2.2.2     |
| UD-DOC-019 | test_duration_entity_days_business                | UD   | 🟠 P1     | 2.2.2     |
| UD-DOC-020 | test_duration_entity_months                       | UD   | 🟠 P1     | 2.2.2     |
| UD-DOC-021 | test_money_entity_eur_format                      | UD   | 🔴 P0     | 2.3.1     |
| UD-DOC-022 | test_money_entity_usd_format                      | UD   | 🟠 P1     | 2.3.1     |
| UD-DOC-023 | test_money_entity_written_format                  | UD   | 🟠 P1     | 2.3.1     |
| UD-DOC-024 | test_money_entity_context_anticipo                | UD   | 🟠 P1     | 2.3.2     |
| UD-DOC-025 | test_money_entity_context_pago_final              | UD   | 🟠 P1     | 2.3.2     |
| UD-DOC-026 | test_confidence_score_calculation_clear_structure | UD   | 🟠 P1     | 2.5.1     |
| UD-DOC-027 | test_confidence_score_calculation_ambiguous       | UD   | 🟠 P1     | 2.5.1     |
| UD-DOC-028 | test_confidence_score_range_validation            | UD   | 🟡 P2     | 2.5.1     |

#### 3.1.2 Coherence Domain (42 tests)

| ID         | Test Name                                            | Tipo | Prioridad | Ciclo TDD |
| ---------- | ---------------------------------------------------- | ---- | --------- | --------- |
| UD-COH-001 | test_category_enum_all_six_values                    | UD   | 🔴 P0     | 6.1.1     |
| UD-COH-002 | test_category_default_weights_sum_to_one             | UD   | 🔴 P0     | 6.5.2     |
| UD-COH-003 | test_rule_r1_time_contract_vs_schedule               | UD   | 🔴 P0     | 6.3.1     |
| UD-COH-004 | test_rule_r2_time_milestone_without_activity         | UD   | 🔴 P0     | 6.3.2     |
| UD-COH-005 | test_rule_r3_technical_contradictory_spec            | UD   | 🟠 P1     | 6.4.1     |
| UD-COH-006 | test_rule_r4_technical_requirement_no_owner          | UD   | 🟠 P1     | 6.4.1     |
| UD-COH-007 | test_rule_r5_time_schedule_exceeds_contract          | UD   | 🔴 P0     | 6.3.3     |
| UD-COH-008 | test_rule_r6_budget_sum_mismatch_over_threshold      | UD   | 🔴 P0     | 6.2.1     |
| UD-COH-009 | test_rule_r6_budget_sum_within_threshold             | UD   | 🔴 P0     | 6.2.1     |
| UD-COH-010 | test_rule_r7_technical_unresolved_dependency         | UD   | 🟠 P1     | 6.4.1     |
| UD-COH-011 | test_rule_r8_legal_penalty_without_milestone         | UD   | 🔴 P0     | 6.4.2     |
| UD-COH-012 | test_rule_r11_scope_wbs_without_activities           | UD   | 🔴 P0     | 6.1.1     |
| UD-COH-013 | test_rule_r11_scope_wbs_level_4_only                 | UD   | 🟠 P1     | 6.1.1     |
| UD-COH-014 | test_rule_r12_scope_wbs_without_budget               | UD   | 🔴 P0     | 6.1.2     |
| UD-COH-015 | test_rule_r12_scope_wbs_zero_budget                  | UD   | 🟠 P1     | 6.1.2     |
| UD-COH-016 | test_rule_r13_scope_uncovered_by_wbs                 | UD   | 🔴 P0     | 6.1.3     |
| UD-COH-017 | test_rule_r13_scope_partial_coverage                 | UD   | 🟠 P1     | 6.1.3     |
| UD-COH-018 | test_rule_r14_time_late_order_date                   | UD   | 🔴 P0     | 4.1.3     |
| UD-COH-019 | test_rule_r14_time_tight_margin_warning              | UD   | 🟠 P1     | 4.1.3     |
| UD-COH-020 | test_rule_r15_budget_bom_without_budget_line         | UD   | 🔴 P0     | 6.2.2     |
| UD-COH-021 | test_rule_r15_budget_bom_client_provided_exception   | UD   | 🟠 P1     | 6.2.2     |
| UD-COH-022 | test_rule_r16_budget_deviation_over_10_percent       | UD   | 🔴 P0     | 6.2.3     |
| UD-COH-023 | test_rule_r16_budget_under_budget_different_severity | UD   | 🟠 P1     | 6.2.3     |
| UD-COH-024 | test_rule_r17_quality_spec_without_standard          | UD   | 🟠 P1     | 6.4.3     |
| UD-COH-025 | test_rule_r18_quality_material_without_cert          | UD   | 🟠 P1     | 4.4.2     |
| UD-COH-026 | test_rule_r20_legal_approver_not_identified          | UD   | 🔴 P0     | 7.2.4     |
| UD-COH-027 | test_subscore_calculation_no_alerts                  | UD   | 🔴 P0     | 6.5.1     |
| UD-COH-028 | test_subscore_calculation_with_alerts                | UD   | 🔴 P0     | 6.5.1     |
| UD-COH-029 | test_subscore_penalty_by_severity                    | UD   | 🟠 P1     | 6.5.1     |
| UD-COH-030 | test_global_score_calculation_default_weights        | UD   | 🔴 P0     | 6.5.2     |
| UD-COH-031 | test_global_score_calculation_custom_weights         | UD   | 🔴 P0     | 6.5.3     |
| UD-COH-032 | test_global_score_weights_normalization              | UD   | 🟠 P1     | 6.5.3     |
| UD-COH-033 | test_global_score_clamped_to_0_100                   | UD   | 🟠 P1     | 6.5.2     |
| UD-COH-034 | test_anti_gaming_mass_changes_detection              | UD   | 🟠 P1     | 6.6.1     |
| UD-COH-035 | test_anti_gaming_mass_changes_threshold              | UD   | 🟠 P1     | 6.6.1     |
| UD-COH-036 | test_anti_gaming_resolve_reintroduce_detection       | UD   | 🟠 P1     | 6.6.2     |
| UD-COH-037 | test_anti_gaming_resolve_reintroduce_hash_different  | UD   | 🟠 P1     | 6.6.2     |
| UD-COH-038 | test_anti_gaming_suspicious_high_score               | UD   | 🟠 P1     | 6.6.3     |
| UD-COH-039 | test_anti_gaming_weight_manipulation                 | UD   | 🟠 P1     | 6.6.4     |
| UD-COH-040 | test_anti_gaming_penalty_application                 | UD   | 🔴 P0     | 6.6.5     |
| UD-COH-041 | test_anti_gaming_penalty_floor_zero                  | UD   | 🟠 P1     | 6.6.5     |
| UD-COH-042 | test_coherence_result_dto_validation                 | UD   | 🔴 P0     | 10.2.1    |

#### 3.1.3 Projects Domain (24 tests)

| ID         | Test Name                                    | Tipo | Prioridad | Ciclo TDD |
| ---------- | -------------------------------------------- | ---- | --------- | --------- |
| UD-PRJ-001 | test_wbs_item_entity_creation                | UD   | 🔴 P0     | 3.1.1     |
| UD-PRJ-002 | test_wbs_item_code_format_validation         | UD   | 🔴 P0     | 3.1.3     |
| UD-PRJ-003 | test_wbs_item_code_pattern_level_1           | UD   | 🟠 P1     | 3.1.3     |
| UD-PRJ-004 | test_wbs_item_code_pattern_level_4           | UD   | 🟠 P1     | 3.1.3     |
| UD-PRJ-005 | test_wbs_item_level_range_1_to_4             | UD   | 🔴 P0     | 3.1.2     |
| UD-PRJ-006 | test_wbs_item_level_invalid_zero             | UD   | 🟠 P1     | 3.1.2     |
| UD-PRJ-007 | test_wbs_item_level_invalid_five             | UD   | 🟠 P1     | 3.1.2     |
| UD-PRJ-008 | test_wbs_item_parent_child_level_validation  | UD   | 🔴 P0     | 3.2.1     |
| UD-PRJ-009 | test_wbs_item_parent_child_level_invalid     | UD   | 🟠 P1     | 3.2.1     |
| UD-PRJ-010 | test_wbs_item_circular_reference_detection   | UD   | 🟠 P1     | 3.2.2     |
| UD-PRJ-011 | test_wbs_item_date_range_validation          | UD   | 🟠 P1     | 3.1.1     |
| UD-PRJ-012 | test_wbs_item_date_range_invalid             | UD   | 🟠 P1     | 3.1.1     |
| UD-PRJ-013 | test_wbs_hierarchy_traversal_children        | UD   | 🟠 P1     | 3.2.1     |
| UD-PRJ-014 | test_wbs_hierarchy_traversal_ancestors       | UD   | 🟠 P1     | 3.2.1     |
| UD-PRJ-015 | test_wbs_item_dto_from_entity                | UD   | 🔴 P0     | 10.1.1    |
| UD-PRJ-016 | test_wbs_item_dto_validation_required_fields | UD   | 🔴 P0     | 10.1.1    |
| UD-PRJ-017 | test_wbs_item_dto_code_format_validation     | UD   | 🟠 P1     | 10.1.2    |
| UD-PRJ-018 | test_wbs_item_dto_level_range_validation     | UD   | 🟠 P1     | 10.1.3    |
| UD-PRJ-019 | test_project_entity_creation                 | UD   | 🔴 P0     | 3.1.1     |
| UD-PRJ-020 | test_project_status_transitions              | UD   | 🟠 P1     | 3.1.1     |
| UD-PRJ-021 | test_project_wbs_root_items                  | UD   | 🟠 P1     | 3.1.1     |
| UD-PRJ-022 | test_project_wbs_max_depth                   | UD   | 🟡 P2     | 3.1.2     |
| UD-PRJ-023 | test_project_clause_association              | UD   | 🟠 P1     | 3.1.1     |
| UD-PRJ-024 | test_project_date_validation                 | UD   | 🟠 P1     | 3.1.1     |

#### 3.1.4 Procurement Domain (22 tests)

| ID          | Test Name                                | Tipo | Prioridad | Ciclo TDD |
| ----------- | ---------------------------------------- | ---- | --------- | --------- |
| UD-PROC-001 | test_bom_item_entity_creation            | UD   | 🔴 P0     | 4.3.1     |
| UD-PROC-002 | test_bom_item_wbs_item_fk_required       | UD   | 🔴 P0     | 4.3.1     |
| UD-PROC-003 | test_bom_item_clause_fk_optional         | UD   | 🟠 P1     | 4.3.2     |
| UD-PROC-004 | test_bom_item_quantity_positive          | UD   | 🟠 P1     | 4.3.1     |
| UD-PROC-005 | test_bom_item_unit_cost_positive         | UD   | 🟠 P1     | 4.3.1     |
| UD-PROC-006 | test_bom_item_total_cost_calculation     | UD   | 🟠 P1     | 4.3.1     |
| UD-PROC-007 | test_lead_time_basic_calculation         | UD   | 🔴 P0     | 4.1.1     |
| UD-PROC-008 | test_lead_time_with_customs              | UD   | 🔴 P0     | 4.1.1     |
| UD-PROC-009 | test_lead_time_with_buffer               | UD   | 🟠 P1     | 4.1.1     |
| UD-PROC-010 | test_lead_time_business_days_calculation | UD   | 🟠 P1     | 4.1.2     |
| UD-PROC-011 | test_lead_time_weekend_adjustment        | UD   | 🟠 P1     | 4.1.2     |
| UD-PROC-012 | test_lead_time_incoterm_exw              | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-013 | test_lead_time_incoterm_ddp              | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-014 | test_lead_time_incoterm_cif              | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-015 | test_lead_time_customs_eu_internal       | UD   | 🟠 P1     | 4.2.2     |
| UD-PROC-016 | test_lead_time_customs_international     | UD   | 🟠 P1     | 4.2.2     |
| UD-PROC-017 | test_incoterm_enum_values                | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-018 | test_incoterm_buyer_responsibility       | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-019 | test_incoterm_seller_responsibility      | UD   | 🟠 P1     | 4.2.1     |
| UD-PROC-020 | test_procurement_plan_generation         | UD   | 🟠 P1     | 4.3.1     |
| UD-PROC-021 | test_procurement_plan_optimal_dates      | UD   | 🟠 P1     | 4.3.1     |
| UD-PROC-022 | test_procurement_plan_alerts_generation  | UD   | 🟠 P1     | 4.1.3     |

#### 3.1.5 Stakeholders Domain (18 tests)

| ID         | Test Name                                      | Tipo | Prioridad | Ciclo TDD |
| ---------- | ---------------------------------------------- | ---- | --------- | --------- |
| UD-STK-001 | test_stakeholder_entity_creation               | UD   | 🔴 P0     | 7.1.1     |
| UD-STK-002 | test_stakeholder_power_interest_classification | UD   | 🔴 P0     | 7.1.1     |
| UD-STK-003 | test_stakeholder_quadrant_manage_closely       | UD   | 🟠 P1     | 7.1.2     |
| UD-STK-004 | test_stakeholder_quadrant_keep_satisfied       | UD   | 🟠 P1     | 7.1.2     |
| UD-STK-005 | test_stakeholder_quadrant_keep_informed        | UD   | 🟠 P1     | 7.1.2     |
| UD-STK-006 | test_stakeholder_quadrant_monitor              | UD   | 🟠 P1     | 7.1.2     |
| UD-STK-007 | test_stakeholder_quadrant_boundary             | UD   | 🟡 P2     | 7.1.2     |
| UD-STK-008 | test_stakeholder_clause_based_power_adjustment | UD   | 🟠 P1     | 7.1.3     |
| UD-STK-009 | test_raci_entry_valid_values                   | UD   | 🔴 P0     | 7.2.1     |
| UD-STK-010 | test_raci_entry_invalid_value                  | UD   | 🟠 P1     | 7.2.1     |
| UD-STK-011 | test_raci_matrix_activity_has_responsible      | UD   | 🔴 P0     | 7.2.2     |
| UD-STK-012 | test_raci_matrix_activity_missing_responsible  | UD   | 🔴 P0     | 7.2.2     |
| UD-STK-013 | test_raci_matrix_multiple_responsible_warning  | UD   | 🟠 P1     | 7.2.2     |
| UD-STK-014 | test_raci_matrix_from_clause                   | UD   | 🟠 P1     | 7.2.3     |
| UD-STK-015 | test_raci_matrix_conflicting_clauses           | UD   | 🟠 P1     | 7.2.3     |
| UD-STK-016 | test_stakeholder_map_data_generation           | UD   | 🟠 P1     | 7.3.1     |
| UD-STK-017 | test_stakeholder_map_coordinates               | UD   | 🟠 P1     | 7.3.2     |
| UD-STK-018 | test_stakeholder_map_jitter_same_position      | UD   | 🟡 P2     | 7.3.2     |

#### 3.1.6 Analysis Domain (12 tests)

| ID         | Test Name                           | Tipo | Prioridad | Ciclo TDD |
| ---------- | ----------------------------------- | ---- | --------- | --------- |
| UD-ANA-001 | test_alert_entity_creation          | UD   | 🔴 P0     | 5.4.1     |
| UD-ANA-002 | test_alert_severity_enum            | UD   | 🔴 P0     | 5.4.1     |
| UD-ANA-003 | test_alert_status_transitions       | UD   | 🟠 P1     | 5.4.1     |
| UD-ANA-004 | test_alert_rule_mapping_to_category | UD   | 🔴 P0     | 5.4.2     |
| UD-ANA-005 | test_alert_affected_entities_list   | UD   | 🟠 P1     | 5.4.1     |
| UD-ANA-006 | test_analysis_result_entity         | UD   | 🟠 P1     | 5.4.1     |
| UD-ANA-007 | test_analysis_result_alerts_list    | UD   | 🟠 P1     | 5.4.1     |
| UD-ANA-008 | test_graph_query_result             | UD   | 🟠 P1     | 5.2.1     |
| UD-ANA-009 | test_graph_node_entity              | UD   | 🟠 P1     | 5.1.1     |
| UD-ANA-010 | test_graph_relationship_entity      | UD   | 🟠 P1     | 5.1.2     |
| UD-ANA-011 | test_semantic_search_result         | UD   | 🟠 P1     | 5.3.1     |
| UD-ANA-012 | test_hybrid_search_result           | UD   | 🟠 P1     | 5.3.2     |

#### 3.1.7 Core - Security Domain (10 tests)

| ID         | Test Name                          | Tipo | Prioridad | Ciclo TDD |
| ---------- | ---------------------------------- | ---- | --------- | --------- |
| UD-SEC-001 | test_allowlist_result_creation     | UD   | 🔴 P0     | 1.1.1     |
| UD-SEC-002 | test_rate_limit_result_creation    | UD   | 🔴 P0     | 1.2.1     |
| UD-SEC-003 | test_query_limit_result_creation   | UD   | 🟠 P1     | 1.3.1     |
| UD-SEC-004 | test_pii_detection_result_creation | UD   | 🔴 P0     | 1.5.1     |
| UD-SEC-005 | test_pii_type_enum_all_values      | UD   | 🟠 P1     | 1.5.1     |
| UD-SEC-006 | test_anonymization_strategy_enum   | UD   | 🟠 P1     | 1.6.1     |
| UD-SEC-007 | test_tenant_context_creation       | UD   | 🔴 P0     | 1.1.1     |
| UD-SEC-008 | test_tenant_context_isolation      | UD   | 🔴 P0     | 1.1.1     |
| UD-SEC-009 | test_mcp_operation_type_enum       | UD   | 🟠 P1     | 1.1.2     |
| UD-SEC-010 | test_anti_gaming_result_creation   | UD   | 🟠 P1     | 6.6.1     |

### 3.2 UNIT TESTS - APPLICATION LAYER (98 tests)

#### 3.2.1 Use Cases (52 tests)

| ID        | Test Name                                        | Tipo | Prioridad | Ciclo TDD |
| --------- | ------------------------------------------------ | ---- | --------- | --------- |
| UA-UC-001 | test_upload_document_use_case_success            | UA   | 🔴 P0     | 2.1.1     |
| UA-UC-002 | test_upload_document_use_case_invalid_format     | UA   | 🟠 P1     | 2.1.1     |
| UA-UC-003 | test_extract_clauses_use_case_success            | UA   | 🔴 P0     | 2.1.1     |
| UA-UC-004 | test_extract_clauses_use_case_no_clauses_found   | UA   | 🟠 P1     | 2.1.1     |
| UA-UC-005 | test_extract_entities_use_case_success           | UA   | 🔴 P0     | 2.2.1     |
| UA-UC-006 | test_calculate_coherence_use_case_success        | UA   | 🔴 P0     | 6.5.2     |
| UA-UC-007 | test_calculate_coherence_use_case_no_data        | UA   | 🟠 P1     | 6.5.2     |
| UA-UC-008 | test_calculate_coherence_use_case_custom_weights | UA   | 🟠 P1     | 6.5.3     |
| UA-UC-009 | test_generate_wbs_use_case_success               | UA   | 🔴 P0     | 3.1.1     |
| UA-UC-010 | test_generate_wbs_use_case_empty_scope           | UA   | 🟠 P1     | 3.1.1     |
| UA-UC-011 | test_create_wbs_item_use_case_success            | UA   | 🟠 P1     | 3.2.1     |
| UA-UC-012 | test_create_wbs_item_use_case_invalid_parent     | UA   | 🟠 P1     | 3.2.1     |
| UA-UC-013 | test_move_wbs_item_use_case_success              | UA   | 🟠 P1     | 3.2.2     |
| UA-UC-014 | test_move_wbs_item_use_case_circular             | UA   | 🟠 P1     | 3.2.2     |
| UA-UC-015 | test_delete_wbs_item_use_case_no_children        | UA   | 🟠 P1     | 3.2.3     |
| UA-UC-016 | test_delete_wbs_item_use_case_with_children      | UA   | 🟠 P1     | 3.2.3     |
| UA-UC-017 | test_delete_wbs_item_use_case_cascade            | UA   | 🟠 P1     | 3.2.3     |
| UA-UC-018 | test_generate_bom_use_case_success               | UA   | 🔴 P0     | 4.3.1     |
| UA-UC-019 | test_generate_bom_use_case_no_wbs                | UA   | 🟠 P1     | 4.3.1     |
| UA-UC-020 | test_calculate_lead_time_use_case_success        | UA   | 🔴 P0     | 4.1.1     |
| UA-UC-021 | test_calculate_lead_time_use_case_missing_data   | UA   | 🟠 P1     | 4.1.1     |
| UA-UC-022 | test_extract_stakeholders_use_case_success       | UA   | 🔴 P0     | 7.1.1     |
| UA-UC-023 | test_classify_stakeholder_use_case_success       | UA   | 🟠 P1     | 7.1.1     |
| UA-UC-024 | test_generate_raci_use_case_success              | UA   | 🔴 P0     | 7.2.1     |
| UA-UC-025 | test_generate_raci_use_case_incomplete           | UA   | 🟠 P1     | 7.2.2     |
| UA-UC-026 | test_run_analysis_use_case_success               | UA   | 🔴 P0     | 5.4.1     |
| UA-UC-027 | test_run_analysis_use_case_llm_fallback          | UA   | 🟠 P1     | 5.4.2     |
| UA-UC-028 | test_approve_alert_use_case_success              | UA   | 🟠 P1     | 12.2.1    |
| UA-UC-029 | test_reject_alert_use_case_success               | UA   | 🟠 P1     | 12.2.1    |
| UA-UC-030 | test_bulk_approve_alerts_use_case_success        | UA   | 🟠 P1     | 12.2.2    |
| UA-UC-031 | test_bulk_approve_alerts_use_case_anti_gaming    | UA   | 🟠 P1     | 12.2.2    |
| UA-UC-032 | test_validate_mcp_operation_use_case_allowed     | UA   | 🔴 P0     | 1.1.1     |
| UA-UC-033 | test_validate_mcp_operation_use_case_blocked     | UA   | 🔴 P0     | 1.1.1     |
| UA-UC-034 | test_check_rate_limit_use_case_under_limit       | UA   | 🔴 P0     | 1.2.1     |
| UA-UC-035 | test_check_rate_limit_use_case_exceeded          | UA   | 🔴 P0     | 1.2.1     |
| UA-UC-036 | test_anonymize_document_use_case_success         | UA   | 🔴 P0     | 1.5.1     |
| UA-UC-037 | test_anonymize_document_use_case_no_pii          | UA   | 🟠 P1     | 1.5.1     |
| UA-UC-038 | test_graph_query_use_case_one_hop                | UA   | 🟠 P1     | 5.2.1     |
| UA-UC-039 | test_graph_query_use_case_multi_hop              | UA   | 🟠 P1     | 5.2.2     |
| UA-UC-040 | test_semantic_search_use_case_success            | UA   | 🟠 P1     | 5.3.1     |
| UA-UC-041 | test_semantic_search_use_case_no_results         | UA   | 🟠 P1     | 5.3.1     |
| UA-UC-042 | test_check_budget_use_case_under_limit           | UA   | 🟠 P1     | 9.3.1     |
| UA-UC-043 | test_check_budget_use_case_warning               | UA   | 🟠 P1     | 9.3.1     |
| UA-UC-044 | test_check_budget_use_case_throttle              | UA   | 🟠 P1     | 9.3.2     |
| UA-UC-045 | test_check_budget_use_case_blocked               | UA   | 🟠 P1     | 9.3.3     |
| UA-UC-046 | test_record_ai_usage_use_case_success            | UA   | 🟠 P1     | 9.3.4     |
| UA-UC-047 | test_evaluate_anti_gaming_use_case_clean         | UA   | 🟠 P1     | 6.6.1     |
| UA-UC-048 | test_evaluate_anti_gaming_use_case_violation     | UA   | 🟠 P1     | 6.6.1     |
| UA-UC-049 | test_create_audit_log_use_case_success           | UA   | 🟠 P1     | 14.1.1    |
| UA-UC-050 | test_create_audit_log_use_case_pii_filtered      | UA   | 🟠 P1     | 14.1.1    |
| UA-UC-051 | test_get_coherence_dashboard_use_case_success    | UA   | 🟠 P1     | 11.2      |
| UA-UC-052 | test_get_stakeholder_map_use_case_success        | UA   | 🟠 P1     | 11.2      |

#### 3.2.2 Application Services (28 tests)

| ID         | Test Name                                  | Tipo | Prioridad | Ciclo TDD |
| ---------- | ------------------------------------------ | ---- | --------- | --------- |
| UA-SVC-001 | test_clause_extraction_service_pdf         | UA   | 🔴 P0     | 2.1.1     |
| UA-SVC-002 | test_clause_extraction_service_docx        | UA   | 🟠 P1     | 2.1.1     |
| UA-SVC-003 | test_clause_extraction_service_xlsx        | UA   | 🟠 P1     | 2.1.1     |
| UA-SVC-004 | test_entity_extraction_service_dates       | UA   | 🔴 P0     | 2.2.1     |
| UA-SVC-005 | test_entity_extraction_service_money       | UA   | 🔴 P0     | 2.3.1     |
| UA-SVC-006 | test_entity_extraction_service_durations   | UA   | 🟠 P1     | 2.2.2     |
| UA-SVC-007 | test_coherence_calculation_service_full    | UA   | 🔴 P0     | 6.5.2     |
| UA-SVC-008 | test_coherence_calculation_service_partial | UA   | 🟠 P1     | 6.5.2     |
| UA-SVC-009 | test_wbs_generation_service_construction   | UA   | 🟠 P1     | 3.1.1     |
| UA-SVC-010 | test_wbs_generation_service_software       | UA   | 🟠 P1     | 3.1.1     |
| UA-SVC-011 | test_bom_generation_service_from_wbs       | UA   | 🟠 P1     | 4.3.1     |
| UA-SVC-012 | test_lead_time_calculation_service_full    | UA   | 🔴 P0     | 4.1.1     |
| UA-SVC-013 | test_stakeholder_classification_service    | UA   | 🟠 P1     | 7.1.1     |
| UA-SVC-014 | test_raci_generation_service_from_clauses  | UA   | 🟠 P1     | 7.2.3     |
| UA-SVC-015 | test_pii_detection_service_dni             | UA   | 🔴 P0     | 1.5.1     |
| UA-SVC-016 | test_pii_detection_service_email           | UA   | 🔴 P0     | 1.5.2     |
| UA-SVC-017 | test_pii_detection_service_phone           | UA   | 🟠 P1     | 1.5.3     |
| UA-SVC-018 | test_pii_detection_service_iban            | UA   | 🟠 P1     | 1.5.4     |
| UA-SVC-019 | test_anonymization_service_redact          | UA   | 🔴 P0     | 1.6.1     |
| UA-SVC-020 | test_anonymization_service_hash            | UA   | 🟠 P1     | 1.6.2     |
| UA-SVC-021 | test_anonymization_service_pseudonymize    | UA   | 🟠 P1     | 1.6.3     |
| UA-SVC-022 | test_rate_limit_service_sliding_window     | UA   | 🔴 P0     | 1.2.1     |
| UA-SVC-023 | test_rate_limit_service_per_tenant         | UA   | 🔴 P0     | 1.2.2     |
| UA-SVC-024 | test_allowlist_service_views               | UA   | 🔴 P0     | 1.1.1     |
| UA-SVC-025 | test_allowlist_service_functions           | UA   | 🔴 P0     | 1.1.2     |
| UA-SVC-026 | test_anti_gaming_service_evaluation        | UA   | 🟠 P1     | 6.6.1     |
| UA-SVC-027 | test_budget_tracking_service_daily_sum     | UA   | 🟠 P1     | 9.3.4     |
| UA-SVC-028 | test_budget_tracking_service_reset         | UA   | 🟠 P1     | 9.3.5     |

#### 3.2.3 DTOs Validation (18 tests)

| ID         | Test Name                             | Tipo | Prioridad | Ciclo TDD |
| ---------- | ------------------------------------- | ---- | --------- | --------- |
| UA-DTO-001 | test_wbs_item_dto_required_fields     | UA   | 🔴 P0     | 10.1.1    |
| UA-DTO-002 | test_wbs_item_dto_code_format         | UA   | 🟠 P1     | 10.1.2    |
| UA-DTO-003 | test_wbs_item_dto_level_range         | UA   | 🟠 P1     | 10.1.3    |
| UA-DTO-004 | test_coherence_result_dto_categories  | UA   | 🔴 P0     | 10.2.1    |
| UA-DTO-005 | test_coherence_result_dto_weights_sum | UA   | 🔴 P0     | 10.2.2    |
| UA-DTO-006 | test_coherence_result_dto_score_range | UA   | 🟠 P1     | 10.2.3    |
| UA-DTO-007 | test_alert_dto_required_fields        | UA   | 🔴 P0     | 10.1.1    |
| UA-DTO-008 | test_alert_dto_severity_enum          | UA   | 🟠 P1     | 10.1.1    |
| UA-DTO-009 | test_clause_dto_required_fields       | UA   | 🔴 P0     | 10.1.1    |
| UA-DTO-010 | test_bom_item_dto_required_fields     | UA   | 🔴 P0     | 10.1.1    |
| UA-DTO-011 | test_stakeholder_dto_required_fields  | UA   | 🟠 P1     | 10.1.1    |
| UA-DTO-012 | test_raci_matrix_dto_validation       | UA   | 🟠 P1     | 10.1.1    |
| UA-DTO-013 | test_serialization_uuid_to_string     | UA   | 🟠 P1     | 10.3.1    |
| UA-DTO-014 | test_serialization_date_iso8601       | UA   | 🟠 P1     | 10.3.2    |
| UA-DTO-015 | test_serialization_nested_dto         | UA   | 🟠 P1     | 10.3.3    |
| UA-DTO-016 | test_deserialization_string_to_uuid   | UA   | 🟠 P1     | 10.3.1    |
| UA-DTO-017 | test_deserialization_date_from_string | UA   | 🟠 P1     | 10.3.2    |
| UA-DTO-018 | test_deserialization_nested_dto       | UA   | 🟠 P1     | 10.3.3    |

### 3.3 UNIT TESTS - ADAPTERS LAYER (58 tests)

#### 3.3.1 HTTP Adapters / Routers (32 tests)

| ID           | Test Name                                   | Tipo | Prioridad | Ciclo TDD |
| ------------ | ------------------------------------------- | ---- | --------- | --------- |
| UAD-HTTP-001 | test_documents_router_upload_success        | UAD  | 🔴 P0     | 10.4.1    |
| UAD-HTTP-002 | test_documents_router_upload_invalid_body   | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-003 | test_documents_router_get_clauses           | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-004 | test_projects_router_create_success         | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-005 | test_projects_router_get_wbs                | UAD  | 🟠 P1     | 10.4.2    |
| UAD-HTTP-006 | test_projects_router_invalid_uuid           | UAD  | 🟠 P1     | 10.4.3    |
| UAD-HTTP-007 | test_procurement_router_get_bom             | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-008 | test_procurement_router_calculate_lead_time | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-009 | test_coherence_router_get_score             | UAD  | 🔴 P0     | 10.4.1    |
| UAD-HTTP-010 | test_coherence_router_get_dashboard         | UAD  | 🟠 P1     | 11.2      |
| UAD-HTTP-011 | test_coherence_router_recalculate           | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-012 | test_stakeholders_router_get_map            | UAD  | 🟠 P1     | 11.2      |
| UAD-HTTP-013 | test_stakeholders_router_get_raci           | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-014 | test_alerts_router_get_all                  | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-015 | test_alerts_router_get_by_category          | UAD  | 🟠 P1     | 11.2      |
| UAD-HTTP-016 | test_alerts_router_approve                  | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-017 | test_alerts_router_reject                   | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-018 | test_alerts_router_bulk_approve             | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-019 | test_evidence_router_get_by_clause          | UAD  | 🟠 P1     | 11.2      |
| UAD-HTTP-020 | test_mcp_gateway_router_validate            | UAD  | 🔴 P0     | 1.1.1     |
| UAD-HTTP-021 | test_mcp_gateway_router_rate_limited        | UAD  | 🔴 P0     | 1.2.1     |
| UAD-HTTP-022 | test_auth_middleware_valid_jwt              | UAD  | 🔴 P0     | 6.2.1     |
| UAD-HTTP-023 | test_auth_middleware_invalid_jwt            | UAD  | 🔴 P0     | 6.2.1     |
| UAD-HTTP-024 | test_auth_middleware_expired_jwt            | UAD  | 🟠 P1     | 6.2.1     |
| UAD-HTTP-025 | test_tenant_middleware_extraction           | UAD  | 🔴 P0     | 6.2.1     |
| UAD-HTTP-026 | test_tenant_middleware_missing              | UAD  | 🟠 P1     | 6.2.1     |
| UAD-HTTP-027 | test_error_handler_validation_error         | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-028 | test_error_handler_not_found                | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-029 | test_error_handler_internal_error           | UAD  | 🟠 P1     | 10.4.1    |
| UAD-HTTP-030 | test_cors_middleware_allowed_origin         | UAD  | 🟡 P2     | 10.4.1    |
| UAD-HTTP-031 | test_cors_middleware_blocked_origin         | UAD  | 🟡 P2     | 10.4.1    |
| UAD-HTTP-032 | test_request_id_middleware_generation       | UAD  | 🟠 P1     | 9.2.1     |

#### 3.3.1.1 Estado de Suites (HTTP Adapters)

- [x] TS-UAD-HTTP-ERR-001 - Error Handlers (Implemented: Unit Tests & Core HTTP Error Handling)

#### 3.3.2 Persistence Adapters (26 tests)

| ID           | Test Name                                     | Tipo | Prioridad | Ciclo TDD |
| ------------ | --------------------------------------------- | ---- | --------- | --------- |
| UAD-PERS-001 | test_clause_repository_model_mapping          | UAD  | 🔴 P0     | 2.4.1     |
| UAD-PERS-002 | test_document_repository_model_mapping        | UAD  | 🔴 P0     | 2.1.1     |
| UAD-PERS-003 | test_wbs_item_repository_model_mapping        | UAD  | 🔴 P0     | 3.3.1     |
| UAD-PERS-004 | test_bom_item_repository_model_mapping        | UAD  | 🟠 P1     | 4.3.1     |
| UAD-PERS-005 | test_stakeholder_repository_model_mapping     | UAD  | 🟠 P1     | 7.1.1     |
| UAD-PERS-006 | test_alert_repository_model_mapping           | UAD  | 🟠 P1     | 5.4.1     |
| UAD-PERS-007 | test_coherence_score_repository_model_mapping | UAD  | 🔴 P0     | 6.7.1     |
| UAD-PERS-008 | test_audit_log_repository_model_mapping       | UAD  | 🟠 P1     | 14.1.1    |
| UAD-PERS-009 | test_ai_usage_repository_model_mapping        | UAD  | 🟠 P1     | 9.4.1     |
| UAD-PERS-010 | test_tenant_filter_application                | UAD  | 🔴 P0     | 6.2.2     |
| UAD-PERS-011 | test_tenant_filter_missing_context            | UAD  | 🟠 P1     | 6.2.2     |
| UAD-PERS-012 | test_soft_delete_implementation               | UAD  | 🟡 P2     | 2.4.1     |
| UAD-PERS-013 | test_timestamp_auto_population                | UAD  | 🟡 P2     | 2.4.1     |
| UAD-PERS-014 | test_jsonb_field_serialization                | UAD  | 🟠 P1     | 6.7.1     |
| UAD-PERS-015 | test_jsonb_field_deserialization              | UAD  | 🟠 P1     | 6.7.1     |
| UAD-PERS-016 | test_vector_field_storage                     | UAD  | 🟠 P1     | 5.3.1     |
| UAD-PERS-017 | test_vector_similarity_query                  | UAD  | 🟠 P1     | 5.3.1     |
| UAD-PERS-018 | test_graph_node_adapter_create                | UAD  | 🟠 P1     | 5.1.1     |
| UAD-PERS-019 | test_graph_node_adapter_query                 | UAD  | 🟠 P1     | 5.2.1     |
| UAD-PERS-020 | test_graph_relationship_adapter_create        | UAD  | 🟠 P1     | 5.1.2     |
| UAD-PERS-021 | test_redis_cache_adapter_set                  | UAD  | 🟠 P1     | 1.2.1     |
| UAD-PERS-022 | test_redis_cache_adapter_get                  | UAD  | 🟠 P1     | 1.2.1     |
| UAD-PERS-023 | test_redis_cache_adapter_expire               | UAD  | 🟠 P1     | 1.2.1     |
| UAD-PERS-024 | test_r2_storage_adapter_upload                | UAD  | 🟠 P1     | 6.5.1     |
| UAD-PERS-025 | test_r2_storage_adapter_download              | UAD  | 🟠 P1     | 6.5.1     |
| UAD-PERS-026 | test_r2_storage_adapter_delete                | UAD  | 🟡 P2     | 6.5.1     |

#### 3.3.2.1 Estado de Suites (Persistence Adapters)

- [x] TS-UAD-PER-GRP-001 - Graph Adapters (Neo4j) (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UAD-PER-R2-001 - R2 Storage Adapters (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UAD-PER-RDS-001 - Redis Adapters (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UAD-PER-REP-001 - All Repositories (Implemented: Unit Tests & Adapter Logic)

---

## 4. Índice Completo por Módulo

### 4.1 Módulo: DOCUMENTS (48 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 28     | -           | -     | 28     |
| Application | 8      | -           | -     | 8      |
| Adapters    | 5      | -           | -     | 5      |
| Integration | -      | 5           | -     | 5      |
| E2E         | -      | -           | 2     | 2      |
| **Total**   | **41** | **5**       | **2** | **48** |

#### 4.1.1 Estado de Suites (Documents Domain)

- [x] TS-UD-DOC-CLS-001 - Clause Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-CLS-002 - Clause Types & Classification (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-CLS-003 - SubClause Hierarchy (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-DOC-001 - Document Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-ENT-001 - Entity Extraction - Dates (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-ENT-002 - Entity Extraction - Money (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-ENT-003 - Entity Extraction - Durations (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-ENT-004 - Entity Extraction - Stakeholders (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-DOC-CNF-001 - Confidence Scoring (Implemented: Unit Tests & Domain Logic)

#### 4.1.2 Estado de Suites (Documents Integration)

- [x] TS-INT-DB-CLS-001 - Clause Repository + DB (Implemented: Integration Tests & Persistence Logic)
- [x] TS-INT-DB-DOC-001 - Document Repository + DB (Implemented: Integration Tests & Persistence Logic)
- [x] TS-INT-MOD-DOC-001 - Documents → Analysis Integration (Implemented: Integration Tests & Mapping Use Case)

#### 4.1.3 Estado de Suites (Documents Application)

- [x] TS-UA-DOC-UC-001 - Upload Document Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-DOC-UC-002 - Extract Clauses Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-DOC-UC-003 - Extract Entities Use Case (Implemented: Unit Tests & Application Logic)

#### 4.1.4 Estado de Suites (Documents Application Services)

- [x] TS-UA-SVC-EXT-001 - Clause Extraction Service (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-SVC-EXT-002 - Entity Extraction Service (Implemented: Unit Tests & Application Logic)

### 4.2 Módulo: COHERENCE (56 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 42     | -           | -     | 42     |
| Application | 6      | -           | -     | 6      |
| Adapters    | 3      | -           | -     | 3      |
| Integration | -      | 3           | -     | 3      |
| E2E         | -      | -           | 2     | 2      |
| **Total**   | **51** | **3**       | **2** | **56** |

#### 4.2.1 Estado de Suites (Coherence Domain)

- [x] TS-UD-COH-CAT-001 - Category Enum & Weights (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-001 - Coherence Rules: Scope Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-002 - Coherence Rules: Budget Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-003 - Coherence Rules: Time Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-004 - Coherence Rules: Technical Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-005 - Coherence Rules: Legal Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-RUL-006 - Coherence Rules: Quality Category (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-SCR-001 - Score Calculator: SubScores (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-SCR-002 - Score Calculator: Global Score (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-SCR-003 - Score Calculator: Custom Weights (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-GAM-001 - Anti-Gaming Policy (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-COH-ALR-001 - Alert Entity & Mapping (Implemented: Unit Tests & Domain Logic)

### 4.3 Módulo: PROJECTS (36 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 24     | -           | -     | 24     |
| Application | 5      | -           | -     | 5      |
| Adapters    | 3      | -           | -     | 3      |
| Integration | -      | 3           | -     | 3      |
| E2E         | -      | -           | 1     | 1      |
| **Total**   | **32** | **3**       | **1** | **36** |

#### 4.3.1 Estado de Suites (Projects Domain)

- [x] TS-UD-PRJ-WBS-001 - WBS Item Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PRJ-WBS-002 - WBS Hierarchy & Codes (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PRJ-WBS-003 - WBS Validation Rules (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PRJ-WBS-004 - WBS CRUD Operations (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PRJ-PRJ-001 - Project Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PRJ-DTO-001 - WBSItemDTO & IWBSQueryPort (Implemented: Unit Tests & Domain Logic)

#### 4.3.2 Estado de Suites (Projects Application)

- [x] TS-UA-PRJ-UC-001 - Generate WBS Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-PRJ-UC-002 - CRUD WBS Item Use Case (Implemented: Unit Tests & Application Logic)

### 4.4 Módulo: PROCUREMENT (32 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 22     | -           | -     | 22     |
| Application | 4      | -           | -     | 4      |
| Adapters    | 2      | -           | -     | 2      |
| Integration | -      | 3           | -     | 3      |
| E2E         | -      | -           | 1     | 1      |
| **Total**   | **28** | **3**       | **1** | **32** |

#### 4.4.1 Estado de Suites (Procurement Domain)

- [x] TS-UD-PROC-BOM-001 - BOM Item Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-BOM-002 - BOM Validation Rules (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-LTM-001 - Lead Time Calculator - Basic (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-LTM-002 - Lead Time Calculator - Incoterms (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-LTM-003 - Lead Time Calculator - Customs (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-LTM-004 - Lead Time Alerts (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-PROC-PLN-001 - Procurement Plan Generation (Implemented: Unit Tests & Domain Logic)

#### 4.4.2 Estado de Suites (Procurement Application)

- [x] TS-UA-PROC-UC-001 - Generate BOM Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-PROC-UC-002 - Calculate Lead Time Use Case (Implemented: Unit Tests & Application Logic)

#### 4.4.3 Estado de Suites (Procurement Integration)

- [x] TS-INT-DB-WBS-001 - WBS Repository + DB (Implemented: Integration Tests & Persistence Logic)
- [x] TS-INT-DB-BOM-001 - BOM Repository + DB (Implemented: Integration Tests & Persistence Logic)
- [x] TS-INT-MOD-WBS-001 - WBS → Procurement Integration (Implemented: Integration Tests & Mapping Use Case)

#### 4.4.4 Estado de Suites (Security Audit Integration)

- [x] TS-INT-DB-AUD-001 - Audit Repository + DB (Implemented: Integration Tests & Persistence Logic)

### 4.5 Módulo: STAKEHOLDERS (26 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 18     | -           | -     | 18     |
| Application | 4      | -           | -     | 4      |
| Adapters    | 2      | -           | -     | 2      |
| Integration | -      | 1           | -     | 1      |
| E2E         | -      | -           | 1     | 1      |
| **Total**   | **24** | **1**       | **1** | **26** |

#### 4.5.1 Estado de Suites (Stakeholders Domain)

- [x] TS-UD-STK-ENT-001 - Stakeholder Entity (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-CLS-001 - Power/Interest Classification (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-CLS-002 - Quadrant Assignment (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-RAC-001 - RACI Entry Validation (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-RAC-002 - RACI Matrix Generation (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-RAC-003 - RACI from Clauses (Implemented: Unit Tests & Domain Logic)
- [x] TS-UD-STK-MAP-001 - Stakeholder Map Data (Implemented: Unit Tests & Domain Logic)

#### 4.5.2 Estado de Suites (Stakeholders Application)

- [x] TS-UA-STK-UC-001 - Extract Stakeholders Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-STK-UC-002 - Generate RACI Use Case (Implemented: Unit Tests & Application Logic)

#### 4.5.3 Estado de Suites (Stakeholders Integration)

- [x] TS-INT-MOD-STK-001 - Stakeholders → RACI Integration (Implemented: Integration Tests & Mapping Use Case)

### 4.6 Módulo: ANALYSIS (24 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 12     | -           | -     | 12     |
| Application | 5      | -           | -     | 5      |
| Adapters    | 3      | -           | -     | 3      |
| Integration | -      | 3           | -     | 3      |
| E2E         | -      | -           | 1     | 1      |
| **Total**   | **20** | **3**       | **1** | **24** |

#### 4.6.1 Estado de Suites (Analysis Domain)

- [x] TS-UD-ANA-GRP-001 - Graph Node Entity (Implemented: Unit Tests & Domain Logic)

#### 4.6.2 Estado de Suites (Analysis Integration)

- [x] TS-INT-MOD-ANA-001 - Analysis → Coherence Integration (Implemented: Integration Tests & Mapping Use Case)
- [x] TS-INT-EXT-LLM-001 - LLM Client Integration (Implemented: Integration Tests & LLM Adapter Flow)
- [x] TS-INT-EXT-LLM-002 - LLM Fallback Integration (Implemented: Integration Tests & Fallback Adapter)
- [x] TS-INT-GRP-NEO-001 - Neo4j Integration (Implemented: Integration Tests & Graph Adapter)

### 4.7 Módulo: SECURITY/MCP (38 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | 10     | -           | -     | 10     |
| Application | 12     | -           | -     | 12     |
| Adapters    | 8      | -           | -     | 8      |
| Integration | -      | 6           | -     | 6      |
| E2E         | -      | -           | 2     | 2      |
| **Total**   | **30** | **6**       | **2** | **38** |

#### 4.7.1 Estado de Suites (Security/MCP)

- [x] TS-UC-SEC-MCP-001 - MCP Gateway Allowlist (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UC-SEC-MCP-002 - MCP Gateway Rate Limiting (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UC-SEC-MCP-003 - MCP Gateway Query Limits (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UC-SEC-MCP-004 - MCP Gateway Audit (Implemented: Unit Tests & Adapter Logic)
- [x] TS-UC-SEC-JWT-001 - JWT Validation (Implemented: Unit Tests & Core Security Logic)
- [x] TS-UC-SEC-AUD-001 - Audit Trail Core (Implemented: Unit Tests & Core Security Logic)
- [x] TS-UC-SEC-ANO-001 - Anonymizer PII Detection (Implemented: Unit Tests & Domain Logic)
- [x] TS-UC-SEC-ANO-002 - Anonymizer Strategies (Implemented: Unit Tests & Application Logic)
- [x] TS-UC-SEC-ANO-003 - Anonymizer Tenant Config (Implemented: Unit Tests & Application Logic)
- [x] TS-UC-SEC-GAM-001 - Anti-Gaming Detection (Implemented: Unit Tests & Domain Logic)
- [x] TS-UC-SEC-TNT-001 - Tenant Context & Isolation (Implemented: Unit Tests & Core Security Logic)
- [x] TS-UA-SEC-UC-001 - Validate MCP Operation Use Case (Implemented: Unit Tests & Application Logic)
- [x] TS-UA-SEC-UC-002 - Anonymize Document Use Case (Implemented: Unit Tests & Application Logic)

### 4.8 Módulo: ASYNC/EVENTS (22 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | -      | -           | -     | -      |
| Application | 4      | -           | -     | 4      |
| Adapters    | 6      | -           | -     | 6      |
| Integration | -      | 10          | -     | 10     |
| E2E         | -      | -           | 2     | 2      |
| **Total**   | **10** | **10**      | **2** | **22** |

#### 4.8.1 Estado de Suites (Async/Events)

- [x] TS-INT-EVT-BUS-001 - Event Bus Publish/Subscribe (Implemented: Integration Tests & Core Event Bus Logic)
- [x] TS-INT-EVT-BUS-001 - Redis Event Bus Runtime Hardening (tenant transport isolation + safe telemetry metadata + correlation-id replay protection) - [x] Implemented (Unit Tests & Adapter Logic)
- [x] TS-INT-EVT-CEL-001 - Celery Job Queue (Implemented: Integration Tests & Task Queue Adapter Logic)
- [x] TS-INT-EVT-DLQ-001 - Dead Letter Queue (Implemented: Integration Tests & Core Event Bus Logic)

### 4.9 Módulo: OBSERVABILITY (18 tests total)

| Capa        | Unit   | Integration | E2E   | Total  |
| ----------- | ------ | ----------- | ----- | ------ |
| Domain      | -      | -           | -     | -      |
| Application | 6      | -           | -     | 6      |
| Adapters    | 6      | -           | -     | 6      |
| Integration | -      | 4           | -     | 4      |
| E2E         | -      | -           | 2     | 2      |
| **Total**   | **12** | **4**       | **2** | **18** |

### 4.10 Módulo: API CONTRACTS (24 tests total)

| Capa           | Unit   | Integration | E2E   | Total  |
| -------------- | ------ | ----------- | ----- | ------ |
| DTOs           | 18     | -           | -     | 18     |
| Adapters       | -      | -           | -     | -      |
| Contract Tests | -      | 6           | -     | 6      |
| **Total**      | **18** | **6**       | **0** | **24** |

#### 4.10.1 Estado de Suites (API Contracts)

- [x] TS-UA-DTO-ALL-001 - All DTOs Validation (Implemented: Unit Tests & Application DTO Logic)
- [x] TS-UA-DTO-SER-001 - Serialization/Deserialization (Implemented: Unit Tests & Core Serialization Logic)

---

dos los módulos | 3 |
| 2 | Security Domain | MCP Gateway | 2 |
| 3 | Anonymizer Service | Documents | 4 |
| 4 | MCP Gateway | Todos los endpoints | 3 |
| 5 | Event Bus | Async flows | 4 |
| 6 | Clause Entity | Analysis, Stakeholders | 5 |
| 7 | Document Repository | Document flows | 3 |
| 8 | WBS Domain | Procurement | 5 |
| 9 | Stakeholders Domain | RACI | 4 |
| 10 | Graph Repository | Analysis | 4 |
| 11 | BOM Domain | Lead Time | 4 |
| 12 | Lead Time Calculator | Procurement alerts | 3 |
| 13 | Coherence Rules | Score Calculator | 8 |
| 14 | Score Calculator | Dashboard | 3 |
| 15 | Anti-Gaming | Compliance | 4 |
| 16 | Integration Flows | E2E | 6 |
| 17 | E2E Core | Release | 5 |

---

## 9. Métricas y KPIs de Testing

### 9.1 KPIs Objetivo

| Métrica                        | Target | Mínimo Aceptable |
| ------------------------------ | ------ | ---------------- |
| **Code Coverage (Lines)**      | 90%    | 80%              |
| **Code Coverage (Branches)**   | 85%    | 75%              |
| **Mutation Score**             | 80%    | 70%              |
| **Unit Test Pass Rate**        | 100%   | 100%             |
| **Integration Test Pass Rate** | 100%   | 98%              |
| **E2E Test Pass Rate**         | 100%   | 95%              |
| **Test Execution Time (Unit)** | <2min  | <5min            |
| **Test Execution Time (Int.)** | <10min | <15min           |
| **Test Execution Time (E2E)**  | <20min | <30min           |
| **Flaky Test Rate**            | 0%     | <2%              |

### 9.2 Métricas por Módulo

| Módulo        | Coverage Target | Tests P0 | Tests Total |
| ------------- | --------------- | -------- | ----------- |
| Documents     | 90%             | 18       | 48          |
| Coherence     | 95%             | 28       | 56          |
| Projects      | 85%             | 12       | 36          |
| Procurement   | 85%             | 10       | 32          |
| Stakeholders  | 85%             | 8        | 26          |
| Analysis      | 80%             | 8        | 24          |
| Security/MCP  | 95%             | 22       | 38          |
| Async/Events  | 85%             | 8        | 22          |
| Observability | 80%             | 6        | 18          |
| API Contracts | 90%             | 12       | 24          |

### 9.3 Dashboard de Progreso

> **Última Actualización:** 2026-02-14

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DASHBOARD DE PROGRESO TDD                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TESTS TOTALES: 487                                                        │
│  ══════════════════════════════════════════════════════════════════════    │
│  ████████████████████████████████████████████░░░░░░░  ~87% (424/487)       │
│                                                                             │
│  POR PRIORIDAD:                                                            │
│  ├── 🔴 P0 (Crítico):  ████████████████████  100% (156/156)               │
│  ├── 🟠 P1 (Alto):     ████████████████████  100% (198/198)               │
│  ├── 🟡 P2 (Medio):    ██████████████░░░░░░   79% (70/89)                 │
│  └── 🟢 P3 (Bajo):     ░░░░░░░░░░░░░░░░░░░░    0% (0/44)                 │
│                                                                             │
│  POR TIPO:                                                                  │
│  ├── Unit Tests:       ████████████████████  100% (312/312)               │
│  ├── Integration:      ████████████████████  100% (127/127)               │
│  └── E2E:              ░░░░░░░░░░░░░░░░░░░░    0% (0/48)                  │
│                                                                             │
│  POR MÓDULO:                                                               │
│  ├── Documents:        ████████████████████  100% (48/48)                  │
│  ├── Coherence:        ████████████████████  100% (56/56)                  │
│  ├── Projects:         ████████████████████  100% (36/36)                  │
│  ├── Procurement:      ████████████████████  100% (32/32)                  │
│  ├── Stakeholders:     ████████████████████  100% (26/26)                  │
│  ├── Analysis:         ████████████████████  100% (24/24)                  │
│  ├── Security/MCP:     ████████████████████  100% (38/38)                  │
│  ├── Async/Events:     ████████████████████  100% (22/22)                  │
│  ├── Observability:    ████████████████░░░░   78% (14/18)                  │
│  └── API Contracts:    ████████████████████  100% (24/24)                  │
│                                                                             │
│  SUITES COMPLETADAS: 78/89     SPRINTS COMPLETADOS: ~12/22                 │
│                                                                             │
│  NOTA: Los conteos reflejan suites marcadas como [x] Implemented en las    │
│  secciones 4.x de este documento. E2E tests y P3 pendientes para Fase 3.  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Anexos

### 10.1 Anexo A: Configuración de pytest

```python
# conftest.py

import pytest
from typing import Generator
from unittest.mock import MagicMock
from uuid import uuid4

# ============================================
# FIXTURES GLOBALES
# ============================================

@pytest.fixture
def tenant_id() -> str:
    """Fixture para tenant_id consistente en tests."""
    return "tenant_test_001"

@pytest.fixture
def user_id() -> str:
    """Fixture para user_id consistente en tests."""
    return str(uuid4())

@pytest.fixture
def trace_id() -> str:
    """Fixture para trace_id."""
    return f"trace_{uuid4().hex[:16]}"

# ============================================
# MOCKS DE SERVICIOS EXTERNOS
# ============================================

@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Mock del cliente LLM (Anthropic/OpenAI)."""
    mock = MagicMock()
    mock.complete.return_value = {"content": "mocked response"}
    return mock

@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock del cliente Redis."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.incr.return_value = 1
    return mock

@pytest.fixture
def mock_neo4j_session() -> MagicMock:
    """Mock de sesión Neo4j."""
    mock = MagicMock()
    mock.run.return_value = []
    return mock

# ============================================
# FACTORIES
# ============================================

@pytest.fixture
def clause_factory():
    """Factory para crear Clause entities."""
    def _create_clause(**kwargs):
        defaults = {
            "id": uuid4(),
            "tenant_id": "tenant_test",
            "document_id": uuid4(),
            "content": "Test clause content",
            "clause_type": "general",
            "confidence_score": 0.95
        }
        defaults.update(kwargs)
        from domain.documents.entities import Clause
        return Clause(**defaults)
    return _create_clause

@pytest.fixture
def wbs_item_factory():
    """Factory para crear WBSItem entities."""
    def _create_wbs_item(**kwargs):
        defaults = {
            "id": uuid4(),
            "code": "1.1",
            "name": "Test WBS Item",
            "level": 1,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31"
        }
        defaults.update(kwargs)
        from domain.projects.entities import WBSItem
        return WBSItem(**defaults)
    return _create_wbs_item

@pytest.fixture
def alert_factory():
    """Factory para crear Alert entities."""
    def _create_alert(**kwargs):
        defaults = {
            "id": uuid4(),
            "rule": "R1",
            "category": "TIME",
            "severity": "high",
            "message": "Test alert message"
        }
        defaults.update(kwargs)
        from domain.analysis.entities import Alert
        return Alert(**defaults)
    return _create_alert

# ============================================
# MARKERS PERSONALIZADOS
# ============================================

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "critical: P0 critical tests")
```

### 10.2 Anexo B: Plantilla de Test TDD

```python
# Template para nuevos tests siguiendo TDD estricto

"""
Test Suite: [NOMBRE]
Componente: [COMPONENTE]
Ciclo TDD: [X.Y.Z]
Prioridad: [P0/P1/P2/P3]
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

# ============================================
# 🔴 RED PHASE - Tests que deben fallar inicialmente
# ============================================

class TestComponentFunctionality:
    """
    Suite de tests para [FUNCIONALIDAD].

    Sigue el patrón TDD:
    1. 🔴 RED: Escribir test que falla
    2. 🟢 GREEN: Implementar código mínimo para pasar
    3. 📐 REFACTOR: Triangular con más casos
    """

    # ----------------------------------------
    # Ciclo TDD X.Y.1: [Funcionalidad Base]
    # ----------------------------------------

    @pytest.mark.unit
    @pytest.mark.critical
    def test_basic_functionality_success(self):
        """
        🔴 RED Test Case A: [Descripción del caso base]

        Given: [Precondiciones]
        When: [Acción]
        Then: [Resultado esperado]
        """
        # Arrange
        input_data = {...}
        expected_output = {...}

        # Act
        # result = component.method(input_data)

        # Assert
        # assert result == expected_output
        pytest.fail("🔴 RED: Implementar test")

    @pytest.mark.unit
    def test_basic_functionality_triangulation(self):
        """
        📐 TRIANGULATION Test Case B: [Caso que fuerza lógica real]

        Given: [Precondiciones diferentes]
        When: [Misma acción]
        Then: [Resultado diferente esperado]
        """
        pytest.fail("📐 TRIANGULATION: Implementar después de GREEN")

    # ----------------------------------------
    # Ciclo TDD X.Y.2: [Funcionalidad Avanzada]
    # ----------------------------------------

    @pytest.mark.unit
    def test_advanced_functionality_edge_case(self):
        """
        🔴 RED Test Case: [Caso borde]
        """
        pytest.fail("🔴 RED: Implementar test")

    # ----------------------------------------
    # Ciclo TDD X.Y.3: [Manejo de Errores]
    # ----------------------------------------

    @pytest.mark.unit
    def test_error_handling_invalid_input(self):
        """
        🔴 RED Test Case: [Error esperado con input inválido]
        """
        # Arrange
        invalid_input = {...}

        # Act & Assert
        # with pytest.raises(ExpectedError):
        #     component.method(invalid_input)
        pytest.fail("🔴 RED: Implementar test")


# ============================================
# 🟢 GREEN PHASE - Estrategias de implementación
# ============================================

"""
ESTRATEGIA GREEN para este suite:

1. test_basic_functionality_success:
   - Fake It: return expected_output directamente

2. test_basic_functionality_triangulation:
   - Obvious Implementation: if condition A: return X else: return Y

3. test_advanced_functionality_edge_case:
   - Triangulate: agregar lógica para manejar edge case
"""
```

### 10.3 Anexo C: Checklist Pre-Commit

```markdown
## Checklist de Tests Pre-Commit

### Antes de cada commit, verificar:

- [ ] Todos los tests unitarios pasan (`pytest tests/unit -v`)
- [ ] Coverage > 80% en código nuevo (`pytest --cov`)
- [ ] No hay tests marcados como `skip` sin justificación
- [ ] No hay tests con `pytest.fail("TODO")` en código completado
- [ ] Linting pasa (`ruff check .`)
- [ ] Type checking pasa (`mypy .`)

### Antes de cada PR, verificar:

- [ ] Tests de integración pasan (`pytest tests/integration -v`)
- [ ] No hay flaky tests
- [ ] Coverage total > 85%
- [ ] E2E críticos pasan (`pytest tests/e2e -m critical`)
- [ ] Documentación de tests actualizada
```

### 10.4 Anexo D: Glosario de Tests

| Término              | Definición                                                     |
| -------------------- | -------------------------------------------------------------- |
| **Unit Test**        | Test aislado de una unidad de código sin dependencias externas |
| **Integration Test** | Test que verifica la integración entre componentes             |
| **E2E Test**         | Test que simula un flujo completo de usuario                   |
| **Contract Test**    | Test que verifica contratos de API entre servicios             |
| **Fake It**          | Estrategia TDD de implementar la solución más simple posible   |
| **Triangulation**    | Agregar tests que fuercen una implementación más general       |
| **Red Phase**        | Fase donde el test falla porque el código no existe            |
| **Green Phase**      | Fase donde se escribe código mínimo para pasar el test         |
| **Refactor Phase**   | Fase donde se mejora el código manteniendo tests verdes        |
| **Fixture**          | Datos o estado predefinido para tests                          |
| **Mock**             | Objeto simulado que reemplaza dependencias reales              |
| **Stub**             | Implementación simplificada que retorna valores fijos          |
| **Coverage**         | Porcentaje de código ejecutado por tests                       |
| **Mutation Testing** | Técnica que introduce bugs para verificar calidad de tests     |

---

## 11. Historial de Cambios

| Versión | Fecha      | Autor                     | Cambios         |
| ------- | ---------- | ------------------------- | --------------- |
| 1.0     | 2026-01-31 | Architecture Review Board | Versión inicial |
| 1.1     | 2026-02-14 | Architecture Review Board | Actualización de estado S1 Core AI (I1/I2) en plan por sprints |
| 1.2     | 2026-02-14 | Architecture Review Board | Actualización de estado S2 Core AI (I3/I4) + security gate assertions |
| 1.3     | 2026-02-14 | Architecture Review Board | Actualización de estado S3 Core AI (I5/I6) + security assertions graph/coherence |
| 1.4     | 2026-02-14 | Architecture Review Board | Actualización de estado S4 Core AI (I7/I8/I9) + security assertions scoring/wbs/procurement |
| 1.5     | 2026-02-15 | Architecture Review Board | Actualización de estado S5 Core AI (I10/I11/I12) + security assertions + DevOps CI/scheduled drift checks |
| 1.6     | 2026-02-15 | Architecture Review Board | Cierre Redis Event Bus: hardening de seguridad/telemetría + bootstrap Redis determinístico local/CI |
| 1.7     | 2026-02-15 | Architecture Review Board | Cierre WS-F S6: runbook I13 real E2E + checklist de prerrequisitos + rationale/riesgos de parche de migración |
| 1.8     | 2026-02-15 | Architecture Review Board | Cierre WS-G S6: contrato RLS GUC `app.current_tenant` (RED→GREEN), bootstrap a nivel conexión PostgreSQL y validación E2E de aislamiento tenant |

---

## 12. Aprobaciones

| Rol                     | Nombre                     | Fecha      | Firma |
| ----------------------- | -------------------------- | ---------- | ----- |
| Lead Software Architect | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | ☐     |
| QA Lead                 | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | ☐     |
| Tech Lead               | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | ☐     |
| Product Owner           | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | ☐     |

---

> **Documento generado por:** Architecture Review Board  
> **Fecha:** 2026-01-31  
> **Versión:** 1.0  
> **Estado:** PENDIENTE APROBACIÓN  
> **Próxima revisión:** Después de Sprint 2

---

## 6. Plan de Ejecución por Sprints

### Sprint 1 (Frontend v4.0)

- [x] S1-15 - Document layer rules ADR (Server vs Client Components) — Implemented (Documentation + CI test)

### Sprint 2 (Frontend v4.0)

- [x] S2-01 - @mswjs/data seed models (8 entities) — Implemented (Seeded demo DB + integration test)
- [x] S2-02 - Custom MSW handlers (demo data + SSE) — Implemented (Handlers + integration test)
- [x] S2-03 - Orval CI check enforcement — Implemented (frontend-ci.yml includes `pnpm generate:api:check`)
- [x] S2-04 - `useProcessingStore` (Zustand) — Implemented (Store + unit tests)
- [x] S2-05 - Project list page (Server Component) — Implemented (Server fetch + table component + unit test)
- [x] S2-06 - Project detail layout (7 tabs) — Implemented (ProjectTabs component + layout)
- [x] S2-07 - Custom SVG CoherenceGauge + 6 ScoreCards — Implemented (SVG gauge + ScoreCard component)
- [x] S2-08 - Weight adjuster (UI-only) — Implemented (client component + unit tests)
- [x] S2-09 - Document upload (drag-drop, PDF/XLSX/BC3, chunked) — Implemented (Dropzone + upload queue + chunk planner + upload integration tests)
- [x] S2-10 - SSE processing stepper + withCredentials — Implemented (ProcessingStepper + credentialed EventSource + SSE integration tests)
- [x] S2-11 - Three-layer SC test strategy — Implemented (FLAG-13 ADR + CI/E2E workflow guardrails)
- [x] S2-12 - Sprint 2 test inventory gate (35 unit + 12 integration + 4 E2E) — Implemented (S2-12 scaffold suites + acceptance flow spec)

### Sprint 3 (Frontend v4.0)

- [x] S3-01 - PDF renderer (lazy) + clause highlighting — Implemented (PdfEvidenceViewer + highlight mapper/style/navigation + integration coverage)
- [x] S3-02 - Mobile Evidence Viewer (tab interface) — Implemented (MobileEvidenceViewer tab shell + ARIA semantics + state continuity + integration coverage)

### Sprint 1 (Core AI Pipeline v4.0)

- [x] TS-I1-CIC-001 - Canonical Ingestion Contract - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I2-OCR-TBL-001 - OCR + Table Parsing Reliability - [x] Implemented (Unit Tests & Domain Logic)

### Sprint 2 (Core AI Pipeline v4.0)

- [x] TS-I3-CLS-DOM-001 / TS-I3-CLS-SVC-001 - Clause Extraction + Normalization - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I4-ROUTER-001 / TS-I4-RAG-SVC-001 - Hybrid RAG Retrieval Correctness - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-SEC-EXT-RET-001 - Security Gate Assertions (low-evidence/high-risk outputs require review) - [x] Implemented (Unit Tests & Domain Logic)

### Sprint 3 (Core AI Pipeline v4.0)

- [x] TS-I5-GRAPH-DOM-001 / TS-I5-GRAPH-APP-001 - Graph Schema + Relationship Integrity - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I6-COH-RULES-001 / TS-I6-COH-CONTRACT-001 / TS-I6-COH-SVC-001 - Coherence Rule Engine + Alert Contract - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-SEC-GRAPH-COH-001 - Security Assertions (referential validation, rules/scoring decoupling, High/Critical review flags) - [x] Implemented (Unit Tests & Domain Logic)

### Sprint 4 (Core AI Pipeline v4.0)

- [x] TS-I7-SCORE-DOM-001 / TS-I7-SCORE-PROFILES-001 / TS-I7-SCORE-SVC-001 - Risk Scoring + Coherence Score Aggregation - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I8-WBS-BOM-DOM-001 / TS-I8-WBS-BOM-APP-001 - WBS/BOM Generation Integrity + Traceability - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I9-PROC-DOM-001 / TS-I9-PROC-APP-001 - Procurement Planning Intelligence (lead-time/conflict deterministic logic) - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-SEC-S4-001 - Security Assertions (no cross-tenant profile leakage, traceability enforcement, no high-impact bypass) - [x] Implemented (Unit Tests & Domain Logic)

### Sprint 5 (Core AI Pipeline v4.0)

- [x] TS-I10-STK-DOM-001 / TS-I10-STK-APP-001 - Stakeholder Resolution + RACI Inference - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I11-HITL-DOM-001 / TS-I11-HITL-APP-001 - Human-in-the-Loop Workflow Enforcement - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-I12-OBS-DOM-001 / TS-I12-OBS-APP-001 - LangSmith Observability + Evaluation Harness - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-SEC-S5-001 - Security Assertions (no HITL bypass, reviewer metadata required, trace sanitization, drift escalation gating) - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-DEVOPS-S5-001 - CI gates for I10-I12 + scheduled drift checks + escalation hooks - [x] Implemented (Unit Tests & Domain Logic)

### Sprint 6 (Core AI Pipeline v4.0)

- [x] TS-I13-E2E-REAL-001 - I13 Decision Intelligence real E2E path (route contract + deterministic auth/tenant harness) - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-DEVOPS-S6-001 - Blocking CI gate `i13-real-e2e` + scheduled reliability workflow with infra preflight and diagnostics artifacts - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-DOC-S6-001 - WS-F documentation closure (tactical checklist prerequisites + architecture/backlog updates + `docs/runbooks/I13_REAL_E2E_INFRA_RUNBOOK.md`) - [x] Implemented (Unit Tests & Domain Logic)
- [x] TS-E2E-SEC-TNT-001 - WS-G RLS GUC contract hardening (`app.current_tenant`) + deterministic tenant-isolation E2E assertions - [x] Implemented (RED/GREEN validated in E2E Security Suite)
- [x] TS-E2E-FLW-BLK-001 - Bulk Operations E2E flow contract (limits, async jobs, progress, partial success, atomic rollback, throttling, tenant isolation) - [x] Implemented (RED/GREEN validated in E2E Flow Suite)
- [x] TS-E2E-ERR-TIM-001 - Timeout & fallback resilience contract (timeout mapping, retry budget, circuit open/close, tenant isolation, traceability headers) - [x] Implemented (RED/GREEN validated in E2E Resilience Suite)
- [x] TS-E2E-ERR-CON-001 - Concurrent modifications resilience contract (optimistic locking, ETag/If-Match preconditions, conflict codes, idempotency replay protection) - [x] Implemented (RED/GREEN validated in E2E Resilience Suite)
