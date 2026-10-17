"""PQ-HITL-09 synthetic journey harness (ACC-01 / #1049 / parent PQ-HITL-09 #945).

Suite ID: TS-PQ-HITL-09-HARNESS-001.

Acceptance test harness validating the 4-document family contracts and
8 end-to-end user journey scenarios (S1-S8) against repository invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT
    / "apps"
    / "api"
    / "tests"
    / "fixtures"
    / "pq_hitl_09_multidoc_journey_matrix_v1.json"
)


def _load_matrix() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestMatrixStructureAndGovernance:
    """Validate matrix schema, task trace, and 4-document/8-scenario coverage."""

    def test_matrix_metadata_traceability(self) -> None:
        matrix = _load_matrix()
        assert matrix["schema"] == "c2pro-pq-hitl-09-multidoc-journey-matrix/v1"
        assert matrix["task_id"] == "PQ-HITL-09"
        assert matrix["issue"] == 945
        assert matrix["board_issue"] == 1049
        assert matrix["status"] == "GOVERNED_TEST_HARNESS_NOT_PROD_MUTATION"

    def test_four_document_families_declared_and_isolated(self) -> None:
        matrix = _load_matrix()
        families = matrix["document_families"]
        assert len(families) == 4
        family_ids = {f["family_id"] for f in families}
        assert family_ids == {"DOC-FAM-01", "DOC-FAM-02", "DOC-FAM-03", "DOC-FAM-04"}

        type_map = {f["document_type"]: f for f in families}
        assert "contract" in type_map
        assert "budget" in type_map
        assert "schedule" in type_map
        assert "technical_spec" in type_map

        # Verify extension policies
        assert ".pdf" in type_map["contract"]["supported_extensions"]
        assert ".xlsx" in type_map["budget"]["supported_extensions"]
        assert ".bc3" in type_map["budget"]["supported_extensions"]
        # Critical security/parsing invariant: .docx rejected for structured budget
        assert ".docx" in type_map["budget"]["rejected_extensions"]

    def test_eight_scenarios_declared_with_non_empty_invariants(self) -> None:
        matrix = _load_matrix()
        scenarios = matrix["scenarios"]
        assert len(scenarios) == 8
        step_ids = [s["step_id"] for s in scenarios]
        assert step_ids == ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

        for s in scenarios:
            assert s["invariants"], (
                f"Scenario {s['step_id']} must have explicit invariants"
            )
            assert s["status"] in {"VERIFIED_CONTRACT", "PARTIAL", "KNOWN_DEFECT"}


class TestScenarioContracts:
    """Validate behavioral contracts for S1 through S8."""

    def test_s1_tenant_isolation_contract(self) -> None:
        """S1: Cross-tenant isolation must fail closed with 404."""
        matrix = _load_matrix()
        s1 = next(s for s in matrix["scenarios"] if s["step_id"] == "S1")
        assert "TENANT_ISOLATION_404_ON_CROSS_ACCESS" in s1["invariants"]
        assert "NO_CREDENTIAL_OR_TOKEN_LEAKAGE" in s1["invariants"]

    def test_s2_ingestion_and_content_addressing_contract(self) -> None:
        """S2: Ingestion enforces sha256 revision addressing and format boundaries."""
        matrix = _load_matrix()
        s2 = next(s for s in matrix["scenarios"] if s["step_id"] == "S2")
        assert "CONTENT_ADDRESSED_REVISION_HASH" in s2["invariants"]
        assert "REJECT_DOCX_ON_STRUCTURED_BUDGET" in s2["invariants"]
        assert "REJECT_UNSUPPORTED_EXTENSIONS_415" in s2["invariants"]

    def test_s3_health_6d_and_honest_null_contract(self) -> None:
        """S3: Health evaluates 6 canonical dimensions without fabricating zeros or green."""
        matrix = _load_matrix()
        s3 = next(s for s in matrix["scenarios"] if s["step_id"] == "S3")
        expected_dims = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}
        assert set(s3["dimension_coverage"]) == expected_dims
        assert "HONEST_NULL_ON_UNMEASURED_DIMENSION" in s3["invariants"]
        assert "NO_FABRICATED_GREEN_OR_ZERO" in s3["invariants"]
        assert "SCORE_AND_CRITICAL_ALERT_COEXISTENCE" in s3["invariants"]

    def test_s4_evidence_traceability_contract(self) -> None:
        """S4: Findings trace to verified spans without fabricating geometry."""
        matrix = _load_matrix()
        s4 = next(s for s in matrix["scenarios"] if s["step_id"] == "S4")
        assert "NO_FABRICATED_BBOX_OR_PAGE" in s4["invariants"]
        assert "FAIL_CLOSED_ON_UNVERIFIED_LOCATOR" in s4["invariants"]
        assert "DEGRADE_TO_DOCUMENT_FALLBACK_IF_SPAN_UNAVAILABLE" in s4["invariants"]

    def test_s5_hitl_granular_ledger_contract(self) -> None:
        """S5: PROPOSED is never silently TRUSTED; settlement is atomic."""
        matrix = _load_matrix()
        s5 = next(s for s in matrix["scenarios"] if s["step_id"] == "S5")
        assert "PROPOSED_NEVER_SILENTLY_TRUSTED" in s5["invariants"]
        assert "IMMUTABLE_FINDING_LEDGER_AUDIT" in s5["invariants"]
        assert "OPTIMISTIC_CONCURRENCY_FENCE_GUARD" in s5["invariants"]

    def test_s6_temporal_what_changed_contract(self) -> None:
        """S6: Temporal comparison bound to exact revisions without hallucinated deltas."""
        matrix = _load_matrix()
        s6 = next(s for s in matrix["scenarios"] if s["step_id"] == "S6")
        assert "EXACT_DELTA_A9_B7_NO_HALLUCINATION" in s6["invariants"]
        assert "CURRENT_STATE_DERIVED_FROM_ACTIVE_REVISION_ONLY" in s6["invariants"]

    def test_s7_one_approved_wbs_contract(self) -> None:
        """S7: One canonical hierarchical WBS root; budget/schedule link to WBS nodes."""
        matrix = _load_matrix()
        s7 = next(s for s in matrix["scenarios"] if s["step_id"] == "S7")
        assert "ONE_CANONICAL_WBS_HIERARCHY" in s7["invariants"]
        assert "BUDGET_AND_SCHEDULE_REFERENCE_WBS_NOT_REPLACE_IT" in s7["invariants"]
        assert "NOT_ASSESSED_ON_DIFFERENT_CURRENCY_OR_TAX" in s7["invariants"]

    def test_s8_persistence_and_runtime_verification_contract(self) -> None:
        """S8: Relogin persistence, cross-tenant denial, and runtime SHA check."""
        matrix = _load_matrix()
        s8 = next(s for s in matrix["scenarios"] if s["step_id"] == "S8")
        assert "PERSISTENCE_ACROSS_SESSION_CYCLES" in s8["invariants"]
        assert "CROSS_TENANT_STRICT_DENIAL" in s8["invariants"]
        assert "RUNTIME_SHA_VERIFICATION_FAIL_CLOSED" in s8["invariants"]
