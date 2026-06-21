"""Category registry path resolution tests.

Test Suite ID: TS-IA-COH-ROUTING-001
"""

from __future__ import annotations

from pathlib import Path

from src.coherence import category_registry


def test_load_category_registry_uses_package_copy_when_docs_path_is_absent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Test Suite ID: TS-IA-COH-ROUTING-001."""
    monkeypatch.chdir(tmp_path)

    registry = category_registry.load_category_registry()

    assert len(registry.categories) == 6


def test_load_category_registry_handles_shallow_container_source_path(
    monkeypatch,
) -> None:
    """Test Suite ID: TS-IA-COH-ROUTING-001."""
    repo_root = Path(__file__).resolve().parents[4]
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        category_registry,
        "__file__",
        "/app/src/coherence/category_registry.py",
    )

    registry = category_registry.load_category_registry()

    assert len(registry.categories) == 6
