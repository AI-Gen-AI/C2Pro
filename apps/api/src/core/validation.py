"""
C2Pro - Input Validation Utilities

Funciones de validación y sanitización para prevenir inyecciones SQL
y otros ataques de entrada maliciosa.
"""

import re

# Patrones sospechosos de inyección SQL
SQL_INJECTION_PATTERNS = [
    r"('|(\\'))",  # Comillas simples
    r"(-{2})",  # Comentarios SQL (--)
    r"(;|\x00)",  # Punto y coma o null byte
    r"(\bunion\b.*\bselect\b)",  # UNION SELECT
    r"(\bor\b.*=.*)",  # OR 1=1
    r"(\bdrop\b.*\btable\b)",  # DROP TABLE
    r"(\binsert\b.*\binto\b)",  # INSERT INTO
    r"(\bupdate\b.*\bset\b)",  # UPDATE SET
    r"(\bdelete\b.*\bfrom\b)",  # DELETE FROM
    r"(\bexec\b|\bexecute\b)",  # EXEC/EXECUTE
    r"(\bsleep\b\s*\()",  # SLEEP() - time-based injection
    r"(\bwaitfor\b.*\bdelay\b)",  # WAITFOR DELAY
    r"(\bcast\b.*\bas\b)",  # CAST AS
    r"(\bconcat\b\s*\()",  # CONCAT()
]


def sanitize_search_query(query: str | None, max_length: int = 100) -> str | None:
    """
    Sanitiza una consulta de búsqueda para prevenir inyección SQL.

    Args:
        query: La consulta de búsqueda a sanitizar
        max_length: Longitud máxima permitida

    Returns:
        Query sanitizada, o un patrón imposible de coincidir si se detecta contenido malicioso

    Raises:
        None
    """
    # Si no hay query, retornar None
    if not query or not query.strip():
        return None

    # Limitar longitud
    query = query.strip()[:max_length]

    # Detectar patrones sospechosos (case-insensitive)
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            # Retornar un UUID aleatorio que nunca coincidirá con nombres/códigos de proyecto
            # Esto hace que la búsqueda devuelva 0 resultados en lugar de todos
            return "00000000-0000-0000-0000-000000000000-INVALID-SEARCH-SANITIZED"

    # Si pasa todas las validaciones, retornar query limpia
    return query


def is_valid_uuid_string(value: str) -> bool:
    """
    Valida que una cadena tenga formato UUID válido.

    Args:
        value: La cadena a validar

    Returns:
        True si es un UUID válido, False si no
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitiza un nombre de archivo para prevenir path traversal.

    Args:
        filename: Nombre de archivo a sanitizar
        max_length: Longitud máxima permitida

    Returns:
        Nombre de archivo sanitizado
    """
    # Remover caracteres peligrosos
    dangerous_chars = ["/", "\\", "..", "\x00", "\n", "\r"]
    sanitized = filename

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "_")

    # Limitar longitud
    sanitized = sanitized[:max_length]

    # Asegurar que no esté vacío
    if not sanitized or sanitized.isspace():
        sanitized = "unnamed"

    return sanitized
