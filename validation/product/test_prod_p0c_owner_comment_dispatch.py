from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/prod-p0c-qualification.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_p0c_comment_authority_is_owner_and_rerun_owner_only() -> None:
    source = _source()
    job_if = source.split("if: >-", 1)[1].split("runs-on:", 1)[0]
    assert "github.event.issue.number == 686" in job_if
    assert "github.event.comment.user.login == github.repository_owner" in job_if
    assert "github.triggering_actor == github.repository_owner" in job_if
    assert "startsWith(github.event.comment.body, 'RUN-ISSUE-686 ')" in job_if


def test_p0c_owner_command_is_exactly_parsed_without_shell_interpolation() -> None:
    source = _source()
    assert "COMMENT_BODY: ${{ github.event.comment.body }}" in source
    assert 'body = os.environ["COMMENT_BODY"].strip()' in source
    assert "pattern.fullmatch(body)" in source
    assert "staged_clear=(?P<staged_clear>true)$" in source
    assert 'print(f"{key}={value}", file=output)' in source
    assert 'output.write(f"{key}={value}' not in source
    parse_block = source.split("Parse exact bounded owner command", 1)[1].split(
        "Fail closed on owner intent and bounded inputs", 1
    )[0]
    assert "${{ github.event.comment.body }}" not in parse_block.split("run: |", 1)[1]


def test_p0c_has_no_secondary_dispatch_or_token_escalation_path() -> None:
    source = _source()
    assert "workflow_dispatch:" not in source
    assert "workflow_call:" not in source
    assert "gh workflow run" not in source
    assert "GH_TOKEN" not in source
    assert "actions: write" not in source
    assert "uses: ./.github/workflows/prod-p0c-qualification.yml" not in source


def test_parsed_values_feed_the_existing_fail_closed_workflow() -> None:
    source = _source()
    for output in (
        "steps.parse.outputs.backend_sha",
        "steps.parse.outputs.backend_deployment",
        "steps.parse.outputs.frontend_sha",
        "steps.parse.outputs.frontend_deployment",
        "steps.parse.outputs.project_id",
        "steps.parse.outputs.document_id",
        "steps.parse.outputs.source_revision_id",
        "steps.parse.outputs.staged_clear",
    ):
        assert output in source
    assert "${{ inputs." not in source
