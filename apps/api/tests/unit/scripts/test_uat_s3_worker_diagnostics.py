"""Synthetic log fixtures only: no Celery, worker or external AI access."""

from scripts.uat_s3_worker_diagnostics import summarize_s3_worker_diagnostics


def test_snapshot_counts_are_correlated_without_exporting_raw_identifiers():
    task = "aabbccdd-1111-2222-3333-444455556666"
    log = (
        f"Task project_snapshots.write[{task}] received\n"
        f"Task project_snapshots.write[{task}] succeeded in 0.12s\n"
        "anthropic_wrapper_request_success prompt=private-secrets\n"
    )
    summary = summarize_s3_worker_diagnostics(log)
    assert summary["snapshot_task_received"] == 1
    assert summary["snapshot_task_succeeded"] == 1
    assert summary["snapshot_task_failed"] == 0
    assert not any(
        task in str(value) or "private-secrets" in str(value) for value in summary.values()
    )


def test_worker_failures_are_not_inferred_from_missing_log_lines():
    summary = summarize_s3_worker_diagnostics("")
    assert summary["snapshot_task_received"] == 0
    assert summary["snapshot_task_failed"] == 0
    assert summary["n8_node_failed"] == 0


def test_explicit_n8_and_snapshot_enqueue_failures_have_separate_counters():
    log = (
        "node_coherence_scorer_failed project=confidential\n"
        "project_snapshot_enqueue_failed token=private\n"
        "project_snapshot_write_failed event=confidential\n"
        "Task project_snapshots.write[aabbccdd-1111-2222-3333-444455556666] retry: Retry in 1s\n"
    )
    summary = summarize_s3_worker_diagnostics(log)
    assert summary["n8_node_failed"] == 1
    assert summary["snapshot_enqueue_failed"] == 1
    assert summary["snapshot_write_failed"] == 1
    assert summary["snapshot_task_retried"] == 1
