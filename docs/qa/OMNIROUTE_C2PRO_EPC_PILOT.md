# C2Pro × OmniRoute — prueba mínima EPC

Este piloto **no cambia la ruta Anthropic de C2Pro**. Añade un cliente compatible
con el puerto `IAIClient.extract_json` y un ensayo muy breve para comparar
las ocho **rutas** que respondieron a solicitudes simples en OmniRoute.
Dos rutas Antigravity pueden compartir la misma cuenta/cuota.

## Ensayo funcional mínimo

En el checkout de esta rama (sobre el VPS que ya aloja OmniRoute):

1. Entrar en `apps/api`.
2. Ejecutar `python3 scripts/smoke_omniroute_epc.py --all`.
3. Introducir la **clave CLIENTE existente de OmniRoute** en la solicitud
   oculta del terminal, no la API key de Google ni las credenciales de los
   proveedores. No incluirla en argumentos, tickets ni el chat.
4. El script emite una petición sintética por ruta, sin datos reales ni
   reintentos, y únicamente muestra nombre del modelo, resultado y latencia.

Se evalúan tres fuentes EPC sintéticas: contrato con fin 30/09/2026 y
precio 1.000.000 EUR; cronograma con fin 31/10/2026; presupuesto de
1.200.000 EUR. Para pasar, cada respuesta debe entregar **JSON** con
`delay_days=31`, `over_budget_eur=200000` y citas a las tres fuentes.
HTTP 200 con respuesta vacía, JSON inválido, datos incorrectos o ausencia de
citas no pasa. Los resultados son evidencia *de este ensayo*, no UAT del
journey documental N4/N12 ni demostración de aislamiento entre tenants.

El cliente acepta `http://127.0.0.1:20128` para pruebas en el propio VPS.
C2Pro desplegado en Railway **no accede al loopback del VPS**. Para usarlo
fuera de ese host hará falta un endpoint HTTPS autorizado y alcanzable, sin
publicar indiscriminadamente el puerto del gateway.

## Candidatos

| Ruta | Modelo ensayado previamente | Estado anterior |
|---|---|---|
| NVIDIA | nvidia/nvidia/nemotron-3.5-bolt-e4b | E2E texto simple |
| OpenRouter | openrouter/liquid/lfm-3-1.7b:free | E2E texto simple |
| Gemini API | gemini/gemini-3.1-flash-lite | E2E texto simple |
| Grok Build | grok-cli/grok-4.7 | E2E texto simple |
| Antigravity CLI | agy/claude-opus-4-6-thinking | E2E texto simple |
| Antigravity | antigravity/claude-opus-4-6-thinking | E2E texto simple |
| Cursor | cursor/auto-cost | E2E texto simple |
| Kiro | kiro/claude-haiku-4.5 | E2E texto simple |

GitHub Copilot no pasó dos modelos (HTTP 400 model_not_supported);
Amazon Q carece de un modelo LLM seleccionable; Kilo Code tenía saldo 0 %;
AI Horde había quedado inconcluso. No se añaden como candidatos aprobados.

## Alcance de la implementación

`src/analysis/adapters/ai/omniroute_pilot.py` ofrece
`OmniRoutePilotClient.extract_json(system_prompt, user_content, task_type)`
y `generate(request)` con uso de tokens, latencia y modelo solicitado.
No introduce fallbacks silenciosos, no expone respuestas upstream de error
y no asigna coste cero a tarifas desconocidas: `cost_usd=None`.

El piloto se ejecuta explícitamente. No lo seleccionar como motor automático
para documentos reales todavía: el flujo Anthropic actual también implementa
anonimización, caché, cálculo de costes y controles de tenant que habría que
conservar al realizar el corte. No se ha conectado la ruta a CORE ni cambiado
el proveedor de producción.

**Advertencia funcional:** algunos accesos OAuth de suscripción se clasifican
en el propio catálogo de OmniRoute como de uso desaconsejado en proxies.
Pruebas sintéticas con permisos de la cuenta no equivalen a derechos para
procesar contratos de clientes. No habilitarlos automáticamente con datos
reales sin confirmar condiciones de uso. Las rutas API oficiales son mejores
candidatas para una integración productiva.
