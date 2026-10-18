"""PC-2b.3 (#922) -- WBS import: immutable source -> import snapshot -> explicit human DRAFT.

IMPORTED SOURCE != DRAFT CANDIDATE != APPROVED WBS. Acceptance B (immutable source), D (authority),
E (candidate), F (digest), G (tenancy), I (comparison), J (retention) and the PC-2b.2 qualification
regression, against the real database guards.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.wbs.adapters.persistence import (
    intelligence_models,  # noqa: F401 - registers the run tables
)
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.governance_repository import Actor, WBSGovernanceRepository
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.application.governed_change_service import (
    AddNode,
    NodeSpec,
    UpdateNode,
    WBSChangeSetInvalidError,
    WBSGovernedChangeService,
)
from src.wbs.domain.digest import DigestNode, tree_digest
from src.wbs.domain.governance import ActorKind, ChangeSetOrigin, EntryMode
from src.wbs.imports.contracts import ImportStatus
from src.wbs.imports.service import (
    WBSImportForbiddenError,
    WBSImportIntegrityError,
    WBSImportInvalidError,
    WBSImportNotFoundError,
    WBSImportService,
    WBSImportStateError,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _legacy_nodes,
    _scope,
)
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _baseline_one, _submit

pytestmark = pytest.mark.asyncio

PLANT_CSV = b"code,name,parent_code\n1,Plant,\n1.1,Civil,1\n1.2,Electrical,1\n1.2.1,Cabling,1.2\n"


# --------------------------------------------------------------------------- fixtures
class _Store:
    """A content-addressed stand-in for the revision object store (exact keys only)."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.root = Path(tempfile.mkdtemp(prefix="pc2b3-"))

    async def download_object(self, key: str) -> Path:
        path = self.root / hashlib.sha256(key.encode()).hexdigest()
        path.write_bytes(self.blobs[key])
        return path


STORE = _Store()


def _svc(db: AsyncSession) -> WBSImportService:
    return WBSImportService(db, storage=STORE)  # type: ignore[arg-type]


def _naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _wbs_document(db: AsyncSession, s: Scope, data: bytes, suffix: str = ".csv", *,
                        document_type: DocumentType = DocumentType.WBS) -> tuple[UUID, UUID]:
    document_id, revision_id = uuid4(), uuid4()
    blob_hash = hashlib.sha256(data).hexdigest()
    key = f"tenants/{s.tenant}/projects/{s.project}/documents/{document_id}/revisions/{blob_hash}{suffix}"
    STORE.blobs[key] = data
    db.add(DocumentORM(id=document_id, project_id=s.project, tenant_id=s.tenant, document_type=document_type,
                       filename=f"wbs{suffix}", file_format=suffix, upload_status=DocumentStatus.UPLOADED,
                       created_by=s.author.user_id, file_hash=blob_hash, storage_url=key))
    await db.flush()
    db.add(DocumentRevisionORM(revision_id=revision_id, document_id=document_id, project_id=s.project,
                               tenant_id=s.tenant, rev_no=1, blob_hash=blob_hash, blob_key=key,
                               valid_from=_naive_now(), created_at=_naive_now()))
    await db.commit()
    return document_id, revision_id


async def _new_revision(db: AsyncSession, s: Scope, document_id: UUID, data: bytes, suffix: str = ".csv") -> UUID:
    blob_hash = hashlib.sha256(data).hexdigest()
    key = f"tenants/{s.tenant}/projects/{s.project}/documents/{document_id}/revisions/{blob_hash}{suffix}"
    STORE.blobs[key] = data
    current = await db.scalar(select(func.max(DocumentRevisionORM.rev_no)).where(
        DocumentRevisionORM.document_id == document_id))
    await db.execute(update(DocumentRevisionORM).where(DocumentRevisionORM.document_id == document_id,
                                                       DocumentRevisionORM.valid_to.is_(None))
                     .values(valid_to=_naive_now()))
    revision_id = uuid4()
    db.add(DocumentRevisionORM(revision_id=revision_id, document_id=document_id, project_id=s.project,
                               tenant_id=s.tenant, rev_no=int(current or 0) + 1, blob_hash=blob_hash, blob_key=key,
                               valid_from=_naive_now(), created_at=_naive_now()))
    await db.commit()
    return revision_id


@dataclass(frozen=True)
class Imp:
    """Plain values of a stored import (ORM rows expire on rollback)."""

    id: UUID
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    blob_hash: str
    format: str
    parser_id: str
    parser_version: str
    import_key: str
    snapshot_digest: str
    status: str
    row_count: int
    blocking_count: int


@dataclass(frozen=True)
class Cand:
    change_set_id: UUID
    revision: int
    node_ids_by_source_ref: dict[str, UUID]
    entry_mode: str
    origin: str
    status: str
    base_baseline_id: UUID | None
    created_by: UUID
    created_by_kind: str


async def _import(db: AsyncSession, s: Scope, document_id: UUID, *, revision_id: UUID | None = None,
                  config: dict[str, Any] | None = None, actor: Actor | None = None) -> Imp:
    result = await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=actor or s.author,
                                          document_id=document_id, revision_id=revision_id, parse_config=config)
    r = result.source
    imp = Imp(r.id, r.tenant_id, r.project_id, r.document_id, r.revision_id, r.blob_hash, r.format, r.parser_id,
              r.parser_version, r.import_key, r.snapshot_digest, r.status, r.row_count, r.blocking_count)
    await db.commit()
    return imp


async def _candidate(db: AsyncSession, s: Scope, import_id: UUID, actor: Actor | None = None) -> Cand:
    result = await _svc(db).create_candidate(project_id=s.project, tenant_id=s.tenant, actor=actor or s.author,
                                             import_id=import_id, title="Imported WBS")
    c = result.change_set
    cand = Cand(c.id, result.revision, dict(result.node_ids_by_source_ref), c.entry_mode, c.origin, c.status,
                c.base_baseline_id, c.created_by, c.created_by_kind)
    await db.commit()
    return cand


async def _nodes(db: AsyncSession, change_set_id: UUID) -> list[WBSChangeSetNodeORM]:
    rows = await db.execute(select(WBSChangeSetNodeORM).where(WBSChangeSetNodeORM.change_set_id == change_set_id)
                            .execution_options(populate_existing=True))
    return list(rows.scalars())


async def _count(db: AsyncSession, model: Any, **where: Any) -> int:
    query = select(func.count()).select_from(model)
    for name, value in where.items():
        query = query.where(getattr(model, name) == value)
    return int(await db.scalar(query) or 0)


async def _plant(db: AsyncSession) -> tuple[Scope, UUID, Imp]:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    return s, document_id, await _import(db, s, document_id)


# =========================================================================== B. immutable source
async def test_10_the_import_binds_the_exact_revision_and_blob(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, revision_id = await _wbs_document(db, s, PLANT_CSV)
    source = await _import(db, s, document_id)
    assert (source.tenant_id, source.project_id, source.document_id, source.revision_id) == (
        s.tenant, s.project, document_id, revision_id)
    assert source.blob_hash == hashlib.sha256(PLANT_CSV).hexdigest()
    assert (source.format, source.parser_id, source.parser_version) == ("csv", "wbs-csv", "v1")
    assert source.status == ImportStatus.READY.value and source.row_count == 4
    document = await db.scalar(select(DocumentORM).where(DocumentORM.id == document_id)
                               .execution_options(populate_existing=True))
    assert document is not None and document.upload_status is DocumentStatus.PARSED  # 9: never analysis-pending


async def test_11_blob_revision_mismatch_is_rejected(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, revision_id = await _wbs_document(db, s, PLANT_CSV)
    blob_key = await db.scalar(select(DocumentRevisionORM.blob_key).where(DocumentRevisionORM.revision_id == revision_id))
    assert blob_key is not None
    STORE.blobs[blob_key] = PLANT_CSV + b"9,Tampered,1\n"  # the stored object no longer matches
    with pytest.raises(WBSImportIntegrityError) as caught:
        await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
    assert caught.value.code == "WBS_IMPORT_BLOB_MISMATCH"
    await db.rollback()
    assert await _count(db, WBSImportSourceORM, document_id=document_id) == 0
    STORE.blobs[blob_key] = PLANT_CSV
    # the database refuses an import that names another blob than its revision
    source = await _import(db, s, document_id)
    with pytest.raises(DBAPIError, match="exact immutable blob"):
        await db.execute(text(
            "INSERT INTO wbs_import_sources SELECT gen_random_uuid(), tenant_id, project_id, document_id, revision_id, "
            "repeat('0', 64), format, parser_id, parser_version, parse_config, parse_config_digest, "
            "'sha256:' || repeat('1', 64), snapshot_schema_version, snapshot, snapshot_digest, diagnostics, row_count, "
            "warning_count, blocking_count, status, created_by, created_by_kind, now() FROM wbs_import_sources "
            "WHERE id = :id"), {"id": source.id})
    await db.rollback()


class _TemporaryCopyStore(_Store):
    """Like R2: every download is a fresh temporary copy that the caller owns."""

    download_object_is_temporary = True

    def __init__(self, blobs: dict[str, bytes]) -> None:
        super().__init__()
        self.blobs = blobs
        self.handed_out: list[Path] = []

    async def download_object(self, key: str) -> Path:
        path = self.root / f"{uuid4().hex}.tmp"
        path.write_bytes(self.blobs[key])
        self.handed_out.append(path)
        return path


async def test_11b_temporary_downloads_are_removed_and_persisted_sources_never_are(db: AsyncSession) -> None:
    from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
    from src.documents.adapters.storage.r2_storage_service import R2StorageService
    from src.documents.ports.storage_service import IStorageService

    assert R2StorageService.download_object_is_temporary is True  # a NamedTemporaryFile per download
    assert LocalFileStorageService.download_object_is_temporary is False  # the stored object itself
    assert IStorageService.download_object_is_temporary is False  # unknown adapters: never delete
    s = await _scope(db)
    document_id, revision_id = await _wbs_document(db, s, PLANT_CSV)
    copies = _TemporaryCopyStore(dict(STORE.blobs))
    await WBSImportService(db, storage=copies).create_import(  # type: ignore[arg-type]
        project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
    await WBSImportService(db, storage=copies).create_import(  # type: ignore[arg-type]
        project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)  # idempotent reparse
    await db.commit()
    blob_key = await db.scalar(select(DocumentRevisionORM.blob_key).where(DocumentRevisionORM.revision_id == revision_id))
    assert blob_key is not None
    copies.blobs[blob_key] = PLANT_CSV + b"9,Tampered,1\n"
    with pytest.raises(WBSImportIntegrityError):  # a failed verification cleans up too
        await WBSImportService(db, storage=copies).create_import(  # type: ignore[arg-type]
            project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
    await db.rollback()
    assert len(copies.handed_out) == 3 and not any(path.exists() for path in copies.handed_out)
    # the real local adapter hands out the stored object itself: it must survive the import untouched
    local = LocalFileStorageService(base_dir=Path(tempfile.mkdtemp(prefix="pc2b3-local-")))
    await local.upload_bytes(PLANT_CSV, blob_key)
    stored = await local.download_object(blob_key)
    await WBSImportService(db, storage=local).create_import(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
    await db.commit()
    assert stored.exists() and stored.read_bytes() == PLANT_CSV


async def test_12_13_import_rows_are_insert_only(db: AsyncSession) -> None:
    _, _, source = await _plant(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(update(WBSImportSourceORM).where(WBSImportSourceORM.id == source.id)
                         .values(snapshot_digest="sha256:" + "f" * 64))
    await db.rollback()
    with pytest.raises(DBAPIError, match="provenance history"):
        await db.execute(text("DELETE FROM wbs_import_sources WHERE id = :id"), {"id": source.id})
    await db.rollback()
    assert await _count(db, WBSImportSourceORM, id=source.id) == 1


async def test_14_a_new_revision_is_a_new_import_and_the_old_one_stays(db: AsyncSession) -> None:
    s, document_id, first = await _plant(db)
    candidate = await _candidate(db, s, first.id)
    revision_b = await _new_revision(db, s, document_id, PLANT_CSV + b"1.3,Substation,1\n")
    second = await _import(db, s, document_id)
    assert second.id != first.id and second.revision_id == revision_b and second.import_key != first.import_key
    assert second.row_count == 5 and second.snapshot_digest != first.snapshot_digest
    old = await _svc(db).get_import(project_id=s.project, tenant_id=s.tenant, import_id=first.id)
    assert old.snapshot_digest == first.snapshot_digest  # still auditable, unchanged
    # 33: no automatic refresh or rebase of the existing candidate
    assert len(await _nodes(db, candidate.change_set_id)) == 4
    # an older revision is still importable on purpose (and keeps its own identity)
    again = await _import(db, s, document_id, revision_id=first.revision_id)
    assert again.id == first.id


async def test_15_reparsing_identical_inputs_reuses_and_verifies(db: AsyncSession) -> None:
    s, document_id, first = await _plant(db)
    result = await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                          document_id=document_id, parse_config={"delimiter": None})
    assert result.reused and result.source.id == first.id
    # a parser that produced another digest for the same identity fails closed (nothing overwritten)
    await db.execute(text("ALTER TABLE wbs_import_sources DISABLE TRIGGER trg_wbs_import_sources_guard"))
    await db.execute(update(WBSImportSourceORM).where(WBSImportSourceORM.id == first.id)
                     .values(snapshot_digest="sha256:" + "e" * 64))
    await db.execute(text("ALTER TABLE wbs_import_sources ENABLE TRIGGER trg_wbs_import_sources_guard"))
    await db.commit()
    with pytest.raises(WBSImportIntegrityError) as caught:
        await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
    assert caught.value.code == "WBS_IMPORT_PARSER_NONDETERMINISM"
    await db.rollback()


async def test_16_concurrent_identical_parses_do_not_duplicate(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    factory = async_sessionmaker(db.bind, expire_on_commit=False)

    async def parse() -> UUID:
        async with factory() as session:
            result = await WBSImportService(session, storage=STORE).create_import(  # type: ignore[arg-type]
                project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=document_id)
            await session.commit()
            return result.source.id

    first, second = await asyncio.gather(parse(), parse())
    assert first == second
    assert await _count(db, WBSImportSourceORM, document_id=document_id) == 1


async def test_parse_config_and_format_rules(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    with pytest.raises(WBSImportInvalidError) as caught:
        await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                     document_id=document_id, parse_config={"sheet": "x"})
    assert caught.value.code == "WBS_IMPORT_CONFIG_INVALID"
    await db.rollback()
    contract_id, _ = await _wbs_document(db, s, b"%PDF", ".pdf", document_type=DocumentType.CONTRACT)
    with pytest.raises(WBSImportInvalidError) as caught:
        await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant, actor=s.author, document_id=contract_id)
    assert caught.value.code == "WBS_IMPORT_NOT_A_WBS_SOURCE"
    await db.rollback()


# =========================================================================== D. authority
async def test_32_33_upload_and_parse_create_no_draft_and_write_no_wbs(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    assert await _count(db, WBSChangeSetORM, project_id=s.project) == 0  # 32: an upload creates nothing
    await _import(db, s, document_id)
    assert await _count(db, WBSChangeSetORM, project_id=s.project) == 0  # 33: a parse creates no DRAFT
    assert await _count(db, WBSNodeORM, project_id=s.project) == 0
    assert await _count(db, WBSBaselineORM, project_id=s.project) == 0


async def test_34_35_only_a_human_creates_the_candidate(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    for kind, role in ((ActorKind.AI, None), (ActorKind.SERVICE, None), (ActorKind.HUMAN, "api"),
                       (ActorKind.HUMAN, "viewer")):
        with pytest.raises(WBSImportForbiddenError):
            await _svc(db).create_candidate(project_id=s.project, tenant_id=s.tenant,
                                            actor=Actor(user_id=uuid4(), kind=kind, role=role),
                                            import_id=source.id, title="x")
        await db.rollback()
        with pytest.raises(WBSImportForbiddenError):
            await _svc(db).create_import(project_id=s.project, tenant_id=s.tenant,
                                         actor=Actor(user_id=uuid4(), kind=kind, role=role), document_id=source.document_id)
        await db.rollback()
    assert await _count(db, WBSChangeSetORM, project_id=s.project) == 0
    result = await _candidate(db, s, source.id)  # the explicit human action
    assert (result.entry_mode, result.origin, result.status, result.base_baseline_id) == (
        "IMPORT_REVIEW", "import", "DRAFT", None)
    assert result.created_by == s.author.user_id and result.created_by_kind == "human"


async def test_36_an_approved_baseline_refuses_an_import_candidate(db: AsyncSession) -> None:
    s = await _scope(db)
    baseline_id, _, _ = await _baseline_one(db, s)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    source = await _import(db, s, document_id)  # parsing is still allowed: input only
    with pytest.raises(WBSImportStateError) as caught:
        await _svc(db).create_candidate(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                        import_id=source.id, title="competing")
    assert caught.value.code == "WBS_IMPORT_BASELINE_EXISTS"
    await db.rollback()
    assert await _count(db, WBSChangeSetORM, source_import_id=source.id) == 0
    # and the database refuses an IMPORT_REVIEW draft with a base baseline even outside the service
    with pytest.raises((IntegrityError, DBAPIError)):
        await WBSGovernanceRepository(db).create_change_set(
            project_id=s.project, tenant_id=s.tenant, actor=s.author, title="x",
            entry_mode=EntryMode.IMPORT_REVIEW, origin=ChangeSetOrigin.IMPORT, source_import_id=source.id)
    await db.rollback()
    assert baseline_id is not None


async def test_37_38_39_40_legacy_rows_are_neither_adopted_nor_retired(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 3)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    source = await _import(db, s, document_id)
    result = await _candidate(db, s, source.id)  # LEGACY_UNGOVERNED is allowed for a first baseline
    nodes = await _nodes(db, result.change_set_id)
    assert {n.origin_kind for n in nodes} == {"minted"} and not {n.node_id for n in nodes} & set(legacy)
    retirements = await db.scalar(text("SELECT count(*) FROM wbs_change_set_retirements WHERE change_set_id = :c"),
                                  {"c": result.change_set_id})
    assert retirements == 0
    live = await db.execute(select(WBSNodeORM.id).where(WBSNodeORM.project_id == s.project))
    assert {row.id for row in live} == set(legacy)  # 39: no canonical wbs_nodes write
    assert await _count(db, WBSBaselineORM, project_id=s.project) == 0  # 40: no baseline write


async def test_invalid_import_cannot_become_a_candidate(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, b"code,name,parent_code\n1,A,9\n")
    source = await _import(db, s, document_id)
    assert source.status == "INVALID" and source.blocking_count >= 1
    document = await db.scalar(select(DocumentORM).where(DocumentORM.id == document_id)
                               .execution_options(populate_existing=True))
    assert document is not None and document.upload_status is DocumentStatus.ERROR
    with pytest.raises(WBSImportStateError) as caught:
        await _candidate(db, s, source.id)
    assert caught.value.code == "WBS_IMPORT_INVALID_SOURCE"
    await db.rollback()
    with pytest.raises((IntegrityError, DBAPIError), match="non-INVALID"):
        await db.execute(text(
            "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, "
            "created_by_kind, source_import_id) VALUES (gen_random_uuid(), :t, :p, 'import', 'IMPORT_REVIEW', 'x', "
            ":u, 'human', :i)"), {"t": s.tenant, "p": s.project, "u": s.author.user_id, "i": source.id})
    await db.rollback()


# =========================================================================== E. candidate
async def test_41_42_43_44_45_48_candidate_ids_provenance_and_source_link(db: AsyncSession) -> None:
    s = await _scope(db)
    external = str(uuid4())
    data = json.dumps({"format": "wbs-import/v1", "nodes": [
        {"id": external, "code": "1", "name": "Root", "level": 1},
        {"id": "kid-a", "parent_id": external, "code": "1.1", "name": "A", "level": 2},
        {"id": "kid-b", "parent_id": external, "code": "1.1", "name": "B", "level": 2},
    ]}).encode()
    document_id, revision_id = await _wbs_document(db, s, data, ".json")
    source = await _import(db, s, document_id)
    assert source.status == "READY_WITH_WARNINGS"
    result = await _candidate(db, s, source.id)
    change_set = await db.scalar(select(WBSChangeSetORM).where(WBSChangeSetORM.id == result.change_set_id))
    assert change_set is not None and change_set.source_import_id == source.id  # 48
    nodes = {n.node_id: n for n in await _nodes(db, change_set.id)}
    assert str(UUID(external)) not in {str(i) for i in nodes}  # 42: a source UUID is never a canonical id
    assert all(n.origin_kind == "minted" for n in nodes.values())  # 41
    by_ref = {n.provenance["import"]["source_ref"]: n for n in nodes.values()}
    root, a, b = by_ref["/nodes/0"], by_ref["/nodes/1"], by_ref["/nodes/2"]
    assert a.parent_id == root.node_id and b.parent_id == root.node_id and (a.sort_order, b.sort_order) == (1, 2)
    origin = root.provenance["import"]
    assert origin == {"origin": "import", "import_source_id": str(source.id), "document_id": str(document_id),
                      "revision_id": str(revision_id), "snapshot_digest": source.snapshot_digest,
                      "parser_id": "wbs-json", "parser_version": "v1", "source_ref": "/nodes/0", "raw_code": "1",
                      "external_id": external}  # 43
    assert (a.code, b.code) == (None, None)  # 45: duplicate codes are materialized as NULL
    assert a.provenance["import"]["raw_code"] == "1.1" == b.provenance["import"]["raw_code"]  # 44
    assert "import" not in json.dumps(root.dictionary or {})  # never in the WBS Dictionary
    # the source link is immutable
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(update(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set.id)
                         .values(source_import_id=None))
    await db.rollback()


async def test_46_one_invalid_node_rolls_the_whole_candidate_back(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    governed = WBSGovernedChangeService(db)
    created = await governed.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="t")
    change_set_id, revision = created.id, created.revision
    await db.commit()

    def ok(_minted: Any) -> tuple[AddNode, dict[str, Any]]:
        return AddNode(spec=NodeSpec(name="fine")), {"source_ref": "row:2"}

    def bad(_minted: Any) -> tuple[AddNode, dict[str, Any]]:
        return AddNode(spec=NodeSpec(name="   ")), {"source_ref": "row:3"}  # no name: invalid governed command

    with pytest.raises(WBSChangeSetInvalidError):
        await governed.execute_add_sequence(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant,
                                            actor=s.author, expected_revision=revision, steps=[ok, bad])
    await db.rollback()
    assert await _nodes(db, change_set_id) == []
    assert await db.scalar(select(WBSChangeSetORM.revision).where(WBSChangeSetORM.id == change_set_id)) == 1
    assert source.status == "READY"


async def test_47_human_edits_change_the_candidate_never_the_import(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    civil = result.node_ids_by_source_ref["row:3"]
    await WBSGovernedChangeService(db).execute(
        project_id=s.project, change_set_id=result.change_set_id, tenant_id=s.tenant, actor=s.author,
        expected_revision=result.revision, command=UpdateNode(node_id=civil, changes={"name": "Civil & Structural"}))
    await db.commit()
    stored = await _svc(db).get_import(project_id=s.project, tenant_id=s.tenant, import_id=source.id)
    await db.refresh(stored)
    assert stored.snapshot_digest == source.snapshot_digest
    assert [r["name"] for r in stored.snapshot["rows"]] == ["Plant", "Civil", "Electrical", "Cabling"]


# =========================================================================== F. digest
async def test_50_parser_identity_is_part_of_the_import_key(db: AsyncSession) -> None:
    from src.wbs.imports.contracts import ImportFormat
    from src.wbs.imports.parser import parse_source
    from src.wbs.imports.service import import_key

    base = parse_source(ImportFormat.CSV, PLANT_CSV)
    bumped = type(base)(**{**base.__dict__, "parser_version": "v2"})
    ids = {"tenant_id": uuid4(), "project_id": uuid4(), "document_id": uuid4(), "revision_id": uuid4(),
           "blob_hash": "0" * 64}
    assert import_key(**ids, result=base) != import_key(**ids, result=bumped)
    configured = parse_source(ImportFormat.CSV, PLANT_CSV, {"delimiter": ","})
    assert import_key(**ids, result=base) != import_key(**ids, result=configured)  # 51


async def test_52_import_provenance_does_not_change_the_semantic_tree_digest(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    nodes = await _nodes(db, result.change_set_id)

    def digest(rows: list[WBSChangeSetNodeORM]) -> str:
        return tree_digest(s.project, [DigestNode(node_id=n.node_id, parent_id=n.parent_id, sort_order=n.sort_order,
                                                  code=n.code, name=n.name, decomposition_kind=n.decomposition_kind,
                                                  control_level=n.control_level, dictionary=n.dictionary)
                                       for n in rows])

    before = digest(nodes)
    for node in nodes:  # the same tree with MANUAL provenance
        node.provenance = {"command": "ADD_NODE"}
    await db.commit()
    assert digest(await _nodes(db, result.change_set_id)) == before
    submitted = await _submit(db, s, result.change_set_id)  # the governed submit digest ignores provenance too
    assert submitted.startswith("sha256:")


# =========================================================================== G. tenancy
async def test_53_54_55_57_imports_are_scoped_to_their_tenant_and_project(db: AsyncSession) -> None:
    a, _, source = await _plant(db)
    b = await _scope(db)
    for scope in (b,):
        with pytest.raises(WBSImportNotFoundError):  # 53
            await _svc(db).get_import(project_id=scope.project, tenant_id=scope.tenant, import_id=source.id)
        with pytest.raises(WBSImportNotFoundError):  # 54
            await _svc(db).create_candidate(project_id=scope.project, tenant_id=scope.tenant, actor=scope.author,
                                            import_id=source.id, title="stolen")
        await db.rollback()
    same_tenant_other_project = await db.execute(text(
        "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :t, 'other', :c, 'construction', 'active', 'EUR', now(), now()) RETURNING id"),
        {"t": a.tenant, "c": f"P-{uuid4().hex[:8]}"})
    other_project = same_tenant_other_project.scalar_one()
    await db.commit()
    with pytest.raises(WBSImportNotFoundError):  # 55
        await _svc(db).create_candidate(project_id=other_project, tenant_id=a.tenant, actor=a.author,
                                        import_id=source.id, title="cross project")
    await db.rollback()
    with pytest.raises(WBSImportNotFoundError):  # a document of another tenant is not found either
        await _svc(db).create_import(project_id=b.project, tenant_id=b.tenant, actor=b.author,
                                     document_id=source.document_id)
    await db.rollback()
    # the database refuses a change set linking another project's import (composite FK)
    with pytest.raises((IntegrityError, DBAPIError)):
        await db.execute(text(
            "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, "
            "created_by_kind, source_import_id) VALUES (gen_random_uuid(), :t, :p, 'import', 'IMPORT_REVIEW', 'x', "
            ":u, 'human', :i)"), {"t": a.tenant, "p": other_project, "u": a.author.user_id, "i": source.id})
    await db.rollback()


async def test_56_missing_tenant_context_fails_closed(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    with pytest.raises(ValueError):
        await _svc(db).get_import(project_id=s.project, tenant_id=None, import_id=source.id)  # type: ignore[arg-type]


# =========================================================================== I. comparison
async def test_62_63_64_65_comparison_is_a_pure_read(db: AsyncSession) -> None:
    s, _, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    change_set_id = result.change_set_id
    civil = result.node_ids_by_source_ref["row:3"]
    governed = WBSGovernedChangeService(db)
    revision = result.revision
    revision = (await governed.execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant,
                                       actor=s.author, expected_revision=revision,
                                       command=UpdateNode(node_id=civil, changes={"name": "Civil works"}))).revision
    await governed.execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                           expected_revision=revision, command=AddNode(spec=NodeSpec(name="Commissioning", code="1.9"),
                                                                       parent_id=result.node_ids_by_source_ref["row:2"]))
    await db.commit()
    before = await db.execute(text(
        "SELECT (SELECT count(*) FROM wbs_change_set_nodes), (SELECT count(*) FROM wbs_import_sources), "
        "(SELECT count(*) FROM wbs_intelligence_decisions), (SELECT count(*) FROM wbs_intelligence_runs), "
        "(SELECT revision FROM wbs_change_sets WHERE id = :c)"), {"c": change_set_id})
    snapshot_before = tuple(before.one())
    view = await _svc(db).comparison(project_id=s.project, tenant_id=s.tenant, import_id=source.id,
                                     change_set_id=change_set_id)
    assert [r["name"] for r in view["imported"]] == ["Plant", "Civil", "Electrical", "Cabling"]  # 62
    statuses = {r["source_ref"]: (r["status"], r["changes"]) for r in view["rows"]}
    assert statuses["row:3"] == ("CHANGED", ["name"]) and statuses["row:2"] == ("UNCHANGED", [])  # 63
    assert len(view["added_node_ids"]) == 1
    assert view["proposed"] == {"status": "NOT_AVAILABLE", "reason": "NO_INTELLIGENCE_RUN", "nodes": []}  # 64
    after = await db.execute(text(
        "SELECT (SELECT count(*) FROM wbs_change_set_nodes), (SELECT count(*) FROM wbs_import_sources), "
        "(SELECT count(*) FROM wbs_intelligence_decisions), (SELECT count(*) FROM wbs_intelligence_runs), "
        "(SELECT revision FROM wbs_change_sets WHERE id = :c)"), {"c": change_set_id})
    assert tuple(after.one()) == snapshot_before  # 65: zero writes, no implicit qualification
    assert not db.new and not db.dirty  # nothing staged either


async def test_64b_a_run_without_proposals_keeps_proposed_not_available(db: AsyncSession) -> None:
    from src.wbs.intelligence.application.service import WBSIntelligenceService
    from src.wbs.intelligence.contracts.run import TargetKind

    s, _, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    run = (await WBSIntelligenceService(db).request_deterministic_run(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target_kind=TargetKind.CANDIDATE,
        change_set_id=result.change_set_id)).run
    await db.commit()
    view = await _svc(db).comparison(project_id=s.project, tenant_id=s.tenant, import_id=source.id,
                                     change_set_id=result.change_set_id, intelligence_run_id=run.id)
    assert view["proposed"]["status"] == "NOT_AVAILABLE" and view["proposed"]["reason"] == "NO_PROPOSALS"


# =========================================================================== J. retention
async def test_66_a_source_document_cannot_disappear_under_its_import(db: AsyncSession) -> None:
    s, document_id, source = await _plant(db)
    await _candidate(db, s, source.id)
    with pytest.raises(IntegrityError, match="fk_wbs_import_sources_revision"):
        await db.execute(text("DELETE FROM documents WHERE id = :d"), {"d": document_id})
        await db.flush()
    await db.rollback()
    assert await _count(db, DocumentORM, id=document_id) == 1
    assert await _count(db, WBSImportSourceORM, id=source.id) == 1


async def test_66b_the_delete_use_case_answers_409_and_keeps_the_bytes(db: AsyncSession) -> None:
    from fastapi import HTTPException

    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.delete_document_use_case import DeleteDocumentUseCase

    s, document_id, _ = await _plant(db)

    class _Get:
        async def execute(self, *_args: Any) -> Any:
            return await SqlAlchemyDocumentRepository(session=db).get_by_id(s.tenant, document_id)

    class _Storage:
        deleted: list[str] = []

        async def delete_prefix(self, prefix: str) -> None:
            self.deleted.append(prefix)

        async def delete_file(self, key: str) -> None:
            self.deleted.append(key)

    storage = _Storage()
    use_case = DeleteDocumentUseCase(SqlAlchemyDocumentRepository(session=db), storage, _Get())  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as caught:
        await use_case.execute(document_id, s.author.user_id, s.tenant)
    assert caught.value.status_code == 409 and storage.deleted == []
    await db.rollback()


async def test_67_project_deletion_cascades_without_deadlock(db: AsyncSession) -> None:
    s, document_id, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    await db.execute(text("DELETE FROM projects WHERE id = :p"), {"p": s.project})
    await db.commit()
    assert await _count(db, WBSImportSourceORM, id=source.id) == 0
    assert await _count(db, WBSChangeSetORM, id=result.change_set_id) == 0
    assert await _count(db, DocumentORM, id=document_id) == 0


# =========================================================================== 45. qualification regression
async def test_deterministic_qualification_runs_on_the_imported_draft(db: AsyncSession) -> None:
    from src.wbs.intelligence.application.service import WBSIntelligenceService
    from src.wbs.intelligence.contracts.run import TargetKind

    s, _, source = await _plant(db)
    result = await _candidate(db, s, source.id)
    assert await _count(db, WBSChangeSetORM, source_import_id=source.id) == 1
    run = (await WBSIntelligenceService(db).request_deterministic_run(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target_kind=TargetKind.CANDIDATE,
        change_set_id=result.change_set_id)).run
    await db.commit()
    assert (run.execution_type, run.status, run.model_provenance) == ("DETERMINISTIC", "COMPLETED", None)
    results = {r["dimension"]: r for r in run.qualification["results"]}
    assert results["EVIDENCE_COVERAGE"]["status"] == "NOT_EVALUATED"  # no PASS-by-absence
    assert results["SCHEDULE_MAPPING_COVERAGE"]["status"] != "PASS"  # Schedule evidence unavailable
    assert results["BUDGET_COST_MAPPING_COVERAGE"]["status"] != "PASS"  # no Cost authority from an import
    assert not any(r["status"] == "PASS" and r.get("method") == "AI" for r in results.values())
    # the import itself never started a run: only this explicit request did
    count = await db.scalar(text("SELECT count(*) FROM wbs_intelligence_runs WHERE project_id = :p"), {"p": s.project})
    assert count == 1
