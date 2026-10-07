"""Architecture contracts for prompt authority boundaries (Wave 3.10)."""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

QUARANTINED_PREFIXES = (
    "src.core.ai.prompts.legacy",
    "src.core.ai.prompts.tooling",
)


def _api_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _package_for_path(api_root: Path, path: Path) -> str:
    relative = path.relative_to(api_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
        return ".".join(parts)
    return ".".join(parts[:-1])


def _resolved_imports(content: str, *, package: str) -> set[str]:
    imports: set[str] = set()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level:
            relative_name = "." * node.level + (node.module or "")
            try:
                base = resolve_name(relative_name, package)
            except ImportError:
                continue
        else:
            base = node.module or ""

        if base:
            imports.add(base)
            imports.update(f"{base}.{alias.name}" for alias in node.names)
    return imports


def test_legacy_and_tooling_assets_live_outside_canonical_prompt_namespace() -> None:
    api_root = _api_root()
    prompts = api_root / "src/core/ai/prompts"

    for old_path in (
        prompts / "registry.py",
        prompts / "i18n.py",
        prompts / "validator.py",
        prompts / "v1/coherence_analysis.py",
        prompts / "v1/contract_extraction.py",
        prompts / "v1_1/coherence_analysis_cot.py",
    ):
        assert not old_path.exists()

    assert (prompts / "legacy/registry.py").exists()
    assert (prompts / "legacy/i18n.py").exists()
    assert (prompts / "legacy/v1/coherence_analysis.py").exists()
    assert (prompts / "legacy/v1_1/coherence_analysis_cot.py").exists()
    assert (prompts / "tooling/validator.py").exists()


def test_only_prompt_hub_registry_keeps_prompt_registry_name() -> None:
    from src.core.ai import prompt_registry as canonical_registry
    from src.core.ai.prompts.legacy import registry as legacy_registry

    assert hasattr(canonical_registry, "PromptRegistry")
    assert hasattr(legacy_registry, "LegacyPromptRegistry")
    assert not hasattr(legacy_registry, "PromptRegistry")


def test_production_source_does_not_import_prompt_legacy_or_tooling() -> None:
    api_root = _api_root()
    src_root = api_root / "src"
    offenders: set[Path] = set()

    for path in src_root.rglob("*.py"):
        relative = path.relative_to(api_root)
        if relative.parts[:5] in {
            ("src", "core", "ai", "prompts", "legacy"),
            ("src", "core", "ai", "prompts", "tooling"),
        }:
            continue

        imports = _resolved_imports(
            path.read_text(encoding="utf-8"),
            package=_package_for_path(api_root, path),
        )
        if any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for imported in imports
            for prefix in QUARANTINED_PREFIXES
        ):
            offenders.add(relative)

    assert offenders == set()


def test_runtime_prompt_manager_remains_the_local_prompt_authority() -> None:
    api_root = _api_root()
    base_tool = (api_root / "src/core/ai/tools/base.py").read_text(encoding="utf-8")
    sync_prompts = (api_root / "src/core/ai/sync_prompts.py").read_text(encoding="utf-8")

    assert "from src.core.ai.prompts import get_prompt_manager" in base_tool
    assert "src.core.ai.prompts.legacy" not in base_tool
    assert "src.core.ai.prompts.tooling" not in base_tool
    assert "from src.core.ai.prompt_registry import PromptHubClient, PromptRegistry" in sync_prompts


def test_import_scanner_detects_absolute_and_relative_quarantine_imports() -> None:
    samples = (
        ("import src.core.ai.prompts.legacy.i18n", "src.core.ai"),
        ("from src.core.ai.prompts import legacy", "src.core.ai"),
        ("from .legacy import registry", "src.core.ai.prompts"),
        ("from .tooling.validator import validate_template", "src.core.ai.prompts"),
    )
    for source, package in samples:
        imports = _resolved_imports(source, package=package)
        assert any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for imported in imports
            for prefix in QUARANTINED_PREFIXES
        )
