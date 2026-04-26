"""Delegate ``python -m evals.run_evals`` from apps/api to the repo runner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_root_runner() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[3]
    evals_dir = repo_root / "evals"
    runner_path = evals_dir / "run_evals.py"
    if str(evals_dir) not in sys.path:
        sys.path.insert(0, str(evals_dir))
    spec = importlib.util.spec_from_file_location("_c2pro_root_evals_run_evals", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load eval runner from {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    """Run the canonical top-level evals runner.

    Test Suite ID: TS-UD-COH-CORP-007.
    """
    effective_argv = ["--corpus", "--ci"] if argv is None else argv
    return int(_load_root_runner().main(effective_argv))


if __name__ == "__main__":
    sys.exit(main())
