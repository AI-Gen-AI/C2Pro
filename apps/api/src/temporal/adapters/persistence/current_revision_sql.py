"""The one trusted-current revision rule, as SQL every reader embeds (Lane C / C3a).

``current_revision_lateral(document, tenant)`` is a ``LATERAL`` subquery yielding,
for one document of one tenant:

* ``revision_id`` -- the current revision (NULL when unresolved or without lineage);
* ``resolved`` / ``trusted`` / ``single_revision`` -- see ``CurrentRevisionStatus``.

The ``*_IN_CURRENT_SCOPE`` predicates then decide whether a clause row, a RAG
chunk or a document's parsed text belongs to that current revision. A row bound
(or stamped) to the current revision is in scope; an unbound / unstamped legacy row
only when the document has at most one revision -- and for clauses only while that
revision has no bound rows of its own, so two sets are never mixed. Anything of an
unresolved document is out of scope (fail closed).

Read-only. #714 ``document_artifacts`` stays the only trust authority.
"""

from __future__ import annotations

_TRUSTED_BOUND = (
    "a.trust_state = 'trusted' AND a.lifecycle_status = 'active' "
    "AND a.document_revision_id IS NOT NULL"
)


def current_revision_lateral(document: str, tenant: str) -> str:
    """SQL for ``CROSS JOIN LATERAL (...) AS <alias>`` over one document and tenant."""
    in_lineage = (
        "EXISTS (SELECT 1 FROM public.document_revisions lr "
        f"WHERE lr.revision_id = t.trusted_revision AND lr.document_id = {document} "
        f"AND lr.tenant_id = {tenant})"
    )
    trusted = f"(t.trusted_bound = 1 AND {in_lineage})"
    single = "(t.trusted_bound = 0 AND l.revisions <= 1 AND NOT t.rejected_only)"
    return f"""(
        SELECT
            CASE WHEN {trusted} THEN t.trusted_revision
                 WHEN {single} THEN l.only_revision
            END AS revision_id,
            ({trusted} OR {single}) AS resolved,
            {trusted} AS trusted,
            (l.revisions <= 1) AS single_revision
        FROM (
            SELECT count(*) AS revisions, (array_agg(r.revision_id))[1] AS only_revision
            FROM public.document_revisions r
            WHERE r.document_id = {document} AND r.tenant_id = {tenant}
        ) AS l
        CROSS JOIN (
            SELECT
                count(DISTINCT a.document_revision_id) FILTER (WHERE {_TRUSTED_BOUND})
                    AS trusted_bound,
                (array_agg(DISTINCT a.document_revision_id) FILTER (WHERE {_TRUSTED_BOUND}))[1]
                    AS trusted_revision,
                (COALESCE(bool_or(a.trust_state = 'rejected'), false)
                 AND NOT COALESCE(bool_or(a.trust_state IN ('proposed', 'trusted')), false))
                    AS rejected_only
            FROM public.document_artifacts a
            WHERE a.document_id = {document} AND a.tenant_id = {tenant}
        ) AS t
    )"""


def clause_in_current_scope(clause: str, current: str) -> str:
    """Predicate: clause row ``clause`` belongs to the current revision ``current``."""
    return f"""{current}.resolved AND (
        {clause}.revision_id = {current}.revision_id
        OR ({clause}.revision_id IS NULL AND {current}.single_revision AND NOT EXISTS (
            SELECT 1 FROM public.clauses bound
            WHERE bound.document_id = {clause}.document_id
              AND bound.tenant_id = {clause}.tenant_id
              AND bound.revision_id = {current}.revision_id))
    )"""


def stamp_in_current_scope(stamp: str, current: str) -> str:
    """Predicate for a JSONB-stamped artifact (RAG chunk metadata, parsed text).

    ``stamp`` is the JSONB text expression holding the revision id (NULL when
    unstamped, i.e. written before C3a).
    """
    return f"""{current}.resolved AND (
        {stamp} = {current}.revision_id::text
        OR ({stamp} IS NULL AND {current}.single_revision)
    )"""


def chunk_in_current_scope(chunk: str, current: str) -> str:
    return stamp_in_current_scope(f"({chunk}.metadata ->> 'revision_id')", current)


def parsed_text_in_current_scope(document: str, current: str) -> str:
    return stamp_in_current_scope(
        f"({document}.document_metadata ->> 'parsed_text_revision_id')", current
    )


def current_chunk_join(chunk: str, alias: str = "cur") -> str:
    """``CROSS JOIN LATERAL`` clause resolving the current revision of a chunk's document."""
    return (
        f"CROSS JOIN LATERAL {current_revision_lateral(f'{chunk}.document_id', f'{chunk}.tenant_id')}"
        f" AS {alias}"
    )


__all__ = [
    "chunk_in_current_scope",
    "clause_in_current_scope",
    "current_chunk_join",
    "current_revision_lateral",
    "parsed_text_in_current_scope",
    "stamp_in_current_scope",
]
