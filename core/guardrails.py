"""Guardrails — Validacion de esquemas y cortacircuitos de seguridad.

Valida que las salidas de los agentes cumplan con los JSON Schema
antes de permitir escrituras en blackboard.json o en el disco.
"""
import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path("schemas")


def validar_blackboard(data: dict) -> list[str]:
    """Valida blackboard.json contra su esquema. Devuelve lista de errores."""
    esquema = _cargar_esquema("blackboard_schema.json")
    if not esquema:
        return ["Esquema blackboard no encontrado"]
    return _validar_contra_esquema(data, esquema)


def validar_salida_backend(data: dict) -> list[str]:
    """Valida la salida del agente backend contra su esquema."""
    esquema = _cargar_esquema("backend_output.json")
    if not esquema:
        return ["Esquema backend no encontrado"]
    return _validar_contra_esquema(data, esquema)


def validar_reporte_qa(data: dict) -> list[str]:
    """Valida el reporte QA contra su esquema."""
    esquema = _cargar_esquema("qa_report_schema.json")
    if not esquema:
        return ["Esquema QA no encontrado"]
    return _validar_contra_esquema(data, esquema)


def validar_plan(data: dict) -> list[str]:
    """Valida el plan del planner contra su esquema."""
    esquema = _cargar_esquema("plan_output.json")
    if not esquema:
        return ["Esquema plan no encontrado"]
    return _validar_contra_esquema(data, esquema)


def verificar_ruta_protegida(ruta: str, rutas_protegidas: list[str]) -> bool:
    """Verifica si una ruta esta protegida (no modificable)."""
    from fnmatch import fnmatch
    for patron in rutas_protegidas:
        if fnmatch(ruta, patron):
            return True
    return False


def verificar_cortacircuitos(bb: dict) -> bool:
    """Verifica si el cortacircuitos de reintentos esta activado."""
    reintentos = bb.get("reintentos", 0)
    max_reintentos = bb.get("max_reintentos", 3)
    return reintentos >= max_reintentos


def _cargar_esquema(nombre: str) -> dict | None:
    """Carga un JSON Schema desde el directorio de esquemas."""
    ruta = SCHEMAS_DIR / nombre
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _validar_contra_esquema(data: dict, esquema: dict) -> list[str]:
    """Validacion manual basica contra JSON Schema (sin jsonschema lib)."""
    errores = []

    # Validar campos requeridos
    requeridos = esquema.get("required", [])
    for campo in requeridos:
        if campo not in data:
            errores.append(f"Campo requerido ausente: {campo}")

    # Validar tipos
    propiedades = esquema.get("properties", {})
    for campo, valor in data.items():
        if campo in propiedades:
            tipo_esperado = propiedades[campo].get("type")
            if tipo_esperado and not _coincide_tipo(valor, tipo_esperado):
                errores.append(f"Tipo incorrecto para '{campo}': esperado {tipo_esperado}, obtenido {type(valor).__name__}")

            # Validar enum
            enum_valores = propiedades[campo].get("enum")
            if enum_valores and valor not in enum_valores:
                errores.append(f"Valor invalido para '{campo}': {valor}. Debe ser uno de: {enum_valores}")

    # Validar propiedades adicionales no permitidas
    if esquema.get("additionalProperties") is False:
        permitidos = set(propiedades.keys())
        for campo in data:
            if campo not in permitidos:
                errores.append(f"Propiedad no permitida: {campo}")

    # Validar items de arrays
    for campo, valor in data.items():
        if isinstance(valor, list) and "items" in propiedades.get(campo, {}):
            item_schema = propiedades[campo]["items"]
            for i, item in enumerate(valor):
                if isinstance(item, dict) and "properties" in item_schema:
                    item_errores = _validar_contra_esquema(item, item_schema)
                    errores.extend([f"{campo}[{i}].{e}" for e in item_errores])

    return errores


def _coincide_tipo(valor: Any, tipo_esperado: str) -> bool:
    """Verifica si un valor coincide con el tipo JSON Schema esperado."""
    tipo_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    tipo_python = tipo_map.get(tipo_esperado)
    if tipo_python is None:
        return True
    # null es siempre aceptable si el schema lo permite
    if valor is None:
        return True
    # bool es subclase de int en Python, manejar explicitamente
    if tipo_esperado == "integer" and isinstance(valor, bool):
        return False
    return isinstance(valor, tipo_python)


if __name__ == "__main__":
    # Test rapido de validacion
    test_bb = {
        "session_id": "test_001",
        "objetivo_global": "Test",
        "estado_actual": "idle",
        "tareas": [],
        "contexto_paso_anterior": "",
        "trazas_de_error": [],
        "reintentos": 0,
        "max_reintentos": 3,
    }
    errores = validar_blackboard(test_bb)
    if errores:
        print(f"ERRORES: {errores}")
    else:
        print("Validacion OK: blackboard.json es valido")
