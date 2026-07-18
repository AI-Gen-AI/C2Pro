"""Test fixtures for core/ai tests."""
from __future__ import annotations

import pytest

from src.core.ai.prompts import (
    COHERENCE_CHECK_V1_0,
    CONTRACT_EXTRACTION_V1_0,
    PROMPT_REGISTRY,
    STAKEHOLDER_CLASSIFICATION_V1_0,
    register_template,
)

_BASE_TEMPLATES = (
    CONTRACT_EXTRACTION_V1_0,
    STAKEHOLDER_CLASSIFICATION_V1_0,
    COHERENCE_CHECK_V1_0,
)


@pytest.fixture(autouse=True)
def _reset_prompt_registry():
    """Clear and re-register only base V1.0 templates to prevent i18n pollution."""
    saved = dict(PROMPT_REGISTRY)
    PROMPT_REGISTRY.clear()
    for template in _BASE_TEMPLATES:
        register_template(template)
    yield
    PROMPT_REGISTRY.clear()
    PROMPT_REGISTRY.update(saved)
