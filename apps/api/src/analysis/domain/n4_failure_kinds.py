"""N4 Journey-V1 frozen interface contract (WP JV1-A1).

Single source for the vocabulary that the ledger/runner (A2/A3), provider
(A5), bridge/graph (A7), direct engine (A8), ingestion metadata (A12), HITL
gates (A15/A16), exports (A19/A20) and the direct reference arm (B3) share.

Coverage status is derived in application code. It is NEVER written to
``n4_extraction_runs.status`` (varchar(16) with a closed CHECK); no migration.

No ``from __future__ import annotations`` here: on Python 3.11 stringified
annotations hide ``NotRequired`` from ``TypedDict`` and every key would
become required at runtime.
"""
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict


class N4FailureKind(StrEnum):
    """Why a window did not end EXAMINED (persisted as the block reason)."""

    OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
    INVALID_ENVELOPE = "INVALID_ENVELOPE"
    PROVIDER_REJECTED_UNBILLED = "PROVIDER_REJECTED_UNBILLED"
    PROVIDER_RESULT_UNCERTAIN = "PROVIDER_RESULT_UNCERTAIN"
    BUDGET_UNAVAILABLE = "BUDGET_UNAVAILABLE"


class N4CoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_GAPS = "COMPLETE_WITH_GAPS"
    INCOMPLETE = "INCOMPLETE"


class N4GapResolution(StrEnum):
    OPEN = "OPEN"
    CLOSED_MANUALLY = "CLOSED_MANUALLY"


N4_COVERAGE_SCHEMA_VERSION = "n4-coverage-v1"
N4_ITEM_DATA_COVERAGE_KEY = "n4_coverage"
N4_METADATA_COVERAGE_KEY = "analysis_n4_coverage"


def derive_n4_coverage_status(
    *, total_windows: int, examined_windows: int, gap_windows: Sequence[int],
) -> N4CoverageStatus:
    """Classify a run once its windows are examined or recorded as gaps.

    COMPLETE_WITH_GAPS requires every window to be terminal (examined or gap)
    and at least one examined result; anything else is INCOMPLETE.
    """
    gaps = len(set(gap_windows))
    if total_windows > 0 and examined_windows == total_windows and gaps == 0:
        return N4CoverageStatus.COMPLETE
    if examined_windows > 0 and gaps > 0 and examined_windows + gaps == total_windows:
        return N4CoverageStatus.COMPLETE_WITH_GAPS
    return N4CoverageStatus.INCOMPLETE


class N4CoverageGap(TypedDict):
    ordinal: int
    failure_kind: str  # N4FailureKind value
    reason: str
    attempts: int
    page_start: int | None  # approximate; None until the page map exists
    page_end: int | None
    resolution: str  # N4GapResolution value
    closed_reason: NotRequired[str]
    closed_by: NotRequired[str]
    closed_at: NotRequired[str]  # ISO-8601 UTC


class N4Coverage(TypedDict):
    """Shape of ``item_data.n4_coverage`` and ``metadata.analysis_n4_coverage``."""

    schema_version: str  # N4_COVERAGE_SCHEMA_VERSION
    status: str  # N4CoverageStatus value
    run_id: str
    source_sha256: str
    total_windows: int
    examined_windows: int
    gap_windows: list[int]
    gaps: list[N4CoverageGap]
    model_id: NotRequired[str]


N4Dimension = Literal["SCOPE", "BUDGET", "TIME", "LEGAL", "QUALITY", "TECHNICAL"]
N4Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]

N4_DIMENSIONS: tuple[N4Dimension, ...] = (
    "SCOPE", "BUDGET", "TIME", "LEGAL", "QUALITY", "TECHNICAL",
)
N4_SEVERITIES: tuple[N4Severity, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
N4_SOURCE_QUOTE_MAX_CHARS = 1200
N4_SUPPORTING_QUOTES_MAX = 2


class N4SharedFinding(TypedDict):
    """Finding schema shared by windowed N4, direct engine (A8) and arm (B3).

    ``risk_reason`` is model interpretation; ``source_quote`` is literal text.
    ``severity_proposed`` is only a proposal the reviewer confirms or corrects.
    """

    title: str
    category: str
    dimension: N4Dimension
    severity_proposed: N4Severity
    risk_reason: str
    source_quote: str
    page_start: int | None
    page_end: int | None
    epc_control_id: NotRequired[int]  # 1..20, plan §6.2
    clause_ref: NotRequired[str]
    supporting_quotes: NotRequired[list[str]]
    impact: NotRequired[str]
    quote_omits_figures: NotRequired[bool]
    window_ordinal: NotRequired[int]
