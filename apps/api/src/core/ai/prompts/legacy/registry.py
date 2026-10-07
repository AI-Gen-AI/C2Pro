"""Legacy compatibility adapter for the local PromptManager registry.

NON-AUTHORITATIVE: the canonical Prompt Hub synchronization registry is
`src.core.ai.prompt_registry.PromptRegistry`.
"""

from __future__ import annotations

from src.core.ai.prompts import PromptTemplate, register_template


class LegacyPromptRegistry:
    """Compatibility adapter that registers into the local PromptManager store."""

    def register(self, template: PromptTemplate) -> None:
        register_template(template)


__all__ = ["LegacyPromptRegistry", "PromptTemplate"]
