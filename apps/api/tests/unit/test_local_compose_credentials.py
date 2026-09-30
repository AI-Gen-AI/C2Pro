"""Security regression for local docker-compose database credentials."""

import os
import subprocess
import sys
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
    assert "python scripts/validate_local_postgres_password.py" in makefile

    start_dev_sh = (REPO_ROOT / "scripts/start-dev.sh").read_text(encoding="utf-8")
    start_dev_ps1 = (REPO_ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
    assert quick_start.count("validate_local_postgres_password.py") >= 2
    assert "validate_local_postgres_password.py" in start_dev_sh
    assert "validate_local_postgres_password.py" in start_dev_ps1

    assert "existing postgres_data volume" in quick_start
    assert "\\password postgres" in quick_start
    assert "docker compose down -v" not in quick_start
    assert '"volumes"]["postgres_data"]["name"]' in quick_start

    assert "dotenv_values" in contract_flow
    assert "dotenv_values" in checkpointer_e2e


def test_local_postgres_password_validator_matches_effective_precedence(
    tmp_path: Path,
) -> None:
    validator = REPO_ROOT / "scripts" / "validate_local_postgres_password.py"

    def run_guard(
        env_text: str | None,
        *,
        exported: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env_path = tmp_path / ".env"
        if env_text is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(env_text, encoding="utf-8")

        env = os.environ.copy()
        env.pop("POSTGRES_PASSWORD", None)
        if exported is not None:
            env["POSTGRES_PASSWORD"] = exported

        return subprocess.run(
            [sys.executable, str(validator)],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    missing = run_guard(None)
    assert missing.returncode != 0
    assert ".env is required" in (missing.stdout + missing.stderr)

    empty = run_guard("POSTGRES_PASSWORD=\n")
    assert empty.returncode != 0
    assert "POSTGRES_PASSWORD must be non-empty" in (empty.stdout + empty.stderr)

    unsafe = run_guard("POSTGRES_PASSWORD=bad/password\n")
    assert unsafe.returncode != 0
    assert "URI-unreserved" in (unsafe.stdout + unsafe.stderr)

    safe = run_guard("POSTGRES_PASSWORD=Safe_Local-123.~\n")
    assert safe.returncode == 0, safe.stdout + safe.stderr

    unsafe_export_override = run_guard(
        "POSTGRES_PASSWORD=Safe_Local-123.~\n",
        exported="bad/password",
    )
    assert unsafe_export_override.returncode != 0
    assert "URI-unreserved" in (
        unsafe_export_override.stdout + unsafe_export_override.stderr
    )

    duplicate_last_wins = run_guard(
        "POSTGRES_PASSWORD=Safe_Local-123.~\n"
        "POSTGRES_PASSWORD=bad/password\n"
    )
    assert duplicate_last_wins.returncode != 0

    duplicate_last_safe = run_guard(
        "POSTGRES_PASSWORD=bad/password\n"
        "POSTGRES_PASSWORD=Safe_Local-123.~\n"
    )
    assert duplicate_last_safe.returncode == 0, (
        duplicate_last_safe.stdout + duplicate_last_safe.stderr
    )

    exported_without_file = run_guard(None, exported="Safe_Export-123.~")
    assert exported_without_file.returncode != 0
    assert ".env is required" in (
        exported_without_file.stdout + exported_without_file.stderr
    )
