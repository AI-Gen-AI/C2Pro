from __future__ import annotations

from pathlib import Path
import os
import sys

import pytest

repo_root = Path(__file__).resolve().parents[2]
api_root = repo_root / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


@pytest.fixture(scope="session")
def sample_files_path() -> Path:
    """
    Base path for parser integration fixtures.

    Required files (place under tests/fixtures/files/):
    - valid_contract.pdf
    - complex_budget.xlsx
    - legacy.bc3
    """
    return repo_root / "tests" / "fixtures" / "files"
