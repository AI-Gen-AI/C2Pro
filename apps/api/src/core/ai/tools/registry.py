"""
core/ai/tools/registry.py

Central registry for AI tools with autodiscovery.
"""
from __future__ import annotations

from typing import Any, Type

import structlog

from src.core.ai.model_router import AITaskType

from .exceptions import ToolNotFoundError
from .metadata import ToolMetadata
from .protocol import Tool


logger = structlog.get_logger()


class ToolRegistry:
    """
    Central registry for AI tools.

    Supports:
    - Registration by name and version
    - Lookup by name (latest version by default)
    - Lookup by task type
    - List all registered tools
    - Get tool metadata without instantiation

    Usage:
        registry = get_tool_registry()

        # Register tool
        registry.register(RiskExtractionTool)

        # Get tool instance
        tool = registry.get("risk_extraction", version="1.0")

        # Get tool by task type
        tools = registry.get_by_task_type(AITaskType.COMPLEX_EXTRACTION)
    """

    def __init__(self):
        # name -> version -> Tool class
        self._tools: dict[str, dict[str, Type[Tool]]] = {}

        # task_type -> list of (name, version)
        self._task_type_index: dict[AITaskType, list[tuple[str, str]]] = {}

        logger.info("tool_registry_initialized")

    def register(
        self,
        tool_class: Type[Tool],
        name: str | None = None,
        version: str | None = None,
    ) -> None:
        """
        Register a tool class.

        Args:
            tool_class: Tool class (must implement Tool protocol)
            name: Override tool name (uses tool_class.name if None)
            version: Override version (uses tool_class.version if None)
        """
        tool_name = name or getattr(tool_class, "name", tool_class.__name__)
        tool_version = version or getattr(tool_class, "version", "1.0")

        # Validate tool implements protocol
        if not hasattr(tool_class, "execute"):
            raise ValueError(
                f"Tool class {tool_class.__name__} must implement 'execute' method"
            )

        # Register tool
        if tool_name not in self._tools:
            self._tools[tool_name] = {}

        self._tools[tool_name][tool_version] = tool_class

        # Index by task type
        task_type = getattr(tool_class, "task_type", None)
        if task_type:
            if task_type not in self._task_type_index:
                self._task_type_index[task_type] = []
            self._task_type_index[task_type].append((tool_name, tool_version))

        logger.info(
            "tool_registered",
            tool_name=tool_name,
            version=tool_version,
            task_type=task_type.value if task_type else None,
        )

    def get(
        self, name: str, version: str = "latest", **init_kwargs: Any
    ) -> Tool:
        """
        Get a tool instance by name and version.

        Args:
            name: Tool name
            version: Tool version ("latest" for most recent)
            **init_kwargs: Keyword arguments passed to tool constructor

        Returns:
            Instantiated tool

        Raises:
            ToolNotFoundError: If tool not found
        """
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{name}' not found. Available: {list(self._tools.keys())}"
            )

        tool_versions = self._tools[name]

        if version == "latest":
            version = self._get_latest_version(name)

        if version not in tool_versions:
            raise ToolNotFoundError(
                f"Version '{version}' not found for tool '{name}'. "
                f"Available: {list(tool_versions.keys())}"
            )

        tool_class = tool_versions[version]
        return tool_class(**init_kwargs)

    def get_by_task_type(
        self, task_type: AITaskType
    ) -> list[tuple[str, str, Type[Tool]]]:
        """
        Get all tools for a specific task type.

        Returns:
            List of (name, version, tool_class) tuples
        """
        if task_type not in self._task_type_index:
            return []

        result = []
        for name, version in self._task_type_index[task_type]:
            tool_class = self._tools[name][version]
            result.append((name, version, tool_class))

        return result

    def get_metadata(self, name: str, version: str = "latest") -> ToolMetadata:
    """Get tool metadata without instantiating."""
    return self.get(name, version).metadata
        """Get tool metadata without instantiating."""
        tool = self.get(name, version)
        return tool.metadata

    def list_tools(self) -> list[tuple[str, list[str]]]:
        """
        List all registered tools.

        Returns:
            List of (name, versions) tuples
        """
        return [
            (name, list(versions.keys())) for name, versions in self._tools.items()
        ]

    def _get_latest_version(self, name: str) -> str:
        """Get latest version of a tool."""
        versions = list(self._tools[name].keys())

        try:
            # Try semantic versioning
            def parse_version(v: str) -> tuple[int, ...]:
                return tuple(int(x) for x in v.split("."))

            return sorted(versions, key=parse_version, reverse=True)[0]
        except (ValueError, AttributeError):
            # Fallback to alphabetical
            return sorted(versions, reverse=True)[0]


# ============================================
# SINGLETON INSTANCE
# ============================================

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton tool registry instance."""
    global _registry

    if _registry is None:
        _registry = ToolRegistry()

    return _registry


def reset_registry() -> None:
    """Reset registry (for testing)."""
    global _registry
    _registry = None


# ============================================
# DECORATOR FOR AUTODISCOVERY
# ============================================


def register_tool(
    name: str | None = None,
    version: str | None = None,
    auto_register: bool = True,
):
    """
    Decorator for automatic tool registration.

    Usage:
        @register_tool("risk_extraction", version="1.0")
        class RiskExtractionTool(BaseTool[RiskInput, list[RiskItem]]):
            '''Extracts risks from contracts'''
            pass

    Args:
        name: Tool name (uses class name if None)
        version: Tool version (uses class attribute if None)
        auto_register: If True, register immediately on import
    """

    def decorator(cls: Type[Tool]) -> Type[Tool]:
        if auto_register:
            registry = get_tool_registry()
            registry.register(cls, name=name, version=version)

        # Attach metadata to class for introspection
        cls._tool_registry_name = name or getattr(cls, "name", cls.__name__)
        cls._tool_registry_version = version or getattr(cls, "version", "1.0")

        return cls

    return decorator


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================


def get_tool(name: str, version: str = "latest", **kwargs: Any) -> Tool:
    """
    Convenience function to get a tool instance.

    Equivalent to: get_tool_registry().get(name, version, **kwargs)
    """
    return get_tool_registry().get(name, version, **kwargs)


def list_tools() -> list[tuple[str, list[str]]]:
    """List all registered tools."""
    return get_tool_registry().list_tools()
