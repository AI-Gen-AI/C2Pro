"""Static contract for independent API, worker and scheduler entrypoints."""
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (API_ROOT / relative).read_text(encoding="utf-8")


def test_api_entrypoint_owns_migrations_and_uvicorn_only() -> None:
    source = _read("scripts/run_api.sh")
    assert "alembic upgrade head" in source
    assert "exec uvicorn" in source
    assert "celery" not in source.lower()


def test_worker_entrypoint_execs_celery_without_uvicorn_or_migrations() -> None:
    source = _read("scripts/run_worker.sh")
    assert "exec celery" in source
    assert "worker" in source
    assert "document_parsing" in source
    assert "uvicorn" not in source
    assert "alembic" not in source


def test_scheduler_entrypoint_execs_beat_without_worker_or_api() -> None:
    source = _read("scripts/run_scheduler.sh")
    assert "exec celery" in source
    assert " beat " in source.replace("\n", " ")
    assert "uvicorn" not in source
    assert "alembic" not in source


def test_legacy_start_is_api_only_compatibility_shim() -> None:
    source = _read("start.sh")
    assert "scripts/run_api.sh" in source
    assert "celery" not in source.lower()


def test_docker_default_process_is_api_entrypoint() -> None:
    source = _read("Dockerfile")
    assert 'CMD ["bash", "scripts/run_api.sh"]' in source
