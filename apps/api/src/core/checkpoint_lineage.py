"""Authority-scoped LangGraph checkpoint lineage for document processing (#758).

The #711 processing-authority fence protects the application's durable
writes, but LangGraph's checkpoint writes go through AsyncPostgresSaver,
outside that transaction — the saver has no notion of a fencing token and
will happily append for a worker that lost its lease.

While every processing attempt for a document shared ONE checkpoint thread
(``document:{document_id}:analysis``), that gap was exploitable:

    A owns fence N, enters the graph, writes checkpoints
    A's lease expires; B acquires fence N+1
    stale A appends ANOTHER checkpoint to the same thread

The current owner then selected "latest state for the thread" and could
legitimately bind, and later resume, a checkpoint produced by the stale
attempt. Fencing the metadata write did not help: the write was correctly
fenced, the VALUE being written was not.

This module removes the shared namespace instead of trying to filter it
afterwards. Each processing attempt gets its own thread, named from the
authority that owns it, so a stale writer's appends land on a lineage that
nothing current names. Two consequences matter:

* a stale attempt can still write (nothing can stop it) but its writes are
  unreachable from the current review — isolation by construction, not by
  detection;
* "latest checkpoint for this thread" becomes authority-pure, so the
  deliberate thread-only fallback in ``CheckpointService`` can no longer
  cross a processing-authority boundary even when no checkpoint id was
  recorded.

``fencing_token`` is the attempt discriminator because it is monotonic per
document and never reset — ``begin_generation`` bumps it along with the
generation, and each grant bumps it again — so (document, generation, fence)
identifies exactly one attempt across the document's whole history.
Generation is kept in the name because it is what a reprocess/new revision
advances, which makes a lineage legible to an operator reading a thread id.
The revision id is deliberately NOT included: ``begin_generation`` sets
revision and generation together, so generation already reflects it, and a
second UUID would add length without adding discrimination.

HITL resume never calls into here. It replays the EXACT persisted
``(thread_id, checkpoint_ns, checkpoint_id)`` recorded on the review, so
resume semantics are unchanged by the naming, and a direct user resume —
which runs with no ambient processing authority — cannot be influenced by
this at all.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.core.processing_authority import ProcessingAuthority

__all__ = [
    "AUTHORITY_ANALYSIS_THREAD_RE",
    "LEGACY_SHARED_ANALYSIS_THREAD_RE",
    "analysis_thread_id",
    "is_authority_scoped_analysis_thread",
    "is_legacy_shared_analysis_thread",
    "legacy_shared_analysis_thread_id",
]

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

#: The pre-#758 shared form: one thread for every attempt on a document.
LEGACY_SHARED_ANALYSIS_THREAD_RE = re.compile(rf"^document:{_UUID}:analysis$")

#: The authority-scoped form: one thread per processing attempt.
AUTHORITY_ANALYSIS_THREAD_RE = re.compile(rf"^document:({_UUID}):g(\d+):f(\d+):analysis$")


def legacy_shared_analysis_thread_id(document_id: UUID | str) -> str:
    """The pre-#758 shared thread name.

    Still produced when analysis somehow runs with no processing authority
    bound, so such a path keeps working exactly as before rather than
    silently changing identity. Production analysis always runs under an
    authority (``_run_document_analysis`` acquires one before invoking the
    graph), so this is a compatibility edge, not the normal path.
    """
    return f"document:{document_id}:analysis"


def analysis_thread_id(
    *, document_id: UUID | str, authority: ProcessingAuthority | None
) -> str:
    """The checkpoint thread this processing ATTEMPT owns.

    Every distinct attempt — a retry, a recovery hand-off, a takeover after
    a lease expiry, a reprocess — holds a different fencing token and so
    gets a different thread. That is the whole point: a stale attempt cannot
    append to the lineage the current owner is building.

    Returns the legacy shared name when no authority is bound, so callers
    outside a processing worker are unaffected.
    """
    if authority is None:
        return legacy_shared_analysis_thread_id(document_id)
    return (
        f"document:{authority.document_id}"
        f":g{authority.generation}"
        f":f{authority.fencing_token}"
        ":analysis"
    )


def is_authority_scoped_analysis_thread(thread_id: str | None) -> bool:
    """True when this thread belongs to exactly one processing attempt.

    For such a thread, "latest checkpoint on the thread" is authority-pure:
    only the one attempt named in the thread id ever wrote to it.
    """
    return bool(thread_id) and AUTHORITY_ANALYSIS_THREAD_RE.match(thread_id or "") is not None


def is_legacy_shared_analysis_thread(thread_id: str | None) -> bool:
    """True for a pre-#758 thread that several attempts may have written to.

    Only meaningful for lineages created before this fix; nothing produces
    this shape for an owned analysis run any more.
    """
    return (
        bool(thread_id) and LEGACY_SHARED_ANALYSIS_THREAD_RE.match(thread_id or "") is not None
    )
