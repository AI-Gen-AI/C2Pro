#!/usr/bin/env python3
"""Test Suite ID: TS-DEV-024-OSV-GATE-001. Severity gate for osv-scanner JSON output (TASK-DEV-024).

The retired ``pnpm audit --audit-level critical`` blocked CI only on findings
at or above a severity threshold. osv-scanner's own exit code fails on *any*
advisory regardless of severity, which would spuriously block on pre-existing
Medium/Low advisories in pinned or transitive dependencies.

This gate restores threshold semantics: it fails only when the dependency tree
contains a Critical advisory (CVSS base score >= 9.0). Everything is
still reported (to stdout and the GitHub step summary) for visibility, so
Medium/Low advisories remain tracked without breaking the build.

Usage: ``python osv_gate.py <osv-results.json> [--threshold 9.0]``

Fail-closed: a missing or unparseable results file exits non-zero, so a broken
scan can never be mistaken for a clean tree.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_THRESHOLD = 9.0  # CVSS v3 base score for Critical severity.


def _score(group: dict) -> float | None:
    """Return the group's max CVSS base score, or None when unrated."""
    raw = str(group.get("max_severity", "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", help="Path to osv-scanner --format=json output")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    if not os.path.exists(args.results):
        print(
            f"::error::osv-scanner produced no results file at '{args.results}'; "
            "treating as a scan failure (fail-closed)."
        )
        return 1

    try:
        with open(args.results, encoding="utf-8") as handle:
            data = json.loads(handle.read() or "{}")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error::could not read/parse osv results '{args.results}': {exc}")
        return 1

    reported: list[tuple[str, str, str, float | None]] = []
    blocking: list[tuple[str, str, str, float | None]] = []
    for result in data.get("results", []):
        for pkg in result.get("packages", []):
            meta = pkg.get("package", {})
            name = meta.get("name", "?")
            version = meta.get("version", "?")
            for group in pkg.get("groups", []):
                score = _score(group)
                ids = ",".join(group.get("ids", [])) or "?"
                row = (name, version, ids, score)
                reported.append(row)
                if score is not None and score >= args.threshold:
                    blocking.append(row)

    lines = [
        "## OSV dependency scan",
        "",
        f"Advisories found: {len(reported)} -- "
        f"blocking (CVSS >= {args.threshold:g}): {len(blocking)}",
        "",
    ]
    if reported:
        lines += ["| Package | Version | CVSS | IDs | Blocking |", "|---|---|---|---|---|"]
        for name, version, ids, score in sorted(
            reported, key=lambda row: -(row[3] or 0.0)
        ):
            shown = f"{score:g}" if score is not None else "?"
            flag = "**yes**" if (score is not None and score >= args.threshold) else "no"
            lines.append(f"| {name} | {version} | {shown} | {ids} | {flag} |")
    report = "\n".join(lines) + "\n"
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(report)

    if blocking:
        print(
            f"::error::{len(blocking)} Critical advisory(ies) "
            "(CVSS >= {:g}) in the dependency tree.".format(args.threshold)
        )
        return 1

    print(
        "No Critical advisories. "
        "(High/Medium/Low advisories are reported above but do not block.)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
