from __future__ import annotations

"""
Legacy compatibility registry for prompt templates.

Prefer using src.core.ai.prompts.PromptManager.
"""

from src.core.ai.prompts import PromptTemplate, register_template


class PromptRegistry:
    def register(self, template: PromptTemplate) -> None:
        register_template(template)


__all__ = ["PromptRegistry", "PromptTemplate"]
