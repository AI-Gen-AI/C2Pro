"""Test Suite ID: TASK-OPS-DOCFLOW-011.

Golden regression coverage for structured real-document outputs.
"""

from __future__ import annotations

from evals.run_evals import run_real_document_corpus


def test_real_document_golden_report_uses_ranges_and_alert_contracts() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-011."""

    report = run_real_document_corpus()

    assert report["mode"] == "real_document_corpus"
    assert report["total_documents"] >= 1
    assert report["failed_documents"] == 0
    assert report["schema_version"] == 1

    for document in report["documents"]:
        assert set(document) == {
            "document_id",
            "document_type",
            "filename",
            "score_check",
            "expected_score_range",
            "expected_alerts",
            "schema_keys",
        }
        assert document["score_check"] == "range"
        assert set(document["expected_score_range"]) == {"min", "max"}
        assert document["expected_score_range"]["min"] <= document["expected_score_range"]["max"]
        assert document["expected_alerts"]
        for alert in document["expected_alerts"]:
            assert set(alert) == {"category", "severity"}
            assert alert["category"] in {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}
            assert alert["severity"] in {"low", "medium", "high", "critical"}


def test_real_document_golden_report_is_tenant_safe() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-011."""

    report = run_real_document_corpus()
    forbidden_keys = {"tenant_id", "user_id", "created_by", "owner_id"}

    for document in report["documents"]:
        assert forbidden_keys.isdisjoint(document)
        assert forbidden_keys.isdisjoint(document["schema_keys"])
