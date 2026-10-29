"""Fail closed when the Ops harness is pointed outside its job-owned cluster."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def assert_ops_database_binding(
    database_url: str, job_id: str | None, evidence_dir: str | None = None
) -> None:
    if job_id is None:
        return  # Preserve the existing local/CI harness contract.
    if re.fullmatch(r"[0-9a-f]{24}", job_id) is None:
        raise RuntimeError("invalid_ops_job_id")
    url = urlsplit(database_url)
    query = parse_qs(url.query, keep_blank_values=True)
    directory = Path(evidence_dir or f"/srv/c2pro/ops-c2pro-runner/jobs/{job_id}")
    if (not directory.is_absolute() or ".." in directory.parts
            or directory.name != job_id or directory.parent.name != "jobs"):
        raise RuntimeError("invalid_ops_evidence_directory")
    socket = str(directory / "pg-socket")
    if (
        url.scheme not in ("postgresql", "postgresql+asyncpg")
        or url.hostname is not None
        or url.username != "aigenadmin"
        or url.password is not None
        or url.path != "/c2pro_ops_" + job_id[:16]
        or query != {"host": [socket], "port": ["55432"]}
    ):
        raise RuntimeError("ops_database_target_not_job_private")
