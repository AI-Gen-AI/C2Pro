# SPEC — Category Routing & Coherence Score v1.0

> Brief de implementación para Claude Code. Consolida las decisiones de diseño
> acordadas para sustituir la detección de categoría por keywords por un sistema
> de routing per-chunk con priors, embeddings y escalado LLM, y para fijar la base
> del Coherence Score como número descomponible.
>
> **Estado:** borrador para confirmación. Ver §9 (Decisiones abiertas) antes de ejecutar.
> **Alcance:** Gate 5 (Coherence Score Formal) / Sprint S2 — Coherence Engine MVP.

---

## 1. Objetivo y problema

El método actual identifica la categoría (LEGAL, SCOPE, BUDGET, SCHEDULE, TECHNICAL,
QUALITY) por coincidencia de keywords. Si no hay match, **la categoría no se detecta
y no se evalúa** → falso negativo silencioso. Caso patológico: un contrato sin la
keyword exacta deja LEGAL sin score, cuando un contrato *es* LEGAL por definición.

**Causa raíz:** se usa un mismo mecanismo (keyword gate) para dos decisiones que
deben separarse:

1. **Routing** — ¿esta categoría está presente / es relevante? (qué se evalúa)
2. **Scoring** — ¿qué coherencia tiene? (cuánto puntúa)

**Corrección de diseño:** pasar de *gate binario* a *relevancia continua con suelo
(prior)*. La ausencia genuina de evidencia se convierte en `InsufficientEvidence`
explícito, nunca en categoría desaparecida.

---

## 2. Decisiones arquitectónicas (constraints — NO renegociar en implementación)

- **D1.** Separar routing de scoring. El routing decide qué categorías se evalúan; el
  scoring (ya existente: alertas × impacto → decay) puntúa dentro de cada categoría.
- **D2.** La relevancia de categoría se calcula **per-chunk** y se **agrega a documento**.
- **D3.** Cascada en capas por coste/confianza:
  - **Capa 0 — Priors por tipo:** suelo mínimo de relevancia, solo para categorías
    *definitorias* del tipo de segmento.
  - **Capa 1 — Determinista (sin LLM):** similitud por embeddings contra prototipos de
    categoría (pgvector) + señales estructurales + lexicón degradado (lematizado, ES+EN).
  - **Capa 2 — Nodo LLM (LangGraph):** clasificador multi-label, invocado **solo** para
    chunks en zona ambigua (relevancia entre umbrales de escalado).
- **D4.** `doc_relevance(cat) = max(prior_floor(cat), aggregated_chunk_relevance(cat))`.
  Esta es la pieza que mata el falso negativo.
- **D5.** Si ninguna señal supera el umbral mínimo → `InsufficientEvidence` (cablear con
  `poor_extraction_quality`), nunca omisión.
- **D6.** `doc_type` **manual** en v1.0 (ya existe en el upload). Autodetección diferida
  a v1.1+ y solo como *contraste* sobre la etiqueta manual, nunca como fuente primaria.
- **D7.** **La unidad interna es el SEGMENTO, no el archivo.** Ingesta unificada:
  - *Docs separados:* archivo = 1 segmento, tipo = etiqueta manual.
  - *Monolito:* archivo = N segmentos, separados por **marcadores estructurales**
    (ANEXO/ANNEX/APÉNDICE + ToC), con fallback a segmento único del tipo declarado.
  - La segmentación se apoya en **estructura** (p.ej. tabla con columnas fecha/duración),
    NO en la palabra suelta. ⚠️ `schedule` en EN = "anexo" Y "cronograma": no segmentar
    por la palabra.
- **D8.** El segmento es, en v1.0, **routing + anclaje** (Opción B), NO un nivel con score
  propio. **Pero `segment_id` se persiste en cada chunk y finding desde el día uno**, de
  modo que un futuro "score por segmento" (Opción A) sea puramente aditivo, sin migración.
- **D9.** El segmento es el ancla para los evaluadores cross-dimensionales (BUDGET↔SCHEDULE,
  SCOPE↔BUDGET): da el "esta región es el cronograma / esta el presupuesto".
- **D10.** **Veredicto global descomponible**, no escalar plano:
  `titular único → 6 categorías → findings con cláusula`. Mismo número a tres altitudes.
- **D11.** **Núcleo canónico fijo vs overlay configurable.** El scoring intra-categoría y
  la composición canónica a global son fijos, versionados y publicables (candidato a
  estándar/marca). La ponderación por empresa es **overlay diferido, siempre por encima del
  canónico, etiquetado como "vista personalizada", y NUNCA llamado "Coherence Score".**
- **D12.** Comparabilidad gobernada por `score_version` + `cutoff_date`, **visibles** en
  salida. Dos scores con `score_version` distinto no son directamente comparables.

---

## 3. Alcance v1.0 (in scope)

1. `CategoryRegistry` (YAML → Pydantic v2) como fuente de verdad.
2. Build step de **centroides de prototipo** → cache en pgvector con clave
   `(category, embedding_model, score_version)`.
3. `CategoryRouter` (Capa 0 + Capa 1): relevancia per-chunk per-categoría + prior floor.
4. `CategoryClassifierNode` (Capa 2, LangGraph): escalado solo de chunks ambiguos.
5. Agregación chunk → segmento (anclaje) → documento, con la regla `max(prior, agg)`.
6. Ingesta unificada a segmentos (separados + monolito con segmentación estructural).
7. Composición de veredicto global **descomponible**.
8. Tests TDD + ampliación del golden corpus (ver §8).

## 3b. Fuera de alcance v1.0 (NO construir ahora — explícito para evitar over-build)

- Autodetección de `doc_type` (diferida a v1.1+, solo contraste).
- Score por segmento / Opción A (solo persistir `segment_id`).
- Ponderación de categorías configurable por empresa (overlay, fase posterior).
- Calibración automática de pesos/umbrales (dejar **hook**, usar pesos fijos en v1.0).

---

## 4. Modelo de datos (cambios)

> Respetar hexagonal: YAML/DB son adaptadores; el dominio recibe modelos Pydantic
> validados e inyectables. Mantener compatibilidad de API.

- **`segments`** (nueva): `id`, `document_id` (FK), `segment_type` (enum categorías-tipo),
  `ordinal`, `span`/offsets, `source` ∈ {`file`, `monolith_marker`, `fallback_single`}.
- **`chunks`**: añadir `segment_id` (FK). **Persistir siempre**, incluso en modo separados.
- **`findings`**: añadir `segment_id` (FK) para anclaje (refuerza Gate 4).
- **`category_relevance`** (nueva o JSONB en chunk): relevancia por chunk × categoría, con
  desglose de señal (`embedding`, `structural`, `lexicon`) para trazabilidad/depuración.
- **`category_centroids`** (nueva, pgvector): `category`, `embedding_model`, `score_version`,
  `vector`, `seed_hash`. Reproducibilidad histórica por `score_version`.
- Mantener RLS / `_apply_tenant_filter` en toda tabla nueva.

---

## 5. CategoryRegistry — formato

Fuente de verdad: `config/category_registry.yaml`. Cargado y validado en Pydantic v2 al
arranque. **Guarda texto semilla de prototipos, NO vectores** (los vectores se precalculan
y cachean — §4).

```yaml
version:
  registry_version: "1.0.0"
  score_version: 7
  embedding_model: "bge-m3"     # CANDIDATO, no cerrado — bake-off empírico (§9)
  cutoff_date: "2026-06-01"
  languages: [es, en]

defaults:
  weights: { embedding: 0.60, structural: 0.25, lexicon: 0.15 }   # fijos v1.0
  thresholds: { escalate_low: 0.35, escalate_high: 0.65, insufficient_evidence: 0.20 }

categories:
  LEGAL:
    enum: LEGAL                 # debe coincidir con enum de dominio
    prototypes:
      es: ["Cláusula de indemnización y limitación de responsabilidad",
           "Resolución del contrato por incumplimiento"]
      en: ["Indemnification and limitation of liability",
           "Termination for breach of contract"]
    structural_signals:
      section_titles:
        es: [indemnización, responsabilidad, resolución, jurisdicción, garantía]
        en: [indemnification, liability, termination, jurisdiction, warranty]
      patterns: ['\bcláusula\s+\d+', '\bclause\s+\d+']
    lexicon:                    # degradado a "una señal más"
      es: [contrato, cláusula, penalización]
      en: [contract, clause, penalty]
  # ... SCOPE, BUDGET, SCHEDULE, TECHNICAL, QUALITY

doc_type_priors:                # SOLO categorías definitorias del tipo
  contract:        { LEGAL: 0.70, SCOPE: 0.55 }
  budget_boq:      { BUDGET: 0.75 }
  schedule_gantt:  { SCHEDULE: 0.75 }
  technical_spec:  { TECHNICAL: 0.70 }

ingestion:
  segmentation:
    monolith_strategy: structural_markers
    fallback: single_segment_declared_type
    markers:
      es: [anexo, apéndice, pliego]
      en: [annex, appendix]     # OJO: "schedule" excluido a propósito (trampa léxica)

aggregation:
  chunk_combiner: weighted_mean
  doc_method: top_k_saturating
  top_k: 3
  doc_relevance: "max(prior_floor, aggregated_chunk_relevance)"
  keep_evidence_pointers: true
```

---

## 6. Flujo (LangGraph)

```
ingest → segmentar (D7) → chunk → embeddings
      → CategoryRouter [Capa0 priors + Capa1 determinista]  (per-chunk × categoría)
          ├─ relevancia clara → enrutar a evaluadores de esa categoría
          ├─ zona ambigua     → CategoryClassifierNode [Capa2 LLM]
          └─ bajo umbral      → InsufficientEvidence
      → agregación chunk→segmento→documento (D4)
      → evaluadores por categoría + cross-dimensionales (anclados a segmento, D9)
      → ScoringService (decay intra-categoría) → composición global (D10)
```

Encaja en el subgrafo de 7 nodos existente y el `ScoringService`. Mantener spans de
LangSmith en los nodos deterministas nuevos. Claude vía `AnthropicWrapper` en Capa 2.

---

## 7. Veredicto global

- Intra-categoría: alertas × impacto → decay exponencial (**ya existe, no tocar**).
- **Titular global: eslabón débil (mínimo penalizado)** — *orientación recomendada, NO
  cerrada (§9).* Más resistente a manipulación y más fiel al riesgo de un gate de compra:
  una dimensión crítica rota impide verde aunque las otras 5 brillen. Variante exacta (mín.
  puro / penalizado / mín. sobre subconjunto crítico + media en el resto) pendiente de
  análisis sobre el golden corpus. Media ponderada disponible solo como **lente secundaria**,
  nunca como titular canónico.
- Salida **descomponible** (D10): titular → score por las 6 categorías → findings con
  cláusula y `segment_id`.
- Núcleo canónico fijo (D11). Cualquier overlay configurable se calcula aparte y se
  etiqueta como vista personalizada.

---

## 8. Testing (TDD)

Tests que deben existir antes de cerrar la fase:

1. **Regresión del falso negativo (test estrella):** documento donde una categoría está
   presente pero **sin la keyword** → la categoría se detecta y evalúa (no desaparece).
2. **Prior floor:** contrato sin señales léxicas de LEGAL → LEGAL nunca cae a 0.
3. **Bilingüe ES/EN:** mismos prototipos detectan equivalentes en ambos idiomas.
4. **Monolito:** PDF con cuerpo + anexo presupuesto + anexo cronograma → segmentos
   correctos; BUDGET embebido detectado por Capa 1 aunque el doc_type sea `contract`.
5. **Trampa léxica:** `schedule` (EN) como anexo legal NO se confunde con cronograma.
6. **Degradación:** monolito sin marcadores → fallback a segmento único, sin fantasmas.
7. **Escalado:** chunk ambiguo invoca Capa 2; chunk claro NO invoca LLM (control de coste).
8. **Reproducibilidad:** mismo `score_version` + `embedding_model` → mismos centroides.

Ampliar el golden corpus (15 bundles) con fixtures para 1, 3, 4, 5. Mantener CI verde.

---

## 9. Decisiones abiertas — CONFIRMAR antes de ejecutar

1. **Composición global canónica:** orientación → **eslabón débil** (más potente y veraz,
   resistente a manipulación). NO cerrada. Análisis pendiente sobre el golden corpus: mínimo
   puro vs penalizado/suavizado vs mínimo sobre subconjunto crítico + media en el resto, y
   explicabilidad a C-level. Define la fórmula publicable, así que cambiarla tras publicar es
   costoso — analizar bien antes de fijar.
2. **Embedding model:** el *enfoque* (embeddings multilingües vs prototipos) está confirmado;
   el *modelo concreto* NO. Elegir por **bake-off empírico** sobre el golden corpus, no por
   reputación. Candidatos: `bge-m3`, `multilingual-e5-large`, OpenAI `text-embedding-3`,
   Cohere multilingual v3. Criterios: separación de las 6 categorías en ES+EN, coste/hosting
   (open-weights self-host vs API), dimensión (impacto en índice pgvector). La clave
   `(category, embedding_model, score_version)` permite cambiar y comparar sin retrabajo.
3. **`segments`:** ¿tabla dedicada (recomendado) o metadata ligera en chunk?
4. **Naming:** alinear enum de dominio (`TIME` vs `SCHEDULE`) con el registry para evitar drift.
5. **Curación de prototipos:** quién redacta el texto semilla por categoría (ES+EN). Es
   trabajo real y determina la calidad de Capa 1.

**(Decision, 2026-06-03):** Empirical bake-off deferred for v1.0. OpenAI
`text-embedding-3-small` (1536-dim) chosen to match existing pgvector columns
(`document_chunks`, `clause_embeddings`, `category_centroids`). Model is swappable
via the `(category, embedding_model, score_version)` composite key; a 1024-dim
model
(e.g. `bge-m3`) requires a vector-column migration. `centroid_builder` enforces a
runtime dimension guard against mismatches (pre-flight `_KNOWN_MODEL_DIMS` reject
+
post-embedding length backstop).

---

## 10. Fases de implementación (orden sugerido)

1. Enum/naming + `CategoryRegistry` (YAML + loader Pydantic) + tests de carga/validación.
2. `segments` + `segment_id` en chunks/findings + ingesta unificada (D7) + degradación.
3. Build de centroides + cache pgvector (`category_centroids`).
4. `CategoryRouter` (Capa 0 + Capa 1) + agregación `max(prior, agg)` + `InsufficientEvidence`.
5. `CategoryClassifierNode` (Capa 2) con escalado por umbral + spans LangSmith.
6. Composición de veredicto global descomponible.
7. Golden corpus ampliado + tests §8 en verde.

---

## 11. Contexto estratégico (NO es trabajo de Claude Code — registrado para no perderlo)

- **Patente:** valorar provisional sobre el *engine* de detección cross-dimensional ANTES
  de publicar/defender el TFM (novedad absoluta UE, sin año de gracia). Confirmar con
  asesor de IP. Sin límite de tiempo del TFM, la secuencia viable es: provisional → defensa
  → whitepaper.
- **Publicación:** publicar el **método** (las 6 categorías, decay, composición canónica);
  proteger el **engine** y la **marca** (patrón NPS).
- **Marca:** "Coherence Score" es descriptivo (protege flojo). Valorar envoltorio de marca
  más distintivo.
- **Validación (palanca de referente):** arrancar loop "score bajo → sobrecoste",
  retrospectivo sobre el golden corpus. *Esto sí puede convertirse en harness de análisis
  más adelante.*
- **Vehículos:** TFM = rigor; whitepaper = adopción. Ambos, no intercambiables.
