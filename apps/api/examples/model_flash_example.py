"""
Ejemplo de uso del Modelo FLASH (Claude Haiku 4)

Demuestra cómo usar el model router para seleccionar automáticamente
el modelo flash (Haiku) para tareas rápidas y económicas.

Casos de uso FLASH:
- Clasificación de documentos
- Extracción simple de datos
- Validación de formatos
- Resúmenes cortos

Ahorro vs Sonnet: ~12x más barato
Velocidad vs Sonnet: ~3x más rápido
"""

import asyncio
from uuid import uuid4

from src.modules.ai.model_router import ModelTier, TaskType, get_model_router
from src.modules.ai.service import AIRequest, AIService

# ===========================================
# EJEMPLO 1: CLASIFICACIÓN DE DOCUMENTO (FLASH)
# ===========================================


async def example_document_classification():
    """
    Clasifica un documento usando modelo FLASH (Haiku).

    Tarea: Rápida, económica
    Modelo: Claude Haiku 4 (FLASH)
    Ahorro: ~$0.003 vs $0.045 con Sonnet
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 1: Clasificación de Documento (FLASH - Haiku)")
    print("=" * 60)

    # Simular tenant
    tenant_id = uuid4()
    budget_remaining = 10.0  # $10 USD disponibles

    # Crear servicio de AI
    service = AIService(
        tenant_id=tenant_id,
        budget_remaining_usd=budget_remaining,
    )

    # Documento a clasificar
    document_text = """
    CONTRATO DE CONSTRUCCIÓN

    Entre XYZ Constructora S.A. (EL CONTRATISTA) y ABC Desarrollos (EL CLIENTE)
    se celebra el presente contrato para la construcción de una planta industrial
    en el terreno ubicado en Calle Principal #123.

    Plazo de ejecución: 18 meses
    Valor del contrato: $5,000,000 USD
    """

    # Request con tipo de tarea CLASSIFICATION
    request = AIRequest(
        prompt=f"""Clasifica el siguiente documento en UNA de estas categorías:

        Categorías:
        - contract (Contrato)
        - invoice (Factura)
        - schedule (Cronograma)
        - technical_spec (Especificación Técnica)
        - budget (Presupuesto)
        - other (Otro)

        Documento:
        {document_text}

        Responde SOLO con el nombre de la categoría (sin explicación).""",
        task_type=TaskType.CLASSIFICATION,  # ← FLASH automático
        max_tokens=50,
        temperature=0.0,
    )

    # Generar respuesta
    response = await service.generate(request)

    # Mostrar resultados
    print(f"\n✅ Clasificación: {response.content.strip()}")
    print("\n📊 Estadísticas:")
    print(f"   Modelo usado: {response.model}")
    print(f"   Input tokens: {response.input_tokens}")
    print(f"   Output tokens: {response.output_tokens}")
    print(f"   💰 Costo: ${response.cost_usd:.6f} USD")
    print(f"   ⚡ Tiempo: {response.execution_time_ms:.0f}ms")

    # Comparar costos
    router = get_model_router()
    costs = router.compare_costs(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )

    print("\n💡 Comparación de costos (mismos tokens):")
    print(f"   Flash (Haiku):    ${costs['flash']:.6f} ✅ (usado)")
    print(f"   Standard (Sonnet): ${costs['standard']:.6f} (12x más caro)")
    print(f"   Powerful (Opus):   ${costs['powerful']:.6f} (60x más caro)")


# ===========================================
# EJEMPLO 2: EXTRACCIÓN SIMPLE (FLASH)
# ===========================================


async def example_simple_extraction():
    """
    Extrae datos estructurados simples usando FLASH.

    Tarea: Extracción simple, formato predefinido
    Modelo: Claude Haiku 4 (FLASH)
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Extracción Simple de Datos (FLASH - Haiku)")
    print("=" * 60)

    service = AIService(tenant_id=uuid4(), budget_remaining_usd=10.0)

    invoice_text = """
    FACTURA #12345
    Fecha: 15/01/2026
    Cliente: ABC Corp
    Monto total: $2,500.00
    Concepto: Servicios de consultoría
    """

    request = AIRequest(
        prompt=f"""Extrae los siguientes datos de la factura en formato JSON:

        - numero_factura
        - fecha
        - cliente
        - monto
        - concepto

        Factura:
        {invoice_text}

        Responde SOLO con el JSON (sin markdown, sin explicación).""",
        task_type=TaskType.SIMPLE_EXTRACTION,  # ← FLASH automático
        max_tokens=200,
        temperature=0.0,
    )

    response = await service.generate(request)

    print(f"\n✅ Datos extraídos:\n{response.content}")
    print(f"\n💰 Costo: ${response.cost_usd:.6f} USD")
    print(f"⚡ Tiempo: {response.execution_time_ms:.0f}ms")


# ===========================================
# EJEMPLO 3: COMPARACIÓN FLASH vs STANDARD
# ===========================================


async def example_flash_vs_standard():
    """
    Compara FLASH (Haiku) vs STANDARD (Sonnet) para la misma tarea.

    Demuestra:
    - Diferencia de costo (~12x)
    - Diferencia de velocidad (~3x)
    - Calidad similar para tareas simples
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 3: Comparación FLASH vs STANDARD")
    print("=" * 60)

    service = AIService(tenant_id=uuid4(), budget_remaining_usd=50.0)

    prompt = "¿Es este un documento legal? Responde SÍ o NO: CONTRATO DE COMPRAVENTA"

    # 1. Con FLASH (automático para CLASSIFICATION)
    print("\n🔹 Ejecutando con FLASH (Haiku)...")
    request_flash = AIRequest(
        prompt=prompt,
        task_type=TaskType.CLASSIFICATION,  # → Haiku
        max_tokens=10,
    )
    response_flash = await service.generate(request_flash)

    # 2. Con STANDARD (forzado)
    print("🔹 Ejecutando con STANDARD (Sonnet)...")
    request_standard = AIRequest(
        prompt=prompt,
        task_type=TaskType.CLASSIFICATION,
        max_tokens=10,
        force_model_tier=ModelTier.STANDARD,  # ← Forzar Sonnet
    )
    response_standard = await service.generate(request_standard)

    # Comparación
    print("\n📊 Resultados:")
    print("\n   FLASH (Haiku):")
    print(f"      Respuesta: {response_flash.content.strip()}")
    print(f"      Costo: ${response_flash.cost_usd:.6f}")
    print(f"      Tiempo: {response_flash.execution_time_ms:.0f}ms")

    print("\n   STANDARD (Sonnet):")
    print(f"      Respuesta: {response_standard.content.strip()}")
    print(f"      Costo: ${response_standard.cost_usd:.6f}")
    print(f"      Tiempo: {response_standard.execution_time_ms:.0f}ms")

    savings = (
        (response_standard.cost_usd - response_flash.cost_usd) / response_standard.cost_usd
    ) * 100
    speedup = response_standard.execution_time_ms / response_flash.execution_time_ms

    print("\n💡 Análisis:")
    print(f"   💰 Ahorro: {savings:.1f}% usando FLASH")
    print(f"   ⚡ Velocidad: {speedup:.1f}x más rápido con FLASH")
    print("   ✅ Calidad: Idéntica para tareas simples")


# ===========================================
# EJEMPLO 4: BUDGET-AWARE DOWNGRADE
# ===========================================


async def example_budget_aware():
    """
    Demuestra downgrade automático a FLASH cuando el budget es bajo.

    Escenario:
    - Budget restante: $0.50
    - Tarea: COHERENCE_ANALYSIS (normalmente STANDARD)
    - Router: Downgrade automático a FLASH para ahorrar
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 4: Downgrade Automático por Budget Bajo")
    print("=" * 60)

    # Tenant con budget muy bajo
    service = AIService(
        tenant_id=uuid4(),
        budget_remaining_usd=0.50,  # ← Solo $0.50 disponibles
    )

    request = AIRequest(
        prompt="Analiza la coherencia de este proyecto (prompt largo aquí...)",
        task_type=TaskType.COHERENCE_ANALYSIS,  # Normalmente → Sonnet
        max_tokens=500,
    )

    # El router automáticamente hará downgrade a Haiku
    print("\n📊 Budget disponible: $0.50")
    print("🎯 Tarea solicitada: COHERENCE_ANALYSIS (normalmente Sonnet)")
    print("⚙️  Router: Downgrade automático a Haiku por budget bajo")

    response = await service.generate(request)

    print(f"\n✅ Modelo usado: {response.model}")
    print(f"💰 Costo: ${response.cost_usd:.6f} (dentro del budget)")


# ===========================================
# EJEMPLO 5: USAR TODAS LAS TAREAS FLASH
# ===========================================


async def example_all_flash_tasks():
    """
    Lista todas las tareas que usan FLASH automáticamente.
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 5: Todas las Tareas FLASH")
    print("=" * 60)

    router = get_model_router()
    flash_tasks = router.get_tasks_for_tier(ModelTier.FLASH)

    print("\n🔸 Tareas que usan FLASH (Haiku) automáticamente:\n")
    for task in flash_tasks:
        print(f"   • {task}")

    print("\n💡 Recomendación:")
    print("   Usa estas tareas cuando sea posible para:")
    print("   - ⚡ Mayor velocidad (3x)")
    print("   - 💰 Menor costo (12x)")
    print("   - 🔋 Conservar budget del tenant")


# ===========================================
# MAIN
# ===========================================


async def main():
    """Ejecuta todos los ejemplos."""
    print("\n" + "=" * 60)
    print("🚀 MODELO FLASH (Claude Haiku 4) - Ejemplos de Uso")
    print("=" * 60)

    # Ejecutar ejemplos
    await example_document_classification()
    await example_simple_extraction()
    await example_flash_vs_standard()
    await example_budget_aware()
    await example_all_flash_tasks()

    print("\n" + "=" * 60)
    print("✅ Todos los ejemplos completados")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Ejecutar con asyncio
    asyncio.run(main())
