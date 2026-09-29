"""Security regression for local docker-compose database credentials."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_local_compose_requires_environment_supplied_postgres_password():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    quick_start = (REPO_ROOT / "QUICK_START.md").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    api_readme = (REPO_ROOT / "apps/api/README.md").read_text(encoding="utf-8")
    contract_flow = (REPO_ROOT / "scripts/prove_real_contract_flow.py").read_text(
        encoding="utf-8"
    )
    checkpointer_e2e = (REPO_ROOT / "scripts/test_checkpointer_e2e.py").read_text(
        encoding="utf-8"
    )

    assert "POSTGRES_PASSWORD: postgres" not in compose
    assert "postgresql://postgres:postgres@postgres:5432/c2pro" not in compose
    assert compose.count("${POSTGRES_PASSWORD:?") == 3

    assert "POSTGRES_PASSWORD=" in env_example
    assert "postgresql://postgres:postgres@localhost:5432/c2pro" not in env_example
    assert "postgresql://postgres:postgres@localhost:5432/c2pro" not in quick_start
    assert "postgresql://postgres:postgres@localhost:5432/c2pro" not in api_readme
    assert "postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro" not in contract_flow
    assert "postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro" not in checkpointer_e2e

    assert "check-local-postgres-password" in makefile
    assert "POSTGRES_PASSWORD must be non-empty" in makefile
    assert "URI-unreserved" in makefile
    assert "A-Za-z0-9._~-" in makefile

    assert "existing postgres_data volume" in quick_start
    assert "\\password postgres" in quick_start
