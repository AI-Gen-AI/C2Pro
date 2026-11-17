"""Fail-closed path authorities for isolated C2Pro V4.1 command-line tools.

Never derive a file-system authority from CLI arguments alone. The GitHub
runner's RUNNER_TEMP fixes the known public SEC sample input and output;
manual private recovery requires two separately authorized directories.
No application tenant, credential, provider, or production storage access.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_PRIVATE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json\Z")


class V41PathAuthorityError(ValueError):
    """A proposed CLI path is outside its independently authorized directory."""


def _root_from_env(name: str) -> Path:
    supplied = os.environ.get(name)
    if not supplied:
        raise V41PathAuthorityError("EXPLICIT_PRIVATE_PATH_ROOT_REQUIRED")
    raw = Path(supplied)
    if raw.is_symlink() or not raw.is_absolute():
        raise V41PathAuthorityError("PRIVATE_PATH_ROOT_NOT_ABSOLUTE_OR_SYMLINK")
    try:
        root = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise V41PathAuthorityError("PRIVATE_PATH_ROOT_UNAVAILABLE") from exc
    if not root.is_dir():
        raise V41PathAuthorityError("PRIVATE_PATH_ROOT_NOT_DIRECTORY")
    return root


def authorize_runner_sec_paths(
    proposed_pdf: Path, proposed_out: Path, *, stage: str,
) -> tuple[Path, Path]:
    """Use only the pinned SEC filename within the GitHub runner's job root."""
    if stage not in ("source", "real"):
        raise V41PathAuthorityError("UNRECOGNIZED_V41_STAGE")
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise V41PathAuthorityError("RUNNER_ONLY_SOURCE_PREFLIGHT")
    runner_temp = _root_from_env("RUNNER_TEMP")
    root = runner_temp / ("c2pro-v41-" + stage)
    if root.is_symlink() or not root.is_dir():
        raise V41PathAuthorityError("EXPECTED_RUNNER_SOURCE_DIRECTORY_MISSING")
    try:
        if (proposed_out.is_symlink()
            or proposed_pdf.is_symlink()
            or proposed_out.resolve(strict=True) != root.resolve(strict=True)
            or proposed_pdf.resolve(strict=True) !=
                (root / "sec_8k.pdf").resolve(strict=True)):
            raise V41PathAuthorityError("RUNNER_PATHS_DIFFER_FROM_FIXED_WORKFLOW")
    except (OSError, RuntimeError) as exc:
        raise V41PathAuthorityError("RUNNER_PDF_OR_DIRECTORY_NOT_ACCESSIBLE") from exc
    locked_pdf = root / "sec_8k.pdf"
    if not locked_pdf.is_file():
        raise V41PathAuthorityError("PINNED_SEC_PDF_MISSING")
    return locked_pdf, root


def authorize_private_input(proposed: Path, *, filename: str) -> Path:
    """Read one exact evidence filename, never a user-selected arbitrary path."""
    root = _root_from_env("C2PRO_V41_PRIVATE_EVIDENCE_ROOT")
    if proposed.name != filename or proposed.is_symlink() or ".." in proposed.parts:
        raise V41PathAuthorityError("PRIVATE_EVIDENCE_FILENAME_NOT_AUTHORIZED")
    try:
        resolved = proposed.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise V41PathAuthorityError("PRIVATE_EVIDENCE_NOT_ACCESSIBLE") from exc
    if resolved != root / filename or not resolved.is_file():
        raise V41PathAuthorityError("PRIVATE_EVIDENCE_OUTSIDE_ROOT")
    return root / filename


def authorize_private_output(proposed: Path) -> Path:
    """Create output only directly in the separately authorized private root."""
    root = _root_from_env("C2PRO_V41_PRIVATE_OUTPUT_ROOT")
    name = proposed.name
    if (not _PRIVATE_NAME.fullmatch(name)
        or ".." in proposed.parts or proposed.is_symlink()):
        raise V41PathAuthorityError("PRIVATE_OUTPUT_FILENAME_NOT_AUTHORIZED")
    try:
        parent = proposed.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise V41PathAuthorityError("PRIVATE_OUTPUT_DIRECTORY_NOT_ACCESSIBLE") from exc
    if parent != root:
        raise V41PathAuthorityError("PRIVATE_OUTPUT_OUTSIDE_ROOT")
    return root / name
