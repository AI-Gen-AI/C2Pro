"""TDD tests for product-control git-truth drift detection (G2 continuation, Task 4).

`production_position.reconciled_against_main_sha` is a point-in-time
reconciliation snapshot, not a live pointer -- being behind the current
`origin/main` tip is normal and expected. What is NOT normal is the recorded
SHA being invalid or not an ancestor of main at all (a typo, a rewritten
history, or a diverged reference). These tests exercise that check with an
injectable `run_fn` so no test touches the network; a network call happens
only when this module's own `default_git_run_fn` is exercised.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import check_control_parity as c  # noqa: E402


def _run_fn(responses: dict[tuple, str | Exception]):
    def _run(cmd: list[str]) -> str:
        key = tuple(cmd)
        if key not in responses:
            raise AssertionError(f"Unexpected command: {cmd}")
        value = responses[key]
        if isinstance(value, Exception):
            raise value
        return value

    return _run


def test_valid_ancestor_sha_produces_no_problems():
    doc = {"production_position": {"reconciled_against_main_sha": "abc123"}}
    run_fn = _run_fn(
        {
            ("git", "cat-file", "-e", "abc123^{commit}"): "",
            ("git", "merge-base", "--is-ancestor", "abc123", "origin/main"): "",
        }
    )
    assert c.validate_reconciled_sha_against_git(doc, run_fn=run_fn) == []


def test_missing_sha_is_a_problem():
    doc = {"production_position": {}}
    problems = c.validate_reconciled_sha_against_git(doc, run_fn=_run_fn({}))
    assert any("missing" in p for p in problems), problems


def test_invalid_sha_is_a_problem():
    doc = {"production_position": {"reconciled_against_main_sha": "not-a-real-commit"}}
    run_fn = _run_fn(
        {
            ("git", "cat-file", "-e", "not-a-real-commit^{commit}"): subprocess.CalledProcessError(1, []),
        }
    )
    problems = c.validate_reconciled_sha_against_git(doc, run_fn=run_fn)
    assert any("does not resolve to a real commit" in p for p in problems), problems


def test_diverged_sha_is_a_problem():
    doc = {"production_position": {"reconciled_against_main_sha": "deadbeef"}}
    run_fn = _run_fn(
        {
            ("git", "cat-file", "-e", "deadbeef^{commit}"): "",
            ("git", "merge-base", "--is-ancestor", "deadbeef", "origin/main"): subprocess.CalledProcessError(1, []),
        }
    )
    problems = c.validate_reconciled_sha_against_git(doc, run_fn=run_fn)
    assert any("NOT an ancestor" in p for p in problems), problems


def test_stale_but_valid_sha_is_not_a_problem():
    """Being behind main is expected for a reconciliation snapshot -- never fails."""
    doc = {"production_position": {"reconciled_against_main_sha": "stale_sha"}}
    run_fn = _run_fn(
        {
            ("git", "cat-file", "-e", "stale_sha^{commit}"): "",
            ("git", "merge-base", "--is-ancestor", "stale_sha", "origin/main"): "",
        }
    )
    assert c.validate_reconciled_sha_against_git(doc, run_fn=run_fn) == []


def test_report_reconciliation_staleness_counts_commits_behind():
    doc = {"production_position": {"reconciled_against_main_sha": "stale_sha"}}
    run_fn = _run_fn({("git", "rev-list", "--count", "stale_sha..origin/main"): "4"})
    report = c.report_reconciliation_staleness(doc, run_fn=run_fn)
    assert "4 commits ahead" in report


def test_real_product_control_sha_is_a_valid_ancestor_of_origin_main():
    """Regression against the real repo: whatever the recorded reconciliation
    SHA is, it must be a genuine, reachable commit -- proves the checker
    works end-to-end with real git, not just fakes."""
    doc = c.load_yaml()
    problems = c.validate_reconciled_sha_against_git(doc)
    assert problems == [], problems
