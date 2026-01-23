"""
C2Pro - Coherence LLM Integration (CE-22)

Integración de LLM para análisis de coherencia cualitativo.
Utiliza el AnthropicWrapper existente para llamadas a Claude API.

Features:
- Análisis de cláusulas contractuales con LLM
- Detección de ambigüedades y riesgos implícitos
- Verificación de coherencia entre documentos
- Caché inteligente para respuestas similares

Version: 1.0.0
Sprint: P2-02
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import structlog

from src.modules.ai.anthropic_wrapper import (
    AIRequest,
    AIResponse,
    get_anthropic_wrapper,
    AnthropicWrapper,
)
from src.modules.ai.model_router import AITaskType, ModelTier
from src.modules.coherence.models import Clause, ProjectContext, Alert, Evidence

logger = structlog.get_logger()


# ===========================================
# DATA STRUCTURES
# ===========================================


@dataclass
class ClauseAnalysisResult:
    """Resultado del análisis LLM de una cláusula."""

    clause_id: str
    has_issues: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: str = ""

    # Tracking
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    cached: bool = False


@dataclass
class CoherenceAnalysisResult:
    """Resultado del análisis de coherencia completo con LLM."""

    project_id: str
    overall_assessment: str
    risk_level: str  # low, medium, high, critical
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Metrics
    total_clauses_analyzed: int = 0
    clauses_with_issues: int = 0

    # Tracking
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0


# ===========================================
# PROMPT TEMPLATES
# ===========================================

CLAUSE_ANALYSIS_SYSTEM_PROMPT = """Eres un experto analista de contratos de construcción y proyectos de ingeniería.
Tu rol es identificar problemas de coherencia, ambigüedades, riesgos y contradicciones en cláusulas contractuales.

REGLAS:
1. Analiza la cláusula buscando:
   - Ambigüedades en el lenguaje
   - Términos vagos o indefinidos
   - Contradicciones internas
   - Riesgos ocultos o implícitos
   - Obligaciones poco claras
   - Fechas o plazos inconsistentes
   - Montos o cantidades sin especificar

2. Para cada problema encontrado, proporciona:
   - Tipo de problema (ambiguity, risk, contradiction, vague_term, unclear_obligation)
   - Severidad (low, medium, high, critical)
   - Descripción clara del problema
   - Cita textual de la parte problemática
   - Recomendación de mejora

3. Si la cláusula es clara y sin problemas, indica has_issues: false

RESPONDE SIEMPRE EN JSON VÁLIDO con este formato exacto:
{
    "has_issues": true/false,
    "issues": [
        {
            "type": "ambiguity|risk|contradiction|vague_term|unclear_obligation",
            "severity": "low|medium|high|critical",
            "description": "Descripción del problema",
            "quote": "Texto exacto problemático",
            "recommendation": "Sugerencia de mejora"
        }
    ],
    "confidence": 0.0-1.0,
    "reasoning": "Explicación breve del análisis"
}"""


COHERENCE_CHECK_SYSTEM_PROMPT = """Eres un experto en análisis de coherencia de proyectos de construcción.
Tu rol es verificar si una cláusula específica cumple con una regla de coherencia determinada.

REGLAS DE ANÁLISIS:
1. Evalúa la cláusula contra la regla proporcionada
2. Identifica si hay violación de la regla
3. Si hay violación, proporciona evidencia específica
4. Asigna un nivel de severidad basado en el impacto

RESPONDE SIEMPRE EN JSON VÁLIDO:
{
    "rule_violated": true/false,
    "severity": "low|medium|high|critical",
    "evidence": {
        "quote": "Texto exacto que evidencia el problema",
        "explanation": "Por qué esto viola la regla"
    },
    "confidence": 0.0-1.0
}"""


MULTI_CLAUSE_COHERENCE_PROMPT = """Analiza las siguientes cláusulas en conjunto para detectar:
1. Contradicciones entre cláusulas
2. Inconsistencias en fechas, montos o términos
3. Gaps o vacíos en la cobertura contractual
4. Superposiciones o duplicaciones

CLÁUSULAS A ANALIZAR:
{clauses_text}

RESPONDE EN JSON:
{
    "cross_clause_issues": [
        {
            "type": "contradiction|inconsistency|gap|overlap",
            "severity": "low|medium|high|critical",
            "affected_clauses": ["clause_id_1", "clause_id_2"],
            "description": "Descripción del problema",
            "evidence": "Citas relevantes de ambas cláusulas"
        }
    ],
    "overall_coherence_score": 0-100,
    "summary": "Resumen del análisis"
}"""


# ===========================================
# COHERENCE LLM SERVICE
# ===========================================


class CoherenceLLMService:
    """
    Servicio de LLM para análisis de coherencia cualitativo.

    Utiliza Claude API via AnthropicWrapper para:
    - Análisis de cláusulas individuales
    - Verificación de reglas de coherencia
    - Análisis de coherencia multi-cláusula

    Example:
        service = CoherenceLLMService()

        clause = Clause(id="C1", text="El contratista deberá...")
        result = await service.analyze_clause(clause)

        if result.has_issues:
            for issue in result.issues:
                print(f"[{issue['severity']}] {issue['description']}")
    """

    def __init__(
        self,
        wrapper: Optional[AnthropicWrapper] = None,
        default_task_type: AITaskType = AITaskType.COHERENCE_ANALYSIS,
        low_budget_mode: bool = False,
    ):
        """
        Inicializa el servicio de coherencia LLM.

        Args:
            wrapper: AnthropicWrapper personalizado (si None, usa singleton)
            default_task_type: Tipo de tarea por defecto para routing
            low_budget_mode: Activar modo de bajo presupuesto
        """
        self.wrapper = wrapper or get_anthropic_wrapper()
        self.default_task_type = default_task_type
        self.low_budget_mode = low_budget_mode

        # Statistics
        self.total_analyses = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        logger.info(
            "coherence_llm_service_initialized",
            default_task_type=default_task_type.value,
            low_budget_mode=low_budget_mode,
        )

    # ===========================================
    # CLAUSE ANALYSIS
    # ===========================================

    async def analyze_clause(
        self,
        clause: Clause,
        tenant_id: Optional[UUID] = None,
        use_cache: bool = True,
    ) -> ClauseAnalysisResult:
        """
        Analiza una cláusula individual buscando problemas de coherencia.

        Args:
            clause: Cláusula a analizar
            tenant_id: ID del tenant para tracking
            use_cache: Usar caché de respuestas

        Returns:
            ClauseAnalysisResult con los hallazgos
        """
        self.total_analyses += 1

        logger.info(
            "analyzing_clause",
            clause_id=clause.id,
            text_length=len(clause.text),
        )

        # Build prompt
        prompt = f"""Analiza la siguiente cláusula contractual:

CLÁUSULA ID: {clause.id}
TEXTO:
\"\"\"
{clause.text}
\"\"\"

DATOS ADICIONALES:
{json.dumps(clause.data, indent=2, ensure_ascii=False) if clause.data else "Ninguno"}

Identifica todos los problemas de coherencia, ambigüedades y riesgos."""

        # Make LLM request
        request = AIRequest(
            prompt=prompt,
            task_type=self.default_task_type,
            system_prompt=CLAUSE_ANALYSIS_SYSTEM_PROMPT,
            low_budget_mode=self.low_budget_mode,
            tenant_id=tenant_id,
            use_cache=use_cache,
            temperature=0.0,  # Deterministic for consistency
        )

        try:
            response = await self.wrapper.generate(request)

            # Update stats
            self.total_tokens += response.total_tokens
            self.total_cost += response.cost_usd

            # Parse response
            result = self._parse_clause_analysis_response(
                clause_id=clause.id,
                response=response,
            )

            logger.info(
                "clause_analysis_complete",
                clause_id=clause.id,
                has_issues=result.has_issues,
                issues_count=len(result.issues),
                cached=response.cached,
                cost_usd=response.cost_usd,
            )

            return result

        except Exception as e:
            logger.error(
                "clause_analysis_failed",
                clause_id=clause.id,
                error=str(e),
            )
            raise

    # ===========================================
    # RULE-BASED COHERENCE CHECK
    # ===========================================

    async def check_coherence_rule(
        self,
        clause: Clause,
        rule_id: str,
        rule_description: str,
        detection_logic: str,
        tenant_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Verifica si una cláusula viola una regla de coherencia específica.

        Args:
            clause: Cláusula a verificar
            rule_id: ID de la regla
            rule_description: Descripción de la regla
            detection_logic: Lógica de detección en lenguaje natural
            tenant_id: ID del tenant

        Returns:
            Dict con el resultado de la verificación
        """
        logger.info(
            "checking_coherence_rule",
            clause_id=clause.id,
            rule_id=rule_id,
        )

        prompt = f"""REGLA A VERIFICAR:
ID: {rule_id}
Descripción: {rule_description}
Lógica de detección: {detection_logic}

CLÁUSULA A EVALUAR:
ID: {clause.id}
Texto: \"\"\"{clause.text}\"\"\"

Evalúa si esta cláusula viola la regla especificada."""

        request = AIRequest(
            prompt=prompt,
            task_type=AITaskType.COHERENCE_CHECK,  # Uses faster model (Haiku)
            system_prompt=COHERENCE_CHECK_SYSTEM_PROMPT,
            low_budget_mode=self.low_budget_mode,
            tenant_id=tenant_id,
            use_cache=True,
            temperature=0.0,
        )

        try:
            response = await self.wrapper.generate(request)

            self.total_tokens += response.total_tokens
            self.total_cost += response.cost_usd

            # Parse JSON response
            result = self._parse_json_response(response.content)
            result["clause_id"] = clause.id
            result["rule_id"] = rule_id
            result["model_used"] = response.model_used
            result["cached"] = response.cached

            logger.info(
                "coherence_rule_check_complete",
                clause_id=clause.id,
                rule_id=rule_id,
                rule_violated=result.get("rule_violated", False),
            )

            return result

        except Exception as e:
            logger.error(
                "coherence_rule_check_failed",
                clause_id=clause.id,
                rule_id=rule_id,
                error=str(e),
            )
            raise

    # ===========================================
    # MULTI-CLAUSE ANALYSIS
    # ===========================================

    async def analyze_multi_clause_coherence(
        self,
        clauses: list[Clause],
        tenant_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Analiza coherencia entre múltiples cláusulas.

        Args:
            clauses: Lista de cláusulas a analizar en conjunto
            tenant_id: ID del tenant

        Returns:
            Dict con análisis de coherencia cruzada
        """
        if len(clauses) < 2:
            return {
                "cross_clause_issues": [],
                "overall_coherence_score": 100,
                "summary": "Se requieren al menos 2 cláusulas para análisis cruzado",
            }

        logger.info(
            "analyzing_multi_clause_coherence",
            clauses_count=len(clauses),
        )

        # Build clauses text
        clauses_text = "\n\n".join([
            f"--- CLÁUSULA {c.id} ---\n{c.text}"
            for c in clauses
        ])

        prompt = MULTI_CLAUSE_COHERENCE_PROMPT.format(clauses_text=clauses_text)

        request = AIRequest(
            prompt=prompt,
            task_type=AITaskType.COHERENCE_ANALYSIS,  # Uses Sonnet for complex analysis
            system_prompt="Eres un experto en análisis de coherencia contractual.",
            low_budget_mode=self.low_budget_mode,
            tenant_id=tenant_id,
            use_cache=True,
            temperature=0.0,
        )

        try:
            response = await self.wrapper.generate(request)

            self.total_tokens += response.total_tokens
            self.total_cost += response.cost_usd

            result = self._parse_json_response(response.content)
            result["clauses_analyzed"] = [c.id for c in clauses]
            result["model_used"] = response.model_used

            logger.info(
                "multi_clause_analysis_complete",
                clauses_count=len(clauses),
                issues_found=len(result.get("cross_clause_issues", [])),
            )

            return result

        except Exception as e:
            logger.error(
                "multi_clause_analysis_failed",
                error=str(e),
            )
            raise

    # ===========================================
    # PROJECT CONTEXT ANALYSIS
    # ===========================================

    async def analyze_project_context(
        self,
        context: ProjectContext,
        tenant_id: Optional[UUID] = None,
        analyze_individual: bool = True,
        analyze_cross_clause: bool = True,
    ) -> CoherenceAnalysisResult:
        """
        Análisis completo de coherencia para un contexto de proyecto.

        Args:
            context: Contexto del proyecto con cláusulas
            tenant_id: ID del tenant
            analyze_individual: Analizar cláusulas individuales
            analyze_cross_clause: Analizar coherencia cruzada

        Returns:
            CoherenceAnalysisResult completo
        """
        logger.info(
            "analyzing_project_context",
            project_id=context.id,
            clauses_count=len(context.clauses),
        )

        findings = []
        total_tokens = 0
        total_cost = 0.0
        clauses_with_issues = 0

        # Individual clause analysis
        if analyze_individual:
            for clause in context.clauses:
                result = await self.analyze_clause(
                    clause=clause,
                    tenant_id=tenant_id,
                )

                total_tokens += result.tokens_used
                total_cost += result.cost_usd

                if result.has_issues:
                    clauses_with_issues += 1
                    for issue in result.issues:
                        findings.append({
                            "source": "individual_analysis",
                            "clause_id": clause.id,
                            **issue,
                        })

        # Cross-clause analysis
        if analyze_cross_clause and len(context.clauses) >= 2:
            cross_result = await self.analyze_multi_clause_coherence(
                clauses=context.clauses,
                tenant_id=tenant_id,
            )

            for issue in cross_result.get("cross_clause_issues", []):
                findings.append({
                    "source": "cross_clause_analysis",
                    **issue,
                })

        # Determine risk level
        risk_level = self._calculate_risk_level(findings)

        # Generate recommendations
        recommendations = self._generate_recommendations(findings)

        result = CoherenceAnalysisResult(
            project_id=context.id,
            overall_assessment=self._generate_assessment(findings, len(context.clauses)),
            risk_level=risk_level,
            findings=findings,
            recommendations=recommendations,
            total_clauses_analyzed=len(context.clauses),
            clauses_with_issues=clauses_with_issues,
            total_tokens_used=total_tokens,
            total_cost_usd=total_cost,
        )

        logger.info(
            "project_context_analysis_complete",
            project_id=context.id,
            findings_count=len(findings),
            risk_level=risk_level,
            total_cost=total_cost,
        )

        return result

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def _parse_clause_analysis_response(
        self,
        clause_id: str,
        response: AIResponse,
    ) -> ClauseAnalysisResult:
        """Parsea la respuesta del análisis de cláusula."""
        try:
            data = self._parse_json_response(response.content)

            return ClauseAnalysisResult(
                clause_id=clause_id,
                has_issues=data.get("has_issues", False),
                issues=data.get("issues", []),
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                raw_response=response.content,
                model_used=response.model_used,
                tokens_used=response.total_tokens,
                cost_usd=response.cost_usd,
                cached=response.cached,
            )
        except Exception as e:
            logger.warning(
                "failed_to_parse_clause_analysis",
                clause_id=clause_id,
                error=str(e),
            )
            return ClauseAnalysisResult(
                clause_id=clause_id,
                has_issues=False,
                reasoning=f"Error parsing response: {e}",
                raw_response=response.content,
                model_used=response.model_used,
                tokens_used=response.total_tokens,
                cost_usd=response.cost_usd,
                cached=response.cached,
            )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parsea respuesta JSON del LLM."""
        # Try to extract JSON from response
        content = content.strip()

        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e), content=content[:200])
            return {"parse_error": str(e), "raw_content": content}

    def _calculate_risk_level(self, findings: list[dict]) -> str:
        """Calcula el nivel de riesgo basado en los hallazgos."""
        if not findings:
            return "low"

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in findings:
            severity = finding.get("severity", "low")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        if severity_counts["critical"] > 0:
            return "critical"
        if severity_counts["high"] >= 2:
            return "high"
        if severity_counts["high"] >= 1 or severity_counts["medium"] >= 3:
            return "medium"
        return "low"

    def _generate_recommendations(self, findings: list[dict]) -> list[str]:
        """Genera recomendaciones basadas en los hallazgos."""
        recommendations = []

        # Group by type
        types_found = set(f.get("type") for f in findings if f.get("type"))

        if "ambiguity" in types_found:
            recommendations.append(
                "Revisar y clarificar los términos ambiguos identificados en las cláusulas"
            )
        if "risk" in types_found:
            recommendations.append(
                "Evaluar los riesgos identificados con el equipo legal antes de firmar"
            )
        if "contradiction" in types_found:
            recommendations.append(
                "Resolver las contradicciones detectadas entre cláusulas"
            )
        if "vague_term" in types_found:
            recommendations.append(
                "Definir claramente los términos vagos con valores específicos"
            )
        if "unclear_obligation" in types_found:
            recommendations.append(
                "Especificar claramente las obligaciones de cada parte"
            )

        # Add specific recommendations from findings
        for finding in findings:
            if finding.get("recommendation"):
                recommendations.append(finding["recommendation"])

        return list(set(recommendations))[:10]  # Limit to 10 unique recommendations

    def _generate_assessment(self, findings: list[dict], total_clauses: int) -> str:
        """Genera una evaluación general."""
        if not findings:
            return f"Análisis completado de {total_clauses} cláusulas sin hallazgos significativos."

        critical = sum(1 for f in findings if f.get("severity") == "critical")
        high = sum(1 for f in findings if f.get("severity") == "high")

        if critical > 0:
            return f"Se encontraron {critical} problemas críticos que requieren atención inmediata."
        if high > 0:
            return f"Se identificaron {high} problemas de alta severidad que deben revisarse."

        return f"Se encontraron {len(findings)} hallazgos menores en {total_clauses} cláusulas analizadas."

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas del servicio."""
        return {
            "total_analyses": self.total_analyses,
            "total_tokens_used": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "low_budget_mode": self.low_budget_mode,
            "wrapper_stats": self.wrapper.get_statistics(),
        }


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_service: Optional[CoherenceLLMService] = None


def get_coherence_llm_service(
    low_budget_mode: bool = False,
) -> CoherenceLLMService:
    """
    Obtiene instancia singleton del servicio de coherencia LLM.

    Args:
        low_budget_mode: Activar modo de bajo presupuesto

    Returns:
        CoherenceLLMService configurado
    """
    global _service

    if _service is None:
        _service = CoherenceLLMService(low_budget_mode=low_budget_mode)

    return _service


def reset_coherence_llm_service() -> None:
    """Reset singleton (útil para testing)."""
    global _service
    _service = None
