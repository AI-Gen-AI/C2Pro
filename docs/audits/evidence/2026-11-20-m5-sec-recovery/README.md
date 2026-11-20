# M5 / T0.5: recuperación y medición offline de los 142 candidatos N4 SEC (2026-11-20)

| Campo | Valor |
|---|---|
| Ejecutado por | Runner de AI-GEN Ops en el VPS de QA, por orden directa del propietario (que sustituye para esta medición al sobre DEV-16) |
| Herramienta | `python -m scripts.reconcile_v41_n4_real_artifact` (sin modificar), con entradas privadas pinneadas y salida nueva `0600` |
| Restricciones respetadas | Sin inferencia, sin escrituras en BD, sin contenido contractual fuera del VPS; sin N12, HITL, ProjectGraph ni Score |
| Informe privado | `n4_t05_metrics_20261120.json` en el VPS (`0600`), SHA256 `fc14d62891463e8221046ca2d0e74fd98526a242ead0ac9ff3831b0dcf8b1b1c` |
| Entradas (SHA256) | artefacto `549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad` · N2 `cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4` · filing `2370812124b5f42713153122fc45f1e5716dd85385d881bdd339bd87b9dced06` |
| Dictamen M5 | **PASS** en recuperación y métricas documentales. **Calidad contractual: no demostrada** |

Este documento solo contiene cifras agregadas, sin texto del contrato ni de los candidatos.

## Métricas
- 142 candidatos, 142 claves únicas, 24 recibos SETTLED distintos (uno por ventana).
- Citas: **50 verificadas en N2 (35,2 %)** y **92 no verificadas (64,8 %)**, todas con motivo `NOT_FOUND_IN_MODEL_SAFE_SOURCE`.
- Categorías: contractual 118, cronograma 10, técnico 7, presupuesto 3, otros 4.
- Candidatos por ventana: entre 3 y 8 (ventanas 0–23).
- Duplicados: 0 grupos con el mismo título normalizado; 1 par con solape de span entre ventanas distintas (posible duplicado documental).
- De las 50 citas verificadas en N2, frente al PDF original:
  - **4** coinciden de forma exacta y única en la página;
  - **45** coinciden tras normalizar espacios;
  - 1 coincidencia exacta aparece repetida en la página.
- Páginas con al menos una cita verificada: **35/73 del EX-99.1 (47,9 %)** y 35/224 del filing completo.

## Lectura técnica (auditor)
1. **Dos comparadores de citas incoherentes (CONFIRMADO en código `799ce531`).**
   - `_evidence()` en `n4_compact_window_response.py:94-108` exige una coincidencia **exacta**, sin normalizar espacios, dentro de la ventana N2. Si falla, `parse_n4_window_output` guarda `source_quote = None`: **el texto que citó el modelo se pierde para siempre**. Por eso N4-H2 no se puede comprobar.
   - `classify_quote()` en `risk_provenance.py:27-47`, que se usa después en el puente, sí normaliza los espacios (`_squash`).
   - Indicio cuantitativo: frente al PDF, de 50 citas solo 4 coinciden exactamente y 45 al normalizar espacios.
   - **Hipótesis (no demostrada):** una parte de los 92 "no localizados" difiere solo en saltos de línea o espacios.
   - Corrección propuesta para VS-2, sin coste: unificar la comparación con espacios normalizados y un mapeo exacto de offsets, y **conservar siempre la cita cruda** con su estado.
2. **Sesgo de alcance:** el 83 % de los candidatos son "contractual"; presupuesto (3) y cronograma (10) apenas aparecen. Es coherente con que el prompt v1 solo pida riesgos.
3. **La cobertura documental es parcial:** el 52 % de las páginas del EX-99.1 no tienen ninguna cita verificada. Esto **no es recall**, pero indica dónde debe mirar primero el oráculo.
4. **Sin medir:** el recall (`NOT_MEASURED_NO_ORACLE`) y N4-H2 (`NOT_TESTABLE_WITH_ARTIFACT`). El documento SEC no es el PDF de 94 páginas del usuario.
