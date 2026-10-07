"""Architecture boundary for quarantined Core AI experiments."""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

EXPERIMENTAL_IMPORT = "src.core.ai.experimental"
ALLOWED_PRODUCTION_IMPORTERS = {
    Path("src/modules/extraction/application/ports.py"),
}


def _api_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _package_for_path(api_root: Path, path: Path) -> str:
    relative = path.relative_to(api_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
        return ".".join(parts)
    return ".".join(parts[:-1])


def _imports_experimental(content: str, *, package: str) -> bool:
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == EXPERIMENTAL_IMPORT
                or alias.name.startswith(f"{EXPERIMENTAL_IMPORT}.")
                for alias in node.names
            ):
                return True
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

        if base == EXPERIMENTAL_IMPORT or base.startswith(f"{EXPERIMENTAL_IMPORT}."):
            return True

        if any(
            f"{base}.{alias.name}" == EXPERIMENTAL_IMPORT
            or f"{base}.{alias.name}".startswith(f"{EXPERIMENTAL_IMPORT}.")
            for alias in node.names
            if base
        ):
            return True

    return False


def test_experimental_ai_modules_live_outside_canonical_core_namespace() -> None:
    api_root = _api_root()

    assert not (api_root / "src/core/ai/ab_experiment.py").exists()
    assert not (api_root / "src/core/ai/langsmith_hub.py").exists()
    assert (api_root / "src/core/ai/experimental/ab_experiment.py").exists()
    assert (api_root / "src/core/ai/experimental/langsmith_hub.py").exists()


def test_experimental_ai_coverage_is_quarantined_by_namespace() -> None:
    api_root = _api_root()
    pyproject = (api_root / "pyproject.toml").read_text(encoding="utf-8")

    assert '"src/core/ai/experimental/*"' in pyproject
    assert '"src/core/ai/ab_experiment.py"' not in pyproject
    assert '"src/core/ai/langsmith_hub.py"' not in pyproject


def test_only_explicit_legacy_surface_imports_experimental_ai() -> None:
    api_root = _api_root()
    src_root = api_root / "src"
    importers: set[Path] = set()

    for path in src_root.rglob("*.py"):
        relative = path.relative_to(api_root)
        if relative.parts[:4] == ("src", "core", "ai", "experimental"):
            continue
        content = path.read_text(encoding="utf-8")
        if _imports_experimental(
            content,
            package=_package_for_path(api_root, path),
        ):
            importers.add(relative)

    assert importers == ALLOWED_PRODUCTION_IMPORTERS


def test_experimental_import_scanner_detects_supported_import_forms() -> None:
    samples = [
        "import src.core.ai.experimental.langsmith_hub",
        "from src.core.ai.experimental import langsmith_hub",
        "from src.core.ai import experimental",
        "from .experimental.langsmith_hub import PromptHubResolver",
        "from . import experimental",
    ]

    assert all(
        _imports_experimental(sample, package="src.core.ai")
        for sample in samples
    )


def test_experimental_import_scanner_ignores_unrelated_imports() -> None:
    assert not _imports_experimental(
        "from src.core.ai import prompts",
        package="src.core.ai",
    )


def test_legacy_extraction_surface_declares_non_authoritative_prompt_hub_dependency() -> None:
    api_root = _api_root()
    content = (api_root / "src/modules/extraction/application/ports.py").read_text(
        encoding="utf-8"
    )

    assert "LEGACY / NON-AUTHORITATIVE APPLICATION SERVICE" in content
    assert (
        "from src.core.ai.experimental.langsmith_hub import PromptHubResolver"
        in content
    )
