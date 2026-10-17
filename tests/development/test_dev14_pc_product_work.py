"""DEV-14/#991: synthetic PC WORK proofs, never real assignment receipts."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.development.product_work_identity import (
    PC_SDD, PC_TASKS, ProductWorkError, matching_pc_assignment,
    validate_pc_work, work_path,
)
from scripts.development.review_attestation.base_work_implementation_verifier import (
    ProvenanceError, resolve_base_work_implementation,
)

EXEC_BASE = "b" * 40
PROTECTED_BASE = "c" * 40
HEAD = "d" * 40


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _case(root: Path, task: str = "PC-3", *, status: str = "assigned") -> tuple[Path, Path]:
    rule = PC_TASKS[task]
    sdd = root / PC_SDD
    sdd.parent.mkdir(parents=True, exist_ok=True)
    sdd.write_text("# Synthetic stand-in for existing Project Controls product addendum\n", encoding="utf-8")
    receipt = f".c2pro/product-work/receipts/{task}.yaml"
    work = {
        "schema": "c2pro-product-work-envelope-v1",
        "schema_version": 1,
        "work_id": task, "task_id": task, "parent_issue": 672,
        "status": status, "base_sha": EXEC_BASE,
        "branch": rule["branch"], "sdd_path": PC_SDD,
        "acceptance_ids": [task],
        "scope": [rule["scope_prefix"] + "**"],
        "forbidden_paths": [".github/**", "supabase/**"],
        "assigned_to": rule["worker"] if status == "assigned" else None,
        "workspace_receipt": receipt if status == "assigned" else None,
    }
    work_path_abs = root / work_path(task)
    _write(work_path_abs, work)
    observation = {
        "schema": "c2pro-workspace-observation-v1",
        "work_id": task, "task_id": task, "parent_issue": 672,
        "worker_id": rule["worker"], "branch": rule["branch"],
        "base_sha": EXEC_BASE, "observed_head_sha": EXEC_BASE,
        "observed_by": "orchestrator", "clean": True,
        "workspace_path": "/synthetic/isolated/" + task,
        "observed_at": "2026-10-17T09:00:00+02:00",
    }
    observation_path = root / receipt
    if status == "assigned":
        _write(observation_path, observation)
    # The DEV control remains idle and is never reinterpreted as PC authority.
    _write(root / ".c2pro/control/current.yaml",
           {"control_status": "reconciled_idle", "active_work": []})
    _write(root / ".c2pro/control/work-queue.yaml", {"items": []})
    return work_path_abs, observation_path


def _subject(task: str = "PC-3", **extra: str) -> dict:
    return {
        "repository_id": 123, "pr_number": 321,
        "base_sha": PROTECTED_BASE, "merge_base_sha": EXEC_BASE,
        "head_sha": HEAD, "head_ref": PC_TASKS[task]["branch"], **extra,
    }


@pytest.mark.parametrize("task,worker", [("PC-3", "codex"), ("PC-7a", "claude_code")])
def test_pc_protected_base_assignment_does_not_use_idle_dev_queue(
    tmp_path: Path, task: str, worker: str,
) -> None:
    _case(tmp_path, task)
    evidence = resolve_base_work_implementation(tmp_path, _subject(task))
    assert evidence is not None
    assert evidence["verified"] is True
    assert evidence["work_id"] == task
    assert evidence["worker_id"] == worker
    assert f"protected-base:{PROTECTED_BASE}:product-work:{task}:" in evidence["evidence_ref"]
    assert (tmp_path / ".c2pro/control/current.yaml").is_file()


def test_no_pc_work_never_infers_worker_from_branch(tmp_path: Path) -> None:
    assert resolve_base_work_implementation(tmp_path, _subject()) is None


def test_prepared_work_cannot_be_interpreted_as_active(tmp_path: Path) -> None:
    _case(tmp_path, status="prepared")
    assert resolve_base_work_implementation(tmp_path, _subject()) is None


def test_wrong_lane_does_not_leak_other_worker_identity(tmp_path: Path) -> None:
    _case(tmp_path, "PC-7a")
    assert resolve_base_work_implementation(tmp_path, _subject("PC-3")) is None


@pytest.mark.parametrize("change", [
    {"assigned_to": "claude_code"},
    {"assigned_to": None},
    {"branch": "feat/other-pc3"},
    {"base_sha": "e" * 40},
    {"work_id": "PC-7a"},
    {"parent_issue": 991},
    {"task_id": "PQ-HITL-09.1"},
    {"acceptance_ids": ["PC-7a"]},
    {"sdd_path": "docs/product/pq-hitl-2026-01-delivery-spec-v1.md"},
    {"scope": ["apps/web/**"]},
    {"scope": [".github/**"]},
    {"scope": ["apps/api/../web/**"]},
    {"workspace_receipt": "claimed-by-author-in-PR-body"},
    {"workspace_receipt": "../../tmp/receipt"},
])
def test_invalid_pc_work_fails_closed(tmp_path: Path, change: dict) -> None:
    path, _ = _case(tmp_path)
    work = yaml.safe_load(path.read_text())
    work.update(change)
    _write(path, work)
    with pytest.raises(ProvenanceError, match="Project Controls WORK provenance invalid"):
        resolve_base_work_implementation(tmp_path, _subject())


@pytest.mark.parametrize("change", [
    {"worker_id": "claude_code"},
    {"branch": "feat/other"},
    {"base_sha": "f" * 40},
    {"observed_head_sha": "f" * 40},
    {"work_id": "PC-7a"},
    {"observed_by": "codex"},
    {"clean": False},
    {"workspace_path": "../fake"},
    {"workspace_path": "/tmp/../unsafe"},
    {"observed_at": ""},
    {"fabricated_signature": "no"},
])
def test_forged_or_stale_workspace_observation_fails_closed(
    tmp_path: Path, change: dict,
) -> None:
    _, receipt_path = _case(tmp_path)
    receipt = yaml.safe_load(receipt_path.read_text())
    receipt.update(change)
    _write(receipt_path, receipt)
    with pytest.raises(ProvenanceError, match="Project Controls WORK provenance invalid"):
        resolve_base_work_implementation(tmp_path, _subject())


@pytest.mark.parametrize("missing", ["receipt", "work"])
def test_missing_authoritative_file_fails_closed(tmp_path: Path, missing: str) -> None:
    work_path_abs, receipt_path = _case(tmp_path)
    (receipt_path if missing == "receipt" else work_path_abs).unlink()
    if missing == "work":
        assert resolve_base_work_implementation(tmp_path, _subject()) is None
    else:
        with pytest.raises(ProvenanceError, match="Project Controls WORK provenance invalid"):
            resolve_base_work_implementation(tmp_path, _subject())


def test_symlinked_receipt_is_not_authority(tmp_path: Path) -> None:
    _, receipt_path = _case(tmp_path)
    target = receipt_path.with_name("elsewhere.yaml")
    target.write_text(receipt_path.read_text(encoding="utf-8"), encoding="utf-8")
    receipt_path.unlink()
    receipt_path.symlink_to(target.name)
    with pytest.raises(ProvenanceError, match="Project Controls WORK provenance invalid"):
        resolve_base_work_implementation(tmp_path, _subject())


def test_branch_and_merge_base_bound_to_trusted_github_subject(tmp_path: Path) -> None:
    _case(tmp_path)
    with pytest.raises(ProvenanceError, match="stale or absent trusted merge-base"):
        resolve_base_work_implementation(tmp_path, _subject(merge_base_sha="e" * 40))
    with pytest.raises(ProvenanceError, match="merge-base is unverified"):
        resolve_base_work_implementation(tmp_path, _subject(merge_base_sha="invalid"))
    assert resolve_base_work_implementation(tmp_path, _subject(head_ref="feat/other")) is None


def test_unknown_pc_id_never_falls_back_to_dev_work(tmp_path: Path) -> None:
    with pytest.raises(ProductWorkError, match="unregistered"):
        work_path("PC-99")
    _case(tmp_path)
    assert matching_pc_assignment(tmp_path, "feat/unrelated", EXEC_BASE) is None


def test_pc_ids_not_dev_namespace_or_forged_legacy_identity() -> None:
    import jsonschema
    from scripts.development.validate_c2pro_control import SCHEMAS

    schema = yaml.safe_load((SCHEMAS / "product-work-envelope.schema.yaml").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    for task in ("PC-3", "PC-7a"):
        # Only the namespace pattern is tested here; full envelope validation
        # is exercised by the resolver and the existing schema regression.
        assert validator.schema["properties"]["task_id"]["pattern"].startswith("^(")
        assert __import__("re").fullmatch(validator.schema["properties"]["work_id"]["pattern"], task)
    assert not __import__("re").fullmatch(validator.schema["properties"]["work_id"]["pattern"], "C2PRO-DEV-14")
    assert not __import__("re").fullmatch(validator.schema["properties"]["work_id"]["pattern"], "PC-99")


def test_project_controls_registry_does_not_create_new_wbs_or_dev_task() -> None:
    from scripts.development.validate_task_trace import load_registry
    from scripts.development.validate_c2pro_control import ROOT

    registry = load_registry(ROOT)
    for task in ("PC-3", "PC-7a"):
        assert registry[task]["issue"] == 672
        assert registry[task]["acceptance_ids"] == {task}
        assert registry[task]["sdd_path"] == PC_SDD
    assert "C2PRO-DEV-14" in registry
