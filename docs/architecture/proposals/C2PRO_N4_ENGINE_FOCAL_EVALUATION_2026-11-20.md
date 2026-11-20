# N4: evaluación focal del motor (A: Pydantic actual · B: PydanticAI · C: consulta de cláusulas y anexos)

| Campo | Valor |
|---|---|
| Fecha | 2026-11-20 |
| Estado | Decisión técnica **propuesta**. No autoriza dependencias, migraciones, llamadas facturables ni frameworks. **No detiene VS-1** |
| Código observado | Runtime `799ce531` |
| Evidencia | `docs/audits/evidence/2026-11-20-n4-engine-spike/` (spike de PydanticAI con modelo simulado y resolución de dependencias, ambos en un venv aislado; ninguna instalación en el producto) |

## 1. Decisión

**No cambiar el motor N4.** Se adopta **A**, más una versión **determinista y acotada de C**. **B se rechaza por ahora.** Docling y LlamaIndex no se incorporan mientras no haya una carencia demostrada.

El problema de N4 observado hasta ahora **no es de estructura de respuesta**:
- En el piloto SEC, las 24 respuestas se parsearon y se persistieron (142 candidatos con un esquema válido).
- Los fallos reales son otros cuatro:
  1. referencias pendientes que bloquean ventanas;
  2. un puente "todo o nada";
  3. severidad descartada y un alcance limitado a riesgos;
  4. el 65 % de citas no localizadas (92 de 142).

Ningún framework corrige estos cuatro puntos. Se corrigen con prompt, contrato de datos, contexto y trazabilidad.

## 2. Respuestas a las seis preguntas

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿PydanticAI mejora la calidad semántica o solo la estructura? | **Solo la estructura** (validación tipada, bucle de herramientas). Con el mismo modelo, el mismo prompt y el mismo contexto, la semántica no cambia. Además, **por defecto vuelve a llamar al modelo si la salida es inválida**, y esa segunda llamada sería facturable. Con `retries=0` falla cerrado, que es lo que ya hace `parse_n4_window_output`. | Spike: con salida inválida, 2 llamadas por defecto y con `retries=1`; 1 llamada con `retries=0`. Es compatible con las versiones fijadas (`anthropic 0.125.0`, `pydantic 2.14.4`, `pydantic-ai-slim 2.32.2`), así que el obstáculo es de valor y riesgo, no de compatibilidad |
| ¿Cómo mantener un análisis exhaustivo sin depender solo de RAG? | El **barrido completo por ventanas** sigue siendo la pasada principal: el 100 % del texto N2, con ledger de cobertura por ventana. RAG solo devuelve los *k* fragmentos más parecidos y no garantiza cobertura. Por eso la recuperación se usa **solo** para resolver referencias y para consultas entre documentos, nunca para decidir qué se analiza. | `plan_n4_source_windows` + `n4_extraction_windows`; el RAG actual (`rag_service.py`) trocea en bloques de 1.000 caracteres sin respetar cláusulas |
| ¿Cómo evitar reintentos facturables y accesos no autorizados? | (1) Una llamada por reserva, sin reintento automático (`UNKNOWN=STOP`). (2) **Sin bucles de herramientas guiados por el modelo**: con *tool use* cada turno es otra llamada facturable, y el número de turnos no se conoce de antemano. Las cláusulas y anexos referidos se **resuelven antes** de llamar al modelo, de forma determinista, y se añaden al contexto con su procedencia. (3) Las consultas pasan por el repositorio con RLS del tenant, limitadas al mismo proyecto, a la familia documental y a la revisión vigente. | Ledger `reserve_call`/`account_call`; guarda cross-generation de #1276 |
| ¿Cómo distinguir hechos contractuales de riesgos? | Salida tipada con discriminador `record_type`: `fact` (`kind` ∈ obligación, hito, garantía, penalización, pago, exclusión, responsabilidad; valor tipado; cita; cláusula) o `risk` (`risk_reason`, `severity_proposed` o `UNASSESSED`, consecuencia, `fact_refs[]`). Los **hechos no generan alertas, severidad ni penalización del Score**. Se validan con una unión discriminada de Pydantic v2, que ya es dependencia. | Lo exige CORE (#1259, 7022543946 §3) |
| ¿Cómo garantizar trazabilidad al documento y la página originales? | La cadena es: cita verificada en N2 → mapa de redacciones N2 → offset en `parsed_text` → bloque de PyMuPDF (`page`, `bbox`, ya extraídos en `pdf_file_parser.py:217-238`) → **verificación literal contra el texto de esa página, releída del PDF original con su `blob_hash`**. Si algún eslabón falla, `ORIGINAL_PAGE_UNVERIFIED`. Se reutiliza la lógica de `attest_original_sec_filing_pages` del recuperador SEC. | El parser ya guarda la página; falta el mapa de offsets (hipótesis H-c) |
| ¿Qué se reutiliza y qué sobra? | Ver §3 | — |

## 3. Qué reutilizar, qué falta y qué sobra

- **Se reutiliza:**
  - planificador de ventanas, ledger y reservas, puente gobernado y validador de ventana (ampliado a un modelo Pydantic tipado);
  - parser PyMuPDF (páginas y `bbox`; tiene `find_tables()` nativo sin dependencias nuevas, aún sin usar);
  - N2;
  - entidad `Clause` con `clause_number`;
  - RAG con pgvector, solo para resolver referencias y para consultas entre documentos;
  - arneses de evaluación `n4_n12_representative_eval.py`/`_gate.py` (topes `MAX_CALLS` y `MAX_USD`) y `golden/`.
- **Falta, sin framework nuevo:**
  - **A1:** prompt v2 con hechos y riesgos tipados.
  - **A2:** pedir la salida con *tool use* forzado del SDK de Anthropic y un esquema generado desde el modelo Pydantic, en lugar de JSON en texto libre.
  - **A3:** revisar `max_tokens=2048` (`n4_anthropic_window_provider.py:94`), que con hechos y riesgos puede truncar la salida, y recalcular la reserva por ventana en consecuencia.
  - **C1:** resolvedor determinista de referencias contra el índice de cláusulas y la familia documental.
  - **T1:** mapa de offsets hasta la página.
- **Sobra o no aporta ahora:**
  - el bucle de agente de PydanticAI (B);
  - LlamaIndex, que duplicaría el RAG y la orquestación con LangGraph;
  - Docling, mientras no se demuestre una pérdida de tablas u orden de lectura;
  - la ruta legada `risk_extraction_tool` de una sola llamada, candidata a retirarse cuando el N4 gobernado sea la única ruta (fuera del alcance actual).

## 4. Experimento mínimo para demostrar la decisión

| Fase | Qué | Coste | Autorización | Criterio de decisión |
|---|---|---|---|---|
| **E0** (hecho) | Spike de PydanticAI (reintentos, compatibilidad) | 0 | Ninguna (scratch) | B no aporta nada estructural que A no tenga, y añade riesgo de reintentos facturables por defecto |
| **E1** | Fidelidad del parser sobre el PDF SEC original, en el VPS: páginas con tablas, texto de celdas presente en `parsed_text`, orden de lectura y páginas vacías u OCR | 0 | DEV-16 y acceso al VPS (misión M5) | Si se pierde texto material en tablas o en el orden de lectura y `find_tables()` no lo arregla, se evalúa Docling en un experimento aparte. Si no, se descarta |
| **E2** | Ablación sobre **6 ventanas estratificadas** de un contrato público autorizado (referencias a anexos, tabla de precios o hitos, excepción, pago, garantía, ventana simple). **V0**: prompt v1 actual. **VA**: v2 tipado con *tool use* forzado. **VA+C**: VA más referencias resueltas de antemano. 1 llamada por ventana y variante (18 llamadas), `retries=0`, `temperature=0`, mismo modelo, con el arnés `n4_n12_representative_eval` | Hipótesis ≤ $1 (tope duro de `MAX_USD`; el SEC costó $0,016 por ventana) | **GO económico específico** de CORE + un oráculo humano para esas 6 ventanas | VA o VA+C deben mejorar frente a V0 el recall de elementos del oráculo y el porcentaje de citas literales, con 0 hechos sin cita. **B solo entra en E3 si VA tiene más de un 5 % de sobres inválidos o truncados** |

Lo que E2 **no demuestra**: el recall sobre un contrato completo ni la generalización. Eso corresponde a FG-1 y FG-1c.

## 5. Orden respecto a la recuperación en curso

- VS-1 (visibilidad parcial) sigue siendo lo primero y no depende de esta decisión.
- El prompt v2 (A1–A3) y C1 forman la propuesta VS-2, condicionada a E2.
- La trazabilidad de página (T1) puede diseñarse en paralelo.
- Ninguna de estas piezas añade dependencias al producto.
