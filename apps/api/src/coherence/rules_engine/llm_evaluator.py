"""
C2Pro - LLM Rule Evaluator (CE-23)

Evaluador de reglas basado en LLM para reglas cualitativas.
Utiliza Claude API para evaluar reglas que no pueden resolverse
con lógica determinista.

Features:
- Evaluación de reglas con lenguaje natural
- Integración con el sistema de reglas existente
- Soporte para diferentes tipos de análisis
- Caché de evaluaciones para optimizar costos

Version: 1.0.0
Sprint: P2-02
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
from uuid import UUID

import structlog

from src.core.ai.anthropic_wrapper import AIRequest, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType
from src.coherence.models import Clause
from src.coherence.rules_engine.base import Finding, RuleEvaluator

logger = structlog.get_logger()


# ===========================================
# LLM RULE EVALUATOR
# ===========================================


class LlmRuleEvaluator(RuleEvaluator):
    """
    Evaluador de reglas basado en LLM.

    Utiliza Claude para evaluar reglas cualitativas que requieren
    comprensión del lenguaje natural y razonamiento complejo.

    Example:
        evaluator = LlmRuleEvaluator(
            rule_id="R-SCOPE-01",
            rule_name="Scope Clarity",
            rule_description="El alcance del trabajo debe estar claramente definido",
            detection_logic="Verifica que el alcance no contenga términos ambiguos como 'según sea necesario', 'cuando corresponda', 'razonable'"
        )

        clause = Clause(id="C1", text="El contratista realizará trabajos adicionales según sea necesario...")
        finding = await evaluator.evaluate_async(clause)

        if finding:
            print(f"Regla violada: {finding.raw_data}")
    """

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        detection_logic: str,
        default_severity: str = "medium",
        category: str = "general",
        low_budget_mode: bool = False,
        tenant_id: Optional[UUID] = None,
    ):
        """
        Inicializa el evaluador de reglas LLM.

        Args:
            rule_id: ID único de la regla
            rule_name: Nombre descriptivo de la regla
            rule_description: Descripción de qué verifica la regla
            detection_logic: Lógica de detección en lenguaje natural
            default_severity: Severidad por defecto si no se especifica
            category: Categoría de la regla (legal, financial, technical, etc.)
            low_budget_mode: Usar modelos más económicos
            tenant_id: ID del tenant para tracking
        """
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.rule_description = rule_description
        self.detection_logic = detection_logic
        self.default_severity = default_severity
        self.category = category
        self.low_budget_mode = low_budget_mode
        self.tenant_id = tenant_id

        # Get wrapper
        self.wrapper = get_anthropic_wrapper()

        # Statistics
        self.evaluations_count = 0
        self.violations_found = 0
        self.total_cost = 0.0

        logger.info(
            "llm_rule_evaluator_initialized",
            rule_id=rule_id,
            rule_name=rule_name,
            category=category,
        )

    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Método síncrono requerido por la interfaz base.
        Ejecuta la evaluación async en un event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si ya hay un loop corriendo, crear una tarea
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.evaluate_async(clause))
                    return future.result()
            else:
                return loop.run_until_complete(self.evaluate_async(clause))
        except RuntimeError:
            # No hay event loop, crear uno nuevo
            return asyncio.run(self.evaluate_async(clause))

    async def evaluate_async(self, clause: Clause) -> Finding | None:
        """
        Evalúa una cláusula contra la regla usando LLM.

        Args:
            clause: La cláusula a evaluar

        Returns:
            Finding si la regla es violada, None si no hay violación
        """
        self.evaluations_count += 1

        logger.info(
            "llm_evaluating_clause",
            rule_id=self.rule_id,
            clause_id=clause.id,
            text_length=len(clause.text),
        )

        # Build prompt
        prompt = self._build_evaluation_prompt(clause)
        system_prompt = self._build_system_prompt()

        # Make LLM request
        request = AIRequest(
            prompt=prompt,
            task_type=AITaskType.COHERENCE_CHECK,  # Uses Haiku for speed
            system_prompt=system_prompt,
            low_budget_mode=self.low_budget_mode,
            tenant_id=self.tenant_id,
            use_cache=True,
            temperature=0.0,  # Deterministic
        )

        try:
            response = await self.wrapper.generate(request)
            self.total_cost += response.cost_usd

            # Parse response
            result = self._parse_evaluation_response(response.content)

            if result.get("rule_violated", False):
                self.violations_found += 1

                logger.info(
                    "llm_rule_violation_detected",
                    rule_id=self.rule_id,
                    clause_id=clause.id,
                    severity=result.get("severity", self.default_severity),
                )

                return Finding(
                    triggered_clause=clause,
                    raw_data={
                        "rule_id": self.rule_id,
                        "rule_name": self.rule_name,
                        "category": self.category,
                        "severity": result.get("severity", self.default_severity),
                        "evidence": result.get("evidence", {}),
                        "confidence": result.get("confidence", 0.0),
                        "recommendation": result.get("recommendation", ""),
                        "model_used": response.model_used,
                        "cached": response.cached,
                    },
                )

            logger.debug(
                "llm_rule_no_violation",
                rule_id=self.rule_id,
                clause_id=clause.id,
            )
            return None

        except Exception as e:
            logger.error(
                "llm_evaluation_failed",
                rule_id=self.rule_id,
                clause_id=clause.id,
                error=str(e),
            )
            raise

    def _build_system_prompt(self) -> str:
        """Construye el system prompt para la evaluación."""
        return f"""Eres un verificador de reglas de coherencia contractual experto.

TU TAREA:
Evaluar si una cláusula específica viola la siguiente regla de coherencia:

REGLA: {self.rule_name}
DESCRIPCIÓN: {self.rule_description}
CATEGORÍA: {self.category}

PROCESO:
1. Lee la cláusula cuidadosamente
2. Aplica la lógica de detección especificada
3. Determina si hay violación
4. Si hay violación, proporciona evidencia textual exacta
5. Asigna severidad según el impacto potencial

SEVERIDADES:
- critical: Puede causar disputas legales o pérdidas financieras mayores
- high: Riesgo significativo de malentendidos o incumplimiento
- medium: Problema que debería corregirse pero no es urgente
- low: Mejora recomendada para claridad

IMPORTANTE: Responde SOLO en JSON válido."""

    def _build_evaluation_prompt(self, clause: Clause) -> str:
        """Construye el prompt de evaluación."""
        clause_data_str = ""
        if clause.data:
            clause_data_str = f"\n\nDATOS ESTRUCTURADOS:\n{json.dumps(clause.data, indent=2, ensure_ascii=False)}"

        return f"""LÓGICA DE DETECCIÓN A APLICAR:
{self.detection_logic}

CLÁUSULA A EVALUAR:
ID: {clause.id}
TEXTO:
\"\"\"
{clause.text}
\"\"\"{clause_data_str}

Evalúa si esta cláusula viola la regla y responde en JSON:

```json
{{
    "rule_violated": true/false,
    "severity": "low|medium|high|critical",
    "evidence": {{
        "quote": "Texto exacto que evidencia la violación (si aplica)",
        "explanation": "Por qué esto constituye una violación"
    }},
    "confidence": 0.0-1.0,
    "recommendation": "Acción recomendada para corregir (si aplica)"
}}
```"""

    def _parse_evaluation_response(self, content: str) -> dict[str, Any]:
        """Parsea la respuesta JSON del LLM."""
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(
                "llm_response_parse_failed",
                rule_id=self.rule_id,
                error=str(e),
            )
            # Return safe default
            return {
                "rule_violated": False,
                "parse_error": str(e),
            }

    def get_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas del evaluador."""
        violation_rate = (
            self.violations_found / self.evaluations_count
            if self.evaluations_count > 0
            else 0
        )

        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "evaluations_count": self.evaluations_count,
            "violations_found": self.violations_found,
            "violation_rate": round(violation_rate, 3),
            "total_cost_usd": round(self.total_cost, 4),
        }


# ===========================================
# FACTORY FUNCTIONS
# ===========================================


def create_llm_evaluator_from_rule(
    rule: dict[str, Any],
    low_budget_mode: bool = False,
    tenant_id: Optional[UUID] = None,
) -> LlmRuleEvaluator:
    """
    Crea un LlmRuleEvaluator desde un diccionario de regla.

    Args:
        rule: Diccionario con la definición de la regla
        low_budget_mode: Usar modelos económicos
        tenant_id: ID del tenant

    Returns:
        LlmRuleEvaluator configurado
    """
    return LlmRuleEvaluator(
        rule_id=rule["id"],
        rule_name=rule.get("name", rule["id"]),
        rule_description=rule.get("description", ""),
        detection_logic=rule.get("detection_logic", rule.get("description", "")),
        default_severity=rule.get("default_severity", "medium"),
        category=rule.get("category", "general"),
        low_budget_mode=low_budget_mode,
        tenant_id=tenant_id,
    )


# ===========================================
# PRE-DEFINED QUALITATIVE RULES
# ===========================================

# Reglas cualitativas que requieren LLM para su evaluación
QUALITATIVE_RULES = [
    {
        "id": "R-SCOPE-CLARITY-01",
        "name": "Scope Clarity Check",
        "description": "El alcance del trabajo debe estar claramente definido sin términos ambiguos",
        "detection_logic": """Verifica que el alcance NO contenga:
1. Términos vagos como: "según sea necesario", "cuando corresponda", "razonable", "apropiado", "oportuno"
2. Frases abiertas como: "y otros trabajos relacionados", "incluyendo pero no limitado a"
3. Referencias indefinidas como: "según las necesidades del proyecto", "a satisfacción del cliente"
4. Cantidades no especificadas: "suficiente", "adecuado", "necesario"

Si encuentra alguno de estos, la regla está VIOLADA.""",
        "default_severity": "high",
        "category": "scope",
    },
    {
        "id": "R-PAYMENT-CLARITY-01",
        "name": "Payment Terms Clarity",
        "description": "Las condiciones de pago deben especificar montos, plazos y condiciones exactas",
        "detection_logic": """Verifica que las condiciones de pago especifiquen CLARAMENTE:
1. Montos exactos o porcentajes específicos
2. Plazos en días calendario específicos (no "oportuno" o "razonable")
3. Condiciones de pago completas (qué debe cumplirse para facturar)
4. Forma de pago (transferencia, cheque, etc.)
5. Moneda del contrato

Si falta alguno de estos elementos o usa términos vagos, la regla está VIOLADA.""",
        "default_severity": "high",
        "category": "financial",
    },
    {
        "id": "R-RESPONSIBILITY-01",
        "name": "Responsibility Assignment",
        "description": "Las responsabilidades deben asignarse claramente a una parte específica",
        "detection_logic": """Verifica que las responsabilidades:
1. Se asignen a una parte específica (Contratista, Cliente, etc.) - NO usar "las partes"
2. Tengan verbos claros de acción (deberá, realizará, proporcionará)
3. NO usen voz pasiva sin sujeto ("se realizará", "será entregado")
4. NO contengan responsabilidades compartidas ambiguas

Si las responsabilidades son ambiguas o no están claramente asignadas, la regla está VIOLADA.""",
        "default_severity": "medium",
        "category": "legal",
    },
    {
        "id": "R-TERMINATION-01",
        "name": "Termination Conditions",
        "description": "Las condiciones de terminación deben ser específicas y balanceadas",
        "detection_logic": """Verifica que las condiciones de terminación:
1. Especifiquen causales claras (no solo "por incumplimiento")
2. Incluyan período de notificación específico en días
3. Describan consecuencias de terminación
4. Sean balanceadas para ambas partes (no solo permitir terminación a una parte)
5. Incluyan procedimiento de terminación

Si las condiciones son vagas, desbalanceadas o incompletas, la regla está VIOLADA.""",
        "default_severity": "high",
        "category": "legal",
    },
    {
        "id": "R-QUALITY-STANDARDS-01",
        "name": "Quality Standards Definition",
        "description": "Los estándares de calidad deben referenciarse específicamente",
        "detection_logic": """Verifica que los estándares de calidad:
1. Referencien normas específicas (ISO, ASTM, NOM, etc.) con número
2. NO usen solo "buenas prácticas de la industria" sin especificar cuáles
3. Incluyan criterios de aceptación medibles
4. Especifiquen procedimientos de inspección

Si los estándares son vagos o no referenciados, la regla está VIOLADA.""",
        "default_severity": "medium",
        "category": "quality",
    },
]


def get_predefined_llm_evaluators(
    low_budget_mode: bool = False,
    tenant_id: Optional[UUID] = None,
) -> list[LlmRuleEvaluator]:
    """
    Obtiene los evaluadores LLM predefinidos.

    Args:
        low_budget_mode: Usar modelos económicos
        tenant_id: ID del tenant

    Returns:
        Lista de LlmRuleEvaluator configurados
    """
    return [
        create_llm_evaluator_from_rule(rule, low_budget_mode, tenant_id)
        for rule in QUALITATIVE_RULES
    ]

