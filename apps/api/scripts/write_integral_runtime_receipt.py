#!/usr/bin/env python
"""Redacted RUNTIME SHA receipt for one process of the integral UAT, verified against the process itself.

"The frontend and the backend boot from this exact checkout" is a claim about running processes, not about a URL.
This finds the process by its command line, reads ITS working directory from ``/proc`` (not the caller's), proves
that directory is inside the job's workspace, asks git for the HEAD of THAT directory and compares it with the SHA
the run is judged on. It records only the role, the SHAs, the pid and booleans -- never the environment of the
process (which holds secrets) and never its full command line.

Exit codes: 0 receipt written and the SHA matches; 1 the process was not found, runs outside the workspace, or runs
another SHA (a receipt with ``matches = false`` is still written so the failure is evidenced).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def find_pids(pattern: str, proc_root: Path = Path("/proc")) -> list[int]:
    """Pids whose command line contains ``pattern`` (this script's own process excluded)."""
    found: list[int] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if pattern in command:
            found.append(int(entry.name))
    return sorted(found)


def head_of(directory: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def build_receipt(
    *, role: str, pattern: str, expected_sha: str, workspace: Path, proc_root: Path = Path("/proc")
) -> dict[str, Any]:
    pids = find_pids(pattern, proc_root)
    receipt: dict[str, Any] = {
        "role": role,
        "expected_sha": expected_sha,
        "process_found": bool(pids),
        "processes": len(pids),
        "runtime_sha": "",
        "cwd_inside_workspace": False,
        "matches": False,
    }
    if not pids:
        return receipt
    try:
        cwd = Path(os.readlink(proc_root / str(pids[0]) / "cwd")).resolve()
    except OSError:
        return receipt
    receipt["cwd_inside_workspace"] = cwd.is_relative_to(workspace.resolve())
    if receipt["cwd_inside_workspace"]:
        receipt["runtime_sha"] = head_of(cwd)
    receipt["matches"] = bool(receipt["runtime_sha"]) and receipt["runtime_sha"] == expected_sha
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--role", required=True, choices=["backend", "worker", "frontend"])
    parser.add_argument(
        "--process-pattern", required=True, help="substring of the process command line"
    )
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--workspace", type=Path, default=Path(os.environ.get("GITHUB_WORKSPACE", "."))
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--wait-seconds", type=int, default=0, help="keep looking for the process this long"
    )
    args = parser.parse_args()

    deadline = time.monotonic() + max(args.wait_seconds, 0)
    while True:
        receipt = build_receipt(
            role=args.role,
            pattern=args.process_pattern,
            expected_sha=args.expected_sha,
            workspace=args.workspace,
        )
        if receipt["process_found"] or time.monotonic() >= deadline:
            break
        time.sleep(2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{args.role}: found={receipt['process_found']} inside_workspace={receipt['cwd_inside_workspace']} "
        f"matches={receipt['matches']}"
    )
    return 0 if receipt["matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
