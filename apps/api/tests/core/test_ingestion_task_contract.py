"""
TS-INT-DOC-PROC-002: Ingestion task contract tests.
"""

from __future__ import annotations

from src.core.tasks.ingestion_tasks import _build_processing_details


def test_build_processing_details_marks_parsed_as_pre_analysis() -> None:
    details = _build_processing_details({"stakeholders": 2})

    assert details["processing_stage"] == "parsed_pending_analysis"
    assert details["analysis_status"] == "queued"
    assert "analysis orchestration queued" in details["status_detail"].lower()
    assert details["extraction_summary"] == {"stakeholders": 2}
