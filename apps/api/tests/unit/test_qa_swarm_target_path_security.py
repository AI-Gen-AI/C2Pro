import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.qa_swarm import qa_swarm_orchestrator as orchestrator  # noqa: E402


def _configure_sandbox_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    allowed_root = repo_root / "apps/api/src"
    allowed_root.mkdir(parents=True)

    monkeypatch.setattr(
        orchestrator,
        "_REPO_ROOT",
        repo_root,
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "_ALLOWED_TARGET_ROOT",
        allowed_root.resolve(),
        raising=False,
    )

    return repo_root, allowed_root


async def _assert_rejected_before_read(
    target_file: str,
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
) -> None:
    def forbidden_read(
        path: Path,
        *args: object,
        **kwargs: object,
    ) -> str:
        raise AssertionError(
            f"QA_SWARM_INVALID_TARGET_REACHED_READ:{path}"
        )

    monkeypatch.setattr(Path, "read_text", forbidden_read)

    result = await orchestrator.run_qa_swarm(
        target_file,
        "unused-coverage.xml",
    )

    assert "error" in result
    assert "apps/api/src" in result["error"]
    assert str(repo_root) not in result["error"]


@pytest.mark.asyncio
async def test_run_qa_swarm_accepts_repository_relative_python_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, allowed_root = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    valid_target = allowed_root / "valid.py"
    valid_target.write_text("VALUE = 1\n", encoding="utf-8")

    original_read_text = Path.read_text

    def confirm_target_read(
        path: Path,
        *args: object,
        **kwargs: object,
    ) -> str:
        if path.resolve() == valid_target.resolve():
            raise AssertionError(
                "QA_SWARM_VALID_TARGET_REACHED_READ"
            )

        return original_read_text(
            path,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        Path,
        "read_text",
        confirm_target_read,
    )

    with pytest.raises(
        AssertionError,
        match="QA_SWARM_VALID_TARGET_REACHED_READ",
    ):
        await orchestrator.run_qa_swarm(
            "apps/api/src/valid.py",
            "unused-coverage.xml",
        )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_absolute_target_outside_api_src(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _ = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    invalid_target = repo_root / "outside.py"
    invalid_target.write_text("VALUE = 1\n", encoding="utf-8")

    await _assert_rejected_before_read(
        str(invalid_target.resolve()),
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_parent_traversal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _ = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    outside_target = repo_root / "apps/api/outside.py"
    outside_target.parent.mkdir(parents=True, exist_ok=True)
    outside_target.write_text("VALUE = 1\n", encoding="utf-8")

    await _assert_rejected_before_read(
        "apps/api/src/../outside.py",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_normalized_traversal_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, allowed_root = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    (allowed_root / "pkg").mkdir()

    outside_target = repo_root / "apps/outside.py"
    outside_target.parent.mkdir(parents=True, exist_ok=True)
    outside_target.write_text("VALUE = 1\n", encoding="utf-8")

    await _assert_rejected_before_read(
        "apps/api/src/pkg/../../../outside.py",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_relative_path_outside_api_src(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _ = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    outside_target = repo_root / "scripts/outside.py"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_text("VALUE = 1\n", encoding="utf-8")

    await _assert_rejected_before_read(
        "scripts/outside.py",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_symlink_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, allowed_root = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    outside_target = repo_root / "outside.py"
    outside_target.write_text("VALUE = 1\n", encoding="utf-8")

    symlink_target = allowed_root / "escape.py"
    symlink_target.symlink_to(outside_target)

    await _assert_rejected_before_read(
        "apps/api/src/escape.py",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_directory_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, allowed_root = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    (allowed_root / "package").mkdir()

    await _assert_rejected_before_read(
        "apps/api/src/package",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_non_python_regular_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, allowed_root = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    non_python = allowed_root / "notes.txt"
    non_python.write_text("not python\n", encoding="utf-8")

    await _assert_rejected_before_read(
        "apps/api/src/notes.txt",
        monkeypatch,
        repo_root,
    )


@pytest.mark.asyncio
async def test_run_qa_swarm_rejects_missing_python_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _ = _configure_sandbox_repo(
        monkeypatch,
        tmp_path,
    )

    await _assert_rejected_before_read(
        "apps/api/src/missing.py",
        monkeypatch,
        repo_root,
    )
