"""C2PRO-DEV-15 Wave 3.8 assurance for PromptManager runtime authority."""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

import src.core.ai.prompts as prompts_module
from src.core.ai.prompts import (
    COHERENCE_CHECK_V1_0,
    CONTRACT_EXTRACTION_V1_0,
    PROMPT_REGISTRY,
    PromptManager,
    PromptTemplate,
    get_prompt_manager,
    register_template,
)
from src.core.ai.tools.base import BaseTool
from src.core.ai.tools.metadata import ToolResult


def test_prompt_manager_authority_is_measured_without_promoting_legacy_submodules() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    pyproject = tomllib.loads(
        (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert "src/core/ai/prompts/*" not in omitted
    assert "src/core/ai/prompts/legacy/*" in omitted
    assert "src/core/ai/prompts/legacy/v1/*" in omitted
    assert "src/core/ai/prompts/legacy/v1_1/*" in omitted
    assert "src/core/ai/prompts/tooling/*" in omitted

    for stale_path in (
        "src/core/ai/prompts/i18n.py",
        "src/core/ai/prompts/registry.py",
        "src/core/ai/prompts/validator.py",
        "src/core/ai/prompts/v1/*",
        "src/core/ai/prompts/v1_1/*",
    ):
        assert stale_path not in omitted


def test_builtin_prompt_registry_contains_runtime_manager_templates() -> None:
    assert PROMPT_REGISTRY["contract_extraction"]["1.0"] is CONTRACT_EXTRACTION_V1_0
    assert PROMPT_REGISTRY["coherence_check"]["1.0"] is COHERENCE_CHECK_V1_0
    assert {
        "contract_extraction",
        "stakeholder_classification",
        "coherence_check",
    }.issubset(PROMPT_REGISTRY)


@pytest.mark.parametrize(
    ("task_name", "context", "expected_fragment"),
    [
        (
            "contract_extraction",
            {"document_text": "Payment is due in 30 days.", "max_clauses": 3},
            "Payment is due in 30 days.",
        ),
        (
            "stakeholder_classification",
            {
                "project_description": "Solar EPC project",
                "stakeholders": [{"name": "Owner", "role": "Sponsor"}],
            },
            "Solar EPC project",
        ),
        (
            "coherence_check",
            {
                "document_text": "Start 2026-01-01. Finish 2026-12-31.",
                "document_pairs": [],
                "check_types": ["fecha"],
            },
            "Start 2026-01-01",
        ),
    ],
)
def test_prompt_manager_renders_builtin_templates(
    task_name: str,
    context: dict[str, object],
    expected_fragment: str,
) -> None:
    manager = PromptManager()

    system, user, version = manager.render_prompt(
        task_name=task_name,
        context=context,
        version="latest",
    )

    assert system.strip()
    assert expected_fragment in user
    assert version == "1.0"


def test_prompt_manager_rejects_unknown_task_and_version() -> None:
    manager = PromptManager()

    with pytest.raises(ValueError, match="not found in prompt registry"):
        manager.get_template("does_not_exist")

    with pytest.raises(ValueError, match="Version '9.9' not found"):
        manager.get_template("contract_extraction", "9.9")


def test_prompt_template_validates_required_identity_fields() -> None:
    with pytest.raises(ValueError, match="task_name is required"):
        PromptTemplate(
            task_name="",
            version="1.0",
            system_prompt="system",
            user_prompt_template="user",
            description="bad",
        )

    with pytest.raises(ValueError, match="version is required"):
        PromptTemplate(
            task_name="task",
            version="",
            system_prompt="system",
            user_prompt_template="user",
            description="bad",
        )

    with pytest.raises(ValueError, match="user_prompt_template is required"):
        PromptTemplate(
            task_name="task",
            version="1.0",
            system_prompt="system",
            user_prompt_template="",
            description="bad",
        )


def test_prompt_manager_semver_and_fallback_version_ordering() -> None:
    manager = PromptManager()
    task = "wave_3_8_version_order"
    previous = PROMPT_REGISTRY.get(task)

    try:
        PROMPT_REGISTRY[task] = {}
        for version in ("1.2", "1.10", "2.0"):
            register_template(
                PromptTemplate(
                    task_name=task,
                    version=version,
                    system_prompt="system",
                    user_prompt_template="{{ value }}",
                    description=version,
                )
            )

        assert manager.list_versions(task) == ["1.2", "1.10", "2.0"]
        assert manager.get_template(task, "latest").version == "2.0"

        PROMPT_REGISTRY[task] = {
            "beta": PromptTemplate(
                task_name=task,
                version="beta",
                system_prompt="system",
                user_prompt_template="{{ value }}",
                description="beta",
            ),
            "alpha": PromptTemplate(
                task_name=task,
                version="alpha",
                system_prompt="system",
                user_prompt_template="{{ value }}",
                description="alpha",
            ),
        }

        assert manager.list_versions(task) == ["alpha", "beta"]
        assert manager.get_template(task, "latest").version == "beta"
    finally:
        if previous is None:
            PROMPT_REGISTRY.pop(task, None)
        else:
            PROMPT_REGISTRY[task] = previous


def test_prompt_manager_lists_tasks_versions_and_template_info() -> None:
    manager = PromptManager()

    assert "contract_extraction" in manager.list_tasks()
    assert manager.list_versions("contract_extraction") == ["1.0"]

    info = manager.get_template_info("contract_extraction")
    assert info["task_name"] == "contract_extraction"
    assert info["version"] == "1.0"
    assert info["system_prompt_length"] > 0
    assert info["user_template_length"] > 0
    assert info["metadata"]["author"] == "C2Pro Team"

    with pytest.raises(ValueError, match="Task 'missing' not found"):
        manager.list_versions("missing")


def test_get_prompt_manager_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts_module, "_prompt_manager_instance", None)

    first = get_prompt_manager()
    second = get_prompt_manager()

    assert first is second


class _Input(BaseModel):
    text: str


class _RuntimeTool(BaseTool[_Input, dict[str, str]]):
    name = "wave_3_8_runtime_tool"

    async def _execute_impl(self, input_data, tenant_id, ai_response):
        return {"text": input_data.text}

    def extract_input_from_state(self, state):
        return _Input(text=state["text"])

    def inject_output_into_state(
        self,
        state,
        result: ToolResult[dict[str, str]],
    ):
        return state

    def _build_default_prompt(self, input_data, is_retry):
        return input_data.text, None


def test_basetool_runtime_wiring_resolves_default_prompt_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = MagicMock(spec=PromptManager)
    wrapper = SimpleNamespace()

    monkeypatch.setattr("src.core.ai.tools.base.get_prompt_manager", lambda: sentinel)

    tool = _RuntimeTool(anthropic_wrapper=wrapper)

    assert tool.prompt_manager is sentinel


def test_basetool_preserves_injected_prompt_manager() -> None:
    injected = MagicMock(spec=PromptManager)
    wrapper = SimpleNamespace()

    tool = _RuntimeTool(anthropic_wrapper=wrapper, prompt_manager=injected)

    assert tool.prompt_manager is injected
