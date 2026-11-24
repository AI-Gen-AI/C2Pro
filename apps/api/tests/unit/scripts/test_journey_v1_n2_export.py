"""B0 · JV1-N2-EXPORT: tests exactos canónicos para journey V1, sintéticos, aislados, sin PII.

No se usan contratos reales, PII real ni APIs pagadas. Todos los datos son
sintéticos y el comportamiento está completamente determinado por fixturas
y el confinamiento de rutas (confined_path, private root per JV1-B3).

Ejecutar desde checkout B0:
  python -m pytest apps/api/tests/unit/scripts/test_journey_v1_n2_export.py -q
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))

from pathlib import Path

import pytest
from apps.api.scripts.journey_v1_n2_export import (
    BLOCKED_BY_N2_CONTRACT,
    REPO_ROOT,
    N2Projection,
    N2Span,
    _create_private_output,
    confined_path,
    export_n2_j1,
    make_n2_projection,
)


# ──────────────────────────────────────────────────────────────────
# Tests de confinamiento de rutas (confined_path)
# ──────────────────────────────────────────────────────────────────
def test_confined_path_under_root():
    """Paths under the defended root must succeed and stay under it."""
    root_outside = Path("/tmp")
    p = confined_path("epc_control_taxonomy.yaml", root_outside)
    p_str = str(p)
    assert p_str.startswith(str(root_outside))
    assert not Path(p_str).is_relative_to(str(REPO_ROOT))


def test_confined_path_escape_rejected():
    """Paths that escape the root (via ``..`` or symlinks) must be rejected."""
    with pytest.raises(ValueError, match="escapes the defended root"):
        confined_path("../../../etc/passwd", Path("/tmp/should_not_happen"))


def test_confined_path_rejects_repo_root():
    """Paths inside the repository must be rejected (JV1-B3 private root rule)."""
    with pytest.raises(ValueError, match="must stay outside the repository"):
        confined_path(
            "evals/journey_v1/epc_control_taxonomy.yaml",
            REPO_ROOT,
        )


# ──────────────────────────────────────────────────────────────────
# Tests de N2Projection y make_n2_projection
# ──────────────────────────────────────────────────────────────────
def test_n2_projection_creates():
    """N2Projection debe crearse con valores válidos."""
    p = N2Projection(
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        page_count=1,
        spans=[],
        text="",
    )
    assert p.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_make_n2_projection_basic():
    """make_n2_projection debe crear una proyección con SHA-256 y texto."""
    p = make_n2_projection("Contrato EPC-706 de suministro.")
    assert isinstance(p.sha256, str)
    assert len(p.sha256) == 64
    assert all(c in "0123456789abcdef" for c in p.sha256)
    assert p.text == "Contrato EPC-706 de suministro."
    assert p.page_count == 1
    assert list(p.spans) == []


def test_make_n2_projection_with_spans():
    """Well-formed local spans still lack the required N2 page receipt."""

    spans = [
        N2Span(page=1, start_offset=0, end_offset=3),
        N2Span(page=1, start_offset=5, end_offset=15),
        N2Span(page=2, start_offset=16, end_offset=20),
    ]
    with pytest.raises(ValueError, match=BLOCKED_BY_N2_CONTRACT):
        make_n2_projection("test text with spans", spans=spans)


# ──────────────────────────────────────────────────────────────────
# Tests de export_n2_j1
# ──────────────────────────────────────────────────────────────────
def test_export_n2_j1_basic():
    """No success or payload without a trusted upstream receipt."""
    with pytest.raises(ValueError, match=BLOCKED_BY_N2_CONTRACT):
        export_n2_j1("Texto de contrato sintético de prueba.")


def test_export_n2_j1_with_spans():
    """Export cannot manufacture N2 page facts from locally supplied spans."""
    with pytest.raises(ValueError, match=BLOCKED_BY_N2_CONTRACT):
        export_n2_j1(
            "Texto de contrato con spans de página.",
            spans=[N2Span(page=1, start_offset=0, end_offset=20)],
        )


def test_export_n2_j1_deterministic_sha():
    """Local helper SHA is deterministic, but does not authorize export."""
    result1 = make_n2_projection("Mismo texto de contrato.")
    result2 = make_n2_projection("Mismo texto de contrato.")
    result3 = make_n2_projection("Texto diferente.")
    assert result1.sha256 == result2.sha256
    assert result1.sha256 != result3.sha256


@pytest.mark.parametrize(
    "text",
    [
        "Texto sintético sin datos reales.",
        "Synthetic Person Name at Fictional City",
        "synthetic.person@example.test",
        "+34 600 123 456",
        "123e4567-e89b-12d3-a456-426614174000",
    ],
)
def test_export_n2_j1_no_pii_leakage(text):
    """No untrusted payload can cross the canonical export gate."""
    with pytest.raises(ValueError, match=BLOCKED_BY_N2_CONTRACT):
        export_n2_j1(text)


# ──────────────────────────────────────────────────────────────────
# Tests de casos negativos de confinamiento
# ──────────────────────────────────────────────────────────────────
def test_confined_path_absolute_within_repo_rejected():
    """Absolute paths within the repo must be rejected."""
    with pytest.raises(ValueError):
        confined_path("/etc/passwd", REPO_ROOT)


# ──────────────────────────────────────────────────────────────────
# Tests de salida CLI --out (JV1-B3 confinamiento)
# ──────────────────────────────────────────────────────────────────
def test_cli_out_outside_repo_blocked_without_receipt():
    """An otherwise valid output path cannot bypass the N2 gate."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="jv1-b0-cli-") as directory:
        output = Path(directory) / "b0-export.json"
        raw = "Synthetic content without canonical receipt"
        result = subprocess.run(
            [sys.executable, "-m", "apps.api.scripts.journey_v1_n2_export",
             "--text", raw, "--out", str(output)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode != 0
        assert BLOCKED_BY_N2_CONTRACT in result.stderr
        assert not output.exists()
        assert raw not in result.stdout + result.stderr


def test_cli_without_out_never_emits_untrusted_text():
    import subprocess

    raw = "Synthetic Person Name at Fictional City"
    result = subprocess.run(
        [sys.executable, "-m", "apps.api.scripts.journey_v1_n2_export", "--text", raw],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert BLOCKED_BY_N2_CONTRACT in result.stderr
    assert not result.stdout
    assert raw not in result.stderr


def test_private_writer_creates_0600_and_refuses_overwrite():
    """Local filesystem primitive is tested independently of the N2 gate."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="jv1-b0-writer-") as directory:
        out = Path(directory) / "private.json"
        _create_private_output(out, "synthetic fixture")
        assert out.stat().st_mode & 0o777 == 0o600
        assert out.read_text(encoding="utf-8") == "synthetic fixture"
        with pytest.raises(FileExistsError):
            _create_private_output(out, "must not overwrite")
        assert out.read_text(encoding="utf-8") == "synthetic fixture"


def test_cli_out_inside_repo_rejected():
    """--out con ruta dentro del reposorio debe ser rechazado (fail-closed)."""
    import subprocess
    # Infer repo root desde __file__ para portabilidad CI
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
    # Derivar REPO_ROOT de forma autocontenida, sin rutas VPS fijas
    REPO_ROOT = Path(__file__).resolve().parents[5]
    # No especificar cwd: el test runner determinará el directorio actual
    # Usamos cwd=REPO_ROOT para que Python encuentre el módulo 'apps'
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.api.scripts.journey_v1_n2_export",
            "--text",
            "Texto de prueba dentro del repo.",
            "--out",
            "evals/journey_v1/export_test.json",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0, "Expected failure for inside-repo output path"
    assert "ERROR: output path must be absolute and outside repository" in result.stderr


def test_confined_path_symmetric_parentheses_rejected():
    """Paths with excessive parentheses/nav must be rejected."""
    with pytest.raises(ValueError):
        confined_path("((((..)))", REPO_ROOT)


# ──────────────────────────────────────────────────────────────────
# Tests de validación de spans N2 (constraints fail-closed)
# ──────────────────────────────────────────────────────────────────
def test_make_n2_projection_invalid_page_raises():
    """make_n2_projection debe rechazar spans con page < 1."""
    from apps.api.scripts.journey_v1_n2_export import N2Span
    with pytest.raises(ValueError, match="span page must be >= 1"):
        make_n2_projection("test", spans=[N2Span(page=0, start_offset=0, end_offset=5)])


def test_make_n2_projection_invalid_start_offset_raises():
    """make_n2_projection debe rechazar spans con start_offset < 0."""
    from apps.api.scripts.journey_v1_n2_export import N2Span
    with pytest.raises(ValueError, match="span start_offset must be >= 0"):
        make_n2_projection("test", spans=[N2Span(page=1, start_offset=-1, end_offset=5)])


def test_make_n2_projection_invalid_end_offset_raises():
    """make_n2_projection debe rechazar spans con end_offset <= start_offset."""
    from apps.api.scripts.journey_v1_n2_export import N2Span
    with pytest.raises(ValueError, match="span end_offset must be > start_offset"):
        make_n2_projection("test", spans=[N2Span(page=1, start_offset=0, end_offset=0)])


@pytest.mark.parametrize(
    ("text", "spans", "message"),
    [
        ("short", [N2Span(page=1, start_offset=0, end_offset=6)], "exceeds normalized"),
        (
            "abcdef",
            [N2Span(page=1, start_offset=0, end_offset=4), N2Span(page=1, start_offset=3, end_offset=6)],
            "must not overlap",
        ),
        (
            "abcdef",
            [N2Span(page=2, start_offset=0, end_offset=3), N2Span(page=1, start_offset=3, end_offset=6)],
            "page order must not be reversed",
        ),
        ("\uff21BC", [N2Span(page=1, start_offset=0, end_offset=3)], "require NFKC-normalized"),
    ],
)
def test_make_n2_projection_rejects_untrusted_span_coordinates(text, spans, message):
    """Never fabricate canonical page facts from invalid or changed offsets."""
    with pytest.raises(ValueError, match=message):
        make_n2_projection(text, spans=spans)


def test_default_home_inside_repository_fails_closed(monkeypatch):
    """A hostile HOME cannot make the exporter choose a silent /opt fallback."""
    from apps.api.scripts import journey_v1_n2_export as subject

    monkeypatch.setattr(subject.Path, "home", classmethod(lambda cls: REPO_ROOT))
    with pytest.raises(ValueError, match="outside the repository"):
        subject.export_n2_j1("synthetic only")


def test_anchored_output_creation_survives_parent_symlink_switch(monkeypatch):
    """A parent renamed to a symlink after opening stays anchored to its dirfd."""
    import tempfile

    from apps.api.scripts import journey_v1_n2_export as subject

    with tempfile.TemporaryDirectory(prefix="jv1-n2-toctou-") as directory:
        tmp_path = Path(directory)
        guarded_parent = tmp_path / "guarded"
        guarded_parent.mkdir()
        attacker_parent = tmp_path / "attacker"
        attacker_parent.mkdir()
        original_parent = tmp_path / "guarded-before-switch"
        target = guarded_parent / "export.json"
        real_open = os.open
        switched = False

        def switch_after_parent_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal switched
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if path == "guarded" and flags & os.O_DIRECTORY and not switched:
                switched = True
                guarded_parent.rename(original_parent)
                guarded_parent.symlink_to(attacker_parent, target_is_directory=True)
            return fd

        monkeypatch.setattr(subject.os, "open", switch_after_parent_open)
        with pytest.raises((OSError, ValueError)):
            _create_private_output(target, "synthetic\n")

        assert switched
        assert not (original_parent / "export.json").exists()
        assert not (attacker_parent / "export.json").exists()


def test_preexisting_parent_symlink_is_rejected():
    """Traversal starts at / and refuses every symlinked parent component."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="jv1-n2-symlink-") as directory:
        tmp_path = Path(directory)
        safe_parent = tmp_path / "safe"
        safe_parent.mkdir()
        link_parent = tmp_path / "link"
        link_parent.symlink_to(safe_parent, target_is_directory=True)

        with pytest.raises(OSError):
            _create_private_output(link_parent / "export.json", "synthetic\n")


def test_writer_detects_parent_swap_at_final_open(monkeypatch):
    import tempfile

    with tempfile.TemporaryDirectory(prefix="jv1-b0-final-swap-") as directory:
        root = Path(directory)
        parent = root / "safe"
        parent.mkdir()
        outside = root / "outside"
        outside.mkdir()
        original = root / "safe-original"
        real_open = os.open
        swapped = False

        def swap_at_final_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "artifact.json" and flags & os.O_CREAT and not swapped:
                swapped = True
                parent.rename(original)
                parent.symlink_to(outside, target_is_directory=True)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", swap_at_final_open)
        with pytest.raises((OSError, ValueError)):
            _create_private_output(parent / "artifact.json", "synthetic fixture")
        assert swapped
        assert not (outside / "artifact.json").exists()
        assert not (original / "artifact.json").exists()


@pytest.mark.parametrize("with_output", [False, True])
def test_contract_blocked_even_if_export_unexpectedly_returns(
    monkeypatch, capsys, with_output
):
    """CLI must not expose or write any payload before a trusted N2 contract."""
    from apps.api.scripts import journey_v1_n2_export as subject

    import tempfile

    with tempfile.TemporaryDirectory(prefix="b0-contract-") as directory:
        target = Path(directory) / "forbidden.json"
        argv = ["export", "--text", "synthetic"]
        if with_output:
            argv += ["--out", str(target)]
        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(subject, "export_n2_j1", lambda *a: {"text": "synthetic"})
        def forbidden_writer(*args, **kwargs):
            pytest.fail("blocked CLI reached the private writer")
        monkeypatch.setattr(subject, "_create_private_output", forbidden_writer)
        assert subject.main() == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert BLOCKED_BY_N2_CONTRACT in captured.err
        assert not target.exists()
