"""
Test Suite ID: TASK-INF-057

Regression checks for container runtime portability across hosted platforms.
"""

from pathlib import Path


def test_api_dockerfile_binds_platform_port() -> None:
    """TASK-INF-057: Railway-style platforms require the process to bind $PORT."""
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert 'HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\' in content
    assert "localhost:${PORT:-8000}/health" in content
    # Docker defaults to the canonical API entrypoint after #710 cutover.
    run_api = Path(__file__).resolve().parents[2] / "scripts" / "run_api.sh"
    startup = run_api.read_text(encoding="utf-8")
    assert 'CMD ["bash", "scripts/run_api.sh"]' in content
    assert "uvicorn src.main:app --host 0.0.0.0" in startup
    assert '"${PORT:-8000}"' in startup


def test_api_runtime_requirements_include_pgvector() -> None:
    """TASK-INF-058: the API image must install pgvector before vector-backed ORM imports load."""
    requirements = Path(__file__).resolve().parents[2] / "requirements.txt"
    content = requirements.read_text(encoding="utf-8")

    assert "pgvector" in content


def test_api_runtime_image_uses_explicit_runtime_copy_surface() -> None:
    """R17-HS-C: production image must not recursively copy the API build context."""
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY --chown=appuser:appgroup . ." not in content

    required_runtime_copies = [
        "COPY --chown=appuser:appgroup src/ ./src/",
        "COPY --chown=appuser:appgroup alembic/ ./alembic/",
        "COPY --chown=appuser:appgroup alembic.ini ./alembic.ini",
        "COPY --chown=appuser:appgroup scripts/ ./scripts/",
        "COPY --chown=appuser:appgroup start.sh ./start.sh",
    ]
    for expected in required_runtime_copies:
        assert expected in content
