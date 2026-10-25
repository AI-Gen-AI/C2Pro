"""ACC-01 S7: fail-closed technical-to-WBS mapping *candidate*.

A technical specification section, a canonical WBS node and a human-approved
relationship are three different objects. This pure-domain guard checks source
lineage and approved WBS scope, but deliberately does NOT approve or persist a
relationship, produce a technical score, or invent cross-document comparability.

The application adapter must obtain current_trusted_revision_id from the C3a
trusted-current resolver and approved_wbs_scope from the transaction-locked
current-approved WBS authority service. Never accept those as API user input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from src.analysis.domain.budget_row_evidence import ApprovedWBSScope
from src.documents.domain.models import Clause
from src.temporal.domain.document_revision import DocumentRevision

_SOURCE_SECTION = re.compile(r"\d{1,3}(?:\.\d{1,3}){0,6}\Z")
# Detect ALL numbered source headings as authority boundaries, including
# unsupported over-depth/overlong codes. An ignored heading must not let an
# earlier approved-looking section claim obligations written below it.
_SOURCE_HEADING = re.compile(
    r"^[ \t]*(?:section|secci[oó]n|apartado)[ \t]+"
    r"(?P<code>\d+(?:\.\d+)*)(?=[ \t\r\n.:\-–]|$)",
    re.IGNORECASE | re.MULTILINE,
)
_EXTRACTION_MODEL = "deterministic-technical-section-v1"


class TechnicalWBSLinkCandidateError(ValueError):
    """Requested preview is not supported by trusted source and approved scope."""


class TechnicalLinkState(StrEnum):
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass(frozen=True)
class TechnicalWBSLinkCandidate:
    """Not a canonical link; the actual link requires separate durable HITL."""

    tenant_id: UUID
    project_id: UUID
    technical_document_id: UUID
    technical_revision_id: UUID
    source_blob_hash: str
    source_clause_id: UUID
    source_section: str
    source_start_offset: int
    source_end_offset: int
    proposed_wbs_baseline_id: UUID
    proposed_wbs_node_id: UUID
    state: TechnicalLinkState = TechnicalLinkState.HUMAN_REVIEW_REQUIRED
    assessment: str = "NOT_ASSESSED"

    @property
    def is_approved_link(self) -> bool:
        return False


def preview_technical_wbs_link(
    *,
    document_revision: DocumentRevision,
    clause: Clause,
    trusted_current_revision_id: UUID | None,
    parsed_revision_text: str,
    approved_wbs_scope: ApprovedWBSScope | None,
    proposed_wbs_node_id: UUID,
    actor_tenant_id: UUID,
) -> TechnicalWBSLinkCandidate:
    """Check a proposed technical-source -> approved-WBS-node association.

    This function is an eligibility check, NOT a link writer. Approval of a WBS
    baseline does not approve the association or a technical compliance result.
    """
    if (
        actor_tenant_id != document_revision.tenant_id
        or clause.tenant_id != document_revision.tenant_id
        or clause.project_id != document_revision.project_id
        or clause.document_id != document_revision.document_id
    ):
        raise TechnicalWBSLinkCandidateError("technical source is not in the authorized project")
    if (
        clause.revision_id is None
        or clause.revision_id != document_revision.revision_id
        or trusted_current_revision_id != document_revision.revision_id
    ):
        raise TechnicalWBSLinkCandidateError("technical source revision is not trusted-current")
    if clause.extraction_model != _EXTRACTION_MODEL:
        raise TechnicalWBSLinkCandidateError("technical source extraction provenance is missing")

    technical = clause.extracted_entities.get("technical_requirement")
    location = clause.extracted_entities.get("evidence_location")
    if not isinstance(technical, dict) or not isinstance(location, dict):
        raise TechnicalWBSLinkCandidateError("technical section source locator is missing")
    section = technical.get("source_section")
    if (
        not isinstance(section, str)
        or _SOURCE_SECTION.fullmatch(section) is None
        or section != clause.clause_code
        or technical.get("verification_status") != "unverified"
        or location.get("revision_id") != str(document_revision.revision_id)
    ):
        raise TechnicalWBSLinkCandidateError("technical section provenance is inconsistent")
    start, end = clause.text_start_offset, clause.text_end_offset
    if (
        start is None
        or end is None
        or start < 0
        or end <= start
        or end > len(parsed_revision_text)
        or not clause.full_text
        or parsed_revision_text[start:end] != clause.full_text
    ):
        raise TechnicalWBSLinkCandidateError("technical source span is not verified against revision")

    # Read section identity from the independently pinned source, not two
    # metadata fields that an upstream bug could falsify together. The saved
    # evidence window can begin AFTER the heading in long technical sections.
    # Find the last source heading preceding that window and enforce that its
    # scope still contains the complete literal evidence span.
    headings = list(_SOURCE_HEADING.finditer(parsed_revision_text))
    enclosing_heading = next(
        (heading for heading in reversed(headings) if heading.start() <= start),
        None,
    )
    if enclosing_heading is None or enclosing_heading.group("code") != section:
        raise TechnicalWBSLinkCandidateError("technical section is not the source heading")
    next_heading = next(
        (heading for heading in headings if heading.start() > enclosing_heading.start()),
        None,
    )
    if next_heading is not None and end > next_heading.start():
        raise TechnicalWBSLinkCandidateError("technical source span crosses source sections")

    if (
        approved_wbs_scope is None
        or approved_wbs_scope.tenant_id != document_revision.tenant_id
        or approved_wbs_scope.project_id != document_revision.project_id
        or proposed_wbs_node_id not in approved_wbs_scope.node_ids
    ):
        raise TechnicalWBSLinkCandidateError("WBS node is not part of current approved scope")

    return TechnicalWBSLinkCandidate(
        tenant_id=document_revision.tenant_id,
        project_id=document_revision.project_id,
        technical_document_id=document_revision.document_id,
        technical_revision_id=document_revision.revision_id,
        source_blob_hash=document_revision.blob_hash,
        source_clause_id=clause.id,
        source_section=section,
        source_start_offset=start,
        source_end_offset=end,
        proposed_wbs_baseline_id=approved_wbs_scope.baseline_id,
        proposed_wbs_node_id=proposed_wbs_node_id,
    )
