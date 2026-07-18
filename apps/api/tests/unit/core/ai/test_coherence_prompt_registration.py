"""TS-UT-CORE-AI-COHERENCE-001: Legacy coherence prompt registration coverage."""

from src.core.ai.prompts import PROMPT_REGISTRY
from src.core.ai.prompts.registry import PromptRegistry
from src.core.ai.prompts.v1.coherence_analysis import register_coherence_prompts


def test_register_coherence_prompts_uses_current_template_contract() -> None:
    """TS-UT-CORE-AI-COHERENCE-001: Legacy prompt registration remains executable."""
    prompt_names = {
        "coherence_clause_analysis",
        "coherence_rule_verification",
        "coherence_cross_clause",
        "coherence_project_analysis",
        "coherence_budget_analysis",
        "coherence_schedule_analysis",
    }
    previous_templates = {name: PROMPT_REGISTRY.get(name) for name in prompt_names}

    try:
        register_coherence_prompts(PromptRegistry())

        assert prompt_names <= PROMPT_REGISTRY.keys()
    finally:
        for name, previous_template in previous_templates.items():
            if previous_template is None:
                PROMPT_REGISTRY.pop(name, None)
            else:
                PROMPT_REGISTRY[name] = previous_template
