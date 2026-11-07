"""S3 first-failure forensic counts: no verdict, no raw data."""

from scripts.verify_integral_s1_s8_pg import summarize_s3_lineage


def test_s3_missing_snapshot_after_successful_evaluation_is_distinguishable():
    value = summarize_s3_lineage(
        [{"has_assessment": True, "assessment_count": 6}],
        [
            {
                "has_analysis_id": True,
                "matching_analysis": True,
                "analysis_has_assessment": True,
                "snapshot_count": 0,
            }
        ],
        [],
    )
    assert value["analyses_with_six_assessments"] == 1
    assert value["graph_with_assessment"] == 1
    assert value["graph_with_snapshot"] == 0
    assert value["snapshots_total"] == 0
    assert value["evidence"] == "read_only_counts_not_a_root_cause_verdict"


def test_s3_missing_n8_assessment_is_not_mislabeled_evaluated_empty():
    value = summarize_s3_lineage(
        [{"has_assessment": False, "assessment_count": None}],
        [
            {
                "has_analysis_id": True,
                "matching_analysis": True,
                "analysis_has_assessment": False,
                "snapshot_count": 1,
            }
        ],
        [{"trigger": "graph_completed", "assessment_count": None}],
    )
    assert value["analyses_with_assessment"] == 0
    assert value["graph_with_matching_analysis"] == 1
    assert value["graph_with_snapshot"] == 1
    assert value["snapshots_with_coverage"] == 0
    assert value["latest_snapshot_assessment_count"] is None


def test_s3_bad_graph_lineage_even_with_an_analysis_is_observable():
    value = summarize_s3_lineage(
        [{"has_assessment": True, "assessment_count": 6}],
        [
            {
                "has_analysis_id": False,
                "matching_analysis": False,
                "analysis_has_assessment": False,
                "snapshot_count": 1,
            }
        ],
        [{"trigger": "scheduled", "assessment_count": 3}],
    )
    assert value["graph_completed_total"] == 1
    assert value["graph_with_analysis_id"] == 0
    assert value["graph_with_matching_analysis"] == 0
    assert value["snapshots_with_coverage"] == 1
    assert value["latest_snapshot_trigger"] == "scheduled"
    assert value["latest_snapshot_assessment_count"] == 3
    assert not any(
        k in value for k in ("prompt", "content", "project_id", "tenant_id", "source_event_id")
    )
