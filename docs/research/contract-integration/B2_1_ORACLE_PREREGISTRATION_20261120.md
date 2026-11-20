# B2.1 — Prerregistro antes de comparar N4 v2 con LangExtract

Fecha: 20/11/2026. Rama experimental `research/c2pro-docling-contract-integration-20261120`. **No es un gold standard experto**.

- Origen único: SEC Longfellow EPC HTML, SHA-256 de proyección `b4009aee679ebef7c81c07446a897ad5f9b7e8c224db7f0156f6a7967af99044`.
- Oráculo provisional conservado **solo en VPS**, hash SHA-256 del JSON: `3eee6ee765dd04bf7ddab754662a78c5c3466eaed03b1688cd3099b404c01bd3`. Contiene **13 raíces** creadas leyendo directamente la fuente sin utilizar las respuestas de los modelos. Se congela **antes** de la inferencia N4 v2.
- Cobertura: obligaciones o derechos de penalización por retraso (raíz, importes y cap como atributos), cambios de plazo y aprobación, reporte mensual, RFI Log, materiales peligrosos, subcontratación, seguridad, personal cualificado, planes de seguridad, emergencias y acceso.
- Regla de granularidad: una obligación/derecho autónomo puede llevar varias condiciones, tarifas, importes y topes anidados; una cláusula puede contener varias raíces. Los anexos faltantes se consideran referencias abiertas, no aprobación bloqueada.
- **Advertencia:** estos 13 ejemplos no son una anotación completa de todos los hechos de ambas ventanas. **No permiten medir recall global**. Tampoco hay experto EPC independiente que haya ratificado sus límites y agrupaciones; cualquier cobertura respecto a estos 13 es una comprobación exploratoria.
- Comparación N4 v2 propuesta: mismo `nvidia/nemotron-3.5-bolt-e4b`, misma proyección SEC, las mismas ventanas C2Pro 7/8 (SHA `916808c5`), mismos ocho fragmentos nativos LangExtract (4k y contexto previo de 400 caracteres), una pasada sin ejemplo frente a una pasada LangExtract con few-shot (configuración diferente, deliberada); presupuesto de salida no superior a 3072 tokens por llamada.
- Gate de aceptación: registrar JSON válido, gasto en tokens, solo citas **exactamente presentes** en proyección y raíz contractual. No atribuir página física del PDF, certeza jurídica, N12 o ProjectGraph. Evitar *denominador 13 = recall universal* y no mezclar hechos fuente con aprobaciones.
- Comparación de coste limitada a tokens y tiempos; precio monetario de NVIDIA no atestado.
