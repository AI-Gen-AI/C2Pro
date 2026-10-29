"""Real PostgreSQL regressions for ORM + migration-only fixture lifecycle.

Run the whole file twice in independent jobs, and with the reported S5 suite.
These tests must never be represented as a full Alembic/RLS acceptance gate.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("iteration", [1, 2])
async def test_schema_is_fresh_with_recovery_and_external_fk(db, iteration):
    assert (await db.execute(text(
        "SELECT to_regclass('system_recovery.document_work_index')"
    ))).scalar_one() is not None
    assert (await db.execute(text(
        "SELECT count(*) FROM pg_trigger WHERE tgrelid='public.documents'::regclass "
        "AND tgname='trg_documents_recovery_index' AND tgenabled <> 'D'"
    ))).scalar_one() == 1
    assert (await db.execute(text(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conrelid='system_recovery.document_work_index'::regclass AND contype='f'"
    ))).scalar_one() == 1
    assert (await db.execute(text(
        "SELECT count(*) FROM system_recovery.document_work_index"
    ))).scalar_one() == 0
    assert (await db.execute(text(
        "SELECT to_regclass('public.harness_external_dependency')"
    ))).scalar_one() is None
    # Reproduce a SQL-only table referencing ORM metadata, like the HITL ledger.
    await db.execute(text(
        "CREATE TABLE public.harness_external_dependency ("
        "artifact_id uuid REFERENCES public.document_artifacts(artifact_id))"
    ))
    await db.commit()


async def test_recovery_trigger_tracks_insert_update_and_delete(db, test_tenant):
    from uuid import uuid4

    project, document = uuid4(), uuid4()
    from src.documents.adapters.persistence.models import DocumentORM
    from src.documents.domain.models import DocumentType
    from src.projects.adapters.persistence.models import ProjectORM

    db.add(ProjectORM(id=project, tenant_id=test_tenant.id, name="fixture lifecycle"))
    await db.flush()
    db.add(DocumentORM(
        id=document, project_id=project, tenant_id=test_tenant.id,
        filename="fixture.pdf", document_type=DocumentType.CONTRACT,
        file_format="pdf", file_size_bytes=1, storage_url="local://fixture",
    ))
    await db.commit()
    row = (await db.execute(text(
        "SELECT tenant_id, upload_status FROM system_recovery.document_work_index WHERE document_id=:d"
    ), {"d": document})).one()
    assert row.tenant_id == test_tenant.id and row.upload_status == 'uploaded'
    await db.execute(text(
        "UPDATE documents SET updated_at=timestamp '2001-01-01 00:00:00' WHERE id=:d"
    ), {"d": document})
    await db.commit()
    assert (await db.execute(text(
        "SELECT updated_at=timestamp '2001-01-01 00:00:00' "
        "FROM system_recovery.document_work_index WHERE document_id=:d"
    ), {"d": document})).scalar_one() is True
    await db.execute(text("DELETE FROM documents WHERE id=:d"), {"d": document})
    await db.commit()
    assert (await db.execute(text(
        "SELECT count(*) FROM system_recovery.document_work_index WHERE document_id=:d"
    ), {"d": document})).scalar_one() == 0


@pytest.mark.parametrize("iteration", [1, 2])
async def test_trusted_projection_schema_matches_migration(db, iteration):
    """Each ORM fixture must restore the SQL-only #714/C3b obligations.

    This is a metadata-fixture shape regression, not a full Alembic/RLS gate.
    """
    assert (await db.execute(text(
        "SELECT to_regclass('system_recovery.trusted_projection_index')"
    ))).scalar_one() is not None, f"trusted_projection_missing_iteration_{iteration}"

    columns = (await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'system_recovery' "
        "AND table_name = 'trusted_projection_index'"
    ))).scalars().all()
    assert {
        "artifact_id", "document_id", "tenant_id", "project_id",
        "artifact_version", "artifact_hash", "projection_state",
        "materialization_state", "materialization_attempts",
        "materialization_checked_at", "materialized_analysis_id",
        "materialization_detail",
    }.issubset(set(columns))

    assert (await db.execute(text(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conrelid='system_recovery.trusted_projection_index'::regclass "
        "AND contype='f'"
    ))).scalar_one() == 1
    assert (await db.execute(text(
        "SELECT count(*) FROM system_recovery.trusted_projection_index"
    ))).scalar_one() == 0
