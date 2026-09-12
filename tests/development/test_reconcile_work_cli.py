"""TDD tests for the G2 reconciliation CLI (scripts/development/reconcile_work.py).

The CLI is a thin wrapper: it collects Git/GitHub evidence (via an injectable
`run_fn` so tests never touch the network) and feeds it to the existing
`core.reconciler.reconcile_result` (genuine worker results) or
`core.legacy_closure.reconcile_legacy_closure` (pre-schema, machine-derived
closures) libraries. It contains no reconciliation logic of its own.

Every mutating path is dry-run by default and only writes when --apply is
passed. Dry-run must make zero filesystem writes to the real control
directory and must show the exact proposed delta.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "development"))

import reconcile_work  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def control_dir(tmp_path):
    d = tmp_path / ".c2pro" / "control"
    d.mkdir(parents=True, exist_ok=True)

    wq_data = {
        "schema": "c2pro-work-queue-v1",
        "schema_version": 1,
        "queue_policy": {
            "open_only": True,
            "completed_items_forbidden": True,
            "historical_source": "git_pr_ci_evidence",
        },
        "items": [
            {
                "work_id": "C2PRO-DEV-02",
                "status": "in_progress",
                "role": "orchestrator",
                "work_ref": ".c2pro/work/C2PRO-DEV-02.yaml",
                "priority": "P0",
                "depends_on": [],
                "review_policy": "principal_and_challenger",
            }
        ],
    }
    with open(d / "work-queue.yaml", "w", encoding="utf-8") as f:
        yaml.dump(wq_data, f)

    current_data = {
        "schema": "c2pro-current-v1",
        "schema_version": 1,
        "baseline": {"main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d"},
        "active_work": ["C2PRO-DEV-02"],
    }
    with open(d / "current.yaml", "w", encoding="utf-8") as f:
        yaml.dump(current_data, f)

    return d


def _fake_run_fn(responses: dict[tuple, str]):
    """Builds a run_fn(cmd: list[str]) -> str stub from a {tuple(cmd): output} map."""

    def _run(cmd: list[str]) -> str:
        key = tuple(cmd)
        if key not in responses:
            raise AssertionError(f"Unexpected command in test: {cmd}")
        return responses[key]

    return _run


DEV02_PR_JSON = json.dumps(
    {
        "merged": True,
        "state": "closed",
        "base": {"ref": "main", "sha": "3fa846d60cecd14239ddb0a953be5e34bede463d"},
        "head": {"ref": "feat/c2pro-dev-02-role-authority-v1", "sha": "f633d5ea22fd4f464b290fe36bc4891563efa1ef"},
        "merge_commit_sha": "0400c05e8af1458aaa14bc47a8378d9cdd560284",
        "html_url": "https://github.com/AI-Gen-AI/C2Pro/pull/564",
    }
)
DEV02_STATUS_JSON = json.dumps({"state": "success", "total_count": 1})


def _dev02_fake_run_fn(main_sha="32eba9431ddaab198088a09fe9294ae5ecc38318"):
    return _fake_run_fn(
        {
            ("gh", "api", "repos/AI-Gen-AI/C2Pro/pulls/564"): DEV02_PR_JSON,
            (
                "gh",
                "api",
                "repos/AI-Gen-AI/C2Pro/commits/f633d5ea22fd4f464b290fe36bc4891563efa1ef/status",
            ): DEV02_STATUS_JSON,
            ("git", "rev-parse", "origin/main"): main_sha,
            (
                "git",
                "merge-base",
                "--is-ancestor",
                "0400c05e8af1458aaa14bc47a8378d9cdd560284",
                "origin/main",
            ): "",
        }
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parser_requires_a_subcommand():
    parser = reconcile_work.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_legacy_close_requires_pr_and_reason():
    parser = reconcile_work.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["legacy-close", "--work-id", "C2PRO-DEV-02"])

    args = parser.parse_args(
        ["legacy-close", "--work-id", "C2PRO-DEV-02", "--pr", "564", "--reason", "predates schema"]
    )
    assert args.command == "legacy-close"
    assert args.pr == 564
    assert args.apply is False


def test_parser_reconcile_requires_pr_and_result_file():
    parser = reconcile_work.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["reconcile", "--work-id", "C2PRO-DEV-02"])


# ---------------------------------------------------------------------------
# Evidence collection (pure functions, network replaced by fake run_fn)
# ---------------------------------------------------------------------------


def test_collect_pr_evidence_uses_only_gh_and_git():
    evidence = reconcile_work.collect_pr_evidence(564, run_fn=_dev02_fake_run_fn())
    assert evidence["branch"] == "feat/c2pro-dev-02-role-authority-v1"
    assert evidence["remote_head_sha"] == "f633d5ea22fd4f464b290fe36bc4891563efa1ef"
    assert evidence["pr_base_sha"] == "3fa846d60cecd14239ddb0a953be5e34bede463d"
    assert evidence["pr_state"] == "merged"
    assert evidence["merge_commit_sha"] == "0400c05e8af1458aaa14bc47a8378d9cdd560284"
    assert evidence["authoritative_main_sha"] == "32eba9431ddaab198088a09fe9294ae5ecc38318"
    assert evidence["main_contains_merge_commit"] is True


def test_collect_legacy_evidence_carries_explicit_provenance():
    evidence = reconcile_work.collect_legacy_evidence(
        work_id="C2PRO-DEV-02",
        pr_number=564,
        reason="PR #564 merged 2026-08-24, predates the c2pro-implementation-result-v1 schema.",
        run_fn=_dev02_fake_run_fn(),
    )
    assert evidence["work_id"] == "C2PRO-DEV-02"
    assert evidence["head_sha"] == "f633d5ea22fd4f464b290fe36bc4891563efa1ef"
    assert evidence["pr_state"] == "merged"
    assert evidence["ci_status"] == "success"
    assert "schema" not in evidence  # never declares c2pro-implementation-result-v1
    assert "github_pull_request_api" in evidence["provenance"]["derived_from"]
    assert "predates the c2pro-implementation-result-v1 schema" in evidence["provenance"]["reason"]


# ---------------------------------------------------------------------------
# legacy-close command: dry-run vs apply
# ---------------------------------------------------------------------------


def test_legacy_close_dry_run_shows_delta_and_makes_no_mutation(control_dir, capsys):
    wq_before = (control_dir / "work-queue.yaml").read_text(encoding="utf-8")
    current_before = (control_dir / "current.yaml").read_text(encoding="utf-8")
    history_path = control_dir / "reconciliation-history.yaml"
    assert not history_path.exists()

    args = reconcile_work.build_parser().parse_args(
        [
            "legacy-close",
            "--work-id",
            "C2PRO-DEV-02",
            "--pr",
            "564",
            "--reason",
            "predates the c2pro-implementation-result-v1 schema",
        ]
    )
    exit_code = reconcile_work.cmd_legacy_close(
        args, run_fn=_dev02_fake_run_fn(), control_dir=control_dir
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "DRY RUN" in captured.out
    assert "3fa846d60cecd14239ddb0a953be5e34bede463d" in captured.out
    assert "32eba9431ddaab198088a09fe9294ae5ecc38318" in captured.out
    assert "C2PRO-DEV-02" in captured.out
    assert "LEGACY_CLOSED" in captured.out

    # Zero mutation of the real control directory.
    assert (control_dir / "work-queue.yaml").read_text(encoding="utf-8") == wq_before
    assert (control_dir / "current.yaml").read_text(encoding="utf-8") == current_before
    assert not history_path.exists()
    assert not (control_dir / "reconciliation-transaction.yaml").exists()


def test_legacy_close_apply_mutates_real_control_dir(control_dir, capsys):
    args = reconcile_work.build_parser().parse_args(
        [
            "legacy-close",
            "--work-id",
            "C2PRO-DEV-02",
            "--pr",
            "564",
            "--reason",
            "predates the c2pro-implementation-result-v1 schema",
            "--apply",
        ]
    )
    exit_code = reconcile_work.cmd_legacy_close(
        args, run_fn=_dev02_fake_run_fn(), control_dir=control_dir
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "LEGACY_CLOSED" in captured.out
    assert "DRY RUN" not in captured.out.split("APPLYING")[-1]

    with open(control_dir / "work-queue.yaml", encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    assert wq["items"] == []

    with open(control_dir / "current.yaml", encoding="utf-8") as f:
        current = yaml.safe_load(f)
    assert current["baseline"]["main_sha"] == "32eba9431ddaab198088a09fe9294ae5ecc38318"
    assert current["active_work"] == []

    with open(control_dir / "reconciliation-history.yaml", encoding="utf-8") as f:
        history = yaml.safe_load(f)
    assert history["completed_work"]["C2PRO-DEV-02"]["closure_type"] == "legacy_machine_derived"


def test_legacy_close_blocked_by_uncovered_provenance_loss(control_dir, capsys):
    """A work-queue.yaml comment about to be silently stripped, with no
    .c2pro/evidence/<id>.yaml coverage, must block the reconciliation --
    dry-run or apply -- rather than lose it."""
    wq_path = control_dir / "work-queue.yaml"
    with open(wq_path, encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    wq["items"].append({"work_id": "C2PRO-DEV-99", "status": "ready"})
    raw = yaml.dump(wq, sort_keys=False)
    # Inject a hand-written provenance comment ahead of the new item, exactly
    # like the real DEV-DEBT comments in the live work-queue.yaml.
    raw = raw.replace(
        "- work_id: C2PRO-DEV-99\n",
        "# DEV-DEBT: registered for a reason that lives only in this comment.\n"
        "- work_id: C2PRO-DEV-99\n",
    )
    wq_path.write_text(raw, encoding="utf-8")
    wq_before = wq_path.read_text(encoding="utf-8")

    args = reconcile_work.build_parser().parse_args(
        ["legacy-close", "--work-id", "C2PRO-DEV-02", "--pr", "564", "--reason", "n/a"]
    )
    exit_code = reconcile_work.cmd_legacy_close(
        args, run_fn=_dev02_fake_run_fn(), control_dir=control_dir
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ERROR" in captured.err
    assert "C2PRO-DEV-99" in captured.err
    assert wq_path.read_text(encoding="utf-8") == wq_before


def test_legacy_close_succeeds_once_provenance_evidence_exists(control_dir, capsys):
    """The same comment loss is accepted once a c2pro-evidence-reference-v1
    file with a summary already preserves the meaning."""
    wq_path = control_dir / "work-queue.yaml"
    with open(wq_path, encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    wq["items"].append({"work_id": "C2PRO-DEV-99", "status": "ready"})
    raw = yaml.dump(wq, sort_keys=False)
    raw = raw.replace(
        "- work_id: C2PRO-DEV-99\n",
        "# DEV-DEBT: registered for a reason that lives only in this comment.\n"
        "- work_id: C2PRO-DEV-99\n",
    )
    wq_path.write_text(raw, encoding="utf-8")

    evidence_dir = control_dir.parent / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with open(evidence_dir / "C2PRO-DEV-99.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "schema": "c2pro-evidence-reference-v1",
                "schema_version": 1,
                "work_id": "C2PRO-DEV-99",
                "status": "collecting",
                "references": [
                    {
                        "kind": "audit",
                        "locator": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                        "immutable": True,
                        "summary": "registered for a reason that lives only in this comment.",
                    }
                ],
            },
            f,
        )

    args = reconcile_work.build_parser().parse_args(
        ["legacy-close", "--work-id", "C2PRO-DEV-02", "--pr", "564", "--reason", "n/a"]
    )
    exit_code = reconcile_work.cmd_legacy_close(
        args, run_fn=_dev02_fake_run_fn(), control_dir=control_dir
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "LEGACY_CLOSED" in captured.out


def test_legacy_close_invalid_evidence_exits_nonzero_without_mutation(control_dir, capsys):
    """A PR that is still open must never be legacy-closed -- fail loudly, mutate nothing."""
    open_pr_json = json.dumps(
        {
            "merged": False,
            "state": "open",
            "base": {"ref": "main", "sha": "3fa846d60cecd14239ddb0a953be5e34bede463d"},
            "head": {"ref": "feat/c2pro-dev-02-role-authority-v1", "sha": "f633d5ea22fd4f464b290fe36bc4891563efa1ef"},
            "merge_commit_sha": None,
            "html_url": "https://github.com/AI-Gen-AI/C2Pro/pull/564",
        }
    )
    run_fn = _fake_run_fn(
        {
            ("gh", "api", "repos/AI-Gen-AI/C2Pro/pulls/564"): open_pr_json,
            ("git", "rev-parse", "origin/main"): "32eba9431ddaab198088a09fe9294ae5ecc38318",
            (
                "gh",
                "api",
                "repos/AI-Gen-AI/C2Pro/commits/f633d5ea22fd4f464b290fe36bc4891563efa1ef/status",
            ): json.dumps({"state": "pending", "total_count": 0}),
        }
    )
    wq_before = (control_dir / "work-queue.yaml").read_text(encoding="utf-8")

    args = reconcile_work.build_parser().parse_args(
        ["legacy-close", "--work-id", "C2PRO-DEV-02", "--pr", "564", "--reason", "n/a", "--apply"]
    )
    exit_code = reconcile_work.cmd_legacy_close(args, run_fn=run_fn, control_dir=control_dir)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ERROR" in captured.out or "ERROR" in captured.err
    assert (control_dir / "work-queue.yaml").read_text(encoding="utf-8") == wq_before
    assert not (control_dir / "reconciliation-history.yaml").exists()


# ---------------------------------------------------------------------------
# reconcile command (genuine worker result path): dry-run vs apply
# ---------------------------------------------------------------------------

VALID_WORKER_RESULT = """
```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-02
base_sha: 3fa846d60cecd14239ddb0a953be5e34bede463d
head_sha: 7c3a8347a5bea0c28f2e540559bd515f9afd282a
branch: feat/c2pro-dev-02-role-authority-v1
files_changed:
  - core/supervisor.py
tests:
  - name: test_single_writer_control_plane
    status: PASS
ci_status: success
findings: []
residual_risks: []
recommendation: approve
pr_url: https://github.com/AI-Gen-AI/C2Pro/pull/597
```
"""


def _worker_result_fake_run_fn():
    pr_json = json.dumps(
        {
            "merged": True,
            "state": "closed",
            "base": {"ref": "main", "sha": "3fa846d60cecd14239ddb0a953be5e34bede463d"},
            "head": {
                "ref": "feat/c2pro-dev-02-role-authority-v1",
                "sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
            },
            "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
            "html_url": "https://github.com/AI-Gen-AI/C2Pro/pull/597",
        }
    )
    status_json = json.dumps({"state": "success", "total_count": 1})
    return _fake_run_fn(
        {
            ("gh", "api", "repos/AI-Gen-AI/C2Pro/pulls/597"): pr_json,
            (
                "gh",
                "api",
                "repos/AI-Gen-AI/C2Pro/commits/7c3a8347a5bea0c28f2e540559bd515f9afd282a/status",
            ): status_json,
            ("git", "rev-parse", "origin/main"): "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
            (
                "git",
                "merge-base",
                "--is-ancestor",
                "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
                "origin/main",
            ): "",
        }
    )


def test_reconcile_dry_run_then_apply(control_dir, tmp_path, capsys):
    result_file = tmp_path / "result.md"
    result_file.write_text(VALID_WORKER_RESULT, encoding="utf-8")

    args = reconcile_work.build_parser().parse_args(
        [
            "reconcile",
            "--work-id",
            "C2PRO-DEV-02",
            "--pr",
            "597",
            "--result-file",
            str(result_file),
        ]
    )
    exit_code = reconcile_work.cmd_reconcile(
        args, run_fn=_worker_result_fake_run_fn(), control_dir=control_dir
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "DRY RUN" in captured.out
    assert "RECONCILED" in captured.out
    # dry-run: no mutation
    assert not (control_dir / "reconciliation-history.yaml").exists()

    args.apply = True
    exit_code = reconcile_work.cmd_reconcile(
        args, run_fn=_worker_result_fake_run_fn(), control_dir=control_dir
    )
    assert exit_code == 0
    with open(control_dir / "work-queue.yaml", encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    assert wq["items"] == []
