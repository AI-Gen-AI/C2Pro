"""
CI guard: no ad-hoc coherence cache key literals in apps/api/src/**

Self-test for the GitHub Actions step added by Phase G (ADR-009 §G).

Suite ID: TS-UD-COH-CI-GUARD-001

If this test fails, it means a `f"coherence:` string literal was added outside the
designated SoT modules. Fix: use `src.coherence.cache_keys.key()` instead.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_no_adhoc_coherence_cache_key_literals() -> None:
    """Assert zero ad-hoc coherence cache key literals exist outside the SoT modules."""
    src_root = Path(__file__).resolve().parents[2] / "src"

    # Modules that are ALLOWED to contain coherence: literals
    excluded: set[Path] = {
        src_root / "coherence" / "cache_keys.py",
        src_root / "coherence" / "cache_invalidation.py",
    }

    # Match f-string literals that start a coherence cache key
    pattern = re.compile(r'f["\']coherence:')

    offenders: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        if py_file in excluded:
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                offenders.append(
                    f"{py_file.relative_to(src_root)}:{lineno}: {line.strip()}"
                )

    assert not offenders, (
        "ADR-009 §G violation — ad-hoc coherence cache key literal(s) detected. "
        "Use src.coherence.cache_keys.key() instead:\n" + "\n".join(offenders)
    )
