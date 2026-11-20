# C2Pro — Coherence Integration / Open Source — Línea de investigación independiente

**Fecha:** 2026-11-20  
**Estado vigente desde 20/11/2026:** INTEGRACIÓN ACTIVA en rama aislada; priorizar adaptadores reutilizables, código verificable y pruebas de integración. Sin autorización de merge, despliegue o modificación de la UAT.  
**Rama:** `research/c2pro-integration-open-source-20261120`  
**Base de creación:** `299aaf19f5025a2162c6a2c626542f6dd472c3c6` (main observado al crearla)  
**Fuente corporativa:** [Radar AI-GEN, pestaña Radar](https://docs.google.com/spreadsheets/d/1bNf7JVuk5o4HY6WMAhGl-CrTupZc5gJJdKMVnFJ5JQM/edit?gid=211126696#gid=211126696) (147 registros observados el 20/11/2026).

## Cambio de prioridad — orden expresa del propietario (20/11/2026)

**Esta iniciativa es de INTEGRACIÓN DE COMPONENTES, no de clasificación de los archivos personales/históricos.** Se detienen aquí inventarios, OCR y análisis de nuevos expedientes. El trabajo documental existente queda en la [carpeta privada F2 de Drive](https://drive.google.com/drive/folders/1Zgzou1cCncT4sqrrRWA8J2u4olkKjbqN), como línea separada e inactiva para este frente. No hay obligación de continuarla.

**Objetivo inmediato (I-01):** integrar un adaptador opcional MPXJ de lectura `.mpp`/`.xer`, alineado con los tipos de evidencia y revisiones de C2Pro, con pruebas automatizadas sobre fixtures no confidenciales. Sin cambiar todavía política de upload, endpoints, bases de datos, ProjectGraph ni el flujo N4/N12. Después validar Docling como adaptador opcional de estructura y spans, no sustitución de parser ni de inteligencia contractual.

**Entregable = código ejecutado + pruebas + contrato de interfaz + reporte de límites; NO más inventarios.** Toda futura tarea debe cumplir esta condición o pertenecer a la otra línea.

**Rama de origen históricamente desactualizada:** base `main` de 28/10/2026; antes de proponer un PR contra el código vivo habrá que comparar las ramas UAT actuales sin rebase ni fusionarlas a ciegas.

**Seguridad:** repositorio público; solo código genérico y fixtures sintéticos. No publicar nombres de proveedores, PO, informes OCR o hashes de archivos privados. Los commits antiguos con metadatos potencialmente internos siguen pudiendo existir por SHA: limpiar una rama no demuestra borrado del historial remoto.

Ver [INTEGRATION_EXECUTION_PLAN.md](INTEGRATION_EXECUTION_PLAN.md) para prioridades y gates.

## 1. Hipótesis (no decisión)
Estudiar si C2Pro aporta más valor como **capa de inteligencia de coherencia EPC/ETO** conectada a componentes existentes que como suite monolítica que vuelve a implementar todos los sistemas. El núcleo potencialmente propio sería ProjectGraph canónico, inferencia/comprobación de relaciones entre obligaciones/partidas/hitos/especificaciones/BOM/RFQ/PO, evidencia, HITL y Coherence Score. La propuesta ha de competir con alternativas build, buy, integrate y mixtas; no dar por cierta su superioridad.

## 2. Alcance de investigación
- Contrato integral, anexos, pliegos, versiones y referencias/citas; verificación de cobertura N4/N12 frente a motores alternativos.
- Presupuesto/BOQ, cronograma WBS, ruta crítica, especificaciones, ingeniería/BIM y BOM.
- Compras: requisiciones, RFQ, respuestas, evaluación técnica/comercial, PO, proveedor, factura, aceptación.
- Responsables RACI y comunicaciones; alertas dirigidas con autoridad apropiada.
- Exposición API/MCP hacia Claude, ChatGPT, Procore u otros clientes; y consumo desde C2Pro de APIs/MCP comerciales.
- Licencias OSS, términos comerciales API, protección de datos de clientes, tenant isolation, costes reales y soporte operacional.
- Pruebas con corpus legalmente disponible: contratos + anexos + presupuesto + cronograma + BOM; oráculo y evaluación independiente.

## 3. Delimitación estricta
Esta rama es de **integración experimental de solo código aislado y pruebas** (no se activan rutas productivas). No sincroniza ni reescribe el camino crítico UAT/VS-1/G4/N4-only (#1259, #1276), ni cambia MASTER, ADR canónicas, prompts productivos, N4/N12, HITL, ProjectGraph, Coherence Score, datos, infraestructura, integraciones activas, despliegues o routing de modelos. No merges ni producción. Se permite implementar y probar adaptadores **aislados y opt-in** dentro de esta rama, sin efectuar inferencia facturable, migraciones ni alterar despliegues. No instalar servicios persistentes ni cambiar políticas de confianza.

La base `main` usada al crear la rama puede estar atrasada respecto a otras ramas activas; el Planner deberá confrontar la arquitectura propuesta con la SHA del flujo funcional actual sin fusionar ni sobrescribir trabajo.

## 4. Artefactos de esta iniciativa
- [PLAN.md](PLAN.md): fases, entregables, gates y criterios de abandono.
- [CANDIDATES.md](CANDIDATES.md): inventario de alternativas del radar, OSS, Hugging Face, riesgos de licencia y madurez.
- [PLANNER_HANDOFF.md](PLANNER_HANDOFF.md): misión explícita al rol Planner y retorno estructurado.

## 5. Resultados decisionales esperados
1. Matriz por dominio **reusar / integrar por API / comprar / mantener propio / descartar** con evidencia y coste.
2. Arquitectura de referencia mínima con contrato de evidencia y enlaces canónicos entre objetos.
3. Plan de benchmark autónomo, reproducible, sin promoción basada solo en tests de código.
4. Viabilidad de demo de coherencia **contrato + anexo + cronograma + presupuesto + BOM/RFQ**, con criterios de éxito y fallos.
5. Recomendación final y alternativas; ninguna implementación productiva queda aprobada por este GO.

**Propietario de aprobación:** usuario. **Planner:** agente de planificación documental; no desarrolla código productivo.  
