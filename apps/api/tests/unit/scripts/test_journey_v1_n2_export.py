"""B0 · JV1-N2-EXPORT: tests exactos canónicos para journey V1, sintéticos, aislados, sin PII.

No se usan contratos reales, PII real ni APIs pagadas. Todos los datos son
sintéticos y el comportamiento está completamente determinado por fixturas
y el confinamiento de rutas (confined_path, private root per JV1-B3).

Ejecutar desde checkout B0:
  cd /home/aigenadmin/c2pro-jv1-a1-20261121
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH=apps/api/src
  python -m pytest apps/api/tests/unit/scripts/test_journey_v1_n2_export.py -q
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))

import re
from pathlib import Path

import pytest
from apps.api.scripts.journey_v1_n2_export import (
    REPO_ROOT,
    N2Projection,
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
    """make_n2_projection debe aceptar spans y ordenarlos."""
    from apps.api.scripts.journey_v1_n2_export import N2Span

    spans = [
        N2Span(page=2, start_offset=50, end_offset=100),
        N2Span(page=1, start_offset=5, end_offset=15),
        N2Span(page=1, start_offset=0, end_offset=3),
    ]
    p = make_n2_projection("test text with spans", spans=spans)
    offsets = [s.start_offset for s in p.spans]
    assert offsets == sorted(offsets), "Spans must be sorted by start_offset"
    assert p.spans[0].start_offset == 0
    assert p.page_count == 2


# ──────────────────────────────────────────────────────────────────
# Tests de export_n2_j1
# ──────────────────────────────────────────────────────────────────
def test_export_n2_j1_basic():
    """Export basic: schema completa, SHA-256, page_count, spans, text, exported_at, export_root."""
    result = export_n2_j1("Texto de contrato sintético de prueba.")
    assert "sha256" in result
    assert len(result["sha256"]) == 64
    assert all(c in "0123456789abcdef" for c in result["sha256"])
    assert result["page_count"] >= 1
    assert "spans" in result
    assert isinstance(result["spans"], list)
    assert "text" in result
    assert result["text"] == "Texto de contrato sintético de prueba."
    assert "exported_at" in result
    # export_root debe estar FUERA del repositorio (JV1-B3)
    assert not Path(result["export_root"]).is_relative_to(str(REPO_ROOT))


def test_export_n2_j1_with_spans():
    """Export with spans: mapa de páginas rastreable."""
    from apps.api.scripts.journey_v1_n2_export import N2Span

    result = export_n2_j1(
        "Texto de contrato con spans de página.",
        spans=[N2Span(page=1, start_offset=0, end_offset=20)],
    )
    assert result["page_count"] == 1
    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["page"] == 1
    assert span["start_offset"] == 0
    assert span["end_offset"] == 20


def test_export_n2_j1_deterministic_sha():
    """Mismo input → mismo SHA-256; input distinto → SHA distinto."""
    result1 = export_n2_j1("Mismo texto de contrato.")
    result2 = export_n2_j1("Mismo texto de contrato.")
    result3 = export_n2_j1("Texto diferente.")

    assert result1["sha256"] == result2["sha256"], "Mismo input → mismo SHA"
    assert result1["sha256"] != result3["sha256"], "Input distinto → SHA distinto"


def test_export_n2_j1_no_pii_leakage():
    """Export text must not contain real PII patterns."""
    result = export_n2_j1("Texto de contrato sintético sin datos reales.")
    assert not re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", result["text"])
    assert not re.search(r"\+\d{2}\s\d{3}\s\d{3}\s\d{3}", result["text"])
    assert not re.search(r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", result["text"])


# ──────────────────────────────────────────────────────────────────
# Tests de casos negativos de confinamiento
# ──────────────────────────────────────────────────────────────────
def test_confined_path_absolute_within_repo_rejected():
    """Absolute paths within the repo must be rejected."""
    with pytest.raises(ValueError):
        confined_path("/etc/passwd", REPO_ROOT)


def test_confined_path_symmetric_parentheses_rejected():
    """Paths with excessive parentheses/nav must be rejected."""
    with pytest.raises(ValueError):
        confined_path("((((..)))", REPO_ROOT)


# ──────────────────────────────────────────────────────────────────
# Tests de salida CLI --out (JV1-B3 confinamiento)
# ──────────────────────────────────────────────────────────────────
def test_cli_out_outside_repo_succeeds():
    """--out con ruta fuera del reposorio debe exitoar y escribir archivo real."""
    import subprocess
    import sys
    import tempfile
    from pathlib import Path
    # Usar tmp_path de pytest para ruta portable fuera del repo
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.api.scripts.journey_v1_n2_export",
                "--text",
                "Texto de prueba de salida confinada.",
                "--out",
                tmp_path,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Expected success, got: {result.stderr}"
        # Verificar que el archivo fue creado fuera del reposorio
        assert Path(tmp_path).exists(), "Output file should exist"
        content = Path(tmp_path).read_text(encoding="utf-8")
        assert "sha256" in content
        assert "Texto de prueba de salida confinada." in content
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_cli_out_inside_repo_rejected():
    """--out con ruta dentro del reposorio debe ser rechazado (fail-closed)."""
    import subprocess
    import sys
    # Usar ruta relativa evals/journey_v1/export_test.json relative al repo root
    # No especificar cwd: el test runner determinará el directorio actual
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
    )
    assert result.returncode != 0, "Expected failure for inside-repo output path"
    assert "ERROR: output path must be absolute and outside repository" in result.stderr


def test_cli_out_no_out_uses_stdout():
    """Sin --out, debe usar stdout (comportamiento por defecto)."""
    import subprocess
    import sys
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.api.scripts.journey_v1_n2_export",
            "--text",
            "Texto de prueba stdout.",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Texto de prueba stdout." in result.stdout
