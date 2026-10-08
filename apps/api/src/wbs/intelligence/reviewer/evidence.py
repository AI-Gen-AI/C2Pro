"""Evidence inventory, manifest-scoped retrieval and excerpt preparation of the WBS Reviewer.

Every read binds ``tenant_id`` AND ``project_id`` in the SQL itself (the application role bypasses
RLS; RLS is the second wall) and only selects the exact current revisions admitted to the run:

* inventory -- each project document's current revision (the C3a trusted-current rule over #714
  ``document_artifacts``) is classified: a TRUSTED revision is ``TRUSTED_PROJECT_EVIDENCE`` (a
  schedule or budget only ever ``ADVISORY_EVIDENCE``); an untrusted revision enters only when the
  human explicitly includes it, as ``PROPOSED_EVIDENCE``; a WBS source is never evidence. A requested
  document or revision outside this set is refused before any model call;
* retrieval -- ``ManifestScopedChunkReader`` reads ``document_chunks`` stamped with an admitted
  (document, revision) pair only, matched as exact pairs and bounded (per document and in total, in
  a deterministic order) inside the SQL itself. No embedding, no similarity search, no generic
  retrieval port and no fallback to any wider collection; a missing scope fails closed;
* excerpts -- the canonical locator (document, revision, blob hash and, only when the chunk carries
  exact original coordinates, page / offsets) is captured from the ORIGINAL chunk BEFORE
  anonymisation. The model sees only the anonymised text; its length never becomes an offset.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import C2ProException
from src.evidence.domain.models import LocatorQuality
from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral
from src.wbs.intelligence.contracts.evidence import (
    MAX_EXCERPT_CHARS,
    CanonicalSourceRef,
    EvidenceManifest,
    InputClass,
    ManifestItem,
    ModelVisibleExcerpt,
)
from src.wbs.intelligence.contracts.run import RunScope
from src.wbs.intelligence.reviewer.limits import ReviewLimits
from src.wbs.intelligence.reviewer.privacy import (
    ANONYMIZER_TRANSFORM,
    Anonymizer,
    default_anonymizer,
)

SCOPE_DOCUMENT_TYPES: Final = frozenset({"contract", "specification", "technical_spec"})
ADVISORY_DOCUMENT_TYPES: Final = frozenset({"schedule", "budget"})
_CLASS_PRIORITY: Final = {InputClass.TRUSTED_PROJECT_EVIDENCE: 0, InputClass.ADVISORY_EVIDENCE: 1,
                          InputClass.PROPOSED_EVIDENCE: 2}
_MAX_INT_DIGITS: Final = 18  # always within PostgreSQL bigint and Python's int-from-str limit


class ReviewerScopeError(C2ProException):
    """A requested document or revision is not admissible evidence of this tenant's project."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message=message, code="WBS_REVIEWER_SCOPE_DENIED", status_code=403, details=details)


@dataclass(frozen=True)
class EvidenceRequest:
    """The human's evidence scope for one review (all optional)."""

    include_document_ids: tuple[UUID, ...] = ()  # narrow to these project documents (empty = all eligible)
    include_proposed_revision_ids: tuple[UUID, ...] = ()  # untrusted current revisions the human includes
    user_context: str | None = None  # bounded free text; data, recorded


@dataclass(frozen=True)
class EvidenceSource:
    document_id: UUID
    revision_id: UUID
    blob_hash: str
    document_type: str
    input_class: InputClass


@dataclass(frozen=True)
class EvidenceInventory:
    sources: tuple[EvidenceSource, ...]
    has_trusted_contract: bool
    has_trusted_scope_evidence: bool


def _inventory_sql() -> str:
    return f"""
        SELECT d.id AS document_id, d.document_type::text AS document_type, cur.revision_id, cur.trusted,
               r.blob_hash
          FROM public.documents d
         CROSS JOIN LATERAL {current_revision_lateral('d.id', 'd.tenant_id')} AS cur
          LEFT JOIN public.document_revisions r
                 ON r.revision_id = cur.revision_id AND r.document_id = d.id
                AND r.tenant_id = d.tenant_id AND r.project_id = d.project_id
         WHERE d.tenant_id = CAST(:tenant AS uuid) AND d.project_id = CAST(:project AS uuid)
         ORDER BY d.id
    """


async def inventory_evidence(session: AsyncSession, *, scope: RunScope, request: EvidenceRequest) -> EvidenceInventory:
    rows = (await session.execute(text(_inventory_sql()), {"tenant": str(scope.tenant_id),
                                                          "project": str(scope.project_id)})).mappings().all()
    documents = {UUID(str(row["document_id"])): row for row in rows}
    wanted = set(request.include_document_ids)
    unknown = [str(d) for d in wanted if d not in documents or documents[d]["document_type"] == "wbs"]
    if unknown:
        raise ReviewerScopeError("a requested document is not evidence of this project", document_ids=unknown)
    current = {UUID(str(row["revision_id"])): row for row in rows if row["revision_id"] is not None}
    proposed = set(request.include_proposed_revision_ids)
    for revision_id in proposed:
        row = current.get(revision_id)
        if row is None or row["document_type"] == "wbs":
            raise ReviewerScopeError("a requested revision is not the current revision of a project document",
                                     revision_id=str(revision_id))
        if row["trusted"]:
            raise ReviewerScopeError("a requested revision is TRUSTED, not PROPOSED evidence",
                                     revision_id=str(revision_id))
    sources = []
    for document_id, row in documents.items():
        if row["document_type"] == "wbs" or row["revision_id"] is None or row["blob_hash"] is None:
            continue  # a WBS source is never evidence; an unresolved document is out of scope (fail closed)
        if wanted and document_id not in wanted:
            continue
        revision_id = UUID(str(row["revision_id"]))
        if row["trusted"]:
            cls = (InputClass.ADVISORY_EVIDENCE if row["document_type"] in ADVISORY_DOCUMENT_TYPES
                   else InputClass.TRUSTED_PROJECT_EVIDENCE)
        elif revision_id in proposed:
            cls = InputClass.PROPOSED_EVIDENCE
        else:
            continue  # untrusted evidence enters only when a human includes it
        sources.append(EvidenceSource(document_id=document_id, revision_id=revision_id, blob_hash=str(row["blob_hash"]),
                                      document_type=str(row["document_type"]), input_class=cls))
    trusted_types = {s.document_type for s in sources if s.input_class is InputClass.TRUSTED_PROJECT_EVIDENCE}
    return EvidenceInventory(sources=tuple(sources), has_trusted_contract="contract" in trusted_types,
                             has_trusted_scope_evidence=bool(trusted_types & SCOPE_DOCUMENT_TYPES))


def prioritised(sources: Iterable[EvidenceSource]) -> list[EvidenceSource]:
    """Deterministic retrieval priority: trusted, then advisory, then proposed evidence."""
    return sorted(sources, key=lambda s: (_CLASS_PRIORITY[s.input_class], str(s.document_id)))


# ============================================================================ retrieval
@dataclass(frozen=True)
class ScopedChunk:
    chunk_id: UUID
    document_id: UUID
    revision_id: UUID
    content: str
    page: int | None
    char_start: int | None
    char_end: int | None


def _int(value: Any) -> int | None:
    """A non-negative, bounded integer from chunk metadata; anything else is unusable (None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value < 10 ** _MAX_INT_DIGITS else None
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= _MAX_INT_DIGITS:
        return int(value)
    return None


# Exact (document, revision) pairs, bounded per document and in total inside the database. The
# order is deterministic: chunk_index (only a well-formed, bigint-safe index; NULLS LAST), creation
# time, id within a document; documents take turns in the caller's priority order.
_CHUNKS_SQL: Final = f"""
    WITH allowed AS (
        SELECT a.document_id, a.revision_id, a.position
          FROM unnest(CAST(:documents AS uuid[]), CAST(:revisions AS text[])) WITH ORDINALITY
               AS a(document_id, revision_id, position)
    ), ranked AS (
        SELECT c.id, c.document_id, c.content, c.metadata, a.position,
               row_number() OVER (
                   PARTITION BY c.document_id
                   ORDER BY CASE WHEN (c.metadata ->> 'chunk_index') ~ '^[0-9]{{1,{_MAX_INT_DIGITS}}}$'
                                 THEN CAST(c.metadata ->> 'chunk_index' AS bigint) END NULLS LAST,
                            c.created_at, c.id) AS rank
          FROM public.document_chunks c
          JOIN allowed a ON a.document_id = c.document_id
                        AND a.revision_id = (c.metadata ->> 'revision_id')
         WHERE c.tenant_id = CAST(:tenant AS uuid)
           AND c.project_id = CAST(:project AS uuid)
    )
    SELECT id, document_id, content, metadata
      FROM ranked
     WHERE rank <= :per_document
     ORDER BY rank, position
     LIMIT :total
"""


class ManifestScopedChunkReader:
    """Reads only chunks of admitted (document, revision) pairs of ONE tenant's project."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def read(self, *, tenant_id: UUID, project_id: UUID, allowed: Sequence[tuple[UUID, UUID]],
                   per_document: int = 8, total: int = 40) -> list[ScopedChunk]:
        """At most ``per_document`` chunks per document and ``total`` overall, in ``allowed`` priority."""
        if tenant_id is None or project_id is None:
            raise ValueError("chunk retrieval requires tenant_id and project_id (no global collection)")
        if per_document < 1 or total < 1:
            raise ValueError("chunk retrieval is bounded: per_document and total are positive")
        pairs = list(dict.fromkeys((str(document_id), str(revision_id)) for document_id, revision_id in allowed))
        if not pairs:
            return []
        rows = (await self.session.execute(text(_CHUNKS_SQL), {
            "tenant": str(tenant_id), "project": str(project_id), "documents": [d for d, _ in pairs],
            "revisions": [r for _, r in pairs], "per_document": per_document, "total": total})).all()
        admitted = set(pairs)
        chunks: list[ScopedChunk] = []
        for chunk_id, document_id, content, metadata in rows:
            meta = metadata if isinstance(metadata, Mapping) else {}
            pair = (str(document_id), str(meta.get("revision_id")))
            if pair not in admitted:  # pragma: no cover - the SQL already matched the exact pair
                continue
            start, end = _int(meta.get("char_start")), _int(meta.get("char_end"))
            if start is None or end is None or end < start:
                start = end = None
            page = _int(meta.get("page"))
            chunks.append(ScopedChunk(chunk_id=UUID(str(chunk_id)), document_id=UUID(pair[0]),
                                      revision_id=UUID(pair[1]), content=str(content),
                                      page=page if page is not None and page >= 1 else None,
                                      char_start=start, char_end=end))
        return chunks


# ============================================================================ excerpts / manifest
def _canonical(source: EvidenceSource, chunk: ScopedChunk, original: str) -> CanonicalSourceRef:
    """The original-text locator; offsets only when the chunk carries exact original coordinates."""
    exact = (chunk.char_start is not None and chunk.char_end is not None
             and chunk.char_end - chunk.char_start == len(chunk.content))
    start = chunk.char_start if exact else None
    end = (chunk.char_start + len(original)) if exact and chunk.char_start is not None else None
    quality = (LocatorQuality.EXACT if exact and chunk.page is not None
               else LocatorQuality.APPROXIMATE if chunk.page is not None else LocatorQuality.MISSING)
    return CanonicalSourceRef(document_id=source.document_id, revision_id=source.revision_id,
                              blob_hash=source.blob_hash, page=chunk.page, char_start=start, char_end=end,
                              locator_quality=quality)


def _visible(original: str, anonymize: Anonymizer) -> ModelVisibleExcerpt | None:
    sanitised = anonymize(original)[:MAX_EXCERPT_CHARS].strip()
    return ModelVisibleExcerpt.of(sanitised, transform=ANONYMIZER_TRANSFORM) if sanitised else None


@dataclass(frozen=True)
class ImportStructure:
    """The immutable import under an IMPORT_REVIEW candidate: the structure under review (not proof)."""

    document_id: UUID
    revision_id: UUID
    blob_hash: str
    outline: str


def build_manifest(
    *,
    scope: RunScope,
    inventory: EvidenceInventory,
    chunks: Sequence[ScopedChunk],
    anonymize: Anonymizer,
    limits: ReviewLimits,
    import_structure: ImportStructure | None = None,
    user_context: str | None = None,
) -> EvidenceManifest:
    by_pair = {(s.document_id, s.revision_id): s for s in inventory.sources}
    ordered = sorted((c for c in chunks if (c.document_id, c.revision_id) in by_pair),
                     key=lambda c: (_CLASS_PRIORITY[by_pair[(c.document_id, c.revision_id)].input_class],
                                    str(c.document_id)))
    items: list[ManifestItem] = []
    for chunk in ordered[:limits.max_excerpts]:
        source = by_pair[(chunk.document_id, chunk.revision_id)]
        original = chunk.content[:limits.max_excerpt_chars]
        canonical = _canonical(source, chunk, original)  # captured BEFORE anonymisation
        visible = _visible(original, anonymize)
        if visible is None:
            continue
        items.append(ManifestItem(excerpt_id=f"E{len(items) + 1:03d}", input_class=source.input_class,
                                  canonical_source=canonical, model_visible=visible))
    if import_structure is not None:
        visible = _visible(import_structure.outline[:limits.max_excerpt_chars], anonymize)
        if visible is not None:
            items.append(ManifestItem(
                excerpt_id="IMP001", input_class=InputClass.HUMAN_PROVIDED_IMPORT, model_visible=visible,
                canonical_source=CanonicalSourceRef(document_id=import_structure.document_id,
                                                    revision_id=import_structure.revision_id,
                                                    blob_hash=import_structure.blob_hash, section="imported WBS rows",
                                                    locator_quality=LocatorQuality.APPROXIMATE)))
    if user_context and user_context.strip():
        visible = _visible(user_context.strip()[:limits.max_user_context_chars], anonymize)
        if visible is not None:
            items.append(ManifestItem(excerpt_id="U001", input_class=InputClass.USER_CONTEXT, canonical_source=None,
                                      model_visible=visible))
    return EvidenceManifest(tenant_id=scope.tenant_id, project_id=scope.project_id, items=tuple(items))


__all__ = [
    "ADVISORY_DOCUMENT_TYPES",
    "ANONYMIZER_TRANSFORM",
    "SCOPE_DOCUMENT_TYPES",
    "EvidenceInventory",
    "EvidenceRequest",
    "EvidenceSource",
    "ImportStructure",
    "ManifestScopedChunkReader",
    "ReviewerScopeError",
    "ScopedChunk",
    "Anonymizer",
    "build_manifest",
    "default_anonymizer",
    "inventory_evidence",
    "prioritised",
]
