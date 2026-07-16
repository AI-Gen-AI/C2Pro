#!/usr/bin/env python3
"""mypy baseline ratchet (EPIC-MYPY-STRICT / TASK-DEV-031).

mypy 1.8 has no native baseline. This gate lets the ~1,357 existing strict-mode
errors burn down incrementally while **blocking any new one** — with no extra
dependency.

Mechanism: normalize each mypy error line by stripping the `:line:col:` position
(so refactors that shift lines don't churn the baseline), then compare the
*multiset* of normalized errors against a committed baseline. Any error present
in the current run beyond its baseline multiplicity is a regression and fails.
Errors fixed since the baseline are reported (ratchet down) and never fail.

Usage:
  # write/refresh the baseline (run after a wave reduces errors):
  mypy src --no-error-summary --no-color-output | python scripts/mypy_ratchet.py --update mypy-baseline.txt
  # gate (CI):
  mypy src --no-error-summary --no-color-output | python scripts/mypy_ratchet.py --check mypy-baseline.txt

Reads the mypy run from stdin. Exit 1 on new errors (check mode) or on a missing
baseline; exit 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

# Matches "path:line:col: error: message  [code]" and "... : note: ...".
_POS = re.compile(r"^(?P<path>[^:]+):\d+:(?:\d+:)?\s*(?P<rest>(?:error|note):\s.*)$")


def _normalize(stream: object) -> Counter[str]:
    """Return a multiset of position-stripped mypy *error* lines."""
    counter: Counter[str] = Counter()
    for raw in stream:  # type: ignore[attr-defined]
        line = raw.rstrip("\r\n")  # tolerate CRLF (Windows working copies)
        m = _POS.match(line)
        if not m:
            continue
        rest = m.group("rest")
        if not rest.startswith("error:"):
            continue  # notes are context, not gated
        # Normalize path separators so a baseline written on Windows (backslash)
        # matches mypy output on Linux CI (forward slash) — the paths are the same.
        path = m.group("path").replace("\\", "/")
        counter[f"{path}: {rest}"] += 1
    return counter


def _read_baseline(path: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")  # tolerate CRLF (Windows working copies)
            if line:
                counter[line] += 1
    return counter


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", metavar="BASELINE")
    group.add_argument("--update", metavar="BASELINE")
    args = parser.parse_args(argv)

    current = _normalize(sys.stdin)

    if args.update:
        with open(args.update, "w", encoding="utf-8", newline="\n") as fh:
            for sig in sorted(current.elements()):
                fh.write(sig + "\n")
        print(f"Wrote {sum(current.values())} baseline errors to {args.update}")
        return 0

    import os

    if not os.path.exists(args.check):
        print(f"::error::mypy baseline '{args.check}' not found (fail-closed).")
        return 1
    baseline = _read_baseline(args.check)

    new = current - baseline  # multiset difference: current beyond baseline
    fixed = baseline - current
    print(
        f"mypy ratchet: baseline={sum(baseline.values())} current={sum(current.values())} "
        f"new={sum(new.values())} fixed={sum(fixed.values())}"
    )
    if new:
        print("::error::mypy introduced new type errors (not in the baseline):")
        for sig in sorted(new.elements()):
            print(f"  + {sig}")
        print(
            "Fix them, or if intended, refresh the baseline with "
            "`make mypy-baseline` after reducing errors (never to hide a regression)."
        )
        return 1
    if fixed:
        print(
            f"{sum(fixed.values())} baseline error(s) fixed — refresh mypy-baseline.txt "
            "to ratchet the gate down."
        )
    print("No new mypy errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
