# Matriz inicial de candidatos — investigación, no selección

**Método:** fuentes primarias declaradas en Radar 2026-11-20 y repositorios GitHub / fichas Hugging Face consultados. Licencia referida al repo principal o ficha de modelo; requiere examen de dependencias, datos y términos comerciales. No se ha instalado ni comparado rendimiento sobre C2Pro.

| Capa | Candidato | Fuente verificable | Licencia declarada | Hipótesis y riesgo | Orden |
| --- | --- | --- | --- | --- | --- |
| Anotación/grafo documental | OpenContracts | https://github.com/Open-Source-Legal/OpenContracts | MIT | GraphQL/REST/MCP, extracción y anotaciones; posible duplicación de ProjectGraph/HITL | P0 evaluar |
| Parsing documento | Docling | https://github.com/docling-project/docling | MIT (modelos aparte) | PDF y estructura/tablas con anclajes; integración con parser actual | P0 evaluar |
| Extracción con grounding | LangExtract | https://github.com/google/langextract | Apache-2.0 | Source spans, schema, ventanas; depende de LLM, falsos positivos | P0 evaluar |
| Parsing alternativo | Unstructured | https://github.com/Unstructured-IO/unstructured | Apache-2.0 | Alternativa ETL; solapamiento con Docling | P1 |
| Conversión sencilla | MarkItDown | https://github.com/microsoft/markitdown | MIT | Baseline económica; potencial pérdida de layout | P1 |
| Modelo de documentos | Granite-Docling-258M | https://huggingface.co/ibm-granite/granite-docling-258M | Apache-2.0 | OCR/estructura, no análisis contractual | P1 |
| Datos de oráculo | CUAD | https://huggingface.co/datasets/theatticusproject/cuad | CC BY-4.0 | Benchmark de cláusulas en inglés, no EPC; verificar derechos y anotaciones | P1 |
| Retrieval contractual | LegalBench-RAG | https://huggingface.co/datasets/awinml/legalbench-rag | other | Span retrieval; licencias mixtas; no asumir reutilización comercial | P2 |
| Reranker contractual | CUAD cross-encoder v11 | https://huggingface.co/datgacon/cuad-cross-encoder-v11 | Apache-2.0 | Reranking no razonamiento legal; benchmark específico | P2 |
| Modelo contractual pequeño | ClauseLM 3B | https://huggingface.co/Z-Nadjib/Llama-3.2-3B-ClauseLM | Llama 3.2 | Poca evidencia independiente; no baseline principal | OBSERVAR |
| Planificación profesional | MPXJ | https://github.com/joniles/mpxj | LGPL 2.1 | MPP/XER/PMXML/Asta; asegurar fidelidad de calendario/baselines y servicio Java | P0 evaluar |
| IFC/BIM | IfcOpenShell/IfcTester | https://github.com/IfcOpenShell/IfcOpenShell | LGPL-3.0 principal | Relación requisito IFC/BOM; solo donde exista fuente IFC | P2 |
| ERP/Sourcing completo | ERPNext | https://github.com/frappe/erpnext | GPL-3.0 | RFQ→PO→factura, integración API; no incrustar código GPL sin revisión | P1 evaluar |
| BOM/Inventario | InvenTree | https://github.com/inventree/InvenTree | MIT | BOM, proveedor e inventario; distinto de sourcing EPC | P1 evaluar |
| Plan de proyecto | OpenProject | https://github.com/opf/openproject | GPL-3.0 | PMO/tareas/Gantt; mejor referencia que dependencia núcleo | P2 |
| Pipeline IA | Haystack | https://github.com/deepset-ai/haystack | Apache-2.0 | Componentes de recuperación/flujo; posible duplicación de runtime actual | P2 |
| Indexación/conectores | LlamaIndex | https://github.com/run-llama/llama_index | MIT | Conectores útiles, no reemplazo Coherence Engine | P2 |
| Knowledge retrieval | Microsoft GraphRAG | https://github.com/microsoft/graphrag | MIT | Grafo para búsqueda, no trusted ProjectGraph | OBSERVAR |
| MCP externo | Python MCP SDK | https://github.com/modelcontextprotocol/python-sdk | MIT | API C2Pro read-only para Claude/ChatGPT, versionado y auth | P1 diseño |
| Runtime/data jobs | Prefect | https://github.com/PrefectHQ/prefect | Apache-2.0 | Solo comparar si se prueba carencia del sistema actual | P3 |

## Candidatos comerciales ya registrados en Radar
- **#36 Ironclad:** CLM/metadata, API; términos de uso y comercialización a revisar.
- **#117 Asta Powerproject:** contract-to-schedule; el importador MPXJ puede permitir evaluación sin licencia nueva.
- **#118 Innova Suppliers:** SRM/qualificación; no reimplementar completo.
- **#120 SAP Fieldglass:** servicios/SOW/aceptación/factura.
- **#121 Supabase app-scoped MCP:** conexión potencial a asistentes con RLS; no asumir autorización de negocio.
- **#123 Zip:** procurement industrial; pendientes de validar APIs y demo.
- **#125 Samsung SDS Caidentia:** Design-to-Source; endpoint/documentación pública específica pendiente.
- **#127 Archlet:** sourcing CAPEX/MRO, escenarios adjudicación; comparar con lógica exclusiva de evidencia C2Pro.
- **#133 Mandel AI:** supplier coordination email/ERP/PO/factura; términos y evidencia pendientes.
- **#147 Beroe MAX:** procurement decision intelligence; competencia conceptual a comprobar.
- **Fuera del Radar o a vincular:** Icertis, Document Crunch, Procore, Oracle Primavera, Autodesk Forma. No crear duplicados sin consultar la hoja canónica.

Radar canónico: https://docs.google.com/spreadsheets/d/1bNf7JVuk5o4HY6WMAhGl-CrTupZc5gJJdKMVnFJ5JQM/edit?gid=211126696#gid=211126696

## Descartes iniciales condicionados
- No implantar suites ERP/CLM enteras como condición para MVP.
- No asumir licencias comerciales por ser "open source" ni reutilización legal de modelos/datasets.
- No evaluar solo mediante estrellas, pruebas unitarias o demos del proveedor.
- No adoptar GraphRAG como sistema canónico de proyectos.
