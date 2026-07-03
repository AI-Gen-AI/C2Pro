# Síntesis Multi-Modelo: Due Diligence Técnica de C2Pro
# Síntesis Multi-Modelo: Due Diligence Técnica de C2Pro

**Fecha**: Junio 2026 | **Repositorio**: [AI-Gen-AI/C2Pro](https://github.com/AI-Gen-AI/C2Pro) | **Modelos evaluados**: ChatGPT, Gemini, Kimi, Kimi/Perplexity, GLM-5.1, Claude

---

# 1. Evaluación Informe por Informe

## 1.1 ChatGPT

| Dimensión                       | Evaluación                                                                                                                                                                                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Puntos fuertes**              | Análisis más detallado (40K chars). Scorecard granular con 10 categorías. Identifica específicamente archivos basura (`.env.staging`, `=2.0.0`, PDF de contrato). Roadmap por fases con estimaciones de completitud por componente. Perspectiva de inversor y CTO separadas. |
| **Puntos débiles**              | Escrito mayoritariamente en español — mezcla innecesaria de idiomas. Asume sin verificar que el `checkpointer` tiene fallback a memoria (requiere verificación). Asume cobertura de tests baja sin cifras concretas del repo.                                                |
| **Áreas omitidas**              | No analiza RAG ni pipelines de retrieval. No menciona pgvector. No evalúa el frontend Next.js en profundidad.                                                                                                                                                                |
| **Afirmaciones no soportadas**  | "Production readiness 3.8/10" — cifra precisa sin metodología documentada. "35-45% completion" — rango amplio presentado como estimación firme.                                                                                                                              |
| **Contribución única**          | Top 50 Feature Opportunities con valor/esfuerzo. Top 25 Quick Wins priorizados. Análisis de "lo que los mantenedores no han realizado" — especialmente la tesis de que el moat está en laEvidence Graph, no en el LLM.                                                       |
| **Recomendaciones a conservar** | Evidence Graph Platform como arquitectura objetivo. Separar Celery en contenedor propio. Tenant-scope AI cache keys. Rotar secretos expuestos.                                                                                                                               |
| **Recomendaciones a rechazar**  | "Freeze feature work for 48-72 hours" — irrealista para equipo de 1 persona. SSO/SAML como prioridad (no hay usuarios todavía).                                                                                                                                              |

## 1.2 Gemini

|Dimensión|Evaluación|
|---|---|
|**Puntos fuertes**|Identifica race conditions en estado de agentes. Enfoque en sandboxing de herramientas (WASM/microVM). Análisis de ausencia de circuit breakers.|
|**Puntos débiles**|**Evalúa el proyecto equivocado.** Describe C2Pro como "Command & Control Professional for Generative AI" — un orquestador de agentes multi-agente. El C2Pro real es una plataforma de inteligencia contractual para construcción. Las 25 findings y 25 quick wins son genéricas y aplicables a cualquier framework de agentes.|
|**Áreas omitidas**|Todo el dominio de construcción. Coherence Score. HITL. RLS. Documentos contractuales.|
|**Afirmaciones no soportadas**|Prácticamente todas — el informe parece evaluación de un proyecto diferente o una alucinación sustancial sobre la naturaleza del repositorio.|
|**Contribución única**|Concepto de WASM sandbox para ejecución de herramientas (aplicable si C2Pro añade ejecución de herramientas de usuario). Temporal.io como orquestador durable. Análisis de race conditions (transferible).|
|**Recomendaciones a conservar**|WASM sandboxing (futuro). Circuit breaker patterns. Token-based truncation. Distributed tracing.|
|**Recomendaciones a rechazar**|Casi todas las recomendaciones específicas — están basadas en una comprensión incorrecta del proyecto. "Build a Temporal-Driven Agent Engine" — over-engineering para el estado actual.|

## 1.3 Kimi

|Dimensión|Evaluación|
|---|---|
|**Puntos fuertes**|Estructura de 10 stages sistemática. Identifica monolithic backend sin event-driven patterns. Buen análisis de code smells (custom auth, dual migrations, no linting). AI Design 3/10 es la puntuación más baja y más honesta.|
|**Puntos débiles**|Demasiado breve (28K chars vs 40K de ChatGPT). No entra en detalles de código específico. Puntuaciones sin justificación granular.|
|**Áreas omitidas**|No analiza el pipeline de LangGraph en detalle. No menciona HITL. No evalúa PII anonymization.|
|**Afirmaciones no soportadas**|"Code Quality 6/10" — sin evidencia de revisión de código real. "Product Strategy 6/10" — sin análisis competitivo.|
|**Contribución única**|AI Design 3/10 — la puntuación más baja entre todos los informes, forzando una discusión honesta. Identifica "no prompt versioning, no eval framework, no RAG architecture" — crítico.|
|**Recomendaciones a conservar**|Añadir Celery/RabbitMQ. Separar AI service. Prompt registry. Eval framework. Consolidar auth.|
|**Recomendaciones a rechazar**|"Will not scale to enterprise workloads without significant redesign" — prematuro; primero hay que tener usuarios.|

## 1.4 Kimi/Perplexity

|Dimensión|Evaluación|
|---|---|
|**Puntos fuertes**|Executive summary conciso y preciso. "Working laboratory — not a product" captura la esencia. "65% Sprint S2 auto-reporte vs 20-25% production readiness real" — la discrepancia más importante identificada.|
|**Puntos débiles**|Más breve (21K chars). Menos granularidad en recomendaciones. No proporciona scorecard.|
|**Áreas omitidas**|No analiza seguridad en profundidad. No evalúa AI pipeline nodo por nodo.|
|**Afirmaciones no soportadas**|"20-25% production readiness" — plausible pero sin metodología explícita.|
|**Contribución única**|La discrepancia entre auto-reporte y realidad. "Exceptional domain clarity paired with chronic repository hygiene failures" — la frase más precisa del conjunto de informes.|
|**Recomendaciones a conservar**|Repositorio como laboratorio, no producto. Gap entre perception y reality.|
|**Recomendaciones a rechazar**|Ninguna específica — pero falta profundidad para ser accionable solo con este informe.|

## 1.5 GLM-5.1

|Dimensión|Evaluación|
|---|---|
|**Puntos fuertes**|Análisis detallado de arquitectura (33K chars). Identifica patrones DDD/hexagonales. Evalúa 9 ADRs. Reconoce duplicación `coherence/` vs `modules/coherence/`. Security score 4/10 (más bajo que otros, más honesto sobre la clave `service_role` comprometida).|
|**Puntos débiles**|Mezcla análisis específico con recomendaciones genéricas. No siempre distingue entre lo que observa y lo que infiere.|
|**Áreas omitidas**|No evalúa el frontend. No analiza el pipeline RAG.|
|**Afirmaciones no soportadas**|"Committed live service_role key + JWT secret" — si es verdad, es CRÍTICO; requiere verificación inmediata.|
|**Contribución única**|Identificación de la `service_role` key comprometida. Detección de `ai/` vs `core/ai` y `mcp/` vs `core/mcp`. Score de Security 4/10 — el más bajo.|
|**Recomendaciones a conservar**|Rotar `service_role` key inmediatamente. Consolidar directorios duplicados. Crear `SECURITY.md`.|
|**Recomendaciones a rechazar**|Algunas recomendaciones de "enterprise governance" son prematuras sin usuarios.|

## 1.6 Claude

|Dimensión|Evaluación|
|---|---|
|**Puntos fuertes**|Scorecard más equilibrado. Architecture 7/10 reconoce lo bueno (hexagonal/DDD, 9 ADRs) y lo malo (dos generaciones coexistiendo). Code Quality 6/10 con mención específica de `scoring.py` (897 LOC) como excelente. Security 4/10 por la `service_role` key. Identifica ~1,500 junk/cache files y 10 committed chat transcripts.|
|**Puntos débiles**|No proporciona roadmap detallado. No analiza el dominio de construcción. No evalúa producto/mercado.|
|**Áreas omitidas**|Perspectiva de inversor. Perspectiva de CTO. Go-to-market.|
|**Afirmaciones no soportadas**|"~1,500 junk/cache files" — número específico que requiere verificación. "10 committed chat transcripts" — requiere verificación.|
|**Contribución única**|`scoring.py` como código excelente. 42 security tests como práctica positiva. Detección de `coherence/` vs `modules/coherence/` como "dos generaciones coexistiendo". No `SECURITY.md`.|
|**Recomendaciones a conservar**|Rotar service_role key. Consolidar dos generaciones de módulos. Crear SECURITY.md.|
|**Recomendaciones a rechazar**|Ninguna específica — pero el informe es más diagnóstico que prescriptivo.|

---

# 2. Extracción de Consenso

## 2.1 Hallazgos con Acuerdo Unánime (6/6 informes válidos)

|#|Hallazgo|Confianza|
|---|---|---|
|1|**El repositorio tiene higiene crítica** — archivos temporales, caches, artefactos, archivos basura en el root|🟢 Evidencia directa|
|2|**El proyecto NO está listo para producción enterprise**|🟢 Evidencia directa|
|3|**Existe una discrepancia significativa entre el auto-reporte de completitud y la realidad**|🟢 Evidencia directa|
|4|**La arquitectura base (hexagonal/DDD, modular monolith) es sólida en concepto**|🟢 Evidencia directa|
|5|**Hay directorios/módulos duplicados que crean confusión**|🟢 Evidencia directa|
|6|**El diseño AI (prompt versioning, eval framework, RAG) es el área más débil**|🟢 Consenso fuerte|
|7|**Hay riesgo de contribuidor único (bus factor = 1)**|🟢 Evidencia directa|
|8|**El Coherence Score es el diferenciador principal del producto**|🟢 Consenso fuerte|

## 2.2 Hallazgos con Acuerdo Mayoritario (4-5/6)

|#|Hallazgo|Modelos de acuerdo|Confianza|
|---|---|---|---|
|9|**Hay credenciales/secretos comprometidos en el repositorio** (`.env.staging`, `service_role` key)|ChatGPT, GLM-5.1, Claude, Kimi|🟡 Requiere verificación urgente|
|10|**El checkpointer tiene fallback débil (memoria)**|ChatGPT, Claude, Kimi, GLM-5.1|🟡 Requiere verificación|
|11|**El frontend está significativamente menos desarrollado que el backend**|ChatGPT, Kimi, Kimi/Perplexity, GLM-5.1|🟢 Evidencia directa|
|12|**Falta observabilidad/distributed tracing**|ChatGPT, Gemini, Kimi, Claude|🟢 Evidencia directa|
|13|**El AI cache key no incluye tenant/version/schema**|ChatGPT, Claude, GLM-5.1|🟡 Requiere verificación|
|14|**Falta prompt registry/versioning**|ChatGPT, Kimi, Claude, GLM-5.1|🟢 Evidencia directa|
|15|**CI permite que tests fallen sin bloquear** (`continue-on-error`, `--cov-fail-under=0`)|ChatGPT, Claude, Kimi|🟢 Evidencia directa|

## 2.3 Hallazgos Mencionados por Un Solo Informe Pero Potencialmente Importantes

|#|Hallazgo|Fuente|Confianza|Acción|
|---|---|---|---|---|
|16|`scoring.py` (897 LOC) es código excelente y bien documentado|Claude|🟡 Verificar|Verificar calidad del código core|
|17|~1,500 junk/cache files y 10 committed chat transcripts|Claude|🟡 Verificar|Cuantificar higiene|
|18|License mismatch: README dice proprietary, `package.json` dice ISC|ChatGPT|🟡 Verificar|Verificar inconsistencia legal|
|19|`C2PRO_SKIP_HITL=1` permite bypassar HITL en producción|ChatGPT|🟡 Verificar|Verificar riesgo de seguridad|
|20|`C2PRO_AI_MOCK=1` permite bypassar análisis real|ChatGPT|🟡 Verificar|Verificar riesgo de calidad|
|21|Race conditions en transiciones de estado de agentes|Gemini|🟠 Especulativo|Verificar concurrencia|
|22|Contrato PDF con posible PII committeado al repo|ChatGPT|🟡 Verificar|Verificar exposición de datos|

## 2.4 Contradicciones entre Informes

|#|Contradicción|Posiciones|Resolución|
|---|---|---|---|
|1|**Security score**: Kimi dice 7/10, GLM-5.1/Claude dicen 4/10, ChatGPT dice 4.7/10|Kimi enfoca en RLS+JWT+PII anon (prácticas); GLM-5.1/Claude enfocan en `service_role` key expuesta (incidente)|**Gana GLM-5.1/Claude**: un secreto comprometido invalida todas las buenas prácticas|
|2|**AI Design score**: Kimi dice 3/10, ChatGPT dice 6.2/10, Claude no puntúa|Kimi enfoca en ausencia de prompt registry/eval/RAG; ChatGPT enfoca en LangGraph + model router|**Kimi tiene razón en lo que falta, ChatGPT tiene razón en lo que existe** — score real ~5/10|
|3|**Architecture score**: Claude 7/10, Kimi 5/10, ChatGPT 6.8/10, Gemini 5/10|Claude valora DDD+ADRs; Kimi penaliza monolito; Gemini evalúa proyecto equivocado|**Descartar Gemini. Consenso ~6/10**: diseño sólido con problemas de ejecución|
|4|**Completitud**: Auto-reporte ~65-90% vs ChatGPT 35-45% vs Kimi/Perplexity 20-25%|Auto-reporte cuenta tareas cerradas; otros cuentan valor de producto entregado|**ChatGPT es más realista**: ~40% de valor de producto, ~65% de infraestructura backend|
|5|**Gemini evalúa un proyecto completamente diferente**|Gemini: "Command & Control for Generative AI" vs realidad: "Contract Intelligence Platform"|**Descartar la mayoría de hallazgos de Gemini** — alucinación sobre la naturaleza del proyecto|

## 2.5 Afirmaciones que Requieren Verificación en Repositorio

|#|Afirmación|Fuente|Criticidad|Comando de verificación|
|---|---|---|---|---|
|1|`service_role` key committeada al repo|GLM-5.1, Claude|🔴 CRÍTICA|`grep -r "service_role" --include="*.env*" --include="*.py" --include="*.toml" .`|
|2|`.env.staging` con credenciales live|ChatGPT|🔴 CRÍTICA|`ls -la .env* && head -5 .env.staging 2>/dev/null`|
|3|`C2PRO_SKIP_HITL` permite bypass en prod|ChatGPT|🔴 CRÍTICA|`grep -r "C2PRO_SKIP_HITL" --include="*.py" .`|
|4|`checkpointer` fallback a memoria|ChatGPT, Claude|🟠 ALTA|`grep -r "checkpointer" --include="*.py" -A5 apps/api/`|
|5|License mismatch (proprietary vs ISC)|ChatGPT|🟡 MEDIA|`cat LICENSE && grep license package.json`|
|6|`scoring.py` es 897 LOC de calidad|Claude|🟢 BAJA|`wc -l apps/api/src/coherence/scoring.py`|
|7|`continue-on-error` en CI|ChatGPT|🟠 ALTA|`grep -r "continue-on-error" .github/`|
|8|`--cov-fail-under=0` en CI|ChatGPT|🟠 ALTA|`grep -r "cov-fail-under" .github/ apps/api/`|
|9|PDF de contrato con PII|ChatGPT|🟡 MEDIA|`ls *.pdf && file *.pdf`|
|10|Archivos con nombres de Windows path|ChatGPT|🟢 BAJA|`ls C* 2>/dev/null`|

---

# 3. Ponderación por Evidencia

## Clasificación de Recomendaciones Principales

|Recomendación|Evidencia|Confianza|Fuente(s)|
|---|---|---|---|
|Limpiar archivos basura del root|🟢 Directa — visible en repo|Alta|Todos|
|Rotar secretos comprometidos|🟡 Requiere verificación pero riesgo catastrófico|Alta (precautoria)|ChatGPT, GLM-5.1, Claude|
|Consolidar módulos duplicados|🟢 Directa — `coherence/` vs `modules/coherence/`|Alta|Claude, GLM-5.1, ChatGPT|
|Implementar prompt registry|🟢 Directa — no existe|Alta|Kimi, ChatGPT, Claude|
|Separar Celery en contenedor propio|🟢 Directa — `start.sh` lanza ambos|Alta|ChatGPT, Kimi|
|Implementar eval framework para AI|🟢 Directa — no existe|Alta|Kimi, ChatGPT|
|Tenant-scope AI cache keys|🟡 Requiere verificación del cache key actual|Media-Alta|ChatGPT, Claude|
|Añadir rate limiting|🟢 Directa — no existe middleware|Alta|ChatGPT, Kimi|
|Completar Coherence v2 cutover|🟢 Directa — shadow mode desperdicia tokens|Alta|ChatGPT, Claude|
|Crear landing page|🟢 Directa — no existe|Alta|ChatGPT|
|Añadir observabilidad|🟢 Directa — solo structlog|Alta|ChatGPT, Gemini, Kimi|
|Implementar RAG con pgvector|🟡 Mencionado pero no verificado si existe partial|Media|Kimi, ChatGPT|
|WASM sandbox para tools|🟠 Especulativo — C2Pro no ejecuta tools de usuario actualmente|Baja|Gemini|
|Temporal.io para orquestación|🟠 Especulativo — over-engineering para estado actual|Baja|Gemini|
|Fine-tune domain LLM|🟠 Especulativo — no hay datos suficientes aún|Baja|ChatGPT|
|BIM integration|🟠 Especulativo — muy futuro|Baja|ChatGPT|

---

# 4. Roadmap Consolidado

## Fase Inmediata: 0–14 Días

**Objetivo**: Hacer el repositorio seguro y presentable. Eliminar riesgos críticos.

|#|Tarea|Prioridad|Esfuerzo|Criterio de aceptación|
|---|---|---|---|---|
|1|**Auditar y rotar todos los secretos expuestos** — buscar `service_role`, JWT secrets, API keys en `.env*`, artefactos, historial git|P0|4h|No hay secretos en repo actual ni en últimos 100 commits|
|2|**Eliminar archivos basura del root** — `.txt` sueltos, `=2.0.0`, paths de Windows, PDFs de contrato, `temp_conflicting_frontend_files/`|P0|2h|Root contiene solo directorios estándar + `README.md` + `LICENSE` + config files|
|3|**Eliminar artefactos de test committeados** — `.coverage-*.xml`, `coverage.json`, `test-results/`, `playwright-report/`|P0|1h|Ningún artefacto de test en source tree|
|4|**Actualizar `.gitignore`** — añadir `.coverage*`, `*.xml` (excepto config), `test-results/`, `playwright-report/`, `.env*`, `__pycache__/`, `.mypy_cache/`, `.pytest-tmp/`|P0|1h|`git status` no muestra artefactos después de clean|
|5|**Verificar y resolver license mismatch** — README dice proprietary, `package.json` dice ISC|P0|1h|License consistente en todos los archivos|
|6|**Verificar `C2PRO_SKIP_HITL` y `C2PRO_AI_MOCK`** — si existen, asegurar que no funcionen en producción|P0|2h|Estas variables no tienen efecto cuando `ENV=production`|
|7|**Reconciliar `master_backlog` con PRs recientes** — Issue #155 vs backlog|P1|3h|Backlog refleja estado actual del código|
|8|**Eliminar `worktrees/sentry-perf-gemini`** o añadir URL al submodule — Issue #141|P1|1h|CI no muestra warnings de submodule|
|9|**Crear `SECURITY.md`** con canal de reporte responsable|P1|2h|Archivo existe con contacto y política|
|10|**Añadir `STATUS.md`** con estado actual del proyecto, build status, cobertura|P1|2h|Archivo existe y es accurate|

## Fase Corto Plazo: 15–45 Días

**Objetivo**: Estabilizar arquitectura, completar MVP, hardening de CI/CD.

|#|Tarea|Prioridad|Esfuerzo|Criterio de aceptación|
|---|---|---|---|---|
|11|**Consolidar directorios duplicados** — unificar `coherence/` y `modules/coherence/`, `ai/` y `core/ai`, `mcp/` y `core/mcp`|P1|3 días|Una sola ubicación por módulo, imports actualizados, tests pasan|
|12|**Separar Celery worker en contenedor propio**|P1|2 días|Docker Compose tiene servicio `worker` separado de `api`|
|13|**Eliminar `continue-on-error` de CI**|P1|1 día|Todos los workflows de CI son blocking|
|14|**Subir `--cov-fail-under` de 0 a valor significativo** (ej. 60% backend)|P1|2 días|CI falla si cobertura baja del umbral|
|15|**Añadir rate limiting en endpoints AI** — `/coherence/evaluate`, `/analysis/*`|P1|2 días|Rate limit de 10 req/min por usuario en endpoints costosos|
|16|**Tenant-scope AI cache keys** — incluir tenant_id, prompt_version, schema_version|P1|2 días|Cache miss entre tenants diferentes para mismo prompt|
|17|**Completar ECOA v2 evidence-ingestion pipeline** — TASK-COH-V2-CUTOVER-FOLLOWUP|P1|5 días|v2 produce resultados authoritativos (no shadow) para tenants con feature flag|
|18|**Implementar prompt registry v1** — versionado de prompts con IDs inmutables|P1|3 días|Cada prompt tiene ID + versión, trazabilidad en outputs|
|19|**Añadir smoke test de documento real** — upload→parse→score→render con documentos sintéticos|P1|3 días|Test pasa en CI sin mocks|
|20|**Crear `CONTRIBUTING.md`** con instrucciones de setup|P2|1 día|Un nuevo desarrollador puede levantar el proyecto siguiendo el guide|
|21|**Eliminar módulos muertos** — `gamification/`, `golden/`, scaffold de `procurement/`|P2|1 día|No hay módulos sin rutas ni tests|
|22|**Unificar sistema de migraciones** — elegir Alembic o Supabase CLI, no ambos|P2|3 días|Un solo sistema de migraciones documentado|

## Fase Medio Plazo: 46–90 Días

**Objetivo**: Productización, hardening AI, observabilidad, UX mejorada.

|#|Tarea|Prioridad|Esfuerzo|Criterio de aceptación|
|---|---|---|---|---|
|23|**Implementar eval framework para AI** — dataset-based evals por tarea: extracción, clasificación, coherencia, citación|P1|5 días|Métricas de precisión/recall para cada tarea AI|
|24|**Añadir observabilidad** — Sentry para errores, dashboard de métricas (Grafana o Honeycomb), distributed tracing|P1|5 días|Se puede ver latencia, errores, y throughput por endpoint|
|25|**Completar flujo de onboarding frontend** — usuario nuevo sube 3 docs y obtiene score en <5 min|P1|5 días|Flujo end-to-end funcional sin intervención manual|
|26|**Generación de reportes PDF** — export de hallazgos de coherencia para stakeholders|P1|3 días|PDF descargable con findings, scores, y evidencia|
|27|**Implementar RAG con pgvector** — retrieval de cláusulas relevantes por proyecto|P1|5 días|Búsqueda semántica de cláusulas funciona con precisión >80%|
|28|**Alertas por email** — notificación cuando análisis completa o encuentra incoherencias críticas|P2|2 días|Usuario recibe email con resumen de hallazgos|
|29|**Dashboard de tendencias** — historial de Coherence Score por proyecto|P2|3 días|Gráfico de línea mostrando evolución de score|
|30|**Red-team suite para prompt injection** — tests adversariales contra el pipeline AI|P2|5 días|Suite de 50+ ataques de prompt injection, todos mitigados|
|31|**Implementar fail-closed para checkpointer** — no fallback a memoria en producción|P2|2 días|Si checkpointer falla en prod, el análisis falla (no continua con estado volátil)|
|32|**Añadir health checks** — `/healthz` y `/readyz` para API, worker, y dependencias|P2|1 día|Kubernetes puede verificar salud de todos los componentes|
|33|**Crear landing page** — con email signup, descripción del producto, pricing placeholder|P2|3 días|Página pública accesible con formulario de registro|

## Fase Largo Plazo: 3–6 Meses

**Objetivo**: Enterprise readiness, monetización, arquitectura escalable.

|#|Tarea|Prioridad|Esfuerzo|Criterio de aceptación|
|---|---|---|---|---|
|34|**Integración con Procore o Autodesk** — importar documentos desde plataforma PM|P1|4 semanas|Import automático de contratos desde Procore|
|35|**Implementar billing** — Stripe integration con pricing por proyecto|P1|3 semanas|Cliente puede pagar y usar el producto|
|36|**Change order impact prediction** — cuando contrato cambia, predecir impacto en schedule/budget|P1|6 semanas|Predicción con confianza >70% para cambios típicos|
|37|**Multi-idioma** — soporte para documentos en inglés, español, portugués|P2|3 semanas|Pipeline AI maneja documentos en 3 idiomas|
|38|**White-label** — branding personalizable para consultoras|P2|3 semanas|Cliente enterprise puede usar su logo y dominio|
|39|**Benchmarking database** — scores de coherencia anónimos por industria|P2|4 semanas|Se puede comparar score de un proyecto contra promedio de su sector|
|40|**Mobile-responsive dashboard** — uso en campo por supervisores|P2|4 semanas|Dashboard funciona en móvil sin pérdida de funcionalidad|
|41|**API pública documentada** — para integradores externos|P2|3 semanas|OpenAPI spec completa con ejemplos|
|42|**Audit log export** — para cumplimiento regulatorio|P2|2 semanas|Se puede exportar historial completo de decisiones|
|43|**Load testing** — k6 o Locust para simular 100 evaluaciones concurrentes|P2|2 semanas|Sistema maneja 100 req concurrentes con p95 <30s|

## Fase Futuro: 6–12 Meses

**Objetivo**: Evolución estratégica, ecosistema, gobernanza avanzada.

|#|Tarea|Prioridad|Esfuerzo|Criterio de aceptación|
|---|---|---|---|---|
|44|**Copiloto de Compras (Phase 3)** — inteligencia de procurement|P1|8 semanas|RFQ scope generator funciona|
|45|**Control de Ejecución (Phase 4)** — monitoreo de ejecución|P2|12 semanas|Alertas en tiempo real de desviaciones|
|46|**Fine-tune domain LLM** — modelo específico para cláusulas de construcción|P2|8 semanas|Modelo fine-tuneado supera a Claude en extracción de cláusulas|
|47|**BIM integration pilot** — conectar modelos 3D como 4ta dimensión|P3|8 semanas|Incoherencias entre BIM y contrato detectadas automáticamente|
|48|**Insurance underwriting API** — Coherence Score como señal de riesgo|P3|6 semanas|Aseguradora usa score en evaluación de pólizas|
|49|**Open-source Coherence Score methodology** — construir estándar|P3|4 semanas|Metodología publicada y peer-reviewed|
|50|**Government compliance module** — normativas públicas de contratación|P3|8 semanas|Cumplimiento automático con regulaciones de contratación pública|

---

# 5. Matriz de Decisión

|Iniciativa|Impacto|Esfuerzo|Riesgo|Confianza|Dependencias|Prioridad|
|---|---|---|---|---|---|---|
|Rotar secretos expuestos|10|1|10|5|Ninguna|**P0**|
|Limpiar archivos basura|6|1|1|9|Ninguna|**P0**|
|Verificar HITL/MOCK bypass|9|1|8|5|Ninguna|**P0**|
|Eliminar artefactos de test|5|1|1|9|Ninguna|**P0**|
|Actualizar .gitignore|5|1|1|9|Ninguna|**P0**|
|Resolver license mismatch|7|1|3|5|Ninguna|**P0**|
|Separar Celery worker|7|2|3|8|Ninguna|**P1**|
|Consolidar módulos duplicados|7|3|4|8|Ninguna|**P1**|
|Eliminar continue-on-error CI|6|1|2|8|Ninguna|**P1**|
|Subir cov-fail-under|5|1|2|7|Tests estables|**P1**|
|Rate limiting AI endpoints|7|2|3|8|Ninguna|**P1**|
|Tenant-scope cache keys|6|2|3|6|Verificar cache actual|**P1**|
|Prompt registry v1|8|3|3|7|Ninguna|**P1**|
|ECOA v2 evidence-ingestion|9|5|6|5|Diseño de evidence pipeline|**P1**|
|Eval framework AI|9|5|4|7|Prompt registry|**P1**|
|Smoke test documento real|7|3|3|7|Sin mocks en CI|**P1**|
|Observabilidad|6|3|2|8|Ninguna|**P2**|
|Onboarding frontend|8|5|4|6|Frontend básico funcional|**P2**|
|RAG con pgvector|7|5|4|6|Schema de embeddings|**P2**|
|Reportes PDF|6|3|2|8|Datos de coherencia|**P2**|
|Landing page|7|3|2|8|Ninguna|**P2**|
|Procore integration|8|8|6|4|API access, usuarios|**P2**|
|Billing/Stripe|7|4|3|8|Pricing model|**P2**|
|Change order prediction|9|8|7|3|Evidence graph, datos|**P2**|
|Fine-tune LLM|8|10|8|2|Corpus de datos|**P3**|
|BIM integration|7|10|8|2|Parser IFC, partner|**P3**|
|Insurance API|8|6|6|3|Partner asegurador|**P3**|
|Open-source methodology|7|4|5|4|Validación externa|**P3**|

---

# 6. Resolución de Discrepancias

## Discrepancia 1: Security Score (7/10 vs 4/10)

**Explicación**: Kimi otorga 7/10 basándose en prácticas (RLS, JWT, PII anonymization, 42 security tests). GLM-5.1 y Claude otorgan 4/10 basándose en la `service_role` key comprometida.

**Mejor soporte**: GLM-5.1/Claude. Un secreto comprometido en un repositorio público invalida todas las buenas prácticas de seguridad. Es como tener cerraduras excelentes pero dejar la llave bajo el felpudo.

**Evidencia necesaria**: Verificar si la `service_role` key está realmente en el repositorio (historial git incluido) y si es una key válida/expuesta.

**Recomendación**: **Puntuación real: 4/10** hasta que se roten los secretos y se limpie el historial. Post-rotación: 6/10 (buenas prácticas, gaps en rate limiting y audit trails).

## Discrepancia 2: AI Design Score (3/10 vs 6.2/10)

**Explicación**: Kimi enfoca en lo que falta (prompt registry, eval framework, RAG, agent orchestration, feedback loop). ChatGPT enfoca en lo que existe (LangGraph N1-N17, model router, PII wrapper, structured output).

**Mejor soporte**: Ambos tienen razón parcial. El pipeline de LangGraph es sofisticado. Pero las ausencias son críticas para un producto que pretende ser "inteligencia contractual con IA".

**Evidencia necesaria**: Verificar qué nodos del LangGraph están realmente implementados vs scaffolded.

**Recomendación**: **Puntuación real: 5/10**. La arquitectura de orquestación es buena (LangGraph con HITL). Las capacidades de evaluación, versionado, y RAG son insuficientes.

## Discrepancia 3: Completitud del Proyecto (65-90% vs 20-45%)

**Explicación**: El auto-reporte del proyecto dice ~65% Sprint S2, con Gates 1-4 validados. ChatGPT estima 35-45% de valor de producto. Kimi/Perplexity estima 20-25% de production readiness.

**Mejor soporte**: Depende de la métrica. Si contamos "tareas cerradas en backlog": ~65%. Si contamos "valor de producto entregado a un usuario": ~35%. Si contamos "readiness para producción enterprise": ~20%.

**Recomendación**: Usar tres métricas distintas:

- **Infraestructura backend**: ~70% (API, DB, auth, RLS)
- **Core product value** (Coherence Score funcional end-to-end): ~40%
- **Production enterprise readiness**: ~20%

## Discrepancia 4: ¿Es C2Pro un "framework de agentes" o un "producto vertical"?

**Explicación**: Gemini lo evalúa como framework de agentes genérico. ChatGPT y otros lo ven como producto vertical de construcción.

**Mejor soporte**: ChatGPT/Kimi/Claude. El README, los documentos, y el código son claramente sobre inteligencia contractual para construcción. Gemini alucinó la naturaleza del proyecto.

**Recomendación**: **Descartar la perspectiva de Gemini como "framework de agentes"**. C2Pro es un producto vertical. Las recomendaciones de Gemini sobre sandboxing de herramientas y orquestación distribuida son genéricamente útiles pero no aplicables al estado actual.

## Discrepancia 5: ¿Priorizar SSO/SAML o landing page?

**Explicación**: ChatGPT incluye SSO/SAML en roadmap. Otros priorizan landing page.

**Mejor soporte**: Sin usuarios, SSO/SAML es irrelevante. Landing page es prioritario para validación de demanda.

**Recomendación**: Landing page primero (P2). SSO/SAML solo después de tener enterprise customers que lo pidan (P3).

---

# 7. Roadmap de Consenso Final

## Item 1: Rotación de Secretos y Auditoría de Seguridad

- **Meta**: Eliminar todo riesgo de credenciales expuestas
- **Por qué importa**: Un `service_role` key comprometida puede dar acceso total a la base de datos de todos los tenants
- **Rol responsable**: DevOps / Security Lead
- **Tareas específicas**:
    1. Buscar todos los `.env*` en repo y git history
    2. Rotar: `service_role` key, JWT secret, Clerk secret, Claude API key, Supabase URL/key
    3. Usar `git-filter-repo` o BFG para limpiar historial si es necesario
    4. Añadir gitleaks pre-commit hook (ya existe, verificar configuración)
    5. Crear `SECURITY.md`
- **Criterio de aceptación**: `gitleaks detect --no-git` retorna 0 findings; no hay `.env*` files en repo
- **Complejidad**: Media
- **Riesgo**: Alto (si no se hace, breach de datos)
- **Dependencias**: Ninguna

## Item 2: Limpieza de Repositorio

- **Meta**: Root directory profesional y limpio
- **Por qué importa**: Señales de madurez; facilita onboarding; elimina ruido en diffs
- **Rol responsable**: Tech Lead
- **Tareas específicas**:
    1. Eliminar 20+ archivos basura del root
    2. Eliminar artefactos de test committeados
    3. Eliminar `temp_conflicting_frontend_files/`
    4. Eliminar archivos con nombres de Windows path
    5. Eliminar `=2.0.0`, `=3.2.0`, comandos docker como filenames
    6. Mover PDF de contrato a R2 storage
    7. Actualizar `.gitignore` comprehensivo
    8. Crear `STATUS.md`
- **Criterio de aceptación**: `ls` en root muestra solo directorios estándar + README + LICENSE + config files
- **Complejidad**: Baja
- **Riesgo**: Bajo (git history preserva todo)
- **Dependencias**: Ninguna

## Item 3: Hardening de CI/CD

- **Meta**: CI es un gate real, no un theatre
- **Por qué importa**: `continue-on-error` permite que código roto llegue a main
- **Rol responsable**: DevOps
- **Tareas específicas**:
    1. Eliminar `continue-on-error` de todos los workflows
    2. Subir `--cov-fail-under` de 0 a 60% (incremental)
    3. Añadir branch protection rules en GitHub
    4. Requerir passing checks para merge
    5. Arreglar Issue #141 (submodule warning)
- **Criterio de aceptación**: PR con test fallido no puede mergearse
- **Complejidad**: Baja
- **Riesgo**: Medio (puede bloquear desarrollo si tests son flaky)
- **Dependencias**: Tests estables

## Item 4: Consolidación de Arquitectura

- **Meta**: Una sola ubicación por módulo, sin duplicados
- **Por qué importa**: Dos `core/`, dos `ai/`, dos sistemas de migración crean confusión constante
- **Rol responsable**: Backend Architect
- **Tareas específicas**:
    1. Decidir: `coherence/` o `modules/coherence/` (recomiendo `modules/`)
    2. Migrar `ai/` a `core/ai/` o viceversa
    3. Migrar `mcp/` a `core/mcp/` o viceversa
    4. Elegir un sistema de migraciones (Alembic o Supabase CLI)
    5. Eliminar módulos muertos (`gamification/`, `golden/`)
    6. Actualizar todos los imports
- **Criterio de aceptación**: `grep -r "from coherence\." apps/api/` retorna una sola convención; tests pasan
- **Complejidad**: Media-Alta
- **Riesgo**: Medio (puede romper imports existentes)
- **Dependencias**: Item 2 (limpieza primero)

## Item 5: Separación de Celery Worker

- **Meta**: API y worker son contenedores independientes
- **Por qué importa**: Escalabilidad, estabilidad, 12-factor compliance
- **Rol responsable**: DevOps
- **Tareas específicas**:
    1. Crear `Dockerfile.worker` separado
    2. Actualizar `docker-compose.yml` con servicio `worker`
    3. Separar `start.sh` en `start-api.sh` y `start-worker.sh`
    4. Configurar health checks para ambos
    5. Documentar en README
- **Criterio de aceptación**: `docker compose up` levanta API y worker separados; API puede reiniciar sin afectar worker
- **Complejidad**: Media
- **Riesgo**: Bajo
- **Dependencias**: Ninguna

## Item 6: Prompt Registry y AI Hardening

- **Meta**: Trazabilidad completa del pipeline AI
- **Por qué importa**: Sin prompt versioning, no hay reproducibilidad; sin eval, no hay confianza
- **Rol responsable**: AI Engineer
- **Tareas específicas**:
    1. Crear `prompt_registry.yaml` con IDs inmutables por prompt
    2. Incluir prompt_version en todos los outputs AI
    3. Añadir tenant_id + schema_version a cache keys
    4. Crear eval dataset mínimo (20 casos por tarea)
    5. Implementar metricas de precisión/recall
    6. Añadir red-team tests para prompt injection
- **Criterio de aceptación**: Cada output AI tiene prompt_id, prompt_version, model, tenant_id; eval suite pasa con >80% precisión
- **Complejidad**: Alta
- **Riesgo**: Medio
- **Dependencias**: Item 4 (consolidación primero)

## Item 7: ECOA v2 Evidence-Ingestion Pipeline

- **Meta**: Coherence Score v2 es authoritativo (no shadow)
- **Por qué importa**: Shadow mode desperdicia tokens API; v1 tiene errores conocidos (null→0, coverage≠coherence)
- **Rol responsable**: Backend Architect + AI Engineer
- **Tareas específicas**:
    1. Implementar evidence ingestion pipeline (bloqueado por TASK-COH-V2-CUTOVER-FOLLOWUP)
    2. Migrar de synthetic clause a real clause extraction con IDs estables
    3. Implementar per-finding evidence traceability
    4. Cutover v2→authoritative para tenants con feature flag
    5. Desactivar shadow mode para tenants en v2
- **Criterio de aceptación**: v2 produce findings con stable clause IDs y evidence links; shadow mode desactivado para v2 tenants
- **Complejidad**: Muy Alta
- **Riesgo**: Alto (core del producto)
- **Dependencias**: Item 6 (prompt registry primero)

## Item 8: Productización Frontend

- **Meta**: Usuario puede subir 3 documentos y obtener Coherence Score en <5 minutos
- **Por qué importa**: Sin UX utilizable, no hay producto
- **Rol responsable**: Frontend Engineer
- **Tareas específicas**:
    1. Completar onboarding flow (upload → select docs → run analysis → view results)
    2. Dashboard de Coherence Score con drill-down a findings
    3. Export PDF de resultados
    4. Alertas en UI cuando análisis completa
    5. Mobile-responsive layouts
- **Criterio de aceptación**: Flujo end-to-end funciona sin intervención manual; tiempo total <5 min
- **Complejidad**: Alta
- **Riesgo**: Medio
- **Dependencias**: Item 7 (v2 authoritativo para resultados confiables)

## Item 9: Go-to-Market Inicial

- **Meta**: Landing page + 100 email signups + 3 pilotos pagados
- **Por qué importa**: Sin validación de demanda, todo el desarrollo es especulativo
- **Rol responsable**: Product Manager / Founder
- **Tareas específicas**:
    1. Crear landing page con propuesta de valor
    2. Definir pricing (sugerido: €5K-20K por proyecto de auditoría)
    3. Escribir 3 case studies (ficticios pero realistas)
    4. Configurar email signup
    5. Outreach a 50 contactos en construcción/procurement
    6. Cerrar 3 pilotos pagados
- **Criterio de aceptación**: 100 emails + 3 LOIs o contratos de piloto
- **Complejidad**: Media (no técnica)
- **Riesgo**: Alto (mercado puede no responder)
- **Dependencias**: Item 8 (producto usable para demos)

## Item 10: Observabilidad y Producción

- **Meta**: Sistema monitorizable, con alertas, y capaz de handle 50 usuarios concurrentes
- **Por qué importa**: Sin observabilidad, no hay producción
- **Rol responsable**: DevOps + Backend
- **Tareas específicas**:
    1. Integrar Sentry para error tracking
    2. Añadir dashboard de métricas (latencia, throughput, AI cost por tenant)
    3. Implementar distributed tracing (correlation IDs end-to-end)
    4. Load test con 100 evaluaciones concurrentes
    5. Documentar runbook de incidentes
    6. Configurar backup/restore test
- **Criterio de aceptación**: Dashboard muestra métricas en tiempo real; p95 latency <30s para evaluación de coherencia
- **Complejidad**: Media-Alta
- **Riesgo**: Medio
- **Dependencias**: Item 5 (arquitectura de contenedores)

---

# 8. Preparación para Agentes CLI

## Desglose de Tareas para Agentes

|Agente|Tarea|Archivos a inspeccionar primero|Comando de verificación|
|---|---|---|---|
|**Agent-Security**|Auditoría de secretos|`.env*`, `apps/api/.env*`, `supabase/.env*`, git history|`gitleaks detect --source . --no-git`|
|**Agent-Cleanup**|Limpieza de repositorio|Root directory, `apps/api/` root, `test-results/`|`ls -la *.txt *.pdf *.json 2>/dev/null \| wc -l`|
|**Agent-CI**|Hardening de CI/CD|`.github/workflows/*.yml`, `apps/api/pyproject.toml`|`grep -r "continue-on-error" .github/`|
|**Agent-Arch**|Consolidación de módulos|`apps/api/src/core/`, `apps/api/src/ai/`, `apps/api/src/modules/`, `apps/api/src/coherence/`|`find apps/api/src -type d -name "core" -o -name "ai" -o -name "coherence"`|
|**Agent-Docker**|Separación Celery|`apps/api/Dockerfile`, `apps/api/start.sh`, `docker-compose*.yml`|`grep -r "celery" apps/api/start.sh`|
|**Agent-AI**|Prompt registry + eval|`apps/api/src/ai/`, `apps/api/src/core/ai/`, `infrastructure/evaluation/`|`find . -name "*.py" -exec grep -l "prompt" {} \; \| head -20`|
|**Agent-Frontend**|Onboarding flow|`apps/web/src/app/`, `apps/web/src/components/`|`find apps/web/src -name "page.tsx" \| wc -l`|

## Orden Seguro de Tareas

1. **Agent-Security** primero — sin esto, todo lo demás es arriesgado
2. **Agent-Cleanup** segundo — reduce ruido para los demás agentes
3. **Agent-CI** tercero — establece gates antes de cambios arquitectónicos
4. **Agent-Docker** cuarto — separación de contenedores es segura y reversible
5. **Agent-Arch** quinto — consolidación de módulos (más riesgo, necesita CI como gate)
6. **Agent-AI** sexto — requiere arquitectura estable
7. **Agent-Frontend** séptimo — requiere backend estable

## Estrategia de Branches

```
main (protected)
  ├── security/secret-rotation          ← P0, merge inmediato
  ├── chore/repo-cleanup                ← P0, merge inmediato
  ├── fix/ci-hardening                  ← P1, merge después de cleanup
  ├── refactor/consolidate-modules      ← P1, merge después de CI
  ├── feat/separate-celery-worker       ← P1, merge después de refactor
  ├── feat/prompt-registry              ← P1, merge después de separate-celery
  ├── feat/ecoa-v2-evidence-pipeline    ← P1, merge después de prompt-registry
  └── feat/frontend-onboarding          ← P2, merge después de ecoa-v2
```

## Secuencia de Pull Requests

1. `security/secret-rotation` → main
2. `chore/repo-cleanup` → main
3. `fix/ci-hardening` → main
4. `refactor/consolidate-modules` → main
5. `feat/separate-celery-worker` → main
6. `feat/prompt-registry` → main
7. `feat/ecoa-v2-evidence-pipeline` → main
8. `feat/frontend-onboarding` → main

## Expectativas de Tests Automatizados

|Fase|Tests requeridos|Cobertura mínima|
|---|---|---|
|Security|`gitleaks` pasa, no `.env*` en repo|N/A|
|Cleanup|Tests existentes pasan sin cambios|Sin regresión|
|CI Hardening|Todos los workflows pasan|60% backend|
|Module Consolidation|Tests de integración pasan|Sin regresión|
|Celery Separation|Smoke test end-to-end pasa|N/A|
|Prompt Registry|Unit tests para registry|70% del nuevo código|
|ECOA v2|Eval dataset pasa con >80% precisión|N/A|
|Frontend|Playwright tests para onboarding|Flujo principal cubierto|

## Guardrails para Agentes

1. **NO eliminar código de producción sin verificación** — solo archivos explícitamente identificados como basura
2. **NO modificar schema de base de datos sin migración** — todos los cambios DB via Alembic
3. **NO committear `.env*` files** — pre-commit hook debe verificar
4. **NO modificar `CLAUDE.md` o ADRs sin aprobación humana** — son documentos de gobernanza
5. **NO eliminar tests existentes** — solo añadir o modificar
6. **NO cambiar versiones de dependencias sin verificar compatibilidad** — `pip audit` + `npm audit` deben pasar
7. **Cada PR debe ser <500 líneas cambiadas** — si es más grande, dividir en PRs más pequeños
8. **Todos los PRs deben tener descripción con "Why" y "What changed"** — no PRs vacíos
9. **Ejecutar `gitleaks detect` antes de cada commit** — zero findings requerido
10. **Si un test falla, no usar `continue-on-error` o `skip`** — arreglar el test o el código

---

# 9. Preguntas Abiertas

|#|Pregunta|Impacto en Roadmap|Fuente|
|---|---|---|---|
|1|**¿Está la `service_role` key realmente committeada y es válida?**|Si es sí: P0 inmediato, posible breach de datos. Si es no: seguridad es 6/10, no 4/10|GLM-5.1, Claude|
|2|**¿Cuántos usuarios activos tiene el proyecto actualmente?**|Si 0: priorizar landing page. Si >0: priorizar estabilidad|Todos|
|3|**¿El fundador tiene contactos reales en la industria de construcción?**|Si sí: GTM viable en 3 meses. Si no: necesitar partner comercial|ChatGPT|
|4|**¿Cuál es el costo real de Claude API por evaluación de coherencia?**|Si >€5: margen bajo. Si <€1: margen saludable|Todos|
|5|**¿Existe ya un pipeline RAG parcial (pgvector) o no existe en absoluto?**|Si existe parcial: completar es P1. Si no existe: evaluar si es necesario|Kimi|
|6|**¿El `checkpointer` realmente hace fallback a memoria en producción?**|Si sí: P0 de seguridad de datos. Si no: bajar prioridad|ChatGPT, Claude|
|7|**¿Cuál es la tasa de alucinación actual del pipeline AI?**|Si >20%: problema crítico. Si <5%: aceptable para HITL|Todos|
|8|**¿Hay algún cliente enterprise interesado o en conversaciones?**|Si sí: priorizar sus requisitos. Si no: validar demanda primero|ChatGPT|
|9|**¿El código de `scoring.py` (897 LOC) es realmente excelente como dice Claude?**|Si sí: proteger como asset core. Si no: refactorizar antes de expandir|Claude|
|10|**¿Cuál es la estrategia de precios contemplada?**|Afecta priorización de billing vs features|ChatGPT|

---

# 10. Output Final

# Consenso Final

## La acción más importante a realizar ahora

**Rotar inmediatamente todos los secretos potencialmente expuestos en el repositorio y limpiar el historial de git.** Tres informes independientes (GLM-5.1, Claude, ChatGPT) identifican credenciales comprometidas. Si la `service_role` key de Supabase está expuesta y es válida, cualquier persona tiene acceso de escritura a la base de datos de todos los tenants. Esto es un riesgo existencial que debe resolverse antes de cualquier otra acción.

## Top 5 Prioridades de Ejecución

|#|Prioridad|Por qué|
|---|---|---|
|1|**Rotación de secretos y auditoría de seguridad**|Riesgo existencial si credenciales son válidas|
|2|**Limpieza de repositorio** (archivos basura, artefactos, dead code)|Señal de madurez; facilita todo lo demás; 3 horas de trabajo|
|3|**Hardening de CI/CD** (eliminar `continue-on-error`, subir coverage threshold, branch protection)|Sin gates reales, cualquier cambio puede romper main|
|4|**Prompt registry + eval framework**|El AI es el core del producto; sin trazabilidad ni evaluación, no hay confianza|
|5|**Landing page + validación de demanda**|Sin usuarios, todo el desarrollo técnico es especulativo; necesidad de señales de mercado|

## Top 5 Riesgos

|#|Riesgo|Severidad|Mitigación|
|---|---|---|---|
|1|**Credenciales expuestas con acceso real a datos de tenants**|Crítica|Rotar todos los secretos inmediatamente; limpiar git history|
|2|**Bus factor = 1** (solo un contribuidor)|Alta|Documentar arquitectura; crear CONTRIBUTING.md; buscar co-founder|
|3|**Coherence Score no es confiable** (hallucination rate desconocida, v1 tiene errores conocidos)|Alta|Implementar eval framework; completar v2 cutover; HITL siempre activo|
|4|**Sin validación de mercado** (0 usuarios, 0 revenue, 0 landing page)|Alta|Crear landing page; 50 customer interviews; 3 LOIs|
|5|**Deuda de repositorio impide onboarding** (40+ archivos basura, módulos duplicados, docs inconsistentes)|Media-Alta|Limpieza de repo; consolidación de módulos; docs reconciliation|

## Top 5 Oportunidades Estratégicas

|#|Oportunidad|Valor|Horizonte|
|---|---|---|---|
|1|**Coherence Score™ como estándar de la industria** (como FICO para crédito o LEED para construcción sostenible)|🔥🔥🔥|12-24 meses|
|2|**Insurance underwriting API** — Coherence Score como señal de riesgo para aseguradoras de construcción|🔥🔥🔥|6-12 meses|
|3|**Change order impact prediction** — cuando un contrato cambia, predecir ripple effects en schedule/budget|🔥🔥|3-6 meses|
|4|**API-first Coherence Score** — vender el score como API integrable en ERP/PM tools existentes|🔥🔥|3-6 meses|
|5|**Benchmarking database** — scores anónimos por industria generan network effects y data moat|🔥🔥|6-12 meses|

## Prompt Recomendado para Segunda Pasada de Agentes CLI

```
You are a CLI coding agent performing a SECOND-PASS technical audit and implementation on the C2Pro repository (https://github.com/AI-Gen-AI/C2Pro).

CONTEXT: A multi-model due diligence has identified critical issues. Your job is to VERIFY and FIX them in priority order.

PHASE 1 — VERIFICATION (do not modify any code):
1. Run: `gitleaks detect --source . --no-git` — report ALL findings
2. Run: `find . -name ".env*" -not -path "./.git/*"` — list ALL env files
3. Run: `grep -r "service_role" --include="*.py" --include="*.env*" --include="*.toml" .` — find exposed service_role key
4. Run: `grep -r "C2PRO_SKIP_HITL\|C2PRO_AI_MOCK" --include="*.py" .` — find bypass flags
5. Run: `grep -r "continue-on-error" .github/` — find non-blocking CI
6. Run: `grep -r "cov-fail-under" .github/ apps/api/` — find zero-coverage gates
7. Run: `ls -la *.txt *.pdf *.json 2>/dev/null` — find root garbage files
8. Run: `find . -name "core" -type d` — find duplicate core directories
9. Run: `grep -r "from coherence\." apps/api/src/ | head -20` — check import conventions
10. Run: `cat apps/api/src/coherence/scoring.py | wc -l` — verify scoring.py size

PHASE 2 — IMMEDIATE FIXES (with human approval):
- After verification, propose fixes for P0 items ONLY
- Each fix must be in a separate branch
- Each PR must be <200 lines changed
- Run full
```