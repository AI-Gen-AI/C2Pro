# C2Pro CORE — wiring TRUSTED ProjectState en ProjectGraph (09/11/2026)

## Problema y alcance

En EPC-SYN-2026-11-05 existen datos contractuales analizados y físicos, pero no estado canónico. PR #1206 explica honestamente el NULL, y PR #1207 implementa un bootstrap estricto en aplicación. Esta PR conecta esos dos elementos al ProjectGraph en la transacción del runner.

## Ruta exacta

1. run_project_graph_once consulta exclusivamente list_trusted_for_project(project_id, tenant_id), que filtra ACTIVE y TRUSTED y excluye candidatos estructurados.
2. En la misma sesión transaccional, el callback del task runner obtiene para cada artefacto las cláusulas físicamente vinculadas a (tenant, document, revision).
3. materialize_trusted_state_if_absent rechaza riesgos sin cita única/verbatim, sin revisión, ambiguos o duplicados; no persiste un subconjunto de riesgos ni falsos clean assessments.
4. SQL INSERT ON CONFLICT DO NOTHING no destruye un ProjectState existente. En conflicto, devuelve unchanged o reconciliation_required. Si no se puede acreditar el estado, no se entrega a Health.
5. El nodo ProjectGraph.health recibe las cláusulas y riesgos canónicos solamente si el status es created/unchanged y las revisiones e identidad coinciden. Si falta evidencia, contract/risk quedan NULL y se expone la causa. No cambia los umbrales de Coherence ni las decisiones HITL.
6. El mismo transaction boundary engloba la materialización, graph, alertas y mark_loaded_projected. Si falla alguna operación, rollback del caller; no hay commits en los nuevos servicios.

## Límites deliberados

- Ni XLSX source-only, ni PROPOSED, ni REJECTED alimentan el estado.
- Un documento TRUSTED sin cláusulas físicas de la misma revisión bloquea el bootstrap: no fabrica evidencia ni invita a aprobar un documento.
- Un ProjectState existente que difiere no se actualiza silenciosamente; requiere reconciliación revisional explícita. El Graph queda disponible, pero el status de la materialización es visible y esas dimensiones Health no se puntúan a partir del estado posiblemente obsoleto.
- Health composite y Coherence Score global son indicadores diferentes. Un Health no nulo no acredita Coherence ni aceptación UAT.
- Los snapshots anteriores no se reescriben; no hay backfill ni deploy. Para verificar el caso EPC actual en el entorno operativo hará falta nuevo evento/snapshot legítimo, con controles de tenant e HITL, tras despliegue explícito.

## Gates

- QA Python + PostgreSQL aislado sobre SHA exacto, incluyendo casos negativos A/B, revisión y fuentes no confiables.
- Auditoría independiente de Claude y Codex sobre el runner y el nodo Health.
- Un ensayo vertical EPC real de 4 documentos: fuente, citas dobles, N4/N12, HITL, Health y Coherence cuando haya evidencia suficiente.
- No marcar CORE como UAT ni RELEASE hasta pasar la aceptación vertical.
