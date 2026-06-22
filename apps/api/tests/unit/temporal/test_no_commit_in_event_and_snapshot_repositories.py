"""No-commit static gate for ProjectEvent and ProjectSnapshot repos (ADR-015)."""

from __future__ import annotations

import pathlib
import re

_ADAPTERS = pathlib.Path(__file__).resolve().parents[3] / "src" / "temporal" / "adapters"
_COMMIT = re.compile(r"\.commit\s*\(")


def test_event_and_snapshot_repositories_never_call_commit() -> None:
    offenders = [
        str(path)
        for path in _ADAPTERS.rglob("*.py")
        if _COMMIT.search(path.read_text(encoding="utf-8"))
    ]

    assert not offenders, f"ADR-015 temporal repos must not call commit(): {offenders}"
