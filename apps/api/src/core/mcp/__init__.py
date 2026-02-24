"""
C2Pro - MCP (Model Context Protocol) Integration

Este paquete contiene los servidores MCP para integración segura
con agentes de IA y sistemas externos.

Security First:
- Allowlist estricta de vistas y funciones
- Query limits (timeout, row count, cost)
- Rate limiting por tenant
- Logging completo para auditoría
- NO permite SQL arbitrario

Uses lazy imports (PEP 562) to avoid pulling in database
dependencies at ``import src.core.mcp`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DatabaseMCPServer": ("src.core.mcp.servers.database_server", "DatabaseMCPServer"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.mcp' has no attribute {name!r}")
