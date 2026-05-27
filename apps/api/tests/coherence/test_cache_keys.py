"""
Tests for coherence cache_keys module.

Suite ID: TS-UD-COH-CACHE-KEYS-001
References: ADR-009 §G, spec §6 (2026-05-25-ecoa-v2-hotfix-and-cutover-design.md)
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2

# Delay import to allow RED phase to fail at import
import importlib


@pytest.fixture()
def cache_keys():
    """Import cache_keys module — fails in RED phase."""
    return importlib.import_module("src.coherence.cache_keys")


TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ---------------------------------------------------------------------------
# key() happy paths
# ---------------------------------------------------------------------------


class TestKeyHappyPath:
    def test_dashboard_v1_produces_correct_string(self, cache_keys):
        result = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert result == f"coherence:{SCORE_VERSION_V1}:dashboard:{TENANT_ID}:{PROJECT_ID}"

    def test_diagnostics_v2_produces_correct_string(self, cache_keys):
        result = cache_keys.key(
            namespace="diagnostics",
            version=SCORE_VERSION_V2,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert result == f"coherence:{SCORE_VERSION_V2}:diagnostics:{TENANT_ID}:{PROJECT_ID}"

    def test_aggregate_v1_produces_correct_string(self, cache_keys):
        result = cache_keys.key(
            namespace="aggregate",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert result == f"coherence:{SCORE_VERSION_V1}:aggregate:{TENANT_ID}:{PROJECT_ID}"

    def test_export_v2_produces_correct_string(self, cache_keys):
        result = cache_keys.key(
            namespace="export",
            version=SCORE_VERSION_V2,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert result == f"coherence:{SCORE_VERSION_V2}:export:{TENANT_ID}:{PROJECT_ID}"

    def test_all_four_namespaces_produce_unique_strings(self, cache_keys):
        namespaces = ["dashboard", "diagnostics", "aggregate", "export"]
        results = [
            cache_keys.key(
                namespace=ns,
                version=SCORE_VERSION_V1,
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
            )
            for ns in namespaces
        ]
        assert len(set(results)) == 4, "All namespaces must produce distinct keys"

    def test_both_versions_produce_distinct_strings(self, cache_keys):
        v1_key = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        v2_key = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V2,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert v1_key != v2_key
        assert SCORE_VERSION_V1 in v1_key
        assert SCORE_VERSION_V2 in v2_key

    def test_suffix_appended_with_colon_separator(self, cache_keys):
        result = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            suffix="page:2",
        )
        expected = f"coherence:{SCORE_VERSION_V1}:dashboard:{TENANT_ID}:{PROJECT_ID}:page:2"
        assert result == expected

    def test_no_suffix_omits_trailing_colon(self, cache_keys):
        result = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        assert not result.endswith(":")

    def test_different_tenants_produce_different_keys(self, cache_keys):
        other_tenant = uuid4()
        k1 = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        k2 = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=other_tenant,
            project_id=PROJECT_ID,
        )
        assert k1 != k2

    def test_different_projects_produce_different_keys(self, cache_keys):
        other_project = uuid4()
        k1 = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
        )
        k2 = cache_keys.key(
            namespace="dashboard",
            version=SCORE_VERSION_V1,
            tenant_id=TENANT_ID,
            project_id=other_project,
        )
        assert k1 != k2


# ---------------------------------------------------------------------------
# key() error paths
# ---------------------------------------------------------------------------


class TestKeyErrors:
    @pytest.mark.parametrize(
        "bad_namespace",
        ["foo", "", "DASHBOARD", "admin", "cache", "v1", "v2"],
    )
    def test_unknown_namespace_raises_value_error(self, cache_keys, bad_namespace):
        with pytest.raises(ValueError, match="Unknown cache namespace"):
            cache_keys.key(
                namespace=bad_namespace,  # type: ignore[arg-type]
                version=SCORE_VERSION_V1,
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
            )

    @pytest.mark.parametrize(
        "bad_version",
        ["v0_flag_based", "v1_exponential_decay", "v1", "v2", "", "coherence_v1"],
    )
    def test_unknown_version_raises_value_error(self, cache_keys, bad_version):
        with pytest.raises(ValueError, match="Unknown score_version"):
            cache_keys.key(
                namespace="dashboard",
                version=bad_version,  # type: ignore[arg-type]
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
            )


# ---------------------------------------------------------------------------
# tenant_prefix()
# ---------------------------------------------------------------------------


class TestTenantPrefix:
    def test_v1_tenant_prefix_contains_wildcard_and_tenant(self, cache_keys):
        prefix = cache_keys.tenant_prefix(version=SCORE_VERSION_V1, tenant_id=TENANT_ID)
        assert prefix == f"coherence:{SCORE_VERSION_V1}:*:{TENANT_ID}:*"

    def test_v2_tenant_prefix_contains_wildcard_and_tenant(self, cache_keys):
        prefix = cache_keys.tenant_prefix(version=SCORE_VERSION_V2, tenant_id=TENANT_ID)
        assert prefix == f"coherence:{SCORE_VERSION_V2}:*:{TENANT_ID}:*"

    def test_unknown_version_raises_value_error(self, cache_keys):
        with pytest.raises(ValueError, match="Unknown score_version"):
            cache_keys.tenant_prefix(version="bad-version", tenant_id=TENANT_ID)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# tenant_all_versions_prefix()
# ---------------------------------------------------------------------------


class TestTenantAllVersionsPrefix:
    def test_returns_tuple_of_two_strings(self, cache_keys):
        result = cache_keys.tenant_all_versions_prefix(tenant_id=TENANT_ID)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_v1_prefix(self, cache_keys):
        v1_prefix, _ = cache_keys.tenant_all_versions_prefix(tenant_id=TENANT_ID)
        assert SCORE_VERSION_V1 in v1_prefix
        assert str(TENANT_ID) in v1_prefix

    def test_second_element_is_v2_prefix(self, cache_keys):
        _, v2_prefix = cache_keys.tenant_all_versions_prefix(tenant_id=TENANT_ID)
        assert SCORE_VERSION_V2 in v2_prefix
        assert str(TENANT_ID) in v2_prefix

    def test_both_prefixes_differ(self, cache_keys):
        v1_prefix, v2_prefix = cache_keys.tenant_all_versions_prefix(tenant_id=TENANT_ID)
        assert v1_prefix != v2_prefix


# ---------------------------------------------------------------------------
# project_prefix()
# ---------------------------------------------------------------------------


class TestProjectPrefix:
    def test_project_prefix_contains_tenant_and_project(self, cache_keys):
        prefix = cache_keys.project_prefix(tenant_id=TENANT_ID, project_id=PROJECT_ID)
        assert str(TENANT_ID) in prefix
        assert str(PROJECT_ID) in prefix

    def test_project_prefix_uses_wildcard_for_version(self, cache_keys):
        prefix = cache_keys.project_prefix(tenant_id=TENANT_ID, project_id=PROJECT_ID)
        # Must span across versions — contains wildcard
        assert "*" in prefix

    def test_project_prefix_format(self, cache_keys):
        prefix = cache_keys.project_prefix(tenant_id=TENANT_ID, project_id=PROJECT_ID)
        assert prefix == f"coherence:*:*:{TENANT_ID}:{PROJECT_ID}*"

    def test_different_projects_produce_different_prefixes(self, cache_keys):
        other = uuid4()
        p1 = cache_keys.project_prefix(tenant_id=TENANT_ID, project_id=PROJECT_ID)
        p2 = cache_keys.project_prefix(tenant_id=TENANT_ID, project_id=other)
        assert p1 != p2
