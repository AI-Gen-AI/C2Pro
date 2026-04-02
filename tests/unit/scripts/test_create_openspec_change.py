"""TS-OPS-OPENSPEC-CREATE-001

Unit tests for OpenSpec change scaffold creation helpers.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.create_openspec_change import (  # noqa: E402
    ChangeScaffoldInput,
    build_paths,
    normalize_change_name,
    normalize_domain_name,
)


def test_normalize_change_name_slugifies_human_title() -> None:
    assert normalize_change_name("Follow Up Change 01") == "follow-up-change-01"


def test_normalize_change_name_rejects_path_like_input() -> None:
    with pytest.raises(ValueError, match="must not include path separators"):
        normalize_change_name("foo/bar")


def test_normalize_change_name_rejects_parent_traversal() -> None:
    with pytest.raises(ValueError, match="must not include traversal"):
        normalize_change_name("..")


def test_normalize_domain_name_rejects_nested_path() -> None:
    with pytest.raises(ValueError, match="must not include path separators"):
        normalize_domain_name("contracts/legal")


def test_build_paths_uses_canonical_change_layout(tmp_path: Path) -> None:
    scaffold_input = ChangeScaffoldInput(
        repo_root=tmp_path,
        change_name="follow-up-auth",
        domain_name="security",
    )

    paths = build_paths(scaffold_input)

    assert paths.change_root == tmp_path / "openspec" / "changes" / "follow-up-auth"
    assert paths.proposal == paths.change_root / "proposal.md"
    assert paths.design == paths.change_root / "design.md"
    assert paths.tasks == paths.change_root / "tasks.md"
    assert paths.spec == paths.change_root / "specs" / "security" / "spec.md"
