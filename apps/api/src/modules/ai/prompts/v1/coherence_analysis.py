"""
C2Pro - Coherence Analysis Prompt Templates (CE-22)

Templates de prompts para análisis de coherencia con LLM.
Implementa prompts optimizados para detección de problemas contractuales.

Version: 1.0.0
Sprint: P2-02
"""

from typing import Any

from src.modules.ai.prompts.registry import PromptRegistry, PromptTemplate


# ===========================================
# SYSTEM PROMPTS
# ===========================================

COHERENCE_ANALYST_SYSTEM = """Eres un experto analista de contratos de construcción y proyectos de ingeniería con 20 años de experiencia.

TU ROL:
- Identificar problemas de coherencia, ambigüedades y riesgos en documentos contractuales
- Detectar contradicciones entre cláusulas
- Evaluar cumplimiento de reglas de coherencia
- Proporcionar recomendaciones accionables

PRINCIPIOS:
1. Precisión: Cita textualmente las partes problemáticas
2. Objetividad: Basa tus hallazgos en evidencia concreta
3. Claridad: Explica los problemas de forma comprensible
4. Priorización: Asigna severidad correcta (critical > high > medium > low)

CONTEXTO LEGAL:
- Familiarizado con contratos FIDIC, NEC, AIA
- Conocimiento de normativas de construcción internacionales
- Experiencia en disputas contractuales

SIEMPRE responde en JSON válido siguiendo el formato especificado."""


RULE_CHECKER_SYSTEM = """Eres un verificador de reglas de coherencia contractual.

TU TAREA:
Evaluar si una cláusula específica viola una regla de coherencia determinada.

PROCESO DE EVALUACIÓN:
1. Lee y comprende la regla completamente
2. Analiza la cláusula en detalle
3. Determina si hay violación de la regla
4. Si hay violación, identifica la evidencia exacta
5. Asigna severidad basada en el impacto potencial

SEVERIDADES:
- critical: Puede causar disputas legales o pérdidas financieras mayores
- high: Riesgo significativo de malentendidos o incumplimiento
- medium: Problema que debería corregirse pero no es urgente
- low: Mejora recomendada para claridad

SIEMPRE responde en JSON válido."""


# ===========================================
# PROMPT TEMPLATES
# ===========================================

CLAUSE_ANALYSIS_TEMPLATE = """Analiza la siguiente cláusula contractual buscando problemas de coherencia:

## CLÁUSULA
**ID:** {clause_id}
**Tipo:** {clause_type}
**Documento origen:** {document_name}

**TEXTO:**
```
{clause_text}
```

{additional_context}

## INSTRUCCIONES
Identifica TODOS los problemas en las siguientes categorías:
1. **Ambigüedades**: Lenguaje que puede interpretarse de múltiples formas
2. **Términos vagos**: Palabras como "razonable", "apropiado", "oportuno" sin definición
3. **Riesgos implícitos**: Obligaciones ocultas o consecuencias no evidentes
4. **Inconsistencias**: Contradicciones internas en la cláusula
5. **Obligaciones poco claras**: Responsabilidades no bien definidas

## FORMATO DE RESPUESTA
```json
{{
    "has_issues": true/false,
    "issues": [
        {{
            "type": "ambiguity|vague_term|risk|inconsistency|unclear_obligation",
            "severity": "low|medium|high|critical",
            "description": "Descripción clara del problema",
            "quote": "Texto exacto problemático de la cláusula",
            "recommendation": "Sugerencia específica de mejora",
            "impact": "Consecuencia potencial si no se corrige"
        }}
    ],
    "confidence": 0.0-1.0,
    "reasoning": "Explicación del análisis realizado"
}}
```"""


RULE_VERIFICATION_TEMPLATE = """Verifica si la siguiente cláusula viola la regla de coherencia especificada:

## REGLA DE COHERENCIA
**ID:** {rule_id}
**Nombre:** {rule_name}
**Categoría:** {rule_category}
**Descripción:** {rule_description}

**LÓGICA DE DETECCIÓN:**
{detection_logic}

## CLÁUSULA A EVALUAR
**ID:** {clause_id}
**Texto:**
```
{clause_text}
```

## DATOS ESTRUCTURADOS DE LA CLÁUSULA
{clause_data}

## INSTRUCCIONES
1. Evalúa si la cláusula viola la regla especificada
2. Si hay violación, proporciona evidencia textual exacta
3. Explica por qué constituye una violación
4. Asigna severidad según el impacto

## FORMATO DE RESPUESTA
```json
{{
    "rule_violated": true/false,
    "severity": "low|medium|high|critical",
    "evidence": {{
        "quote": "Texto exacto que evidencia la violación",
        "explanation": "Explicación de por qué esto viola la regla"
    }},
    "confidence": 0.0-1.0,
    "mitigating_factors": ["Lista de factores atenuantes si existen"],
    "recommendation": "Acción recomendada para resolver"
}}
```"""


CROSS_CLAUSE_ANALYSIS_TEMPLATE = """Analiza la coherencia entre las siguientes cláusulas:

## CLÁUSULAS A COMPARAR
{clauses_block}

## INSTRUCCIONES
Busca los siguientes tipos de problemas ENTRE las cláusulas:

1. **Contradicciones**: Cláusulas que dicen cosas opuestas
2. **Inconsistencias**: Fechas, montos o términos que no coinciden
3. **Gaps (vacíos)**: Aspectos no cubiertos que deberían estarlo
4. **Superposiciones**: Cláusulas que cubren lo mismo con diferente redacción

## FORMATO DE RESPUESTA
```json
{{
    "cross_clause_issues": [
        {{
            "type": "contradiction|inconsistency|gap|overlap",
            "severity": "low|medium|high|critical",
            "affected_clauses": ["id_1", "id_2"],
            "description": "Descripción del problema encontrado",
            "evidence_clause_1": "Cita de la primera cláusula",
            "evidence_clause_2": "Cita de la segunda cláusula",
            "recommendation": "Cómo resolver el problema"
        }}
    ],
    "overall_coherence_score": 0-100,
    "summary": "Resumen ejecutivo del análisis"
}}
```"""


PROJECT_COHERENCE_TEMPLATE = """Realiza un análisis completo de coherencia del proyecto:

## INFORMACIÓN DEL PROYECTO
**ID:** {project_id}
**Nombre:** {project_name}
**Total de cláusulas:** {total_clauses}

## CLÁUSULAS DEL PROYECTO
{all_clauses}

## REGLAS DE COHERENCIA APLICABLES
{applicable_rules}

## INSTRUCCIONES
1. Evalúa cada cláusula contra las reglas aplicables
2. Identifica problemas de coherencia cruzada
3. Calcula un score general de coherencia (0-100)
4. Genera recomendaciones priorizadas

## FORMATO DE RESPUESTA
```json
{{
    "project_id": "{project_id}",
    "overall_coherence_score": 0-100,
    "risk_level": "low|medium|high|critical",
    "executive_summary": "Resumen ejecutivo del análisis",
    "rule_violations": [
        {{
            "rule_id": "ID de la regla",
            "clause_id": "ID de la cláusula",
            "severity": "severidad",
            "description": "descripción"
        }}
    ],
    "cross_clause_issues": [...],
    "recommendations": [
        {{
            "priority": 1-5,
            "action": "Acción recomendada",
            "affected_clauses": ["ids"],
            "expected_impact": "Impacto esperado"
        }}
    ],
    "strengths": ["Aspectos positivos del contrato"]
}}
```"""


# ===========================================
# SPECIALIZED TEMPLATES
# ===========================================

BUDGET_ANALYSIS_TEMPLATE = """Analiza las cláusulas financieras y de presupuesto:

## CLÁUSULAS FINANCIERAS
{budget_clauses}

## INSTRUCCIONES
Verifica:
1. Consistencia de montos entre cláusulas
2. Claridad en formas de pago
3. Condiciones de ajuste de precios
4. Penalizaciones y bonificaciones
5. Retenciones y garantías

## FORMATO DE RESPUESTA
```json
{{
    "budget_coherence_score": 0-100,
    "total_contract_value": "valor detectado",
    "payment_terms_clear": true/false,
    "issues": [...],
    "financial_risks": [
        {{
            "type": "tipo de riesgo",
            "description": "descripción",
            "potential_impact_usd": "impacto estimado"
        }}
    ]
}}
```"""


SCHEDULE_ANALYSIS_TEMPLATE = """Analiza las cláusulas de cronograma y plazos:

## CLÁUSULAS DE CRONOGRAMA
{schedule_clauses}

## INSTRUCCIONES
Verifica:
1. Consistencia de fechas entre cláusulas
2. Hitos claramente definidos
3. Condiciones de extensión de plazo
4. Penalizaciones por retraso
5. Dependencias entre actividades

## FORMATO DE RESPUESTA
```json
{{
    "schedule_coherence_score": 0-100,
    "key_milestones": [...],
    "date_conflicts": [...],
    "schedule_risks": [...],
    "recommendations": [...]
}}
```"""


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def format_clauses_block(clauses: list[dict]) -> str:
    """Formatea un bloque de cláusulas para el prompt."""
    blocks = []
    for i, clause in enumerate(clauses, 1):
        block = f"""### Cláusula {i}
**ID:** {clause.get('id', 'N/A')}
**Tipo:** {clause.get('type', 'general')}
```
{clause.get('text', '')}
```
"""
        blocks.append(block)
    return "\n".join(blocks)


def format_rules_block(rules: list[dict]) -> str:
    """Formatea un bloque de reglas para el prompt."""
    blocks = []
    for rule in rules:
        block = f"""- **{rule.get('id', 'N/A')}**: {rule.get('description', '')}
  - Categoría: {rule.get('category', 'general')}
  - Severidad por defecto: {rule.get('default_severity', 'medium')}
"""
        blocks.append(block)
    return "\n".join(blocks)


def build_clause_analysis_prompt(
    clause_id: str,
    clause_text: str,
    clause_type: str = "general",
    document_name: str = "Documento sin nombre",
    additional_context: str = "",
) -> str:
    """Construye prompt para análisis de cláusula individual."""
    context_block = ""
    if additional_context:
        context_block = f"\n## CONTEXTO ADICIONAL\n{additional_context}\n"

    return CLAUSE_ANALYSIS_TEMPLATE.format(
        clause_id=clause_id,
        clause_type=clause_type,
        document_name=document_name,
        clause_text=clause_text,
        additional_context=context_block,
    )


def build_rule_verification_prompt(
    rule_id: str,
    rule_name: str,
    rule_category: str,
    rule_description: str,
    detection_logic: str,
    clause_id: str,
    clause_text: str,
    clause_data: dict[str, Any] | None = None,
) -> str:
    """Construye prompt para verificación de regla."""
    import json

    data_str = "Ninguno"
    if clause_data:
        data_str = json.dumps(clause_data, indent=2, ensure_ascii=False)

    return RULE_VERIFICATION_TEMPLATE.format(
        rule_id=rule_id,
        rule_name=rule_name,
        rule_category=rule_category,
        rule_description=rule_description,
        detection_logic=detection_logic,
        clause_id=clause_id,
        clause_text=clause_text,
        clause_data=data_str,
    )


def build_cross_clause_prompt(clauses: list[dict]) -> str:
    """Construye prompt para análisis cruzado de cláusulas."""
    clauses_block = format_clauses_block(clauses)
    return CROSS_CLAUSE_ANALYSIS_TEMPLATE.format(clauses_block=clauses_block)


# ===========================================
# REGISTER TEMPLATES
# ===========================================


def register_coherence_prompts(registry: PromptRegistry) -> None:
    """Registra los templates de coherencia en el registry."""
    # Clause analysis
    registry.register(
        PromptTemplate(
            name="coherence_clause_analysis",
            version="1.0",
            system_prompt=COHERENCE_ANALYST_SYSTEM,
            user_prompt_template=CLAUSE_ANALYSIS_TEMPLATE,
            description="Analiza una cláusula individual buscando problemas de coherencia",
            task_type="coherence_analysis",
        )
    )

    # Rule verification
    registry.register(
        PromptTemplate(
            name="coherence_rule_verification",
            version="1.0",
            system_prompt=RULE_CHECKER_SYSTEM,
            user_prompt_template=RULE_VERIFICATION_TEMPLATE,
            description="Verifica si una cláusula viola una regla de coherencia",
            task_type="coherence_check",
        )
    )

    # Cross-clause analysis
    registry.register(
        PromptTemplate(
            name="coherence_cross_clause",
            version="1.0",
            system_prompt=COHERENCE_ANALYST_SYSTEM,
            user_prompt_template=CROSS_CLAUSE_ANALYSIS_TEMPLATE,
            description="Analiza coherencia entre múltiples cláusulas",
            task_type="coherence_analysis",
        )
    )

    # Project coherence
    registry.register(
        PromptTemplate(
            name="coherence_project_analysis",
            version="1.0",
            system_prompt=COHERENCE_ANALYST_SYSTEM,
            user_prompt_template=PROJECT_COHERENCE_TEMPLATE,
            description="Análisis completo de coherencia de un proyecto",
            task_type="coherence_analysis",
        )
    )

    # Budget analysis
    registry.register(
        PromptTemplate(
            name="coherence_budget_analysis",
            version="1.0",
            system_prompt=COHERENCE_ANALYST_SYSTEM,
            user_prompt_template=BUDGET_ANALYSIS_TEMPLATE,
            description="Análisis de coherencia de cláusulas financieras",
            task_type="coherence_analysis",
        )
    )

    # Schedule analysis
    registry.register(
        PromptTemplate(
            name="coherence_schedule_analysis",
            version="1.0",
            system_prompt=COHERENCE_ANALYST_SYSTEM,
            user_prompt_template=SCHEDULE_ANALYSIS_TEMPLATE,
            description="Análisis de coherencia de cláusulas de cronograma",
            task_type="coherence_analysis",
        )
    )
