#!/usr/bin/env python
"""Independently read PostgreSQL and prove the PJ-01 revision trace (ACC-01 S6).

The PJ-01 browser journey judges what the application SAYS (Current State, Health, What Changed).
This script judges what the database HOLDS, without going through the application: it re-reads the
journey's project and proves that

* the project has exactly one logical document with two revisions, whose stored content hashes are
  the SHA-256 of the committed fixture files for contract A (revision 1) and contract B (revision 2);
* revision A was a trusted source before B: its artifact was trusted and has since been superseded (trusted + lifecycle superseded);
* revision B's artifact is the single active trusted one, and nothing is left proposed;
* the review of revision B was decided by a human (approved), not auto-trusted.

With ``--kind reject`` it proves the S5 rejection instead: the review the browser rejected is REJECTED
with the typed reason stored (compared by SHA-256), nothing of the project is approved or still
pending, no artifact is trusted and the document did not become analysed.

It never mutates. It prints booleans and counts only (no tenant, user or Clerk identifiers), and
exits non-zero on the first failed claim so the CI step is red when the database disagrees.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _normalize_database_url(raw: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if raw.startswith(prefix):
            return raw.replace(prefix, "postgresql+asyncpg://", 1)
    return raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


MARKER = {"journey": "revisionFixture", "reject": "s5Reject"}


def _facts_of(kind: str, run_dir: Path) -> dict[str, Any]:
    """Facts of the newest run in ``run_dir`` that is of ``kind`` (never another spec's run)."""
    candidates = sorted(
        run_dir.glob("*/run.json"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for run_json in candidates:
        facts = json.loads(run_json.read_text(encoding="utf-8")).get("facts", {})
        if MARKER[kind] in facts:
            return facts
    raise SystemExit(f"FAIL: no {kind} run.json under {run_dir} ({len(candidates)} run(s) found)")


def _project_id_from_facts(facts: dict[str, Any]) -> UUID:
    raw = facts.get("projectId") or (facts.get("s5Reject") or {}).get("projectId")
    if not raw:
        raise SystemExit("FAIL: the run records no projectId")
    return UUID(str(raw))


async def verify_reject(
    database_url: str,
    project_id: UUID,
    document_id: UUID,
    item_id: UUID,
    row_id: UUID,
    reason_sha256: str,
) -> list[str]:
    failures: list[str] = []
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            reviews = (
                await conn.execute(
                    text(
                        "SELECT id, item_id, upper(current_status::text) AS status, approved_by, review_metadata "
                        "FROM review_items WHERE project_id = :p AND document_id = :d"
                    ),
                    {"p": project_id, "d": document_id},
                )
            ).all()
            statuses = sorted(r.status for r in reviews)
            if statuses != ["REJECTED"]:
                failures.append(
                    f"review statuses of the document are {statuses}, expected exactly ['REJECTED']"
                )
            for review in reviews:
                # The browser reports both identities of the review it rejected: the business key (item_id)
                # and the row (primary key). They are different ids; binding to both proves THIS decision,
                # not merely "some rejection".
                if review.item_id != item_id:
                    failures.append("the rejected review is not the item the browser rejected")
                if review.id != row_id:
                    failures.append("the rejected review is not the row the browser rejected")
                if not review.approved_by:
                    failures.append("the rejection does not name who took the decision")
                reason = (review.review_metadata or {}).get("rejection_reason")
                if (
                    not isinstance(reason, str)
                    or hashlib.sha256(reason.encode()).hexdigest() != reason_sha256
                ):
                    failures.append("the stored rejection reason is not the one the browser typed")
            other = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM review_items WHERE project_id = :p AND document_id <> :d "
                        "AND upper(current_status::text) = 'APPROVED'"
                    ),
                    {"p": project_id, "d": document_id},
                )
            ).scalar_one()
            if other:
                failures.append(
                    f"{other} review item(s) of the project are approved without a rejection"
                )
            trusted = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM document_artifacts WHERE project_id = :p AND trust_state = 'trusted'"
                    ),
                    {"p": project_id},
                )
            ).scalar_one()
            if trusted:
                failures.append(
                    f"{trusted} artifact(s) became trusted although the review was rejected"
                )
            status = (
                await conn.execute(
                    text("SELECT upload_status::text FROM documents WHERE id = :d"),
                    {"d": document_id},
                )
            ).scalar_one_or_none()
            if status is None or status.lower() == "analyzed":
                failures.append(f"document status is {status!r} after the rejection")
    finally:
        await engine.dispose()
    return failures


async def verify(database_url: str, project_id: UUID, hash_a: str, hash_b: str) -> list[str]:
    failures: list[str] = []
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            revisions = (
                await conn.execute(
                    text(
                        "SELECT document_id, revision_id, rev_no, blob_hash FROM document_revisions "
                        "WHERE project_id = :p ORDER BY document_id, rev_no"
                    ),
                    {"p": project_id},
                )
            ).all()
            documents = {row.document_id for row in revisions}
            if len(documents) != 1:
                failures.append(f"expected one logical document, found {len(documents)}")
                return failures
            if [(r.rev_no, r.blob_hash) for r in revisions] != [(1, hash_a), (2, hash_b)]:
                failures.append(
                    f"stored revisions {[(r.rev_no, r.blob_hash[:12]) for r in revisions]} "
                    f"are not [(1, A:{hash_a[:12]}), (2, B:{hash_b[:12]})]"
                )
                return failures
            rev_a, rev_b = revisions
            artifacts = (
                await conn.execute(
                    text(
                        "SELECT document_revision_id, trust_state, lifecycle_status FROM document_artifacts "
                        "WHERE project_id = :p ORDER BY artifact_version"
                    ),
                    {"p": project_id},
                )
            ).all()
            by_revision = {a.document_revision_id: a for a in artifacts}
            a_artifact = by_revision.get(rev_a.revision_id)
            b_artifact = by_revision.get(rev_b.revision_id)
            if a_artifact is None or (a_artifact.trust_state, a_artifact.lifecycle_status) != (
                "trusted",
                "superseded",
            ):
                failures.append(
                    "revision A is not a previously trusted, now superseded source "
                    f"(artifact: {None if a_artifact is None else (a_artifact.trust_state, a_artifact.lifecycle_status)})"
                )
            if b_artifact is None or (b_artifact.trust_state, b_artifact.lifecycle_status) != (
                "trusted",
                "active",
            ):
                failures.append(
                    "revision B is not the active trusted artifact "
                    f"(artifact: {None if b_artifact is None else (b_artifact.trust_state, b_artifact.lifecycle_status)})"
                )
            leftovers = [a for a in artifacts if a.trust_state == "proposed"]
            if leftovers:
                failures.append(
                    f"{len(leftovers)} proposed artifact(s) are still waiting for a decision"
                )
            approved = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM review_items WHERE project_id = :p "
                        "AND upper(current_status::text) = 'APPROVED'"
                    ),
                    {"p": project_id},
                )
            ).scalar_one()
            if approved < 1:
                failures.append("no review item of the project was approved by a human")
    finally:
        await engine.dispose()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=sorted(MARKER), default="journey")
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="directory holding the recorder's <run>/run.json files",
    )
    parser.add_argument(
        "--contract-a", type=Path, help="committed fixture PDF of contract A (journey)"
    )
    parser.add_argument(
        "--contract-b", type=Path, help="committed fixture PDF of contract B (journey)"
    )
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        print("FAIL: no database url (set DATABASE_URL or pass --database-url)")
        return 2

    facts = _facts_of(args.kind, args.run_dir)
    project_id = _project_id_from_facts(facts)
    if args.kind == "reject":
        recorded = facts["s5Reject"]
        failures = asyncio.run(
            verify_reject(
                args.database_url,
                project_id,
                UUID(str(recorded["documentId"])),
                UUID(str(recorded["reviewItemId"])),
                UUID(str(recorded["reviewRowId"])),
                str(recorded["reasonSha256"]),
            )
        )
        ok = "OK: PostgreSQL holds the rejected review with the typed reason, no approval and no trusted artifact"
    else:
        if not (args.contract_a and args.contract_b):
            print("FAIL: --contract-a and --contract-b are required for --kind journey")
            return 2
        failures = asyncio.run(
            verify(
                args.database_url, project_id, _sha256(args.contract_a), _sha256(args.contract_b)
            )
        )
        ok = "OK: PostgreSQL holds revision A (trusted, now superseded) and revision B (active trusted) for the journey"
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
