# Frente B — auditoría offline cruzada de gobernador y recibos (17/11/2026)

**Alcance:** sin proveedores LLM, sin DB, sin salida de texto contractual ni IDs
de llamadas. No implica autorización de merge, UAT, revisión HITL o gasto.
Coordinar exclusivamente en [#1049](https://github.com/AI-Gen-AI/C2Pro/issues/1049).

## Motivación y contrato

La CLI financiera de #1258 coteja `n4_usage_reservations` y
`legacy_ai_usage_reservations` contra el balance del tenant, pero el
JSON N3 legacy carece de `provider_request_id`. El artefacto
independiente del gobernador `c2pro-v41-openai-governor.jsonl` permite
un segundo cotejo, sin hacer nuevas llamadas:

- Debe haber exactamente una reserva y una finalización por `id`
  dentro del archivo; operaciones y request IDs duplicados fallan.
- Cada recibo N4 debe enlazar con un `done/completed` mediante el
  `provider_request_id` y coincidir en tokens e importe estimado a seis
  decimales. No se transforman identificadores ni se publican.
- El conjunto de `done` sin atribuir a N4 se compara con recibos
  N3/N12 legacy. **Si solo existe uno por ruta**, coste y tokens pueden
  cotejarse; la identidad del proveedor NO se considera demostrada sin
  la clave `provider_request_id` persistida en ledger legacy.
- La suma de todos los `done` debe igualar el total de recibos.
  Costes excedidos respecto a reserva, respuesta desconocida, IDs
  repetidos, evento ausente o inconsistencia del auditor financiero
  bloquean el resultado.
- Múltiples recibos legacy sin identidades verificadas fallan cerrado.
  Una discrepancia de nombre entre alias y modelo versionado figura
  como limitación sin declarar la tarifa real comprobada.

## Uso de prueba

Descargar el artefacto **exacto** del job aprobado; verificar run, SHA
y SHA256 antes de usar. Desde la carpeta raíz de extracción de ZIP:

```bash
cd /ruta/segura/artefacto-extraido
PYTHONPATH=/ruta/repo/apps/api python \
  /ruta/repo/apps/api/scripts/audit_v41_governor_evidence.py \
  _temp/c2pro-v41-real/real_analysis_evidence.json \
  C2Pro/C2Pro/apps/api/c2pro-v41-openai-governor.jsonl
```

Ambas rutas deben ser relativas al directorio de extracción, sus nombres
base exactos y sin `..` ni escapes por symlink. Hasta 25 MB de JSON
financiero, 10 MB de JSONL y 1.000 eventos; no lee rutas arbitrarias.

## Evidencia del piloto real

[GitHub Actions #44007355327](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44007355327),
Frente A `61df7648715085112ad41dacf61565e57725b710`, artefacto
`real_analysis_evidence.json` SHA256
`549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad`.

- 25 eventos reserve y 25 done, sin duplicados; todos completed.
- N4: 24/24 recibos enlazados por request ID, tokens y coste coinciden
  con el gobernador. N3: recibo único matched por consumo, sin request
  ID persistido en el ledger N3.
- Total `0.394394 USD` de coste **estimado** en ambos orígenes.
  No hay factura oficial ni tarifa facturada comprobada.
- Modelo del ledger `gpt-4.1`; el gobernador informa versión
  `gpt-4.1-2025-04-14`, diferencia advertida, no ignorada.
- Salida: `GOVERNOR_LINKED_PARTIAL_PILOT_NO_GO`, salida 1 por
  `N4 PARTIAL (examined_windows=0/24)`. Son 142 candidatos sin
  aceptación; N12 sigue sin ejecutarse.

**Limitación de integridad:** dos archivos del mismo ZIP permiten un
cotejo cruzado, no una garantía criptográfica de independencia ni
ausencia de cargos duplicados entre runs distintos. El coste estimado
no sustituye la factura ni convierte citas no verificadas en evidencia.

## Pruebas y gates

Las pruebas unitarias incluyen modificaciones adversariales de ID,
tokens, importes, recibos y paths. Requiere todavía regresión
PostgreSQL integrada de Coherence e inventario, y revisión independiente
sobre la SHA final. G2/G4 **NO-GO productivo**.

No modificar el flujo propietario del Frente A ni su contrato de
continuación N4/N12 sin decisión de CORE.
