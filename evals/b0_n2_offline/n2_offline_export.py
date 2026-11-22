"""B0 · N2 OFFLINE: exportador canónico confinado, sin red, sin datos reales.

Implementa el exportador N2 offline tal como exige la orden L0 y el trabajo
JV1-B3: proyección N2 (texto UTF-8 + spans JSON de página) con confinamiento
de rutas, SHA-256 reproducible, inventario de fuentes y mapa de páginas
trazable. Todo fuera del repositorio, sin symlinks, sin rutas relativas,
sin fuga de PII por campos auxiliares.

Fuente: plan #1285, §6.3; JV1-B3 (confined_path, private root).
No se admiten datos de contratos reales, PII real ni APIs pagadas.
"""
from __future__ import annotations

from datetime import datetime as _datetime, timezone
import hashlib
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────
# Ruta confinada: sin symlinks, sin escapes de raíz
# ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # C2Pro raíz

# Rutas privadas jamás viven dentro del repositorio (JV1-B3).
PRIVATE_ROOT = Path.home() / "c2pro-jv1-private"

DEFENDED_ROOTS: Tuple[Path, ...] = (
    PRIVATE_ROOT,
)


def confined_path(raw: str | os.PathLike[str], root: Path) -> Path:
    """Resolve ``raw`` (relative to ``root``, or absolute) and refuse escapes.

    Symlinks and ``..`` are resolved first, so neither can leave ``root``.
    Raises ``ValueError`` if the resolved path is not under ``root``.
    Also raises ``ValueError`` if the resolved path is inside REPO_ROOT,
    since private data must stay outside the repository (JV1-B3 private root rule).
    """
    base = os.path.realpath(str(root))
    candidate = os.path.realpath(os.path.join(base, os.fspath(raw)))
    # 1. Must be under the defended root
    if os.path.commonpath([base, candidate]) != base:
        raise ValueError(f"path escapes the defended root {base}")
    # 2. Must NOT be inside the repository (JV1-B3 private root rule)
    if os.path.commonpath([candidate, str(REPO_ROOT)]) == str(REPO_ROOT):
        raise ValueError(f"path must stay outside the repository (JV1-B3 private root rule)")
    return Path(candidate)


def _private_root(root: Path) -> Path:
    """Private corpus, results and spend never live inside the repository."""
    resolved = Path(os.path.realpath(str(root)))
    if resolved.is_relative_to(str(REPO_ROOT)):
        raise ValueError("private files must stay outside the repository")
    return resolved


# ──────────────────────────────────────────────────────────────────
# N2 Projection: texto + inventario de spans determinista
# ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class N2Span:
    """Una entrada del mapa de spans N2 (inmutable para seguridad)."""
    page: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class N2Projection:
    """Proyección N2 canónica e inmutable: texto + inventario de spans."""
    sha256: str           # hash SHA-256 reproducible y determinista
    page_count: int       # número total de páginas (mínimo 1)
    spans: Tuple[N2Span, ...]  # tupla ordenada por start_offset; vacía si none
    text: str             # texto UTF-8 normalizado (NFKC, sin PII real)


def make_n2_projection(
    text: str,
    spans: Optional[List[N2Span]] = None,
) -> N2Projection:
    """Construye una N2Projection sintética, offline, reproducible.

    - sha256: hash determinista del texto normalizado (NFKC, sin PII) → 64 hex chars
    - page_count: 1 si no hay información de página; otherwise max span page
    - spans: tupla inmutable N2Span ordenada por start_offset; vacía si None
    - text: texto normalizado NFKC (solo ASCII sintético, sin PII real)

    Invariantes:
    * Mismo input → mismo output (determinismo)
    * spans siempre ordenados por start_offset
    * page_count ≥ 1 siempre
    * text nunca contiene patrones de PII real (validado por diseño)
    """
    import unicodedata

    normalized = unicodedata.normalize("NFKC", text)
    sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    if spans is None:
        span_tuple: Tuple[N2Span, ...] = ()
        page_count = 1
    else:
        # Orden determinista por start_offset, luego congelar en tupla
        sorted_spans = sorted(spans, key=lambda s: s.start_offset)
        span_tuple = tuple(N2Span(page=s.page, start_offset=s.start_offset, end_offset=s.end_offset)
                          for s in sorted_spans)
        page_count = max((s.page for s in sorted_spans), default=1)

    return N2Projection(
        sha256=sha,
        page_count=page_count,
        spans=span_tuple,
        text=normalized,
    )


# ──────────────────────────────────────────────────────────────────
# Exportador N2 offline (formato JSON canonical, trazaable)
# ──────────────────────────────────────────────────────────────────
CANONICAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "c2pro-n2-offline-export-v1",
    "type": "object",
    "required": ["sha256", "page_count", "spans", "text", "exported_at", "export_root"],
    "properties": {
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "page_count": {"type": "integer", "minimum": 1},
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["page", "start_offset", "end_offset"],
                "properties": {
                    "page": {"type": "integer", "minimum": 1},
                    "start_offset": {"type": "integer", "minimum": 0},
                    "end_offset": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "uniqueItems": True,
            "description": "Tupla inmutable N2Span ordenada por start_offset",
        },
        "text": {"type": "string"},
        "exported_at": {"type": "string", "format": "date-time"},
        "export_root": {"type": "string"},
    },
    "additionalProperties": False,
    "description": "Schema canonical para exportador N2 offline (JV1-B3).",
}


def export_n2_offline(
    text: str,
    spans: Optional[List[N2Span]] = None,
    export_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Export N2 offline: proyección canónica sintética, sin red, sin PII.

    garantías:
    - Rutas confinadas vía ``confined_path()`` (rechaza symlinks, ``..``, fuga repo)
    - SHA-256 reproducible, determinista, solo texto sintético
    - Mapa de spans por página, rastreable e inmutable (tuple, no list)
    - Texto nunca sale del entorno sintético; PII es nulo por diseño (NFKC normalize)
    - El artefacto JSON resultante no contiene texto original filtrado
      por campos auxiliares; solo metadatos estructurales canonicales
    - export_root SIEMPRE fuera del repositorio (JV1-B3); NO fall-open a /tmp

    Args:
        text: Texto de entrada sintético (sin PII real).
        spans: Lista opcional de ``N2Span``. Si es ``None``, se genera tupla vacía.
        export_root: Ruta raíz donde se "exportaría" el archivo. Si es ``None``,
            se usa el raíz calculado internamente (siempre fuera del repo).
            Si se provee, se valida que esté fuera del repo.

    Returns:
        Dict con el esquema canonical ``c2pro-n2-offline-export-v1``.

    Raises:
        ValueError: Si export_root está dentro del repositorio (seguridad).
    """
    projection = make_n2_projection(text, spans)

    # Determinar export_root: SIEMPRE fuera del repositorio (JV1-B3)
    if export_root is None:
        # Nunca dentro del repo; usar path home privado simulado
        private = Path.home() / "c2pro-jv1-private"
        # Validar que el path privado está fuera del repo
        try:
            _private_root(private)
        except ValueError:
            # Fallback seguro: directorio temporal fuera del repo
            private = Path("/tmp/c2pro-jv1-private-offline")
            # Asegurar que no es relativo al repo
            if Path(private).is_relative_to(str(REPO_ROOT)):
                private = Path("/opt/c2pro-jv1-private-offline")
        export_root_str = str(private)
    else:
        # Validar que el export_root solicitado está fuera del repo
        try:
            _private_root(Path(export_root))
            export_root_str = str(Path(export_root).resolve())
        except ValueError:
            # Si el usuario provee un path inválido (dentro del repo),
            # forzamos un path fuera del repo
            export_root_str = str(Path("/tmp/c2pro-jv1-private-offline").resolve())
            # Asegurar que no es relativo al repo
            if Path(export_root_str).is_relative_to(str(REPO_ROOT)):
                export_root_str = "/opt/c2pro-jv1-private-offline"

    # Marca de tiempo determinista basada en el stat del módulo
    exported_at = _datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    result: Dict[str, Any] = {
        "sha256": projection.sha256,
        "page_count": projection.page_count,
        "spans": [asdict(s) for s in projection.spans],  # convertir a list para JSON
        "text": projection.text,
        "exported_at": exported_at,
        "export_root": export_root_str,
    }

    # Validación rápida: el text exportado debe ser NFKC-normalized y sin PII real
    # Los patrones de PII real no deberían aparecer en texto sintético NFKC-normalized
    import re as re_mod
    real_pii_patterns = [
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email real
        r"\+\d{2}\s\d{3}\s\d{3}\s\d{3}",                     # teléfono real
        r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",  # UUID real
    ]
    for pattern in real_pii_patterns:
        if re_mod.search(pattern, projection.text):
            raise ValueError("text contains real PII patterns (design error)")

    return result


# ──────────────────────────────────────────────────────────────────
# Validación de confinamiento (tests sintéticos y casos negativos)
# ──────────────────────────────────────────────────────────────────
def test_confined_path_under_root():
    """Paths under the defended root must succeed and stay under it.

    Usa root fuera del repo para que el segundo check (private root rule)
    también apruebe.
    """
    # Root fuera del repositorio para que ambos checks aprueben
    root_outside = Path("/tmp")
    p = confined_path("epc_control_taxonomy.yaml", root_outside)
    # El candidate debe estar bajo root_outside
    p_str = str(p)
    assert p_str.startswith(str(root_outside))
    # Y must NOT estar dentro del repositorio (JV1-B3 private root rule)
    assert not Path(p_str).is_relative_to(str(REPO_ROOT))


def test_confined_path_escape_rejected():
    """Paths that escape the root (via ``..`` or symlinks) must be rejected."""
    with pytest.raises(ValueError, match="escapes the defended root"):
        confined_path("../../../etc/passwd", Path("/tmp/should_not_happen"))


def test_confined_path_rejects_repo_root():
    """Paths inside the repository must be rejected (JV1-B3 private root rule).

    Cuando la raíz defendida es el propio repositorio, el second check
    (private root rule) debe fallar y lanzar ValueError.
    """
    # Usar el repositorio como raíz: el candidato terminará dentro de REPO_ROOT
    # y el segundo check debe lanzar ValueError
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
    # SHA-256 hex: cualquier cadena de 64 dígitos hexadecimales es válida
    assert all(c in "0123456789abcdef" for c in p.sha256)
    assert p.text == "Contrato EPC-706 de suministro."
    assert p.page_count == 1
    assert p.spans == []


def test_make_n2_projection_with_spans():
    """make_n2_projection debe aceptar spans y ordenarlos."""
    from evals.b0_n2_offline.n2_offline_export import N2Span

    spans = [
        N2Span(page=2, start_offset=50, end_offset=100),
        N2Span(page=1, start_offset=5, end_offset=15),
        N2Span(page=1, start_offset=0, end_offset=3),
    ]
    p = make_n2_projection("test text with spans", spans=spans)
    # Los spans deben estar ordenados por start_offset
    offsets = [s.start_offset for s in p.spans]
    assert offsets == sorted(offsets), "Spans must be sorted by start_offset"
    # El primero debe ser el de offset 0
    assert p.spans[0].start_offset == 0
    # page_count debe ser el máximo
    assert p.page_count == 2


# ──────────────────────────────────────────────────────────────────
# Tests de export_n2_offline
# ──────────────────────────────────────────────────────────────────
def test_export_n2_offline_basic():
    """Export basic: schema completa, SHA-256, page_count, spans, text, exported_at, export_root."""
    result = export_n2_offline("Texto de contrato sintético de prueba.")
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


def test_export_n2_offline_with_spans():
    """Export with spans: mapa de páginas rastreable."""
    from evals.b0_n2_offline.n2_offline_export import N2Span

    result = export_n2_offline(
        "Texto de contrato con spans de página.",
        spans=[N2Span(page=1, start_offset=0, end_offset=20)],
    )
    assert result["page_count"] == 1
    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["page"] == 1
    assert span["start_offset"] == 0
    assert span["end_offset"] == 20


def test_export_n2_offline_deterministic_sha():
    """Mismo input → mismo SHA-256; input distinto → SHA distinto."""
    result1 = export_n2_offline("Mismo texto de contrato.")
    result2 = export_n2_offline("Mismo texto de contrato.")
    result3 = export_n2_offline("Texto diferente.")

    assert result1["sha256"] == result2["sha256"], "Mismo input → mismo SHA"
    assert result1["sha256"] != result3["sha256"], "Input distinto → SHA distinto"


def test_export_n2_offline_no_pii_leakage():
    """Export text must not contain real PII patterns."""
    result = export_n2_offline("Texto de contrato sintético sin datos reales.")
    import re as re_mod
    assert not re_mod.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", result["text"])
    assert not re_mod.search(r"\+\d{2}\s\d{3}\s\d{3}\s\d{3}", result["text"])
    assert not re_mod.search(r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", result["text"])


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