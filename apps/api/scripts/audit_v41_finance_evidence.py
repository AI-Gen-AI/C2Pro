#!/usr/bin/env python3
"""Read-only, credential-free audit of a C2Pro V4.1 pilot JSON artifact.

Usage:
  PYTHONPATH=apps/api python apps/api/scripts/audit_v41_finance_evidence.py     path/to/real_analysis_evidence.json

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
        print("usage: audit_v41_finance_evidence.py <real_analysis_evidence.json>",
              file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        if path.stat().st_size > 25_000_000:
            raise ValueError("pilot summary too large")
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
