"""Lossless, provider-neutral source window inventory for N4 V4 (WBS 2.1).

This is mechanical context allocation, NOT semantic keyword filtering or risk
selection. Each codepoint belongs to exactly one non-overlapping core span;
the LLM receives bounded surrounding context to interpret boundary clauses.
There is no top-N and no document-wide character cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class N4SourceWindow:
    ordinal: int
    source_sha256: str
    revision_id: str | None
    core_start: int
    core_end: int
    context_start: int
    context_end: int
    context_sha256: str
    context_text: str

    @property
    def core_text(self) -> str:
        left = self.core_start - self.context_start
        return self.context_text[left:left + self.core_end - self.core_start]

    @property
    def context_chars(self) -> int:
        return self.context_end - self.context_start


def plan_n4_source_windows(
    model_safe_text: str,
    *,
    revision_id: str | None = None,
    max_context_chars: int = 12_000,
    overlap_chars: int = 400,
) -> tuple[N4SourceWindow, ...]:
    """Partition the full text without silently omitting any source content.

    All ranges use Python character offsets into the immutable N2-safe
    projection. Source/revision SHA alone does not attest to the PDF original;
    the source store must separately preserve an original-span mapping.
    The returned list is a plan only: EXAMINED cannot be assigned until the
    provider response for that window has been checked and persisted.
    """
    if not isinstance(model_safe_text, str) or not model_safe_text.strip():
        raise ValueError("N4 source is unavailable: no model-safe text to inspect")
    if max_context_chars < 200:
        raise ValueError("max_context_chars must be at least 200")
    if overlap_chars < 0 or 2 * overlap_chars >= max_context_chars:
        raise ValueError("overlap must be nonnegative and leave core capacity")

    full_digest = sha256(model_safe_text.encode("utf-8")).hexdigest()
    core_capacity = max_context_chars - 2 * overlap_chars
    source_len = len(model_safe_text)
    windows: list[N4SourceWindow] = []
    start = 0
    while start < source_len:
        end = min(start + core_capacity, source_len)
        # Prefer paragraph/line boundaries when this does not discard source.
        # Never split so close to the start that a tiny repeating fragment
        # creates a loop. Oversized paragraphs are split at exact offsets.
        if end < source_len and core_capacity >= 100:
            lower = start + (core_capacity * 3 // 4)
            for boundary in ("\n\n", "\n", " "):
                cut = model_safe_text.rfind(boundary, lower, end)
                if cut > lower:
                    end = min(end, cut + len(boundary))
                    break

        context_start = max(0, start - overlap_chars)
        context_end = min(source_len, end + overlap_chars)
        context = model_safe_text[context_start:context_end]
        if end <= start or len(context) > max_context_chars:
            raise AssertionError("N4 source window invariant violated")

        windows.append(N4SourceWindow(
            ordinal=len(windows),
            source_sha256=full_digest,
            revision_id=revision_id,
            core_start=start,
            core_end=end,
            context_start=context_start,
            context_end=context_end,
            context_sha256=sha256(context.encode("utf-8")).hexdigest(),
            context_text=context,
        ))
        start = end

    # Enforce a gap-free, exactly-once core inventory. Context overlap is
    # allowed; two windows may cite the same risk but the ledger deduplicates.
    cursor = 0
    for window in windows:
        if window.core_start != cursor or not window.core_text:
            raise AssertionError("N4 source inventory has a coverage gap")
        cursor = window.core_end
    if cursor != source_len:
        raise AssertionError("N4 source inventory failed to cover the end")
    return tuple(windows)
