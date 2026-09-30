from __future__ import annotations

import copy
from pathlib import Path

import pytest

from validation.product.verify_prod_deployment_identity import (
    IdentityError,
    _resolve_provider_input,
    _resolve_output_path,
    verify,
)

BACKEND = "a" * 40
FRONTEND = "b" * 40


def railway(service_id: str, *, sha: str = BACKEND, status: str = "SUCCESS"):
    return [{"id": service_id, "status": status, "meta": {"commitHash": sha}}]


def vercel(*, sha: str = FRONTEND, state: str = "READY", target: str = "production"):
    return {
        "uid": "dpl_frontend",
        "readyState": state,
        "target": target,
        "meta": {"githubCommitSha": sha},
    }


def run(**overrides):
    kwargs = {
        "api_payload": railway("dep_api"),
        "worker_payload": railway("dep_worker"),
        "scheduler_payload": railway("dep_scheduler"),
        "frontend_payload": vercel(),
        "expected_backend_sha": BACKEND,
        "expected_api_deployment": "dep_api",
        "expected_frontend_sha": FRONTEND,
        "expected_frontend_deployment": "dpl_frontend",
    }
    kwargs.update(overrides)
    return verify(**kwargs)


def test_provider_observation_proves_all_four_runtime_identities():
    result = run()
    assert result["backend"]["api"]["commit_sha"] == BACKEND
    assert result["backend"]["worker"]["commit_sha"] == BACKEND
    assert result["backend"]["scheduler"]["commit_sha"] == BACKEND
    assert result["frontend"]["commit_sha"] == FRONTEND


@pytest.mark.parametrize("service", ["api", "worker", "scheduler"])
def test_backend_provider_sha_mismatch_fails_closed(service):
    with pytest.raises(IdentityError, match="Git SHA mismatch"):
        run(**{f"{service}_payload": railway(f"dep_{service}", sha="c" * 40)})


def test_operator_expected_api_deployment_cannot_self_assert_observed_identity():
    with pytest.raises(IdentityError, match="deployment id"):
        run(expected_api_deployment="typed_by_operator_but_not_observed")


def test_frontend_provider_sha_mismatch_fails_closed():
    with pytest.raises(IdentityError, match="Git SHA mismatch"):
        run(frontend_payload=vercel(sha="d" * 40))


def test_frontend_provider_deployment_mismatch_fails_closed():
    with pytest.raises(IdentityError, match="deployment id"):
        run(expected_frontend_deployment="dpl_not_observed")


def test_nonproduction_frontend_fails_closed():
    with pytest.raises(IdentityError, match="production"):
        run(frontend_payload=vercel(target="preview"))


def test_nonterminal_backend_fails_closed():
    with pytest.raises(IdentityError, match="not SUCCESS"):
        run(worker_payload=railway("dep_worker", status="DEPLOYING"))


def test_missing_provider_commit_metadata_fails_closed():
    payload = copy.deepcopy(railway("dep_worker"))
    payload[0]["meta"] = {}
    with pytest.raises(IdentityError, match="metadata unavailable"):
        run(worker_payload=payload)



def test_railway_public_graphql_shapes_are_supported():
    api_graphql = {
        "data": {
            "deployment": {
                "id": "dep_api",
                "status": "SUCCESS",
                "meta": {"commitHash": BACKEND},
            }
        }
    }
    worker_graphql = {
        "data": {
            "deployments": {
                "edges": [
                    {
                        "node": {
                            "id": "dep_worker",
                            "status": "SUCCESS",
                            "meta": {"commitHash": BACKEND},
                        }
                    }
                ]
            }
        }
    }
    scheduler_graphql = {
        "data": {
            "deployments": {
                "edges": [
                    {
                        "node": {
                            "id": "dep_scheduler",
                            "status": "SUCCESS",
                            "meta": {"commitHash": BACKEND},
                        }
                    }
                ]
            }
        }
    }

    result = run(
        api_payload=api_graphql,
        worker_payload=worker_graphql,
        scheduler_payload=scheduler_graphql,
    )
    assert result["backend"]["api"]["deployment_id"] == "dep_api"
    assert result["backend"]["worker"]["deployment_id"] == "dep_worker"
    assert result["backend"]["scheduler"]["deployment_id"] == "dep_scheduler"


def test_provider_payload_paths_are_bounded_to_canonical_evidence_root(tmp_path: Path):
    provider_root = tmp_path / "evidence/product-qualification/runtime/provider"
    provider_root.mkdir(parents=True)
    allowed = provider_root / "railway-api.json"
    allowed.write_text("{}", encoding="utf-8")

    assert (
        _resolve_provider_input(
            str(allowed),
            expected_name="railway-api.json",
            repo_root=tmp_path,
        )
        == allowed
    )

    with pytest.raises(IdentityError, match="canonical provider evidence"):
        _resolve_provider_input(
            str(tmp_path / "outside.json"),
            expected_name="railway-api.json",
            repo_root=tmp_path,
        )


def test_deployment_identity_output_is_exact_canonical_evidence_path(tmp_path: Path):
    allowed = (
        tmp_path
        / "evidence/product-qualification/runtime/deployment-identity.json"
    )
    allowed.parent.mkdir(parents=True)

    assert _resolve_output_path(str(allowed), repo_root=tmp_path) == allowed

    with pytest.raises(IdentityError, match="canonical deployment identity output"):
        _resolve_output_path(str(tmp_path / "outside.json"), repo_root=tmp_path)
