"""Resolve Coherence alert XLSX row refs against current original revisions.

This resolves *source identity*, NOT human approval, technical compliance or
a VERIFIED source_clause_id. The caller retains the governing HITL state.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.dtos import AlertCreate
from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral

_SOURCE_SQL = text(f"""
SELECT r.blob_hash
  FROM document_revisions AS r
  JOIN documents AS d ON d.id=r.document_id
       AND d.tenant_id=r.tenant_id AND d.project_id=r.project_id
  CROSS JOIN LATERAL {current_revision_lateral("d.id", "d.tenant_id")} AS cur
  JOIN document_source_units AS u ON u.document_id=r.document_id
       AND u.revision_id=r.revision_id AND u.tenant_id=r.tenant_id
       AND u.project_id=r.project_id
 WHERE r.tenant_id=CAST(:tenant AS uuid)
   AND r.project_id=CAST(:project AS uuid)
   AND r.document_id=CAST(:document AS uuid)
   AND r.revision_id=CAST(:revision AS uuid)
   AND r.valid_to IS NULL
   AND cur.resolved AND cur.revision_id = r.revision_id
   AND u.family=:family AND u.source_locator=:locator
 LIMIT 2
 -- Protect current-revision and row provenance until alert-ledger COMMIT.
 -- A concurrent retirement/update must wait; read-only binds are not HITL.
 FOR SHARE OF r, u
""")


_CONTRACT_SOURCE_SQL = text(f"""
SELECT r.blob_hash
  FROM clauses AS c
  JOIN documents AS d ON d.id=c.document_id
       AND d.tenant_id=c.tenant_id AND d.project_id=c.project_id
  CROSS JOIN LATERAL {current_revision_lateral("d.id", "d.tenant_id")} AS cur
  JOIN document_revisions AS r ON r.revision_id=cur.revision_id
       AND r.document_id=d.id AND r.tenant_id=d.tenant_id AND r.project_id=d.project_id
 WHERE d.tenant_id=CAST(:tenant AS uuid)
   AND d.project_id=CAST(:project AS uuid)
   AND d.id=CAST(:document AS uuid)
   AND r.revision_id=CAST(:revision AS uuid)
   AND c.id=CAST(:locator AS uuid)
   AND c.revision_id=r.revision_id
   AND d.document_type::text='contract'
   AND r.valid_to IS NULL AND cur.canonical
 LIMIT 2
 FOR SHARE OF r,c
""")


async def _verified_contract_source(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    value: object,
) -> bool:
    if not isinstance(value, dict) or value.get("family") != "contract":
        return False
    doc, rev, locator = (
        _uuid(value.get(name))
        for name in (
            "document_id",
            "revision_id",
            "source_locator",
        )
    )
    sha = value.get("blob_sha256")
    if not (doc and rev and locator and isinstance(sha, str) and len(sha) == 64):
        return False
    rows = (
        await db.execute(
            _CONTRACT_SOURCE_SQL,
            {
                "tenant": str(tenant_id),
                "project": str(project_id),
                "document": doc,
                "revision": rev,
                "locator": locator,
            },
        )
    ).all()
    return len(rows) == 1 and rows[0].blob_hash == sha


def _uuid(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


async def resolve_alert_original_rows(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    payloads: list[AlertCreate],
) -> None:
    """Resolve hashes only for persisted original row+current revision+tenant.

    A stale/foreign/fabricated locator must never acquire a source hash. A
    pre-supplied mismatched hash also fails closed; no guessed replacement.
    """
    for payload in payloads:
        metadata = dict(payload.alert_metadata or {})
        detection = metadata.get("detection_evidence")
        if not isinstance(detection, dict):
            continue
        refs = detection.get("structured_sources")
        if not isinstance(refs, list) or not refs:
            continue
        updated: list[dict] = []
        resolved = True
        for value in refs:
            if not isinstance(value, dict):
                resolved = False
                continue
            ref = dict(value)
            doc, rev = _uuid(ref.get("document_id")), _uuid(ref.get("revision_id"))
            family, locator = ref.get("family"), ref.get("source_locator")
            if (
                doc is None
                or rev is None
                or family not in ("budget", "schedule")
                or not isinstance(locator, str)
                or not locator.strip()
            ):
                ref.pop("blob_sha256", None)
                resolved = False
            else:
                rows = (
                    await db.execute(
                        _SOURCE_SQL,
                        {
                            "tenant": str(tenant_id),
                            "project": str(project_id),
                            "document": doc,
                            "revision": rev,
                            "family": family,
                            "locator": locator,
                        },
                    )
                ).all()
                digest = rows[0].blob_hash if len(rows) == 1 else None
                expected = ref.get("blob_sha256")
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or expected not in (None, "", digest)
                ):
                    ref.pop("blob_sha256", None)
                    resolved = False
                else:
                    ref["blob_sha256"] = digest
            updated.append(ref)
        detection["structured_sources"] = updated
        contract_source = detection.get("contract_source")
        if contract_source is not None and not await _verified_contract_source(
            db, tenant_id=tenant_id, project_id=project_id, value=contract_source,
        ):
            resolved = False
        metadata["detection_evidence"] = detection
        metadata["original_row_binding"] = (
            "CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED" if resolved else "NOT_VERIFIED"
        )
        payload.alert_metadata = metadata


def annotate_related_economic_alerts(payloads: list[AlertCreate]) -> None:
    """Expose one discrepancy group even though two rule alerts remain visible.

    Only exact comparison keys emitted by the deterministic scorer can pair.
    Do not deduplicate by category, similar prose or a shared budget row alone.
    """
    groups: dict[str, list[AlertCreate]] = {}
    for payload in payloads:
        meta = payload.alert_metadata or {}
        key = meta.get("economic_discrepancy_key")
        if isinstance(key, str) and key.startswith("CONTRACT_BUDGET:"):
            groups.setdefault(key, []).append(payload)
    for group in groups.values():
        rules = {p.rule_id for p in group}
        if len(group) != 2 or rules != {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"}:
            continue
        for payload in group:
            meta = dict(payload.alert_metadata or {})
            meta["economic_impact_accounting"] = "ONE_DELTA_TWO_RELATED_ALERTS"
            meta["related_rule_codes"] = sorted(rules)
            payload.alert_metadata = meta


async def revalidate_listed_alert_source_bindings(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    alerts: list,
) -> None:
    """Read-time currentness, without changing the historical alert ledger.

    'CURRENT' recorded at detection is a historical transaction observation.
    When later document revision changes, API clients must see STALE_SOURCE,
    never continue treating the original source as CURRENT. This read-only
    recheck does NOT auto-upgrade any NOT_VERIFIED item or promote HITL.
    """
    for alert in alerts:
        if getattr(alert, "original_row_binding", None) != (
            "CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED"
        ):
            continue
        evidence = getattr(alert, "detection_evidence", None)
        refs = getattr(evidence, "structured_sources", None)
        if not refs:
            alert.original_row_binding = "STALE_SOURCE"
            continue
        current = True
        for ref in refs:
            doc, rev = _uuid(ref.document_id), _uuid(ref.revision_id)
            if (
                doc is None
                or rev is None
                or ref.family not in ("budget", "schedule")
                or not isinstance(ref.source_locator, str)
                or not ref.source_locator.strip()
                or not ref.blob_sha256
            ):
                current = False
                break
            hashes = (
                await db.execute(
                    _SOURCE_SQL,
                    {
                        "tenant": str(tenant_id),
                        "project": str(project_id),
                        "document": doc,
                        "revision": rev,
                        "family": ref.family,
                        "locator": ref.source_locator,
                    },
                )
            ).all()
            if len(hashes) != 1 or hashes[0].blob_hash != ref.blob_sha256:
                current = False
                break
        if current and getattr(evidence, "contract_source", None) is not None:
            current = await _verified_contract_source(
                db,
                tenant_id=tenant_id,
                project_id=project_id,
                value=evidence.contract_source,
            )
        if not current:
            alert.original_row_binding = "STALE_SOURCE"
