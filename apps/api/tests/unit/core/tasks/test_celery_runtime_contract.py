"""Runtime contract for Celery queue coverage and periodic recovery."""
from pathlib import Path

from src.core.tasks.celery_app import celery_app

API_ROOT = Path(__file__).resolve().parents[4]
TASKS_DIR = API_ROOT / "src" / "core" / "tasks"


def test_worker_default_queue_matches_deployed_worker_entrypoint() -> None:
    worker = (API_ROOT / "scripts" / "run_worker.sh").read_text(encoding="utf-8")
    assert celery_app.conf.task_default_queue == "document_parsing"
    assert 'CELERY_QUEUES:-document_parsing' in worker


def test_celery_app_registers_all_scheduler_task_modules() -> None:
    source = (TASKS_DIR / "celery_app.py").read_text(encoding="utf-8")
    for module in (
        "src.core.tasks.budget_alerts",
        "src.core.tasks.snapshot_tasks",
        "src.core.tasks.snapshot_retention",
        "src.core.tasks.hitl_resume_reconciler",
        "src.core.tasks.document_recovery",
    ):
        assert f'"{module}"' in source


def test_beat_schedule_contains_required_recovery_and_snapshot_jobs() -> None:
    schedule = celery_app.conf.beat_schedule
    assert schedule["hitl-resume-reconcile"]["task"] == "hitl_resume.reconcile"
    assert schedule["hitl-resume-reconcile"]["schedule"] == 60.0
    assert (
        schedule["project-snapshots-daily"]["task"]
        == "project_snapshots.enqueue_daily"
    )
    assert schedule["project-snapshots-retention"]["task"] == "project_snapshots.retention"
    assert (
        schedule["document-processing-reconcile"]["task"]
        == "documents.reconcile_stale_processing"
    )
    assert schedule["document-processing-reconcile"]["schedule"] == 60.0


def test_periodic_jobs_use_worker_consumed_default_queue() -> None:
    """No periodic entry may silently route to a queue absent from the worker."""
    for entry in celery_app.conf.beat_schedule.values():
        assert entry.get("options", {}).get(
            "queue", celery_app.conf.task_default_queue
        ) == "document_parsing"
