"""
Ejemplo de uso del Prompt Cache

Demuestra:
- Cache HIT en segunda llamada idéntica
- Ahorro de costos con cache
- Ahorro de tiempo de ejecución
- Control manual de cache (use_cache)

Usage:
    cd apps/api
    python -m src.core.ai.example_prompt_cache
"""

import asyncio
import time
from uuid import uuid4

from src.core.ai.model_router import TaskType
from src.core.ai.prompt_cache import build_prompt_hash, get_prompt_cache_service
from src.core.ai.service import AIRequest, AIService


async def example_basic_cache() -> None:
    """Ejemplo básico de cache hit/miss."""
    print("=" * 60)
    print("EJEMPLO 1: Cache Hit/Miss Básico")
    print("=" * 60)

    # Simular tenant ID
    tenant_id = uuid4()

    # Crear servicio de AI
    service = AIService(tenant_id=tenant_id)

    prompt = "Clasifica este documento: Este es un contrato de servicios de construcción."

    # Primera llamada - Cache MISS
    print("\n[1] Primera llamada - Esperamos CACHE MISS...")
    start = time.perf_counter()
    request1 = AIRequest(
        prompt=prompt,
        task_type=TaskType.CLASSIFICATION,
        temperature=0.0,
        use_cache=True,  # Habilitar cache
    )

    # Nota: Esta llamada fallará sin API key válida
    # En producción, funcionará correctamente
    try:
        response1 = await service.generate(request1)
        elapsed1 = (time.perf_counter() - start) * 1000

        print(f"✅ Respuesta: {response1.content[:100]}...")
        print(f"   Modelo: {response1.model}")
        print(f"   Costo: ${response1.cost_usd:.6f}")
        print(f"   Tiempo: {elapsed1:.0f}ms")
        print(f"   Cached: {response1.cached}")

        # Segunda llamada idéntica - Cache HIT
        print("\n[2] Segunda llamada (prompt idéntico) - Esperamos CACHE HIT...")
        start = time.perf_counter()
        request2 = AIRequest(
            prompt=prompt,  # Mismo prompt
            task_type=TaskType.CLASSIFICATION,
            temperature=0.0,  # Mismos parámetros
            use_cache=True,
        )

        response2 = await service.generate(request2)
        elapsed2 = (time.perf_counter() - start) * 1000

        print(f"✅ Respuesta: {response2.content[:100]}...")
        print(f"   Modelo: {response2.model}")
        print(f"   Costo: ${response2.cost_usd:.6f} (¡$0 porque es cached!)")
        print(f"   Tiempo: {elapsed2:.0f}ms")
        print(f"   Cached: {response2.cached}")

        # Estadísticas
        print("\n📊 Ahorro con Cache:")
        print(f"   Costo ahorrado: ${response1.cost_usd:.6f}")
        print(f"   Tiempo ahorrado: ~{elapsed1 - elapsed2:.0f}ms")
        print(f"   Speedup: {elapsed1 / elapsed2:.1f}x")

    except Exception as e:
        print(f"⚠️  Demo sin API key: {e}")
        print("   (En producción, el cache funcionaría correctamente)")


async def example_hash_stability() -> None:
    """Ejemplo de estabilidad del hash SHA-256."""
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Estabilidad del Hash SHA-256")
    print("=" * 60)

    prompt = "Analiza la coherencia de este proyecto"

    # Mismo prompt, mismos parámetros → mismo hash
    hash1 = build_prompt_hash(
        prompt=prompt, system_prompt="Eres experto", temperature=0.0, model="claude-sonnet-4"
    )

    hash2 = build_prompt_hash(
        prompt=prompt, system_prompt="Eres experto", temperature=0.0, model="claude-sonnet-4"
    )

    print(f"\n[1] Hash 1: {hash1[:32]}...")
    print(f"[2] Hash 2: {hash2[:32]}...")
    print(f"✅ Hashes idénticos: {hash1 == hash2}")

    # Cambiar un parámetro → hash diferente
    hash3 = build_prompt_hash(
        prompt=prompt,
        system_prompt="Eres experto",
        temperature=0.5,
        model="claude-sonnet-4",  # Cambio
    )

    print(f"\n[3] Hash 3 (temperature=0.5): {hash3[:32]}...")
    print(f"❌ Hash diferente: {hash1 != hash3}")

    print("\n📝 Conclusión:")
    print("   - Prompts idénticos → mismo hash → cache HIT")
    print("   - Cualquier cambio → hash diferente → cache MISS")


async def example_cache_control() -> None:
    """Ejemplo de control manual del cache."""
    print("\n" + "=" * 60)
    print("EJEMPLO 3: Control Manual del Cache")
    print("=" * 60)

    service = AIService(tenant_id=uuid4())

    prompt = "Resume este texto: Claude es un modelo de lenguaje avanzado."

    try:
        # Con cache habilitado (default)
        print("\n[1] Request con use_cache=True")
        request1 = AIRequest(prompt=prompt, task_type=TaskType.SUMMARIZATION_SHORT, use_cache=True)
        await service.generate(request1)
        print("   Cache enabled: Sí")

        # Sin cache (forzar llamada a API)
        print("\n[2] Request con use_cache=False (forzar API)")
        request2 = AIRequest(
            prompt=prompt,
            task_type=TaskType.SUMMARIZATION_SHORT,
            use_cache=False,  # Desactivar cache
        )
        await service.generate(request2)
        print("   Cache enabled: No")
        print("   Resultado: Siempre llama a la API, aunque el prompt sea idéntico")

    except Exception as e:
        print(f"⚠️  Demo sin API key: {e}")


async def example_cache_stats() -> None:
    """Ejemplo de estadísticas del cache."""
    print("\n" + "=" * 60)
    print("EJEMPLO 4: Estadísticas del Cache")
    print("=" * 60)

    cache = get_prompt_cache_service()

    stats = await cache.get_cache_stats()

    print("\n📊 Configuración del Cache:")
    print(f"   Enabled: {stats['enabled']}")
    print(f"   TTL: {stats['ttl_hours']} horas")
    print(f"   Cache Type: {stats['cache_type']}")

    print("\n💡 Observabilidad:")
    print("   - Hit/Miss se registran en logs estructurados")
    print("   - Métricas disponibles vía observability module")
    print("   - Compatible con Prometheus/Grafana")


async def main() -> None:
    """Ejecuta todos los ejemplos."""
    print("\n🚀 C2Pro - Prompt Cache Examples\n")

    await example_basic_cache()
    await example_hash_stability()
    await example_cache_control()
    await example_cache_stats()

    print("\n" + "=" * 60)
    print("✅ Ejemplos completados")
    print("=" * 60)
    print("\n📚 Más info:")
    print("   - Documentación: apps/api/src/core/ai/README_PROMPT_CACHE.md")
    print("   - Código: apps/api/src/core/ai/prompt_cache.py")
    print("   - Service: apps/api/src/core/ai/service.py")


if __name__ == "__main__":
    asyncio.run(main())

