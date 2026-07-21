"""
DB round-trip certification for Evidence Intelligence Layer shadow persistence.

Refers to Suite ID: TS-INT-DB-EVI-SHADOW-001.

Validates the end-to-end shadow write path:
    EPC fixture payloads
    → LegalExtractionAdapter (in-memory validation)
    → SqlAlchemyEvidenceShadowRepository (DB persistence)
    → raw SQL verification via AsyncSession

Explicitly NOT:
  - Connected to Celery
  - Read by Coherence Engine
  - Touching any scoring logic
  - Using real PDF ingestion
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.adapters.persistence.evidence_shadow_repository import (
    SqlAlchemyEvidenceShadowRepository,
)
from src.evidence.adapters.persistence.models import (
    EvidenceClaimORM,
    EvidenceExtractionEventORM,
)
from src.evidence.domain.models import (
    VerificationStatus,
)
from src.evidence.legal.adapter import LegalExtractionAdapter
from tests.modules.evidence.legal.fixtures.epc_contract_001 import (
    EPC_001_DOCUMENT_ID,
    EPC_001_EXPECTATIONS,
    build_epc_001_payloads,
)

# Stable test tenant / project — never a real customer ID.
_TEST_TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_TEST_PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _count_table(db: AsyncSession, table_name: str) -> int:
    result = await db.execute(text(f"SELECT count(*) FROM {table_name}"))
    return result.scalar_one()


async def _select_all_claims(db: AsyncSession) -> list[EvidenceClaimORM]:
    result = await db.execute(select(EvidenceClaimORM))
    return list(result.scalars().all())


async def _select_all_events(db: AsyncSession) -> list[EvidenceExtractionEventORM]:
    result = await db.execute(select(EvidenceExtractionEventORM))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def extraction_run_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.requires_services
@pytest.mark.asyncio
class TestEvidencePersistenceRoundtrip:
    """Full round-trip: adapter → repository → DB verification."""

    async def test_full_roundtrip_cardinality(
        self,
        db: AsyncSession,
        extraction_run_id: UUID,
    ) -> None:
        """4 claims in evidence_claims, 3 events in evidence_extraction_events."""
        adapter = LegalExtractionAdapter(document_id=EPC_001_DOCUMENT_ID)
        payloads = build_epc_001_payloads()
        adapter_result = adapter.adapt(payloads)

        repo = SqlAlchemyEvidenceShadowRepository(db)
        await repo.add_batch(
            tenant_id=_TEST_TENANT_ID,
            project_id=_TEST_PROJECT_ID,
            extraction_run_id=extraction_run_id,
            adapter_result=adapter_result,
        )

        claim_count = await _count_table(db, "evidence_claims")
        event_count = await _count_table(db, "evidence_extraction_events")

        assert claim_count == EPC_001_EXPECTATIONS["claim_count"]  # 4
        assert event_count == (
            EPC_001_EXPECTATIONS["out_of_scope_count"]
            + EPC_001_EXPECTATIONS["processing_error_count"]
        )  # 3

    async def test_claims_channel_populated(
        self,
        db: AsyncSession,
        extraction_run_id: UUID,
    ) -> None:
        """All 4 claims have lifecycle_status='shadow', correct dimension/claim_type."""
        adapter = LegalExtractionAdapter(document_id=EPC_001_DOCUMENT_ID)
        result = adapter.adapt(build_epc_001_payloads())

        repo = SqlAlchemyEvidenceShadowRepository(db)
        await repo.add_batch(
            tenant_id=_TEST_TENANT_ID,
            project_id=_TEST_PROJECT_ID,
            extraction_run_id=extraction_run_id,
            adapter_result=result,
        )

        claims = await _select_all_claims(db)
        assert len(claims) == 4

        for c in claims:
            assert c.lifecycle_status == "shadow"
            assert c.dimension == "LEGAL"
            assert c.tenant_id == _TEST_TENANT_ID
            assert c.project_id == _TEST_PROJECT_ID
            assert c.document_id == EPC_001_DOCUMENT_ID
            assert c.verification_status == VerificationStatus.UNCERTAIN.value
            assert c.verification_trace.get("cvc_disabled") is True
            assert c.algorithmic_certainty >= 0
            assert c.algorithmic_certainty <= 1
            assert c.freshness >= 0
            assert c.freshness <= 1

        claim_types = {c.claim_type for c in claims}
        assert claim_types == {"payment_terms", "late_fees_penalties", "liability_cap"}

        # 2 payment_terms, 1 late_fees_penalties, 1 liability_cap
        ct_counts = {c.claim_type: 0 for c in claims}
        for c in claims:
            ct_counts[c.claim_type] = ct_counts.get(c.claim_type, 0) + 1
        assert ct_counts == {
            "payment_terms": 2,
            "late_fees_penalties": 1,
            "liability_cap": 1,
        }

    async def test_events_channel_populated(
        self,
        db: AsyncSession,
        extraction_run_id: UUID,
    ) -> None:
        """3 extraction events: 2 out_of_scope + 1 processing_error."""
        adapter = LegalExtractionAdapter(document_id=EPC_001_DOCUMENT_ID)
        result = adapter.adapt(build_epc_001_payloads())

        repo = SqlAlchemyEvidenceShadowRepository(db)
        await repo.add_batch(
            tenant_id=_TEST_TENANT_ID,
            project_id=_TEST_PROJECT_ID,
            extraction_run_id=extraction_run_id,
            adapter_result=result,
        )

        events = await _select_all_events(db)
        assert len(events) == 3

        oos_events = [e for e in events if e.event_type == "out_of_scope"]
        err_events = [e for e in events if e.event_type == "processing_error"]
        assert len(oos_events) == EPC_001_EXPECTATIONS["out_of_scope_count"]  # 2
        assert len(err_events) == EPC_001_EXPECTATIONS["processing_error_count"]  # 1

        for e in events:
            assert e.tenant_id == _TEST_TENANT_ID
            assert e.project_id == _TEST_PROJECT_ID
            assert e.document_id == EPC_001_DOCUMENT_ID

        oos_reasons = {e.reason for e in oos_events}
        assert oos_reasons == {"wrong_dimension", "unknown_claim_type"}

        processing_error = err_events[0]
        assert processing_error.reason == "schema_validation_error"
        assert processing_error.claim_type == "late_fees_penalties"
        assert processing_error.dimension == "LEGAL"

    async def test_shared_extraction_run_id(
        self,
        db: AsyncSession,
        extraction_run_id: UUID,
    ) -> None:
        """All claims and events share the same extraction_run_id."""
        adapter = LegalExtractionAdapter(document_id=EPC_001_DOCUMENT_ID)
        result = adapter.adapt(build_epc_001_payloads())

        repo = SqlAlchemyEvidenceShadowRepository(db)
        await repo.add_batch(
            tenant_id=_TEST_TENANT_ID,
            project_id=_TEST_PROJECT_ID,
            extraction_run_id=extraction_run_id,
            adapter_result=result,
        )

        claims = await _select_all_claims(db)
        events = await _select_all_events(db)

        claim_run_ids = {c.extraction_run_id for c in claims}
        event_run_ids = {e.extraction_run_id for e in events}

        assert claim_run_ids == {extraction_run_id}
        assert event_run_ids == {extraction_run_id}

    async def test_jsonb_null_preservation(
        self,
        db: AsyncSession,
        extraction_run_id: UUID,
    ) -> None:
        """Silent fields from Schedule 4 partial payment_terms remain null in JSONB."""
        adapter = LegalExtractionAdapter(document_id=EPC_001_DOCUMENT_ID)
        result = adapter.adapt(build_epc_001_payloads())

        repo = SqlAlchemyEvidenceShadowRepository(db)
        await repo.add_batch(
            tenant_id=_TEST_TENANT_ID,
            project_id=_TEST_PROJECT_ID,
            extraction_run_id=extraction_run_id,
            adapter_result=result,
        )

        claims = await _select_all_claims(db)
        schedule4_claims = [
            c
            for c in claims
            if c.claim_type == "payment_terms" and c.page == 72
        ]
        assert len(schedule4_claims) == 1

        value = schedule4_claims[0].value
        assert value["milestone_count"] == 7
        # Silent fields must be null, not absent or defaulted
        assert value.get("currency") is None
        assert value.get("net_days") is None
        assert value.get("advance_payment_pct") is None
        assert value.get("retention_pct") is None

    async def test_db_enum_constraints_enforced(
        self,
        db: AsyncSession,
    ) -> None:
        """The DB-level CHECK constraints on dimension, verification_status,
        and locator_quality prevent invalid direct inserts."""
        from uuid import uuid4 as _uuid4

        # Invalid dimension
        with pytest.raises(Exception):  # IntegrityError
            await db.execute(
                text(
                    "INSERT INTO evidence_claims (claim_id, extraction_run_id, "
                    "tenant_id, project_id, document_id, dimension, claim_type, "
                    "value, algorithmic_certainty, freshness, "
                    "verification_status, verification_trace, locator_quality) "
                    "VALUES (:cid, :rid, :tid, :pid, :did, 'INVALID', 'test', "
                    "'{}'::jsonb, 0.5, 1.0, 'uncertain', '{}'::jsonb, 'exact')"
                ),
                {
                    "cid": _uuid4(),
                    "rid": _uuid4(),
                    "tid": _TEST_TENANT_ID,
                    "pid": _TEST_PROJECT_ID,
                    "did": EPC_001_DOCUMENT_ID,
                },
            )
            await db.flush()

    async def test_db_range_constraints_enforced(
        self,
        db: AsyncSession,
    ) -> None:
        """algorithmic_certainty and freshness must be in [0, 1] at DB level."""
        from uuid import uuid4 as _uuid4

        with pytest.raises(Exception):  # IntegrityError
            await db.execute(
                text(
                    "INSERT INTO evidence_claims (claim_id, extraction_run_id, "
                    "tenant_id, project_id, document_id, dimension, claim_type, "
                    "value, algorithmic_certainty, freshness, "
                    "verification_status, verification_trace, locator_quality) "
                    "VALUES (:cid, :rid, :tid, :pid, :did, 'LEGAL', 'test', "
                    "'{}'::jsonb, -0.1, 1.0, 'uncertain', '{}'::jsonb, 'exact')"
                ),
                {
                    "cid": _uuid4(),
                    "rid": _uuid4(),
                    "tid": _TEST_TENANT_ID,
                    "pid": _TEST_PROJECT_ID,
                    "did": EPC_001_DOCUMENT_ID,
                },
            )
            await db.flush()
