"""TS-OPS-ENV-GUARD-001

Guardrail script to prevent manual runtime QA against test databases.
"""

from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse


class RuntimeEnvValidationError(ValueError):
    """Raised when runtime environment points to a test-only database."""


class RuntimeEnvValidationResult:
    def __init__(self, environment: str, database_name: str) -> None:
        self.environment = environment
        self.database_name = database_name


def _database_name_from_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    return parsed.path.rsplit("/", 1)[-1].strip()


def _looks_like_test_database(database_name: str) -> bool:
    normalized = database_name.lower()
    return any(marker in normalized for marker in ("test", "pytest", "spec"))


def validate_runtime_env(database_url: str, environment: str) -> RuntimeEnvValidationResult:
    database_name = _database_name_from_url(database_url)
    normalized_environment = environment.lower().strip()

    if normalized_environment != "test" and _looks_like_test_database(database_name):
        raise RuntimeEnvValidationError(
            f"Refusing to run manual/runtime workload against test database '{database_name}'."
        )

    return RuntimeEnvValidationResult(
        environment=normalized_environment,
        database_name=database_name,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate runtime environment against test DB misuse")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL"),
        help="Database URL to validate",
    )
    parser.add_argument(
        "--environment",
        default=os.getenv("ENVIRONMENT", "development"),
        help="Runtime environment name",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeEnvValidationError("DATABASE_URL is required for runtime environment validation")

    result = validate_runtime_env(args.database_url, args.environment)
    print(
        f"Runtime environment OK: environment={result.environment} database={result.database_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
