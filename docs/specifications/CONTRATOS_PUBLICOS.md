# Contratos Publicos por Modulo

## Objetivo
Definir los puntos de integracion permitidos entre modulos. Cualquier uso cross-modulo debe consumir **solo** los contratos listados aqui.

## Regla base (obligatoria)
- Permitido: `src.<modulo>.ports`, `src.<modulo>.application.dtos`, `src.<modulo>.application.<use_cases>`.
- Prohibido: `src.<modulo>.adapters.*`, `src.<modulo>.domain.*`, `src.<modulo>.application.services.*` desde otros modulos.
- Los routers HTTP solo consumen `application` de su propio modulo.

---
## Documents
**Puertos (interfaces)**
- `src.documents.ports.IDocumentRepository`
- `src.documents.ports.IStorageService`
- `src.documents.ports.IFileParserService`
- `src.documents.ports.IEntityExtractionService`
- `src.documents.ports.IRagService`
- `src.documents.ports.IRagIngestionService`

**DTOs**
- `src.documents.application.dtos` (Document*, Clause*, Rag* schemas)

**Use cases (publicos)**
- `src.documents.application.upload_document_use_case`
- `src.documents.application.update_document_storage_path_use_case`
- `src.documents.application.update_document_status_use_case`
- `src.documents.application.parse_document_use_case`
- `src.documents.application.list_project_documents_use_case`
- `src.documents.application.get_document_with_clauses_use_case`
- `src.documents.application.get_document_use_case`
- `src.documents.application.download_document_use_case`
- `src.documents.application.delete_document_use_case`
- `src.documents.application.create_and_queue_document_use_case`
- `src.documents.application.check_clause_exists_use_case`
- `src.documents.application.get_clause_text_map_use_case`
- `src.documents.application.answer_rag_question_use_case`

---
## Stakeholders
**Puertos (interfaces)**
- `src.stakeholders.ports.IStakeholderRepository`

**DTOs**
- `src.stakeholders.application.dtos` (Stakeholder*, RACI* schemas)

**Use cases (publicos)**
- `src.stakeholders.application.create_stakeholder_use_case`
- `src.stakeholders.application.update_stakeholder_use_case`
- `src.stakeholders.application.delete_stakeholder_use_case`
- `src.stakeholders.application.list_project_stakeholders_use_case`
- `src.stakeholders.application.get_raci_matrix_use_case`
- `src.stakeholders.application.upsert_raci_assignment_use_case`
- `src.stakeholders.application.review_stakeholder_approval_use_case`

---
## Analysis
**Puertos (interfaces)**
- `src.analysis.ports.IAnalysisRepository`
- `src.analysis.ports.AlertRepository`
- `src.analysis.ports.ICoherenceRepository`
- `src.analysis.ports.IAIClient`
- `src.analysis.ports.AnalysisOrchestrator`
- `src.analysis.ports.KnowledgeGraphPort`

**DTOs**
- `src.analysis.application.dtos` (CoherenceScoreResponse, AlertBase, AlertCreate)
- `src.analysis.domain.enums` (AnalysisType, AnalysisStatus, AlertSeverity, AlertStatus)

**Use cases (publicos)**
- `src.analysis.application.analyze_document_use_case`
- `src.analysis.application.alerts_use_cases`
- `src.analysis.application.build_project_knowledge_graph_use_case`

---
## Projects
**Puertos (interfaces)**
- `src.projects.ports.ProjectRepository`
  - incluye `exists_by_id(project_id, tenant_id)`

**DTOs**
- `src.projects.application.dtos` (Project* schemas)

**Use cases (publicos)**
- `src.projects.application.use_cases.create_project_use_case`
- `src.projects.application.use_cases.update_project_use_case`
- `src.projects.application.use_cases.delete_project_use_case`
- `src.projects.application.use_cases.get_project_use_case`
- `src.projects.application.use_cases.list_projects_use_case`

---
## Procurement (WBS/BOM)
**Puertos (interfaces)**
- `src.procurement.ports.IWBSRepository`
- `src.procurement.ports.IBOMRepository`

**DTOs**
- `src.procurement.application.dtos` (WBS*, BOM* schemas)

**Use cases (publicos)**
- `src.procurement.application.use_cases.wbs_use_cases`
- `src.procurement.application.use_cases.bom_use_cases`

---
## Coherence
**Public API**
- `src.coherence` (exporta engine, models y LLM service via `__all__`)
- **Nota**: No importar `src.coherence.adapters` desde otros modulos.

---
## Core (infraestructura)
**Public API**
- `src.core` (exports centralizados: DB, auth, mcp, observability, security)
- `src.core.*` submodulos segun necesidad (auth, mcp, observability, middleware, tasks).

---
## Shared Kernel
**Public API**
- `src.shared_kernel` (cuando se creen VOs/Eventos compartidos).

---
## Cumplimiento
- Cualquier import cross-modulo fuera de esta lista se considera **violacion**.
- Validar con `rg` y actualizar este documento al introducir un nuevo contrato publico.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
