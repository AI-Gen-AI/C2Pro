#!/usr/bin/env python
"""Assert the P0b journey actually persisted, not just that the UI looked right.

TS-E2E-P0B-HEALTH-001 (database half).

The production failure this guards against was invisible from the browser: the
Analysis page rendered, the API answered 200, and the document said
``analyzed`` -- while ``analyses``, ``project_events`` and ``project_snapshots``
were all empty and zero RAG chunks had ever been written. A UI-only assertion
would have passed.

So the Playwright spec proves what the user sees, and this proves the chain
underneath it really ran. Run it immediately after the spec, against the project
id the spec recorded.

Exits non-zero with a per-check report on any failure. Never mutates.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_PROJECT_ID_FILE = "apps/web/playwright/.p0b/project-id.txt"

# apps/api/scripts/verify_p0b_journey.py -> the repository checkout.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The single file the Playwright journey records its project id into, and the
# only file --project-id-file may name. DEFAULT_PROJECT_ID_FILE is the same
# file spelled relative to the repository root.
EXPECTED_PROJECT_ID_FILE = _REPO_ROOT / DEFAULT_PROJECT_ID_FILE


class CheckFailure(Exception):
    """A required P0b persistence guarantee did not hold."""


def _literal_target(path: Path) -> Path:
    """Absolute path with the final component kept literal.

    The parent is resolved (so ``..`` and symlinked directories collapse) but
    the last component is not, because resolving it would follow a symlink
    planted AT the destination and make the escape compare equal to the very
    contract it escapes.
    """
    return path.parent.resolve() / path.name


def resolve_project_id_file(raw: str) -> Path:
    """Require ``--project-id-file`` to be exactly the canonical P0b id file.

    The option names a file this script READS and then parses as a UUID, so an
    unconstrained value is a path-injection sink: it lets whoever controls the
    argument point the verifier at any readable file and have a fragment of it
    echoed back through the resulting ``ValueError``.

    Only one file is ever legitimate. ``ci.yml`` spells it
    ``../web/playwright/.p0b/project-id.txt`` from ``apps/api`` and the default
    spells it from the repository root; the two differ textually and resolve to
    the same file. Nothing else in the checkout is authorised, so the check is
    equality against that one path rather than containment in a directory.
    """
    expected = _literal_target(EXPECTED_PROJECT_ID_FILE)
    candidate = Path(raw).expanduser()
    resolved = _literal_target(candidate)
    if resolved != expected:
        raise CheckFailure(
            f"--project-id-file resolves to {resolved}, which is not the canonical P0b "
            f"project id file ({expected}). Refusing to read it."
        )
    if candidate.is_symlink():
        raise CheckFailure(
            f"--project-id-file is a symlink at {resolved}. Refusing to read through it."
        )
    return resolved


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


async def _scalar(conn: object, sql: str, project_id: UUID) -> int:
    result = await conn.execute(text(sql), {"pid": str(project_id)})  # type: ignore[attr-defined]
    return int(result.scalar_one())


async def verify(project_id: UUID, database_url: str) -> list[tuple[str, bool, str]]:
    """Return (check_name, passed, detail) for every required guarantee."""
    engine = create_async_engine(_normalize_database_url(database_url))
    checks: list[tuple[str, bool, str]] = []
    try:
        async with engine.connect() as conn:
            documents = await _scalar(
                conn,
                "SELECT count(*) FROM documents WHERE project_id = CAST(:pid AS uuid)",
                project_id,
            )
            checks.append(("document persisted", documents >= 1, f"documents={documents}"))

            analyzed = await _scalar(
                conn,
                """
                SELECT count(*) FROM documents
                WHERE project_id = CAST(:pid AS uuid)
                  AND upload_status IN ('parsed', 'analyzed')
                """,
                project_id,
            )
            checks.append(
                ("document reached parsed/analyzed", analyzed >= 1, f"terminal_docs={analyzed}")
            )

            clauses = await _scalar(
                conn,
                "SELECT count(*) FROM clauses WHERE project_id = CAST(:pid AS uuid)",
                project_id,
            )
            checks.append(("clauses > 1", clauses > 1, f"clauses={clauses}"))

            chunks = await _scalar(
                conn,
                """
                SELECT count(*) FROM document_chunks
                WHERE project_id = CAST(:pid AS uuid)
                """,
                project_id,
            )
            # The exact production breakpoint: zero chunks silently skipped the
            # graph. This check is the reason this script exists.
            checks.append(("RAG chunks > 0", chunks > 0, f"document_chunks={chunks}"))

            analyses = await _scalar(
                conn,
                "SELECT count(*) FROM analyses WHERE project_id = CAST(:pid AS uuid)",
                project_id,
            )
            checks.append(("analysis artifact exists", analyses >= 1, f"analyses={analyses}"))

            events = await _scalar(
                conn,
                """
                SELECT count(*) FROM project_events
                WHERE project_id = CAST(:pid AS uuid)
                  AND event_type = 'graph.completed'
                """,
                project_id,
            )
            checks.append(("graph.completed event exists", events >= 1, f"events={events}"))

            snapshots = await _scalar(
                conn,
                """
                SELECT count(*) FROM project_snapshots
                WHERE project_id = CAST(:pid AS uuid)
                  AND health_vector IS NOT NULL
                """,
                project_id,
            )
            checks.append(
                ("snapshot with health_vector exists", snapshots >= 1, f"snapshots={snapshots}")
            )

            covered = await _scalar(
                conn,
                """
                SELECT count(*) FROM project_snapshots
                WHERE project_id = CAST(:pid AS uuid)
                  AND jsonb_array_length(
                        health_vector -> 'single_document_coverage' -> 'assessments'
                      ) = 6
                """,
                project_id,
            )
            checks.append(
                ("snapshot carries six category assessments", covered >= 1, f"six_category={covered}")
            )
    finally:
        await engine.dispose()
    return checks


def _resolve_project_id(args: argparse.Namespace) -> UUID:
    if args.project_id:
        return UUID(args.project_id)
    path = resolve_project_id_file(args.project_id_file)
    if not path.is_file():
        raise CheckFailure(
            f"No project id at {path}. The Playwright journey must run first and record one; "
            "an absent id means the journey did not complete, which is a failure, not a skip."
        )
    return UUID(path.read_text(encoding="utf8").strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", help="Project UUID to verify.")
    parser.add_argument("--project-id-file", default=DEFAULT_PROJECT_ID_FILE)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        print("FAIL: DATABASE_URL is required to verify the P0b journey.", file=sys.stderr)
        return 2

    try:
        project_id = _resolve_project_id(args)
    except (CheckFailure, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    checks = asyncio.run(verify(project_id, args.database_url))

    print(f"P0b journey verification for project {project_id}")
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} ({detail})")

    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        print(f"\nFAIL: {len(failed)} required P0b guarantee(s) not met: {', '.join(failed)}")
        return 1
    print("\nPASS: the P0b persistence chain completed end to end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
