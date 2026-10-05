#!/usr/bin/env python3
"""Read-only verifier for #867 B1-12 exact-runtime production acceptance."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path("evidence/product-qualification/runtime/b1-12-verifier.json")


class VerificationFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    raise VerificationFailure("database URL must use PostgreSQL")


def _uuid(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure(f"{label} must be a UUID") from exc


def _history(metadata: dict[str, Any], *, action: str, decision: str | None = None) -> list[dict[str, Any]]:
    raw = metadata.get("history")
    if not isinstance(raw, list):
        return []
    items = [item for item in raw if isinstance(item, dict) and item.get("action") == action]
    if decision is not None:
        items = [item for item in items if item.get("decision") == decision]
    return items


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def _one(conn: AsyncConnection, sql: str, params: dict[str, object]) -> dict[str, Any] | None:
    row = (await conn.execute(text(sql), params)).mappings().one_or_none()
    return dict(row) if row is not None else None


async def verify(
    *,
    database_url: str,
    tenant_id: UUID,
    clerk_org_id: str,
    project_id: UUID,
    genuine_alert_id: UUID,
    false_positive_alert_id: UUID,
    post_revision_false_positive_alert_id: UUID,
    genuine_rule: str,
    false_positive_rule: str,
) -> tuple[list[Check], dict[str, Any]]:
    engine = create_async_engine(_url(database_url))
    checks: list[Check] = []
    evidence: dict[str, Any] = {"project_id": str(project_id)}

    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )

                tenant = await _one(
                    conn,
                    """
                    SELECT id, clerk_org_id, settings
                      FROM tenants
                     WHERE id=:tenant AND is_active IS TRUE
                    """,
                    {"tenant": tenant_id},
                )
                tenant_ok = bool(
                    tenant
                    and tenant.get("clerk_org_id") == clerk_org_id
                    and isinstance(tenant.get("settings"), dict)
                    and tenant["settings"].get("synthetic_acceptance") is True
                )
                checks.append(Check("synthetic tenant binding", tenant_ok, f"tenant_found={tenant is not None}"))

                project = await _one(
                    conn,
                    """
                    SELECT id, name FROM projects
                     WHERE id=:project AND tenant_id=:tenant
                    """,
                    {"project": project_id, "tenant": tenant_id},
                )
                project_ok = bool(project and str(project.get("name", "")).startswith("ACCEPT-867-"))
                checks.append(Check("bounded B1 project", project_ok, f"name={project.get('name') if project else None}"))

                alert_rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT id, rule_id, status::text AS status,
                                   approval_status::text AS approval_status,
                                   reviewed_at, alert_metadata
                              FROM alerts
                             WHERE project_id=:project
                               AND tenant_id=:tenant
                               AND alert_type::text='coherence'
                            """
                        ),
                        {"project": project_id, "tenant": tenant_id},
                    )
                ).mappings().all()
                alerts = [dict(row) for row in alert_rows]
                by_id = {row["id"]: row for row in alerts}
                genuine = by_id.get(genuine_alert_id)
                false_positive = by_id.get(false_positive_alert_id)

                checks.append(
                    Check(
                        "browser alert identity remains canonical",
                        false_positive_alert_id == post_revision_false_positive_alert_id,
                        f"initial={false_positive_alert_id} current={post_revision_false_positive_alert_id}",
                    )
                )
                checks.append(
                    Check(
                        "genuine alert exists",
                        bool(genuine and genuine.get("rule_id") == genuine_rule),
                        f"rule={genuine.get('rule_id') if genuine else None}",
                    )
                )
                checks.append(
                    Check(
                        "false-positive family exists",
                        bool(false_positive and false_positive.get("rule_id") == false_positive_rule),
                        f"rule={false_positive.get('rule_id') if false_positive else None}",
                    )
                )

                genuine_meta = dict(genuine.get("alert_metadata") or {}) if genuine else {}
                fp_meta = dict(false_positive.get("alert_metadata") or {}) if false_positive else {}
                approve_history = _history(genuine_meta, action="reviewed", decision="approve")
                reject_history = _history(fp_meta, action="reviewed", decision="reject")
                basis_history = _history(fp_meta, action="basis_changed_reopened")

                checks.append(Check("one genuine review", len(approve_history) == 1, f"approve_reviews={len(approve_history)}"))
                checks.append(Check("one false-positive review", len(reject_history) == 1, f"reject_reviews={len(reject_history)}"))
                checks.append(Check("basis change reopened once", len(basis_history) == 1, f"basis_reopens={len(basis_history)}"))

                finding_key = fp_meta.get("finding_key")
                current_basis = fp_meta.get("current_observation_key")
                reviewed_basis = fp_meta.get("disposition_basis_key")
                stale_basis_rejected = bool(
                    isinstance(finding_key, str)
                    and finding_key
                    and isinstance(current_basis, str)
                    and current_basis
                    and isinstance(reviewed_basis, str)
                    and reviewed_basis
                    and current_basis != reviewed_basis
                    and false_positive
                    and false_positive.get("status") == "open"
                    and false_positive.get("approval_status") == "pending"
                )
                checks.append(
                    Check(
                        "stale false-positive basis does not inherit",
                        stale_basis_rejected,
                        f"status={false_positive.get('status') if false_positive else None} current!=reviewed={current_basis != reviewed_basis}",
                    )
                )

                family_rows = [
                    row
                    for row in alerts
                    if row.get("rule_id") == false_positive_rule
                    and isinstance(row.get("alert_metadata"), dict)
                    and row["alert_metadata"].get("finding_key") == finding_key
                ]
                checks.append(Check("single alert family", len(family_rows) == 1, f"family_rows={len(family_rows)}"))

                results = [
                    dict(row)
                    for row in (
                        await conn.execute(
                            text(
                                """
                                SELECT id, global_score, category_scores, score_version,
                                       score_reason, score_missing_dimensions,
                                       scoring_snapshot, calculated_at
                                  FROM coherence_results
                                 WHERE project_id=:project AND tenant_id=:tenant
                                 ORDER BY calculated_at ASC, id ASC
                                """
                            ),
                            {"project": project_id, "tenant": tenant_id},
                        )
                    ).mappings().all()
                ]
                checks.append(Check("coherence results exist", len(results) >= 3, f"results={len(results)}"))

                rescored = [
                    row
                    for row in results
                    if isinstance(row.get("scoring_snapshot"), dict)
                    and isinstance(row["scoring_snapshot"].get("last_rescore"), dict)
                    and row["scoring_snapshot"]["last_rescore"].get("reason") == "human_false_positive"
                ]
                checks.append(Check("single governed false-positive rescore", len(rescored) == 1, f"rescores={len(rescored)}"))

                source_result = None
                rescore_result = rescored[0] if len(rescored) == 1 else None
                if rescore_result is not None:
                    last_rescore = rescore_result["scoring_snapshot"]["last_rescore"]
                    source_id = last_rescore.get("source_result_id")
                    source_result = next((row for row in results if str(row["id"]) == source_id), None)
                    exact_rescore = bool(
                        source_result
                        and last_rescore.get("reviewed_finding_key") == finding_key
                        and last_rescore.get("reviewed_observation_key") == reviewed_basis
                        and rescore_result["score_version"] == source_result["score_version"]
                        and int(rescore_result["global_score"]) >= int(source_result["global_score"])
                    )
                    checks.append(
                        Check(
                            "same-version exact-snapshot rescore",
                            exact_rescore,
                            f"source_score={source_result.get('global_score') if source_result else None} rescored={rescore_result.get('global_score')}",
                        )
                    )
                else:
                    checks.append(Check("same-version exact-snapshot rescore", False, "no unique rescore row"))

                approve_at = _parse_timestamp(approve_history[0].get("timestamp")) if len(approve_history) == 1 else None
                reject_at = _parse_timestamp(reject_history[0].get("timestamp")) if len(reject_history) == 1 else None
                if approve_at and reject_at and source_result:
                    source_at = source_result["calculated_at"]
                    unexpected = [
                        row
                        for row in results
                        if source_at < row["calculated_at"] < reject_at
                        and row["id"] != source_result["id"]
                    ]
                    approval_no_score_write = approve_at < reject_at and not unexpected
                    checks.append(
                        Check(
                            "approve does not improve canonical score",
                            approval_no_score_write,
                            f"intermediate_score_rows={len(unexpected)}",
                        )
                    )
                else:
                    checks.append(Check("approve does not improve canonical score", False, "review/result timestamps unavailable"))

                latest = results[-1] if results else None
                latest_snapshot = dict(latest.get("scoring_snapshot") or {}) if latest else {}
                latest_findings = latest_snapshot.get("findings")
                current_family = (
                    [
                        item
                        for item in latest_findings
                        if isinstance(item, dict) and item.get("finding_key") == finding_key
                    ]
                    if isinstance(latest_findings, list)
                    else []
                )
                current_observation_in_snapshot = bool(
                    len(current_family) == 1
                    and current_family[0].get("observation_key") == current_basis
                    and current_family[0].get("observation_key") != reviewed_basis
                )
                checks.append(
                    Check(
                        "new authoritative observation is in latest scoring snapshot",
                        current_observation_in_snapshot,
                        f"matching_findings={len(current_family)}",
                    )
                )

                missing = list(latest.get("score_missing_dimensions") or []) if latest else []
                scores = dict(latest.get("category_scores") or {}) if latest else {}
                aliases = {"schedule": "TIME", "financial": "BUDGET", "general": "SCOPE"}
                honest_missing = all(
                    scores.get(aliases.get(str(dim).lower(), str(dim).upper())) is None
                    for dim in missing
                )
                checks.append(
                    Check(
                        "unsupported dimensions remain null",
                        honest_missing,
                        f"missing={missing}",
                    )
                )

                evidence.update(
                    {
                        "genuine_alert_id": str(genuine_alert_id),
                        "false_positive_alert_id": str(false_positive_alert_id),
                        "finding_key": finding_key,
                        "reviewed_observation_key": reviewed_basis,
                        "current_observation_key": current_basis,
                        "coherence_result_count": len(results),
                        "source_result_id": str(source_result["id"]) if source_result else None,
                        "rescore_result_id": str(rescore_result["id"]) if rescore_result else None,
                        "latest_result_id": str(latest["id"]) if latest else None,
                        "source_score": source_result.get("global_score") if source_result else None,
                        "rescored_score": rescore_result.get("global_score") if rescore_result else None,
                        "latest_score": latest.get("global_score") if latest else None,
                        "latest_score_version": latest.get("score_version") if latest else None,
                        "latest_missing_dimensions": missing,
                    }
                )

                await tx.rollback()
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()

    return checks, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--clerk-org-id", default=os.getenv("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--genuine-alert-id", required=True)
    parser.add_argument("--false-positive-alert-id", required=True)
    parser.add_argument("--post-revision-false-positive-alert-id", required=True)
    parser.add_argument("--genuine-rule", required=True)
    parser.add_argument("--false-positive-rule", required=True)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: required production qualification configuration is missing.", file=sys.stderr)
        return 2

    try:
        checks, evidence = asyncio.run(
            verify(
                database_url=database_url,
                tenant_id=_uuid(args.tenant_id, "tenant id"),
                clerk_org_id=args.clerk_org_id,
                project_id=_uuid(args.project_id, "project id"),
                genuine_alert_id=_uuid(args.genuine_alert_id, "genuine alert id"),
                false_positive_alert_id=_uuid(args.false_positive_alert_id, "false-positive alert id"),
                post_revision_false_positive_alert_id=_uuid(
                    args.post_revision_false_positive_alert_id,
                    "post-revision false-positive alert id",
                ),
                genuine_rule=args.genuine_rule,
                false_positive_rule=args.false_positive_rule,
            )
        )
    except Exception as exc:
        print(f"FAIL: B1-12 verifier execution failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2

    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed

    if args.write_evidence:
        out = REPO_ROOT / OUTPUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "schema": "c2pro-b1-12-production-verifier/v1",
                    "verdict": "FAIL" if failed else "PASS",
                    "evidence": evidence,
                    "checks": [
                        {"name": item.name, "passed": item.passed, "detail": item.detail}
                        for item in checks
                    ],
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
