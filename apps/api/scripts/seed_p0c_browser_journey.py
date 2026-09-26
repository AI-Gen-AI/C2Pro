#!/usr/bin/env python
"""Provision the deterministic PJ-01 P0c temporal fixture for browser E2E.

This is test infrastructure, not a product endpoint.  It writes only the
non-secret browser manifest requested by ``--output`` after persisting the
canonical P0c revision/event projections through their repositories.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.core.database import close_db, get_raw_session, init_db
from tests.e2e_seed.p0c_temporal import seed_p0c_browser_fixture


def _resolve_output_path(path: Path) -> Path:
    """Resolve ``--output`` against the invocation directory and refuse one that
    would write outside it (CWE-22). This is a local CI/dev seed script, never a
    network-facing endpoint, but the destination still comes from argv, so it is
    validated -- resolved to an absolute path and checked against the base it must
    stay under -- before the write sink, rather than trusted implicitly. Run it from
    wherever the manifest should land (a Playwright artifact directory, pytest's
    ``tmp_path``, ...); ``--output`` is always relative to that.
    """
    root = Path.cwd().resolve()
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"--output must resolve inside {root}, got {resolved}")
    return resolved


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write a stable, non-secret fixture manifest for the Playwright process."""
    resolved = _resolve_output_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def provision(output: Path) -> dict[str, Any]:
    """Initialize application DB access, seed PJ-01, and emit its browser IDs."""
    await init_db()
    try:
        async with get_raw_session() as db:
            manifest = await seed_p0c_browser_fixture(db)
        write_manifest(output, manifest)
        return manifest
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="JSON manifest path")
    args = parser.parse_args()
    manifest = asyncio.run(provision(args.output))
    print(
        "P0C_BROWSER_FIXTURE_READY "
        f"project={manifest['project_id']} document={manifest['document_id']} output={args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - command entry point
    raise SystemExit(main())
