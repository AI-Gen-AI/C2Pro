"""The canonical identity a HITL resume is authorized against (#758).

Three separate races all had the same shape: a human decision or a recovery
operation created for processing lineage A stayed usable after lineage B
became authoritative. Rather than three independent guards, resumability
gets ONE explicit identity and every seam compares against it.

The identity of "the lineage this review may be resumed through" is::

    review row id
      + thread_id                  the LangGraph checkpoint lineage (#758)
      + checkpoint / source checkpoint  (already carried per operation)
      + lineage_generation         the processing generation that bound it
      + lineage_fencing_token      the processing attempt that bound it

``lineage_generation`` / ``lineage_fencing_token`` are stamped onto the
review row by the attempt that claims its lineage, straight from the #711
:class:`~src.core.processing_authority.ProcessingAuthority`. They are stored
rather than parsed back out of the thread string so the identity survives
any future change to thread naming, and so a legacy row (both NULL) is
explicitly distinguishable from a fenced one.

From that, two comparisons decide everything:

* **is the review's lineage still current for its document?**
  ``(lineage_generation, lineage_fencing_token)`` must still equal the
  document's live ``document_processing_operations`` grant. A new revision
  or reprocess bumps both in the same transaction as the reset
  (:func:`~src.core.processing_authority.begin_generation`), so the moment a
  new generation becomes authoritative every review bound to the superseded
  one stops being resumable -- at the generation transition itself, not
  later when some worker happens to reach the HITL gate.

* **is the resume operation bound to the review's CURRENT lineage?**
  ``resume_operations.thread_id`` is the lineage the operation was
  authorized against. Once the review is rebound, that snapshot no longer
  matches and the operation can no longer resume the graph, continue N17,
  finalize a graph-completed run, or finalize the review/document.

Both comparisons fail CLOSED. A review whose lineage is not current is not
approvable until a live attempt re-claims it -- which is what a takeover or
a new generation does on its way to its own actionable checkpoint. That is
deliberately a refusal rather than a best guess: resuming a superseded
lineage replays evidence the current revision has already invalidated.

Nothing here destroys durable evidence. A stale operation keeps its row,
its phase, its analysis and its whole attempt ledger; it simply stops being
*actionable*, which is the distinction P1-3 turns on.

Legacy compatibility is explicit: a review whose lineage columns are NULL
was bound before this identity existed (including the UUID-style threads
production still has pending), and a document with no
``document_processing_operations`` row was never processed under #711. In
both cases the currency comparison is skipped and behaviour is exactly what
it was, which is why the pre-#758 shared-thread refusal in
``ResumeWorkflowUseCase`` remains the guard for those rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import text

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.core.processing_authority import ProcessingAuthority

__all__ = [
    "OPERATION_LINEAGE_SUPERSEDED",
    "PHASES_WITH_DURABLE_EFFECT",
    "RESUMABLE_REVIEW_STATUSES",
    "REVIEW_LINEAGE_NOT_CURRENT",
    "REVIEW_LINEAGE_REBOUND",
    "REVIEW_ROW_MISSING",
    "LineageDecision",
    "ReviewLineage",
    "authority_lineage",
    "decide_resume_lineage",
    "read_review_lineage",
    "stamp_superseded_reviews",
]

#: The review's recorded thread is no longer the one the caller read. Somebody
#: took the lineage over between the authorization read and this point.
REVIEW_LINEAGE_REBOUND = "review_lineage_rebound"

#: The review's lineage belongs to a superseded processing generation/attempt.
REVIEW_LINEAGE_NOT_CURRENT = "review_lineage_not_current_for_document"

#: The operation was created for a lineage this review no longer owns, and it
#: already carries durable business effects for that lineage.
OPERATION_LINEAGE_SUPERSEDED = "operation_bound_to_superseded_lineage"

#: The review row backing this operation is gone.
REVIEW_ROW_MISSING = "review_row_missing"

#: Phases whose business effect is already durable for the lineage they ran
#: against. Such an operation may NEVER be re-pointed at another lineage: its
#: analysis, its ``analysis.persisted`` event and possibly its
#: ``graph.completed`` marker all belong to the run that produced them.
PHASES_WITH_DURABLE_EFFECT = frozenset({"N17_DURABLE", "GRAPH_COMPLETED"})

#: Review states that still await (or may return to) a human decision. Only
#: these are worth superseding at a generation transition; a decided row is
#: history and must not be touched.
RESUMABLE_REVIEW_STATUSES = (
    "PENDING_REVIEW_REQUIRED",
    "PENDING_REVIEW_CONDITIONAL",
    "ESCALATED",
)


@dataclass(frozen=True)
class ReviewLineage:
    """A review row's lineage, next to the document's live processing grant.

    ``authority_generation`` / ``authority_fencing_token`` are None when the
    document has no ``document_processing_operations`` row -- it was never
    processed under #711 -- or when the review gates no document at all.
    """

    review_row_id: UUID
    thread_id: str | None
    document_id: UUID | None
    lineage_generation: int | None
    lineage_fencing_token: int | None
    authority_generation: int | None
    authority_fencing_token: int | None

    @property
    def is_fenced(self) -> bool:
        """Whether this review was bound by a #711-fenced processing attempt."""
        return self.lineage_generation is not None or self.lineage_fencing_token is not None

    @property
    def is_current_for_document(self) -> bool:
        """Whether the attempt that bound this review still owns the document.

        Unfenced (legacy) lineages and documents with no authority row are
        reported current: there is nothing to compare them against, and
        silently refusing them would strand rows that predate this identity.
        """
        if not self.is_fenced:
            return True
        if self.authority_generation is None:
            return True
        if (
            self.lineage_generation is not None
            and int(self.lineage_generation) != int(self.authority_generation)
        ):
            return False
        return not (
            self.lineage_fencing_token is not None
            and self.authority_fencing_token is not None
            and int(self.lineage_fencing_token) != int(self.authority_fencing_token)
        )


@dataclass(frozen=True)
class LineageDecision:
    """May this caller act, and must it adopt the review's current lineage?

    ``adopt_operation_lineage`` is set when the operation row still names the
    lineage it was first created for while the review has since moved on, and
    the operation carries no durable business effect. That operation is a
    lifecycle shell with nothing to protect, so the fresh authorization
    re-points it at the current lineage instead of leaving the review
    permanently unapprovable. Anything durable refuses instead.
    """

    refusal: str | None = None
    adopt_operation_lineage: bool = False

    @property
    def allowed(self) -> bool:
        return self.refusal is None


def decide_resume_lineage(
    lineage: ReviewLineage | None,
    *,
    authorized_thread_id: str | None,
    operation_thread_id: str | None,
    operation_phase: str | None,
) -> LineageDecision:
    """Whether a resume authorized against ``authorized_thread_id`` may run.

    Pure, so the whole safety matrix is unit-testable without a database.

    Order matters. "The review moved" is checked before "is the review
    current", because a caller that read lineage A has been superseded
    whatever the new lineage's own standing is.
    """
    if lineage is None:
        return LineageDecision(REVIEW_ROW_MISSING)
    if lineage.thread_id != authorized_thread_id:
        return LineageDecision(REVIEW_LINEAGE_REBOUND)
    if not lineage.is_current_for_document:
        return LineageDecision(REVIEW_LINEAGE_NOT_CURRENT)
    if operation_thread_id is not None and operation_thread_id != lineage.thread_id:
        if (operation_phase or "") in PHASES_WITH_DURABLE_EFFECT:
            return LineageDecision(OPERATION_LINEAGE_SUPERSEDED)
        return LineageDecision(adopt_operation_lineage=True)
    return LineageDecision()


# ── persistence ──────────────────────────────────────────────────────────────

_READ_LINEAGE = """
    SELECT r.id AS review_row_id,
           r.thread_id,
           r.document_id,
           r.lineage_generation,
           r.lineage_fencing_token,
           a.generation AS authority_generation,
           a.fencing_token AS authority_fencing_token
      FROM review_items r
      LEFT JOIN document_processing_operations a
             ON a.document_id = r.document_id
            AND a.tenant_id = r.tenant_id
     WHERE r.id = cast(:review_row_id as uuid)
       AND r.tenant_id = cast(:tenant_id as uuid)
"""

# FOR UPDATE OF r locks only the review row -- the authority row is read as
# evidence and must not be locked here, or a resume would contend with the
# processing worker that owns it. Locking the review is what makes the
# comparison a true compare-and-set against a concurrent rebind, which
# always takes this same row lock.
_READ_LINEAGE_SQL = text(_READ_LINEAGE)
_READ_LINEAGE_FOR_UPDATE_SQL = text(_READ_LINEAGE + " FOR UPDATE OF r")

#: Reusable predicate for a candidate scan that wants to skip operations whose
#: review has been rebound. A hint only -- the authoritative comparison is
#: :func:`decide_resume_lineage` inside the acquisition transaction, because a
#: cross-tenant scan cannot see the fail-closed authority table at all.
OPERATION_LINEAGE_MATCHES_REVIEW_SQL = "r.thread_id IS NOT DISTINCT FROM o.thread_id"

_STAMP_SUPERSEDED_SQL = text(
    f"""
    UPDATE review_items
       SET lineage_generation = cast(:superseded_generation as bigint),
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE document_id = cast(:document_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND lineage_generation IS NULL
       AND current_status::text IN (
           {", ".join(f"'{status}'" for status in RESUMABLE_REVIEW_STATUSES)}
       )
    RETURNING id
    """
)


async def read_review_lineage(
    session: Any, *, review_row_id: UUID, tenant_id: UUID, for_update: bool = False
) -> ReviewLineage | None:
    """The review's lineage and its document's live grant, in one read."""
    statement = _READ_LINEAGE_FOR_UPDATE_SQL if for_update else _READ_LINEAGE_SQL
    row = (
        await session.execute(
            statement,
            {"review_row_id": str(review_row_id), "tenant_id": str(tenant_id)},
        )
    ).first()
    if row is None:
        return None
    return ReviewLineage(
        review_row_id=UUID(str(row.review_row_id)),
        thread_id=row.thread_id,
        document_id=UUID(str(row.document_id)) if row.document_id else None,
        lineage_generation=(
            None if row.lineage_generation is None else int(row.lineage_generation)
        ),
        lineage_fencing_token=(
            None if row.lineage_fencing_token is None else int(row.lineage_fencing_token)
        ),
        authority_generation=(
            None if row.authority_generation is None else int(row.authority_generation)
        ),
        authority_fencing_token=(
            None
            if row.authority_fencing_token is None
            else int(row.authority_fencing_token)
        ),
    )


async def stamp_superseded_reviews(
    session: Any, *, tenant_id: UUID, document_id: UUID, superseded_generation: int
) -> list[UUID]:
    """Name the generation an unfenced pending review belonged to.

    Called from :func:`~src.core.processing_authority.begin_generation`, in
    the SAME transaction as the generation bump and the document reset, so a
    new revision or reprocess makes every pending review of the superseded
    lineage non-current atomically.

    Only rows with NO recorded generation are touched. A review already
    stamped by the attempt that bound it is left exactly as it is: the bump
    has already made its recorded generation stale, and rewriting it would
    lose which attempt actually owned it. This UPDATE therefore exists purely
    to bring legacy rows -- bound before this identity existed, so carrying
    no generation and otherwise indistinguishable from a current one -- into
    the same comparison.
    """
    rows = (
        await session.execute(
            _STAMP_SUPERSEDED_SQL,
            {
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "superseded_generation": int(superseded_generation),
            },
        )
    ).all()
    return [UUID(str(row.id)) for row in rows]


def authority_lineage(authority: ProcessingAuthority | None) -> tuple[int | None, int | None]:
    """The (generation, fencing token) a claim by this attempt should stamp."""
    if authority is None:
        return None, None
    return int(authority.generation), int(authority.fencing_token)
