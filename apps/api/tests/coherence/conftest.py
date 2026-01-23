# conftest.py for coherence module tests
"""
C2Pro - Coherence Module Test Fixtures (CE-25)

Provides fixtures for testing both deterministic and LLM-based evaluators.
Includes mocking strategies for consistent LLM testing.

Version: 1.0.0
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.coherence.models import Clause, ProjectContext


# ===========================================
# CLAUSE FIXTURES
# ===========================================


@pytest.fixture
def sample_clause_clear():
    """A clearly written clause without ambiguities."""
    return Clause(
        id="CLAUSE-CLEAR-001",
        text="""El Contratista deberá entregar el informe mensual de avance
        dentro de los primeros 5 días hábiles de cada mes. El informe debe incluir:
        1. Porcentaje de avance físico
        2. Porcentaje de avance financiero
        3. Fotografías del sitio
        4. Lista de personal activo

        El incumplimiento de esta obligación resultará en una penalización
        de $1,000.00 USD por cada día de retraso.""",
        data={"type": "reporting", "frequency": "monthly"}
    )


@pytest.fixture
def sample_clause_ambiguous():
    """A clause with ambiguous terms that should trigger LLM rules."""
    return Clause(
        id="CLAUSE-AMBIG-001",
        text="""El Contratista realizará trabajos adicionales según sea necesario
        para completar el proyecto a satisfacción del Cliente. Los trabajos
        deberán ejecutarse de manera oportuna y con la calidad apropiada,
        utilizando materiales de buena calidad y siguiendo las buenas prácticas
        de la industria. El pago se realizará en un plazo razonable después
        de la entrega.""",
        data={"type": "scope", "category": "additional_work"}
    )


@pytest.fixture
def sample_clause_payment_vague():
    """A payment clause with vague terms."""
    return Clause(
        id="CLAUSE-PAY-001",
        text="""El Cliente pagará al Contratista los montos acordados
        en el presupuesto inicial. Los pagos se realizarán de forma periódica
        conforme al avance de los trabajos. El Contratista deberá presentar
        facturas oportunamente para recibir su pago.""",
        data={"type": "payment"}
    )


@pytest.fixture
def sample_clause_payment_clear():
    """A payment clause with clear terms."""
    return Clause(
        id="CLAUSE-PAY-002",
        text="""El Cliente pagará al Contratista la cantidad total de $500,000.00 USD
        (quinientos mil dólares americanos) de la siguiente manera:
        - 30% ($150,000.00 USD) como anticipo, dentro de los 5 días hábiles
          posteriores a la firma del contrato
        - 40% ($200,000.00 USD) al completar el 50% del avance físico,
          dentro de los 15 días naturales posteriores a la certificación
        - 30% ($150,000.00 USD) restante al término y entrega final,
          dentro de los 30 días naturales posteriores a la recepción formal

        Los pagos se realizarán mediante transferencia bancaria a la cuenta
        especificada en el Anexo B.""",
        data={"type": "payment", "total": 500000, "currency": "USD"}
    )


@pytest.fixture
def sample_clause_responsibility_unclear():
    """A clause with unclear responsibility assignment."""
    return Clause(
        id="CLAUSE-RESP-001",
        text="""Se coordinará entre las partes la obtención de los permisos
        necesarios. Los materiales serán adquiridos conjuntamente y la
        supervisión se realizará de común acuerdo. Cualquier problema
        será resuelto por las partes.""",
        data={"type": "responsibilities"}
    )


@pytest.fixture
def sample_project_context(sample_clause_ambiguous, sample_clause_payment_vague):
    """A project context with multiple clauses for testing."""
    return ProjectContext(
        id="PROJECT-TEST-001",
        clauses=[sample_clause_ambiguous, sample_clause_payment_vague]
    )


# ===========================================
# LLM MOCK FIXTURES
# ===========================================


@pytest.fixture
def mock_llm_response_violation():
    """Mock LLM response indicating a rule violation."""
    return {
        "rule_violated": True,
        "severity": "high",
        "evidence": {
            "quote": "según sea necesario",
            "explanation": "El término 'según sea necesario' es ambiguo y no define claramente el alcance de los trabajos adicionales."
        },
        "confidence": 0.92,
        "recommendation": "Especificar criterios objetivos para determinar cuándo son necesarios trabajos adicionales."
    }


@pytest.fixture
def mock_llm_response_no_violation():
    """Mock LLM response indicating no rule violation."""
    return {
        "rule_violated": False,
        "severity": "low",
        "evidence": {
            "quote": "",
            "explanation": "La cláusula está claramente redactada con términos específicos."
        },
        "confidence": 0.95,
        "recommendation": ""
    }


@pytest.fixture
def mock_clause_analysis_with_issues():
    """Mock LLM response for clause analysis with issues."""
    return {
        "has_issues": True,
        "issues": [
            {
                "type": "vague_term",
                "severity": "high",
                "description": "El término 'según sea necesario' no define criterios objetivos",
                "quote": "según sea necesario",
                "recommendation": "Definir criterios específicos para trabajos adicionales"
            },
            {
                "type": "ambiguity",
                "severity": "medium",
                "description": "La frase 'a satisfacción del Cliente' es subjetiva",
                "quote": "a satisfacción del Cliente",
                "recommendation": "Establecer criterios de aceptación medibles"
            },
            {
                "type": "vague_term",
                "severity": "medium",
                "description": "'Plazo razonable' no especifica días",
                "quote": "plazo razonable",
                "recommendation": "Especificar plazo en días calendario"
            }
        ],
        "confidence": 0.88,
        "reasoning": "La cláusula contiene múltiples términos vagos que podrían generar disputas."
    }


@pytest.fixture
def mock_clause_analysis_no_issues():
    """Mock LLM response for clause analysis without issues."""
    return {
        "has_issues": False,
        "issues": [],
        "confidence": 0.94,
        "reasoning": "La cláusula está bien estructurada con términos claros y específicos."
    }


# ===========================================
# MOCK AI RESPONSE CLASS
# ===========================================


class MockAIResponse:
    """Mock AIResponse for testing without actual API calls."""

    def __init__(
        self,
        content: str | dict,
        model_used: str = "claude-haiku-4-20250514",
        input_tokens: int = 500,
        output_tokens: int = 200,
        cost_usd: float = 0.0002,
        cached: bool = False,
    ):
        if isinstance(content, dict):
            self.content = json.dumps(content)
        else:
            self.content = content
        self.model_used = model_used
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.cached = cached
        self.retries = 0
        self.request_id = str(uuid4())
        self.task_type = "coherence_check"
        self.raw_response = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def usage(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@pytest.fixture
def mock_ai_response_factory():
    """Factory fixture for creating mock AI responses."""
    def _create_response(content: str | dict, **kwargs) -> MockAIResponse:
        return MockAIResponse(content, **kwargs)
    return _create_response


# ===========================================
# WRAPPER MOCK FIXTURES
# ===========================================


@pytest.fixture
def mock_anthropic_wrapper(mock_llm_response_violation):
    """Mock AnthropicWrapper for testing without API calls."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=MockAIResponse(mock_llm_response_violation)
    )
    mock.get_statistics = MagicMock(return_value={
        "total_requests": 1,
        "cache_hits": 0,
        "cache_misses": 1,
        "cache_hit_rate": 0,
        "total_cost_usd": 0.0002,
    })
    return mock


@pytest.fixture
def mock_anthropic_wrapper_no_violation(mock_llm_response_no_violation):
    """Mock AnthropicWrapper that returns no violation."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=MockAIResponse(mock_llm_response_no_violation)
    )
    mock.get_statistics = MagicMock(return_value={
        "total_requests": 1,
        "cache_hits": 0,
        "cache_misses": 1,
        "cache_hit_rate": 0,
        "total_cost_usd": 0.0002,
    })
    return mock


# ===========================================
# PATCH FIXTURES
# ===========================================


@pytest.fixture
def patch_anthropic_wrapper(mock_anthropic_wrapper):
    """Patch get_anthropic_wrapper to return mock."""
    with patch(
        "src.modules.coherence.rules_engine.llm_evaluator.get_anthropic_wrapper",
        return_value=mock_anthropic_wrapper
    ):
        yield mock_anthropic_wrapper


@pytest.fixture
def patch_anthropic_wrapper_for_integration(mock_anthropic_wrapper):
    """Patch get_anthropic_wrapper in llm_integration module."""
    with patch(
        "src.modules.coherence.llm_integration.get_anthropic_wrapper",
        return_value=mock_anthropic_wrapper
    ):
        yield mock_anthropic_wrapper


# ===========================================
# EVALUATOR FIXTURES
# ===========================================


@pytest.fixture
def llm_evaluator_scope_clarity(patch_anthropic_wrapper):
    """LlmRuleEvaluator for scope clarity with mocked wrapper."""
    from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

    return LlmRuleEvaluator(
        rule_id="R-SCOPE-CLARITY-01",
        rule_name="Scope Clarity Check",
        rule_description="El alcance del trabajo debe estar claramente definido",
        detection_logic="Verifica que el alcance no contenga términos ambiguos",
        default_severity="high",
        category="scope",
        low_budget_mode=True,
    )


# ===========================================
# EXPECTED RESULTS FOR VALIDATION
# ===========================================


# Golden test cases: input clauses and expected detection results
GOLDEN_TEST_CASES = {
    "scope_ambiguous": {
        "clause_text": "El contratista realizará trabajos adicionales según sea necesario.",
        "expected_violation": True,
        "expected_severity": "high",
        "trigger_terms": ["según sea necesario"],
    },
    "scope_clear": {
        "clause_text": "El contratista realizará exactamente 50 metros lineales de cerca perimetral.",
        "expected_violation": False,
        "expected_severity": None,
        "trigger_terms": [],
    },
    "payment_vague": {
        "clause_text": "El pago se realizará en un plazo razonable después de la entrega.",
        "expected_violation": True,
        "expected_severity": "high",
        "trigger_terms": ["plazo razonable"],
    },
    "payment_clear": {
        "clause_text": "El pago de $10,000 USD se realizará dentro de los 30 días naturales.",
        "expected_violation": False,
        "expected_severity": None,
        "trigger_terms": [],
    },
    "responsibility_unclear": {
        "clause_text": "Las partes colaborarán conjuntamente en la obtención de permisos.",
        "expected_violation": True,
        "expected_severity": "medium",
        "trigger_terms": ["las partes", "conjuntamente"],
    },
}


@pytest.fixture
def golden_test_cases():
    """Provides golden test cases for validation."""
    return GOLDEN_TEST_CASES
