#!/usr/bin/env python3
"""Offline two-artifact QA: C2Pro ledger + governor, no model or DB access.

Run from the trusted GitHub artifact extraction root:
  PYTHONPATH=/repo/apps/api python /repo/apps/api/scripts/audit_v41_governor_evidence.py \
      _temp/c2pro-v41-real/real_analysis_evidence.json \
      C2Pro/C2Pro/apps/api/c2pro-v41-openai-governor.jsonl
Only relative paths under the current directory are accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.core.ai.v41_governor_evidence_check import audit_v41_governor_evidence


def _read_scoped(root: Path, path_arg: str, basename: str, limit: int) -> str:
    relative = Path(path_arg)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("absolute/parent path not allowed")
    candidate = (root / relative).resolve(strict=True)
    if not candidate.is_relative_to(root) or candidate.name != basename:
        raise ValueError("artifact path not trusted")
    if not candidate.is_file() or candidate.stat().st_size > limit:
        raise ValueError("artifact missing/oversized")
    return candidate.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: audit_v41_governor_evidence.py "
              "<relative-real_analysis_evidence.json> "
              "<relative-c2pro-v41-openai-governor.jsonl>", file=sys.stderr)
        return 2
    try:
        root = Path.cwd().resolve()
        report = json.loads(_read_scoped(
            root, args[0], "real_analysis_evidence.json", 25_000_000,
        ))
        contents = _read_scoped(
            root, args[1], "c2pro-v41-openai-governor.jsonl", 10_000_000,
        )
        lines = contents.splitlines()
        if not 0 < len(lines) <= 1000:
            raise ValueError("unbounded governor events")
        events = [json.loads(x) for x in lines]
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({
            "status": "NOT_AUDITABLE", "findings": ["ARTIFACT_UNREADABLE_OR_UNTRUSTED"],
            "invoice_verified": False,
        }, sort_keys=True))
        return 2
    result = audit_v41_governor_evidence(report, events)
    print(json.dumps(result.sanitized_summary(), sort_keys=True))
    return 0 if result.status == "MATCHED_WITH_LIMITATIONS_NOT_INVOICE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
