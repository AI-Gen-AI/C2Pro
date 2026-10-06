from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / ".github/workflows/prod-p0c-owner-comment-dispatch.yml"
TARGET = REPO_ROOT / ".github/workflows/prod-p0c-qualification.yml"


def _source() -> str:
    return DISPATCHER.read_text(encoding="utf-8")


def test_dispatcher_is_issue_686_owner_only_and_minimum_permission() -> None:
    source = _source()
    assert "issue_comment:" in source
    assert "types: [created]" in source
    assert "contents: read" in source
    assert "actions: write" not in source
    assert "github.event.issue.number == 686" in source
    assert "github.event.comment.user.login == github.repository_owner" in source
    assert "github.triggering_actor == github.repository_owner" in source
    assert "startsWith(github.event.comment.body, 'RUN-ISSUE-686 ')" in source


def test_dispatcher_rejects_non_owner_reruns() -> None:
    source = _source()
    job_if = source.split("if: >-", 1)[1].split("runs-on:", 1)[0]
    assert "github.event.comment.user.login == github.repository_owner" in job_if
    assert "github.triggering_actor == github.repository_owner" in job_if


def test_dispatcher_parses_comment_via_environment_not_shell_interpolation() -> None:
    source = _source()
    assert "COMMENT_BODY: ${{ github.event.comment.body }}" in source
    assert 'body = os.environ["COMMENT_BODY"].strip()' in source
    assert "pattern.fullmatch(body)" in source
    assert "staged_clear=(?P<staged_clear>true)$" in source
    assert "github.event.comment.body" not in source.split("qualification:", 1)[1]


def test_dispatcher_calls_reusable_workflow_without_actions_token() -> None:
    source = _source()
    assert "uses: ./.github/workflows/prod-p0c-qualification.yml" in source
    assert "needs: authorize" in source
    assert "secrets: inherit" in source
    assert "gh workflow run" not in source
    assert "GH_TOKEN" not in source
    assert "confirm_production: RUN-ISSUE-686" in source
    for field in (
        "backend_commit_sha",
        "backend_deployment_id",
        "frontend_commit_sha",
        "frontend_deployment_id",
        "project_id",
        "document_id",
        "source_revision_id",
        "railway_staged_changes_clear",
    ):
        assert f"{field}:" in source


def test_target_has_no_direct_dispatch_entrypoint() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "workflow_call:" in source
    assert "workflow_dispatch:" not in source
    assert "issue_comment:" not in source
