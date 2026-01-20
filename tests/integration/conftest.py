from __future__ import annotations

from pathlib import Path
import sys

import pytest


@pytest.fixture(scope="session")
def sample_files_path() -> Path:
    """
    Base path for parser integration fixtures.

    Required files (place under tests/fixtures/files/):
    - valid_contract.pdf
    - complex_budget.xlsx
    - legacy.bc3
    """
    repo_root = Path(__file__).resolve().parents[2]
    api_root = repo_root / "apps" / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))
    return repo_root / "tests" / "fixtures" / "files"
