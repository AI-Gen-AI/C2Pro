# C2Pro - Diagrama de Flujo del Proyecto (Mermaid)

Este documento concentra el **flujo funcional del negocio** (casos de uso) en un solo diagrama Mermaid y un índice de flujos detallados para mantener contexto LLM.

## Indice de flujos

1. F1 - Onboarding y seguridad multi-tenant (Auth + RLS)
2. F2 - Creacion y gestion de proyectos
3. F3 - Ingesta de documentos (upload + storage)
4. F4 - Parsing y extraccion IA (clausulas, entidades)
5. F5 - Trazabilidad legal (clauses + FKs)
6. F6 - Knowledge Graph + Graph RAG
7. F7 - Coherence Engine (reglas deterministas + LLM)
8. F8 - Alertas y scoring (Coherence Score)
9. F9 - Stakeholder Intelligence + RACI
10. F10 - Procurement (WBS/BOM + plan de compras)
11. F11 - Human-in-the-loop (validacion y resolucion)
12. F12 - Observabilidad y costos IA

---

## Diagrama general (Mermaid)

```mermaid
flowchart TD
  %% Actores y UI
  U[Usuario / Equipo EPC] --> UI["Frontend Next.js - Dashboard / Alertas / RACI / Procurement"]

  %% Auth y seguridad (F1 - Cerrado)
  UI --> AUTH["Auth + JWT + Tenant Middleware<br>Roles: C2Pro Global Admin / Company Admin / Risk Validator / Documentalista / Project Viewer"]:::done
  AUTH --> API["API FastAPI (Routers por módulo + RLS)"]

  %% Proyecto (F2 - Cerrado)
  API --> P1["Projects: crear/listar/actualizar<br>Campos: nombre, país, moneda, fechas inicio/fin, valor contractual<br>Código auto-generado<br>Estados: Borrador  En Revisión  Activo"]:::done
  P1 --> DB[(PostgreSQL + RLS)]

  %% Ingesta documentos (F3 - Cerrado)
  API --> D1["Documents: upload/metadata + Watch carpeta<br>Formatos: PDF, Word, Excel (MVP watch)<br>Metadatos: tipo, descripción, fecha auto, usuario<br>Versiones: inmutables, retención 180 días, override manual 'vigente'"]:::done
  D1 --> R2[(Storage R2 / Cloudflare R2)]
  D1 --> DB

  %% Parsing y extracción IA (F4 - Cerrado)
  D1 --> PARSE[Parsing PDF/Word/Excel/BC3]:::done
  PARSE --> PII[PII Anonymizer]:::done
  PII --> LLM["Claude API + Circuit Breaker<br>Clasificación mixta: tipo documento + reglas deterministas + LLM fallback"]:::done
  LLM --> CLAUSE["Clause Extractor<br>Cláusulas + dominios (scope/legal/quality/budget/cronograma/technical)"]:::done
  LLM --> EXTR["Entity Extractors: fechas, importes, stakeholders, WBS items"]:::done

  %% Trazabilidad (F5 - Cerrado)
  CLAUSE --> CLAUSES[(clauses table - entidad central)]:::done
  EXTR --> STAKE["stakeholders table + campos manuales: email/teléfono/departamento"]:::done
  EXTR --> WBS[(wbs_items table)]:::done
  EXTR --> BOM[(bom_items table - Fase 2)]:::pending
  CLAUSES -->|FK clause_id| STAKE
  CLAUSES -->|FK clause_id| WBS
  CLAUSES -->|FK clause_id| BOM

  %% Knowledge Graph (F6 - Cerrado MVP)
  CLAUSES --> KG["Knowledge Graph: nodes/edges<br>MVP: clauses + stakeholders + WBS<br>BOM  Fase 2"]:::done
  STAKE --> KG
  WBS --> KG
  KG --> RAG["Graph RAG + MCP Views<br>Consultas multi-hop con trazabilidad"]:::done

  %% Coherence Engine (F7 - Cerrado)
  KG --> COH["Coherence Engine<br>12 reglas deterministas + LLM cualitativo<br>Score basado solo en alertas (penalizaciones por domain)"]:::done
  CLAUSES --> COH
  COH --> RULES["Reglas deterministas (YAML/DB) + LLM fallback"]:::done
  RULES --> ALERTS["alerts table<br>domain, severity, evidence, suggested_actions"]:::done
  RULES --> SCORE["coherence_score<br>global + por domain<br>tiempo real, pero 'En Revisión' hasta confirmación"]:::done

  %% Alertas y Scoring (F8 - Cerrado)
  ALERTS --> UI
  SCORE --> UI
  ALERTS --> NOTIF["Notificaciones: in-app + email opcional configurable<br>Recordatorio >48h high/critical (desactivable)"]:::done

  %% Stakeholder + RACI (F9 - Cerrado)
  STAKE --> RACI["RACI Matrix por WBS item<br>Generada automática + validación humana<br>Campos manuales editables"]:::done
  RACI --> UI

  %% Procurement (F10 - Cerrado MVP)
  WBS --> PROC["Procurement Plan<br>Lista priorizada BOM por fecha óptima pedido<br>Visibilidad + alertas riesgos (sin integración ERP)"]:::done
  BOM --> PROC
  PROC --> UI

  %% Human-in-the-loop (F11 - Cerrado)
  UI --> REVIEW["Human-in-the-loop<br>Obligatorio high/critical<br>Opciones: Aprobar / Rechazar / Ignorar / Nota / Re-ejecutar LLM"]:::done
  REVIEW --> ALERTS
  REVIEW --> SCORE

  %% Observabilidad (F12 - Cerrado)
  LLM --> LOGS["ai_usage_logs<br>tokens, cost, trace_id<br>Dashboard interno C2Pro solo<br>Alerta >$30/día por tenant"]:::done
  API --> LOGS
  LOGS --> UI["C2Pro Global Admin"]

  %% Tests y Resiliencia
  TEST["Unit/Integration Tests (TDD)"] --> PARSE
  TEST --> LLM
  TEST --> COH
  TEST --> REVIEW
  ERROR["Error Handling + Fallbacks"] --> LLM
  ERROR --> RULES

  %% Estilos
  classDef done fill:#90EE90,stroke:#333,stroke-width:2px
  classDef partial fill:#FFD700,stroke:#333,stroke-width:2px
  classDef pending fill:#FF6347,stroke:#333,stroke-width:2px
```

---

## F1 - Onboarding y seguridad multi-tenant (Auth + RLS)

**Objetivo:** aislar datos por tenant y habilitar acceso seguro.

- Entrada: alta de usuarios y login (JWT con tenant_id).
- Proceso: roles por nivel (C2Pro Global Admin multi-tenant, Company Admin, Risk Validator, Documentalista, Project Viewer) + permisos; middleware extrae tenant_id y aplica filtros.
- Salida: acceso por rol y tenant; Risk Validator puede cerrar alertas high/critical sin Company Admin; C2Pro Global Admin con alcance de soporte/operaciones.

---

## F2 - Creacion y gestion de proyectos

**Objetivo:** representar el proyecto EPC como entidad core.

- Entrada: datos de proyecto (por C2Pro Global Admin o Company Admin).
- Proceso: CRUD via Projects module con permisos por rol; Company Admin crea sin aprobacion, con posibilidad futura de validacion C2Pro por capacidad/volumen; Risk Validator puede editar/cerrar y gestionar estado "En Revision".
- Salida: project_id usado por documentos, analisis y procurement.

---

## F3 - Ingesta de documentos (upload + storage)

**Objetivo:** subir contrato, cronograma, presupuesto.

- Entrada: archivos PDF/Excel/Word/BC3 (y futuros formatos de cronograma).
- Proceso: upload, metadata y persistencia; watch por proyecto (carpeta sincronizada) con confirmacion de conflictos de version; subida permitida para Risk Validator y Documentalista.
- Salida: documento almacenado y listo para parsing.

---

## F4 - Parsing y extraccion IA (clausulas, entidades)

**Objetivo:** transformar documentos en datos estructurados.

- Entrada: documento almacenado.
- Proceso: parsing + anonymizer + LLM extraction; validacion humana posterior; revision automatica por umbral de confianza (numerico) y reglas por tipo de dato; parsing estructurado (Excel/BC3) prioriza validaciones deterministas y usa LLM solo si falta contexto.
- Salida: clausulas, entidades, estructuras.

---

## F5 - Trazabilidad legal (clauses + FKs)

**Objetivo:** asegurar evidencia trazable por clausula.

- Entrada: clausulas extraidas.
- Proceso: guardar clauses y relacionar FKs; separar trazabilidad legal, WBS/BOM y stakeholders.
- Salida: stakeholders/WBS/BOM/alerts con clause_id y trazabilidad por dominio; cualquier alerta debe tener clause_id o evidencia alternativa obligatoria.

---

## F6 - Knowledge Graph + Graph RAG

**Objetivo:** conectar entidades para consultas y evidencia.

- Entrada: clausulas + entidades.
- Proceso: nodos/edges + vistas MCP allowlist; RAG solo usa vistas allowlist y respeta RLS; politicas de redaccion/anonimizacion antes de respuestas.
- Salida: grafo navegable y RAG con trazabilidad.

---

## F7 - Coherence Engine (reglas deterministas + LLM)

**Objetivo:** detectar incoherencias entre documentos.

- Entrada: clausulas + entidades + grafo.
- Proceso: reglas deterministas y evaluadores LLM con umbrales de confianza y validacion humana para alertas criticas; versionado y auditoria de reglas.
- Salida: alertas y score de coherencia; cada alerta guarda rule_id, version, inputs y evidencias.

---

## F8 - Alertas y scoring (Coherence Score)

**Objetivo:** priorizar riesgos y cuantificar impacto.

- Entrada: resultados del motor de coherencia.
- Proceso: severidad, evidencia, scoring 0-100; clasificacion por dominios (scope, legal, quality, budget, cronograma, technical); score puede quedar "En Revision" hasta validacion humana; alertas high/critical bloquean estado "Activo" hasta revision.
- Salida: alertas en UI y score agregado por proyecto por dominio cuando hay datos suficientes.

---

## F9 - Stakeholder Intelligence + RACI

**Objetivo:** mapear stakeholders y responsabilidades.

- Entrada: menciones en clausulas/documentos.
- Proceso: clasificacion + matriz RACI; stakeholders creados por extraccion y manualmente.
- Salida: mapa de stakeholders y RACI en UI; en fase 2, alertas/acciones y recordatorios directos por stakeholder.

---

## F10 - Procurement (WBS/BOM + plan de compras)

**Objetivo:** conectar contrato con compras y materiales.

- Entrada: WBS y BOM generados (BOM puede ser manual y por IA).
- Proceso: versionado y plan de compras; validacion por Risk Validator.
- Salida: visibilidad de procurement y riesgos; fase 2; alertas de procurement se clasifican con los mismos criterios de coherence (costes, plazos, calidad) aplicados a compras.

---

## F11 - Human-in-the-loop (validacion y resolucion)

**Objetivo:** validacion humana obligatoria en outputs criticos.

- Entrada: alertas y findings.
- Proceso: revision, aprobacion, notas; aprobacion/rechazo por Risk Validator; sin SLA definido.
- Salida: alertas resueltas y score recalculado; feedback al sistema.

---

## F12 - Observabilidad y costos IA

**Objetivo:** trazabilidad de uso, costos y seguridad.

- Entrada: llamadas a LLM y eventos API.
- Proceso: logging estructurado + ai_usage_logs.
- Salida: dashboard de uso, costos y anomalias; foco interno C2Pro en fase actual; en fase 2, posible vista basica para cliente; limites/circuit breaker por tenant para evitar sobrecoste de APIs (gestion C2Pro).
