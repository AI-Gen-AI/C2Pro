#!/usr/bin/env python3
"""ACC-01 S2: independent, read-only PostgreSQL check of the browser's exact project.

Consumes the Playwright JSON report ONLY for IDs and fixture hashes. Every
persistent fact is re-read from PostgreSQL before the Nightly deletes its DB.
This checks source lineage and processing, NOT real AI/LLM acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

FAMILIES = {
    "triplet-contract.docx": "contract",
    "triplet-budget.xlsx": "budget",
    "triplet-schedule.xlsx": "schedule",
    "triplet-specification.docx": "technical_spec",
}
NEGATIVES = {
    "invalid-budget.docx": 400,
    "invalid-schedule.docx": 400,
    "unsupported-technical.bin": 415,
}


def invalid(reason: str):
    raise ValueError(f"S2_INDEPENDENT_PG_FAIL: {reason}")


def specs(suites: list[dict[str, Any]]):
    for suite in suites:
        yield from suite.get("specs", [])
        yield from specs(suite.get("suites", []))


def annotation(test: dict[str, Any], kind: str) -> dict[str, Any]:
    entries = {
        item.get("description")
        for ctx in [test, *(test.get("results") or [])]
        for item in ctx.get("annotations", [])
        if item.get("type") == kind
    }
    if len(entries) != 1:
        invalid(f"expected unique {kind}, found {len(entries)}")
    try:
        result = json.loads(entries.pop())
    except (TypeError, ValueError):
        invalid(f"malformed {kind}")
    if not isinstance(result, dict):
        invalid(f"{kind} must be an object")
    return result


def source_trace(report: dict[str, Any], manifest: dict[str, Any], fixtures: Path):
    entries = [
        s for s in specs(report.get("suites", []))
        if str(s.get("file", "")).endswith("triplet-user-journey.spec.ts")
    ]
    if len(entries) != 1:
        invalid("triplet browser spec missing or ambiguous")
    matching = [
        t for t in entries[0].get("tests", [])
        if t.get("projectName") == "triplet-journey"
    ]
    if len(matching) != 1 or matching[0].get("status") != "expected":
        invalid("triplet browser test not uniquely passed")
    results = matching[0].get("results") or []
    if len(results) != 1 or results[0].get("status") != "passed":
        invalid("triplet browser test failed, retried or did not run")
    ledger = annotation(matching[0], "s2-source-ledger")
    negative = annotation(matching[0], "s2-negative-uploads")
    try:
        project_id = UUID(str(ledger["projectId"]))
    except (ValueError, KeyError, TypeError):
        invalid("invalid project identifier")
    if str(negative.get("projectId")) != str(project_id):
        invalid("negative uploads reference another project")
    tests = negative.get("results")
    if (
        not isinstance(tests, list)
        or len(tests) != 3
        or {
            x.get("filename"): (x.get("expected"), x.get("actual"))
            for x in tests if isinstance(x, dict)
        } != {name: (status, status) for name, status in NEGATIVES.items()}
        or negative.get("unchangedDocuments") != 4
    ):
        invalid("negative upload evidence is incomplete")
    sources = ledger.get("sources")
    if not isinstance(sources, list) or len(sources) != 4:
        invalid("expected exactly four uploaded sources")
    seen_names: set[str] = set()
    seen_docs: set[UUID] = set()
    seen_revs: set[UUID] = set()
    checked = []
    for s in sources:
        if not isinstance(s, dict):
            invalid("malformed source entry")
        name = s.get("filename")
        if name not in FAMILIES or name in seen_names or s.get("type") != FAMILIES[name]:
            invalid("missing, duplicate or misclassified source family")
        try:
            doc_id = UUID(str(s["documentId"]))
            rev_id = UUID(str(s["revisionId"]))
        except (ValueError, KeyError, TypeError):
            invalid("invalid document/revision identity")
        if doc_id in seen_docs or rev_id in seen_revs:
            invalid("source IDs are not unique")
        seen_names.add(name)
        seen_docs.add(doc_id)
        seen_revs.add(rev_id)
        expected = manifest.get("sha256", {}).get(name)
        if (
            not isinstance(expected, str) or len(expected) != 64
            or s.get("sha256") != expected
            or hashlib.sha256((fixtures / name).read_bytes()).hexdigest() != expected
        ):
            invalid(f"fixture SHA256 is not pinned for {name}")
        checked.append((name, FAMILIES[name], doc_id, rev_id, expected))
    if seen_names != set(FAMILIES):
        invalid("canonical fourth document absent")
    return project_id, checked


def local_test_dsn(raw: str) -> str:
    if not raw:
        invalid("TEST_DATABASE_URL missing")
    url = urlparse(raw)
    if (
        url.hostname not in {"localhost", "127.0.0.1"}
        or url.port != 5433 or url.path != "/c2pro_test"
        or url.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}
    ):
        invalid("database is not the isolated localhost:5433/c2pro_test")
    return raw.replace(url.scheme + "://", "postgresql+asyncpg://", 1)


async def verify(database_url: str, project_id: UUID, sources: list):
    engine = create_async_engine(local_test_dsn(database_url))
    try:
        async with engine.connect() as db:
            # A genuinely independent SQL reader, not an app API or a shared session.
            await db.execute(text("SET TRANSACTION READ ONLY"))
            row = (await db.execute(text(
                "SELECT tenant_id FROM projects WHERE id=:p"
            ), {"p": project_id})).all()
            if len(row) != 1:
                invalid("the Playwright project does not exist exactly once")
            tenant = row[0].tenant_id
            params = {"p": project_id}
            docs = (await db.execute(text(
                "SELECT id, tenant_id, project_id, filename, document_type::text AS type, "
                "file_hash, document_metadata, parsed_at, upload_status::text AS status "
                "FROM documents WHERE project_id=:p"
            ), params)).all()
            revs = (await db.execute(text(
                "SELECT revision_id, document_id, project_id, tenant_id, rev_no, "
                "parent_revision_id, blob_hash, blob_key, valid_to "
                "FROM document_revisions WHERE project_id=:p"
            ), params)).all()
            events = (await db.execute(text(
                "SELECT source_revision_id, project_id, tenant_id "
                "FROM project_events WHERE project_id=:p AND event_type='revision.ingested'"
            ), params)).all()
            work = (await db.execute(text(
                "SELECT op.document_id, op.tenant_id, op.revision_id, op.stage, "
                "op.phase, op.fencing_token FROM document_processing_operations op "
                "JOIN documents d ON d.id=op.document_id WHERE d.project_id=:p"
            ), params)).all()
            counts = tuple(map(len, (docs, revs, events, work)))
            if counts != (4, 4, 4, 4):
                invalid(f"SQL document/revision/event/worker counts {counts}, expected 4 each")
            by_doc = {d.id: d for d in docs}
            by_rev = {r.revision_id: r for r in revs}
            by_event = {e.source_revision_id: e for e in events}
            by_work = {w.document_id: w for w in work}
            if any(len(x) != 4 for x in (by_doc, by_rev, by_event, by_work)):
                invalid("missing or repeated SQL source identities")
            output = []
            for name, kind, document_id, revision_id, sha in sources:
                d = by_doc.get(document_id)
                r = by_rev.get(revision_id)
                ev = by_event.get(revision_id)
                w = by_work.get(document_id)
                if None in (d, r, ev, w):
                    invalid(f"SQL lineage missing for {name}")
                if (d.project_id != project_id or d.tenant_id != tenant or d.filename != name
                        or d.type != kind):
                    invalid(f"wrong project, tenant or document type for {name}")
                # Initial upload records the hash in metadata; file_hash is optional
                # on the legacy document row. The revision's immutable hash is mandatory.
                if (d.document_metadata or {}).get("file_hash") != sha:
                    invalid(f"stored document metadata hash differs for {name}")
                if d.file_hash is not None and d.file_hash != sha:
                    invalid(f"legacy document hash differs for {name}")
                if (r.document_id != document_id or r.project_id != project_id
                        or r.tenant_id != tenant or r.rev_no != 1
                        or r.parent_revision_id is not None or r.valid_to is not None
                        or r.blob_hash != sha or sha not in r.blob_key):
                    invalid(f"immutable revision lineage mismatch for {name}")
                if ev.project_id != project_id or ev.tenant_id != tenant:
                    invalid(f"revision.ingested not bound to the same project for {name}")
                if (w.tenant_id != tenant or w.revision_id != revision_id
                        or w.phase == "FAILED" or w.fencing_token < 1):
                    invalid(f"worker authority not bound to revision for {name}")
                if d.parsed_at is None:
                    invalid(f"worker has not durably parsed {name}")
                output.append({
                    "filename": name, "type": kind, "document_id": str(document_id),
                    "revision_id": str(revision_id), "sha256": sha,
                    "worker_stage": w.stage, "worker_phase": w.phase, "document_state": d.status
                })
            return {
                "verification": "ACC-01 S2", "state": "PASS",
                "kind": "independent direct PostgreSQL (read only)",
                "project_id": str(project_id),
                "counts": {"documents": 4, "revisions": 4, "ingested_events": 4, "worker_records": 4},
                "sources": output, "real_ai_uat": "NOT_VERIFIED"
            }
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playwright-json", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_id, entries = source_trace(
        json.loads(args.playwright_json.read_text()),
        json.loads(args.manifest.read_text()), args.fixture_dir
    )
    report = await verify(os.environ.get("TEST_DATABASE_URL", ""), project_id, entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS S2 independent SQL: 4 documents, revisions, events, processing authorities")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, KeyError, OSError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc
