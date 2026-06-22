"""No-commit static gate for temporal repositories (ADR-015 / TASK-V3-015-01).

DocumentRevision repositories MUST NOT call session.commit().
"""

from __future__ import annotations

import pathlib
import re

_ADAPTERS = pathlib.Path(__file__).resolve().parents[3] / "src" / "temporal" / "adapters"
_COMMIT = re.compile(r"\.commit\s*\(")


def test_revision_repositories_never_call_commit():
    if not _ADAPTERS.exists():
        return
    offenders = [
        str(path)
        for path in _ADAPTERS.rglob("*.py")
        if _COMMIT.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"ADR-015: revision repos must not call commit(): {offenders}"
