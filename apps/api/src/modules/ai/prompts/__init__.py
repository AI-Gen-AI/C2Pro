"""
C2Pro - Prompt Templates with Versioning

Sistema centralizado de gestión de plantillas de prompts con soporte para versionado.

Características:
- Templates con Jinja2 para lógica condicional y sustitución de variables
- Versionado completo (trazabilidad para auditoría)
- Separación de system/user prompts
- Registro automático de prompt_version en logs

Uso:
    from src.modules.ai.prompts import get_prompt_manager

    manager = get_prompt_manager()

    # Renderizar un prompt
    prompt, version = manager.render_prompt(
        task_name="contract_extraction",
        context={
            "document_text": "El contrato establece...",
            "max_clauses": 10
        },
        version="latest"  # o "1.0", "1.1", etc.
    )

    # El version retornado se debe guardar en ai_usage_logs.prompt_version

Version: 1.0.0
Author: C2Pro Team
Date: 2026-01-13
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from jinja2 import Environment, Template, select_autoescape

logger = structlog.get_logger()

# ===========================================
# DATA STRUCTURES
# ===========================================


@dataclass
class PromptTemplate:
    """
    Representa una plantilla de prompt versionada.

    Attributes:
        task_name: Nombre de la tarea (ej: "contract_extraction")
        version: Versión del template (ej: "1.0", "1.1")
        system_prompt: Instrucciones fijas para el modelo (rol, contexto)
        user_prompt_template: Template Jinja2 con variables para el user message
        description: Descripción de qué hace este template
        metadata: Información adicional (autor, fecha, changelog, etc.)
    """

    task_name: str
    version: str
    system_prompt: str
    user_prompt_template: str
    description: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        """Valida los campos requeridos."""
        if not self.task_name:
            raise ValueError("task_name is required")
        if not self.version:
            raise ValueError("version is required")
        if not self.user_prompt_template:
            raise ValueError("user_prompt_template is required")


# ===========================================
# PROMPT REGISTRY
# ===========================================

# Registry: task_name -> version -> PromptTemplate
PROMPT_REGISTRY: dict[str, dict[str, PromptTemplate]] = {}


def register_template(template: PromptTemplate) -> None:
    """
    Registra un template en el registry.

    Args:
        template: PromptTemplate a registrar
    """
    if template.task_name not in PROMPT_REGISTRY:
        PROMPT_REGISTRY[template.task_name] = {}

    PROMPT_REGISTRY[template.task_name][template.version] = template

    logger.debug(
        "prompt_template_registered",
        task_name=template.task_name,
        version=template.version,
    )


# ===========================================
# TEMPLATE DEFINITIONS - V1.0
# ===========================================

# ---------------------------------------------
# CONTRACT EXTRACTION v1.0
# ---------------------------------------------
CONTRACT_EXTRACTION_V1_0 = PromptTemplate(
    task_name="contract_extraction",
    version="1.0",
    description="Extrae cláusulas, fechas, montos y metadatos de contratos",
    system_prompt="""Eres un experto legal especializado en análisis de contratos de construcción y obra pública.

Tu tarea es extraer información estructurada de documentos contractuales en español (Chile/LATAM).

Instrucciones:
1. Extrae SOLO información que aparezca explícitamente en el texto
2. Si una información no está presente, indica "No especificado"
3. Para montos, extrae el valor numérico y la moneda (CLP, USD, UF)
4. Para fechas, usa formato ISO 8601 (YYYY-MM-DD)
5. Identifica el tipo de contrato (obra, servicios, suministro, etc.)

IMPORTANTE:
- NO inventes información
- NO hagas suposiciones
- Sé preciso con cifras y fechas
- Mantén los nombres exactos de las partes""",
    user_prompt_template="""Analiza el siguiente documento contractual y extrae la información solicitada.

DOCUMENTO:
```
{{ document_text }}
```

{% if max_clauses %}
LÍMITE: Extrae máximo {{ max_clauses }} cláusulas principales.
{% endif %}

Retorna la información en el siguiente formato JSON:

{
  "partes": {
    "contratante": "Nombre oficial",
    "contratista": "Nombre oficial"
  },
  "objeto": "Descripción breve del objeto del contrato",
  "tipo_contrato": "obra|servicios|suministro|otro",
  "monto_total": {
    "valor": 0.00,
    "moneda": "CLP|USD|UF"
  },
  "fechas": {
    "firma": "YYYY-MM-DD",
    "inicio_obra": "YYYY-MM-DD",
    "termino_obra": "YYYY-MM-DD"
  },
  "clausulas_principales": [
    {
      "numero": "X.Y",
      "titulo": "Título de la cláusula",
      "contenido": "Resumen de la cláusula"
    }
  ],
  "garantias": [
    {
      "tipo": "fiel cumplimiento|anticipo|calidad",
      "monto_porcentaje": 0.0
    }
  ]
}""",
    metadata={
        "author": "C2Pro Team",
        "date": "2026-01-13",
        "changelog": "Initial version",
    },
)

# ---------------------------------------------
# STAKEHOLDER CLASSIFICATION v1.0
# ---------------------------------------------
STAKEHOLDER_CLASSIFICATION_V1_0 = PromptTemplate(
    task_name="stakeholder_classification",
    version="1.0",
    description="Clasifica stakeholders por nivel de poder e interés (matriz poder-interés)",
    system_prompt="""Eres un analista de stakeholders experto en proyectos de construcción y obra pública.

Tu tarea es clasificar stakeholders según la matriz de Poder-Interés:
- PODER: Capacidad de influir en el proyecto (Alto/Medio/Bajo)
- INTERÉS: Nivel de afectación o interés en el proyecto (Alto/Medio/Bajo)

Criterios de clasificación:
- PODER ALTO: Autoridades, financistas, gerentes de proyecto, reguladores
- PODER MEDIO: Jefes de área, supervisores, proveedores principales
- PODER BAJO: Vecinos, comunidad local, proveedores menores

- INTERÉS ALTO: Directamente afectados por el proyecto (positiva o negativamente)
- INTERÉS MEDIO: Afectación indirecta o moderada
- INTERÉS BAJO: Afectación mínima o tangencial

IMPORTANTE:
- Usa el contexto del proyecto para la clasificación
- Considera regulaciones chilenas/LATAM
- Sé objetivo en la evaluación""",
    user_prompt_template="""Clasifica los siguientes stakeholders del proyecto.

CONTEXTO DEL PROYECTO:
{{ project_description }}

STAKEHOLDERS A CLASIFICAR:
{% for stakeholder in stakeholders %}
- {{ stakeholder.name }}{% if stakeholder.role %} ({{ stakeholder.role }}){% endif %}
{% endfor %}

Retorna el análisis en formato JSON:

{
  "clasificaciones": [
    {
      "stakeholder": "Nombre",
      "poder": "alto|medio|bajo",
      "interes": "alto|medio|bajo",
      "cuadrante": "gestionar_de_cerca|mantener_satisfecho|mantener_informado|monitorear",
      "justificacion": "Breve explicación de por qué se asignó este nivel",
      "estrategia_recomendada": "Cómo gestionar esta relación"
    }
  ]
}

Mapeo de cuadrantes:
- Poder Alto + Interés Alto = "gestionar_de_cerca"
- Poder Alto + Interés Bajo = "mantener_satisfecho"
- Poder Bajo + Interés Alto = "mantener_informado"
- Poder Bajo + Interés Bajo = "monitorear" """,
    metadata={
        "author": "C2Pro Team",
        "date": "2026-01-13",
        "changelog": "Initial version",
    },
)

# ---------------------------------------------
# COHERENCE CHECK v1.0
# ---------------------------------------------
COHERENCE_CHECK_V1_0 = PromptTemplate(
    task_name="coherence_check",
    version="1.0",
    description="Detecta contradicciones entre fechas, montos y compromisos en documentos",
    system_prompt="""Eres un auditor experto en detectar inconsistencias y contradicciones en documentación de proyectos.

Tu tarea es identificar:
1. Contradicciones en FECHAS (plazos incompatibles, secuencias ilógicas)
2. Contradicciones en MONTOS (sumas incorrectas, valores duplicados o inconsistentes)
3. Contradicciones en COMPROMISOS (obligaciones conflictivas)

Tipos de inconsistencias a detectar:
- Fechas de término anteriores a fechas de inicio
- Hitos con fechas fuera del plazo total del proyecto
- Montos parciales que no suman el total declarado
- Mismo concepto con diferentes montos en distintas secciones
- Compromisos mutuamente excluyentes
- Referencias a documentos inexistentes

IMPORTANTE:
- Reporta SOLO contradicciones verificables
- Incluye referencias exactas (secciones, párrafos)
- Indica el nivel de severidad (crítico/moderado/menor)
- Sugiere correcciones cuando sea obvio el error""",
    user_prompt_template="""Analiza los siguientes documentos para detectar contradicciones.

{% if document_pairs %}
DOCUMENTOS A COMPARAR:
{% for doc in document_pairs %}
### Documento {{ loop.index }}: {{ doc.name }}
```
{{ doc.content }}
```
{% endfor %}
{% else %}
DOCUMENTO A ANALIZAR:
```
{{ document_text }}
```
{% endif %}

{% if check_types %}
TIPOS DE VERIFICACIÓN SOLICITADOS:
{% for check_type in check_types %}
- {{ check_type }}
{% endfor %}
{% endif %}

Retorna el análisis en formato JSON:

{
  "coherencia_global": {
    "score": 0.85,  // 0.0 (muy incoherente) a 1.0 (perfectamente coherente)
    "es_coherente": true,
    "resumen": "Descripción general del estado de coherencia"
  },
  "contradicciones": [
    {
      "tipo": "fecha|monto|compromiso|otro",
      "severidad": "critico|moderado|menor",
      "descripcion": "Descripción clara de la contradicción",
      "ubicaciones": [
        {
          "documento": "nombre_documento",
          "seccion": "Sección 3.2",
          "texto_relevante": "Fragmento que muestra la contradicción"
        }
      ],
      "impacto": "Explicación del impacto de esta contradicción",
      "sugerencia_correccion": "Cómo podría resolverse (si es obvio)"
    }
  ],
  "advertencias": [
    {
      "tipo": "fecha_proxima|monto_ambiguo|termino_confuso",
      "descripcion": "Advertencia sobre posibles problemas",
      "ubicacion": "Dónde se encontró"
    }
  ]
}""",
    metadata={
        "author": "C2Pro Team",
        "date": "2026-01-13",
        "changelog": "Initial version",
    },
)

# Registrar todos los templates
register_template(CONTRACT_EXTRACTION_V1_0)
register_template(STAKEHOLDER_CLASSIFICATION_V1_0)
register_template(COHERENCE_CHECK_V1_0)


# ===========================================
# PROMPT MANAGER
# ===========================================


class PromptManager:
    """
    Gestor centralizado de plantillas de prompts.

    Responsabilidades:
    - Obtener templates por nombre y versión
    - Renderizar templates con contexto dinámico (Jinja2)
    - Retornar la versión utilizada para logging
    - Validar variables requeridas

    Uso:
        manager = PromptManager()

        prompt, version = manager.render_prompt(
            task_name="contract_extraction",
            context={"document_text": "..."},
            version="latest"
        )

        # Guardar 'version' en ai_usage_logs.prompt_version
    """

    def __init__(self):
        """Inicializa el PromptManager con el entorno Jinja2."""
        self.env = Environment(
            autoescape=select_autoescape(),
            trim_blocks=True,  # Elimina whitespace después de tags
            lstrip_blocks=True,  # Elimina whitespace antes de tags
        )

        logger.info(
            "prompt_manager_initialized",
            registered_tasks=list(PROMPT_REGISTRY.keys()),
            total_versions=sum(len(versions) for versions in PROMPT_REGISTRY.values()),
        )

    # ===========================================
    # MAIN METHODS
    # ===========================================

    def get_template(self, task_name: str, version: str = "latest") -> PromptTemplate:
        """
        Obtiene un template por nombre y versión.

        Args:
            task_name: Nombre de la tarea (ej: "contract_extraction")
            version: Versión del template (ej: "1.0", "1.1", "latest")

        Returns:
            PromptTemplate correspondiente

        Raises:
            ValueError: Si el task_name no existe
            ValueError: Si la versión no existe
        """
        if task_name not in PROMPT_REGISTRY:
            available_tasks = ", ".join(PROMPT_REGISTRY.keys())
            raise ValueError(
                f"Task '{task_name}' not found in prompt registry. "
                f"Available tasks: {available_tasks}"
            )

        task_versions = PROMPT_REGISTRY[task_name]

        # Si se solicita "latest", obtener la versión más reciente
        if version == "latest":
            version = self._get_latest_version(task_name)
            logger.debug(
                "using_latest_prompt_version",
                task_name=task_name,
                resolved_version=version,
            )

        if version not in task_versions:
            available_versions = ", ".join(task_versions.keys())
            raise ValueError(
                f"Version '{version}' not found for task '{task_name}'. "
                f"Available versions: {available_versions}"
            )

        template = task_versions[version]

        logger.debug(
            "prompt_template_retrieved",
            task_name=task_name,
            version=version,
            description=template.description,
        )

        return template

    def render_prompt(
        self,
        task_name: str,
        context: dict[str, Any],
        version: str = "latest",
    ) -> tuple[str, str, str]:
        """
        Renderiza un prompt con el contexto provisto.

        Args:
            task_name: Nombre de la tarea
            context: Diccionario con variables para el template
            version: Versión del template a usar

        Returns:
            Tupla de (system_prompt, user_prompt, version_used)

            - system_prompt: Instrucciones fijas para el modelo
            - user_prompt: Mensaje renderizado con el contexto
            - version_used: Versión exacta utilizada (para logging)

        Raises:
            ValueError: Si el template no existe
            jinja2.TemplateError: Si hay error en el renderizado

        Ejemplo:
            system, user, ver = manager.render_prompt(
                "contract_extraction",
                {"document_text": "El contrato..."},
                "1.0"
            )

            # Usar system y user para llamar a la API
            # Guardar 'ver' en ai_usage_logs.prompt_version
        """
        # 1. Obtener template
        template = self.get_template(task_name, version)

        # 2. Renderizar user prompt con Jinja2
        try:
            jinja_template = self.env.from_string(template.user_prompt_template)
            user_prompt = jinja_template.render(**context)

        except Exception as e:
            logger.error(
                "prompt_render_failed",
                task_name=task_name,
                version=template.version,
                error=str(e),
                context_keys=list(context.keys()),
            )
            raise ValueError(
                f"Failed to render prompt for task '{task_name}' v{template.version}: {e}"
            ) from e

        logger.info(
            "prompt_rendered",
            task_name=task_name,
            version=template.version,
            user_prompt_length=len(user_prompt),
            system_prompt_length=len(template.system_prompt),
            context_keys=list(context.keys()),
        )

        # 3. Retornar ambos prompts + versión utilizada
        return template.system_prompt, user_prompt, template.version

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def _get_latest_version(self, task_name: str) -> str:
        """
        Obtiene la versión más reciente de un template.

        Estrategia: Ordenar versiones semánticamente (1.0, 1.1, 2.0, etc.)
        Si no se puede parsear como semver, usar la última alfabéticamente.

        Args:
            task_name: Nombre de la tarea

        Returns:
            Versión más reciente como string
        """
        versions = list(PROMPT_REGISTRY[task_name].keys())

        if not versions:
            raise ValueError(f"No versions found for task '{task_name}'")

        # Intentar ordenar semánticamente
        try:
            # Convertir "1.0" -> (1, 0), "1.1" -> (1, 1)
            def parse_version(v: str) -> tuple[int, ...]:
                return tuple(int(x) for x in v.split("."))

            sorted_versions = sorted(versions, key=parse_version, reverse=True)
            return sorted_versions[0]

        except (ValueError, AttributeError):
            # Si falla el parseo semántico, usar orden alfabético
            return sorted(versions, reverse=True)[0]

    def list_tasks(self) -> list[str]:
        """Retorna lista de todas las tareas disponibles."""
        return list(PROMPT_REGISTRY.keys())

    def list_versions(self, task_name: str) -> list[str]:
        """
        Retorna lista de versiones disponibles para una tarea.

        Args:
            task_name: Nombre de la tarea

        Returns:
            Lista de versiones (ordenadas)

        Raises:
            ValueError: Si el task_name no existe
        """
        if task_name not in PROMPT_REGISTRY:
            raise ValueError(f"Task '{task_name}' not found")

        versions = list(PROMPT_REGISTRY[task_name].keys())

        # Ordenar semánticamente si es posible
        try:

            def parse_version(v: str) -> tuple[int, ...]:
                return tuple(int(x) for x in v.split("."))

            return sorted(versions, key=parse_version)
        except (ValueError, AttributeError):
            return sorted(versions)

    def get_template_info(self, task_name: str, version: str = "latest") -> dict[str, Any]:
        """
        Obtiene información sobre un template (sin renderizar).

        Args:
            task_name: Nombre de la tarea
            version: Versión del template

        Returns:
            Diccionario con metadata del template
        """
        template = self.get_template(task_name, version)

        return {
            "task_name": template.task_name,
            "version": template.version,
            "description": template.description,
            "system_prompt_length": len(template.system_prompt),
            "user_template_length": len(template.user_prompt_template),
            "metadata": template.metadata or {},
        }


# ===========================================
# FACTORY & SINGLETON
# ===========================================

_prompt_manager_instance: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """
    Factory singleton para PromptManager.

    Returns:
        Instancia única de PromptManager
    """
    global _prompt_manager_instance

    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager()

    return _prompt_manager_instance


# Export public API
__all__ = [
    "PromptTemplate",
    "PromptManager",
    "get_prompt_manager",
    "register_template",
    "PROMPT_REGISTRY",
    "CONTRACT_EXTRACTION_V1_0",
    "STAKEHOLDER_CLASSIFICATION_V1_0",
    "COHERENCE_CHECK_V1_0",
]
