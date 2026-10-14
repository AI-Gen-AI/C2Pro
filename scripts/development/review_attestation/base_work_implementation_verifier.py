"""Resolve implementation worker identity only from protected-base C2Pro control.

This module is intentionally narrow. It does not authorize execution or merge.
It only answers one question for the review-attestation adapter: does the
protected PR base prove which worker was effectively assigned to this branch?

A valid proof requires all of:
- current.yaml marks the work active and its baseline equals the PR base SHA;
- work-queue.yaml contains that active work in an implementation lifecycle state;
- the referenced c2pro-work-envelope-v1 is from the protected base checkout;
- work base_sha and branch match the trusted PR subject;
- worker_selection.selected is explicit and eligible;
- workspace_receipt is a non-empty approved-base evidence reference.

No identity is inferred from commits, PR authors, comments, model names,
providers, harnesses or the pull-request head.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_WORK_ID = re.compile(r"^C2PRO-DEV-[0-9]{2}$")
_WORKER_ID = re.compile(r"^[a-z0-9_]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,170}$")
_EFFECTIVE_QUEUE_STATES = {"in_progress", "awaiting_review", "awaiting_owner"}


class ProvenanceError(ValueError):
    """Protected-base implementation provenance is malformed or ambiguous."""


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProvenanceError(f"cannot read trusted control artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"trusted control artifact is not a mapping: {path.name}")
    return value


def _safe_repo_path(root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw or raw.startswith("/"):
        raise ProvenanceError("work_ref is missing or unsafe")
    rel = Path(raw)
    if any(part in ("", ".", "..") for part in rel.parts):
        raise ProvenanceError("work_ref is not canonical")
    root_resolved = root.resolve()
    path = (root / rel).resolve(strict=False)
    if path != root_resolved and root_resolved not in path.parents:
        raise ProvenanceError("work_ref escapes repository")
    if path.is_symlink() or not path.is_file():
        raise ProvenanceError("work_ref does not resolve to a regular trusted-base file")
    return path


def _subject(subject: dict[str, Any]) -> tuple[str, str, str]:
    base = subject.get("base_sha")
    head = subject.get("head_sha")
    head_ref = subject.get("head_ref")
    if not isinstance(base, str) or not _SHA40.fullmatch(base):
        raise ProvenanceError("subject base_sha is malformed")
    if not isinstance(head, str) or not _SHA40.fullmatch(head):
        raise ProvenanceError("subject head_sha is malformed")
    if not isinstance(head_ref, str) or not _BRANCH.fullmatch(head_ref):
        raise ProvenanceError("subject head_ref is missing or malformed")
    return base, head, head_ref


def resolve_base_work_implementation(repo_root: Path, subject: dict[str, Any]) -> dict[str, Any] | None:
    """Return trusted implementation evidence for one exact PR subject, or None.

    None means the protected base has no effective work matching this branch.
    A matching-but-malformed or ambiguous assignment raises ProvenanceError.
    """
    base_sha, head_sha, head_ref = _subject(subject)
    current = _load_mapping(repo_root / ".c2pro/control/current.yaml")
    queue = _load_mapping(repo_root / ".c2pro/control/work-queue.yaml")

    active = current.get("active_work")
    if not isinstance(active, list) or any(not isinstance(x, str) for x in active):
        raise ProvenanceError("current.active_work is malformed")
    if not active:
        return None

    baseline = current.get("baseline", {}).get("main_sha")
    if baseline != base_sha:
        return None

    items = queue.get("items")
    if not isinstance(items, list):
        raise ProvenanceError("work queue items are malformed")

    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ProvenanceError("work queue contains a non-mapping item")
        work_id = item.get("work_id")
        if not isinstance(work_id, str) or not _WORK_ID.fullmatch(work_id) or work_id in by_id:
            raise ProvenanceError("work queue contains an invalid or duplicate work_id")
        by_id[work_id] = item

    matches: list[tuple[dict[str, Any], str]] = []
    for work_id in active:
        item = by_id.get(work_id)
        if item is None:
            raise ProvenanceError(f"active work {work_id} is absent from the queue")
        if item.get("status") not in _EFFECTIVE_QUEUE_STATES:
            raise ProvenanceError(f"active work {work_id} is not in an effective implementation state")
        work_path = _safe_repo_path(repo_root, item.get("work_ref"))
        work = _load_mapping(work_path)
        if work.get("schema") != "c2pro-work-envelope-v1" or work.get("work_id") != work_id:
            raise ProvenanceError(f"active work {work_id} envelope identity is invalid")
        if work.get("base_sha") != base_sha or work.get("branch") != head_ref:
            continue

        selection = work.get("worker_selection")
        if not isinstance(selection, dict):
            raise ProvenanceError(f"active work {work_id} worker_selection is malformed")
        selected = selection.get("selected")
        if not isinstance(selected, str) or not _WORKER_ID.fullmatch(selected):
            raise ProvenanceError(f"active work {work_id} has no valid selected worker")
        eligible = []
        for key in ("eligible_principals", "eligible_subordinates"):
            values = selection.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ProvenanceError(f"active work {work_id} worker eligibility is malformed")
            eligible.extend(values)
        if selected not in eligible:
            raise ProvenanceError(f"active work {work_id} selected worker is not eligible")

        receipt = work.get("workspace_receipt")
        if not isinstance(receipt, str) or not receipt.strip() or receipt != receipt.strip() or "\n" in receipt or "\r" in receipt:
            raise ProvenanceError(f"active work {work_id} has no valid workspace receipt")
        matches.append((work, receipt))

    if not matches:
        return None
    if len(matches) != 1:
        raise ProvenanceError("multiple active protected-base WORK envelopes match this PR subject")

    work, receipt = matches[0]
    selected = work["worker_selection"]["selected"]
    return {
        "work_id": work["work_id"],
        "worker_id": selected,
        "verified": True,
        "evidence_ref": f"protected-base:{work['work_id']}:{receipt}:head:{head_sha}",
    }


def build_base_work_implementation_verifier(repo_root: Path):
    """Return the injected verifier expected by github_context_adapter."""
    trusted_root = repo_root.resolve()

    def verify(subject: dict[str, Any]) -> dict[str, Any] | None:
        return resolve_base_work_implementation(trusted_root, subject)

    return verify
