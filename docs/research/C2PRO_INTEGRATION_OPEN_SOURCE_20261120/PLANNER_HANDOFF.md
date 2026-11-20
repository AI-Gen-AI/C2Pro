# Convocatoria al Planner — C2Pro Integration & Open Source — 2026-11-20

**Mandato:** GO explícito del propietario para DESARROLLAR LA PLANIFICACIÓN TÉCNICA de una línea de investigación separada, no ejecutar código productivo ni invadir el programa UAT.  
**Repo:** AI-Gen-AI/C2Pro  
**Branch:** `research/c2pro-integration-open-source-20261120`  
**Scope:** `docs/research/C2PRO_INTEGRATION_OPEN_SOURCE_20261120/`  
**Lectura obligatoria:** README.md, PLAN.md, CANDIDATES.md; `roles/role_planner.md`, `context/working/agents/agent_planner.md`; la realidad actual de arquitectura/ADRs y estado exacto N4/N12/VS-1/G4 (#1259/#1276) en sus SHA/referencias originales, sin asumir que main equivale a producción.

## Instrucción al rol Planner
`@planner audit-idea "C2Pro como Coherence Intelligence Layer híbrida, datos contrato+anexos+pliegos+presupuesto+cronograma+BOM/RFQ/RACI; reutilizar OSS/SAAS; exportar MCP"`
y a continuación
`@planner breakdown "C2Pro Integration & Open Source — investigación separada"`.

1. **Desafiar la hipótesis:** identificar qué funcionalidades C2Pro ya tiene (funcionales, parciales, stubs), qué se duplicaría al incorporar OSS, y dónde queda IP diferenciadora. Efectuar auditoría arquitectónica sin alterar nada.
2. **Seleccionar no más de tres spikes iniciales:** recomendados WP1 Docling/LangExtract/OpenContracts y WP2 MPXJ, bajo presupuesto y pruebas autorizados; explicar secuencia, compatibilidad de Python/Java, APIs, datos, licencias y fallback.
3. **Proponer objetos de intercambio:** DocumentEvidence, SourceSpan, Obligation, Requirement, ScheduleActivity, CostLine, BOMItem, OfferLine, ActorRACI, Discrepancy, ReviewDecision, Coverage, ScoreProjection; relaciones de procedencia y vigencia.
4. **Definir fronteras de confianza:** source hash, tenant, revision, run_id, candidate vs trusted, cobertura, QA oráculo independiente, recuperación sin repetir efectos; no aprobar riesgos parciales.
5. **Construir plan técnico por incrementos:** paquete, precondiciones, dependencias, rol, archivos potenciales, coste estimado/supuestos, DoD y evidencia de aceptación. Sin tickets al backlog canónico hasta decisión separada.
6. **Diseñar benchmark/decision record:** matriz ponderada (accuracy, recall critical, evidence, coverage, cost, compliance, portability, maintenance); identificar criterios de NO GO.
7. **Contrastar con radar corporativo:** reconocer candidatos #36/#117/#118/#120/#121/#123/#125/#127/#133/#147; proponer registros nuevos sin escribir la hoja.
8. **Vía MCP:** consumo de SaaS y publicación de C2Pro read-only, sin nuevas credenciales ni alta de usuarios.
9. **Entregar propuesta final:** 2 arquitecturas candidatas, trade-offs, riesgos, primera demo verificable y decisión que requiere aprobación del propietario.

## Entregables esperados
- `PLANNER_RESULT.md`: informe de arquitectura, 2 alternativas y tradeoffs.
- `PLANNER_EXECUTION_PLAN.md`: paquetes atómicos con responsables y criterios DoD.
- `PLANNER_INTERFACE_PROPOSAL.md`: esquemas lógicos, interfaces y diagrama Mermaid.
- `PLANNER_EVAL_MATRIX.md`: matriz de pruebas, oráculo, resultados pendientes y reglas de promoción.
Todos los entregables son **propuesta**, no implementación.

## Salvaguarda respecto al Planner histórico
Hay instrucciones históricas del rol para escribir `blackboard.json` y backlog canónico. Esta misión **no autoriza** esa escritura ni la generación de IDs del MASTER. Si el agente requiere esos cambios para ejecutar su protocolo habitual, debe señalar la incompatibilidad en su informe y quedarse en planificación documental de la rama; nunca invadir estados operativos actuales.

## Criterio de éxito de convocatoria
Planner acepta y devuelve análisis crítico aplicable a esta rama, sin código ni despliegues. Si la herramienta operativa de agentes solo permite revisión read-only, deberá producir respuesta estructurada para su incorporación posterior a estos documentos, sin fingir que ha realizado commits.
