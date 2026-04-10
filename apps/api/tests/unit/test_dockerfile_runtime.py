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
    assert 'CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]' in content
