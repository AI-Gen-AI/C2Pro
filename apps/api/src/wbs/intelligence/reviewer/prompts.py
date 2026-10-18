"""Versioned, repo-reviewed prompt templates of the WBS Reviewer (no remote prompt hub).

A template is identified by task, version and the SHA-256 digest of its exact text; the digests are
part of the run's idempotency key and provenance. Templates contain instructions only -- project,
import and user content is never interpolated into them; it travels in isolated DATA blocks.
"""

from __future__ import annotations

import hashlib
from typing import Final

from src.wbs.intelligence.contracts.run import PromptTemplateRef
from src.wbs.intelligence.reviewer.model_port import ReviewTask

TEMPLATE_VERSION: Final = "v1"

MAP_TEMPLATE: Final = """You review ONE bounded cluster of a Work Breakdown Structure against project evidence.
Return only a JSON object of contract wbs-proposal/v1 with:
- "findings": qualification findings for nodes of THIS cluster only (dimension, status GAP / WARNING /
  AMBIGUOUS, summary, node_ids, evidence, confidence_pct);
- "proposals": optional improvement proposals for THIS cluster only, expressed as governed edit
  operations against the listed node ids or new local labels. A finding never requires a proposal;
- "qualification": [] (the tree-level qualification is produced separately).
Cite evidence only by the excerpt ids shown, quoting their visible text exactly. Never state a
document, page or offset. Never invent node ids. Do not propose approval, submission or any change to
profiles, policies or permissions: those are human decisions and not part of the schema."""

REDUCE_TEMPLATE: Final = """You qualify a whole Work Breakdown Structure against project evidence.
Return only a JSON object of contract wbs-proposal/v1 with "qualification": one entry per dimension of
wbs-qualification/v1 (status SUPPORTED / GAP / WARNING / NOT_EVALUATED / AMBIGUOUS with a summary and
evidence). "findings" and "proposals" are [] (they were collected per cluster). A dimension you cannot
assess from the evidence shown is NOT_EVALUATED with a reason; absence of evidence is never SUPPORTED.
Cite evidence only by the excerpt ids shown, quoting their visible text exactly."""

_TEMPLATES: Final = {ReviewTask.MAP: MAP_TEMPLATE, ReviewTask.REDUCE: REDUCE_TEMPLATE}


def template_text(task: ReviewTask) -> str:
    return _TEMPLATES[task]


def template_ref(task: ReviewTask) -> PromptTemplateRef:
    text = _TEMPLATES[task]
    return PromptTemplateRef(task=task.value, version=TEMPLATE_VERSION,
                             digest="sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest())


def template_refs() -> tuple[PromptTemplateRef, ...]:
    return tuple(template_ref(task) for task in ReviewTask)


__all__ = ["MAP_TEMPLATE", "REDUCE_TEMPLATE", "TEMPLATE_VERSION", "template_ref", "template_refs", "template_text"]
