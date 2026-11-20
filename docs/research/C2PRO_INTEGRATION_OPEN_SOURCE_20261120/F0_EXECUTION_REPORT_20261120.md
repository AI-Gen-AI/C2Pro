# F0 — Primeras ejecuciones reales de integración OSS (2026-11-20)

**Iniciativa:** investigación C2Pro híbrido, separada de UAT. **Autoridad:** GO explícito del propietario para actuar en el PC administrado. **Ámbito:** experimentos sintéticos aislados, sin producción. **No es aprobación de arquitectura.**

## Entorno operativo
- Equipo Windows conectado mediante canal administrativo de AI-GEN Ops (comprobado; canal ordinario `pcops_status` indicó `pc_remote_unavailable`, pero `pcops_admin_status` y `pcops_admin_exec` funcionaron).
- Carpeta de pruebas: `%LOCALAPPDATA%\AI-GEN\C2ProOSSResearch20261120`, con `scripts/`, `fixtures/`, `results/`, `logs/`, `models/`.
- Entornos virtuales **separados** `.venv` (MPXJ) y `.venv-docling` (Docling). Python 3.11.9; Java 25; Windows.
- Bibliotecas efectivamente instaladas en entornos aislados: MPXJ 16.10.0, JPype1 1.7.1, Docling 2.151.1, ReportLab 5.1.0.
- Docling descargó pesos públicos para ejecutar localmente; **no** hubo llamadas de inferencia comercial de pago ni envío de contratos de clientes. Los únicos documentos de entrada fueron generados sintéticamente.

## Ejecuciones verificadas

| Ensayo | Resultado | Evidencia | Qué demuestra |
|---|---|---|---|
| MPXJ synthetic schedule | **PASS** | [JSON](evidence/mpxj_smoke_result.json) · [script](spikes/mpxj_synthetic_roundtrip.py) | Generación y relectura de MSPDI/XML y XER con 4 tareas y 2 dependencias preservadas en ambas representaciones |
| Docling digital contract+annex | **PASS** | [JSON](evidence/docling_smoke_result.json) · [script](spikes/docling_synthetic_pdf.py) · [contrato parseado](evidence/synthetic_contract_docling.md) · [anexo parseado](evidence/synthetic_annex_docling.md) | 2 PDF digitales convertidos, 2+1 páginas, recuperación de términos esperados y 1 tabla en anexo |
| Comprobación literal contrato/anexo | **PASS (solo fixture)** | [JSON](evidence/cross_document_candidate_result.json) · [script](spikes/cross_document_fixture_check.py) | Identificación de 2 diferencias **sembradas**: FAT 21 días más tarde y oferta +80.000 EUR, con referencias a fragmentos Markdown |

### Medición local de Docling
- PDF de contrato de dos páginas: **118,859 s** con carga inicial/descarga/preparación de modelos.
- PDF de anexo de una página: **4,094 s** con motor preparado.
- No inferir SLA ni latencia general de Docling a partir de estas 2 observaciones; no existe comparación contra parser de C2Pro.

### Salidas de discrepancia: frontera de confianza
- `FAT_DATE_CONTRADICTION`: 30 mayo 2027 (contrato) vs 20 junio 2027 (anexo), 21 días.
- `BUDGET_OFFER_CONTRADICTION`: 950.000 EUR (límite) vs 1.030.000 EUR (oferta), +80.000 EUR.
- **Estado de ambas:** `CANDIDATE_UNVALIDATED`, sin aprobación humana, sin escritura a ProjectGraph ni persistencia productiva, sin Alerts, sin cambio de Coherence Score.
- Los spans del detector apuntan a posiciones en Markdown, **no** a coordenadas/páginas del PDF original. La correspondencia visual inversa aún es una pregunta abierta.

## Incidencias encontradas y resueltas
1. La instalación base de MPXJ en Python no aportó JPype automáticamente: fue necesario instalar JPype1 en el mismo entorno virtual.
2. Ejemplo histórico de MPXJ usaba `Relation.Builder().targetTask(...)`; MPXJ 16.10.0 expone `predecessorTask(...)` y `successorTask(...)`. Se corrigió el script en rama y se ejecutó PASS.
3. Java 25 produce advertencia de acceso nativo JPype; no bloqueó el ensayo. Requiere validar compatibilidad de Java/flags cuando se diseñe empaquetado.
4. PowerShell remoto trata mensajes en stderr como errores: para Docling se separó stdout/stderr usando un proceso supervisado con redirección.
5. El primer PDF requirió descarga/carga de modelos y superó el límite de respuesta remoto; el proceso continuó, se verificó finalización y el resultado final se leyó después de completarse.

## Lo que NO está demostrado
- No existe benchmark de calidad contractual sobre contratos EPC reales ni contra N4/N12.
- No se han probado XER/MPP/Asta auténticos, calendarios complejos, baselines, zonas horarias, relaciones múltiples, fechas tempranas/tardías o critical path. MPXJ fue un **round-trip de datos generados por sí mismo**.
- No se ha evaluado OCR de PDF escaneado ni fidelidad de bounding boxes/páginas frente al origen.
- La comprobación textual de 2 anomalías es una **regex creada para el ejemplo**, no motor generalizable y no valida la semántica jurídica.
- No hay integración real con APIs de C2Pro, HITL, ProjectGraph, Health/Coherence/Alerts, ni ERP/BOM/RFQ de terceros.
- No se han instalado OpenContracts, ERPNext, InvenTree ni LangExtract: esos productos siguen siendo candidatos, no componentes operativos.

## Decisión técnica sugerida después de F0
**PASS limitado para continuar investigación de adaptadores aislados; NO-GO todavía para integración productiva o sustitución N4/N12.**

### Siguiente puerta de validación
1. QA independiente del alcance de estos resultados y de los contratos de procedencia.
2. Conseguir 1–2 archivos de planificación XER/PMXML/MPP representativos y legalmente utilizables; medir preservación contra un oráculo de actividades, WBS, relaciones, calendarios y baselines.
3. Comparar Docling con el parser actual de C2Pro usando **mismo contrato con anexos**, métricas de tablas, páginas, citas y omisiones, sin procesar materiales confidenciales en servicios externos.
4. Solo después, ensayar LangExtract frente a N4/N12 con oráculo independiente y presupuesto de inferencia acotado.
5. Ninguna promoción `pending`→`trusted` sin el circuito aprobado de evaluación, HITL y evidencia.

**Rama exclusiva:** `research/c2pro-integration-open-source-20261120`. No se han realizado merges ni despliegues.
