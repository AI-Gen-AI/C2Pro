"""
Ejemplo de uso del LLM Client Wrapper

Demuestra:
- Retry automático con exponential backoff
- Logging estructurado
- Cost tracking
- Circuit breaker
- Manejo de errores

Usage:
    cd apps/api
    python -m src.modules.ai.example_llm_client
"""

import asyncio
from uuid import uuid4

from src.modules.ai.llm_client import LLMRequest, create_llm_client


async def example_basic_usage():
    """Ejemplo básico de uso del LLM Client."""
    print("=" * 60)
    print("EJEMPLO 1: Uso Básico")
    print("=" * 60)

    # Crear cliente
    client = create_llm_client(max_retries=3)

    # Crear request
    request = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": "¿Qué es un contrato de construcción?"}],
        max_tokens=200,
        temperature=0.0,
        tenant_id=uuid4(),
        task_type="classification",
    )

    print(f"\n📤 Request ID: {request.request_id}")
    print(f"   Model: {request.model}")
    print(f"   Max retries: {client.max_retries}")

    try:
        # Generar respuesta
        response = await client.generate(request)

        print("\n✅ Response:")
        print(f"   Content: {response.content[:100]}...")
        print(f"   Input tokens: {response.input_tokens}")
        print(f"   Output tokens: {response.output_tokens}")
        print(f"   Cost: ${response.cost_usd:.6f}")
        print(f"   Execution time: {response.execution_time_ms:.0f}ms")
        print(f"   Retries: {response.retries}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   (Demo sin API key válida)")


async def example_retry_behavior():
    """Ejemplo de comportamiento de retry."""
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Retry Behavior")
    print("=" * 60)

    client = create_llm_client(
        max_retries=3,
        enable_circuit_breaker=True,
    )

    print("\n⚙️  Configuración:")
    print(f"   Max retries: {client.max_retries}")
    print(f"   Initial delay: {client.initial_retry_delay}s")
    print(f"   Max delay: {client.max_retry_delay}s")
    print(f"   Backoff multiplier: {client.backoff_multiplier}x")
    print("   Circuit breaker: Enabled")

    print("\n📊 Retry delays (exponential backoff):")
    for attempt in range(4):
        delay = client._calculate_retry_delay(attempt, error_type="server_error")
        print(f"   Attempt {attempt + 1}: ~{delay:.1f}s")


async def example_circuit_breaker():
    """Ejemplo de circuit breaker."""
    print("\n" + "=" * 60)
    print("EJEMPLO 3: Circuit Breaker")
    print("=" * 60)

    client = create_llm_client(enable_circuit_breaker=True)

    print("\n🔌 Circuit Breaker:")
    print(f"   State: {client.circuit_breaker.get_state()}")
    print(f"   Failure threshold: {client.circuit_breaker.failure_threshold}")
    print(f"   Recovery timeout: {client.circuit_breaker.recovery_timeout}s")

    print("\n💡 Comportamiento:")
    print("   - CLOSED: Normal operation")
    print(f"   - OPEN: Reject requests after {client.circuit_breaker.failure_threshold} failures")
    print("   - HALF_OPEN: Testing recovery")

    # Simular fallos
    print("\n🔨 Simulando 5 fallos...")
    for i in range(5):
        client.circuit_breaker.record_failure()
        print(f"   Failure {i + 1}: State = {client.circuit_breaker.get_state()}")

    print("\n🛑 Circuit breaker OPENED after threshold")

    # Verificar si puede ejecutar
    can_execute = client.circuit_breaker.can_execute()
    print(f"\n❓ Can execute request? {can_execute}")


async def example_cost_tracking():
    """Ejemplo de cost tracking."""
    print("\n" + "=" * 60)
    print("EJEMPLO 4: Cost Tracking")
    print("=" * 60)

    client = create_llm_client()

    # Simular costs
    print("\n💰 Cost Calculation:")
    print("   Model: Sonnet-4")
    print("   Input: 1,000 tokens × $3.00/1M = $0.003000")
    print("   Output: 500 tokens × $15.00/1M = $0.007500")
    print("   Total: $0.010500")

    cost = client._calculate_cost("claude-sonnet-4", 1000, 500)
    print(f"\n   Calculated: ${cost:.6f}")

    # Statistics
    stats = client.get_statistics()
    print("\n📊 Client Statistics:")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Total retries: {stats['total_retries']}")
    print(f"   Total cost: ${stats['total_cost_usd']:.2f}")
    print(f"   Avg retries/request: {stats['avg_retries_per_request']:.2f}")


async def example_error_classification():
    """Ejemplo de clasificación de errores."""
    print("\n" + "=" * 60)
    print("EJEMPLO 5: Error Classification")
    print("=" * 60)

    client = create_llm_client()

    print("\n🏷️  Tipos de errores:")
    print("   rate_limit      → Retry con delay largo")
    print("   server_error    → Retry con backoff")
    print("   timeout         → Retry")
    print("   connection      → Retry")
    print("   authentication  → NO retry (fatal)")
    print("   invalid_request → NO retry (fatal)")
    print("   not_found       → NO retry (fatal)")

    print("\n📋 Retry strategy:")
    print("   1. Classify error type")
    print("   2. Check if retryable")
    print("   3. Calculate delay (exponential backoff)")
    print("   4. Wait and retry")
    print("   5. Record in circuit breaker")


async def example_logging():
    """Ejemplo de logging estructurado."""
    print("\n" + "=" * 60)
    print("EJEMPLO 6: Structured Logging")
    print("=" * 60)

    print("\n📝 Logs generados:")
    print("\n   llm_client_initialized:")
    print("     - max_retries")
    print("     - timeout_seconds")
    print("     - circuit_breaker_enabled")

    print("\n   llm_request_started:")
    print("     - request_id")
    print("     - tenant_id")
    print("     - model")
    print("     - task_type")

    print("\n   llm_request_attempt_failed:")
    print("     - attempt")
    print("     - error_type")
    print("     - error_message")

    print("\n   llm_request_retrying:")
    print("     - delay_seconds")
    print("     - error_type")

    print("\n   llm_request_success:")
    print("     - input_tokens")
    print("     - output_tokens")
    print("     - cost_usd")
    print("     - execution_time_ms")
    print("     - retries")

    print("\n   llm_request_failed:")
    print("     - total_attempts")
    print("     - final_error")


async def main():
    """Ejecuta todos los ejemplos."""
    print("\n🚀 C2Pro - LLM Client Wrapper Examples\n")

    await example_basic_usage()
    await example_retry_behavior()
    await example_circuit_breaker()
    await example_cost_tracking()
    await example_error_classification()
    await example_logging()

    print("\n" + "=" * 60)
    print("✅ Ejemplos completados")
    print("=" * 60)
    print("\n📚 Más info:")
    print("   - Documentación: apps/api/src/modules/ai/README_LLM_CLIENT.md")
    print("   - Código: apps/api/src/modules/ai/llm_client.py")
    print("   - Service: apps/api/src/modules/ai/service.py")


if __name__ == "__main__":
    asyncio.run(main())
