from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/prod-p0c-owner-comment-dispatch.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_dispatcher_is_issue_686_owner_only_and_actions_write_bounded() -> None:
    source = _source()
    assert "issue_comment:" in source
    assert "types: [created]" in source
    assert "actions: write" in source
    assert "contents: read" in source
    assert "github.event.issue.number == 686" in source
    assert "github.event.comment.user.login == github.repository_owner" in source
    assert "startsWith(github.event.comment.body, 'RUN-ISSUE-686 ')" in source


def test_dispatcher_parses_comment_via_environment_not_shell_interpolation() -> None:
    source = _source()
    assert "COMMENT_BODY: ${{ github.event.comment.body }}" in source
    assert 'body = os.environ["COMMENT_BODY"].strip()' in source
    assert "pattern.fullmatch(body)" in source
    assert "staged_clear=(?P<staged_clear>true)$" in source
    run_block = source.split("Dispatch governed P0c qualification workflow", 1)[1]
    assert "github.event.comment.body" not in run_block


def test_dispatcher_only_invokes_existing_governed_p0c_workflow() -> None:
    source = _source()
    assert "gh workflow run prod-p0c-qualification.yml" in source
    assert "--ref main" in source
    assert "-f confirm_production=RUN-ISSUE-686" in source
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
        assert f"-f {field}=" in source
