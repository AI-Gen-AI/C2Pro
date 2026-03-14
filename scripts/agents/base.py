"""Shared GitHub API client and utilities for agent swarm."""

from __future__ import annotations

import os
import zipfile
import io
from typing import Optional

from github import Github, Auth
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.WorkflowRun import WorkflowRun


def get_github_client() -> Github:
    token = os.environ["GITHUB_TOKEN"]
    return Github(auth=Auth.Token(token))


def get_repo(client: Github, repo_name: str) -> Repository:
    return client.get_repo(repo_name)


def get_pr(repo: Repository, pr_number: int) -> PullRequest:
    return repo.get_pull(pr_number)


def get_workflow_run(repo: Repository, run_id: int) -> WorkflowRun:
    return repo.get_workflow_run(run_id)


def download_workflow_logs(run: WorkflowRun) -> str:
    """Download and concatenate all job logs for a workflow run."""
    import requests

    headers = {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"}
    logs_url = run.logs_url
    response = requests.get(logs_url, headers=headers, timeout=30)
    response.raise_for_status()

    all_logs: list[str] = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        for name in zf.namelist():
            if name.endswith(".txt"):
                content = zf.read(name).decode("utf-8", errors="replace")
                all_logs.append(f"=== {name} ===\n{content}")

    return "\n\n".join(all_logs)


def get_pr_diff(repo: Repository, base_sha: str, head_sha: str) -> str:
    """Return unified diff between two commits."""
    import requests

    headers = {
        "Authorization": f"token {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.diff",
    }
    url = f"https://api.github.com/repos/{repo.full_name}/compare/{base_sha}...{head_sha}"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def create_branch_and_commit(
    repo: Repository,
    base_sha: str,
    branch_name: str,
    file_path: str,
    new_content: str,
    commit_message: str,
) -> str:
    """Create a new branch from base_sha, update file_path, and return the branch name."""
    ref = repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
    existing = repo.get_contents(file_path, ref=branch_name)
    repo.update_file(
        path=file_path,
        message=commit_message,
        content=new_content,
        sha=existing.sha,
        branch=branch_name,
    )
    return branch_name


def open_draft_pr(
    repo: Repository,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> PullRequest:
    return repo.create_pull(
        title=title,
        body=body,
        head=head_branch,
        base=base_branch,
        draft=True,
    )
