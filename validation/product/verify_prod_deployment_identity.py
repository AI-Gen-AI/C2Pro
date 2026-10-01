#!/usr/bin/env python3
"""Fail-closed provider deployment identity verifier for #715.

Consumes provider JSON captured read-only by the workflow. No provider token
or credential is ever accepted or emitted by this script.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_EVIDENCE_ROOT = Path("evidence/product-qualification/runtime/provider")
DEPLOYMENT_IDENTITY_OUTPUT = Path(
    "evidence/product-qualification/runtime/deployment-identity.json"
)


class IdentityError(RuntimeError):
    pass


def _provider_input(expected_name: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """Return one canonical provider evidence input."""
    path = repo_root.resolve() / PROVIDER_EVIDENCE_ROOT / expected_name
    if not path.is_file():
        raise IdentityError("canonical provider evidence is missing")
    return path


def _output_path(*, repo_root: Path = REPO_ROOT) -> Path:
    """Return the single canonical deployment identity output."""
    return repo_root.resolve() / DEPLOYMENT_IDENTITY_OUTPUT


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dict_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _graphql_deployments(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    single = data.get("deployment")
    if isinstance(single, dict):
        return [single]

    service_instance = data.get("serviceInstance")
    if isinstance(service_instance, dict):
        latest = service_instance.get("latestDeployment")
        if isinstance(latest, dict):
            return [latest]

    connection = data.get("deployments")
    if not isinstance(connection, dict):
        return []

    edges = connection.get("edges")
    if not isinstance(edges, list):
        return []

    return [
        edge["node"]
        for edge in edges
        if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
    ]


def _deployments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = _dict_rows(payload)
    elif isinstance(payload, dict):
        rows = _graphql_deployments(payload.get("data"))
        if not rows:
            rows = _dict_rows(payload.get("deployments"))
    else:
        rows = []

    if not rows:
        raise IdentityError("provider deployment payload has no deployments list")
    return rows


def _railway_latest(payload: Any, *, service: str) -> dict[str, str]:
    rows = _deployments(payload)
    if not rows:
        raise IdentityError(f"Railway {service}: no deployment observed")
    row = rows[0]
    deployment_id = str(row.get("id") or "")
    status = str(row.get("status") or "").upper()
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    commit = str(
        meta.get("commitHash")
        or meta.get("commit_hash")
        or row.get("commitHash")
        or ""
    ).lower()
    if not deployment_id:
        raise IdentityError(f"Railway {service}: deployment id missing")
    if status != "SUCCESS":
        raise IdentityError(f"Railway {service}: latest deployment is not SUCCESS")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise IdentityError(f"Railway {service}: exact Git commit metadata unavailable")
    return {"deployment_id": deployment_id, "commit_sha": commit, "status": status}


def _vercel(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise IdentityError("Vercel deployment payload is not an object")
    deployment_id = str(payload.get("uid") or payload.get("id") or "")
    state = str(
        payload.get("readyState")
        or payload.get("state")
        or payload.get("status")
        or ""
    ).upper()
    target = str(payload.get("target") or "").lower()
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    project_id = str(project.get("id") or payload.get("projectId") or "")
    commit = str(
        meta.get("githubCommitSha")
        or meta.get("githubCommitSHA")
        or meta.get("gitCommitSha")
        or ""
    ).lower()
    if not deployment_id:
        raise IdentityError("Vercel: deployment id missing")
    if not project_id:
        raise IdentityError("Vercel: project identity missing")
    if state != "READY":
        raise IdentityError("Vercel: deployment is not READY")
    if target != "production":
        raise IdentityError("Vercel: deployment is not production target")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise IdentityError("Vercel: exact Git commit metadata unavailable")
    return {
        "deployment_id": deployment_id,
        "project_id": project_id,
        "commit_sha": commit,
        "status": state,
    }


def verify(
    *,
    api_payload: Any,
    worker_payload: Any,
    scheduler_payload: Any,
    frontend_payload: Any,
    expected_backend_sha: str,
    expected_api_deployment: str,
    expected_frontend_sha: str,
    expected_frontend_deployment: str,
    expected_frontend_project: str,
) -> dict[str, Any]:
    backend = expected_backend_sha.lower()
    frontend = expected_frontend_sha.lower()
    if len(backend) != 40 or len(frontend) != 40:
        raise IdentityError("expected Git SHAs must be full 40-character values")

    api = _railway_latest(api_payload, service="api")
    worker = _railway_latest(worker_payload, service="worker")
    scheduler = _railway_latest(scheduler_payload, service="scheduler")
    vercel = _vercel(frontend_payload)

    if api["deployment_id"] != expected_api_deployment:
        raise IdentityError("Railway API deployment id does not match expected release")
    for service, observed in (
        ("api", api),
        ("worker", worker),
        ("scheduler", scheduler),
    ):
        if observed["commit_sha"] != backend:
            raise IdentityError(f"Railway {service}: Git SHA mismatch")

    if vercel["deployment_id"] != expected_frontend_deployment:
        raise IdentityError("Vercel deployment id does not match expected release")
    if vercel["project_id"] != expected_frontend_project:
        raise IdentityError("Vercel deployment does not belong to expected project")
    if vercel["commit_sha"] != frontend:
        raise IdentityError("Vercel: Git SHA mismatch")

    return {
        "backend": {
            "api": api,
            "worker": worker,
            "scheduler": scheduler,
        },
        "frontend": vercel,
    }


FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
VERCEL_DEPLOYMENT_RE = re.compile(r"^dpl_[A-Za-z0-9]{20,64}$")
VERCEL_PROJECT_RE = re.compile(r"^prj_[A-Za-z0-9]{8,64}$")


def _full_sha_arg(raw: str) -> str:
    if not FULL_SHA_RE.fullmatch(raw):
        raise argparse.ArgumentTypeError("must be a full 40-character Git SHA")
    return raw.lower()


def _railway_deployment_arg(raw: str) -> str:
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a Railway deployment UUID") from exc


def _vercel_deployment_arg(raw: str) -> str:
    if not VERCEL_DEPLOYMENT_RE.fullmatch(raw):
        raise argparse.ArgumentTypeError("must be a Vercel deployment id")
    return raw


def _vercel_project_arg(raw: str) -> str:
    if not VERCEL_PROJECT_RE.fullmatch(raw):
        raise argparse.ArgumentTypeError("must be a Vercel project id")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-backend-sha", required=True, type=_full_sha_arg)
    parser.add_argument(
        "--expected-api-deployment",
        required=True,
        type=_railway_deployment_arg,
    )
    parser.add_argument("--expected-frontend-sha", required=True, type=_full_sha_arg)
    parser.add_argument(
        "--expected-frontend-deployment",
        required=True,
        type=_vercel_deployment_arg,
    )
    parser.add_argument(
        "--expected-frontend-project",
        required=True,
        type=_vercel_project_arg,
    )
    args = parser.parse_args()

    result = verify(
        api_payload=_load(_provider_input("railway-api.json")),
        worker_payload=_load(_provider_input("railway-worker.json")),
        scheduler_payload=_load(_provider_input("railway-scheduler.json")),
        frontend_payload=_load(_provider_input("vercel-frontend.json")),
        expected_backend_sha=args.expected_backend_sha,
        expected_api_deployment=args.expected_api_deployment,
        expected_frontend_sha=args.expected_frontend_sha,
        expected_frontend_deployment=args.expected_frontend_deployment,
        expected_frontend_project=args.expected_frontend_project,
    )
    output = _output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("production deployment identities verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
