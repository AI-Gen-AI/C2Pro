from __future__ import annotations

import importlib

__all__ = ["models", "service", "schemas", "router"]


def __getattr__(name: str):
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
