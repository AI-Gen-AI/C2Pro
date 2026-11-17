"""Read-only project source manifest backed by real document revisions.

Do not invent one document revision for a multivertical project. Retrieve
every revision from the tenant-scoped PostgreSQL lineage, validate current
source/blob integrity, and bind a single-source Coherence call to the exact
revision that supplied that clause. Aggregate/cross-document clauses are
not supported by the single-source CoherenceCallIdentity port and must
fail closed until a separate project-level snapshot contract is designed.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.ai.coherence_governed_wrapper import (
    CoherenceCallIdentity,
    CoherenceEscrowIdentityError,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class CoherenceRevisionRef:
    document_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        if type(self.document_id) is not UUID or type(self.revision_id) is not UUID:
            raise CoherenceEscrowIdentityError("revision references require real UUIDs")


@dataclass(frozen=True, slots=True)
class CoherenceManifestMember:
    document_id: UUID
    revision_id: UUID
    blob_sha256: str


@dataclass(frozen=True, slots=True)
class CoherenceVerifiedProjectManifest:
    tenant_id: UUID
    project_id: UUID
    run_id: UUID
    members: tuple[CoherenceManifestMember, ...]
    manifest_sha256: str
    complete_project_inventory_verified: bool = False

    def bind_clause_source(
        self, *, document_id: UUID, revision_id: UUID,
        attempt_index: int = 0,
    ) -> CoherenceCallIdentity:
        """Return a single-revision authority only when its identity is pinned.

        A synthesized merged clause with more than one origin MUST NOT be
        passed to this method: an aggregate cannot pretend to originate
        from one document. Caller still must attest clause/source alignment.
        """
        match = [
            member for member in self.members
            if member.document_id == document_id
            and member.revision_id == revision_id
        ]
        if len(match) != 1:
            raise CoherenceEscrowIdentityError(
                "clause source revision not in authenticated project manifest"
            )
        source = match[0]
        return CoherenceCallIdentity(
            tenant_id=self.tenant_id,
            project_id=self.project_id,
            document_id=source.document_id,
            revision_id=source.revision_id,
            run_id=self.run_id,
            source_sha256=source.blob_sha256,
            attempt_index=attempt_index,
        )

    def refuse_multi_source_clause(
        self, *, sources: tuple[CoherenceRevisionRef, ...],
    ) -> None:
        """Explicit refusal of pretending an aggregate has a single origin."""
        if len(sources) != 1:
            raise CoherenceEscrowIdentityError(
                "cross-document clause requires separate aggregate snapshot escrow"
            )
        self.bind_clause_source(
            document_id=sources[0].document_id,
            revision_id=sources[0].revision_id,
        )


async def verify_coherence_project_manifest(
    session: AsyncSession,
    *, tenant_id: UUID, project_id: UUID, run_id: UUID,
    revisions: tuple[CoherenceRevisionRef, ...],
    require_current: bool = True,
    require_complete_project_inventory: bool = False,
) -> CoherenceVerifiedProjectManifest:
    """Read every required lineage record under the tenant-scoped transaction.

    This does NOT attest a parser's PDF/OCR projection. The owner of the
    original source must still validate that each clause and blob reference
    point to the same content. The complete set of *selected* document
    revisions must be supplied by a trusted orchestration checkpoint.
    """
    for value in (tenant_id, project_id, run_id):
        if type(value) is not UUID:
            raise CoherenceEscrowIdentityError("tenant/project/run require UUIDs")
    if not isinstance(revisions, tuple) or not 1 <= len(revisions) <= 64:
        raise CoherenceEscrowIdentityError(
            "one to 64 explicitly pinned source revisions required"
        )
    unique = {(rev.document_id, rev.revision_id) for rev in revisions}
    if len(unique) != len(revisions):
        raise CoherenceEscrowIdentityError(
            "duplicate document/revision entry in source manifest"
        )
    if len({rev.document_id for rev in revisions}) != len(revisions):
        raise CoherenceEscrowIdentityError(
            "one current revision per document is required"
        )
    context = await session.scalar(text(
        "SELECT current_setting('app.current_tenant', true)"
    ))
    if context != str(tenant_id):
        raise CoherenceEscrowIdentityError(
            "tenant must be explicitly pinned before source verification"
        )

    if require_complete_project_inventory:
        # A complete-project declaration requires one stable database
        # snapshot. Under READ COMMITTED, a new document could appear
        # halfway through this inventory read, creating a false PASS.
        isolation = await session.scalar(text(
            "SELECT current_setting('transaction_isolation')"
        ))
        if isolation not in ("repeatable read", "serializable"):
            raise CoherenceEscrowIdentityError(
                "complete project inventory requires stable snapshot isolation"
            )
        # Check the entire project document inventory, including uploads
        # without any revision. An INNER JOIN would silently omit those
        # documents and falsely certify project completeness.
        active_rows = (await session.execute(text("""
            SELECT d.id AS document_id, r.revision_id
              FROM public.documents AS d
              LEFT JOIN public.document_revisions AS r
                ON r.document_id=d.id
               AND r.tenant_id=d.tenant_id
               AND r.project_id=d.project_id
               AND r.valid_to IS NULL
             WHERE d.tenant_id=CAST(:tenant AS uuid)
               AND d.project_id=CAST(:project AS uuid)
             ORDER BY d.id, r.revision_id
             FOR SHARE OF d
        """), {
            "tenant": str(tenant_id), "project": str(project_id),
        })).mappings().all()
        expected = {(r.document_id, r.revision_id) for r in revisions}
        actual = [(r["document_id"], r["revision_id"]) for r in active_rows]
        if (
            len(actual) != len(expected)
            or any(revision is None for _doc, revision in actual)
            or set(actual) != expected
        ):
            raise CoherenceEscrowIdentityError(
                "selected revisions do not cover current project documents"
            )

    members: list[CoherenceManifestMember] = []
    for expected in sorted(
        revisions, key=lambda item: (str(item.document_id), str(item.revision_id))
    ):
        row = (await session.execute(text("""
            SELECT revision_id, document_id, project_id, tenant_id,
                   blob_hash, valid_to
              FROM public.document_revisions
             WHERE revision_id=CAST(:revision AS uuid)
               AND document_id=CAST(:document AS uuid)
               AND project_id=CAST(:project AS uuid)
               AND tenant_id=CAST(:tenant AS uuid)
             FOR SHARE
        """), {
            "revision": str(expected.revision_id),
            "document": str(expected.document_id),
            "project": str(project_id),
            "tenant": str(tenant_id),
        })).mappings().one_or_none()
        if row is None:
            raise CoherenceEscrowIdentityError(
                "source revision not found in same tenant and project"
            )
        if require_current and row["valid_to"] is not None:
            raise CoherenceEscrowIdentityError(
                "historical revision cannot silently become current source"
            )
        digest = str(row["blob_hash"])
        if not _SHA256.fullmatch(digest):
            raise CoherenceEscrowIdentityError(
                "persisted source blob hash is missing or malformed"
            )
        members.append(CoherenceManifestMember(
            document_id=expected.document_id,
            revision_id=expected.revision_id,
            blob_sha256=digest,
        ))

    payload = {
        "version": "coherence-pinned-revisions-v1",
        "complete_project_inventory_verified": require_complete_project_inventory,
        "tenant": str(tenant_id), "project": str(project_id),
        "run": str(run_id),
        "revisions": [
            {
                "document": str(member.document_id),
                "revision": str(member.revision_id),
                "sha256": member.blob_sha256,
            }
            for member in members
        ],
    }
    manifest_sha = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CoherenceVerifiedProjectManifest(
        tenant_id=tenant_id, project_id=project_id, run_id=run_id,
        members=tuple(members), manifest_sha256=manifest_sha,
        complete_project_inventory_verified=require_complete_project_inventory,
    )
