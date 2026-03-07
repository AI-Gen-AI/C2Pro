"""
C2Pro - Coherence Analysis Prompt Templates v1.1 (Chain-of-Thought Enhanced)

Enhanced prompts with explicit chain-of-thought reasoning for improved
consistency and accuracy in coherence analysis.

Version: 1.1.0
Sprint: P3 Optimization
"""

from src.core.ai.prompts import PromptTemplate, register_template


# ===========================================
# ENHANCED SYSTEM PROMPTS WITH COT
# ===========================================

COHERENCE_ANALYST_COT_SYSTEM = """Eres un experto analista de contratos de construcción y proyectos de ingeniería con 20 años de experiencia.

TU ROL:
- Identificar problemas de coherencia, ambigüedades y riesgos en documentos contractuales
- Detectar contradicciones entre cláusulas
- Evaluar cumplimiento de reglas de coherencia
- Proporcionar recomendaciones accionables

METODOLOGÍA DE ANÁLISIS (Chain-of-Thought):
Antes de emitir cualquier conclusión, SIEMPRE sigue estos pasos de razonamiento:

1. LECTURA COMPRENSIVA
   - Lee el texto completo sin hacer juicios
   - Identifica las partes principales y sus roles
   - Nota los términos técnicos y definiciones

2. ANÁLISIS ESTRUCTURAL
   - ¿Qué tipo de cláusula es? (obligación, condición, definición, etc.)
   - ¿Cuáles son los elementos clave? (sujeto, acción, objeto, condiciones)
   - ¿Hay referencias a otras secciones o documentos?

3. EVALUACIÓN DE CLARIDAD
   - ¿Cada término tiene una única interpretación posible?
   - ¿Las obligaciones están claramente asignadas a partes específicas?
   - ¿Los plazos y cantidades son específicos o vagos?

4. DETECCIÓN DE PROBLEMAS
   - Contrasta cada elemento contra criterios de coherencia
   - Busca inconsistencias internas
   - Identifica riesgos implícitos

5. VALIDACIÓN DE HALLAZGOS
   - ¿Puedo citar evidencia textual específica?
   - ¿Mi interpretación es la más razonable?
   - ¿Consideré interpretaciones alternativas?

6. PRIORIZACIÓN
   - Asigna severidad basada en impacto real, no potencial lejano
   - critical: Disputas legales inminentes o pérdidas financieras >10%
   - high: Riesgo significativo de incumplimiento
   - medium: Debería corregirse antes de firma
   - low: Mejora recomendada para claridad

PRINCIPIOS:
- Precisión: Cita textualmente las partes problemáticas
- Objetividad: Basa tus hallazgos en evidencia concreta
- Claridad: Explica los problemas de forma comprensible
- Humildad: Si no estás seguro, indica nivel de confianza bajo

CONTEXTO LEGAL:
- Familiarizado con contratos FIDIC, NEC, AIA
- Conocimiento de normativas de construcción internacionales
- Experiencia en disputas contractuales

SIEMPRE responde en JSON válido siguiendo el formato especificado."""


RULE_CHECKER_COT_SYSTEM = """Eres un verificador de reglas de coherencia contractual con metodología rigurosa.

PROCESO DE EVALUACIÓN (Chain-of-Thought):

PASO 1: COMPRENSIÓN DE LA REGLA
- ¿Qué está prohibido o requerido por esta regla?
- ¿En qué contextos aplica?
- ¿Cuáles son las excepciones válidas?
- ¿Qué evidencia constituiría una violación?

PASO 2: ANÁLISIS DE LA CLÁUSULA
- Lee la cláusula completa sin buscar problemas aún
- Identifica los elementos relevantes para esta regla específica
- Extrae datos estructurados: fechas, montos, porcentajes, partes

PASO 3: COMPARACIÓN SISTEMÁTICA
- ¿La cláusula contiene elementos que la regla prohíbe?
- ¿La cláusula omite elementos que la regla requiere?
- ¿Hay ambigüedades que podrían llevar a violaciones?

PASO 4: VERIFICACIÓN DE EVIDENCIA
- ¿Puedo señalar el texto exacto que evidencia el problema?
- ¿Es una violación directa o una interpretación?
- ¿Hay factores atenuantes que considerar?

PASO 5: EVALUACIÓN DE IMPACTO
- ¿Cuál es la consecuencia real de esta violación?
- ¿Afecta derechos u obligaciones de las partes?
- ¿Podría causar disputas o pérdidas financieras?

PASO 6: ASIGNACIÓN DE SEVERIDAD
- critical: Violación clara con impacto financiero/legal mayor (>$100K o litigio probable)
- high: Violación que probablemente cause problemas operativos
- medium: Violación técnica que debería corregirse
- low: Desviación menor, más recomendación que problema

IMPORTANTE:
- NO marques como violación si hay duda razonable
- SIEMPRE proporciona tu razonamiento paso a paso en el campo "reasoning"
- Si la regla no aplica claramente, indícalo

SIEMPRE responde en JSON válido."""


# ===========================================
# ENHANCED PROMPT TEMPLATES
# ===========================================

CLAUSE_ANALYSIS_COT_TEMPLATE = """Analiza la siguiente cláusula contractual usando razonamiento paso a paso:

## CLÁUSULA
**ID:** {clause_id}
**Tipo:** {clause_type}
**Documento origen:** {document_name}

**TEXTO:**
```
{clause_text}
```

{additional_context}

## INSTRUCCIONES DE ANÁLISIS

Sigue EXACTAMENTE estos pasos de razonamiento:

### PASO 1: Lectura Inicial
- ¿De qué trata esta cláusula en una oración?
- ¿Quiénes son las partes involucradas?
- ¿Cuál es la obligación o derecho principal?

### PASO 2: Identificación de Elementos
Para cada elemento, indica si está claramente definido:
- [ ] Sujeto (¿Quién debe actuar?)
- [ ] Acción (¿Qué debe hacer?)
- [ ] Objeto (¿Sobre qué?)
- [ ] Condiciones (¿Bajo qué circunstancias?)
- [ ] Plazos (¿Cuándo?)
- [ ] Consecuencias (¿Qué pasa si no se cumple?)

### PASO 3: Búsqueda de Problemas
Para cada categoría, indica si encontraste problemas:
1. **Ambigüedades**: ¿Hay frases que pueden interpretarse de múltiples formas?
2. **Términos vagos**: ¿Hay palabras sin definición clara? (razonable, apropiado, oportuno)
3. **Riesgos implícitos**: ¿Hay obligaciones ocultas o consecuencias no evidentes?
4. **Inconsistencias**: ¿Hay contradicciones internas?
5. **Obligaciones poco claras**: ¿Las responsabilidades están bien definidas?

### PASO 4: Validación
Para cada problema identificado:
- ¿Puedo citar el texto exacto?
- ¿Hay una interpretación alternativa razonable que no sea problemática?
- ¿Cuál es la consecuencia práctica si no se corrige?

## FORMATO DE RESPUESTA
```json
{{
    "initial_understanding": "Resumen de una oración de la cláusula",
    "element_checklist": {{
        "subject_clear": true/false,
        "action_clear": true/false,
        "object_clear": true/false,
        "conditions_clear": true/false,
        "timeline_clear": true/false,
        "consequences_clear": true/false
    }},
    "has_issues": true/false,
    "issues": [
        {{
            "type": "ambiguity|vague_term|risk|inconsistency|unclear_obligation",
            "severity": "low|medium|high|critical",
            "description": "Descripción clara del problema",
            "quote": "Texto exacto problemático de la cláusula",
            "alternative_interpretation": "¿Podría interpretarse de otra forma?",
            "practical_impact": "Qué pasaría en la práctica si no se corrige",
            "recommendation": "Sugerencia específica de mejora"
        }}
    ],
    "reasoning": "Explicación detallada del proceso de análisis seguido",
    "confidence": 0.0-1.0,
    "confidence_explanation": "Por qué este nivel de confianza"
}}
```"""


RULE_VERIFICATION_COT_TEMPLATE = """Verifica si la siguiente cláusula viola la regla de coherencia especificada.

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

## PROCESO DE VERIFICACIÓN (Sigue estos pasos exactamente)

### PASO 1: Comprensión de la Regla
Antes de analizar la cláusula, responde:
- ¿Qué prohíbe o requiere esta regla?
- ¿Qué tipo de evidencia mostraría una violación?
- ¿Hay excepciones válidas a esta regla?

### PASO 2: Análisis de la Cláusula
- ¿Qué elementos de la cláusula son relevantes para esta regla?
- ¿Hay datos estructurados que debo considerar?

### PASO 3: Comparación
- ¿La cláusula contiene algo que la regla prohíbe?
- ¿La cláusula omite algo que la regla requiere?
- ¿Hay ambigüedades que podrían considerarse violación?

### PASO 4: Evidencia
- Si hay violación, ¿cuál es el texto exacto que lo demuestra?
- ¿Es una violación directa o una interpretación?

### PASO 5: Contexto y Atenuantes
- ¿Hay algo en el contexto que justifique la aparente violación?
- ¿Es posible que no aplique esta regla a esta cláusula?

### PASO 6: Conclusión
- Basado en el análisis anterior, ¿hay violación?
- ¿Con qué nivel de certeza?

## FORMATO DE RESPUESTA
```json
{{
    "rule_understanding": {{
        "prohibits_or_requires": "Lo que la regla prohíbe o requiere",
        "violation_evidence_type": "Tipo de evidencia que mostraría violación",
        "exceptions": ["Lista de excepciones válidas si las hay"]
    }},
    "clause_analysis": {{
        "relevant_elements": ["Elementos relevantes encontrados"],
        "structured_data_considered": "Datos estructurados relevantes"
    }},
    "comparison_result": {{
        "prohibited_content_found": true/false,
        "required_content_missing": true/false,
        "ambiguity_present": true/false
    }},
    "rule_violated": true/false,
    "severity": "low|medium|high|critical",
    "evidence": {{
        "quote": "Texto exacto que evidencia la violación",
        "explanation": "Explicación de por qué esto viola la regla"
    }},
    "mitigating_factors": ["Lista de factores atenuantes si existen"],
    "confidence": 0.0-1.0,
    "reasoning": "Resumen completo del razonamiento paso a paso",
    "recommendation": "Acción recomendada para resolver"
}}
```"""


CROSS_CLAUSE_COT_TEMPLATE = """Analiza la coherencia entre las siguientes cláusulas usando razonamiento sistemático:

## CLÁUSULAS A COMPARAR
{clauses_block}

## PROCESO DE ANÁLISIS (Sigue estos pasos)

### PASO 1: Inventario de Cláusulas
Para cada cláusula, identifica:
- Tema principal
- Partes mencionadas
- Fechas y plazos
- Montos y porcentajes
- Obligaciones principales

### PASO 2: Matriz de Comparación
Compara cada par de cláusulas buscando:
- ¿Mencionan el mismo tema o elemento?
- ¿Hay valores diferentes para lo mismo?
- ¿Hay obligaciones contradictorias?
- ¿Hay vacíos que una cláusula debería cubrir dado lo que dice la otra?

### PASO 3: Clasificación de Problemas
Para cada discrepancia encontrada, clasifícala:
- **Contradicción**: Dicen cosas opuestas sobre lo mismo
- **Inconsistencia**: Valores o fechas que no coinciden
- **Gap**: Aspecto no cubierto que debería estarlo
- **Superposición**: Cubren lo mismo con diferente redacción

### PASO 4: Evaluación de Impacto
Para cada problema:
- ¿Qué pasaría si ambas cláusulas se aplicaran como están escritas?
- ¿Cuál prevalecería en caso de disputa?
- ¿Es posible una interpretación armónica?

### PASO 5: Score de Coherencia
Calcula el score basado en:
- 100: Sin problemas detectados
- -10 por cada problema bajo
- -20 por cada problema medio
- -30 por cada problema alto
- -40 por cada problema crítico

## FORMATO DE RESPUESTA
```json
{{
    "clause_inventory": [
        {{
            "clause_id": "id",
            "main_topic": "tema",
            "key_dates": ["fechas"],
            "key_amounts": ["montos"],
            "key_obligations": ["obligaciones"]
        }}
    ],
    "comparison_matrix": [
        {{
            "clause_pair": ["id_1", "id_2"],
            "shared_topics": ["temas compartidos"],
            "discrepancies_found": true/false
        }}
    ],
    "cross_clause_issues": [
        {{
            "type": "contradiction|inconsistency|gap|overlap",
            "severity": "low|medium|high|critical",
            "affected_clauses": ["id_1", "id_2"],
            "description": "Descripción del problema encontrado",
            "evidence_clause_1": "Cita de la primera cláusula",
            "evidence_clause_2": "Cita de la segunda cláusula",
            "practical_consequence": "Qué pasaría si no se resuelve",
            "recommendation": "Cómo resolver el problema"
        }}
    ],
    "overall_coherence_score": 0-100,
    "score_calculation": "Explicación de cómo se calculó el score",
    "summary": "Resumen ejecutivo del análisis",
    "reasoning": "Proceso de razonamiento seguido"
}}
```"""


# ===========================================
# REGISTER ENHANCED TEMPLATES
# ===========================================

# Clause Analysis v1.1 (CoT)
CLAUSE_ANALYSIS_COT_V1_1 = PromptTemplate(
    task_name="clause_analysis",
    version="1.1",
    description="Análisis de cláusula con chain-of-thought mejorado",
    system_prompt=COHERENCE_ANALYST_COT_SYSTEM,
    user_prompt_template=CLAUSE_ANALYSIS_COT_TEMPLATE,
    metadata={
        "author": "C2Pro Team",
        "date": "2026-03-07",
        "changelog": "Added chain-of-thought reasoning steps and element checklist",
        "improvement": "Better consistency and explainability",
    },
)

# Rule Verification v1.1 (CoT)
RULE_VERIFICATION_COT_V1_1 = PromptTemplate(
    task_name="rule_verification",
    version="1.1",
    description="Verificación de regla con chain-of-thought mejorado",
    system_prompt=RULE_CHECKER_COT_SYSTEM,
    user_prompt_template=RULE_VERIFICATION_COT_TEMPLATE,
    metadata={
        "author": "C2Pro Team",
        "date": "2026-03-07",
        "changelog": "Added structured reasoning steps and rule understanding",
        "improvement": "More consistent rule evaluation",
    },
)

# Cross-Clause Analysis v1.1 (CoT)
CROSS_CLAUSE_COT_V1_1 = PromptTemplate(
    task_name="cross_clause_analysis",
    version="1.1",
    description="Análisis cruzado con chain-of-thought y matriz de comparación",
    system_prompt=COHERENCE_ANALYST_COT_SYSTEM,
    user_prompt_template=CROSS_CLAUSE_COT_TEMPLATE,
    metadata={
        "author": "C2Pro Team",
        "date": "2026-03-07",
        "changelog": "Added clause inventory and comparison matrix",
        "improvement": "Systematic cross-reference analysis",
    },
)

# Register all templates
register_template(CLAUSE_ANALYSIS_COT_V1_1)
register_template(RULE_VERIFICATION_COT_V1_1)
register_template(CROSS_CLAUSE_COT_V1_1)


# ===========================================
# EXPORTS
# ===========================================

__all__ = [
    "COHERENCE_ANALYST_COT_SYSTEM",
    "RULE_CHECKER_COT_SYSTEM",
    "CLAUSE_ANALYSIS_COT_TEMPLATE",
    "RULE_VERIFICATION_COT_TEMPLATE",
    "CROSS_CLAUSE_COT_TEMPLATE",
    "CLAUSE_ANALYSIS_COT_V1_1",
    "RULE_VERIFICATION_COT_V1_1",
    "CROSS_CLAUSE_COT_V1_1",
]
