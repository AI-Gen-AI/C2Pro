"""Security regression for local docker-compose database credentials."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_local_compose_requires_environment_supplied_postgres_password():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    quick_start = (REPO_ROOT / "QUICK_START.md").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD: postgres" not in compose
    assert "postgresql://postgres:postgres@postgres:5432/c2pro" not in compose
    assert compose.count("${POSTGRES_PASSWORD:?") == 3

    assert "POSTGRES_PASSWORD=" in env_example
    assert "postgresql://postgres:postgres@localhost:5432/c2pro" not in env_example
    assert "postgresql://postgres:postgres@localhost:5432/c2pro" not in quick_start
