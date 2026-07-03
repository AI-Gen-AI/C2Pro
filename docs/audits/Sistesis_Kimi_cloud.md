# Informe de Síntesis Cruzada: C2Pro

## Análisis de Consenso entre 7 Modelos LLM

**Fecha:** 14 de junio de 2026  
**Repositorio:** [AI-Gen-AI/C2Pro](https://github.com/AI-Gen-AI/C2Pro)  
**Método:** Análisis comparativo de 7 informes independientes (ChatGPT, Gemini, Kimi, Kimi+Perplexity, GLM-5.1, Claude, Grok)

---

# 1. Evaluación Reporte por Reporte

## ChatGPT — Fortalezas y Debilidades

**Fortalezas:**

- Análisis más profundo de la deuda técnica organizacional (CI `continue-on-error`, cobertura al 0%, licencia contradictoria)
    
- Identificación única de la "deuda de velocidad asistida por IA" — mucho avance rápido, poca limpieza
    
- Excelente análisis del producto como "evidence graph platform" en lugar de "orquestador de agentes"
    
- Reconocimiento de que el `Coherence Score` puede convertirse en estándar de industria
    

**Debilidades:**

- Sobreestima la madurez del backend (70-75% vs estimación más realista de 35-45%)
    
- No detecta el `.env.staging` como P0 crítico (solo lo menciona como "higiene de repo")
    
- No mide LOC ni historial de commits directamente
    
- Subestima el riesgo de patentes y el timing de divulgación pública
    

**Contribuciones únicas a preservar:**

- "Evidence Graph Platform" como arquitectura objetivo
    
- "Consulting + SaaS" como modelo de monetización híbrido
    
- Análisis de que el motor de coherencia honesto (null en lugar de score fabricado) es la característica de confianza definitoria
    

**Recomendaciones a rechazar:**

- Postergar Gates 6-8 hasta después de PMF — **RECHAZADO**. La seguridad y observabilidad son prerequisitos para cualquier piloto con datos reales, no luxuries post-PMF.
    

---

## Gemini — Fortalezas y Debilidades

**Fortalezas:**

- Identificación de patrones de arquitectura distribuida (Temporal, WASM sandbox)
    
- Enfoque en el "estado como valor" en lugar del "modelo como valor"
    
- Propuesta de routing semántico con modelos locales
    

**Debilidades:**

- **HALUCINACIÓN CRÍTICA:** Trata C2Pro como un "framework de agentes genérico" en lugar de una plataforma de inteligencia contractual vertical. No hay evidencia de "race conditions en transiciones de estado de agentes", "ejecución dinámica de herramientas sin sandbox", o "bucles de eventos síncronos" en el repositorio.
    
- No reconoce la naturaleza específica del dominio (construcción, EPC)
    
- Recomienda "Pydantic v2" cuando el proyecto ya usa Pydantic v2 (señal de análisis superficial)
    
- Sobreestima el potencial de inversión ("Yes, but with reservations") sin evidencia de tracción
    

**Contribuciones únicas a preservar:**

- Enfoque en "state machine durable" como valor central
    
- Propuesta de routing con modelos locales (Llama-3-8B) para tareas simples
    

**Recomendaciones a rechazar:**

- Casi todas las recomendaciones de arquitectura distribuida son **prematuras** para un proyecto pre-MVP
    
- "Reconstruir el motor central alrededor de Temporal.io" — **RECHAZADO**. Over-engineering. Celery + Redis es suficiente para la etapa actual.
    
- "Sandbox WASM para ejecución de herramientas" — **RECHAZADO**. C2Pro no ejecuta código arbitrario; es una plataforma de análisis de documentos.
    

---

## Kimi (Análisis Original) — Fortalezas y Debilidades

**Fortalezas:**

- Claridad brutal en la evaluación: "pre-producto, pre-revenue, pre-MVP"
    
- Identificación correcta de que el motor de coherencia es el diferenciador y está incompleto
    
- Reconocimiento de que la "coherencia 3D es un problema de grafos, no de LLM"
    
- Análisis de que el cliente real es el prestamista/inversionista, no el contratista
    

**Debilidades:**

- Subestima la complejidad del backend (trata el motor de coherencia como "teórico" cuando hay código real y sofisticado)
    
- No detecta el `.env.staging` ni el PDF de HVPNL
    
- Afirma "No CI/CD pipeline" cuando Claude verificó 15 workflows — **INCORRECTO**
    
- Afirma "No RAG architecture" cuando pgvector está en el stack — **INCORRECTO**
    
- Afirma "Frontend barely started" cuando Claude midió 54K LOC — **DESACTUALIZADO**
    

**Contribuciones únicas a preservar:**

- "El cliente real es el prestamista, no el contratista"
    
- "El motor de coherencia 3D es un problema de grafos"
    
- "Abrir el parser de documentos, no la plataforma"
    

**Recomendaciones a rechazar:**

- "Defer Gates 6-8 until after PMF" — **RECHAZADO** (mismo que ChatGPT)
    
- "No investable today" — **PARCIALMENTE RECHAZADO**. Es correcto para inversión institucional, pero subestima el potencial de pre-seed con founder de dominio fuerte.
    

---

## Kimi + Perplexity — Fortalezas y Debilidades

**Fortalezas:**

- **Mejor detección de higiene del repositorio:** Identifica 25 archivos basura en la raíz con nombres específicos
    
- Detección del `blackboard.json` como artefacto de runtime que no debería estar en Git
    
- Reconocimiento del patrón blackboard como "arquitectónicamente significativo"
    
- Identificación del "skill registry" como producto oculto
    
- Detección de que `evals/` y `openspec/` existen pero están vacíos
    

**Debilidades:**

- No mide LOC ni profundidad de código
    
- Sobreestima el riesgo del frontend "type-unsafe 5%" como "inaceptable" — exageración para una etapa pre-MVP
    
- No analiza la calidad del motor de coherencia en profundidad
    

**Contribuciones únicas a preservar:**

- Lista detallada de archivos basura con nombres específicos (útil para limpieza)
    
- "El skill registry es un producto oculto"
    
- "La EU AI Act es un viento de cola, no una cabeza de playa"
    
- "El patrón blackboard es académicamente establecido y comercialmente raro"
    

**Recomendaciones a rechazar:**

- Ninguna significativa; este informe es el más preciso en higiene de repo.
    

---

## GLM-5.1 — Fortalezas y Debilidades

**Fortalezas:**

- **Mejor análisis cuantitativo:** 155 PRs, 442 tests de coherencia, 108/108 endpoints verificados
    
- Identificación única de que el worker Celery corre en el mismo contenedor que la API (violación 12-factor)
    
- Detección de archivos con nombres de versión pip (`=2.0.0`, `=3.2.0`) como commits accidentales
    
- Reconocimiento de que el "shadow mode v2" quema tokens de Claude sin valor
    
- Análisis de que el motor de coherencia es el componente "más ingenierizado"
    

**Debilidades:**

- Afirma "primeros commits ene 2026" contradiciendo a Claude (may 2026) — **POSIBLE HALLUCINACIÓN** o referencia a repo anterior
    
- Sobreestima la madurez del motor de coherencia (80% vs estimación más conservadora de 70-75%)
    
- No detecta el `.env.staging` como crítico (solo como "alto")
    
- Subestima el riesgo de divulgación de patentes
    

**Contribuciones únicas a preservar:**

- "Celery worker en mismo contenedor que API" — bloqueador de producción real
    
- "Shadow mode v2 quema tokens sin valor" — problema de costo operativo inmediato
    
- "Gamification module exists but disconnected" — ejemplo de over-engineering
    
- "Change order impact prediction" como oportunidad estratégica
    

**Recomendaciones a rechazar:**

- "Conditionally yes investable" — **RECHAZADO**. Ningún informe con evidencia de repo sucio, secretos filtrados, y bus factor 1 puede concluir que es investable hoy.
    

---

## Claude — Fortalezas y Debilidades

**Fortalezas:**

- **Único análisis con clon completo y medición directa:** 4,841 archivos rastreados, 225K LOC backend, 54K frontend
    
- **Mejor análisis de seguridad:** Detección de `.env.staging` con `service_role` key real, JWT secret, DB creds
    
- Identificación del "dos C2Pros viviendo en un repo" (wedge de coherencia vs plataforma multi-agente)
    
- Análisis del `scoring.py` (897 LOC) como "genuinamente bien ingenierizado"
    
- Reconocimiento del "honest null-state" como diferenciador de categoría
    
- Detección del riesgo de timing de patentes en EU (novedad absoluta)
    
- Identificación de que "tridimensional" es actualmente "bidimensional"
    
- Medición precisa de bus factor = 1 (118 de 121 commits son del founder)
    

**Debilidades:**

- Subestima ligeramente el potencial de mercado (evita dar números TAM/SAM)
    
- No analiza el frontend en profundidad (mide LOC pero no funcionalidad)
    
- No identifica oportunidades estratégicas tan ampliamente como otros informes
    

**Contribuciones únicas a preservar:**

- "La higiene del repo está destruyendo silenciosamente tu credibilidad"
    
- "El mecanismo de honestidad (null en lugar de score fabricado) es el verdadero foso"
    
- "Has enviado el producto correcto por accidente de disciplina, cargando el cadáver del producto equivocado"
    
- "Tridimensional es tu titular y aún no es verdad"
    
- "El reloj de patentes es el riesgo existencial silencioso"
    

**Recomendaciones a rechazar:**

- Ninguna significativa; este es el informe más equilibrado y evidenciado.
    

---

## Grok — Fortalezas y Debilidades

**Nota:** El informe de Grok no fue proporcionado en los documentos adjuntos. Se omite del análisis cruzado.

---

# 2. Extracción de Consenso

## Hallazgos que TODOS los informes acuerdan (Consenso Unánime)

Table

|#|Hallazgo|Severidad|Evidencia|
|:--|:--|:--|:--|
|1|**El repositorio tiene problemas graves de higiene**|🔴 Crítico|40+ archivos basura en raíz, `.mypy_cache`, chat transcripts, archivos temporales|
|2|**El motor de coherencia no está completo**|🔴 Crítico|Shadow mode v2, cutover pendiente, schedule no contribuye (según Claude)|
|3|**No es investable hoy**|🟠 Alto|Sin ingresos, sin usuarios, repo sucio, bus factor 1|
|4|**El problema de mercado es real y valioso**|🟢 Oportunidad|15-30% sobrecostes en construcción, mercado $12T+|
|5|**La arquitectura base es sólida pero con duplicación**|🟡 Medio|Hexagonal DDD, pero dos `core/`, dos `ai/`, dos motores de coherencia|
|6|**El frontend está por detrás del backend**|🟡 Medio|54K LOC pero funcionalidad incierta, type safety 95%|
|7|**Falta observabilidad en producción**|🟠 Alto|Gate 7 no completado, Sentry no cableado, sin dashboards|
|8|**El bus factor es 1 (fundador único)**|🔴 Crítico|118/121 commits del mismo autor|
|9|**No hay modelo de precios ni landing page**|🟠 Alto|Fase 3 (Copiloto de Compras) no iniciada, sin monetización|
|10|**La documentación es abundante pero inconsistente**|🟡 Medio|ADRs existen pero con drift, README sobredimensiona capacidades|

## Hallazgos que LA MAYORÍA acuerda (5+ de 6 informes)

Table

|#|Hallazgo|Informes de acuerdo|Discrepancia|
|:--|:--|:--|:--|
|1|**`.env.staging` es un riesgo de seguridad**|ChatGPT, Kimi+P, GLM-5.1, Claude|Kimi original no lo detectó; Gemini no lo mencionó|
|2|**El HVPNL contract PDF no debería estar en el repo**|Kimi+P, GLM-5.1, Claude|ChatGPT, Kimi original no lo detectaron|
|3|**El motor de coherencia v2 quema tokens en shadow mode**|ChatGPT, GLM-5.1, Claude|Kimi original dice "no implementado" (contradictorio)|
|4|**Falta un registry de prompts con versionado**|ChatGPT, Kimi, GLM-5.1, Claude|Gemini no lo mencionó|
|5|**Falta un framework de evaluación de IA**|ChatGPT, Kimi, Kimi+P, GLM-5.1|Claude lo asume implícito|
|6|**El worker Celery debe separarse del contenedor API**|GLM-5.1, Claude|ChatGPT, Kimi no lo mencionaron|
|7|**El `continue-on-error` en CI es un problema**|ChatGPT, Kimi+P, GLM-5.1|Claude no lo destacó|
|8|**La cobertura de tests al 0% es meaningless**|ChatGPT, GLM-5.1|Claude no lo destacó|
|9|**El producto debería posicionarse como "Contract-to-Procurement Intelligence"**|ChatGPT, Kimi, Claude|Gemini no aplica (framework genérico)|
|10|**El foso real es el "evidence graph" trazable, no el LLM**|ChatGPT, Kimi, Claude|Gemini enfoca en infraestructura genérica|

## Hallazgos que SOLO UN INFORME menciona pero pueden ser importantes

Table

|#|Hallazgo|Informe|Evaluación de consenso|
|:--|:--|:--|:--|
|1|**Riesgo de timing de patentes EU (novedad absoluta)**|Claude|🔴 **IMPORTANTE** — Ningún otro informe consideró IP. Requiere verificación con abogado.|
|2|**El skill registry es un producto oculto**|Kimi+P|🟡 **PLAUSIBLE** — Interesante pero no prioritario|
|3|**El patrón blackboard es arquitectónicamente significativo**|Kimi+P|🟡 **PLAUSIBLE** — Académicamente correcto, pero no crítico para roadmap|
|4|**La EU AI Act es un viento de cola**|Kimi+P|🟢 **VALIOSO** — Diferenciador de ventas enterprise|
|5|**El cliente real es el prestamista/inversionista**|Kimi|🟢 **VALIOSO** — Insight de go-to-market contraintuitivo|
|6|**El motor de coherencia es un problema de grafos, no de LLM**|Kimi|🟢 **VALIOSO** — Implicaciones arquitectónicas para v3.0|
|7|**Celery worker en mismo contenedor (violación 12-factor)**|GLM-5.1|🔴 **CRÍTICO** — Bloqueador de producción real|
|8|**Archivos con nombres de versión pip (`=2.0.0`) como accidentes**|GLM-5.1|🟡 **MENOR** — Síntoma de proceso de commit deficiente|
|9|**Gamification module existe pero desconectado**|GLM-5.1|🟡 **MENOR** — Dead code a eliminar|
|10|**El shadow mode v2 quema tokens de Claude sin valor**|GLM-5.1|🔴 **CRÍTICO** — Costo operativo inmediato|

## Contradicciones entre Informes que Requieren Resolución

### Contradicción 1: ¿Está el motor de coherencia implementado o no?

Table

|Informe|Posición|Evidencia citada|
|:--|:--|:--|
|Kimi|"No implementado, teórico solo"|README dice 65% de Sprint S2|
|GLM-5.1|"80% completo, 442 tests pasando"|Mediciones propias del repo|
|Claude|"70-75% para el wedge de envío, bien ingenierizado"|Clon completo, `scoring.py` de 897 LOC|
|ChatGPT|"Parcialmente implementado, v2 shadow mode"|PRs recientes, ADR-009|

**Resolución:** Claude tiene la evidencia más fuerte (clon completo + medición directa). El motor de coherencia **SÍ existe** y es sofisticado (scoring exponencial con floor/ceiling, source-weighting, honest null-state). Sin embargo, la **promesa tridimensional NO es completamente verdadera** (schedule no contribuye según TASK-BCK-064), y el **cutover v1→v2 está incompleto** (shadow mode). La posición de Kimi ("teórico") es **incorrecta** pero comprensible si no tuvo acceso al código de `scoring.py`.

**Recomendación final:** El motor de coherencia está **~70% implementado** para el wedge de envío, con una arquitectura genuinamente diferenciada (honest scoring, evidence-maturity layer). El 30% restante (schedule dimension, cutover v2, document pipeline end-to-end) es crítico.

---

### Contradicción 2: ¿Es el proyecto investable hoy?

Table

|Informe|Posición|
|:--|:--|
|Gemini|"Sí, con reservas"|
|GLM-5.1|"Condicionalmente sí"|
|ChatGPT, Kimi, Kimi+P, Claude|"No hoy"|

**Resolución:** La mayoría aplastante (5 de 6) dice "no hoy". Gemini y GLM-5.1 son los disidentes. Gemini trata el proyecto como un framework de agentes genérico (incorrecto framing). GLM-5.1 sobreestima la madurez (80% del motor de coherencia) y no pondera adecuadamente el riesgo del bus factor 1 y los secretos filtrados.

**Recomendación final:** **NO investable hoy** para inversión institucional. Potencialmente investable en **30-90 días** si se completan los P0 (secretos rotados, schedule dimension, repo limpio, 2-3 design partners).

---

### Contradicción 3: ¿Cuál es la puntuación de seguridad?

Table

|Informe|Puntuación|Razonamiento|
|:--|:--|:--|
|Kimi|7/10|RLS, PII, 42 tests|
|GLM-5.1|7/10|RLS, PII, Clerk JWT|
|ChatGPT|4.7/10|Buenas prácticas pero secretos filtrados|
|Claude|4/10|Prácticas fuertes pero god-key filtrado es disqualifying|
|Kimi+P|5/10|`.env.staging` filtrado|
|Gemini|3/10|Trata como framework genérico sin sandbox|

**Resolución:** La discrepancia se debe a **qué se pesa**. Kimi y GLM-5.1 ponderan las prácticas de diseño (RLS, PII, tests). ChatGPT, Claude y Kimi+P ponderan las operaciones (secretos filtrados, sin `SECURITY.md`). Claude tiene la posición más equilibrada: las prácticas de diseño son 7-8/10, pero **un solo god-key filtrado arrastra la puntuación a 4/10** porque en due diligence real eso es disqualifying hasta que se resuelva.

**Recomendación final:** **4/10** hoy, **7/10 potencial** después de rotar secretos, purgar historia, y agregar `SECURITY.md`.

---

### Contradicción 4: ¿Cuál es la puntuación de diseño de IA?

Table

|Informe|Puntuación|Razonamiento|
|:--|:--|:--|
|GLM-5.1|8/10|Coherence Score novel, model routing, shadow mode|
|Claude|7/10|Scoring sofisticado, honest null-state, LangGraph|
|ChatGPT|6.2/10|LangGraph N1-N17, PII wrapper, structured output|
|Gemini|6/10|Modelos mentales multi-agente sofisticados|
|Kimi+P|5/10|Skill registry, blackboard, pero sin evals|
|Kimi|3/10|"Single model dependency, no prompt versioning, no RAG"|

**Resolución:** Kimi subestima significativamente (3/10) porque no detectó la sofisticación del motor de scoring (exponential-decay, floor/ceiling, source-weighting, honest null-state). GLM-5.1 y Claude tienen las mediciones más directas. La posición de consenso está entre **6-7/10** para el motor de scoring específico, pero **3-4/10** para la plataforma multi-agente completa (que está diferida).

**Recomendación final:** **6.5/10** para el motor de coherencia (wedge de envío), **4/10** para la plataforma AI completa (incluyendo agentes diferidos, RAG incompleto, sin evals sistemáticos).

---

# 3. Pesado de Evidencia

## Clasificación de Recomendaciones Principales

Table

|Recomendación|Clasificación|Justificación|
|:--|:--|:--|
|Rotar credenciales de `.env.staging` y purgar historia|**EVIDENCIADA**|Archivo visible en GitHub tree, formato real de JWT|
|Eliminar PDF HVPNL del repo|**EVIDENCIADA**|Archivo visible de 1.3MB en raíz|
|Limpiar 40+ archivos basura de raíz|**EVIDENCIADA**|Visible en GitHub tree|
|El motor de coherencia existe y es sofisticado|**EVIDENCIADA**|Claude midió `scoring.py` de 897 LOC con exponential-decay|
|Schedule no contribuye al scoring|**PLAUSIBLE**|Basado en TASK-BCK-064 del backlog, no verificado ejecutando|
|Shadow mode v2 quema tokens|**PLAUSIBLE**|Consistente entre ChatGPT, GLM-5.1, Claude; no verificado en ejecución|
|Bus factor = 1|**EVIDENCIADA**|Commit history visible en GitHub|
|15 CI workflows existen|**EVIDENCIADA**|Claude midió directamente del clon|
|4,574 tests de Python|**EVIDENCIADA**|Claude midió directamente del clon|
|225K LOC backend / 54K frontend|**EVIDENCIADA**|Claude midió directamente del clon|
|El cliente real es el prestamista|**ESPECULATIVO**|Hipótesis de mercado, no validada con entrevistas|
|El Coherence Score puede ser estándar de industria|**ESPECULATIVO**|Aspiración estratégica, no evidencia de adopción|
|Riesgo de timing de patentes EU|**ESPECULATIVO**|Inferencia legal, no verificada con abogado|
|$12B TAM para construction tech|**ESPECULATIVO**|Estimación de mercado, no derivada del repo|
|Cualquier GPT-4 dev puede replicar en 2 semanas|**PROBABLEMENTE INCORRECTO**|Subestima la sofisticación del scoring y el dominio|

---

# 4. Roadmap Consolidado

## Fase Inmediata: Días 0–14

**Objetivo:** Contención de riesgos críticos, limpieza de emergencia, credibilidad mínima.

Table

|Día|Tarea|Owner|Criterio de aceptación|Riesgo|Complejidad|Dependencias|
|:--|:--|:--|:--|:--|:--|:--|
|0|Rotar TODAS las credenciales de staging/producción|Fundador|Ninguna credencial antigua funciona|🔴 Alto|Baja|Ninguna|
|0-1|Purgar `.env.staging` de historia Git (`git filter-repo`)|Fundador|`git log --all --full-history -- .env.staging` retorna vacío|🔴 Alto|Media|Ninguna|
|1|Purgar PDF HVPNL de historia Git|Fundador|`git log --all --full-history -- "*.pdf"` retorna vacío|🔴 Alto|Media|Ninguna|
|1-2|Eliminar `.mypy_cache/`, `.pytest-tmp/`, `playwright-report/`, `test-results/`, `tmp-gh-artifacts/`, `temp_conflicting_frontend_files/`, `backups/` de Git|Fundador|`git ls-files|grep -E "(cache|temp|test-results|backup)"` retorna vacío|🟡 Bajo|Baja|Ninguna|
|2|Eliminar 10+ chat transcripts y archivos `.txt` de raíz|Fundador|Raíz contiene solo directorios y archivos de proyecto|🟡 Bajo|Baja|Ninguna|
|2|Eliminar archivos accidentales (`=2.0.0`, `=3.2.0`, `nombre prueba`, `{.txt`, `.codex`)|Fundador|No hay archivos con nombres de sintaxis de shell/pip|🟡 Bajo|Baja|Ninguna|
|2-3|Consolidar a un solo package manager (pnpm, eliminar `package-lock.json`)|Fundador|Solo `pnpm-lock.yaml` existe; `npm install` no genera `package-lock.json`|🟡 Bajo|Baja|Ninguna|
|3|Agregar `.gitignore` comprehensivo|Fundador|`git status` no muestra archivos no rastreados en directorios de build|🟡 Bajo|Baja|Ninguna|
|3|Agregar `LICENSE` (proprietary) + `SECURITY.md`|Fundador|Archivos existen en raíz con contenido apropiado|🟡 Bajo|Baja|Ninguna|
|3-5|Agregar pre-commit hook (Husky + gitleaks + lint)|Fundador|Cualquier commit con `.env*` o secretos es bloqueado|🟠 Medio|Media|Ninguna|
|5-7|Agregar CI gate que falle en `.env.*` rastreados|Fundador|PR con `.env.staging` falla CI automáticamente|🟠 Medio|Media|Ninguna|
|7-10|Escribir decisión ADR: ¿congelar o migrar `analysis/` + `modules/`?|Fundador|ADR publicado en `docs/architecture/decisions/`|🟠 Medio|Media|Ninguna|
|10-14|Reconciliar README con realidad actual (o renombrar a "MVP scope")|Fundador|README no afirma capacidades no implementadas|🟠 Medio|Baja|Ninguna|

## Fase Corto Plazo: Días 15–45

**Objetivo:** Completar el motor de coherencia, estabilizar infraestructura, MVP funcional.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Riesgo|Complejidad|Dependencias|
|:--|:--|:--|:--|:--|:--|:--|
|3|Wire schedule dimension into coherence scoring (TASK-BCK-064)|Backend/AI|`/coherence/evaluate/diagnostics` retorna `score_missing_dimensions=[]` con schedule upload|🔴 Alto|Alta|Document pipeline|
|3-4|Fix live 500s on alerts/stakeholders (TASK-BCK-051)|Backend|Ningún 500 en endpoints `/alerts/*` y `/stakeholders/*` en 7 días de monitoreo|🔴 Alto|Media|Sentry|
|3-4|Complete v1→v2 coherence cutover (retire v1)|Backend/AI|Feature flag `feature_coherence_analysis` = v2 para 100% de tenants; shadow mode desactivado|🔴 Alto|Alta|Schedule dimension|
|4|Persist `parsed_at` field (TASK-BCK-063)|Backend|API retorna `parsed_at` con timestamp real para documentos parseados|🟡 Bajo|Baja|Ninguna|
|4|Fix Celery task-registration drift (TASK-BCK-077)|Backend|Worker Celery reconoce todas las tareas de `analysis/` y `documents/`|🟠 Medio|Media|Ninguna|
|4-5|Separate Celery worker into own Docker container|DevOps|`docker-compose up` levanta API y worker como servicios separados; worker escala independientemente|🟠 Medio|Media|Docker|
|4-5|Remove `continue-on-error` from CI workflows|DevOps|Ningún workflow de release tiene `continue-on-error: true`|🟠 Medio|Baja|Test fixes|
|4-5|Set coverage threshold to >60%|DevOps|`pytest --cov-fail-under=60` pasa en CI|🟠 Medio|Baja|Ninguna|
|5|Add rate limiting to AI endpoints (`/coherence/*`, `/analysis/*`)|Backend|`429 Too Many Requests` retornado después de límite configurable por tenant|🟠 Medio|Media|Ninguna|
|5|Wire Sentry DSN for production monitoring|DevOps|Errores en producción aparecen en Sentry dashboard|🟠 Medio|Baja|Ninguna|
|5-6|Add clause_embeddings RLS test (TASK-SEC-012)|Backend|Test e2e verifica que tenant A no puede leer embeddings de tenant B|🟡 Bajo|Baja|Ninguna|
|5-6|Guard cookie-consent endpoints (TASK-SEC-013)|Backend|Endpoints de cookie consent requieren autenticación|🟡 Bajo|Baja|Ninguna|
|6|Add health check endpoints (`/health`, `/ready`)|Backend|Kubernetes/load balancer puede verificar salud del servicio|🟡 Bajo|Baja|Ninguna|
|6|Tag first semantic release (`v0.1.0-alpha`)|Fundador|GitHub Release existe con changelog|🟡 Bajo|Baja|Ninguna|

## Fase Medio Plazo: Días 46–90

**Objetivo:** Productización, hardening de workflows de IA, observabilidad, UX mejorada, estrategia de release.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Riesgo|Complejidad|Dependencias|
|:--|:--|:--|:--|:--|:--|:--|
|7-8|Add prompt registry with version control|AI/Backend|Todos los prompts almacenados en DB con versionado semántico; A/B test posible|🟠 Medio|Media|Ninguna|
|7-8|Build AI evaluation harness (golden corpus)|AI/Backend|50+ casos de prueba golden con métricas de precisión/recall por categoría|🟠 Medio|Alta|Prompt registry|
|7-8|Implement tenant-scoped AI cache keys|Backend|Cache key incluye tenant_id, schema_version, prompt_version|🟡 Bajo|Baja|Ninguna|
|8-9|Add multi-LLM router (OpenAI, local fallback)|AI/Backend|Si Claude falla, sistema enruta a GPT-4 o modelo local sin interrupción|🟠 Medio|Alta|Prompt registry|
|8-9|Add structured observability (OpenTelemetry)|DevOps|Traces distribuidos visibles en Grafana/Datadog; latencia por nodo de LangGraph|🟠 Medio|Alta|Sentry|
|8-9|Build real document smoke test (non-mock)|QA/Backend|Test e2e que sube PDF real, extrae texto, calcula coherencia, renderiza reporte|🔴 Alto|Alta|Document pipeline|
|9-10|Create landing page + email signup|Frontend/Marketing|Página pública con demo video o formulario de email; 100+ signups en 30 días|🟠 Medio|Media|Ninguna|
|9-10|Add data export API (GDPR compliance)|Backend|Usuario puede exportar todos sus datos en JSON/CSV|🟡 Bajo|Media|Ninguna|
|9-10|Consolidate auth model (Supabase vs Clerk decisión canónica)|Backend|Una sola estrategia de auth documentada; migración completada si aplica|🟠 Medio|Media|Ninguna|
|10-12|Add API versioning strategy|Backend|`/api/v2/` existe con plan de deprecación de v1; documentación actualizada|🟡 Bajo|Media|Ninguna|
|10-12|Implement SSO/SAML (Google Workspace, Microsoft Entra)|Backend|Enterprise puede autenticar con su IdP existente|🟠 Medio|Alta|Auth consolidation|
|10-12|Add load testing suite (k6/Locust)|DevOps|Sistema soporta 100 evaluaciones de coherencia concurrentes sin degradación|🟠 Medio|Alta|Separate Celery|

## Fase Largo Plazo: 3–6 Meses

**Objetivo:** Enterprise readiness, monetización, workflows agenticos, arquitectura escalable.

Table

|Mes|Tarea|Owner|Criterio de aceptación|Riesgo|Complejidad|Dependencias|
|:--|:--|:--|:--|:--|:--|:--|
|4|Implement billing (Stripe) con 3 tiers: Solo, Team, Enterprise|Backend|Usuarios pueden suscribirse y pagar sin intervención manual|🟠 Medio|Alta|Landing page|
|4|Build "Contract Memory" vector DB (pgvector)|AI/Backend|Cláusulas extraídas almacenadas con embeddings; búsqueda semántica funcional|🟠 Medio|Alta|Prompt registry|
|4-5|Add change order impact prediction|AI/Backend|Cuando contrato cambia, sistema predice impacto en cronograma y presupuesto|🔴 Alto|Muy alta|Coherence engine|
|4-5|Build procurement package generator (Phase 3)|AI/Backend|RFQ auto-generado a partir de análisis de coherencia|🔴 Alto|Muy alta|Coherence engine|
|5|Add multi-language support (ES/EN/PT)|AI/Backend|Documentos en inglés, español y portugués procesados con precisión comparable|🟠 Medio|Alta|Prompt registry|
|5|Release MCP server|Backend|Claude/GPT pueden llamar a C2Pro como herramienta nativa|🟡 Bajo|Media|API stable|
|5-6|Achieve SOC 2 Type I readiness|Security/Compliance|Controles documentados, auditoría programada|🔴 Alto|Muy alta|SSO, audit logs|
|5-6|First 10 paying customers|Sales/Fundador|€500-2000/MRR demostrable|🔴 Alto|Muy alta|Landing page, billing|
|6|File provisional patent (tridimensional method)|Legal/Fundador|Patente provisional presentada antes de divulgación pública adicional|🔴 Alto|Media|Legal counsel|

## Fase Futura: 6–12 Meses

**Objetivo:** Evolución estratégica de plataforma, ecosistema, integraciones, gobernanza, capacidades AI avanzadas.

Table

|Trimestre|Tarea|Owner|Criterio de aceptación|Riesgo|Complejidad|Dependencias|
|:--|:--|:--|:--|:--|:--|:--|
|Q3|Launch "Incoherence API" as standalone product|Product/Backend|API pública con documentación, webhooks, SDK|🟠 Medio|Muy alta|API platform|
|Q3|Procore/Autodesk integration pilot|Integrations|Usuarios pueden importar proyectos desde Procore/ACC|🔴 Alto|Muy alta|API platform|
|Q3|BIM integration prototype (IFC parsing)|AI/Backend|Modelo 3D parseado y correlacionado con contrato/cronograma|🔴 Alto|Muy alta|Change order|
|Q3|Insurance underwriting API pilot|Business|Aseguradora puede consultar Coherence Score vía API|🔴 Alto|Muy alta|Benchmark data|
|Q4|Build benchmarking database (anonymized)|Data/AI|Comparativa de coherencia entre proyectos de la industria|🟠 Medio|Alta|1000+ contracts|
|Q4|White-label for construction consultancies|Product|Firma de consultoría puede ofrecer auditorías con marca propia|🟠 Medio|Alta|SOC 2|
|Q4|Government procurement compliance module|Product|Validación automática contra regulaciones de licitación pública|🟠 Medio|Alta|Multi-language|
|Q4|Real-time collaboration (WebSocket)|Frontend|Múltiples usuarios revisan coherencia simultáneamente|🟠 Medio|Alta|Contract Memory|
|Q1+|Fine-tune domain-specific LLM|AI|Modelo propio para cláusulas de construcción con precisión >90%|🔴 Alto|Muy alta|Golden corpus|
|Q1+|Open-source deterministic evaluator framework|Community/AI|Framework de evaluadores publicado en GitHub con adopción comunitaria|🟠 Medio|Alta|Patent filed|

---

# 5. Matriz de Decisión Consolidada

Table

|Iniciativa|Impacto|Esfuerzo|Riesgo|Confianza|Dependencias|Prioridad|
|:--|:--|:--|:--|:--|:--|:--|
|Rotar y purgar `.env.staging` de historia Git|Crítico|Bajo|Alto|Alta|Ninguna|**P0**|
|Eliminar PDF HVPNL de historia Git|Crítico|Bajo|Alto|Alta|Ninguna|**P0**|
|Limpiar repo root (40+ archivos basura)|Alto|Bajo|Bajo|Alta|Ninguna|**P0**|
|Agregar `.gitignore` comprehensivo|Alto|Bajo|Bajo|Alta|Ninguna|**P0**|
|Agregar `LICENSE` + `SECURITY.md`|Alto|Bajo|Bajo|Alta|Ninguna|**P0**|
|Wire schedule dimension into scoring (TASK-BCK-064)|Crítico|Alto|Medio|Alta|Coherence v2|**P0**|
|Fix live 500s en alerts/stakeholders (TASK-BCK-051)|Crítico|Medio|Medio|Alta|Observabilidad|**P0**|
|Complete v1→v2 coherence cutover|Crítico|Alto|Medio|Alta|Evidence pipeline|**P0**|
|Consolidar dos motores de coherencia|Alto|Alto|Medio|Media|v2 cutover|**P1**|
|Eliminar `continue-on-error` de CI|Alto|Bajo|Bajo|Alta|Test fixes|**P1**|
|Set coverage threshold >60%|Alto|Bajo|Bajo|Alta|Ninguna|**P1**|
|Add rate limiting a endpoints de IA|Alto|Medio|Bajo|Alta|Ninguna|**P1**|
|Separar worker Celery a contenedor propio|Alto|Medio|Bajo|Alta|Docker|**P1**|
|Wire Sentry DSN|Alto|Bajo|Bajo|Alta|Ninguna|**P1**|
|Add RLS test para clause_embeddings|Medio|Bajo|Bajo|Alta|Ninguna|**P1**|
|Guard cookie-consent endpoints|Medio|Bajo|Bajo|Alta|Ninguna|**P1**|
|Persist `parsed_at` field|Medio|Bajo|Bajo|Alta|Ninguna|**P1**|
|Fix Celery task-registration drift|Medio|Medio|Medio|Alta|Ninguna|**P1**|
|Consolidar modelo de auth (Supabase vs Clerk)|Medio|Medio|Medio|Media|Ninguna|**P2**|
|Add prompt registry con versionado|Alto|Medio|Bajo|Alta|Ninguna|**P2**|
|Build AI evaluation harness (golden corpus)|Alto|Alto|Medio|Alta|Prompt registry|**P2**|
|Implement tenant-scoped AI cache|Medio|Bajo|Bajo|Alta|Ninguna|**P2**|
|Add multi-LLM router|Alto|Alto|Medio|Media|Prompt registry|**P2**|
|Add observabilidad estructurada (OpenTelemetry)|Alto|Alto|Bajo|Alta|Sentry|**P2**|
|Build real document smoke test|Alto|Alto|Medio|Alta|Document pipeline|**P2**|
|Add API versioning strategy|Medio|Medio|Bajo|Alta|Ninguna|**P2**|
|Create landing page + email signup|Alto|Medio|Bajo|Alta|Ninguna|**P2**|
|Add data export API (GDPR)|Medio|Medio|Bajo|Alta|Ninguna|**P2**|
|Implement SSO/SAML|Medio|Alto|Bajo|Media|Auth consolidation|**P3**|
|Add load testing suite|Medio|Alto|Bajo|Alta|Separate Celery|**P3**|
|Build change order impact prediction|Alto|Muy alto|Medio|Media|Coherence engine|**P3**|
|BIM integration prototype|Alto|Muy alto|Alto|Baja|API platform|**P3**|
|Procore/Autodesk integration|Alto|Muy alto|Medio|Media|API platform|**P3**|
|File provisional patent|Alto|Medio|Alto|Baja|Legal counsel|**P3**|
|Open-source evaluator framework|Medio|Alto|Medio|Baja|Patent filed|**P3**|
|Build insurance underwriting API|Alto|Muy alto|Alto|Baja|Benchmark data|**P3**|

---

# 6. Resolución de Discrepancias Importantes

### Discrepancia 1: ¿Es el motor de coherencia implementado o teórico?

**Desacuerdo:** Kimi dice "teórico"; GLM-5.1 dice "80%"; Claude dice "70-75% con scoring sofisticado".

**Lado mejor soportado:** **Claude** (clon completo + medición directa de `scoring.py` de 897 LOC).

**Evidencia necesaria:** Verificar ejecutando `/coherence/evaluate` con documentos reales.

**Recomendación final:** El motor de coherencia **existe y es genuinamente diferenciado** (honest null-state, exponential-decay scoring, evidence-maturity layer). Sin embargo, la **promesa tridimensional NO es completamente cierta** (schedule no contribuye), y el **cutover v1→v2 está en shadow mode**. Prioridad P0: completar schedule dimension y finalizar cutover.

---

### Discrepancia 2: ¿Es investable hoy?

**Desacuerdo:** Gemini y GLM-5.1 dicen "condicionalmente sí"; los otros 4 dicen "no hoy".

**Lado mejor soportado:** **Mayoría** (ChatGPT, Kimi, Kimi+P, Claude). Los disidentes subestiman el riesgo de secretos filtrados y bus factor 1.

**Evidencia necesaria:** Ninguna adicional necesaria; el consenso es claro.

**Recomendación final:** **NO investable hoy** para inversión institucional. Potencialmente investable en **30-90 días** después de P0 completion + 2-3 design partners.

---

### Discrepancia 3: ¿Cuál es la arquitectura de auth canónica?

**Desacuerdo:** README dice "Supabase Auth"; ChatGPT y Claude detectan Clerk en `config.py`; Kimi critica "custom JWT".

**Lado mejor soportado:** **Claude + ChatGPT** (inspección directa de `config.py`).

**Evidencia necesada:** Inspeccionar `src/core/security.py` y frontend para confirmar qué sistema está activo.

**Recomendación final:** **Consolidar a Supabase Auth** (ya pagado como parte del stack, RLS nativo, SSO más fácil) o **documentar explícitamente** por qué Clerk es necesario. No mantener ambos.

---

### Discrepancia 4: ¿Existe pipeline de procesamiento de documentos?

**Desacuerdo:** Kimi dice "no existe"; GLM-5.1 y Claude sugieren que existe pero está incompleto.

**Lado mejor soportado:** **Claude** (clon completo mostró módulos de documentos).

**Evidencia necesaria:** Verificar `src/modules/documents/` o `src/documents/` para confirmar extracción, chunking, embedding real.

**Recomendación final:** **Probablemente existe pero incompleto**. Prioridad P0: verificar end-to-end que un PDF sube → se parsea → se extraen entidades → se calcula coherencia.

---

### Discrepancia 5: ¿El repositorio es una re-inicialización?

**Desacuerdo:** GLM-5.1 dice "6 meses (ene 2026)"; Claude dice "1 mes (may 2026) con 225K LOC".

**Lado mejor soportado:** **Claude** (medición directa del historial Git).

**Evidencia necesaria:** Verificar si existe un repo anterior o migración desde otro VCS.

**Recomendación final:** **Probable re-inicialización** (225K LOC en 1 mes es imposible manualmente). Esto explica la "deuda de velocidad asistida por IA" que ChatGPT identificó. No afecta el roadmap, pero explica la deuda técnica.

---

# 7. Roadmap de Consenso Final (Ejecutable)

## Semana 1: Emergencia de Seguridad

**Meta:** Eliminar riesgos críticos que destruyen credibilidad.

Table

|Día|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|1|Rotar TODAS las credenciales (Supabase, Claude, R2, JWT)|Fundador|Credenciales antiguas invalidadas|Baja|
|1|`git filter-repo` para purgar `.env.staging`|Fundador|Historia limpia, verificado con `git log`|Media|
|1|`git filter-repo` para purgar PDF HVPNL|Fundador|Historia limpia, verificado con `git log`|Media|
|2|`git rm --cached` para `.mypy_cache/`, temp files, test artifacts|Fundador|`git ls-files` no muestra archivos de build|Baja|
|2|Eliminar chat transcripts y archivos `.txt` de raíz|Fundador|Raíz limpia, solo archivos de proyecto|Baja|
|3|Consolidar package manager a pnpm|Fundador|Solo `pnpm-lock.yaml` existe|Baja|
|3|Agregar `.gitignore` comprehensivo|Fundador|`git status` limpio después de build|Baja|
|3-4|Agregar `LICENSE` + `SECURITY.md`|Fundador|Archivos existen con contenido apropiado|Baja|
|4-5|Configurar pre-commit hooks (Husky + gitleaks + lint)|Fundador|Commits con secretos bloqueados automáticamente|Media|
|5-7|Agregar CI gate anti-`.env`|Fundador|PR con `.env.*` rastreado falla CI|Media|

## Semana 2-3: Completar el Motor de Coherencia

**Meta:** El producto cumple su promesa de valor principal.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|2|Investigar TASK-BCK-064 (schedule dimension)|Backend/AI|Documento de análisis de gap|Media|
|2-3|Implementar schedule extraction pipeline|Backend/AI|Schedule parseable a estructura que scoring consume|Alta|
|2-3|Wire schedule dimension into `scoring.py`|Backend/AI|`/coherence/evaluate` retorna score con 3 dimensiones|Alta|
|3|Fix TASK-BCK-051 (500s en alerts/stakeholders)|Backend|7 días sin 500s en monitoreo|Media|
|3|Fix TASK-BCK-063 (persist parsed_at)|Backend|API retorna `parsed_at` real|Baja|
|3|Fix TASK-BCK-077 (Celery task drift)|Backend|Worker reconoce todas las tareas|Media|
|3|Complete v1→v2 cutover (canary 10→50→100)|Backend/AI|v2 es autoritativo para 100% de tenants|Alta|

## Semana 4-5: Infraestructura y CI

**Meta:** Sistema estable, testable, desplegable.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|4|Separate Celery worker a contenedor propio|DevOps|`docker-compose` levanta servicios separados|Media|
|4|Remove `continue-on-error` de CI|DevOps|Todos los workflows de release bloquean en fallo|Baja|
|4|Set coverage threshold >60%|DevOps|`pytest --cov-fail-under=60` pasa|Baja|
|4-5|Add rate limiting a endpoints de IA|Backend|Rate limiting funcional por tenant|Media|
|4-5|Wire Sentry DSN|DevOps|Errores visibles en Sentry|Baja|
|5|Add health checks|Backend|`/health` y `/ready` responden correctamente|Baja|
|5|Add RLS test clause_embeddings|Backend|Test e2e pasa|Baja|
|5|Guard cookie-consent endpoints|Backend|Requieren autenticación|Baja|

## Semana 6-8: Observabilidad y Evaluación

**Meta:** Sistema medible, mejorable, confiable.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|6|Add prompt registry con versionado|AI/Backend|Prompts en DB con versionado semántico|Media|
|6-7|Build AI evaluation harness (50+ casos golden)|AI/Backend|Métricas de precisión/recall por categoría|Alta|
|7|Implement tenant-scoped AI cache|Backend|Cache key incluye tenant_id, schema_version|Baja|
|7-8|Add multi-LLM router|AI/Backend|Fallback funcional a GPT-4/local|Alta|
|7-8|Add OpenTelemetry tracing|DevOps|Traces visibles en Grafana/Datadog|Alta|
|8|Build real document smoke test|QA/Backend|Test e2e end-to-end con PDF real|Alta|

## Semana 9-12: Producto y Go-to-Market

**Meta:** Producto usable por usuarios reales.

Table

|Semana|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|9-10|Create landing page + email signup|Frontend/Marketing|Página pública funcional|Media|
|9-10|Add data export API|Backend|Exportación GDPR funcional|Media|
|10-11|Consolidar auth model|Backend|Una estrategia canónica documentada|Media|
|11-12|Add API versioning|Backend|`/api/v2/` con plan de deprecación|Media|
|11-12|Implement SSO/SAML|Backend|Enterprise puede autenticar con IdP|Alta|
|12|Tag release `v0.2.0-beta`|Fundador|Release con changelog|Baja|

## Mes 4-6: Monetización y Enterprise

**Meta:** Primeros ingresos, enterprise readiness.

Table

|Mes|Tarea|Owner|Criterio de aceptación|Complejidad|
|:--|:--|:--|:--|:--|
|4|Implement billing (Stripe)|Backend|Suscripción funcional con 3 tiers|Alta|
|4|Build "Contract Memory" vector DB|AI/Backend|Búsqueda semántica de cláusulas|Alta|
|4-5|Add change order impact prediction|AI/Backend|Predicción funcional de impacto|Muy alta|
|5|Add multi-language (ES/EN/PT)|AI/Backend|Precisión comparable entre idiomas|Alta|
|5|Release MCP server|Backend|Claude/GPT pueden llamar C2Pro|Media|
|5-6|SOC 2 Type I readiness|Security|Controles documentados|Muy alta|
|6|First 10 paying customers|Sales|€500-2000 MRR demostrable|Muy alta|

---

# 8. Preparación para Agentes CLI

## Desglose de Tareas por Agente

### Agente 1: Equipo SWAT de Seguridad e Higiene

**Alcance:** P0 seguridad + limpieza de repo **Tareas seguras:**

- Rotar TODAS las credenciales de staging/producción
    
- Purgar `.env.staging` de historia Git (`git filter-repo`)
    
- Eliminar PDF HVPNL de historia Git
    
- Eliminar `.mypy_cache/`, archivos temp, chat transcripts de raíz
    
- Actualizar `.gitignore` con reglas comprehensivas
    
- Agregar `LICENSE` + `SECURITY.md`
    
- Verificar no hay otros secretos en historia (`gitleaks scan`)
    

**Archivos a inspeccionar primero:**

- `.env.staging` (verificar contenido antes de purgar)
    
- `.gitignore` (estado actual)
    
- `gitleaks.toml` (config existente)
    
- Listado de directorio raíz (identificar todos los archivos basura)
    
- `HVPNL_First Contract (Main Contents).pdf` (verificar antes de eliminar)
    

**Comandos de verificación:**

bash

```bash
git log --all --full-history -- .env.staging
git log --all --full-history -- "*.pdf"
gitleaks detect --source . --verbose
ls -la | grep -E "(cache|temp|test|backup|worktree|\\.txt$|\\.json$)"
```

**Estrategia de ramas Git:** `hotfix/security-hygiene-p0` **Secuencia de PRs:** DEBE ser PRIMERO, antes de cualquier otro trabajo de agente **Guardrails:**

- NUNCA commitear nuevos secretos
    
- NUNCA hacer push directo a main
    
- SIEMPRE verificar purga de historia con `git log --all --full-history`
    
- Crear rama de backup antes de cualquier reescritura de historia
    

---

### Agente 2: Equipo de Completitud del Motor de Coherencia

**Alcance:** P0 producto - terminar el motor central **Tareas seguras:**

- Wire schedule dimension into scoring (TASK-BCK-064)
    
- Complete v1→v2 coherence cutover
    
- Fix live 500s en alerts/stakeholders (TASK-BCK-051)
    
- Persist `parsed_at` field (TASK-BCK-063)
    
- Fix Celery task-registration drift (TASK-BCK-077)
    

**Archivos a inspeccionar primero:**

- `src/coherence/scoring.py` (motor de scoring canónico)
    
- `src/modules/coherence/` (motor legacy a migrar)
    
- `src/analysis/` (pipeline LangGraph importando módulos legacy)
    
- `TASK-BCK-064` a `TASK-BCK-077` en backlog
    
- `src/main.py` (configuración de feature flags)
    
- `src/config.py` (flags de entorno)
    

**Comandos de verificación:**

bash

```bash
pytest tests/e2e/security/ -v -m "e2e and security"
pytest tests/ -k coherence -v
python -c "from src.coherence.scoring import CoherenceScorer; print('Import OK')"
docker-compose logs celery-worker | tail -50
```

**Estrategia de ramas Git:** `feature/coherence-engine-p0` **Secuencia de PRs:** Después de seguridad/higiene, antes de hardening de CI **Guardrails:**

- NUNCA eliminar `src/modules/coherence/` hasta que `src/analysis/` esté migrado
    
- SIEMPRE ejecutar test suite completo antes de PR
    
- NUNCA cambiar feature flags en producción sin canary
    
- Documentar todos los breaking changes en formato ADR
    

---

### Agente 3: Equipo de Hardening de CI/CD e Infraestructura

**Alcance:** P1 infraestructura **Tareas seguras:**

- Eliminar `continue-on-error` de workflows de CI
    
- Set coverage thresholds (>60%)
    
- Separar worker Celery a contenedor propio
    
- Wire Sentry DSN
    
- Add rate limiting middleware
    
- Fix issue de dual lockfile pnpm/package-lock
    

**Archivos a inspeccionar primero:**

- `.github/workflows/` (los 15 workflows)
    
- `docker-compose.yml` y `docker-compose.dev.yml`
    
- `apps/api/start.sh` (lanzador Celery + API)
    
- `apps/api/Dockerfile`
    
- `src/core/middleware.py` (rate limiting)
    
- `pyproject.toml` o `pytest.ini` (config de coverage)
    

**Comandos de verificación:**

bash

```bash
act -j test  # Ejecutar CI localmente con nektos/act
pytest --cov=src --cov-fail-under=60
pytest tests/e2e/security/ -v
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

**Estrategia de ramas Git:** `feature/ci-infrastructure-p1` **Secuencia de PRs:** Después del motor de coherencia, antes de observabilidad **Guardrails:**

- NUNCA mergear si CUALQUIER workflow falla
    
- SIEMPRE testear builds Docker localmente
    
- NUNCA commitear lockfiles sin verificar `pnpm install`
    
- Mantener `continue-on-error: true` SOLO para workflows experimentales
    

---

### Agente 4: Equipo de Observabilidad y Testing

**Alcance:** P2 observabilidad + infraestructura de evaluación **Tareas seguras:**

- Add structured logging (OpenTelemetry)
    
- Add prompt registry con version control
    
- Build AI evaluation harness (golden corpus)
    
- Add tenant-scoped AI cache
    
- Add real document smoke test
    
- Create landing page
    

**Archivos a inspeccionar primero:**

- `src/core/logging.py` o config de `structlog`
    
- `src/ai/` o `src/core/ai/` (capa de IA)
    
- Estructura de `tests/` (identificar gaps de eval)
    
- `infrastructure/evaluation/` (datasets de eval existentes)
    
- `apps/web/src/app/` (rutas frontend)
    
- `docs/architecture/ADR-009.md` (ADR de scoring)
    

**Comandos de verificación:**

bash

```bash
pytest tests/e2e/ai/ -v  # Nuevos tests de eval AI
pytest tests/contract/schemathesis/ -v -m contract
npm run build  # Verificación de build frontend
npm run test  # Tests frontend
```

**Estrategia de ramas Git:** `feature/observability-p2` **Secuencia de PRs:** Después de infraestructura de CI **Guardrails:**

- NUNCA agregar evals sin métricas baseline
    
- SIEMPRE versionar prompts con semantic versioning
    
- NUNCA commitear documentos de clientes reales en tests
    
- Usar solo fixtures sintéticos/anonymizados
    

---

## Orden Seguro de Tareas (Dependencias Secuenciales)

plain

```plain
Semana 1-2: Agente 1 (Seguridad e Higiene)
    ↓ [BLOQUEANTE: secretos deben purgarse antes de cualquier otro trabajo]
Semana 2-3: Agente 2 (Motor de Coherencia)
    ↓ [BLOQUEANTE: producto core debe funcionar antes de hardening de infra]
Semana 3-4: Agente 3 (CI/CD Infraestructura)
    ↓ [BLOQUEANTE: CI debe pasar antes de agregar nuevas features]
Semana 4-6: Agente 4 (Observabilidad y Testing)
    ↓ [BLOQUEANTE: observabilidad debe existir antes de deploy a producción]
Semana 6+: Deploy a producción + beta testing
```

---

## Expectativas de Tests Automatizados

### Checklist Pre-PR (TODOS los agentes deben verificar)

bash

```bash
# 1. Security scan
python -m bandit -r src/ -f json -o bandit-report.json
gitleaks detect --source . --verbose

# 2. Type checking
mypy src/ --ignore-missing-imports

# 3. Linting
ruff check src/
black --check src/

# 4. Unit tests
pytest tests/unit/ -v --cov=src --cov-fail-under=60

# 5. Integration tests
pytest tests/integration/ -v

# 6. E2E security tests
pytest tests/e2e/security/ -v -m "e2e and security"

# 7. Contract tests (si OpenAPI cambió)
pytest tests/contract/schemathesis/ -v -m contract

# 8. Frontend build
npm run build

# 9. Frontend type check
npm run type-check
```

### Verificación Post-Merge

bash

```bash
# 1. Deploy a staging
# 2. Ejecutar smoke tests contra staging
# 3. Verificar Sentry recibe errores
# 4. Verificar logs son estructurados
# 5. Verificar rate limiting está activo
# 6. Confirmar no hay 500s en endpoints core
```

---

## Guardrails para Prevenir Cambios Destructivos

### PROHIBICIONES ABSOLUTAS:

1. **NUNCA** ejecutar `git push --force` a main
    
2. **NUNCA** eliminar `src/modules/coherence/` sin plan de migración
    
3. **NUNCA** cambiar contenido de `.env.staging` (solo purgar de historia)
    
4. **NUNCA** commitear documentos de clientes reales
    
5. **NUNCA** desactivar RLS en ninguna tabla
    
6. **NUNCA** eliminar tests de seguridad sin reemplazo
    
7. **NUNCA** cambiar JWT secret sin plan de rotación
    

### REVISIONES REQUERIDAS:

1. Cualquier cambio a `src/coherence/scoring.py` → requiere actualización de ADR
    
2. Cualquier cambio a flujo de auth → requiere actualización de test de seguridad
    
3. Cualquier cambio a workflow de CI → requiere verificación local con `act`
    
4. Cualquier nueva dependencia → requiere `pip-audit` o `npm audit`
    
5. Cualquier migración de DB → requiere test de rollback
    

### REQUERIMIENTOS DE BACKUP:

1. Crear tag `backup/pre-cleanup` antes del trabajo del Agente 1
    
2. Crear tag `backup/pre-coherence-cutover` antes del trabajo del Agente 2
    
3. Dump de base de datos antes de cualquier migración
    
4. Export full `git bundle` semanal
    

---

# 9. Preguntas Abiertas

## Preguntas que Materialmente Afectan Decisiones de Roadmap

### 1. ¿El repositorio actual es una re-inicialización de un proyecto más antiguo?

**Discrepancia:** GLM-5.1 afirma "primeros commits ene 2026" (~6 meses); Claude mide "primer commit 2026-05-09" (~1 mes) con 225K LOC.  
**Implicación:** Si es re-inicialización, el historial real puede estar en otro repo. Afecta evaluación de velocidad y deuda técnica.  
**Evidencia necesaria:** Verificar si existe repo anterior o migración desde otro VCS.

### 2. ¿La dimensión "cronograma" realmente no contribuye al Coherence Score?

**Discrepancia:** Claude afirma TASK-BCK-064 muestra schedule no contribuye. Kimi dice motor es "teórico". GLM-5.1 dice 80% completo.  
**Implicación:** Si "tridimensional" es "bidimensional", el producto no cumple su promesa principal.  
**Evidencia necesaria:** Ejecutar `/coherence/evaluate/diagnostics` con documento de cronograma real.

### 3. ¿El motor v2 está en shadow mode desperdiciando tokens?

**Discrepancia:** ChatGPT, GLM-5.1, Claude confirman shadow mode.  
**Implicación:** Cada evaluación gasta doble tokens de Claude sin beneficio. Problema de costo inmediato.  
**Evidencia necesaria:** Revisar `src/coherence/scoring.py` y feature flags.

### 4. ¿Cuál es la arquitectura de auth canónica: Supabase o Clerk?

**Discrepancia:** README dice Supabase. ChatGPT y Claude detectan Clerk. Kimi critica custom JWT.  
**Implicación:** Afecta toda estrategia de identidad y enterprise SSO.  
**Evidencia necesaria:** Inspeccionar `src/core/security.py`, `src/config.py`, y frontend.

### 5. ¿Existe realmente pipeline de procesamiento de documentos?

**Discrepancia:** Kimi dice "no existe". GLM-5.1 y Claude sugieren existe pero incompleto.  
**Implicación:** Sin pipeline, producto no puede ingerir input principal. Bloqueador absoluto.  
**Evidencia necesaria:** Verificar `src/modules/documents/` o `src/documents/`.

### 6. ¿El frontend de 54K LOC es funcional o placeholder?

**Discrepancia:** Claude mide 54K LOC. Kimi dice "no visible routes/pages".  
**Implicación:** Si es mayoritariamente scaffold, esfuerzo de productización es mayor.  
**Evidencia necesaria:** Inspeccionar `apps/web/src/app/`.

### 7. ¿El PDF HVPNL es documento de cliente real o fixture?

**Discrepancia:** Claude identifica "Haryana power utility". Kimi+P lo llama "production PDF".  
**Implicación:** Si es cliente real, exposición es legal/contractual.  
**Evidencia necesaria:** Verificar metadatos del PDF y referencias en código.

### 8. ¿Los 4,574 tests son reales o generados por IA de baja calidad?

**Discrepancia:** Claude mide 4,574 tests. ChatGPT señala cobertura al 0% es meaningless.  
**Implicación:** Si tests son de baja calidad, confianza en sistema es falsa.  
**Evidencia necesaria:** Muestrear 50 tests aleatorios.

### 9. ¿Los 15 CI workflows son funcionales o templates sin activar?

**Discrepancia:** Claude mide 15 workflows. Kimi dice "No CI/CD pipeline".  
**Implicación:** Si no se ejecutan, CI es teórico.  
**Evidencia necesaria:** Verificar `.github/workflows/` y historial de ejecuciones.

### 10. ¿La estrategia de negocio es SaaS, consultoría, o API-first?

**Discrepancia:** ChatGPT sugiere consultoría. Kimi sugiere datos. Claude sugiere evidence trail. GLM-5.1 sugiere SaaS + implementation.