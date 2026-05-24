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
    # CMD delegates to start.sh; verify start.sh binds $PORT
    start_sh = Path(__file__).resolve().parents[2] / "start.sh"
    startup = start_sh.read_text(encoding="utf-8") if start_sh.exists() else ""
    uvicorn_in_dockerfile = "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}" in content
    uvicorn_in_start_sh = "uvicorn src.main:app --host 0.0.0.0" in startup and "${PORT:-8000}" in startup
    assert uvicorn_in_dockerfile or uvicorn_in_start_sh, (
        "Neither Dockerfile CMD nor start.sh binds uvicorn to ${PORT:-8000}"
    )


def test_api_runtime_requirements_include_pgvector() -> None:
    """TASK-INF-058: the API image must install pgvector before vector-backed ORM imports load."""
    requirements = Path(__file__).resolve().parents[2] / "requirements.txt"
    content = requirements.read_text(encoding="utf-8")

    assert "pgvector" in content
