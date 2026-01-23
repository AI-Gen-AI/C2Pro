"""
C2Pro - Ejemplo de uso: Prompt Templates con AIService

Este script muestra cómo usar el sistema de plantillas de prompts
versionadas con el AIService para trazabilidad completa.

Flujo:
1. PromptManager renderiza el template + retorna versión
2. AIService ejecuta la llamada a Claude
3. AIResponse incluye prompt_version para logging
4. Se guarda en ai_usage_logs para auditoría

Ejecutar:
    python -m src.modules.ai.example_prompts

Author: C2Pro Team
Date: 2026-01-13
"""

import asyncio
from uuid import uuid4

from src.modules.ai.prompts import get_prompt_manager
from src.modules.ai.service import AIRequest, AIService, TaskType

# ===========================================
# EJEMPLO 1: EXTRACCIÓN DE CONTRATOS
# ===========================================


async def example_contract_extraction():
    """
    Ejemplo: Extraer información de un contrato usando templates versionados.
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 1: EXTRACCIÓN DE CONTRATO CON TEMPLATES")
    print("=" * 60 + "\n")

    # 1. Preparar el contexto (datos del documento)
    document_text = """
    CONTRATO DE CONSTRUCCIÓN

    Entre la Municipalidad de Santiago (en adelante "EL MANDANTE")
    y CONSTRUCTORA EJEMPLO S.A. (en adelante "EL CONTRATISTA")

    OBJETO: Construcción de Plaza Pública en Av. Libertador 1234

    MONTO: El monto total del contrato es de $150.000.000 CLP (IVA incluido)

    PLAZO:
    - Inicio de obras: 2026-02-01
    - Término de obras: 2026-08-31

    CLÁUSULA 3.1 - GARANTÍAS:
    El contratista debe constituir las siguientes garantías:
    - Fiel cumplimiento: 5% del monto total
    - Buena calidad: 3% del monto total
    """

    context = {
        "document_text": document_text,
        "max_clauses": 5,
    }

    # 2. Obtener el PromptManager
    prompt_manager = get_prompt_manager()

    # 3. Renderizar el template (obtener system + user prompts + versión)
    system_prompt, user_prompt, prompt_version = prompt_manager.render_prompt(
        task_name="contract_extraction",
        context=context,
        version="latest",  # o "1.0" para versión específica
    )

    print(f"📋 Template usado: contract_extraction v{prompt_version}")
    print(f"📏 System prompt: {len(system_prompt)} chars")
    print(f"📏 User prompt: {len(user_prompt)} chars")
    print(f"\n--- SYSTEM PROMPT (primeros 200 chars) ---")
    print(system_prompt[:200] + "...\n")
    print(f"--- USER PROMPT (primeros 300 chars) ---")
    print(user_prompt[:300] + "...\n")

    # 4. Crear AIService
    service = AIService(
        tenant_id=uuid4(),
        budget_remaining_usd=10.0,
    )

    # 5. Crear request con el prompt renderizado + versión
    ai_request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_type=TaskType.COMPLEX_EXTRACTION,
        prompt_version=prompt_version,  # ¡CRÍTICO! Para ai_usage_logs
        max_tokens=4000,
        temperature=0.0,
    )

    # 6. Ejecutar
    print("🚀 Ejecutando llamada a Claude API...\n")

    try:
        response = await service.generate(ai_request)

        print("✅ Respuesta recibida:")
        print(f"   - Modelo: {response.model}")
        print(f"   - Prompt Version: {response.prompt_version}")  # ← Para auditoría
        print(f"   - Input tokens: {response.input_tokens}")
        print(f"   - Output tokens: {response.output_tokens}")
        print(f"   - Costo: ${response.cost_usd:.4f}")
        print(f"   - Cached: {response.cached}")
        print(f"   - Tiempo: {response.execution_time_ms:.2f}ms")
        print(f"\n--- CONTENIDO EXTRAÍDO (primeros 500 chars) ---")
        print(response.content[:500] + "...\n")

        # NOTA: En producción, aquí se guardaría en ai_usage_logs:
        # await save_to_ai_usage_logs(
        #     tenant_id=tenant_id,
        #     model=response.model,
        #     operation="contract_extraction",
        #     prompt_version=response.prompt_version,  # ← Trazabilidad
        #     input_tokens=response.input_tokens,
        #     output_tokens=response.output_tokens,
        #     cost_usd=response.cost_usd,
        # )

        return response

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


# ===========================================
# EJEMPLO 2: CLASIFICACIÓN DE STAKEHOLDERS
# ===========================================


async def example_stakeholder_classification():
    """
    Ejemplo: Clasificar stakeholders usando templates versionados.
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 2: CLASIFICACIÓN DE STAKEHOLDERS CON TEMPLATES")
    print("=" * 60 + "\n")

    # 1. Preparar contexto
    context = {
        "project_description": "Construcción de hospital público en la comuna de Maipú, Santiago. Presupuesto: $50MM USD. Plazo: 36 meses.",
        "stakeholders": [
            {"name": "Ministerio de Salud", "role": "Financista y mandante"},
            {"name": "Alcaldía de Maipú", "role": "Autoridad local"},
            {"name": "Vecinos sector norte", "role": "Comunidad afectada"},
            {"name": "CONSTRUCTORA ABC", "role": "Contratista principal"},
            {"name": "Colegio Médico", "role": "Usuarios finales"},
        ],
    }

    # 2. Renderizar template
    prompt_manager = get_prompt_manager()
    system_prompt, user_prompt, prompt_version = prompt_manager.render_prompt(
        task_name="stakeholder_classification",
        context=context,
        version="1.0",
    )

    print(f"📋 Template usado: stakeholder_classification v{prompt_version}")
    print(f"📏 Stakeholders a analizar: {len(context['stakeholders'])}\n")

    # 3. Crear request
    service = AIService(tenant_id=uuid4())

    ai_request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_type=TaskType.SIMPLE_EXTRACTION,
        prompt_version=prompt_version,
        max_tokens=3000,
    )

    # 4. Ejecutar
    print("🚀 Ejecutando clasificación...\n")

    try:
        response = await service.generate(ai_request)

        print("✅ Clasificación completada:")
        print(f"   - Modelo: {response.model}")
        print(f"   - Prompt Version: {response.prompt_version}")
        print(f"   - Costo: ${response.cost_usd:.4f}")
        print(f"\n--- CLASIFICACIONES (primeros 600 chars) ---")
        print(response.content[:600] + "...\n")

        return response

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


# ===========================================
# EJEMPLO 3: VERIFICACIÓN DE COHERENCIA
# ===========================================


async def example_coherence_check():
    """
    Ejemplo: Verificar coherencia entre documentos usando templates.
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 3: VERIFICACIÓN DE COHERENCIA CON TEMPLATES")
    print("=" * 60 + "\n")

    # 1. Preparar contexto con múltiples documentos
    context = {
        "document_pairs": [
            {
                "name": "Contrato Principal",
                "content": """
                MONTO TOTAL: $150.000.000 CLP
                INICIO: 2026-02-01
                TÉRMINO: 2026-08-31
                Plazo: 7 meses
                """,
            },
            {
                "name": "Cronograma de Obra",
                "content": """
                Inicio obras: 01-Feb-2026
                Hito 1 (fundaciones): 15-Mar-2026
                Hito 2 (estructura): 30-Abr-2026
                Término: 15-Sep-2026
                Duración total: 7.5 meses
                """,
            },
        ],
        "check_types": ["fecha", "monto"],
    }

    # 2. Renderizar template
    prompt_manager = get_prompt_manager()
    system_prompt, user_prompt, prompt_version = prompt_manager.render_prompt(
        task_name="coherence_check",
        context=context,
        version="latest",
    )

    print(f"📋 Template usado: coherence_check v{prompt_version}")
    print(f"📏 Documentos a comparar: {len(context['document_pairs'])}\n")

    # 3. Ejecutar verificación
    service = AIService(tenant_id=uuid4())

    ai_request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_type="coherence_analysis",
        prompt_version=prompt_version,
        max_tokens=3000,
    )

    print("🚀 Verificando coherencia...\n")

    try:
        response = await service.generate(ai_request)

        print("✅ Verificación completada:")
        print(f"   - Modelo: {response.model}")
        print(f"   - Prompt Version: {response.prompt_version}")
        print(f"   - Costo: ${response.cost_usd:.4f}")
        print(f"\n--- ANÁLISIS DE COHERENCIA (primeros 700 chars) ---")
        print(response.content[:700] + "...\n")

        return response

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


# ===========================================
# EJEMPLO 4: LISTAR TEMPLATES DISPONIBLES
# ===========================================


def example_list_templates():
    """
    Ejemplo: Explorar templates disponibles en el sistema.
    """
    print("\n" + "=" * 60)
    print("EJEMPLO 4: EXPLORAR TEMPLATES DISPONIBLES")
    print("=" * 60 + "\n")

    prompt_manager = get_prompt_manager()

    # Listar todas las tareas
    tasks = prompt_manager.list_tasks()

    print(f"📚 Templates disponibles: {len(tasks)}\n")

    for task_name in tasks:
        print(f"📋 Tarea: {task_name}")

        # Listar versiones
        versions = prompt_manager.list_versions(task_name)
        print(f"   Versiones: {', '.join(versions)}")

        # Obtener info de la última versión
        info = prompt_manager.get_template_info(task_name, version="latest")
        print(f"   Descripción: {info['description']}")
        print(f"   Autor: {info['metadata'].get('author', 'N/A')}")
        print(f"   Fecha: {info['metadata'].get('date', 'N/A')}")
        print()


# ===========================================
# MAIN
# ===========================================


async def main():
    """Ejecuta todos los ejemplos."""
    print("\n🚀 C2PRO - SISTEMA DE PROMPT TEMPLATES\n")
    print("Este demo muestra el flujo completo de:")
    print("  1. PromptManager.render_prompt() → (system, user, version)")
    print("  2. AIService.generate() → AIResponse")
    print("  3. Logging de prompt_version para auditoría\n")
    print("=" * 60)

    # Ejemplo 4: Listar templates (no requiere API)
    example_list_templates()

    # NOTA: Los siguientes ejemplos hacen llamadas reales a Claude API
    # Descomentar solo si tienes ANTHROPIC_API_KEY configurada

    # await example_contract_extraction()
    # await example_stakeholder_classification()
    # await example_coherence_check()

    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETADO")
    print("=" * 60)
    print("\nPara ejecutar los ejemplos con API real:")
    print("1. Configura ANTHROPIC_API_KEY en .env")
    print("2. Descomenta las líneas en main()")
    print("3. python -m src.modules.ai.example_prompts\n")


if __name__ == "__main__":
    asyncio.run(main())
