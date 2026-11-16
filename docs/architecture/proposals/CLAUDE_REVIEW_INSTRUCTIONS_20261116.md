# Solicitud de revisión arquitectónica independiente — Claude Code (lectura solamente)
Estás actuando como revisor técnico principal/Staff Engineer independiente de C2Pro, NO como implementador. El propietario ha aprobado conceptualmente la evolución a C2Pro V4, pero exige revisión crítica antes del GO de código.

**Lee íntegramente el documento de diseño**: `/home/aigenadmin/c2pro-architecture-review-20261116/ARCHITECTURE_PLAN.md`.

**Examina el código real en** `/home/aigenadmin/c2pro-n4-multiprovider-20261116` (rama experimental PR #1234). Presta atención a:
- `apps/api/src/analysis/adapters/graph/workflow.py`
- `apps/api/src/analysis/adapters/graph/nodes.py`
- `apps/api/src/analysis/adapters/graph/schema.py`
- `apps/api/src/analysis/adapters/ai/tools/risk_extraction_tool.py`
- `apps/api/src/analysis/adapters/ai/tools/n4_external_provider.py`
- `apps/api/src/coherence/cross_document/`
- `docs/architecture/decisions/ADR-014-project-state-model.md`
- `docs/architecture/decisions/ADR-017-projectgraph-two-tier-orchestration.md`

**Enfoque:** no aceptes la propuesta por cortesía. Refuta supuestos, busca costos ocultos, llamadas innecesarias, cambios de estado inseguros, fallos de compatibilidad y huecos de producto. Verifica explícitamente el grafo y sus bifurcaciones, los contratos con N8/N12/N15/N17, el rol diferenciado de ProjectGraph, la extracción multimodal y la persistencia de hallazgos parciales. Considera todas las clases de proyectos, no solo EPC, evitando WBS/BOQ como ontología universal.

**Revisa especialmente:** ¿es correcto conservar 17 N con seis etapas lógicas o simplificar físicamente? ¿qué es un nodo y qué es un LLM call? ¿cómo rediseñar N4 con tool-calling + checkpoints sin 6 subagentes? ¿qué debe hacer N3 con documento multidisciplinar? ¿cómo evitar repetir N12, model switching arbitrario, desperdicio por JSON monolítico y autocitas falsas? ¿cómo controlar gasto real OAuth/API y costes por tenant/proyecto/documento? ¿cómo llega el resultado al dashboard de riesgos, Coherence validada/provisional, Health y HITL humano?

**Entrega:** respuesta detallada en español, con 1) veredicto y resumen crítico; 2) problemas concretos actuales con rutas+líneas si verificables; 3) arquitectura mejorada mínima; 4) descripción N1–N17, qué mantener/modificar/fusionar sin sobreingeniería; 5) N4 agentic loop paso a paso con contrato/pseudocódigo; 6) estrategia de modelos e interfaces; 7) coste/latencia y mitigaciones; 8) pruebas/gates para GO y MVP priorizado; 9) decisiones abiertas para propietario; 10) riesgos de migración. Incluye objeciones fuertes, no solo aprobación.

**Restricciones terminantes:** SOLO LECTURA de repo y diseño. NO editar archivos ni commits, ni configurar entorno, ni ejecutar herramientas con coste en proveedores del proyecto, ni desplegar ni tocar Railway/Vercel/PG. No imprimir secretos, datos personales ni fuente contractual completa. Si faltan pruebas dilo.

Al terminar, emite el dictamen directamente en tu respuesta; otro proceso guardará esa respuesta en `/home/aigenadmin/c2pro-architecture-review-20261116/CLAUDE_REVIEW_RESULT.md`.
