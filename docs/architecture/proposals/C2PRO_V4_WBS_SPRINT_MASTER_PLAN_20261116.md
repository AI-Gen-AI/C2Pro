# C2Pro V4 — Plan Director WBS y Sprints (versión de aprobación)
**Fecha base:** lunes 16/11/2026 (Europa/Madrid)
**Estado:** PLAN — documentación únicamente. Sin autorizar implementación, PR de código, cambio de piloto ni gasto operativo.
**Fuente:** propuesta V4, dictamen Claude Sonnet, contraste técnico propio, ADR-014/017 y checkpoints #1049/#1229/#1234.

## 1. Objetivo y restricciones
Construir inteligencia de proyectos multivertical con: ingesta segura y fuente íntegra; extractores especializados N4/N5/N9/requisitos; evidencia/versiones; N12/N15; ProjectState y ProjectGraph; Coherence/Health validado vs provisional; decisiones HITL individuales y finales; dashboard y tres modalidades **Rápido (preliminar), Completo (default), Auditoría (reforzado)**.
**No rediseñar 17 N simultáneamente.** Priorizar MVP N4 con ventanas+ledger, introducir tools agénticas adicionales solo tras evidencia de ventaja frente a ese mínimo.
**Coste/latencia:** no model call por cada nodo; modelos para semántica, deterministas para cálculo, seguridad y evidencia. RAG no condiciona inicio de N4/N12.
**No confundir plan con estado real.** PR #1234 está DRAFT no fusionada (HEAD de revisión f04b1b2a); PR #1232 merged; #1229 piloto UAT todavía abierto. Coordinación canónica #1049. No duplicar el documento del piloto, decisiones de usuario ni ingestas en curso.
**No imponer WBS/BOQ a software u otras verticales.** Núcleo mínimo de proyecto+entidades+evidencia+versiones+riesgos+revisión+eventos, especialistas desacoplados.

## 2. Plazos objetivo y capacidades
- S0 17–20 nov 2026: diagnóstico + diseño y baseline.
- S1 23 nov–4 dic: robustez N3/N4/N12/N15; evaluación multiproveedor.
- S2 7–18 dic: N4 V2 ventanas/ledger/checkpoint/budget con feature flag en OFF; 8 dic festivo, capacidad reducida.
- S3 21 dic–8 ene: N12 crítico, N5/N9 y requisitos; Navidad y 1/6 ene reducen capacidad, no planificar producción crítica esas fechas.
- S4 11–22 ene 2027: vínculos cross-doc, ProjectGraph, Coherence/Health y HITL.
- S5 25 ene–5 feb: modos, panel, rendimiento y UAT; gate de aceptación final.
**Objetivos internos condicionados:** 18/12 MVP N4 probado aisladamente; 22/01 inteligencia multi-doc candidata; 05/02 UAT real. No compromiso de entrega. Esfuerzo preliminar 65–95 jornadas técnicas equivalentes en varias líneas paralelas; revisar a cierre de S0. La aprobación final de un humano autorizado y un posible bloqueo del piloto son dependencias externas.
**Capacidad supuesta para planificación:** Backend IA 1 línea principal, QA 1 línea independiente, Ops 0,3–0,5 capacidad, UX desde S4/S5, coordinación ligera. Los modelos son ejecutores auxiliares, no multiplicadores lineales de capacidad; algunas tareas no se paralelizan por migraciones/estados/PR.

## 3. Diccionario de responsables y modelos (PROPUESTO; verificar disponibilidad)
- **Adriana / AI Chief of Staff:** dirección de ejecución, dependencias, coste y riesgos. Modelo Sonnet diario; Opus solo para escalados de alto impacto (cuota verificada).
- **Atlas / revisor técnico independiente:** challenger de arquitectura y decisiones; GPT-6 Sol/Codex cuando el entorno lo permita. Nunca dar por hecha la sesión activa.
- **Alejandro / Backend AI:** contratos, Python/FastAPI, LangGraph, adapters, PostgreSQL. Asignar Codex/GPT Sol para código estructurado y Claude Sonnet para razonamiento/integ.; revisor independiente distinto del autor.
- **Elena / QA:** gold set, exactitud semántica, cobertura y E2E. Gemini para contraste, Sonnet/Sol para réplica; revisión experta humana de materialidad contractual y cálculos.
- **AI-GEN Ops:** infraestructura, secrets, trazas, limites por tenant, CI, rollback, piloto. Scripts y chequeos con modelos de menor coste si aporta.
- **UX Lead:** revisión de hallazgos y panel, modos y progreso; Codex para implementación, Sonnet para experiencia; Elena QA funcional.
- **Tándem CORE #1049:** única coordinación de despliegues y #1229; solo el propietario humano realiza aprobación final HITL.
- **DeepSeek Flash:** transformaciones repetitivas, pruebas no críticas, documentación; no árbitro único de seguridad, calidad ni producción.
Política: el modelo que escribió una implementación no puede ser su único revisor; usar par técnico+QA independiente. Atribuir modelos concretos solo tras comprobar configuración y cuota.

## 4. WBS por sprint
**Unidad de esfuerzo:** jornadas técnicas equivalentes (jTE) agregadas por tarea, rango de estimación; no son tiempo de CPU de agente ni días calendario. Cada tarea termina con enlace a commit/PR, tests y resultados — solo cuando se autorice ejecutar.

### S0 — diagnóstico, diseño y baseline (6 tareas; 7–11 jTE aprox.)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 0.1 | Alcance, límites y coordinación #1049/#1229 | 0,5–1 | — | Adriana / Sonnet | Plano de responsabilidades, veto a duplicidades, riesgos abiertos |
| 0.2 | Mapa real N1–N17 + ProjectGraph + HITL + ADR | 1,5–2 | 0.1 | Alejandro / Codex; Atlas challenger | Grafo y contratos con líneas de código y gaps |
| 0.3 | Medir llamadas LLM, reasoning, coste, p50/p95 y fallos | 1–2 | 0.2 | Ops / scripts + Sonnet | Línea base repetible por nodo/modelo, logs sin fuente/secretos |
| 0.4 | Gold set EPC y casos negativos, fuente/hashes | 1,5–2,5 | 0.1 | Elena / Gemini + experto | Tabla de hallazgos obligatorios/no hallazgos y reglas de evaluación |
| 0.5 | SDD/ADR: ledger, estados, API, N12/HITL y rollback | 1,5–2,5 | 0.2,0.4 | Adriana + Alejandro / Sonnet+Atlas | Diseño con CAS/RLS, migración y compatibilidad aceptable |
| 0.6 | Dependencia de aceptación piloto #1229, sin duplicar | 0,5–0,5 | 0.1 | Tándem CORE / sin LLM | Owner único de UAT y secuencia de aprobación humana |

### S1 — corregir defectos y normalizar proveedores (7 tareas; 10–16 jTE)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 1.1 | N3 `insufficient_extractable_text`, OCR pendiente, ruta válida | 1–1,5 | 0.2 | Alejandro / Codex | Repro test rojo→verde, sin caída de LangGraph |
| 1.2 | N4 tipar COMPLETE/PARTIAL/FAILED/UNASSESSED, 0 riesgos real | 2–3 | 0.5 | Alejandro / Codex | Errores y ausencia real no confundidos, API compat |
| 1.3 | Verificar citas y mapeo fuente original ANTES de HITL | 2–3 | 1.2 | Alejandro+Elena / Codex+Gemini | Verificación visible y citas no verificadas bien marcadas |
| 1.4 | N12 crítica focal, eliminar retry monolítico repetitivo | 1,5–2,5 | 0.3,1.2 | Alejandro / Sonnet | Solo recalcular alcance necesario; coste medido |
| 1.5 | PR #1234: equivalencia proveedor/schemas, reasoning y costes | 1,5–2,5 | 0.3 | Alejandro / Codex, Atlas Sol | Formatos y finish reasons equivalentes; opt-in, sin merge automático |
| 1.6 | Pruebas seguridad PII, RLS, errores parciales, rollback | 1–1,5 | 1.2,1.3 | Ops+Elena / Codex+Gemini | Cero regresiones tenant, priv. y controles |
| 1.7 | Benchmark comparable real sobre mismas cláusulas y fuente | 1–2 | 1.5,0.4 | Elena / Gemini+Sonnet/Sol | Recall/precisión preliminar y factura/coste identificable |

### S2 — N4 incremental (8 tareas; 15–23,5 jTE)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 2.1 | Inventario por sección, página, span y cobertura | 1,5–2,5 | 1.1,0.5 | Alejandro / Sonnet+Codex | 100% de unidades con estado y hash fuente |
| 2.2 | Esquema PG de ledger N4 y ventanas, provenance, RLS | 2,5–3,5 | 1.2,0.5 | Alejandro / Codex Sol | Migración reversible, tenant y revision fencing |
| 2.3 | Ventanas contextuales con referencias y excepciones cruzadas | 2–3 | 2.1 | Alejandro / Sonnet | No pérdida por bordes, sin top-N ni truncamiento |
| 2.4 | Respuestas compactas, normalizador tipado y evidencia referenciada | 1,5–2,5 | 2.2,1.5 | Alejandro / Codex | Límite de respuesta por unidad, no JSON monolítico |
| 2.5 | Checkpoints, reanudación, CAS e idempotencia | 2,5–3,5 | 2.2,2.3 | Alejandro+Ops / Codex | Corte antes/después de emisión y reinicio sin duplicación |
| 2.6 | BudgetLedger: request, run, doc, proyecto, tenant | 2–3,5 | 2.2,1.5 | Ops+Alejandro / Codex | Reserva atomizada, uso parcial y conciliación |
| 2.7 | N4 V2 integrado bajo feature flag OFF por defecto | 1,5–2,5 | 2.3–2.6 | Alejandro / Codex+Sonnet | Ruta piloto intacta con flag off, rollback probado |
| 2.8 | Ensayos contrato real completo, repeatability y gate | 1,5–2,5 | 2.7,0.4 | Elena+Ops / Gemini | 3 runs comparables y dictamen calidad/coste |

### S3 — calidad y especialidades documental (6 tareas; 10,5–16,5 jTE)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 3.1 | N12 crítica semántica focal, gold extendido | 2–3 | 2.8 | Elena+Alejandro / Gemini+Sonnet | Diagnóstico de falsos negativos y materialidad |
| 3.2 | N5 cronograma, WBS, hitos, dependencias, baseline | 2–3 | 2.1,0.5 | Alejandro / Codex | Fechas exactas, relaciones citadas y cobertura |
| 3.3 | N9 presupuesto XLSX/BOQ, unidades, sumas, moneda | 2–3 | 2.1,0.5 | Alejandro / Codex+Gemini | Conciliación de celdas, fórmulas y cálculos |
| 3.4 | Requisitos técnicos: extracción de pruebas/FAT/normas | 1,5–2,5 | 2.1,0.5 | Alejandro / Sonnet+Codex | Requisitos tipados con fuente literal |
| 3.5 | Documento/artefacto multi-formato con revisión y referencias | 1,5–2,5 | 3.2–3.4 | Alejandro+Ops / Codex | Entidades tipadas sin ruptura de lineage |
| 3.6 | Benchmark 4 documentos y casos adversariales | 1,5–2,5 | 3.1,3.5 | Elena / Gemini+Atlas Sol | Matriz multi-doc reproducible y NO-ASSESS donde aplique |

### S4 — inteligencia global, coherencia y HITL (7 tareas; 11,5–18,5 jTE)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 4.1 | N3 multidisciplina, fan-out/join correcto por elemento | 2–3 | 3.5 | Alejandro / Codex | N12 único tras fan-in, sin efectos duplicados |
| 4.2 | ProjectState: entidades y estados temporalizados | 2–3 | 3.5 | Alejandro / Sonnet+Codex | Observado/propuesto/validado separados |
| 4.3 | ProjectGraph alinea obligación-WBS-coste-requisito | 2–3 | 4.1,4.2 | Alejandro / Sonnet, Atlas challenger | Coherencia multi-doc en proyecto verdadero |
| 4.4 | Diff/Coherence/Health con línea base y dos valores | 1,5–2,5 | 4.3 | Alejandro+Elena / Codex+Gemini | Riesgo aceptado no infla score; UNKNOWN honesto |
| 4.5 | N11 recomendaciones e impactos, hechos vs hipótesis | 1–2 | 4.3 | Adriana+Alejandro / Sonnet/Opus | Paquete de decisión con justificación |
| 4.6 | HITL real por hallazgo y final separado, integración #1229 | 1,5–2,5 | 4.3,1.3,#1229 | UX+Alejandro+Elena / Codex | GET 200, ledger y final act de humano real |
| 4.7 | QA Tier-1/Tier-2/Clerk/PG/alertas y rendimiento | 1,5–2,5 | 4.4–4.6 | Elena+Ops / Gemini+Sol | E2E candidato, aislamiento, trazas |

### S5 — 3 modalidades, panel y UAT (6 tareas; 9–14 jTE)
| ID | Paquete | Esfuerzo jTE | Dep. | Responsable/modelo | DoD — evidencia de cierre |
|---|---|---:|---|---|---|
| 5.1 | Back-end Rápido/Completo/Auditoría con semántica de cobertura | 1,5–2,5 | 3.1,4.7 | Alejandro+Elena / Sonnet+Gemini | Rápido nunca equivale a exhaustivo |
| 5.2 | Selector UX, progreso, aviso de parcialidad y coste | 1,5–2,5 | 5.1 | UX / Codex+Sonnet | Selector, feedback, estados consistentes |
| 5.3 | Dashboard validado/provisional, riesgos, fuentes, acciones | 2–3 | 4.7,5.2 | UX / Codex+Gemini | Panel evidenciado, referencias navegables |
| 5.4 | UAT real: contrato, cronograma, presupuesto, especificaciones | 2–3 | 5.1,5.3,#1229 | Elena+Ops+CORE | S1–S8 + humano HITL + ProjectGraph/Health reales |
| 5.5 | P50/P95, coste/expediente, calidad, seguridad, regresión | 1–1,5 | 5.4 | Ops+Elena / Codex | Informe medido y repetibilidad |
| 5.6 | Acta GO/NO-GO, rollback y aprobación propietaria | 1–1,5 | 5.4,5.5 | Adriana/propietario | Puerta de release documentada |

**Ajuste de estimación:** la suma de rangos de paquetes es aprox. 62,5–99 jTE; se reserva planificación 65–95 jTE como *horquilla base provisional*, a reconciliar en S0 por capacidad y riesgos. No confundir suma de máximos independientes con coste esperado. Si las dependencias bloquean, replanificar calendario explícitamente.

## 5. Criterios de entrada/salida por sprint
- **S0→S1:** arquitectura mínima y baseline aprobables, gold inicial, propietario de #1229 identificado.
- **S1→S2:** N3 no rompe con texto insuficiente, N4 vacío/FAIL tipado, citas pre-HITL, providers medibles. Si no: no construir ledger aún.
- **S2→S3:** N4 incremental real sobre contrato con reanudación y ledger; presupuesto acotado; 3 runs; 0 resultados parciales «PASS».
- **S3→S4:** artefactos fiables de contrato, cronograma, presupuesto y requisitos; evidencia legible original; benchmark por separado.
- **S4→S5:** ProjectGraph real, Coherence observada/validada correctamente, candidate-bound HITL, no simulación humana.
- **S5→Release:** modos verificados, proyecto completo, S1–S8 real, humanos, presupuesto, seguridad y rollback. Si UAT falla: NO-GO e informe de gaps.

## 6. Política de presupuestos propuesta (NO habilitada en este plan)
Definir por separado cuotas mensuales de producto/agentes, consumo API y quota OAuth CLI (no equivale a coste cero). S0 mide tarifas reales y consumo de razonamiento por proveedor antes de fijar caps. Propuesta inicial de control para experimentos aislados: reserva por llamada; cupo por run y por documento; tope por tenant y periodo; pausa con PARTIAL/BLOCKED al agotarse (sin repetir costo). Cada corrida guarda spent/reserved, modelo y tokens incluyendo reasoning. Gastos piloto y cambios en producción sujetos a autorización operativa, no asumida por esta WBS.
La planificación de coste/latencia debe reportar €/expediente completo y coste/hallazgo confirmado, no coste por token aislado.

## 7. Riesgos y contingencias
| Riesgo | Señal temprana | Acción |
|---|---|---|
| #1229 persiste | Piloto sin candidato genuine/HITL | Tándem CORE resuelve camino piloto sin duplicar reupload; S4/S5 dependen |
| N4 windows omiten cláusulas conectadas | Gold adversarial falla | Contexto solapado, lookup focal; tools agénticas si valor probado |
| Sesiones/modelos no disponibles | OAuth/API/CLI fail | Proveedor alternativo, no prometer runner |
| N12 repite demasiada fuente | Input tokens > baseline | Crítica focal, pausa económica, límite de iteraciones |
| Migración RLS/ledger rompe revisión | Error de lineage, tenant | Migración reversible, flag off, pruebas de aislamiento |
| Hallazgos «literal» pero irrelevantes | Precisión baja ante experto | Calibrar gold de materialidad, review independiente |
| Nuevas verticales expanden alcance | N5/N9 cambian semántica core | Contratos plugin, diferir dominios fuera EPC |
| Festivos y capacidad agente | Sprint S3 degradado | Buffer Navidad, mover dependencias, priorizar QA y reproducibilidad |

## 8. Gobernanza
Cada tarea WBS tiene `todo|in_progress|blocked|review|done`, referencia PR/SHA, test en CI, evidencia de proveedor REAL si aplica, consumo, bloqueos y owner. Estado DONE exige aceptación de Elena y evidencia; no basta «test unit PASS».
Daily operativa ligera asíncrona en #1049, revisión de sprint con Adriana y Elena, decisión GO/NO-GO con propietario en gates. Cambios de scope se estiman antes de integrarse; no crear decenas de issues hasta que plan esté aprobado.
**Documento planificado, no ejecutado.** No autoriza crear migraciones, desplegar, provisionar agentes ni consumir APIs.
