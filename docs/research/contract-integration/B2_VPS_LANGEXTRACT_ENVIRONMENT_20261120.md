# B2 — LangExtract 1.7.1 instalado y preparado en VPS de AI-GEN

**Fecha:** 2026-11-20. **Estado:** ENTORNO PASS / PROMPTS NATIVOS PASS / INFERENCIA B2 PENDIENTE — NO se ha completado comparación semántica N4 v2 vs LangExtract.

## Corrección de entorno del propietario
La instalación oficial del experimento B2 queda en el VPS, **NO** en el PC Windows ni en el backend productivo de C2Pro.

- Ruta privada en VPS: `/home/aigenadmin/aigen-hybrid-pilot/data/c2pro-b2-langextract-vps/`.
- Entorno virtual: `.venv/`; `Python 3.12.3`; `langextract==1.7.1`, instalado con `uv`.
- Directorios privados: `scripts/`, `fixtures/`, `evidence/`.
- Sin cambios a servicios, dependencias productivas, UAT, ProjectGraph, HITL, Score o despliegues.
- La versión disponible implementa `ExampleData`, `extraction_passes`, `context_window_chars`, `lx.visualize()`, `output_schema` con proveedores nativos. Un `BaseLanguageModel` genérico personalizado **no admite aplicar automáticamente** `output_schema`: para un puente de proveedor personalizado hay que imponerlo/validarlo explícitamente; nunca se debe declarar schema-constrained sin probarlo.

## Fuente reproducible

- Documento público: SolarMax Longfellow EPC en SEC, obtenido directamente como HTML desde `https://www.sec.gov/Archives/edgar/data/1519472/000164033425001363/solarmax_ex991.htm`.
- HTML: 492.928 bytes; SHA-256 `0213ce2d545c38896251c3a7a96ade6283a857ae3308440875e734f04a21ea34`.
- Proyección de texto HTML para el modelo: 227.151 caracteres, SHA-256 `b4009aee679ebef7c81c07446a897ad5f9b7e8c224db7f0156f6a7967af99044`.
- **No es el PDF derivado de 74 páginas** utilizado en B0/B1; la diferencia de fuentes invalida cualquier comparación directa de offsets con ese PDF. Dentro de este nuevo B2 ambos enfoques deberán recibir la **misma** proyección SEC HTML.

## Dos ventanas completas de N4

Usando `plan_n4_source_windows.py` **de la SHA exacta `916808c5212e3dbc652407f35f3a17557623c06c`** sobre la fuente HTML, se planificaron 21 ventanas. Se eligieron dos consecutivas alrededor de §2.5.5:

| Ventana | Inicio core | Fin core | Caracteres de contexto | Hash contexto (prefijo) |
|---|---:|---:|---:|---|
| 7 | 78.376 | 89.575 | 11.999 | `335a5fb99f5d8f4f` |
| 8 | 89.575 | 100.769 | 11.994 | `bc69bab0bd94e9d9` |

Se ejecutó realmente `lx.extract()` con `ExampleData` basado en **una obligación raíz** con `trigger`, `rate_tiers`, `cap`, `dimensions`, `unresolved_refs`, y `extraction_passes=2`, `context_window_chars=400`, `max_char_buffer=12000`. Se usó un modelo de captura *sin inferencia*, exclusivamente para comprobar la composición nativa de los prompts. Resultado: **4 prompts** generados y conservados en `evidence/native_prompts/`; longitudes ~14.066 y 14.062 caracteres. Estas llamadas NO demuestran extracción semántica.

## Bloqueo verificado del ensayo con LLM
- El entorno virtual aislado no dispone de `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` ni `OPENAI_API_KEY` configuradas directamente.
- El broker de AI-GEN devuelve `request_limit` al intentar entregar un prompt LangExtract nativo completo (~14.066 caracteres) a un agente Gemini. Esto **no** equivale a un resultado de inferencia.
- En VPS existe infraestructura de modelos/Hermes configurada para Gemini, pero no se ha acreditado que ofrezca acceso programático compatible con LangExtract o un coste/versión de modelo fijados para el laboratorio. **No copiar secretos ni credenciales a repos públicos o al PC**.

## Requisitos para siguiente GO/B2 generativo controlado
1. Permitir al entorno VPS un proveedor autenticado **con límite explícito de gasto y modelo fijado**, directamente compatible con LangExtract o mediante un adaptador de proveedor que capture tokens, reintentos y coste. No alterar Hermes/Paperclip productivos.
2. Usar la misma proyección SEC, dos ventanas completas, mismo modelo, mismas condiciones de temperatura y salida. Comparar N4 v2 puro frente a LangExtract few-shot de atomicidad raíz + dos pasadas, contabilizando **el doble de llamadas** cuando corresponda.
3. Oráculo held-out independiente de raíces contractuales, atributos, condiciones, obligaciones, importes, derechos, citas exactas, anexos faltantes y falsas interpretaciones. No usar un ejemplo few-shot del mismo fragmento como oráculo.
4. Ejecutar `lx.visualize()` sobre resultados reales dentro del VPS privado. No exponer HTML con documentos/posiciones de origen en el GitHub público.

**Dictamen:** entorno listo y prompts reproducibles en VPS, **pero aún no se ha ejecutado LangExtract con LLM real**. No GO de integración productiva ni conclusión sobre recall, coste o LangExtract vs N4.
