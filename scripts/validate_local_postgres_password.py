#!/usr/bin/env python3
"""Validate the effective local PostgreSQL password contract for Docker Compose."""

from __future__ import annotations

import os
import re
from pathlib import Path

PASSWORD_RE = re.compile(r"[A-Za-z0-9._~-]+")
KEY = "POSTGRES_PASSWORD"


def _last_assignment(path: Path) -> str:
    values: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != KEY:
            continue

        value = value.strip()
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        values.append(value)
    return values[-1] if values else ""


def main() -> int:
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        print("ERROR: .env is required for Docker Compose local targets")
        return 1

    file_value = _last_assignment(env_path)
    value = os.environ.get(KEY, file_value)

    if not value:
        print("ERROR: POSTGRES_PASSWORD must be non-empty")
        return 1
    if PASSWORD_RE.fullmatch(value) is None:
        print(
            "ERROR: local POSTGRES_PASSWORD must use URI-unreserved "
            "characters only (A-Za-z0-9._~-)."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
