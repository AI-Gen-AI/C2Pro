"""ADR-014 locked-invariant gate (TASK-V3-014-02): ProjectState repositories
MUST NOT call ``session.commit()`` — the use case owns the unit of work.

Cwd-independent: the adapters dir is resolved relative to this file. Armed now so
it gates Codex's SQLAlchemy adapters (TASK-V3-014-03) the moment they land.
"""

from __future__ import annotations

import pathlib
import re

_ADAPTERS = pathlib.Path(__file__).resolve().parents[3] / "src" / "project_state" / "adapters"
_COMMIT = re.compile(r"\.commit\s*\(")


def test_project_state_repositories_never_call_commit():
    if not _ADAPTERS.exists():
        return  # adapters not built yet (Codex TASK-V3-014-03) — gate armed for when they are
    offenders = [
        str(path)
        for path in _ADAPTERS.rglob("*.py")
        if _COMMIT.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"ADR-014: repositories must not call commit(): {offenders}"
