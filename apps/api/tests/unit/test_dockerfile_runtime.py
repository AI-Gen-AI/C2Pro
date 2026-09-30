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


def test_api_runtime_copy_surface_is_explicit() -> None:
    """R17-HS-C: runtime image copies only the proven production surfaces."""
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY --chown=appuser:appgroup . ." not in content
    assert "COPY --chown=root:root" not in content
    assert "RUN rm -rf" not in content

    required_runtime_copies = [
        "COPY src/ ./src/",
        "COPY alembic/ ./alembic/",
        "COPY alembic.ini ./alembic.ini",
        "COPY scripts/ ./scripts/",
        "COPY start.sh ./start.sh",
    ]
    for expected in required_runtime_copies:
        assert expected in content


def test_api_docker_context_excludes_in_tree_test_and_evaluation_code() -> None:
    """Production source COPY must omit test/evaluation-only modules under src."""
    dockerignore = Path(__file__).resolve().parents[2] / ".dockerignore"
    content = dockerignore.read_text(encoding="utf-8")

    expected_exclusions = [
        ".env",
        "**/.env",
        ".env.*",
        "**/.env.*",
        "*.db",
        "**/*.db",
        "claves postgre.txt",
        "**/claves postgre.txt",
        "credentials.json",
        "*credentials*.json",
        "*service-account*.json",
        "*.pem",
        "*.key",
        "*.p12",
        "*.pfx",
        "*.crt",
        "*.cer",
        "**/credentials.json",
        "**/*credentials*.json",
        "**/*service-account*.json",
        "**/*.pem",
        "**/*.key",
        "**/*.p12",
        "**/*.pfx",
        "**/*.crt",
        "**/*.cer",
        "src/core/ai/test_*.py",
        "src/core/ai/example_*.py",
        "src/golden/",
        "src/projects/adapters/http/router.py.fullversion",
        "migrate.py",
        "evals/",
        "examples/",
        "test*.py",
        "scripts/*",
        "!scripts/run_api.sh",
        "!scripts/run_worker.sh",
        "!scripts/run_scheduler.sh",
        "!scripts/wait_for_schema.py",
    ]
    for expected in expected_exclusions:
        assert expected in content
