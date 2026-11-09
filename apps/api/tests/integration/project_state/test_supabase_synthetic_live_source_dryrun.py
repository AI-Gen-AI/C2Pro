"""Read-only domain replay of the EPC synthetic case stored in Supabase.

This captures a project-scoped synthetic input snapshot, not credentials or
production customer data. It must never write to Supabase, start AI or approve
a reviewer decision. Source: C2Pro / EPC-SYN-2026-11-05, 2026-11-09.
"""
import asyncio
import json
from dataclasses import replace
from uuid import UUID

import pytest
from src.analysis.domain.contracts import DocumentArtifact
from src.documents.domain.models import Clause as SourceClause
from src.project_state.application.trusted_artifact_projector import TrustedRevisionBundle, build_trusted_state_candidate
from src.project_state.application.materialize_trusted_state import materialize_trusted_state_if_absent

DATA = json.loads("{\"clauses\":[{\"id\":\"fe343e1c-f643-5dc0-8fc6-0d03bb4e051b\",\"title\":\"SYN EPC 2026 - Engineering Procurement Construction Contract\",\"full_text\":\"SYN EPC 2026 - Engineering Procurement Construction Contract\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-001\",\"clause_type\":\"other\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":60,\"manually_verified\":false,\"text_start_offset\":0},{\"id\":\"161a00fe-5fea-5273-8e8b-c29b6fc8d98d\",\"title\":\"Synthetic EPC Owner and Synthetic EPC Contractor. This document is fictional and\",\"full_text\":\"Synthetic EPC Owner and Synthetic EPC Contractor. This document is fictional and for C2Pro functional validation.\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-003\",\"clause_type\":\"other\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":187,\"manually_verified\":false,\"text_start_offset\":74},{\"id\":\"4acb653c-5bb5-5df2-b1a1-38129ad818a1\",\"title\":\"4.1 The total contract price is EUR 1,000,000.00, excluding agreed variations. T\",\"full_text\":\"4.1 The total contract price is EUR 1,000,000.00, excluding agreed variations. The contract sum is fixed unless a written change order is approved by the Owner.\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-005\",\"clause_type\":\"other\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":369,\"manually_verified\":false,\"text_start_offset\":209},{\"id\":\"358aba10-3021-5f2e-bd39-5d4d23c0a81a\",\"title\":\"8.2 The contractual completion deadline is 2027-06-30. Contractor shall achieve \",\"full_text\":\"8.2 The contractual completion deadline is 2027-06-30. Contractor shall achieve completion of all works by 2027-06-30. Any later schedule requires prior written approval.\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-007\",\"clause_type\":\"scope\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":569,\"manually_verified\":false,\"text_start_offset\":399},{\"id\":\"58b25fca-d38e-5bc6-88a0-5ff068a74328\",\"title\":\"8.3 Contractor may be subject to delay penalties for unapproved late completion.\",\"full_text\":\"8.3 Contractor may be subject to delay penalties for unapproved late completion. The contractor must notify changes in writing.\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-009\",\"clause_type\":\"penalty\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":718,\"manually_verified\":false,\"text_start_offset\":591},{\"id\":\"bf4060eb-3368-5d73-bdde-b566812e5bd4\",\"title\":\"SYNTHETIC TEST DOCUMENT - no commercial validity.\",\"full_text\":\"SYNTHETIC TEST DOCUMENT - no commercial validity.\",\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"clause_code\":\"AUTO-010\",\"clause_type\":\"other\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"text_end_offset\":769,\"manually_verified\":false,\"text_start_offset\":720}],\"payload\":{\"doc_type\":\"contract\",\"bom_items\":[],\"citations\":[],\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"extracted_wbs\":[],\"extracted_risks\":[{\"title\":\"Delay Penalties for Unapproved Late Completion\",\"impact\":\"CRITICAL\",\"source\":\"Contractor may be subject to delay penalties for unapproved late completion. The contractor must notify changes in writing.\",\"category\":\"LEGAL\",\"severity\":\"CRITICAL\",\"clause_ref\":\"8.3\",\"confidence\":null,\"likelihood\":\"MEDIUM\",\"description\":\"Clause 8.3 states that the Contractor 'may be subject to delay penalties for unapproved late completion.' The use of 'may be subject to' without specifying a cap, rate, or maximum aggregate amount leaves the penalty exposure undefined and potentially uncapped. Combined with the written-notification obligation for schedule changes, failure to notify in writing could preclude any defence against penalty imposition. The absence of a defined liability cap for delay penalties is a material budget and legal risk.\",\"source_quote\":\"Contractor may be subject to delay penalties for unapproved late completion. The contractor must notify changes in writing.\",\"source_quote_status\":\"VERIFIED\",\"mitigation_suggestion\":\"Negotiate a defined liquidated damages rate and an aggregate cap on delay penalties before contract execution. Implement a robust written-notification procedure for any schedule changes so that all deviations are formally communicated and approval is sought in advance, preserving the Contractor's position.\"},{\"title\":\"Hard Contractual Completion Deadline\",\"impact\":\"HIGH\",\"source\":\"The contractual completion deadline is 2027-06-30. Contractor shall achieve completion of all works by 2027-06-30. Any later schedule requires prior written approval.\",\"category\":\"SCHEDULE\",\"severity\":\"HIGH\",\"clause_ref\":\"8.2\",\"confidence\":null,\"likelihood\":\"MEDIUM\",\"description\":\"Clause 8.2 establishes 2027-06-30 as the contractual completion deadline and requires all works to be completed by that date. Any deviation from this deadline requires prior written approval, meaning the Contractor bears the full risk of schedule overrun unless approval is proactively sought and granted. There is no mention of force majeure relief, employer-caused delay relief, or other excusable delay provisions in the cited clauses, which heightens the Contractor's exposure.\",\"source_quote\":\"The contractual completion deadline is 2027-06-30. Contractor shall achieve completion of all works by 2027-06-30. Any later schedule requires prior written approval.\",\"source_quote_status\":\"VERIFIED\",\"mitigation_suggestion\":\"Conduct a detailed baseline programme review immediately to confirm feasibility of the 2027-06-30 date. Identify critical path activities and build in float. Establish a formal change-approval protocol to ensure any schedule deviation triggers a timely written approval request before the deadline is missed.\"}],\"confidence_score\":null,\"document_category\":\"LEGAL\",\"coherence_findings\":[],\"pii_redaction_count\":0,\"document_revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"documentation_health_signal\":null},\"tenant_id\":\"e16a4ede-f7fa-470d-9417-7213552ef29e\",\"project_id\":\"bb51b6f4-98f1-4ea5-8959-4b6afcc5a1f1\",\"artifact_id\":\"6f7d1425-0480-4fc1-a319-ab4cff2e0f62\",\"document_id\":\"58b9398d-7616-43c9-a61c-eb5da090f6f1\",\"revision_id\":\"a09cd860-6349-4458-ba26-d9aba4ba997a\",\"trust_state\":\"trusted\",\"lifecycle_status\":\"active\"}")
PROJECT = UUID(DATA["project_id"])
TENANT = UUID(DATA["tenant_id"])

def _bundle():
    art=DocumentArtifact.model_validate(DATA["payload"])
    clauses=tuple(SourceClause(
        id=UUID(c["id"]), project_id=UUID(c["project_id"]),
        tenant_id=UUID(c["tenant_id"]), document_id=UUID(c["document_id"]),
        revision_id=UUID(c["revision_id"]), clause_code=c["clause_code"],
        clause_type=c["clause_type"], title=c["title"], full_text=c["full_text"],
        text_start_offset=c["text_start_offset"], text_end_offset=c["text_end_offset"],
        manually_verified=bool(c["manually_verified"])
    ) for c in DATA["clauses"])
    return TrustedRevisionBundle(artifact=art,source_clauses=clauses,
        trust_state=DATA["trust_state"],lifecycle_status=DATA["lifecycle_status"])

class _MemoryRepo:
    def __init__(self): self.stored=None
    async def insert_if_absent(self,state):
        if self.stored is not None: return False
        self.stored=state
        return True
    async def get(self,project_id,tenant_id):
        if self.stored is None:return None
        return self.stored if self.stored.project_id==project_id and self.stored.tenant_id==tenant_id else None

def test_real_stored_synthetic_artifact_builds_six_clauses_two_source_bound_risks():
    bundle=_bundle()
    candidate=build_trusted_state_candidate(project_id=PROJECT,tenant_id=TENANT,bundles=[bundle])
    assert candidate is not None
    diagnostics=candidate.diagnostics
    assert (diagnostics.input_bundles,diagnostics.revision_bound_clauses,diagnostics.source_bound_risks)==(1,6,2)
    assert diagnostics.rejected_unverified_risks==0
    assert diagnostics.missing_clause_source_revisions==0
    assert len(candidate.state.document_revision_ids)==1
    assert str(candidate.state.document_revision_ids[0])==DATA["revision_id"]
    assert all(item.evidence for item in candidate.state.clauses+candidate.state.risks)

@pytest.mark.asyncio
async def test_real_stored_synthetic_artifact_create_then_unchanged_no_db():
    b=_bundle()
    repo=_MemoryRepo()
    first=await materialize_trusted_state_if_absent(project_id=PROJECT,tenant_id=TENANT,bundles=[b],repository=repo)
    second=await materialize_trusted_state_if_absent(project_id=PROJECT,tenant_id=TENANT,bundles=[b],repository=repo)
    assert first.status=="created"
    assert second.status=="unchanged"
    assert len(repo.stored.clauses)==6
    assert len(repo.stored.risks)==2

@pytest.mark.asyncio
async def test_real_stored_synthetic_artifact_malformed_quote_fails_closed():
    b=_bundle()
    unverified=b.artifact.extracted_risks[0].model_copy(update={"source_quote_status":"NOT_FOUND"})
    degraded=b.artifact.model_copy(update={"extracted_risks":[unverified,*b.artifact.extracted_risks[1:]]})
    result=await materialize_trusted_state_if_absent(project_id=PROJECT,tenant_id=TENANT,
        bundles=[replace(b,artifact=degraded)],repository=_MemoryRepo())
    assert result.status=="source_provenance_unavailable"
    assert result.rejected_unverified_risks>=1

def test_real_stored_synthetic_artifact_wrong_tenant_rejected():
    b=_bundle()
    invalid=replace(b.source_clauses[0],tenant_id=UUID("00000000-0000-4000-8000-000000000001"))
    with pytest.raises(ValueError,match="CROSS_TENANT_OR_DOCUMENT"):
        build_trusted_state_candidate(project_id=PROJECT,tenant_id=TENANT,bundles=[
            replace(b,source_clauses=(invalid,*b.source_clauses[1:]))])

def test_real_stored_synthetic_artifact_proposed_not_promoted():
    b=_bundle()
    with pytest.raises(ValueError,match="UNTRUSTED_ARTIFACT"):
        build_trusted_state_candidate(project_id=PROJECT,tenant_id=TENANT,bundles=[
            replace(b,trust_state="proposed")])
