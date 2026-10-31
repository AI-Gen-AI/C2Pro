"""The PostgreSQL verifier scripts only open files inside the repository (SonarCloud S8707, path traversal).

Both scripts are driven by CI with paths such as ``../web/playwright-report/...``. A path that escapes the
checkout (``..``, an absolute path elsewhere) is refused before anything is read or written.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
# Always outside the checkout (pytest's own tmp_path may live inside it).
OUTSIDE = SCRIPTS.parents[2].parent / "outside-the-checkout"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(params=["verify_pj01_revision_trace", "verify_s2_triplet_pg"])
def verifier(request: pytest.FixtureRequest) -> ModuleType:
    return _load(request.param)


def test_a_path_inside_the_repository_is_accepted_as_ci_passes_it(verifier: ModuleType) -> None:
    ci_style = Path("..") / "web" / "playwright-report" / "triplet-results.json"
    assert verifier._within_repo(SCRIPTS.parent / ci_style) == (SCRIPTS.parent / ci_style).resolve()
    assert (
        verifier._within_repo(SCRIPTS / "verify_s2_triplet_pg.py")
        == SCRIPTS / "verify_s2_triplet_pg.py"
    )


@pytest.mark.parametrize(
    "escape",
    [
        Path("..") / ".." / ".." / ".." / "etc" / "passwd",
        Path("/etc/passwd"),
        Path("/tmp/elsewhere/report.json"),
    ],
)
def test_a_path_that_escapes_the_repository_is_refused(verifier: ModuleType, escape: Path) -> None:
    candidate = escape if escape.is_absolute() else SCRIPTS / escape
    with pytest.raises(SystemExit, match="outside the repository"):
        verifier._within_repo(candidate)


def test_a_symlink_inside_the_repository_that_points_outside_is_refused(
    verifier: ModuleType,
) -> None:
    link = SCRIPTS / f"_escape_link_{verifier.__name__}.json"
    link.symlink_to(OUTSIDE / "secret.json")
    try:
        with pytest.raises(SystemExit, match="outside the repository"):
            verifier._within_repo(link)
    finally:
        link.unlink()


def test_the_journey_verifier_refuses_an_outside_run_directory_before_reading_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load("verify_pj01_revision_trace")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify",
            "--kind",
            "reject",
            "--run-dir",
            str(OUTSIDE),
            "--database-url",
            "postgresql://x/y",
        ],
    )
    with pytest.raises(SystemExit, match="outside the repository"):
        module.main()
    capsys.readouterr()
