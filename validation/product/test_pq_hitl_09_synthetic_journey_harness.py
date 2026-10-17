"""PQ-HITL-09 specification matrix schema harness (ACC-01 / #1049 / parent PQ-HITL-09 #945).

Suite ID: TS-PQ-HITL-09-HARNESS-001.

This test suite validates the offline fixture schema and specification matrix for the
4 document families and 8 user journey scenarios. It validates that the matrix specifies
the correct formats (e.g. rejecting DOCX for structured schedules/budgets), invariants,
and explicitly certifies that live runtime acceptance remains NOT_VERIFIED until genuine
end-to-end multi-tenant UAT is executed.
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


class TestMatrixFixtureSchemaCoverage:
    """Validate matrix schema, task trace, and 4-document/8-scenario specification coverage."""

    def test_matrix_metadata_traceability(self) -> None:
        matrix = _load_matrix()
        assert matrix["schema"] == "c2pro-pq-hitl-09-multidoc-journey-matrix/v1"
        assert matrix["task_id"] == "PQ-HITL-09"
        assert matrix["issue"] == 945
        assert matrix["board_issue"] == 1049
        assert matrix["status"] == "SPECIFICATION_MATRIX_NOT_LIVE_UAT"

    def test_four_document_families_declared_and_isolated(self) -> None:
        """Validate 4 document families and their extension policies."""
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

        # Contract supports text/pdf
        assert ".pdf" in type_map["contract"]["supported_extensions"]

        # Budget PDF is uploadable as unstructured source, not XLSX row evidence.
        assert ".xlsx" in type_map["budget"]["supported_extensions"]
        assert ".bc3" in type_map["budget"]["supported_extensions"]
        assert ".pdf" in type_map["budget"]["supported_extensions"]
        assert ".pdf" not in type_map["budget"]["rejected_extensions"]
        assert "does not establish structured budget row extraction" in (
            type_map["budget"]["format_qualification"]
        )
        assert ".docx" in type_map["budget"]["rejected_extensions"]

        # Schedule is structured: supports .xlsx/.bc3, rejects .docx (Codex finding 1)
        assert ".xlsx" in type_map["schedule"]["supported_extensions"]
        assert ".bc3" in type_map["schedule"]["supported_extensions"]
        assert ".docx" in type_map["schedule"]["rejected_extensions"]

    def test_eight_scenarios_declared_with_non_empty_invariants(self) -> None:
        """Verify that all 8 scenarios are specified with required invariants."""
        matrix = _load_matrix()
        scenarios = matrix["scenarios"]
        assert len(scenarios) == 8
        step_ids = [s["step_id"] for s in scenarios]
        assert step_ids == ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

        for s in scenarios:
            assert s["invariants"], (
                f"Scenario {s['step_id']} must have explicit invariants"
            )
            assert s["specification_status"] == "SPECIFIED_IN_SCHEMA"

    def test_all_scenarios_explicitly_record_live_uat_as_not_verified(self) -> None:
        """Codex finding 2: Offline fixture checks must NOT claim live UAT acceptance."""
        matrix = _load_matrix()
        scenarios = matrix["scenarios"]
        for s in scenarios:
            assert s["live_uat_status"] == "NOT_VERIFIED", (
                f"Scenario {s['step_id']} must not claim live acceptance from fixture checks"
            )

    def test_s1_fixture_schema_invariants(self) -> None:
        """S1: Cross-tenant isolation specification invariants."""
        matrix = _load_matrix()
        s1 = next(s for s in matrix["scenarios"] if s["step_id"] == "S1")
        assert "TENANT_ISOLATION_404_ON_CROSS_ACCESS" in s1["invariants"]
        assert "NO_CREDENTIAL_OR_TOKEN_LEAKAGE" in s1["invariants"]

    def test_s2_fixture_schema_invariants(self) -> None:
        """S2: Ingestion revision addressing and structured format rejection invariants."""
        matrix = _load_matrix()
        s2 = next(s for s in matrix["scenarios"] if s["step_id"] == "S2")
        assert "CONTENT_ADDRESSED_REVISION_HASH" in s2["invariants"]
        assert "REJECT_DOCX_ON_STRUCTURED_BUDGET" in s2["invariants"]
        assert "REJECT_DOCX_ON_STRUCTURED_SCHEDULE" in s2["invariants"]
        assert "REJECT_UNSUPPORTED_EXTENSIONS_415" in s2["invariants"]

    def test_s3_fixture_schema_invariants(self) -> None:
        """S3: Health evaluates 6 canonical dimensions without fabricating zeros or green."""
        matrix = _load_matrix()
        s3 = next(s for s in matrix["scenarios"] if s["step_id"] == "S3")
        expected_dims = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}
        assert set(s3["dimension_coverage"]) == expected_dims
        assert "HONEST_NULL_ON_UNMEASURED_DIMENSION" in s3["invariants"]
        assert "NO_FABRICATED_GREEN_OR_ZERO" in s3["invariants"]
        assert "SCORE_AND_CRITICAL_ALERT_COEXISTENCE" in s3["invariants"]

    def test_s4_fixture_schema_invariants(self) -> None:
        """S4: Findings trace to verified spans without fabricating geometry."""
        matrix = _load_matrix()
        s4 = next(s for s in matrix["scenarios"] if s["step_id"] == "S4")
        assert "NO_FABRICATED_BBOX_OR_PAGE" in s4["invariants"]
        assert "FAIL_CLOSED_ON_UNVERIFIED_LOCATOR" in s4["invariants"]
        assert "DEGRADE_TO_DOCUMENT_FALLBACK_IF_SPAN_UNAVAILABLE" in s4["invariants"]

    def test_s5_fixture_schema_invariants(self) -> None:
        """S5: PROPOSED is never silently TRUSTED; settlement is atomic."""
        matrix = _load_matrix()
        s5 = next(s for s in matrix["scenarios"] if s["step_id"] == "S5")
        assert "PROPOSED_NEVER_SILENTLY_TRUSTED" in s5["invariants"]
        assert "IMMUTABLE_FINDING_LEDGER_AUDIT" in s5["invariants"]
        assert "OPTIMISTIC_CONCURRENCY_FENCE_GUARD" in s5["invariants"]

    def test_s6_fixture_schema_invariants(self) -> None:
        """S6: Temporal comparison bound to exact revisions without hallucinated deltas."""
        matrix = _load_matrix()
        s6 = next(s for s in matrix["scenarios"] if s["step_id"] == "S6")
        assert "EXACT_DELTA_A9_B7_NO_HALLUCINATION" in s6["invariants"]
        assert "CURRENT_STATE_DERIVED_FROM_ACTIVE_REVISION_ONLY" in s6["invariants"]

    def test_s7_fixture_schema_invariants(self) -> None:
        """S7: One canonical hierarchical WBS root; budget/schedule link to WBS nodes."""
        matrix = _load_matrix()
        s7 = next(s for s in matrix["scenarios"] if s["step_id"] == "S7")
        assert "ONE_CANONICAL_WBS_HIERARCHY" in s7["invariants"]
        assert "BUDGET_AND_SCHEDULE_REFERENCE_WBS_NOT_REPLACE_IT" in s7["invariants"]
        assert "NOT_ASSESSED_ON_DIFFERENT_CURRENCY_OR_TAX" in s7["invariants"]

    def test_s8_fixture_schema_invariants(self) -> None:
        """S8: Relogin persistence, cross-tenant denial, and runtime SHA check."""
        matrix = _load_matrix()
        s8 = next(s for s in matrix["scenarios"] if s["step_id"] == "S8")
        assert "PERSISTENCE_ACROSS_SESSION_CYCLES" in s8["invariants"]
        assert "CROSS_TENANT_STRICT_DENIAL" in s8["invariants"]
        assert "RUNTIME_SHA_VERIFICATION_FAIL_CLOSED" in s8["invariants"]
