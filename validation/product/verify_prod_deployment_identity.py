#!/usr/bin/env python3
"""Fail-closed provider deployment identity verifier for #715.

Consumes provider JSON captured read-only by the workflow. No provider token
or credential is ever accepted or emitted by this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_EVIDENCE_ROOT = Path("evidence/product-qualification/runtime/provider")
DEPLOYMENT_IDENTITY_OUTPUT = Path(
    "evidence/product-qualification/runtime/deployment-identity.json"
)


class IdentityError(RuntimeError):
    pass


def _resolve_provider_input(
    raw: str, *, expected_name: str, repo_root: Path = REPO_ROOT
) -> Path:
    root = repo_root.resolve()
    expected = (root / PROVIDER_EVIDENCE_ROOT / expected_name).resolve()
    supplied = Path(raw)
    candidate = (supplied if supplied.is_absolute() else root / supplied).resolve()
    if candidate != expected or not candidate.is_file():
        raise IdentityError("provider JSON must use canonical provider evidence")
    return candidate


def _resolve_output_path(raw: str, *, repo_root: Path = REPO_ROOT) -> Path:
    root = repo_root.resolve()
    expected = (root / DEPLOYMENT_IDENTITY_OUTPUT).resolve()
    supplied = Path(raw)
    candidate = (supplied if supplied.is_absolute() else root / supplied).resolve()
    if candidate != expected:
        raise IdentityError("output-json must use canonical deployment identity output")
    return candidate


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _deployments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        # Railway public GraphQL responses.
        data = payload.get("data")
        if isinstance(data, dict):
            single = data.get("deployment")
            if isinstance(single, dict):
                return [single]
            connection = data.get("deployments")
            if isinstance(connection, dict):
                edges = connection.get("edges")
                if isinstance(edges, list):
                    return [
                        edge["node"]
                        for edge in edges
                        if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
                    ]
        # Provider-normalized fixtures / future bounded adapters.
        rows = payload.get("deployments")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise IdentityError("provider deployment payload has no deployments list")


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
    commit = str(
        meta.get("githubCommitSha")
        or meta.get("githubCommitSHA")
        or meta.get("gitCommitSha")
        or ""
    ).lower()
    if not deployment_id:
        raise IdentityError("Vercel: deployment id missing")
    if state != "READY":
        raise IdentityError("Vercel: deployment is not READY")
    if target != "production":
        raise IdentityError("Vercel: deployment is not production target")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise IdentityError("Vercel: exact Git commit metadata unavailable")
    return {"deployment_id": deployment_id, "commit_sha": commit, "status": state}


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
    if vercel["commit_sha"] != frontend:
        raise IdentityError("Vercel: Git SHA mismatch")

    return {
        "backend": {
            "expected_commit_sha": backend,
            "api": api,
            "worker": worker,
            "scheduler": scheduler,
        },
        "frontend": {
            "expected_commit_sha": frontend,
            **vercel,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--railway-api-json", required=True)
    parser.add_argument("--railway-worker-json", required=True)
    parser.add_argument("--railway-scheduler-json", required=True)
    parser.add_argument("--vercel-json", required=True)
    parser.add_argument("--expected-backend-sha", required=True)
    parser.add_argument("--expected-api-deployment", required=True)
    parser.add_argument("--expected-frontend-sha", required=True)
    parser.add_argument("--expected-frontend-deployment", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    result = verify(
        api_payload=_load(
            _resolve_provider_input(
                args.railway_api_json, expected_name="railway-api.json"
            )
        ),
        worker_payload=_load(
            _resolve_provider_input(
                args.railway_worker_json, expected_name="railway-worker.json"
            )
        ),
        scheduler_payload=_load(
            _resolve_provider_input(
                args.railway_scheduler_json, expected_name="railway-scheduler.json"
            )
        ),
        frontend_payload=_load(
            _resolve_provider_input(
                args.vercel_json, expected_name="vercel-frontend.json"
            )
        ),
        expected_backend_sha=args.expected_backend_sha,
        expected_api_deployment=args.expected_api_deployment,
        expected_frontend_sha=args.expected_frontend_sha,
        expected_frontend_deployment=args.expected_frontend_deployment,
    )
    output = _resolve_output_path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("production deployment identities verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
