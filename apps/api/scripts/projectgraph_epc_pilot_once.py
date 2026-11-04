#!/usr/bin/env python3
"""One REAL four-document ProjectGraph pilot, after the existing Clerk S2 browser flow.

This is NOT a unit test or an approval bypass. It consumes the exact S2
PostgreSQL ledger, reuses canonical revision readers and executes Tier-2 once
against the disposable, migrated GitHub Actions database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import text

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.core.database import close_db, get_raw_session, init_db
from src.core.tasks.project_graph_tasks import (
    _load_canonical_project_evidence,
    run_project_graph_once,
)
from src.core.tenants.types import require_tenant_id
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)


def _assert_disposable_runner() -> None:
    value = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(value)
    if (
        parsed.hostname not in ("localhost", "127.0.0.1")
        or parsed.port != 5433
        or parsed.path != "/c2pro_test"
    ):
        raise RuntimeError("PILOT_NONDISPOSABLE_DATABASE_REFUSED")
    if os.environ.get("ENVIRONMENT") != "test":
        raise RuntimeError("PILOT_NONTEST_ENVIRONMENT_REFUSED")
    if os.environ.get("C2PRO_AI_MOCK") != "0":
        raise RuntimeError("PILOT_LLM_MOCK_REFUSED")
    if os.environ.get("FEATURE_V3_COHERENCE_LLM", "").lower() != "true":
        raise RuntimeError("PILOT_COHERENCE_LLM_FLAG_OFF")
    if os.environ.get("FEATURE_V3_PROJECT_GRAPH", "").lower() != "true":
        raise RuntimeError("PILOT_PROJECTGRAPH_FLAG_OFF")


async def _run(ledger: dict, outcome: dict) -> None:
    from src.analysis.adapters.graph.project_graph import (
        is_coherence_llm_enabled,
        is_project_graph_enabled,
    )

    source = ledger.get("sources") or []
    if (
        ledger.get("state") != "PASS"
        or ledger.get("counts", {}).get("documents") != 4
        or len(source) != 4
        or {item.get("type") for item in source}
        != {"contract", "budget", "schedule", "technical_spec"}
    ):
        raise RuntimeError("FOUR_SOURCE_POSTGRESQL_LEDGER_INCOMPLETE")

    project_id = UUID(ledger["project_id"])
    await init_db()
    try:
        async with get_raw_session() as db:
            project = (
                await db.execute(
                    text("SELECT tenant_id FROM projects WHERE id=:p"),
                    {"p": project_id},
                )
            ).one_or_none()
            if project is None:
                raise RuntimeError("PROJECT_ABSENT_FROM_DISPOSABLE_DATABASE")
            tenant_id = require_tenant_id(str(project.tenant_id))
            await db.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            # Four genuinely uploaded files, four persisted revisions, one tenant.
            docs = (
                await db.execute(
                    text(
                        "SELECT document_type::text, upload_status::text, "
                        "COUNT(*) FROM documents "
                        "WHERE project_id=:p AND tenant_id=:t "
                        "GROUP BY document_type::text, upload_status::text"
                    ),
                    {"p": project_id, "t": tenant_id},
                )
            ).all()
            outcome["document_states"] = [
                {"type": kind, "status": status, "count": count}
                for kind, status, count in docs
            ]
            if sum(row[2] for row in docs) != 4:
                raise RuntimeError("FOUR_DOCUMENTS_NOT_PERSISTED")
            outcome["project_id"] = str(project_id)
            outcome["tenant_id"] = str(tenant_id)
            outcome["source_hashes_verified"] = True  # prior S2 SQL gate

            # Bind each of the four uploaded bytes to the canonical trusted-
            # current revision reader; a parsed file is not approved evidence.
            from src.temporal.adapters.persistence.current_revision_sql import (
                current_revision_lateral,
            )
            source_rows = (
                await db.execute(
                    text(
                        "SELECT d.id, d.document_type::text AS family, "
                        "cur.revision_id, cur.canonical, cur.trusted "
                        "FROM documents d "
                        f"CROSS JOIN LATERAL {current_revision_lateral('d.id', 'd.tenant_id')} AS cur "
                        "WHERE d.project_id=:p AND d.tenant_id=:t"
                    ),
                    {"p": project_id, "t": tenant_id},
                )
            ).all()
            outcome["source_authority"] = [
                {
                    "family": row.family,
                    "document_id": str(row.id),
                    "revision_id": str(row.revision_id) if row.revision_id else None,
                    "canonical": bool(row.canonical),
                    "trusted": bool(row.trusted),
                }
                for row in source_rows
            ]
            if len(source_rows) != 4 or any(row.revision_id is None for row in source_rows):
                raise RuntimeError("FOUR_CURRENT_REVISIONS_NOT_RESOLVED")
            for family in ("contract", "technical_spec"):
                if not any(row.family == family and row.trusted for row in source_rows):
                    raise RuntimeError(f"PROJECTGRAPH_{family.upper()}_AWAITING_TRUSTED_APPROVAL")

            flags = {
                "project_graph": await is_project_graph_enabled(tenant_id),
                "coherence_llm": await is_coherence_llm_enabled(tenant_id),
            }
            outcome["effective_feature_flags"] = flags
            if not all(flags.values()):
                raise RuntimeError("PROJECTGRAPH_EFFECTIVE_FLAGS_OFF")

            artifact_repo = SqlAlchemyDocumentArtifactRepository(db)
            snapshot_repo = SqlAlchemyProjectSnapshotRepository(db)
            current = await artifact_repo.list_trusted_for_project(
                project_id=project_id, tenant_id=tenant_id
            )
            clauses, schedule = await _load_canonical_project_evidence(
                db, project_id, tenant_id
            )
            outcome["trusted_document_artifact_count"] = len(current)
            outcome["canonical_clause_count"] = len(clauses)
            outcome["canonical_document_ids"] = sorted(
                {str(c.data.get("document_id")) for c in clauses if c.data.get("document_id")}
            )
            text_ids = {
                str(row.id) for row in source_rows
                if row.family in ("contract", "technical_spec")
            }
            present_text = set(outcome["canonical_document_ids"]) & text_ids
            outcome["verified_text_document_count"] = len(present_text)
            if present_text != text_ids:
                raise RuntimeError("PROJECTGRAPH_TEXT_DOCUMENT_CLAUSES_UNAVAILABLE")
            outcome["schedule_observation_available"] = bool(
                schedule and not schedule.get("reason")
            )
            if not clauses and not current:
                raise RuntimeError("NO_CANONICAL_PROJECT_EVIDENCE")

            # ONE call to the real Tier-2 runtime, on the actual uploaded sources.
            result = await asyncio.wait_for(
                run_project_graph_once(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    artifact_repository=artifact_repo,
                    snapshot_repository=snapshot_repo,
                    db_session=db,
                ),
                timeout=180,
            )
            outcome["graph_status"] = result.get("status")
            outcome["snapshot_id"] = result.get("snapshot_id")
            outcome["projected_obligations"] = result.get("projected_obligations")
            coherence = result.get("coherence_result") or {}
            outcome["coherence"] = {
                "score": coherence.get("overall_score"),
                "score_reason": coherence.get("score_reason"),
                "llm_on": coherence.get("llm_on"),
                "signal_count": coherence.get("signal_count"),
                "finding_count": coherence.get("finding_count"),
                "missing_dimensions": coherence.get("insufficient_data_reasons"),
                "category_scores": coherence.get("category_scores"),
            }
            outcome["node_statuses"] = [
                {
                    "node": n.get("node"),
                    "status": n.get("status"),
                    "degradation_reason": n.get("degradation_reason"),
                }
                for n in result.get("node_results", [])
                if isinstance(n, dict)
            ]
            persisted = await snapshot_repo.latest(project_id, tenant_id)
            # The same repository and DTO mapper used by the authenticated
            # Alerts UI must read the persisted ProjectGraph reconciliation.
            from src.alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
            from src.alerts.application.mappers.alert_mapper import AlertMapper
            alert_rows = await SqlAlchemyAlertRepository(db).list_for_project(
                project_id=project_id, tenant_id=tenant_id
            )
            public_rows = AlertMapper.to_response_list(alert_rows, tenant_id)
            outcome["alert_read_model"] = [
                {
                    "rule_code": row.rule_code,
                    "source_clause_id": str(row.source_clause_id) if row.source_clause_id else None,
                    "source_document_id": (
                        row.detection_evidence.source_document_id
                        if row.detection_evidence else None
                    ),
                    "has_quote": bool(
                        row.detection_evidence and row.detection_evidence.quote
                    ),
                    "structured_ref_count": (
                        len(row.detection_evidence.structured_sources)
                        if row.detection_evidence else 0
                    ),
                    "review_status": row.status,
                }
                for row in public_rows
            ]
            outcome["alerts_persisted"] = len(public_rows)
            outcome["alerts_with_verified_links"] = sum(
                bool(row["source_clause_id"] and row["source_document_id"])
                for row in outcome["alert_read_model"]
            )
            outcome["alerts_with_structured_refs"] = sum(
                row["structured_ref_count"] > 0
                for row in outcome["alert_read_model"]
            )
            outcome["snapshot_durable"] = bool(
                persisted and str(persisted.snapshot_id) == result.get("snapshot_id")
            )
            await db.commit()

            if not outcome["snapshot_durable"]:
                raise RuntimeError("PROJECTGRAPH_SNAPSHOT_NOT_PERSISTED")
            if not outcome["alerts_persisted"]:
                raise RuntimeError("PROJECTGRAPH_NO_PERSISTED_ALERTS")
            if not (outcome["alerts_with_verified_links"] or outcome["alerts_with_structured_refs"]):
                raise RuntimeError("PROJECTGRAPH_NO_VERIFIABLE_ALERT_CITATIONS")
            if not coherence.get("llm_on"):
                raise RuntimeError("PROJECTGRAPH_REAL_LLM_NOT_ENABLED")
            # Contract vs budget and late schedule must produce at least
            # one genuinely observed cross-document issue. A configured LLM
            # or a snapshot alone is NOT sufficient.
            if not (
                (coherence.get("finding_count") or 0) > 0
                or (coherence.get("signal_count") or 0) > 0
            ):
                raise RuntimeError("PROJECTGRAPH_NO_FINDINGS_OR_SIGNALS")
            outcome["state"] = "PARTIAL_REQUIRES_UI_AND_SOURCE_CITATIONS"
            outcome["first_blocker"] = "UI_CITATIONS_AND_RELOGIN_NOT_VERIFIED"
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    outcome = {
        "schema": "c2pro.projectgraph.real_four_sources.v1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "state": "NOT_ACCEPTED",
        "provider_mock": False,
        "first_blocker": None,
    }
    try:
        _assert_disposable_runner()
        asyncio.run(_run(json.loads(args.ledger.read_text()), outcome))
    except Exception as exc:
        # No raw SQL text, credentials, source contents or prompts in artifacts.
        outcome["first_blocker"] = str(exc) if str(exc).startswith(
            ("PILOT_", "FOUR_", "PROJECT_", "NO_CANONICAL_", "PROJECTGRAPH_", "UI_")
        ) else type(exc).__name__
        outcome["state"] = "NOT_ACCEPTED"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print("PROJECTGRAPH_PILOT=" + json.dumps({
        "state": outcome["state"],
        "project_id": outcome.get("project_id"),
        "trusted_artifacts": outcome.get("trusted_document_artifact_count"),
        "canonical_clauses": outcome.get("canonical_clause_count"),
        "snapshot_id": outcome.get("snapshot_id"),
        "first_blocker": outcome["first_blocker"],
    }, sort_keys=True))
    # A valid backend snapshot is PARTIAL, not the user's end-to-end UI UAT.
    # Do not let GitHub's green check suggest ProjectGraph was fully accepted.
    return 0 if outcome["state"] == "ACCEPTED_END_TO_END" else 1


if __name__ == "__main__":
    raise SystemExit(main())
