#!/usr/bin/env python3
"""CLI for G2 canonical control-plane reconciliation (minimum operational G2).

This tool contains NO reconciliation logic of its own. It only:
  1. collects real Git/GitHub evidence for a work item's PR (network calls are
     isolated behind an injectable `run_fn`, so this module never fabricates
     a fact it did not read from `git`/`gh`), and
  2. feeds that evidence into one of the two existing reconciliation
     libraries:
       - `core.reconciler.reconcile_result`      -- genuine worker
         self-reports, conforming to c2pro-implementation-result-v1
         (introduced with G1, PR #597).
       - `core.legacy_closure.reconcile_legacy_closure` -- pre-schema work
         merged before that schema existed, closed on machine-derived
         evidence only. No worker result is parsed, assumed, or fabricated.

Two subcommands:

    reconcile_work.py reconcile --work-id ID --pr N --result-file PATH [--apply]
    reconcile_work.py legacy-close --work-id ID --pr N --reason TEXT [--apply]

Both default to DRY RUN: they run the real reconciliation function against a
throwaway copy of the control directory and print the exact resulting delta
(current.yaml / work-queue.yaml diffs, plus the new reconciliation-history.yaml
entry) -- with ZERO writes to the real .c2pro/control/. Pass --apply to commit
the same, already-previewed change for real.
"""
from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONTROL_DIR = REPO_ROOT / ".c2pro" / "control"
GITHUB_REPO = "AI-Gen-AI/C2Pro"

RunFn = Callable[[list[str]], str]

# core/ is importable from repo root without installation (matches how
# tests/test_g2_reconciler.py and tests/test_legacy_closure.py import it).
sys.path.insert(0, str(REPO_ROOT))

from core.legacy_closure import (  # noqa: E402
    LegacyClosureError,
    reconcile_legacy_closure,
)
from core.provenance_guard import (  # noqa: E402
    ProvenanceLossError,
    assert_no_uncovered_comment_loss,
)
from core.reconciler import ReconciliationError, reconcile_result  # noqa: E402


# ---------------------------------------------------------------------------
# Evidence collection -- the ONLY place this tool talks to git/gh.
# ---------------------------------------------------------------------------


def default_run_fn(cmd: list[str]) -> str:
    """Runs a subprocess command and returns stripped stdout. Raises on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=REPO_ROOT)
    return result.stdout.strip()


def gh_api_json(path: str, run_fn: RunFn = default_run_fn) -> dict[str, Any]:
    """Calls `gh api <path>` and parses the JSON response. No field is invented."""
    return json.loads(run_fn(["gh", "api", path]))


def collect_pr_evidence(pr_number: int, run_fn: RunFn = default_run_fn) -> dict[str, Any]:
    """Collects the remote_evidence shape expected by core.reconciler.reconcile_result."""
    pr = gh_api_json(f"repos/{GITHUB_REPO}/pulls/{pr_number}", run_fn=run_fn)
    head_sha = pr["head"]["sha"]
    merge_commit_sha = pr.get("merge_commit_sha")

    if pr.get("merged"):
        pr_state = "merged"
    elif pr.get("state") == "closed":
        pr_state = "closed_unmerged"
    else:
        pr_state = "open"

    authoritative_main_sha = run_fn(["git", "rev-parse", "origin/main"])

    main_contains_merge_commit = False
    if merge_commit_sha:
        try:
            run_fn(["git", "merge-base", "--is-ancestor", merge_commit_sha, "origin/main"])
            main_contains_merge_commit = True
        except subprocess.CalledProcessError:
            main_contains_merge_commit = False

    return {
        "branch": pr["head"]["ref"],
        "remote_head_sha": head_sha,
        "pr_head_sha": head_sha,
        "pr_base_sha": pr["base"]["sha"],
        "pr_base_branch": pr["base"]["ref"],
        "pr_state": pr_state,
        "merge_commit_sha": merge_commit_sha,
        "authoritative_main_sha": authoritative_main_sha,
        "main_contains_merge_commit": main_contains_merge_commit,
        "pr_url": pr.get("html_url"),
    }


def collect_ci_evidence(head_sha: str, run_fn: RunFn = default_run_fn) -> dict[str, Any]:
    """Collects the ci_evidence shape expected by reconcile_result, from the
    real GitHub combined commit status -- never assumed 'success'."""
    status = gh_api_json(f"repos/{GITHUB_REPO}/commits/{head_sha}/status", run_fn=run_fn)
    return {"ci_sha": head_sha, "ci_status": status.get("state")}


def collect_legacy_evidence(
    work_id: str, pr_number: int, reason: str, run_fn: RunFn = default_run_fn
) -> dict[str, Any]:
    """Collects the evidence shape expected by core.legacy_closure.reconcile_legacy_closure.

    Every field is read from `gh`/`git`; `reason` is the only caller-supplied
    text, and it is carried verbatim into `provenance.reason` for audit --
    never used to fabricate a fact this function could otherwise verify.
    """
    pr_evidence = collect_pr_evidence(pr_number, run_fn=run_fn)
    ci_evidence = collect_ci_evidence(pr_evidence["remote_head_sha"], run_fn=run_fn)

    return {
        "work_id": work_id,
        "branch": pr_evidence["branch"],
        "base_sha": pr_evidence["pr_base_sha"],
        "head_sha": pr_evidence["remote_head_sha"],
        "merge_commit_sha": pr_evidence["merge_commit_sha"],
        "authoritative_main_sha": pr_evidence["authoritative_main_sha"],
        "main_contains_merge_commit": pr_evidence["main_contains_merge_commit"],
        "pr_url": pr_evidence["pr_url"],
        "pr_state": pr_evidence["pr_state"],
        "ci_status": ci_evidence["ci_status"],
        "provenance": {
            "derived_from": [
                "git_merge_base",
                "github_pull_request_api",
                "github_commit_status_api",
            ],
            "reason": reason,
        },
    }


# ---------------------------------------------------------------------------
# Dry-run preview: run the REAL reconciliation function against a throwaway
# copy of the control directory, then diff it against the real one.
# ---------------------------------------------------------------------------


def _read_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _render_diff(label: str, before: str, after: str) -> str:
    if before == after:
        return f"--- {label}: unchanged ---\n"
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{label} (before)",
        tofile=f"{label} (after)",
    )
    return f"--- {label} ---\n" + "".join(diff)


def preview_delta(reconcile_fn: Callable[..., dict[str, Any]], control_dir: Path, **kwargs: Any) -> tuple[dict[str, Any], str]:
    """Runs `reconcile_fn(control_dir=<throwaway copy>, **kwargs)` and returns
    (result, human-readable diff of the three canonical files). Makes zero
    writes to `control_dir` itself."""
    with tempfile.TemporaryDirectory(prefix="c2pro-reconcile-preview-") as tmp:
        preview_dir = Path(tmp) / "control"
        shutil.copytree(control_dir, preview_dir)

        before = {
            name: _read_or_empty(control_dir / name)
            for name in ("current.yaml", "work-queue.yaml", "reconciliation-history.yaml")
        }

        result = reconcile_fn(control_dir=preview_dir, **kwargs)

        after = {
            name: _read_or_empty(preview_dir / name)
            for name in ("current.yaml", "work-queue.yaml", "reconciliation-history.yaml")
        }

    # Refuse to proceed (dry-run preview or real apply -- both call this
    # function first) if the rewrite would silently discard a work-queue
    # provenance comment with no existing .c2pro/evidence/<id>.yaml coverage.
    # evidence_dir is a sibling of control_dir on the REAL control directory,
    # never the throwaway copy -- provenance coverage is checked against
    # canonical state, not the preview.
    evidence_dir = control_dir.parent / "evidence"
    assert_no_uncovered_comment_loss(before["work-queue.yaml"], after["work-queue.yaml"], evidence_dir)

    diff_text = "".join(
        _render_diff(name, before[name], after[name]) for name in before
    )
    return result, diff_text


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_legacy_close(
    args: argparse.Namespace, run_fn: RunFn = default_run_fn, control_dir: Path | None = None
) -> int:
    control_dir = control_dir or DEFAULT_CONTROL_DIR

    try:
        evidence = collect_legacy_evidence(
            work_id=args.work_id, pr_number=args.pr, reason=args.reason, run_fn=run_fn
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: failed to collect evidence: {e}", file=sys.stderr)
        return 1

    try:
        result, diff_text = preview_delta(reconcile_legacy_closure, control_dir, evidence=evidence)
    except (LegacyClosureError, ProvenanceLossError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("=== DRY RUN: proposed legacy-close delta (no files written) ===")
    print(diff_text)
    print(f"Result preview: {result['status']} -- {result['message']}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to commit this exact change.")
        return 0

    print("\n=== APPLYING ===")
    try:
        real_result = reconcile_legacy_closure(evidence, control_dir=control_dir)
    except LegacyClosureError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"{real_result['status']} -- {real_result['message']}")
    return 0


def cmd_reconcile(
    args: argparse.Namespace, run_fn: RunFn = default_run_fn, control_dir: Path | None = None
) -> int:
    control_dir = control_dir or DEFAULT_CONTROL_DIR

    try:
        result_text = Path(args.result_file).read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: failed to read result file: {e}", file=sys.stderr)
        return 1

    try:
        remote_evidence = collect_pr_evidence(args.pr, run_fn=run_fn)
        ci_evidence = collect_ci_evidence(remote_evidence["remote_head_sha"], run_fn=run_fn)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: failed to collect evidence: {e}", file=sys.stderr)
        return 1

    try:
        result, diff_text = preview_delta(
            reconcile_result,
            control_dir,
            result_text=result_text,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
        )
    except (ReconciliationError, ProvenanceLossError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("=== DRY RUN: proposed reconciliation delta (no files written) ===")
    print(diff_text)
    print(f"Result preview: {result['status']} -- {result['message']}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to commit this exact change.")
        return 0

    print("\n=== APPLYING ===")
    try:
        real_result = reconcile_result(
            result_text, remote_evidence, ci_evidence, control_dir=control_dir
        )
    except ReconciliationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"{real_result['status']} -- {real_result['message']}")
    return 0


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="G2 canonical control-plane reconciliation CLI (dry-run by default)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    reconcile_p = sub.add_parser(
        "reconcile", help="Reconcile a genuine worker c2pro-implementation-result-v1 PR."
    )
    reconcile_p.add_argument("--work-id", required=True)
    reconcile_p.add_argument("--pr", type=int, required=True)
    reconcile_p.add_argument(
        "--result-file", required=True, help="File containing the fenced implementation-result YAML block."
    )
    reconcile_p.add_argument("--apply", action="store_true", help="Commit the change (default: dry-run).")

    legacy_p = sub.add_parser(
        "legacy-close",
        help="Close a pre-schema, already-merged work item using machine-derived Git/GitHub evidence only.",
    )
    legacy_p.add_argument("--work-id", required=True)
    legacy_p.add_argument("--pr", type=int, required=True)
    legacy_p.add_argument(
        "--reason", required=True, help="Why this work predates the implementation-result schema."
    )
    legacy_p.add_argument("--apply", action="store_true", help="Commit the change (default: dry-run).")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "reconcile":
        return cmd_reconcile(args)
    if args.command == "legacy-close":
        return cmd_legacy_close(args)

    parser.error(f"Unknown command: {args.command}")
    return 2  # pragma: no cover -- parser.error already exits


if __name__ == "__main__":
    raise SystemExit(main())
