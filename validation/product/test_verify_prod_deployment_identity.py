from __future__ import annotations

import copy
from pathlib import Path

import pytest

from validation.product.verify_prod_deployment_identity import (
    IdentityError,
    _output_path,
    _provider_input,
    verify,
)

BACKEND = "a" * 40
FRONTEND = "b" * 40
FRONTEND_PROJECT = "prj_c2pro"


def railway(service_id: str, *, sha: str = BACKEND, status: str = "SUCCESS"):
    return [{"id": service_id, "status": status, "meta": {"commitHash": sha}}]


def vercel(
    *,
    sha: str = FRONTEND,
    state: str = "READY",
    target: str = "production",
    project_id: str = FRONTEND_PROJECT,
):
    return {
        "uid": "dpl_frontend",
        "readyState": state,
        "target": target,
        "project": {"id": project_id},
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
        "expected_frontend_project": FRONTEND_PROJECT,
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


def test_frontend_provider_project_mismatch_fails_closed():
    with pytest.raises(IdentityError, match="project"):
        run(frontend_payload=vercel(project_id="prj_other"))


def test_frontend_project_id_flat_shape_is_supported():
    payload = vercel()
    payload.pop("project")
    payload["projectId"] = FRONTEND_PROJECT
    result = run(frontend_payload=payload)
    assert result["frontend"]["project_id"] == FRONTEND_PROJECT


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


def test_provider_inputs_are_fixed_to_canonical_evidence_root(tmp_path: Path):
    provider_root = tmp_path / "evidence/product-qualification/runtime/provider"
    provider_root.mkdir(parents=True)
    expected = provider_root / "railway-api.json"
    expected.write_text("{}", encoding="utf-8")

    assert _provider_input("railway-api.json", repo_root=tmp_path) == expected

    with pytest.raises(IdentityError, match="canonical provider evidence is missing"):
        _provider_input("missing.json", repo_root=tmp_path)


def test_deployment_identity_output_is_fixed_to_canonical_evidence_path(tmp_path: Path):
    expected = (
        tmp_path
        / "evidence/product-qualification/runtime/deployment-identity.json"
    )
    assert _output_path(repo_root=tmp_path) == expected

