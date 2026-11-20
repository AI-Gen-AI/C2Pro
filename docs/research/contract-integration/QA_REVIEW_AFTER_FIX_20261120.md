# QA contractual independiente — segunda revisión

**Fecha:** 20/11/2026. **Dictamen:** PASS_LIMITED para preparación estructural de la entrada de N4; **NO GO** todavía para invocación N4/N12 ni promoción de riesgos. Gemini AI-GEN Ops job c958360504c426d2c176abd8d5579929, revisión en ref SHA 4b702709beb5f9351a9d73e30f97bd49cf4c8a1e. Solo lectura.

## Correcciones verificadas (4/4)
1. **Orden intercalado de párrafos y tablas:** PASS — document.iterate_items y self_ref nativos, reading_order explícito.
2. **Matriz de filas/columnas:** PASS — proyección 2D, saltos de línea y separación de columnas.
3. **Procedencia multipágina:** PASS — conserva todas las páginas, no solo la primera.
4. **Fragmentación al límite:** PASS — retroceso a separador; falla de forma explícita si un único token es demasiado grande, sin cortes silenciosos en identificadores o importes.

Pruebas observadas por CORE: **22/22 unitarias PASS** y smoke real Docling sintético con contrato PDF 2 páginas + anexo PDF con tabla **PASS**. Ninguna llamada de N4/N12; ninguna modificación de UAT, ProjectGraph, HITL o Score.

## Cuatro riesgos residuales antes de conectar a N4
- **Parcialidad, no todo o nada:** si Docling omite una línea de su reading_order, hoy se rechaza el paquete completo; sustituir por salida parcial utilizable con cobertura y elementos no anclados claramente indicados (no ocultar omisiones).
- **Ventanas sin contexto compartido:** la continuidad literal de caracteres no asegura comprensión semántica entre cláusulas y definiciones de ventanas adyacentes. Diseñar contexto de solapamiento *sin duplicar hallazgos o alterar conteos de cobertura*.
- **Tablas con celdas fusionadas:** un conflicto de coordenadas actualmente aborta; preservar tabla original y marcar celdas/filas `UNASSESSABLE` para revisión en vez de descartar contrato completo.
- **Lectura visual de columnas:** separadores sin alineación pueden deteriorar correspondencia entre cabeceras e importes. Evaluar estructura de celdas JSON con IDs de fila/columna antes de serializar; no confiar únicamente en texto plano.

## Gate C-03
Crear un puente *opt-in* que lleve páginas, tablas, provenance y cobertura a la interfaz actual de N4/N12, sin falsificar attestation original ni convertir riesgos candidatos en trusted. Validar contra baseline de parser actual con mismo corpus + oráculo experto de obligaciones/riesgos, métricas de falsos positivos, omisiones críticas y citas; no dar por aprobado un contrato por poder leer su PDF.

**Conclusión:** cuatro bugs de QA inicial solventados, pero utilidad contractual todavía sin demostrar. No activar en producción.
