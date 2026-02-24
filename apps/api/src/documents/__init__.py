"""
Public contracts for Documents module.

Expose only ports and application DTOs as public API.

Uses lazy imports (PEP 562) to avoid eagerly loading port
implementations and their transitive dependencies.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str | None]] = {
    "ports": ("src.documents.ports", None),
    "dtos":  ("src.documents.application.dtos", None),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr) if attr else mod
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.documents' has no attribute {name!r}")
