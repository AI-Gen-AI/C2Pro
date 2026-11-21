"""Read-only B3 seam: existing Docling PDF sidecar, MPXJ schedule and XLSX budget.

This is a source inventory adapter for ProjectGraphState. It does not parse
original files, alter uploads, write trusted artifacts, invoke N4/N12, bind
WBS, promote findings or calculate scores. Call it only with already parsed,
revision-checked outputs from the existing respective use cases.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

_SHA = re.compile(r"[0-9a-fA-F]{64}")


class B3SourceBridgeError(ValueError):
    pass


@dataclass(frozen=True)
class B3Revision:
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    blob_sha256: str

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), UUID)
               for key in ("tenant_id", "project_id", "document_id", "revision_id")):
            raise B3SourceBridgeError("source scope requires UUID identifiers")
        if not isinstance(self.blob_sha256, str) or not _SHA.fullmatch(self.blob_sha256):
            raise B3SourceBridgeError("source revision SHA256 required")


def _ref(family: str, r: B3Revision, count: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "family": family,
        "tenant_id": str(r.tenant_id),
        "project_id": str(r.project_id),
        "document_id": str(r.document_id),
        "revision_id": str(r.revision_id),
        "blob_sha256": r.blob_sha256.lower(),
        "role": "SOURCE_EVIDENCE_ONLY_NOT_PROJECTED",
    }
    if count is not None:
        out["observed_source_rows"] = count
    return out


def assemble_b3_source_inventory(
    *, contract_revision: B3Revision,
    contract_sidecar: Mapping[str, Any],
    schedule_revision: B3Revision | None = None,
    native_schedule: Mapping[str, Any] | None = None,
    budget_revision: B3Revision | None = None,
    budget_rows: Collection[Any] = (),
) -> dict[str, Any]:
    """Only source metadata is returned; no source text or monetary score."""
    revisions = [r for r in (contract_revision, schedule_revision, budget_revision) if r]
    if len({(r.tenant_id, r.project_id) for r in revisions}) != 1:
        raise B3SourceBridgeError("mixed tenant or project")
    if contract_sidecar.get("physical_pdf_sha256", "").lower() != contract_revision.blob_sha256.lower():
        raise B3SourceBridgeError("contract source SHA mismatch")
    if (contract_sidecar.get("source_of_n2_text") != "CURRENT_PDF_PARSER"
        or contract_sidecar.get("trusted_promotions") != 0
        or contract_sidecar.get("n4_executed") is not False):
        raise B3SourceBridgeError("contract cannot promote or replace original parser")
    if contract_sidecar.get("docling_table_status") not in ("ADVISORY_ONLY", "UNAVAILABLE"):
        raise B3SourceBridgeError("Docling table provenance invalid")

    refs = [_ref("contract", contract_revision)]
    missing = []
    if native_schedule is None:
        missing.append("NATIVE_SCHEDULE_CANDIDATES")
    else:
        if schedule_revision is None:
            raise B3SourceBridgeError("schedule revision missing")
        scope = native_schedule.get("scope", {})
        if any(scope.get(k) != str(getattr(schedule_revision, k))
               for k in ("tenant_id", "project_id", "document_id", "revision_id")):
            raise B3SourceBridgeError("schedule scope mismatch")
        source = native_schedule.get("source", {})
        if (source.get("sha256", "").lower() != schedule_revision.blob_sha256.lower()
            or source.get("reader") != "mpxj"
            or source.get("format") not in (".mpp", ".xer")):
            raise B3SourceBridgeError("schedule format or SHA invalid")
        if (native_schedule.get("state") != "CANDIDATE_UNVALIDATED"
            or native_schedule.get("trusted_promotions") != 0
            or native_schedule.get("effects_allowed") is not False):
            raise B3SourceBridgeError("schedule authority not candidate-only")
        rows = native_schedule.get("activities")
        if not isinstance(rows, list) or not rows:
            raise B3SourceBridgeError("schedule activities missing")
        if any(not isinstance(row, dict)
               or row.get("wbs_node_id") is not None
               or row.get("approved_wbs_baseline_id") is not None
               for row in rows):
            raise B3SourceBridgeError("unapproved WBS mapping")
        locators = [row.get("source_locator") for row in rows]
        if any(not isinstance(k, str) or not k for k in locators) or len(set(locators)) != len(locators):
            raise B3SourceBridgeError("duplicate schedule locator")
        refs.append(_ref("schedule", schedule_revision, len(rows)))

    rows = tuple(budget_rows)
    if rows and budget_revision is None:
        raise B3SourceBridgeError("budget revision missing")
    if budget_revision is None:
        missing.append("BUDGET_SOURCE")
    else:
        seen = set()
        for row in rows:
            if any(getattr(row, k, None) != getattr(budget_revision, k)
                   for k in ("tenant_id", "project_id", "document_id", "revision_id")):
                raise B3SourceBridgeError("budget row lineage mismatch")
            locator = getattr(row, "source_locator", None)
            if not isinstance(locator, str) or not locator or locator in seen:
                raise B3SourceBridgeError("duplicate budget source locator")
            seen.add(locator)
        if rows:
            refs.append(_ref("budget", budget_revision, len(rows)))
        else:
            missing.append("BUDGET_VERIFIED_ROWS")
    return {
        "tenant_id": str(contract_revision.tenant_id),
        "project_id": str(contract_revision.project_id),
        "structured_source_refs": refs,
        "source_count": len(refs),
        "advisory_docling_tables": len(contract_sidecar.get("docling_tables") or []),
        "unresolved_inputs": missing,
        "source_authority": "CANDIDATE_UNVALIDATED",
        "original_pdf_page_attestation": "UNVERIFIED",
        "schedule_approved_baseline": False,
        "n4_status": "NOT_RUN_BY_BRIDGE",
        "n12_status": "NOT_RUN_BY_BRIDGE",
        "projectgraph_scoring": "BLOCKED_NO_TRUSTED_PROJECTION",
        "coherence_score": None,
        "trusted_promotions": 0,
        "effects_allowed": False,
    }
