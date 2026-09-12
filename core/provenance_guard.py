"""Guards against silent loss of work-queue.yaml provenance comments (G2).

`core.reconciler.reconcile_result` and `core.legacy_closure.reconcile_legacy_closure`
both rewrite `work-queue.yaml` via `yaml.safe_load` -> `yaml.dump`, which has no
comment model and therefore does not round-trip hand-written comments. Some
queue items carry "DEV-DEBT" provenance comments recording why a work_id was
registered a certain way -- e.g. C2PRO-DEV-05 (commit 2f1443e7) and
C2PRO-DEV-13 (commit 5ef8a5ee). If that meaning is not already captured
somewhere schema-safe and machine-readable, silently stripping the comment on
the next reconciliation write would destroy it.

This module never invents provenance text. It only reads text already
committed in the repository (the comment itself) and checks it against the
existing `.c2pro/evidence/<work_id>.yaml` mechanism (schema
`c2pro-evidence-reference-v1`, already used for C2PRO-DEV-01/02) before
allowing a reconciliation write to proceed.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_ITEM_RE = re.compile(r"^\s*-\s*work_id:\s*(\S+)")
_COMMENT_RE = re.compile(r"^\s*#")


class ProvenanceLossError(Exception):
    """Raised when a reconciliation write would silently discard a work-queue
    provenance comment that is not already preserved as machine-readable
    evidence."""


def extract_item_comments(yaml_text: str) -> dict[str, str]:
    """Maps each `work_id` under `items:` to the comment block immediately
    preceding it in the raw YAML text (empty string if no comment precedes
    it). Comment markers and per-line leading whitespace are stripped; the
    remaining text is joined with single spaces so wrapped comment blocks
    compare as equal regardless of line-wrap position.
    """
    comments: dict[str, str] = {}
    buffer: list[str] = []
    for line in yaml_text.splitlines():
        item_match = _ITEM_RE.match(line)
        if item_match:
            comments[item_match.group(1)] = " ".join(buffer).strip()
            buffer = []
            continue
        if _COMMENT_RE.match(line):
            buffer.append(line.strip().lstrip("#").strip())
        elif line.strip() == "":
            continue
        else:
            buffer = []
    return comments


def has_evidence_coverage(work_id: str, evidence_dir: Path) -> bool:
    """True if `<evidence_dir>/<work_id>.yaml` exists, is a valid
    `c2pro-evidence-reference-v1` document, and carries at least one
    reference with a non-empty `summary` -- i.e. the provenance is already
    captured in schema-safe, machine-readable form."""
    evidence_path = Path(evidence_dir) / f"{work_id}.yaml"
    if not evidence_path.exists():
        return False
    try:
        with open(evidence_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return False
    if not isinstance(data, dict) or data.get("schema") != "c2pro-evidence-reference-v1":
        return False
    references = data.get("references", [])
    return any(isinstance(r, dict) and (r.get("summary") or "").strip() for r in references)


def find_uncovered_comment_loss(before_text: str, after_text: str, evidence_dir: Path) -> list[str]:
    """Returns the work_ids whose provenance comment would be silently
    destroyed by rewriting work-queue.yaml from `before_text` to `after_text`,
    and which have no existing evidence-file coverage. Order-stable (input
    order of `before_text`'s items)."""
    before_comments = extract_item_comments(before_text)
    after_comments = extract_item_comments(after_text)

    lost: list[str] = []
    for work_id, comment in before_comments.items():
        if not comment:
            continue
        if after_comments.get(work_id, "") == comment:
            continue  # preserved verbatim
        if has_evidence_coverage(work_id, evidence_dir):
            continue  # already captured in schema-safe machine-readable form
        lost.append(work_id)
    return lost


def assert_no_uncovered_comment_loss(before_text: str, after_text: str, evidence_dir: Path) -> None:
    """Raises ProvenanceLossError if rewriting work-queue.yaml would silently
    discard any provenance comment not already covered by evidence."""
    lost = find_uncovered_comment_loss(before_text, after_text, evidence_dir)
    if lost:
        raise ProvenanceLossError(
            "Refusing to reconcile: rewriting work-queue.yaml would silently discard "
            f"provenance comments for {lost} with no existing "
            ".c2pro/evidence/<work_id>.yaml coverage. Create a c2pro-evidence-reference-v1 "
            "file for each id first (kind: audit, locator: the git commit that introduced "
            "the comment, summary: the comment text) -- do not proceed by deleting it. If no "
            "existing schema field can represent this, that is a genuine schema gap: stop and "
            "escalate the minimal schema change required rather than losing the history."
        )
