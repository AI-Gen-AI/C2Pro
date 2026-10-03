#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
MAX_ARTIFACT_RETENTION_DAYS = 7
STANDARD_PUBLIC_GITHUB_HOSTED_RUNNERS = {
    "ubuntu-slim",
    "ubuntu-latest",
    "ubuntu-24.04",
    "ubuntu-22.04",
    "ubuntu-26.04",
    "ubuntu-24.04-arm",
    "ubuntu-22.04-arm",
    "ubuntu-26.04-arm",
    "windows-latest",
    "windows-2025",
    "windows-2022",
    "windows-11-arm",
    "macos-latest",
    "macos-14",
    "macos-15",
    "macos-15-intel",
    "macos-26",
    "macos-26-intel",
}


def _workflow_paths() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def _runner_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return []


def validate() -> list[str]:
    violations: list[str] = []
    for path in _workflow_paths():
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jobs = payload.get("jobs") or {}
        if not isinstance(jobs, dict):
            violations.append(f"{path.name}: jobs is not an object")
            continue

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                violations.append(f"{path.name}:{job_name}: invalid job")
                continue
            if "uses" in job:
                violations.append(
                    f"{path.name}:{job_name}: reusable workflow requires explicit cost review"
                )
                continue

            runners = _runner_values(job.get("runs-on"))
            if len(runners) != 1 or runners[0] not in STANDARD_PUBLIC_GITHUB_HOSTED_RUNNERS:
                violations.append(
                    f"{path.name}:{job_name}: non-standard/paid/self-hosted runner {job.get('runs-on')!r}"
                )

            steps = job.get("steps") or []
            if not isinstance(steps, list):
                continue
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                action = step.get("uses")
                if not isinstance(action, str) or "actions/upload-artifact@" not in action:
                    continue
                settings = step.get("with") or {}
                if not isinstance(settings, dict):
                    violations.append(
                        f"{path.name}:{job_name}:step{index}: upload-artifact has invalid with block"
                    )
                    continue
                retention = settings.get("retention-days")
                if retention is None:
                    violations.append(
                        f"{path.name}:{job_name}:step{index}: upload-artifact missing retention-days"
                    )
                    continue
                try:
                    days = int(retention)
                except (TypeError, ValueError):
                    violations.append(
                        f"{path.name}:{job_name}:step{index}: invalid retention-days={retention!r}"
                    )
                    continue
                if not 1 <= days <= MAX_ARTIFACT_RETENTION_DAYS:
                    violations.append(
                        f"{path.name}:{job_name}:step{index}: retention-days={days} exceeds policy"
                    )
    return violations


def main() -> int:
    violations = validate()
    if violations:
        print("GITHUB_ACTIONS_STORAGE_POLICY=FAIL")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("GITHUB_ACTIONS_STORAGE_POLICY=PASS")
    print(f"MAX_ARTIFACT_RETENTION_DAYS={MAX_ARTIFACT_RETENTION_DAYS}")
    print("RUNNER_POLICY=STANDARD_PUBLIC_GITHUB_HOSTED_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
