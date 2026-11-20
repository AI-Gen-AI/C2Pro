# C2Pro · VS-2 — Extracción contractual tipada y evidencia multicláusula (POC)

**Estado:** experimento aislado · sin integración en N4 productivo · sin fusión ni despliegue · sin inferencia facturable.  
**Base:** PR #1276, SHA `916808c5212e3dbc652407f35f3a17557623c06c`.  
**Independencia:** VS-1/PR #1279 continúa siendo la mejora de visibilidad ya probada en navegador; no mezclar la aprobación de VS-1 con la calidad de VS-2.

## Problema demostrado

La evaluación offline del SolarMax público de 94 páginas mostró que el N4 histórico podía mencionar correctamente condiciones contractuales **en su interpretación** pero guardar una cita que no demostraba su contenido material:

- §2.5.5: tarifas de 5.000/10.000/20.000 USD/día, límite [5]%, excepciones Owner/Utility;
- §9.6: contradicción literal «ten percent (5%)», desmovilización hasta 2% y otra limitación;
- §2.5.1 / §3.2.1: hitos y pagos asociados a anexos C/D no aportados;
- §12.1.1, §14.14.1, §4.3.1 y artículo 13: cobertura parcial u omisiones directas.

Los 15 riesgos históricos con citas localizadas en texto N2 **no** equivalen a 15 decisiones contractuales correctas. N12 mantuvo `UNASSESSED`.

## Hipótesis focal

Separar **hecho** de **riesgo** y citar de forma independiente *base, importe, condición, excepción, límite, contradicción o referencia* puede mejorar la auditabilidad y reducir conclusiones no sustentadas, **sin migrar a PydanticAI, LangChain ni LlamaIndex**.

El experimento `apps/api/src/analysis/domain/n4_typed_evidence_v2.py` implementa:
- esquema tipado Pydantic v2 de `fact` (obligación, hito, garantía, penalización, pago, exclusión, responsabilidad, terminación, seguros, confidencialidad u otro) y `risk` con referencias explícitas a hechos de la misma ventana;
- citas contiguas **individuales** con roles; solo una coincidencia exacta no ambigua obtiene `EXACT_MODEL_SAFE_MATCH` y offsets de la proyección N2;
- citas falsas/no únicas conservadas solo como hash y estado no verificado, sin mostrar texto como si fuese evidencia literal;
- importe explícito visible solo cuando aparece en una cita realmente localizada; no inferir el valor ante términos contradictorios;
- anexos faltantes conservados como `outstanding_references`: no certificar cobertura total; hechos sin alerta, Score o aprobaciones;
- identidad de documento, revisión, hash N2 y offset en cada referencia; **página del PDF ORIGINAL siempre `UNVERIFIED`** hasta reconstruir mapa N2→parser→PDF;
- envolvente estricta que rechaza campos imprevistos, salida malformada, links a hechos inexistentes y excesos de citas, sin reintentos automáticos ni llamadas al proveedor.

## Lo que esta PR NO hace

**No está conectado al runner, al grafo, a la BD, a la UI ni a N12.** No se puede activar el prompt v2 mediante una variable de entorno: cualquier integración requiere separar hechos de riesgos también en la persistencia y evitar que hechos se conviertan en alertas por defecto.

Tampoco resuelve las referencias entre documentos, la procedencia a la página del PDF original ni la calidad semántica del modelo. El máximo de 2.048 tokens de salida actual puede truncar JSON con más evidencia; aumentar el límite obliga a recalcular el peor coste por ventana, escrow y reserva antes de habilitar nada.

## Secuencia de aceptación mínima

1. **Sin coste:** pruebas unitarias con fragmentos tipo SolarMax: varios importes y condiciones en citas separadas, contradicción sin escoger cifra, dependencia de anexo faltante, offsets de N2 y rechazo de afirmaciones no localizadas. Ejecutar regresión de N4 v1 sin cambios.
2. **Prueba de modelo local exploratoria (no aceptable como QA productiva):** una petición sin retry a Ollama sobre §2.5.5 del PDF de 94 páginas. Medir validez del esquema y presencia de las tres tarifas, tope y excepciones respaldados por citas exactas, sin logs de texto contractual. Fallo de Qwen 4B no prueba que otro modelo falle; éxito tampoco valida el producto.
3. **Evaluación comparada con proveedor autorizado (NO EJECUTAR TODAVÍA):** V0 existente frente a v2 y, después, v2 con referencias previamente resueltas. Igual modelo, mismas seis ventanas públicas, un máximo de una llamada por variante/ventana, sin retry, escrow global verificado, oráculo humano independiente. El presupuesto y la autorización específica siguen pendientes.
4. **Integración posterior, solo con evidencia favorable:** guardar hechos sin promoción HITL/Score, mantener riesgo propuesto con referencias a hechos y a citas, exigir QA de tenant/fencing/revisión, gestión de truncación y trazabilidad PDF real. Promociones y merges separados, no automáticos.

**Criterio de decisión:** no elegir v2 por un JSON estructurado ni por tests verdes; debe identificar más elementos materiales que v1 con respaldo literal fiable, y sin aumentar omisiones críticas o coste fuera de tope. En caso contrario, rechazarlo o reducirlo. No construir un agente autónomo para N4 hasta probar necesidad real.

## Evidencia de ejecución (20/11/2026)

- `66 passed, 1 warning` en 5,90 s con Python 3.11, sobre SHA `402d7c231321dc716d6621fd3f06b63a355ed213`: incluye nueva suite VS-2 y regresiones v1. Advertencia de reescritura de `tests._bootstrap`, sin fallos.
- **Piloto Qwen local (página 36 del PDF SolarMax de 94 páginas): FAIL/TIMEOUT**. Única solicitud a `http://127.0.0.1:11434/api/chat`, modelo `qwen3:4b-instruct`, ventana con §2.5.5 y las tarifas $5.000/$10.000/$20.000, `num_predict=1700`, `num_ctx=8192`, `temperature=0`; `TimeoutError` sin respuesta tras 265,1 s. **Sin reintentos**, gasto de proveedor externo **0 €**. Informe restringido `/home/aigenadmin/qa_evidence/solarmax-real-pdf-20261110/vs2_local_ollama_qwen4b_p36_20261120.json`, SHA256 `b44d81deebb26b53cd8a98507c8dec57fd995d5f858bf3f183dd92b73eba7069`.
- Un timeout **no permite calcular** recall, precisión, cobertura de citas ni validez de salida v2. Qwen local no es un sustituto válido del proveedor de producción en esta configuración. No ejecutar otra llamada local automática ni considerar que esto demuestra una mejora de v2 frente a v1.
- Los 66 PASS **sí** prueban reglas de validación y no-regresión; no prueban que un modelo rellene correctamente las estructuras.

## Límites de autoridad

**`N4_BILLABLE=STOP` · `N12_BILLABLE=STOP` · `MERGE=STOP` · `UAT_DEPLOY=STOP`.** Esta rama no solicita alterar esos controles. El análisis histórico completo permanece en el expediente de QA y el reporte focal en `docs/audits/C2PRO_FG1_SOLARMAX_REAL_CONTRACT_OFFLINE_REPLAY_2026-11-20.md` de la PR #1279.

## Requisito funcional de producto no negociable — generalista ES/EN

**Decisión del propietario (20/11/2026):** C2Pro no es un extractor específico para SolarMax ni para EPC en inglés. El núcleo N4 debe entender y analizar contratos de diferente naturaleza y estar validado para **español e inglés desde la primera aceptación funcional**. Esta decisión corrige el sesgo del POC actual.

### Auditoría del estado del POC

- El prompt experimental actual empieza por «You research EPC contracts» y los ejemplos y tests proceden esencialmente de un contrato EPC estadounidense en inglés. **Esto no demuestra soporte para español ni generalización contractual.**
- La unión Pydantic `fact/risk` es una estructura técnica reutilizable, pero `FactKind` y el vocabulario de riesgos no constituyen aún una ontología completa para servicios, suministro, obras, compras, MSA, O&M, NDA ni otros documentos.
- Una instrucción en inglés puede procesar texto español dependiendo del modelo; **capacidad probable no es cobertura verificada**. No proclamar «multilingüe» ni «multi-contrato» con los tests actuales.
- VS-2 está desconectado de N4 runtime, N12, DB, ProjectGraph y anexos; no es una función disponible para usuarios.

### Requisitos de diseño para la siguiente iteración, antes de promover VS-2

1. **Núcleo contractual agnóstico:** extraer *hechos verificables, obligaciones, derechos, partes, disparadores, plazos, importes, condiciones, exclusiones, contradicciones, riesgos propuestos y referencias a anexos* independientemente del sector. Contrato y subcategoría son metadatos con `unknown` permitido, no filtros que omitan cláusulas. Perfiles EPC, suministro, servicios/O&M, obras/subcontratación, acuerdos marco o confidencialidad amplían preguntas y prioridades, **nunca recortan el barrido exhaustivo**.
2. **Idiomas obligatorios:** EN y ES, incluso contratos que mezclen ambas lenguas. Conservar **cita literal en idioma original** + hash, offsets y futura página; explicación/lectura de interfaz separada en idioma solicitado (ES/EN), con cautela ante términos jurídicos no equivalentes. No traducir una cita y después etiquetarla «literal». Normalizar cifras, separadores, moneda, fechas y duración con conservación del valor bruto y su jurisdicción/contexto; no inferir semántica legal por traducción.
3. **Corpus de aceptación cruzada:** al menos EPC/obra, suministro/compraventa, servicios/O&M y acuerdo marco o subcontratación, en **ambos idiomas**, con documentos independientes *held-out* y uno mixto. Los anexos presupuestos, cronogramas, especificaciones y garantías se evalúan por procedencia y referencia al documento exacto; si faltan, alcance `UNASSESSED/PARTIAL` en lugar de completar datos. Incluir casos con LD, SLA, Incoterms, responsabilidad, fuerza mayor, confidencialidad, renovación, rescisión, penalizaciones, garantías y protección de datos según proceda.
4. **Medición de calidad, no solo validación JSON:** oráculo externo por tipo contractual e idioma para omisión material, precision/recall por elementos tipados, evidencia literal, citas originales/página, valor/fecha/parte correctos, contradicciones, abstención ante anexos ausentes, coste y tasa de truncación. Una matriz 4×2 **no significa 8 contratos suficientes para aceptación estadística**: definir tamaño/umbrales por riesgo y adjudicar omisiones críticas individualmente.
5. **Seguridad y límites:** N2 preserva identidad y la extracción cubre todas las ventanas, sin depender solo de RAG. Ningún hecho se promociona a riesgo aprobado, Score, alertas o ProjectGraph sin reglas posteriores y validación. `N4_BILLABLE=STOP`, `MERGE=STOP`, `UAT_DEPLOY=STOP` hasta los gates necesarios.

**Estado del requisito:** especificado, **NO IMPLEMENTADO / NO VALIDADO**. No modificar el runtime ni proclamar que VS-2 supera esta nueva condición hasta evaluación independiente.
