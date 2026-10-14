from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.development.review_attestation.base_work_implementation_verifier import (
    ProvenanceError,
    resolve_base_work_implementation,
)

PROTECTED_BASE = "b" * 40
EXEC_BASE = "c" * 40
HEAD = "a" * 40
BRANCH = "feat/dev14-proof"
WORK_ID = "C2PRO-DEV-14"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _subject(**overrides: Any) -> dict[str, Any]:
    value = {
        "repository_id": 1,
        "pr_number": 7,
        "head_sha": HEAD,
        "base_sha": PROTECTED_BASE,
        "head_ref": BRANCH,
    }
    value.update(overrides)
    return value


def _repo(
    tmp_path: Path,
    *,
    active: list[str] | None = None,
    queue_status: str = "in_progress",
    selected: Any = "codex",
    receipt: Any = "workspace:synthetic:1",
    base_sha: str = EXEC_BASE,
    branch: str = BRANCH,
    eligible_principals: list[str] | None = None,
    eligible_subordinates: list[str] | None = None,
    extra_match: bool = False,
) -> Path:
    active = [WORK_ID] if active is None else active
    current = {
        "baseline": {"main_sha": EXEC_BASE},
        "active_work": active,
    }
    queue = {
        "items": [{
            "work_id": WORK_ID,
            "status": queue_status,
            "work_ref": f".c2pro/work/{WORK_ID}.yaml",
        }]
    }
    work = {
        "schema": "c2pro-work-envelope-v1",
        "work_id": WORK_ID,
        "base_sha": base_sha,
        "branch": branch,
        "worker_selection": {
            "preferred": None,
            "eligible_principals": ["claude_code", "codex"] if eligible_principals is None else eligible_principals,
            "eligible_subordinates": [] if eligible_subordinates is None else eligible_subordinates,
            "selected": selected,
        },
    }
    if receipt is not None:
        work["workspace_receipt"] = receipt

    _write(tmp_path / ".c2pro/control/current.yaml", current)
    _write(tmp_path / ".c2pro/control/work-queue.yaml", queue)
    _write(tmp_path / f".c2pro/work/{WORK_ID}.yaml", work)

    if extra_match:
        second = "C2PRO-DEV-15"
        current["active_work"].append(second)
        queue["items"].append({
            "work_id": second,
            "status": "awaiting_review",
            "work_ref": f".c2pro/work/{second}.yaml",
        })
        work2 = dict(work)
        work2["work_id"] = second
        _write(tmp_path / ".c2pro/control/current.yaml", current)
        _write(tmp_path / ".c2pro/control/work-queue.yaml", queue)
        _write(tmp_path / f".c2pro/work/{second}.yaml", work2)

    return tmp_path


def test_1023_positive_base_pinned_assignment_proves_implementer(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    evidence = resolve_base_work_implementation(root, _subject())
    assert evidence == {
        "work_id": WORK_ID,
        "worker_id": "codex",
        "verified": True,
        "evidence_ref": (
            f"protected-base:{PROTECTED_BASE}:work:{WORK_ID}:"
            f"baseline:{EXEC_BASE}:workspace:synthetic:1:head:{HEAD}"
        ),
    }


def test_1023_idle_control_plane_proves_no_implementer(tmp_path: Path) -> None:
    root = _repo(tmp_path, active=[])
    assert resolve_base_work_implementation(root, _subject()) is None


def test_1026_protected_base_may_differ_from_execution_baseline(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert PROTECTED_BASE != EXEC_BASE
    evidence = resolve_base_work_implementation(root, _subject())
    assert evidence is not None
    assert f"protected-base:{PROTECTED_BASE}" in evidence["evidence_ref"]
    assert f"baseline:{EXEC_BASE}" in evidence["evidence_ref"]


def test_1026_work_baseline_must_match_current_execution_baseline(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    current_path = root / ".c2pro/control/current.yaml"
    current = yaml.safe_load(current_path.read_text())
    current["baseline"]["main_sha"] = "d" * 40
    _write(current_path, current)
    with pytest.raises(ProvenanceError, match="base_sha differs from current execution baseline"):
        resolve_base_work_implementation(root, _subject())


def test_1023_wrong_branch_proves_no_implementer(tmp_path: Path) -> None:
    assert resolve_base_work_implementation(_repo(tmp_path, branch="feat/other"), _subject()) is None


def test_1026_wrong_work_execution_baseline_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="base_sha differs from current execution baseline"):
        resolve_base_work_implementation(_repo(tmp_path, base_sha="d" * 40), _subject())


@pytest.mark.parametrize("status", ["ready", "blocked"])
def test_1023_active_work_must_be_in_effective_implementation_state(tmp_path: Path, status: str) -> None:
    with pytest.raises(ProvenanceError, match="effective implementation state"):
        resolve_base_work_implementation(_repo(tmp_path, queue_status=status), _subject())


@pytest.mark.parametrize("selected", [None, "", "Claude Code", 7])
def test_1023_selected_worker_must_be_explicit_and_strict(tmp_path: Path, selected: Any) -> None:
    with pytest.raises(ProvenanceError, match="selected worker"):
        resolve_base_work_implementation(_repo(tmp_path, selected=selected), _subject())


@pytest.mark.parametrize("receipt", [None, "", "  ", "receipt\nforged"])
def test_1023_workspace_receipt_is_required_for_assigned_dev_work(tmp_path: Path, receipt: Any) -> None:
    with pytest.raises(ProvenanceError, match="workspace receipt"):
        resolve_base_work_implementation(_repo(tmp_path, receipt=receipt), _subject())


def test_1023_selected_worker_must_be_in_base_pinned_eligibility(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="not eligible"):
        resolve_base_work_implementation(
            _repo(tmp_path, selected="codex", eligible_principals=["claude_code"]),
            _subject(),
        )


def test_1023_multiple_matching_active_work_items_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="multiple active"):
        resolve_base_work_implementation(_repo(tmp_path, extra_match=True), _subject())


@pytest.mark.parametrize("bad_ref", ["../escape.yaml", "/tmp/x.yaml", ".c2pro/../x.yaml"])
def test_1023_unsafe_work_ref_fails_closed(tmp_path: Path, bad_ref: str) -> None:
    root = _repo(tmp_path)
    queue_path = root / ".c2pro/control/work-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    queue["items"][0]["work_ref"] = bad_ref
    _write(queue_path, queue)
    with pytest.raises(ProvenanceError):
        resolve_base_work_implementation(root, _subject())


@pytest.mark.parametrize("head_ref", [None, "", " bad", "bad\nref"])
def test_1023_trusted_subject_requires_canonical_head_ref(tmp_path: Path, head_ref: Any) -> None:
    with pytest.raises(ProvenanceError, match="head_ref"):
        resolve_base_work_implementation(_repo(tmp_path), _subject(head_ref=head_ref))


def test_1023_noncanonical_in_repo_work_ref_is_rejected(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    alt = root / ".c2pro/work/alternate.yaml"
    alt.write_text((root / f".c2pro/work/{WORK_ID}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    queue_path = root / ".c2pro/control/work-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    queue["items"][0]["work_ref"] = ".c2pro/work/alternate.yaml"
    _write(queue_path, queue)
    with pytest.raises(ProvenanceError, match="canonical DEV work-envelope path"):
        resolve_base_work_implementation(root, _subject())


def test_1023_symlinked_work_envelope_is_rejected(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    canonical = root / f".c2pro/work/{WORK_ID}.yaml"
    target = root / ".c2pro/work/real.yaml"
    target.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    canonical.unlink()
    canonical.symlink_to(target.name)
    with pytest.raises(ProvenanceError, match="symlink"):
        resolve_base_work_implementation(root, _subject())
