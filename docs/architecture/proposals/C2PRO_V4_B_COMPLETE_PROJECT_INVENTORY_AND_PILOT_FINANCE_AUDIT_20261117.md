# C2Pro V4.1 — Frente B: inventario integral y auditoría de evidencia del piloto

Fecha: 17/11/2026. Rama apilada sobre #1257 SHA `6d46768a2f60c30a5679e5eda362cdc13cf29325`.
**Solo QA y revisión; feature desactivada en runtime de producción.**

## 1. Por qué este paquete

La verificación anterior en #1257 demostraba que los `revision_id`
seleccionados existen en el proyecto/tenant y representan blobs reales,
pero **NO** acreditaba que incluyeran todos los documentos del proyecto.
Era posible analizar una fuente individual y presentar erróneamente la
selección como proyecto completo.

### Nuevo control independiente, opt-in

`verify_coherence_project_manifest(...,
require_complete_project_inventory=True)` obliga a:

- Una única instantánea `REPEATABLE READ` o `SERIALIZABLE`
  con tenant fijado por `app.current_tenant` — si se ejecuta en
  `READ COMMITTED`, el control falla cerrado.
- Consultar por tenant/proyecto todos los `documents`, mediante
  `LEFT JOIN` de sus revisiones actuales; no invisibilizar documentos
  nuevos sin revisión en un `INNER JOIN`.
- Comparar la lista exacta de `(document_id, revision_id)` contra la
  selección suministrada; faltantes, versiones antiguas, duplicadas,
  documentos sin revisión y documentos de otro proyecto/tenant ⇒ rechazo.
- Calcular el digest canónico incluyendo el modo de cobertura; las
  identidades seleccionadas y las verificadas como «inventario completo»
  no se confunden ni comparten el mismo digest.
- `bind_clause_source` exige por defecto `complete_project_inventory_verified`
  para emitir una identidad gobernada. El modo de **evaluación parcial de
  documento** requiere `require_complete_project_inventory=False`
  expresamente y no constituye aceptación de Coherence a nivel proyecto.
- Mantener un puerto separado que rechace cláusulas cuya procedencia
  combina dos o más revisiones: **no crear un revision_id artificial**.

Este control certifica **solo** exhaustividad frente a las filas actuales
del inventario PostgreSQL en esa instantánea, no que el proyecto incluya
todos los documentos del mundo real. Sucesos posteriores, documentos no
cargados, OCR defectuoso, citas incorrectas o un `run_id` no enlazado a
una orquestación real requieren controles adicionales. La funcionalidad
se mantiene opt-in y **no está conectada al grafo Coherence productivo**.

## 2. Auditoría financiera de evidencia real sin duplicar gasto

Nuevo verificador de artefactos:
`src/core/ai/v41_financial_evidence_check.py`; CLI:
`apps/api/scripts/audit_v41_finance_evidence.py`.

Uso una vez que CORE publique el artefacto *sanitizado* del mismo run y
SHA autorizados:

```bash
# Desde el directorio de extracción fiable (no desde apps/api):
cd /ruta/segura/extraida
PYTHONPATH=/ruta/repo/apps/api python /ruta/repo/apps/api/scripts/audit_v41_finance_evidence.py \
    _temp/c2pro-v41-real/real_analysis_evidence.json
```

Por seguridad, la CLI solo admite rutas relativas contenidas dentro del
directorio actual; rechaza rutas absolutas, `..`, symlinks que escapen de
la raíz y nombres diferentes de `real_analysis_evidence.json`.

No hace llamadas a modelos, PostgreSQL ni API externa. Valida por
`Decimal` totales de N4 y ledger legado N3/N12, cuenta claves repetidas,
reserva/SETTLED/UNKNOWN, saldo de tenant, límite mensual, costes conocidos
por encima de la reserva, ventanas N4 y anomalías de tokens/costes.
Devuelve solo un pequeño JSON de códigos y sumas sin texto documental,
identificadores confidenciales ni transcripción. Un recibo duplicado
queda marcado como inconsistente y **se excluye de las sumas** para no
inflar artificialmente el coste. Si ambos ledgers aportan identificadores
de solicitud del proveedor comparables, detecta su reutilización entre
rutas; cuando la fuente no los aporta, el control NO puede certificar
ausencia de duplicados inter-lane. **Nunca `invoice_verified` true**. Si falta el artefacto o la contabilidad, el resultado es
`NOT_AUDITABLE`; si hay UNKNOWN, `PENDING_PROVIDER_RECONCILIATION`.
También bloquea explícitamente un análisis N4 parcial, sin el número de
recibos correspondiente a sus ventanas, o con reservas aún `RESERVED`.
Por tanto, un saldo contable aritméticamente correcto no hace que un
journey parcial sea aceptable. Solo sale código 0 cuando el ledger interno
está equilibrado y no quedan holds ni sobrecostes, **aunque la factura
del proveedor siempre permanece sin verificar**.

Hipótesis necesaria: la base del piloto es desechable y su tenant contiene
solo las operaciones de ese run. Para tenants de producción con actividad
histórica, consultar el ledger bajo una identidad de run persistente y
filtrar todos los asientos antes de comparar con el saldo acumulado; este
verificador no tiene autoridad para liquidar saldos reales ni corregir
recibos. La comparación contra factura externa requiere un recibo del
proveedor independiente del coste calculado por el wrapper.

## 3. Estado del ensayo CORE (evidencia verificada)

GitHub Actions [#44005398693](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44005398693),
SHA `90aae3efe223c8873bc7aff1233e3b97fbb86946`,
terminó FAILED en `bootstrap_test_infra.py`/Alembic **antes de N3/N4/N12**:
SQLAlchemy rechazó una URL malformada; no se produjo el artefacto
`real_analysis_evidence.json`. Por tanto, no aplicar todavía el auditor
a un fichero inexistente, no inferir gasto real ni resultados semánticos.
El responsable Frente A ha publicado versiones posteriores a esa SHA; la
corrección y el nuevo ensayo pertenecen a Frente A/CORE.

**Revisión independiente:** Codex evaluó la SHA `9072d7e1c...`
mediante job `167bb4f5b9489129f8d0ebdc87d065ee` y emitió
`CHANGES_REQUIRED` acotado al código real. Hallazgos: sumas infladas
por recibos duplicados, falta de obligatoriedad por defecto del
inventario completo y test adversarial de duplicación entre rutas.
Se han incorporado los dos cambios de comportamiento y casos
adversariales; **debe repetirse la revisión en la nueva SHA**. La
comprobación del proveedor externo sigue fuera del alcance.

## 4. QA y limitaciones

- PostgreSQL 16 aislado, revision A/B reales de prueba: test sin y con
  inventario integral, documentos sin revisión, READ COMMITTED rechazado,
  fuentes históricas/tenant/proyecto falsos.
- Batería unitaria de auditoría JSON financiero: SETTLED/UNKNOWN,
  discordancia de saldos, sobrecargo medido, duplicados, anomalías de
  tokens, cobertura N4 y evidencia ausente.
- Nuevos checks son **puramente de integridad financiera y procedencia
  de inventario**; no prueban IA real ni contratos verdaderos.
- G2/G4 NO-GO hasta respaldo externo fiable, cobertura de origen
  contrato→proyección→riesgo, factura real e HITL individual autorizado.

No fusionar fuera del orden #1257 y dependencias; ningún flag productivo
activado y ningún gasto de proveedor.
