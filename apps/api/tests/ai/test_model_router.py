"""
Tests para Model Router

Valida que el routing de modelos funciona correctamente:
- Selección automática por TaskType
- Downgrade por budget
- Downgrade por tamaño
- Cost estimation
"""

import pytest

from src.modules.ai.model_router import (
    ModelRouter,
    ModelTier,
    TaskType,
    get_model_router,
)

# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def router():
    """Crea instancia de ModelRouter."""
    return ModelRouter()


# ===========================================
# TEST 1: AUTOMATIC FLASH SELECTION
# ===========================================


@pytest.mark.asyncio
async def test_flash_selected_for_classification(router: ModelRouter):
    """
    Test: TaskType.CLASSIFICATION selecciona FLASH (Haiku).
    """
    model = router.select_model(
        task_type=TaskType.CLASSIFICATION,
        input_token_estimate=1000,
    )

    assert model.tier == ModelTier.FLASH
    assert "haiku" in model.name.lower()


@pytest.mark.asyncio
async def test_flash_selected_for_simple_extraction(router: ModelRouter):
    """Test: TaskType.SIMPLE_EXTRACTION selecciona FLASH."""
    model = router.select_model(
        task_type=TaskType.SIMPLE_EXTRACTION,
        input_token_estimate=1000,
    )

    assert model.tier == ModelTier.FLASH


@pytest.mark.asyncio
async def test_flash_selected_for_validation(router: ModelRouter):
    """Test: TaskType.VALIDATION selecciona FLASH."""
    model = router.select_model(
        task_type=TaskType.VALIDATION,
        input_token_estimate=500,
    )

    assert model.tier == ModelTier.FLASH


# ===========================================
# TEST 2: STANDARD SELECTION
# ===========================================


@pytest.mark.asyncio
async def test_standard_selected_for_coherence_analysis(router: ModelRouter):
    """Test: TaskType.COHERENCE_ANALYSIS selecciona STANDARD (Sonnet)."""
    model = router.select_model(
        task_type=TaskType.COHERENCE_ANALYSIS,
        input_token_estimate=5000,
    )

    assert model.tier == ModelTier.STANDARD
    assert "sonnet" in model.name.lower()


@pytest.mark.asyncio
async def test_standard_selected_for_complex_extraction(router: ModelRouter):
    """Test: TaskType.COMPLEX_EXTRACTION selecciona STANDARD."""
    model = router.select_model(
        task_type=TaskType.COMPLEX_EXTRACTION,
        input_token_estimate=10000,
    )

    assert model.tier == ModelTier.STANDARD


# ===========================================
# TEST 3: BUDGET-BASED DOWNGRADE
# ===========================================


@pytest.mark.asyncio
async def test_downgrade_to_flash_when_budget_low(router: ModelRouter):
    """
    Test CRÍTICO: Downgrade a FLASH cuando budget < $1.

    Escenario:
    - Tarea: COHERENCE_ANALYSIS (normalmente STANDARD)
    - Budget: $0.50
    - Esperado: Downgrade a FLASH
    """
    model = router.select_model(
        task_type=TaskType.COHERENCE_ANALYSIS,
        input_token_estimate=5000,
        budget_remaining_usd=0.50,  # Budget bajo
    )

    # Debe hacer downgrade a FLASH
    assert model.tier == ModelTier.FLASH


@pytest.mark.asyncio
async def test_no_downgrade_when_budget_sufficient(router: ModelRouter):
    """Test: NO hace downgrade si budget suficiente."""
    model = router.select_model(
        task_type=TaskType.COHERENCE_ANALYSIS,
        input_token_estimate=5000,
        budget_remaining_usd=10.0,  # Budget alto
    )

    # Debe usar STANDARD
    assert model.tier == ModelTier.STANDARD


# ===========================================
# TEST 4: SIZE-BASED FALLBACK
# ===========================================


@pytest.mark.asyncio
async def test_fallback_to_flash_for_large_input(router: ModelRouter):
    """
    Test: Fallback a FLASH para inputs muy grandes.

    Escenario:
    - Tarea: COHERENCE_ANALYSIS (normalmente STANDARD)
    - Input: >100K tokens
    - Esperado: Fallback a FLASH
    """
    model = router.select_model(
        task_type=TaskType.COHERENCE_ANALYSIS,
        input_token_estimate=150_000,  # Muy grande
    )

    # Debe hacer fallback a FLASH
    assert model.tier == ModelTier.FLASH


# ===========================================
# TEST 5: FORCE MODEL TIER
# ===========================================


@pytest.mark.asyncio
async def test_force_flash_on_standard_task(router: ModelRouter):
    """Test: Forzar FLASH en tarea que normalmente usa STANDARD."""
    model = router.select_model(
        task_type=TaskType.COHERENCE_ANALYSIS,
        force_tier=ModelTier.FLASH,  # ← Forzar
    )

    assert model.tier == ModelTier.FLASH


@pytest.mark.asyncio
async def test_force_standard_on_flash_task(router: ModelRouter):
    """Test: Forzar STANDARD en tarea que normalmente usa FLASH."""
    model = router.select_model(
        task_type=TaskType.CLASSIFICATION,
        force_tier=ModelTier.STANDARD,  # ← Forzar
    )

    assert model.tier == ModelTier.STANDARD


# ===========================================
# TEST 6: COST ESTIMATION
# ===========================================


@pytest.mark.asyncio
async def test_cost_estimation_flash(router: ModelRouter):
    """Test: Estimación de costo para FLASH."""
    model = router.get_model_by_tier(ModelTier.FLASH)

    cost = router.estimate_cost(
        model=model,
        input_tokens=1000,
        output_tokens=100,
    )

    # FLASH: $0.25/1M input + $1.25/1M output
    # = (1000/1M * 0.25) + (100/1M * 1.25)
    # = 0.00025 + 0.000125 = 0.000375
    expected = 0.000375
    assert abs(cost - expected) < 0.000001


@pytest.mark.asyncio
async def test_cost_estimation_standard(router: ModelRouter):
    """Test: Estimación de costo para STANDARD."""
    model = router.get_model_by_tier(ModelTier.STANDARD)

    cost = router.estimate_cost(
        model=model,
        input_tokens=1000,
        output_tokens=100,
    )

    # STANDARD: $3.00/1M input + $15.00/1M output
    # = (1000/1M * 3.00) + (100/1M * 15.00)
    # = 0.003 + 0.0015 = 0.0045
    expected = 0.0045
    assert abs(cost - expected) < 0.000001


@pytest.mark.asyncio
async def test_flash_is_cheaper_than_standard(router: ModelRouter):
    """
    Test CRÍTICO: FLASH debe ser más barato que STANDARD.

    Validamos el ahorro de ~12x
    """
    costs = router.compare_costs(
        input_tokens=10_000,
        output_tokens=1_000,
    )

    flash_cost = costs["flash"]
    standard_cost = costs["standard"]

    # FLASH debe ser más barato
    assert flash_cost < standard_cost

    # Debe ser ~12x más barato
    savings_ratio = standard_cost / flash_cost
    assert 10 < savings_ratio < 15  # Entre 10x y 15x


# ===========================================
# TEST 7: TASK TYPE VALIDATION
# ===========================================


@pytest.mark.asyncio
async def test_invalid_task_type_raises_error(router: ModelRouter):
    """Test: TaskType inválido debe lanzar error."""
    with pytest.raises(ValueError, match="Invalid task_type"):
        router.select_model(
            task_type="invalid_task",  # ← Inválido
        )


@pytest.mark.asyncio
async def test_string_task_type_conversion(router: ModelRouter):
    """Test: String task_type se convierte automáticamente."""
    model = router.select_model(
        task_type="classification",  # ← String
    )

    assert model.tier == ModelTier.FLASH


# ===========================================
# TEST 8: UTILITIES
# ===========================================


@pytest.mark.asyncio
async def test_get_available_tasks():
    """Test: Listar tareas disponibles."""
    tasks = ModelRouter.get_available_tasks()

    assert isinstance(tasks, list)
    assert "classification" in tasks
    assert "coherence_analysis" in tasks
    assert len(tasks) > 0


@pytest.mark.asyncio
async def test_get_tasks_for_flash_tier():
    """Test: Listar tareas FLASH."""
    flash_tasks = ModelRouter.get_tasks_for_tier(ModelTier.FLASH)

    assert "classification" in flash_tasks
    assert "simple_extraction" in flash_tasks
    assert "validation" in flash_tasks
    assert "coherence_analysis" not in flash_tasks  # Es STANDARD


@pytest.mark.asyncio
async def test_get_model_by_name(router: ModelRouter):
    """Test: Obtener modelo por nombre."""
    model = router.get_model_by_name("claude-haiku-4-20250514")

    assert model is not None
    assert model.tier == ModelTier.FLASH


# ===========================================
# TEST 9: SINGLETON
# ===========================================


@pytest.mark.asyncio
async def test_singleton_returns_same_instance():
    """Test: get_model_router() retorna la misma instancia."""
    router1 = get_model_router()
    router2 = get_model_router()

    assert router1 is router2


# ===========================================
# SUMMARY
# ===========================================

"""
RESUMEN DE TESTS - MODEL ROUTER

✅ Test 1-3: Selección automática de FLASH (3 tests)
✅ Test 4-5: Selección de STANDARD (2 tests)
✅ Test 6-7: Downgrade por budget (2 tests)
✅ Test 8: Fallback por tamaño (1 test)
✅ Test 9-10: Force model tier (2 tests)
✅ Test 11-13: Cost estimation (3 tests)
✅ Test 14-15: Task type validation (2 tests)
✅ Test 16-18: Utilities (3 tests)
✅ Test 19: Singleton (1 test)

TOTAL: 19 tests

Para ejecutar:
    pytest tests/ai/test_model_router.py -v

Con coverage:
    pytest tests/ai/test_model_router.py --cov=src.modules.ai.model_router -v
"""
