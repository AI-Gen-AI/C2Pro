"""
Regression coverage for alerts package imports.

Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""

import subprocess
import sys
from pathlib import Path


def test_alerts_http_router_imports_from_src_package_root() -> None:
    """
    Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
    """
    api_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "-c", "import src.alerts.adapters.http.router"],
        cwd=api_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
