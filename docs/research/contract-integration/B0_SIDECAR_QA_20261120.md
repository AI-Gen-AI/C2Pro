# B0 — Segunda QA sobre código real de sidecar/bridge (20/11/2026)

**Revisor:** Gemini AI-GEN Ops, job `3c8226e29e1864949202a3f8f529d255`, revisión read-only sobre SHA exacta `e0570af1f9f8bfc13740f702d072a09c7237ecb8`.  
**Dictamen:** PASS_LIMITED **solo para investigación B0**, NO para habilitar N4/N12 ni producción.

## Qué se revisó realmente
- Se leyeron `docling_optional_table_sidecar.py`, `docling_n4_source_bridge.py`, informe B0 y JSON de la ejecución pública SEC de 74 páginas.
- Los dos ficheros de pruebas unitarias **existían pero no fueron leídos** por el agente. Los 6/6 y 7/7 PASS fueron ejecutados por CORE y verificados en el PC autorizado, no repetidos por Gemini.
- La auditoría anterior fijada a SHA `ffa69828...` **no podía revisar** el sidecar, ya que fue añadido después. No utilizar aquel dictamen como auditoría del sidecar.

## Resultado contrastado
- Mantener **texto completo obtenido por PDFFileParser** y permitir Docling como sidecar `ADVISORY_UNVERIFIED` evita reemplazo silencioso cuando el orden de Docling es incompleto.
- El puente a N4 exige proyección N2 exactamente equivalente a los offsets Docling o bloquea; no se ha implementado aún el remapeo bajo redacción PII.
- El A/B sobre documento SEC **derivado** de 74 páginas demuestra fallo de integración directa Docling por `reading_order` incompleto, no que Docling haya perdido irremediablemente sus textos crudos.
- **No se ha invocado N4 ni N12** ni validado resultados de riesgos contractuales, costes, fechas, contrato original firmado o cumplimiento.
- **El sidecar nuevo solo cuenta con pruebas in-memory**, NO ensayo completo Docling+legacy del PDF de 74 páginas end-to-end.

## Precauciones adicionales de CORE
- El sidecar recibe `baseline_blocks` y `physical_pdf_sha256` por separado: **el hash de esos bloques no acredita por sí solo que procedan de los bytes del PDF**, salvo que los produzca un servicio de ingesta/revisión autorizado y vinculado transaccionalmente al mismo documento. Este vínculo es imprescindible antes de producción.
- El resultado devuelve `baseline_text` completo en memoria; está destinado solo al pipeline autorizado. Debe impedirse su serialización en telemetría, logs, UI o sistemas ajenos a permisos de tenant, especialmente si contiene información confidencial.
- La falta de orden Docling completo NO impide el sidecar parcial, siempre que las tablas se mantengan como evidencia advisory, no alteren N4 y su cobertura se haga visible.

**Decisión:** conservar este resultado como evidencia de diseño B0. Siguiente paso útil: integración aislada del sidecar contra un PDF nativo conocido con revisiones autorizadas y prueba de tabla/cita/page original; después oráculo N4 vs LangExtract con mismo texto, modelo, presupuesto y baseline.
