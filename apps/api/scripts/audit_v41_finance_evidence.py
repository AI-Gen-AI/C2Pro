#!/usr/bin/env python3
"""Read-only, credential-free audit of a C2Pro V4.1 pilot JSON artifact.

Usage:
  # Run from the trusted artifact extraction directory:
  PYTHONPATH=/repo/apps/api python /repo/apps/api/scripts/audit_v41_finance_evidence.py _temp/c2pro-v41-real/real_analysis_evidence.json

Outputs only sanitized financial totals and flags. Never prints clauses,
source text, IDs or environment secrets. Exit 0 only on internally balanced
ledger without unverified consumption/overages; invoice remains unverified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.core.ai.v41_financial_evidence_check import audit_v41_financial_evidence


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: audit_v41_finance_evidence.py <relative-path/real_analysis_evidence.json>",
              file=sys.stderr)
        return 2
    try:
        # Trust the operator's working directory, not an arbitrary user-supplied
        # absolute path. Resolve links and enforce the extraction-root boundary
        # before reading any bytes (SonarCloud pythonsecurity:S8707).
        root = Path.cwd().resolve()
        relative = Path(args[0])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("file path must stay under the evidence root")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or path.name != "real_analysis_evidence.json":
            raise ValueError("invalid evidence path")
        if not path.is_file() or path.stat().st_size > 25_000_000:
            raise ValueError("pilot summary missing or too large")
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"status": "NOT_AUDITABLE", "findings": [
            "INPUT_NOT_READABLE_AS_JSON",
        ]}))
        return 2
    result = audit_v41_financial_evidence(document)
    print(json.dumps(result.sanitized_summary(), sort_keys=True))
    return 0 if result.status == "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
