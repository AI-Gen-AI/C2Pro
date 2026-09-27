from __future__ import annotations

import copy

import pytest

from validation.product.verify_prod_deployment_identity import IdentityError, verify

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
