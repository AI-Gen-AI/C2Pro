"""TS-QA-SWAGGER-MIGRATION-001: Alembic migration graph integrity tests."""

from __future__ import annotations

import ast
import re
from pathlib import Path


def test_alembic_version_graph_has_single_head() -> None:
    """TS-QA-SWAGGER-MIGRATION-001: prevent API startup failure from split heads."""
    versions_dir = Path(__file__).parents[2] / "alembic" / "versions"
    revisions: dict[str, str] = {}
    parents_by_revision: dict[str, list[str]] = {}

    for path in versions_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision_match = re.search(
            r"^revision\s*(?::[^=]+)?=\s*(['\"])(.+?)\1", text, re.MULTILINE
        )
        if revision_match is None:
            continue

        revision = revision_match.group(2)
        revisions[revision] = path.name

        down_match = re.search(
            r"^down_revision\s*(?::[^=]+)?=\s*(.+)$", text, re.MULTILINE
        )
        if down_match is None:
            parents_by_revision[revision] = []
            continue

        parsed = ast.literal_eval(down_match.group(1).strip())
        if parsed is None:
            parents: list[str] = []
        elif isinstance(parsed, str):
            parents = [parsed]
        else:
            parents = list(parsed)
        parents_by_revision[revision] = parents

    referenced_parents = {
        parent
        for parents in parents_by_revision.values()
        for parent in parents
        if parent
    }
    heads = sorted(set(revisions) - referenced_parents)

    assert heads == ["20260524_0001"], {
        "heads": [(head, revisions[head]) for head in heads],
    }
