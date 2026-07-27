"""TASK-DEV-030: behavioral contracts for the StrEnum migration."""

import ast
from pathlib import Path


def test_source_has_no_legacy_str_enum_classes() -> None:
    """TS-UD-DEV-030-001: source enums use the single StrEnum implementation."""
    legacy_classes: list[str] = []
    for path in (Path(__file__).parents[2] / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {
                base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else ""
                for base in node.bases
            }
            if {"str", "Enum"} <= bases:
                legacy_classes.append(f"{path.relative_to(Path.cwd())}:{node.name}")
    assert not legacy_classes
