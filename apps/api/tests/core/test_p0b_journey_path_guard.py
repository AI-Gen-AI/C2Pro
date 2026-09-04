"""``--project-id-file`` may name exactly one file, and nothing else.

TS-UT-P0B-PATHGUARD-001.

``verify_p0b_journey.py`` takes a path on the command line and reads it, then
parses the contents as a UUID. An unconstrained value is a path-injection sink:
it lets whoever controls the argument point the verifier at any readable file
and have a fragment of that file echoed back through the resulting
``ValueError``.

Only one file is ever legitimate. ``.github/workflows/ci.yml`` runs

    working-directory: apps/api
    python scripts/verify_p0b_journey.py --project-id-file ../web/playwright/.p0b/project-id.txt

and ``DEFAULT_PROJECT_ID_FILE`` spells the same file from the repository root.
The two differ textually and resolve identically, so the guard is equality
against that one canonical path -- not containment in the checkout, which would
authorise every other file in the repository for no reason.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO_ROOT / "apps" / "api" / "scripts" / "verify_p0b_journey.py"
_CANONICAL = _REPO_ROOT / "apps" / "web" / "playwright" / ".p0b" / "project-id.txt"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_p0b_journey", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


journey = _load()
CheckFailure = journey.CheckFailure


# ---------------------------------------------------------------------------
# The one file, spelled the two ways the repository spells it
# ---------------------------------------------------------------------------


def test_the_contract_is_the_canonical_p0b_file() -> None:
    assert journey.EXPECTED_PROJECT_ID_FILE == _CANONICAL


def test_the_exact_ci_argument_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The literal string ci.yml passes, from the working directory ci.yml sets."""
    monkeypatch.chdir(_REPO_ROOT / "apps" / "api")

    assert journey.resolve_project_id_file("../web/playwright/.p0b/project-id.txt") == _CANONICAL


def test_the_repository_root_default_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_REPO_ROOT)

    assert journey.resolve_project_id_file(journey.DEFAULT_PROJECT_ID_FILE) == _CANONICAL


def test_the_absolute_canonical_path_is_accepted() -> None:
    assert journey.resolve_project_id_file(str(_CANONICAL)) == _CANONICAL


# ---------------------------------------------------------------------------
# Everything else is refused -- including the rest of the repository
# ---------------------------------------------------------------------------


def test_another_file_inside_the_repository_is_refused() -> None:
    """Being in the checkout is not the contract; being THE file is."""
    with pytest.raises(CheckFailure, match="not the canonical"):
        journey.resolve_project_id_file(str(_REPO_ROOT / "apps" / "api" / "alembic.ini"))


def test_a_sibling_in_the_same_directory_is_refused() -> None:
    with pytest.raises(CheckFailure, match="not the canonical"):
        journey.resolve_project_id_file(str(_CANONICAL.parent / "other-id.txt"))


def test_a_runner_temp_path_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RUNNER_TEMP is not a root this verifier reads from."""
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    with pytest.raises(CheckFailure, match="not the canonical"):
        journey.resolve_project_id_file(str(tmp_path / "project-id.txt"))


def test_an_arbitrary_absolute_path_is_refused() -> None:
    with pytest.raises(CheckFailure, match="not the canonical"):
        journey.resolve_project_id_file("/etc/passwd")


def test_traversal_out_of_the_checkout_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """``..`` is collapsed BEFORE the equality check, not after."""
    monkeypatch.chdir(_REPO_ROOT / "apps" / "api")

    with pytest.raises(CheckFailure, match="not the canonical"):
        journey.resolve_project_id_file("../../../../../../etc/passwd")


def test_a_symlink_at_the_contract_path_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A link planted AT the canonical path must not become an escape hatch."""
    link = tmp_path / "project-id.txt"
    link.symlink_to("/etc/passwd")
    monkeypatch.setattr(journey, "EXPECTED_PROJECT_ID_FILE", link)

    with pytest.raises(CheckFailure, match="symlink"):
        journey.resolve_project_id_file(str(link))


def test_the_refusal_names_the_option_and_leaks_no_content(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("SHOULD-NOT-APPEAR", encoding="utf8")

    with pytest.raises(CheckFailure) as excinfo:
        journey.resolve_project_id_file(str(secret))

    message = str(excinfo.value)
    assert "--project-id-file" in message
    assert "SHOULD-NOT-APPEAR" not in message


# ---------------------------------------------------------------------------
# The guard is wired into the resolver the CLI actually uses
# ---------------------------------------------------------------------------


def test_resolver_refuses_before_touching_the_filesystem() -> None:
    """Pinned as RED evidence: the unguarded code really did read this file.

    Before the guard, ``_resolve_project_id`` read ``/etc/passwd`` and fed it to
    ``UUID()``, failing with "badly formed hexadecimal UUID string" -- the
    contents had already been read. It must now fail on the path instead.
    """
    args = argparse.Namespace(project_id=None, project_id_file="/etc/passwd")

    with pytest.raises(CheckFailure, match="not the canonical"):
        journey._resolve_project_id(args)


def test_resolver_still_reads_the_canonical_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded = tmp_path / "project-id.txt"
    recorded.write_text("6f9619ff-8b86-d011-b42d-00c04fc964ff\n", encoding="utf8")
    monkeypatch.setattr(journey, "EXPECTED_PROJECT_ID_FILE", recorded)

    args = argparse.Namespace(project_id=None, project_id_file=str(recorded))

    assert str(journey._resolve_project_id(args)) == "6f9619ff-8b86-d011-b42d-00c04fc964ff"


def test_an_absent_canonical_file_is_a_failure_not_a_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The pre-existing contract: no recorded id means the journey did not run."""
    missing = tmp_path / "project-id.txt"
    monkeypatch.setattr(journey, "EXPECTED_PROJECT_ID_FILE", missing)

    args = argparse.Namespace(project_id=None, project_id_file=str(missing))

    with pytest.raises(CheckFailure, match="No project id at"):
        journey._resolve_project_id(args)
