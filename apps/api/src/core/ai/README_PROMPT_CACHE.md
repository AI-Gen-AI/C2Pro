# Prompt Cache - C2Pro

Sistema de caché inteligente para prompts idénticos usando hash SHA-256.

## 🎯 ¿Qué es el Prompt Cache?

El **Prompt Cache** evita llamadas redundantes a Claude API cacheando respuestas de prompts idénticos.

### Beneficios

- ✅ **Ahorro de costos**: $0 por respuestas cacheadas
- ✅ **Velocidad**: ~100x más rápido (ms vs segundos)
- ✅ **Reducción de latencia**: Respuestas instantáneas
- ✅ **Menor carga API**: Menos requests a Anthropic
- ✅ **Determinismo**: Mismos inputs → mismos outputs

### Características

- 🔐 **Hash SHA-256** del input completo
- ⏱️ **TTL 24 horas** (configurable)
- 🏪 **Redis + fallback memoria**
- 📊 **Métricas automáticas** (hit/miss rate)
- 🔄 **Integración transparente** con AIService

---

## 🏗️ Arquitectura

### Flujo de Cache

```
Request → [Prompt Cache?] ─Yes→ Return cached
               │
               No
               ↓
          [Document Cache?] ─Yes→ Return cached
               │
               No
               ↓
          Call Claude API
               ↓
          Save to caches
               ↓
          Return response
```

### Capas de Cache

1. **Prompt Cache (Layer 1)**: Hash SHA-256 del input completo
2. **Document Cache (Layer 2)**: Por document_hash + task_type
3. **API Call**: Si ambos fallan

---

## 🔑 Hash SHA-256

El hash incluye **todos** los parámetros que afectan la respuesta:

```python
hash_input = {
    "prompt": "Analiza este contrato...",
    "system_prompt": "Eres un experto...",
    "temperature": 0.0,
    "max_tokens": 4096,
    "model": "claude-sonnet-4-20250514"
}
```

**Mismo hash → Cache HIT**
**Hash diferente → Cache MISS**

### Ejemplo

```python
from src.core.ai.prompt_cache import build_prompt_hash

# Mismo prompt, mismos parámetros
hash1 = build_prompt_hash(
    prompt="Clasifica este documento",
    temperature=0.0,
    model="claude-sonnet-4"
)

hash2 = build_prompt_hash(
    prompt="Clasifica este documento",  # Mismo
    temperature=0.0,  # Mismo
    model="claude-sonnet-4"  # Mismo
)

assert hash1 == hash2  # ✅ Cache HIT

# Cambiar un parámetro
hash3 = build_prompt_hash(
    prompt="Clasifica este documento",
    temperature=0.5,  # ← CAMBIO
    model="claude-sonnet-4"
)

assert hash1 != hash3  # ❌ Cache MISS
```

---

## 💻 Uso

### Opción 1: Automático (Recomendado)

El cache está **habilitado por defecto** en todas las requests:

```python
from src.core.ai.service import AIService, AIRequest
from src.core.ai.model_router import TaskType

service = AIService(tenant_id=tenant_id)

# Primera llamada - Cache MISS
request = AIRequest(
    prompt="Analiza la coherencia de este proyecto...",
    task_type=TaskType.COHERENCE_ANALYSIS,
    # use_cache=True  ← Default
)

response = await service.generate(request)
# Costo: $0.0234 (llamó a la API)

# Segunda llamada (prompt idéntico) - Cache HIT
response2 = await service.generate(request)
# Costo: $0.0000 (¡gratis!)
# Tiempo: ~5ms vs 1500ms
```

### Opción 2: Desactivar Cache Manualmente

```python
request = AIRequest(
    prompt="Analiza este proyecto...",
    task_type=TaskType.COHERENCE_ANALYSIS,
    use_cache=False,  # ← Desactivar cache
)

response = await service.generate(request)
# Siempre llama a la API, aunque el prompt sea idéntico
```

### Opción 3: API Directa del Cache

```python
from src.core.ai.prompt_cache import get_prompt_cache_service

cache = get_prompt_cache_service()

# Intentar obtener del cache
cached = await cache.get_cached_response(
    prompt="Clasifica...",
    system_prompt="Eres experto...",
    temperature=0.0,
    model="claude-sonnet-4"
)

if cached:
    print(f"Cache HIT! Respuesta: {cached.content}")
    print(f"Edad: {cached.get_age_seconds()}s")
    print(f"Costo ahorrado: ${cached.cost_usd}")
else:
    # Cache MISS - llamar API
    response = await call_api(...)

    # Guardar en cache
    await cache.set_cached_response(
        prompt=prompt,
        response_content=response.content,
        model=model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        execution_time_ms=execution_time,
    )
```

---

## 📊 Métricas y Observabilidad

### Logs Estructurados

Cada operación de cache genera logs:

**Cache HIT:**
```json
{
  "event": "prompt_cache_hit",
  "hash": "a1b2c3d4...",
  "age_seconds": 1234.5,
  "model": "claude-sonnet-4-20250514",
  "saved_cost_usd": 0.0234
}
```

**Cache MISS:**
```json
{
  "event": "prompt_cache_miss",
  "hash": "a1b2c3d4...",
  "prompt_length": 1024
}
```

**Cache WRITE:**
```json
{
  "event": "prompt_cached",
  "hash": "a1b2c3d4...",
  "model": "claude-sonnet-4",
  "cost_usd": 0.0234,
  "ttl_hours": 24
}
```

### Métricas

```python
from src.core.observability import record_cache_hit, record_cache_miss

# Automático en PromptCacheService
# Expuesto vía Prometheus metrics
```

### Estadísticas

```python
cache = get_prompt_cache_service()
stats = await cache.get_cache_stats()

print(f"Enabled: {stats['enabled']}")
print(f"TTL: {stats['ttl_hours']} hours")
print(f"Type: {stats['cache_type']}")
```

---

## 🔧 Configuración

### TTL del Cache

El TTL por defecto es **24 horas**. Puedes personalizarlo:

```python
from src.core.ai.prompt_cache import PROMPT_CACHE_TTL_SECONDS

# Default: 24 horas
print(PROMPT_CACHE_TTL_SECONDS)  # 86400

# Custom TTL al guardar
await cache.set_cached_response(
    ...,
    ttl_seconds=60 * 60 * 12,  # 12 horas
)
```

### Infraestructura

El Prompt Cache usa el `CacheService` existente:

1. **Con Redis**: Cache persistente, compartido entre workers
2. **Sin Redis**: Fallback a memoria (solo worker local)

```python
# Configurar Redis (opcional pero recomendado)
REDIS_URL=redis://localhost:6379/0
```

---

## 💰 ROI y Ahorro

### Escenario Real: Análisis de Coherencia

**Sin cache:**
- Requests/día: 1,000
- Costo promedio: $0.05 por análisis
- **Total/mes: $1,500 USD**

**Con cache (50% hit rate):**
- Requests cacheadas: 500 × $0.00 = $0.00
- Requests nuevas: 500 × $0.05 = $25.00
- **Total/mes: $750 USD**
- **Ahorro: $750/mes (50%)**

**Con cache (80% hit rate):**
- Requests cacheadas: 800 × $0.00 = $0.00
- Requests nuevas: 200 × $0.05 = $10.00
- **Total/mes: $300 USD**
- **Ahorro: $1,200/mes (80%)**

### Speedup

- Cache HIT: ~5ms
- API call: ~1,500ms
- **Speedup: 300x** 🚀

---

## 🎯 Casos de Uso Ideales

### ✅ Usa Prompt Cache Para:

1. **Análisis repetidos del mismo proyecto**
   - Usuario revisa proyecto múltiples veces
   - Mismo prompt, misma respuesta

2. **Clasificación de documentos similares**
   - Muchos documentos del mismo tipo
   - Prompts estandarizados

3. **Tareas con temperatura=0.0**
   - Respuestas deterministas
   - Mismo input → mismo output

4. **Validaciones frecuentes**
   - Check de formato
   - Validación de estructura

5. **APIs públicas con prompts comunes**
   - Múltiples usuarios, mismas preguntas
   - Cache compartido (con Redis)

### ❌ NO uses Prompt Cache Para:

1. **Temperature > 0.0**
   - Respuestas no deterministas
   - Cache no útil

2. **Prompts únicos**
   - Cada request diferente
   - 0% hit rate

3. **Datos sensibles one-time**
   - Prompts con PII
   - No beneficio del cache

4. **Análisis exploratorios**
   - Usuario experimenta
   - Prompts siempre cambian

---

## 🔐 Seguridad y Privacidad

### Datos Cacheados

El cache almacena:
- ✅ Hash SHA-256 del input
- ✅ Respuesta de Claude
- ✅ Metadata (tokens, costo, tiempo)

**NO** almacena:
- ❌ API keys
- ❌ Tenant IDs en la key
- ❌ Información de autenticación

### Aislamiento por Tenant

El cache es **compartido** entre tenants para maximizar hit rate.

Si necesitas aislamiento:
```python
# Opción: Incluir tenant_id en el prompt
prompt = f"[Tenant: {tenant_id}] {user_prompt}"
# → Hash diferente por tenant
```

### TTL y Expiración

- Cache expira en 24h automáticamente
- No hay datos obsoletos >24h
- Limpieza automática por Redis

### Invalidación Manual

```python
cache = get_prompt_cache_service()

# Invalidar entrada específica
await cache.invalidate_cache(
    prompt=prompt,
    system_prompt=system_prompt,
    temperature=temperature,
    model=model,
)
```

---

## 📖 Ejemplos Completos

Ver archivo: `apps/api/src/core/ai/example_prompt_cache.py`

Ejecutar:
```bash
cd apps/api
python -m src.core.ai.example_prompt_cache
```

Incluye:
- ✅ Cache hit/miss básico
- ✅ Estabilidad del hash SHA-256
- ✅ Control manual del cache
- ✅ Estadísticas y métricas
- ✅ Comparación de costos

---

## 🔍 Troubleshooting

### Problema: Cache nunca hace HIT

**Verificar:**
1. ¿Cache habilitado?
   ```python
   service.prompt_cache.enabled  # True?
   ```

2. ¿Prompts realmente idénticos?
   ```python
   # Verificar hashes
   hash1 = build_prompt_hash(...)
   hash2 = build_prompt_hash(...)
   print(hash1 == hash2)
   ```

3. ¿TTL expirado?
   - Cache expira en 24h
   - Verificar logs: "prompt_cache_expired"

4. ¿Redis configurado?
   - Sin Redis, cache solo funciona en mismo worker
   - Configurar `REDIS_URL` en environment

### Problema: Hit rate muy bajo (<10%)

**Causas posibles:**
- Temperature > 0.0 (respuestas no deterministas)
- Prompts siempre únicos
- TTL muy corto
- Cache se reinicia frecuentemente

**Solución:**
- Usar temperature=0.0 para tareas repetibles
- Estandarizar prompts cuando sea posible
- Configurar Redis para persistencia

### Problema: Cache usa mucha memoria

**Solución:**
- Configurar Redis con política de eviction:
  ```
  maxmemory 1gb
  maxmemory-policy allkeys-lru
  ```
- Reducir TTL si es necesario
- Monitor memoria con `redis-cli INFO memory`

---

## 📚 Referencias

- [Código: prompt_cache.py](./prompt_cache.py)
- [Integración: service.py](./service.py)
- [Cache Core: core/cache.py](../../core/cache.py)
- [Ejemplos: example_prompt_cache.py](./example_prompt_cache.py)

---

## 📝 Changelog

### v1.0.0 (2026-01-09)

**Implementado:**
- ✅ Hash SHA-256 del input completo
- ✅ TTL de 24 horas
- ✅ Integración con AIService
- ✅ Redis + fallback memoria
- ✅ Métricas hit/miss automáticas
- ✅ Documentación completa
- ✅ Ejemplos de uso

**Estado:** ✅ READY FOR PRODUCTION

**Tarea:** CE-S2-006 - Caché de Prompts Idénticos

---

**Autor:** C2Pro AI Team
**Versión:** 1.0.0
**Última Actualización:** 2026-01-09

