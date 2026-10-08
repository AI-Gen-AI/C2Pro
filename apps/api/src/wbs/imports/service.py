"""WBS import application service (PC-2b.3 #922).

IMMUTABLE SOURCE FILE -> IMMUTABLE IMPORT SNAPSHOT -> explicit HUMAN action -> governed DRAFT
candidate -> (deterministic qualification, human review/edit) -> submit -> human approval.

* ``create_import`` parses one exact document revision (bytes verified against the revision's
  blob hash) with one parser identity and one configuration, and stores the result once per
  import key. Re-parsing identical inputs reuses the stored import after VERIFYING it reproduces
  the same snapshot digest; a different digest fails closed as parser nondeterminism. Parsing never
  creates a DRAFT and never touches canonical WBS.
* ``create_candidate`` is the only way from an import to a DRAFT: an explicit human action that
  creates an IMPORT_REVIEW change set linked to the import and populates it ONLY through the PC-2a
  governed ADD_NODE commands (server-minted ids, provenance outside every digest), all or nothing.
  v1: an import establishes Baseline #1 -- with an approved baseline it is refused.
* ``comparison`` is a pure read: IMPORTED (the frozen snapshot) vs CANDIDATE (the current human-edited
  DRAFT); PROPOSED is NOT_AVAILABLE unless an intelligence run with proposals is named, in which case
  it is DERIVED through the PC-2b.2 preview (never persisted).

No AI, no retrieval, no model call.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import C2ProException
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.documents.ports.storage_service import IStorageService
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.wbs.adapters.persistence.governance_models import WBSChangeSetNodeORM, WBSChangeSetORM
from src.wbs.adapters.persistence.governance_repository import Actor, WBSGovernanceRepository
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM
from src.wbs.application.governed_change_service import AddNode, NodeSpec, WBSGovernedChangeService
from src.wbs.domain.digest import canonical_json
from src.wbs.domain.governance import AuthorityState, ChangeSetOrigin, EntryMode, can_author
from src.wbs.imports.config import ImportConfigError
from src.wbs.imports.contracts import (
    FORMAT_BY_EXTENSION,
    SNAPSHOT_SCHEMA_VERSION,
    ImportStatus,
    ParseResult,
)
from src.wbs.imports.parser import parse_source

IMPORT_PROVENANCE_ORIGIN = "import"


# ============================================================================ errors
class WBSImportForbiddenError(C2ProException):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="WBS_IMPORT_FORBIDDEN", status_code=403)


class WBSImportNotFoundError(C2ProException):
    def __init__(self, what: str, identifier: UUID) -> None:
        super().__init__(message=f"{what} not found", code="WBS_IMPORT_NOT_FOUND", status_code=404,
                         details={"id": str(identifier)})


class WBSImportInvalidError(C2ProException):
    def __init__(self, message: str, code: str = "WBS_IMPORT_INVALID", **details: Any) -> None:
        super().__init__(message=message, code=code, status_code=422, details=details)


class WBSImportStateError(C2ProException):
    def __init__(self, message: str, code: str = "WBS_IMPORT_INVALID_STATE", **details: Any) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class WBSImportIntegrityError(C2ProException):
    """The immutable source or the deterministic parser could not be trusted: fail closed."""

    def __init__(self, message: str, code: str, **details: Any) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


# ============================================================================ results
@dataclass(frozen=True)
class ImportResult:
    source: WBSImportSourceORM
    reused: bool


@dataclass(frozen=True)
class CandidateResult:
    change_set: WBSChangeSetORM
    revision: int
    node_ids_by_source_ref: dict[str, UUID]


def import_key(*, tenant_id: UUID, project_id: UUID, document_id: UUID, revision_id: UUID, blob_hash: str,
               result: ParseResult) -> str:
    """Deterministic identity of one parse: revision, exact blob, parser identity and configuration."""
    material = {
        "tenant_id": str(tenant_id), "project_id": str(project_id), "document_id": str(document_id),
        "revision_id": str(revision_id), "blob_hash": blob_hash, "format": result.format.value,
        "parser_id": result.parser_id, "parser_version": result.parser_version,
        "parse_config_digest": result.parse_config_digest,
    }
    return "sha256:" + hashlib.sha256(canonical_json(material)).hexdigest()


def _naive_utc_now() -> datetime:
    """``documents.parsed_at`` is a naive UTC timestamp."""
    return datetime.now(UTC).replace(tzinfo=None)


class WBSImportService:
    def __init__(self, session: AsyncSession, storage: IStorageService | None = None) -> None:
        self.session = session
        self._storage = storage

    @property
    def storage(self) -> IStorageService:
        if self._storage is None:
            from src.documents.adapters.storage.factory import build_storage_service

            self._storage = build_storage_service()
        return self._storage

    # ------------------------------------------------------------------ scoping
    async def _project(self, project_id: UUID, tenant_id: UUID, *, lock: bool = False) -> None:
        query = select(ProjectORM.id).where(ProjectORM.id == project_id, ProjectORM.tenant_id == tenant_id)
        if lock:
            query = query.with_for_update()
        if await self.session.scalar(query) is None:
            raise WBSImportNotFoundError("project", project_id)

    async def get_import(self, *, project_id: UUID, tenant_id: UUID, import_id: UUID) -> WBSImportSourceORM:
        tenant_id = require_tenant_id(tenant_id)
        found = await self.session.scalar(select(WBSImportSourceORM).where(
            WBSImportSourceORM.id == import_id, WBSImportSourceORM.tenant_id == tenant_id,
            WBSImportSourceORM.project_id == project_id))
        if found is None:
            raise WBSImportNotFoundError("WBS import", import_id)
        return found

    async def _read_revision_bytes(self, revision: DocumentRevisionORM) -> bytes:
        path: Path = await self.storage.download_object(revision.blob_key)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != revision.blob_hash:
            raise WBSImportIntegrityError("the stored bytes do not match the immutable revision",
                                          code="WBS_IMPORT_BLOB_MISMATCH", revision_id=str(revision.revision_id))
        return data

    # ------------------------------------------------------------------ parse
    async def create_import(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        document_id: UUID,
        revision_id: UUID | None = None,
        parse_config: Mapping[str, Any] | None = None,
    ) -> ImportResult:
        tenant_id = require_tenant_id(tenant_id)
        if not can_author(actor.kind, actor.role):
            raise WBSImportForbiddenError("only a human user or admin can import a WBS source")
        await self._project(project_id, tenant_id)
        document = await self.session.scalar(select(DocumentORM).where(
            DocumentORM.id == document_id, DocumentORM.tenant_id == tenant_id, DocumentORM.project_id == project_id))
        if document is None:
            raise WBSImportNotFoundError("document", document_id)
        if document.document_type is not DocumentType.WBS:
            raise WBSImportInvalidError("only a document of type 'wbs' is a WBS import source",
                                        code="WBS_IMPORT_NOT_A_WBS_SOURCE")
        revisions = select(DocumentRevisionORM).where(
            DocumentRevisionORM.document_id == document_id, DocumentRevisionORM.tenant_id == tenant_id,
            DocumentRevisionORM.project_id == project_id)
        current = await self.session.scalar(
            revisions.where(DocumentRevisionORM.valid_to.is_(None)).order_by(DocumentRevisionORM.rev_no.desc()).limit(1))
        revision = current if revision_id is None else await self.session.scalar(
            revisions.where(DocumentRevisionORM.revision_id == revision_id))
        if revision is None:
            raise WBSImportNotFoundError("document revision", revision_id or document_id)
        fmt = FORMAT_BY_EXTENSION.get(Path(revision.blob_key).suffix.lower())
        if fmt is None:
            raise WBSImportInvalidError("the revision is not a .xlsx, .csv or .json WBS source",
                                        code="WBS_IMPORT_UNSUPPORTED_FORMAT")
        data = await self._read_revision_bytes(revision)
        try:
            result = parse_source(fmt, data, parse_config)
        except ImportConfigError as exc:
            raise WBSImportInvalidError(str(exc), code="WBS_IMPORT_CONFIG_INVALID") from exc
        key = import_key(tenant_id=tenant_id, project_id=project_id, document_id=document_id,
                         revision_id=revision.revision_id, blob_hash=revision.blob_hash, result=result)
        status = result.status
        inserted = await self.session.scalar(
            pg_insert(WBSImportSourceORM).values(
                id=uuid4(), tenant_id=tenant_id, project_id=project_id, document_id=document_id,
                revision_id=revision.revision_id, blob_hash=revision.blob_hash, format=result.format.value,
                parser_id=result.parser_id, parser_version=result.parser_version, parse_config=result.parse_config,
                parse_config_digest=result.parse_config_digest, import_key=key,
                snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION, snapshot=result.snapshot,
                snapshot_digest=result.snapshot_digest, diagnostics=[d.as_json() for d in result.diagnostics],
                row_count=len(result.rows), warning_count=result.warning_count,
                blocking_count=result.blocking_count, status=status.value, created_by=actor.user_id,
                created_by_kind=actor.kind.value,
            ).on_conflict_do_nothing(constraint="uq_wbs_import_sources_import_key").returning(WBSImportSourceORM.id)
        )
        stored = await self.session.scalar(
            select(WBSImportSourceORM)
            .where(WBSImportSourceORM.tenant_id == tenant_id, WBSImportSourceORM.import_key == key)
            .execution_options(populate_existing=True))
        if stored is None:  # pragma: no cover - the conflicting row is visible to the same tenant
            raise WBSImportIntegrityError("the import could not be stored", code="WBS_IMPORT_NOT_STORED")
        if stored.snapshot_digest != result.snapshot_digest:
            raise WBSImportIntegrityError(
                "re-parsing the same revision with the same parser and configuration produced a different snapshot",
                code="WBS_IMPORT_PARSER_NONDETERMINISM", import_id=str(stored.id),
                stored_digest=stored.snapshot_digest, recomputed_digest=result.snapshot_digest)
        if inserted is not None and current is not None and revision.revision_id == current.revision_id:
            await self._mark_document_parsed(document, status)
        return ImportResult(source=stored, reused=inserted is None)

    async def _mark_document_parsed(self, document: DocumentORM, status: ImportStatus) -> None:
        """The deterministic WBS parse is the terminal state of a WBS source: never analysis-pending."""
        values: dict[str, Any] = (
            {"upload_status": DocumentStatus.ERROR, "parsing_error": "WBS import has blocking diagnostics"}
            if status is ImportStatus.INVALID
            else {"upload_status": DocumentStatus.PARSED, "parsing_error": None, "parsed_at": _naive_utc_now()}
        )
        await self.session.execute(update(DocumentORM).where(
            DocumentORM.id == document.id, DocumentORM.tenant_id == document.tenant_id).values(**values))

    # ------------------------------------------------------------------ candidate (explicit human action)
    async def create_candidate(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        import_id: UUID,
        title: str,
        description: str | None = None,
    ) -> CandidateResult:
        tenant_id = require_tenant_id(tenant_id)
        if not can_author(actor.kind, actor.role):
            raise WBSImportForbiddenError("only a human user or admin can create a candidate from a WBS import")
        await self._project(project_id, tenant_id, lock=True)  # ordered against a concurrent approval
        source = await self.get_import(project_id=project_id, tenant_id=tenant_id, import_id=import_id)
        if source.status == ImportStatus.INVALID.value:
            raise WBSImportStateError("an INVALID import has blocking diagnostics: no candidate can be created",
                                      code="WBS_IMPORT_INVALID_SOURCE", import_id=str(import_id))
        authority = await WBSGovernanceRepository(self.session).authority(project_id, tenant_id)
        if authority.state is AuthorityState.APPROVED_BASELINE:
            raise WBSImportStateError(
                "the project already has an approved WBS baseline: change it through CHANGE_BASELINE or the "
                "Reviewer/Optimizer flow, never through a competing import",
                code="WBS_IMPORT_BASELINE_EXISTS", baseline_id=str(authority.baseline_id))
        governed = WBSGovernedChangeService(self.session)
        change_set = await governed.create_change_set(
            project_id=project_id, tenant_id=tenant_id, actor=actor, title=title, description=description,
            entry_mode=EntryMode.IMPORT_REVIEW, origin=ChangeSetOrigin.IMPORT, source_import_id=source.id,
        )
        rows = _topological(source.snapshot.get("rows", []))
        index = {row["source_ref"]: position for position, row in enumerate(rows)}
        base_provenance = {
            "origin": IMPORT_PROVENANCE_ORIGIN, "import_source_id": str(source.id),
            "document_id": str(source.document_id), "revision_id": str(source.revision_id),
            "snapshot_digest": source.snapshot_digest, "parser_id": source.parser_id,
            "parser_version": source.parser_version,
        }

        def step(row: Mapping[str, Any]) -> Any:
            def build(minted: Sequence[UUID]) -> tuple[AddNode, Mapping[str, Any]]:
                parent_ref = row.get("parent_source_ref")
                spec = NodeSpec(name=row["name"], code=row.get("normalized_code"),
                                control_level=row.get("control_level") or "none",
                                decomposition_kind=row.get("decomposition_kind"), dictionary=row.get("dictionary"))
                parent_id = None if parent_ref is None else minted[index[parent_ref]]
                provenance = {**base_provenance, "source_ref": row["source_ref"], "raw_code": row.get("raw_code"),
                              "external_id": row.get("external_id")}
                return AddNode(spec=spec, parent_id=parent_id), provenance
            return build

        result = await governed.execute_add_sequence(
            project_id=project_id, change_set_id=change_set.id, tenant_id=tenant_id, actor=actor,
            expected_revision=change_set.revision, steps=[step(row) for row in rows],
        )
        return CandidateResult(change_set=change_set, revision=result.revision,
                               node_ids_by_source_ref={row["source_ref"]: node_id
                                                       for row, node_id in zip(rows, result.node_ids, strict=True)})

    # ------------------------------------------------------------------ comparison (pure read)
    async def comparison(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        import_id: UUID,
        change_set_id: UUID,
        intelligence_run_id: UUID | None = None,
    ) -> dict[str, Any]:
        tenant_id = require_tenant_id(tenant_id)
        source = await self.get_import(project_id=project_id, tenant_id=tenant_id, import_id=import_id)
        change_set = await self.session.scalar(select(WBSChangeSetORM).where(
            WBSChangeSetORM.id == change_set_id, WBSChangeSetORM.tenant_id == tenant_id,
            WBSChangeSetORM.project_id == project_id))
        if change_set is None:
            raise WBSImportNotFoundError("WBS change set", change_set_id)
        if change_set.source_import_id != source.id:
            raise WBSImportStateError("the change set was not created from this import",
                                      code="WBS_IMPORT_CHANGE_SET_MISMATCH")
        nodes = (await self.session.execute(select(WBSChangeSetNodeORM).where(
            WBSChangeSetNodeORM.change_set_id == change_set.id))).scalars().all()
        imported_rows = list(source.snapshot.get("rows", []))
        by_ref: dict[str, WBSChangeSetNodeORM] = {}
        for node in nodes:
            origin = (node.provenance or {}).get("import") or {}
            if origin.get("import_source_id") == str(source.id) and origin.get("source_ref"):
                by_ref[origin["source_ref"]] = node
        rows: list[dict[str, Any]] = []
        for row in imported_rows:
            matched = by_ref.get(row["source_ref"])
            if matched is None:
                rows.append({"source_ref": row["source_ref"], "status": "REMOVED", "node_id": None, "changes": []})
                continue
            parent_ref = row.get("parent_source_ref")
            expected_parent = None if parent_ref is None else getattr(by_ref.get(parent_ref), "node_id", "missing")
            changes = [name for name, differs in (
                ("name", matched.name != row["name"]), ("code", matched.code != row.get("normalized_code")),
                ("parent", matched.parent_id != expected_parent)) if differs]
            rows.append({"source_ref": row["source_ref"], "status": "CHANGED" if changes else "UNCHANGED",
                         "node_id": str(matched.node_id), "changes": changes})
        imported_node_ids = {node.node_id for node in by_ref.values()}
        candidate = [
            {"node_id": str(n.node_id), "parent_id": None if n.parent_id is None else str(n.parent_id),
             "sort_order": n.sort_order, "code": n.code, "name": n.name,
             "source_ref": ((n.provenance or {}).get("import") or {}).get("source_ref")
             if n.node_id in imported_node_ids else None}
            for n in sorted(nodes, key=lambda n: (str(n.parent_id or ""), n.sort_order, str(n.node_id)))
        ]
        return {
            "import_id": str(source.id), "change_set_id": str(change_set.id),
            "change_set_revision": change_set.revision, "snapshot_digest": source.snapshot_digest,
            "imported": [{"source_ref": r["source_ref"], "parent_source_ref": r.get("parent_source_ref"),
                          "code": r.get("normalized_code"), "raw_code": r.get("raw_code"), "name": r["name"]}
                         for r in imported_rows],
            "candidate": candidate,
            "proposed": await self._proposed(project_id, tenant_id, change_set.id, intelligence_run_id),
            "rows": rows,
            "added_node_ids": sorted(str(n.node_id) for n in nodes if n.node_id not in imported_node_ids),
        }

    async def _proposed(self, project_id: UUID, tenant_id: UUID, change_set_id: UUID,
                        run_id: UUID | None) -> dict[str, Any]:
        """PROPOSED is DERIVED through the PC-2b.2 preview (zero writes) -- never a stored tree."""
        if run_id is None:
            return {"status": "NOT_AVAILABLE", "reason": "NO_INTELLIGENCE_RUN", "nodes": []}
        from src.wbs.intelligence.application.service import (
            Decision,
            DecisionInput,
            ItemKind,
            WBSIntelligenceService,
        )

        intelligence = WBSIntelligenceService(self.session)
        run = await intelligence.run(run_id, project_id, tenant_id)
        views = await intelligence.items(run)
        selections = [DecisionInput(item_id=v.item.id, decision=Decision.APPLY_AS_PROPOSED)
                      for v in views if v.item.kind == ItemKind.PROPOSAL.value and v.decision is None]
        if not selections:
            return {"status": "NOT_AVAILABLE", "reason": "NO_PROPOSALS", "nodes": []}
        preview = await intelligence.preview(project_id=project_id, run_id=run_id, tenant_id=tenant_id,
                                             change_set_id=change_set_id, selections=selections)
        if not preview.applicable:
            return {"status": "NOT_AVAILABLE", "reason": "PREVIEW_REFUSED", "reasons": list(preview.reasons),
                    "nodes": []}
        return {"status": "DERIVED", "reason": None, "nodes": [
            {"key": n.key, "parent": n.parent, "sort_order": n.sort_order, "code": n.code, "name": n.name}
            for n in preview.resulting_nodes]}


def _topological(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Parents before children; siblings in source order (an import's tree is already acyclic)."""
    children: dict[str | None, list[Mapping[str, Any]]] = {}
    for row in sorted(rows, key=lambda r: int(r["source_ordinal"])):
        children.setdefault(row.get("parent_source_ref"), []).append(row)
    ordered: list[Mapping[str, Any]] = []
    queue = list(children.get(None, []))
    while queue:
        row = queue.pop(0)
        ordered.append(row)
        queue.extend(children.get(row["source_ref"], []))
    if len(ordered) != len(rows):
        raise WBSImportStateError("the import snapshot is not a single acyclic tree", code="WBS_IMPORT_INVALID_SOURCE")
    return ordered


__all__ = [
    "IMPORT_PROVENANCE_ORIGIN",
    "CandidateResult",
    "ImportResult",
    "WBSImportForbiddenError",
    "WBSImportIntegrityError",
    "WBSImportInvalidError",
    "WBSImportNotFoundError",
    "WBSImportService",
    "WBSImportStateError",
    "import_key",
]
