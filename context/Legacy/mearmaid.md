flowchart TD
  %% Actores y UI
  U[Usuario / Equipo EPC] --> UI["Frontend Next.js - Dashboard / Alertas / RACI / Procurement"]

  %% Auth y seguridad (F1 - Cerrado)
  UI --> AUTH["Auth + JWT + Tenant Middleware<br>Roles: C2Pro Global Admin / Company Admin / Risk Validator / Project Viewer"]:::done
  AUTH --> API["API FastAPI (Routers por módulo + RLS)"]

  %% Proyecto (F2 - Cerrado)
  API --> P1["Projects: crear/listar/actualizar<br>Campos: nombre, país, moneda, fechas inicio/fin, valor contractual<br>Código auto-generado<br>Estados: Borrador → En Revisión → Activo"]:::done
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
  CLAUSES --> KG["Knowledge Graph: nodes/edges<br>MVP: clauses + stakeholders + WBS<br>BOM → Fase 2"]:::done
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