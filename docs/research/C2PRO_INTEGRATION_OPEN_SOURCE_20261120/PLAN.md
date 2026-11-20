# Plan de investigación y propuesta técnica — C2Pro Integration & Open Source

## Objetivo de negocio
Validar si C2Pro puede convertirse en una **Coherence Intelligence Layer** para EPC/ETO: correlacionar obligaciones contractuales y sus anexos con cronogramas, presupuesto, BOQ/BOM, especificaciones, RFQ/ofertas/PO, responsabilidad RACI y comunicaciones. Distinguir datos extraídos, inferencias, contradicciones, impactos y decisiones validadas. Comparar con el camino de desarrollo propio.

## Principios de diseño
1. **Usuario primero:** un director de proyecto debe ver una incoherencia material con prueba y acción posible, no seis resúmenes. 
2. **Evidencia de origen:** cada hallazgo debe enlazar documento/versión/página/fragmento/campo y señalar la cobertura realmente examinada. No afirmar revisión completa si no la hubo.
3. **Separación de estados:** candidatos o resultados parciales no son aprobables ni entran en ProjectGraph trusted/Score validado. Incertidumbre explícita. Aprobar un riesgo no equivale a mitigarlo.
4. **Modelo canónico propio:** UUID estable, tenant, proyecto, source-hash, revision/validity, objeto de negocio, tipo de relación, trazabilidad causal, estado de revisión, flags de ausencia.
5. **Adaptadores intercambiables:** conectar producto comercial, OSS o archivo exportado sin que el proveedor sea autoridad del estado del proyecto.
6. **No reimplementar ERP/planificador/CLM sin ventaja demostrable.**
7. **Coste y licencia:** evitar decisiones por popularidad/stars; diferenciar OSS del código, licencia de modelos y datos, TCO de servicio y términos API.

## WP0 — Baseline factual y evaluación comparativa (Planner, Backend/QA, 1er gate)
- Leer estado en rama UAT funcional actual y principales ADR/ProjectGraph/Coherence Score/ingesta/N4-N12, sin editarla.
- Registrar módulos que ya existen, placeholders y limitaciones: ejemplo en `apps/api/src/procurement/application/integration_service.py`: snapshot de demostración, persistencias con listas vacías en main observado. Validar si existe sustitución actual en otra rama.
- Congelar un corpus sintético EPC completo (contrato + anexos + especificaciones + presupuesto BOQ + cronograma XER/MPP + BOM + RFQ/ofertas + responsables); opcional corpus real con derechos explícitos.
- Oráculo independiente: hallazgos críticos sembrados, falsos positivos, obligaciones omitidas, relaciones implícitas y cambios de versión.
- **DoD:** inventario de realidad y fuentes SHA, dataset identificado con permiso, catálogo de hallazgos esperados, métricas y umbrales provisionales.

## WP1 — Document Intelligence y análisis contractual (QA/AI/Backend)
- Comparar ingesta actual vs Docling, Unstructured, MarkItDown y, donde corresponda, Granite-Docling local.
- Comparar extracción de citas/hechos/obligaciones/riesgos N4/N12 vs LangExtract (o OpenContracts como motor de extracción y anotación), con el MISMO corpus, misma taxonomía de salida, presupuesto medido y revisión independiente.
- Probar cobertura de ventanas, tablas anexas, cláusulas transversales, referencias cruzadas, revisiones, source spans, duplicados y contradicciones.
- OpenContracts debe evaluarse como servicio de anotación/document graph, **sin convertir su grafo en autoridad paralela a ProjectGraph**.
- **DoD:** precision/recall por severidad y dominio, omisiones documentadas, anclajes verificables, coste y recomendación de motor.
- **Gate:** no elegir sustituto de N4/N12 sin resultado superior o complementario demostrado.

## WP2 — Planificación/costes/ingeniería (Backend/Domain/QA)
- MPXJ: parseo de XER, PMXML, MPP y formato Asta si disponible; probar IDs WBS, calendarios, relaciones, hitos, baseline/variantes, holgura y preservación del dato.
- Excel/CSV/BOQ: estandarizar partida, moneda, unidad, cantidad, coste comprometido y revisiones; preservar fórmulas/filas/identificadores.
- IFC/IfcOpenShell/IfcTester solo si escenario y derecho de uso lo justifican; mapear requisito técnico y activo/equipo a BOM.
- Crear **especificación de adaptador** sin alterar código canónico: source_id, native_id, project_id, revision, observed_at, assertion, evidence, uncertain_matches.
- **DoD:** al menos un cruce contractual-plazo, uno contractual-presupuesto y uno especificación-BOM demostrados con referencias y falsos positivos controlados.

## WP3 — Procurement/RACI/Workflow (Procurement/Domain/UX)
- Comparar InvenTree vs ERPNext (y comerciales Archlet, Mandel, Caidentia, Zip): alcance real de BOM→RFQ→oferta→adjudicación→PO→recepción→factura; distinguir ERP/SRM, sourcing optimization, email-first coordination.
- RACI: representar responsable operativo, aprobador, consultado, informado y momento/acción; no inferir automáticamente autoridad de compra.
- Detectar fallos concretos: plazo ofertado incompatible, exclusión técnica no verificada, cambio de alcance sin PO, precio vs BOQ, entrega vs hito, factura sin aceptación.
- **DoD:** recorrido de caso sintético con 3 ofertas, criterios excluyentes, discrepancias explicables y propuesta de acción con propietario humano, sin escritura externa.

## WP4 — Interfaces y estrategia MCP/API (Integrations/Security)
- Dos sentidos independientes: (A) C2Pro consume APIs/MCP de terceros; (B) clientes Claude/ChatGPT/otras apps invocan herramientas C2Pro.
- Primer contrato read-only propuesto: `list_project_discrepancies`, `get_evidence_bundle`, `get_coherence_status`, `get_obligation_links`; respuestas con run_id, evidencia, cobertura y autorización de ámbito.
- Revisar permisos tenant/usuario, OAuth, RLS, PII, prompt injection, coste por consulta, limitaciones de MCP y términos comerciales.
- **DoD:** especificación de herramientas (sin despliegue), matriz de seguridad y compatibilidad por host; evitar herramientas de aprobación/escritura en fase inicial.

## WP5 — Business case y decisión (Planner + QA independiente)
- Comparar A build propio, B SaaS comerciales, C OSS self-hosted, D híbrido; costes infra/LLM/licencias/soporte/conectores, riesgos de licencias copyleft, propiedad de datos, dependencia de proveedores y duración de mantenimiento.
- Escenarios de producto: demo con importación de archivos (sin licencias comerciales), conector comercial autorizado, plug-in MCP de consulta.
- Resultado: **GO / CONDITIONAL GO / NO GO** para cada componente, con evidencia, coste y riesgo; decisión separada para arquitectura global.
- **DoD:** matriz TCO estimada con supuestos explícitos, decisión traceable y criterios de reversión.

## Orden y dependencias
WP0 precede a cualquier comparación; WP1 y WP2 pueden evaluarse en paralelo **cuando** WP0 quede preparado. WP3 usa la semántica de WP2. WP4 define contrato sin necesidad de que WP1–3 estén implementadas. WP5 exige evidencia de WP1–4. Son paquetes de planificación e investigación, **no autorizaciones de implementación productiva**.

## Gates de seguridad y no-regresión
- Ningún merge ni modificación de MASTER, ADR canónicas, branch UAT, base de datos operativa, deployment, workflows de aprobación o Coherence Score.
- Pruebas con fuentes y permisos legítimos; evitar subir documentación confidencial a terceros sin autorización.
- Revisión humana independiente de oráculo; criticidad contractual no queda diluida por media.
- No promover datos de proveedor a trusted sin validación; acciones con efectos siempre requieren autorización específica.
- Si un proveedor exige licencia restrictiva o prohíbe revender conectores: evaluar como benchmark o descartar como componente.

## Entrega a Planner
El Planner debe devolver (1) matriz de estado real por módulo, (2) dependencias y paquetes con owners/DoD, (3) arquitectura lógica C4/Mermaid, (4) contratos JSON/Pydantic/OpenAPI propuestos, (5) experimento mínimo reproducible, (6) riesgos/competidores y licencias, (7) criterios de decisión y fallback. Ver PLANNER_HANDOFF.md.
