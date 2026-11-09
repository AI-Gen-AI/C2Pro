# C2Pro CORE — Health/Coherence NULL, diagnóstico 09/11/2026

Estado: NOT_UAT / NO_RELEASE. Observación exclusivamente READ-ONLY en C2Pro Supabase.

## Evidencia real del proyecto EPC-SYN-2026-11-05

Cuatro documentos: contrato DOCX, presupuesto XLSX, cronograma XLSX y especificación DOCX.
Seis cláusulas físicas persistidas y tres riesgos del último análisis terminado.
Un artefacto contractual actual TRUSTED; la especificación está PROPOSED;
presupuesto y cronograma no tienen artefactos TRUSTED en el catálogo examinado.
Tablas public.project_states y project_state_entities vacías (cero filas).
Siete snapshots del proyecto con cero entidades canónicas; el snapshot final
graph_completed tiene cuatro dimensiones Health sin puntuación. Sus motivos
literalmente afirman que no hay cláusulas extraídas y que no se ha ejecutado
la evaluación de riesgos, pese a los registros documentales anteriores.

El snapshot final conserva seis assessments de cobertura con granularidad CLAUSE;
esto es información documental, NO seis señales de Health puntuadas.
analyses.coherence_score NULL; seis valores del breakdown NULL y cero filas
de coherence_results en este proyecto.

## Causa funcional

SnapshotWriter consulta ProjectState canónico por proyecto y tenant.
Como no hay estado materializado, los scorers de contrato/riesgo reciben
listas vacías, emiten NULL y los mensajes inexactos anteriores. El mapeador
map_pipeline_output_to_project_state existe, pero la búsqueda del flujo operativo
no encuentra llamadas de escritura que conviertan los análisis confiables
en el estado canónico. El nodo ProjectGraphHealth también pasa listas vacías
para cláusulas y obligaciones.

Health composite es NULL cuando ninguna señal dispone de score. Coherence global
permanece NULL si no hay categoría evaluada o si active_weight es inferior a 0.35.
Estas reglas protegen el producto; NO modificar sus umbrales.

## Corrección acotada

Cuando ProjectState falta de verdad, SnapshotWriter diferencia:
- risk: canonical project state not materialized; risk assessment availability unverified
- contract: canonical project state not materialized; contract clauses not projected

No se asignan puntuaciones, evidencia, estado confiable ni decisión HITL.
Si el estado canónico sí existe, pero está vacío, se conservan sus causas
de datos ausentes. Tests comprueban ambos casos y que NULL sigue siendo NULL.

## Hitos de cierre, aún pendientes

P0: materialización idempotente de ProjectState solo desde artefactos TRUSTED y
cláusulas de revisiones físicas pertenecientes al mismo tenant. PROPOSED,
REJECTED y XLSX source-only no se promueven; respetar lineage HITL.
P0: verificar en PostgreSQL aislado que la transición trusted->project-state
propaga riesgos y cláusulas hasta SnapshotWriter; probar revisiones y A/B.
P1: determinar seis categorías de Coherence y sus fuentes confiables sin
rebajar el umbral ni fabricar un score con información pendiente.
P2: validación de discrepancias doble fuente, HITL real y Current State,
todo sobre un SHA único antes de UAT.

Esta PR solo corrige la atribución errónea de las razones NULL.
No implica backfill, liberación de producción o aceptación funcional.
