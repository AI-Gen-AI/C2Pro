"""B0 · JV1-N2-EXPORT: proyección N2 sintética para Journey V1, offline, sin PII.

Exporta proyección N2 (texto UTF-8 + spans JSON de página) con confinamiento
de rutas (confined_path per JV1-B3), SHA-256 reproducible, inventario de
fuentes y mapa de páginas trazable. Todo fuera del repositorio, sin symlinks,
sin rutas relativas, sin fuga de PII por campos auxiliares.

Fuente: plan #1285, §6.3; alineado a n4_typed_evidence_v2.py y JV1-B3.
No se admiten datos de contratos reales, PII real ni APIs pagadas.
Solo sintético bajo PYTHONPATH=apps/api/src.
"""

# La paridad N2 canónica y los recibos de recepción están gestionados por el
# contrato N2 externo. Esta proyección sintética no puede afirmar equivalencia
# canónica, recepción, tenant, documento, revisión ni anonimización sin esa
# prueba firmada del propietario N2.
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────
# Configuración JV1-N2-EXPORT
# ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]  # C2Pro raíz real; parents[2]=/apps (dentro repo)
JO1_ROOT = REPO_ROOT / "evals" / "journey_v1"  # taxonomy y óracle sintéticos
PRIVATE_ROOT = Path.home() / "c2pro-jv1-private"  # JV1-B3: fuera del repo
BLOCKED_BY_N2_CONTRACT = "BLOCKED_BY_N2_CONTRACT"

# Rutas canónicas (nuevas, sin esperar a que existan)
SCRIPT_PATH = REPO_ROOT / "apps" / "api" / "scripts" / "journey_v1_n2_export.py"
TEST_PATH = REPO_ROOT / "apps" / "api" / "tests" / "unit" / "scripts" / "test_journey_v1_n2_export.py"

# ──────────────────────────────────────────────────────────────────
# N2 Projection: texto + spans determinista (congelado)
# ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class N2Span:
    """Span inmutable N2: página y offsets."""
    page: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class N2Projection:
    """Proyección N2 sintética e inmutable; no es una afirmación canónica."""
    sha256: str              # hash SHA-256 determinista, 64 hex
    page_count: int          # mínimo 1
    spans: tuple[N2Span, ...]  # tupla ordenada por start_offset
    text: str                # NFKC-normalized, sin PII real


def make_n2_projection(text: str, spans: list[N2Span] | None = None) -> N2Projection:
    """Construye N2Projection sintético, offline, reproducible."""
    import unicodedata
    normalized = unicodedata.normalize("NFKC", text)
    sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if spans is None:
        span_tuple: tuple[N2Span, ...] = ()
        page_count = 1
    else:
        # Offsets submitted for pre-normalized text cannot be safely reused: NFKC
        # can change both characters and length.  Do not invent a remapping.
        if text != normalized:
            raise ValueError("spans require NFKC-normalized text; offset remapping is unavailable")

        previous: N2Span | None = None
        for s in spans:
            if s.page < 1:
                raise ValueError(f"span page must be >= 1, got {s.page}")
            if s.start_offset < 0:
                raise ValueError(f"span start_offset must be >= 0, got {s.start_offset}")
            if s.end_offset <= s.start_offset:
                raise ValueError(f"span end_offset must be > start_offset, got end={s.end_offset}, start={s.start_offset}")
            if s.end_offset > len(normalized):
                raise ValueError("span end_offset exceeds normalized text length")
            if previous is not None:
                if s.page < previous.page:
                    raise ValueError("span page order must not be reversed")
                if s.start_offset < previous.start_offset:
                    raise ValueError("span offsets must be in input order")
                if s.start_offset < previous.end_offset:
                    raise ValueError("span offsets must not overlap")
            previous = s
        # Page identity is an N2 fact.  This module has no signed N2 receipt
        # tying a tenant/document/revision to these spans, so it must not emit
        # a page map merely because local offsets look well formed.
        raise ValueError(
            f"{BLOCKED_BY_N2_CONTRACT}: trusted N2 receipt is required for page spans"
        )
    return N2Projection(sha256=sha, page_count=page_count, spans=span_tuple, text=normalized)


# ──────────────────────────────────────────────────────────────────
# Ruta confinada: sin symlinks, sin escapes, fuera del repo
# ──────────────────────────────────────────────────────────────────
def confined_path(raw: str | os.PathLike[str], root: Path) -> Path:
    """Resolve raw (relative to root, or absolute) and refuse escapes.

    Symlinks and ``..`` are resolved first, so neither can leave ``root``.
    Raises ``ValueError`` if the resolved path is not under ``root``.
    Also raises ``ValueError`` if the resolved path is inside REPO_ROOT
    (JV1-B3 private root rule).
    """
    base = os.path.realpath(str(root))
    candidate = os.path.realpath(os.path.join(base, os.fspath(raw)))
    if os.path.commonpath([base, candidate]) != base:
        raise ValueError(f"path escapes the defended root {base}")
    if os.path.commonpath([candidate, str(REPO_ROOT)]) == str(REPO_ROOT):
        raise ValueError("path must stay outside the repository (JV1-B3 private root rule)")
    return Path(candidate)


def _private_root(root: Path) -> Path:
    """Private files must stay outside the repository."""
    if not root.is_absolute():
        raise ValueError("private files root must be absolute")
    if root.is_relative_to(REPO_ROOT):
        raise ValueError("private files must stay outside the repository")
    resolved = Path(os.path.realpath(str(root)))
    if resolved.is_relative_to(REPO_ROOT):
        raise ValueError("private files must stay outside the repository")
    return resolved


def _create_private_output(path: Path, content: str) -> None:
    """Create ``path`` using descriptor-anchored, no-symlink traversal.

    Every parent directory is opened relative to the preceding directory
    descriptor.  Therefore a symlink substituted after an earlier check cannot
    redirect the final creation to another directory.
    """
    if not path.is_absolute():
        raise ValueError("output path must be absolute")
    if path.is_relative_to(REPO_ROOT):
        raise ValueError("output path must be outside repository (JV1-B3 confined)")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ValueError("secure no-symlink output creation is unavailable")

    components = path.parts[1:]
    if not components or any(component in ("", ".", "..") for component in components):
        raise ValueError("output path contains unsafe components")

    directory_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(
            components[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(file_fd, "w", encoding="utf-8") as output:
            output.write(content)
    finally:
        os.close(directory_fd)


# ──────────────────────────────────────────────────────────────────
# Exportador N2 offline (formato JSON canonical, trazaable)
# ──────────────────────────────────────────────────────────────────
def export_n2_j1(
    text: str,
    spans: list[N2Span] | None = None,
    export_root: str | None = None,
) -> dict[str, Any]:
    """Export N2 journey V1 offline: proyección sintética, sin red.

    Garantías:
    - Rutas confinadas vía ``confined_path()`` (rechaza symlinks, ``..``, fuga repo)
    - SHA-256 reproducible, determinista, solo texto sintético NFKC-normalized
    - Sin recibo N2 firmado, no acepta spans/página que afirmen identidad documental
    - Sin prueba N2 firmada, el resultado queda ejecutablemente bloqueado y no
      afirma canonicalidad, recepción, tenant, documento, revisión ni anonimización
    - export_root SIEMPRE fuera del repositorio (JV1-B3); NO fall-open a /tmp
    - output JSON con schema estable: sha256, page_count, spans, text, exported_at, export_root

    Args:
        text: Texto de entrada sintético (sin PII real).
        spans: Lista opcional de ``N2Span``. Si es ``None``, tupla vacía.
        export_root: Ruta raíz donde se "exportaría" el archivo. Si es ``None``,
            se usa el raíz calculado internamente (siempre fuera del repo).
            Si se provee, se valida que esté fuera del repo.

    Returns:
        Dict con el esquema JV1-N2-EXPORT v1.

    Raises:
        ValueError: Si export_root está dentro del repositorio.
    """
    projection = make_n2_projection(text, spans)

    # Determinar export_root: SIEMPRE fuera del repositorio (JV1-B3)
    if export_root is None:
        # HOME is the only default.  If it points into the repo, refuse rather
        # than silently publishing a different root such as /opt.
        export_root_str = str(_private_root(Path.home() / "c2pro-jv1-private"))
    else:
        export_root_str = str(_private_root(Path(export_root)))

    exported_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    result: dict[str, Any] = {
        "sha256": projection.sha256,
        "page_count": projection.page_count,
        "spans": [asdict(s) for s in projection.spans],  # list para JSON
        "text": projection.text,
        "exported_at": exported_at,
        "export_root": export_root_str,
        "n2_contract_state": BLOCKED_BY_N2_CONTRACT,
    }

    # Defensa heurística adicional; no es evidencia de anonimización N2.
    import re as re_mod
    real_pii_patterns = [
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        r"\+\d{2}\s\d{3}\s\d{3}\s\d{3}",
        r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
    ]
    for pattern in real_pii_patterns:
        if re_mod.search(pattern, projection.text):
            raise ValueError("text contains real PII patterns (design error)")

    return result


# ──────────────────────────────────────────────────────────────────
# CLI principal
# ──────────────────────────────────────────────────────────────────
def main() -> int:
    """CLI: exporta proyección N2 para Journey V1, sintético, offline."""
    import argparse
    parser = argparse.ArgumentParser(description="JV1-N2-EXPORT: exportador N2 canónico sintético")
    parser.add_argument("--text", required=True, help="Texto sintético de entrada")
    parser.add_argument("--spans", default=None, help="JSON list de spans [page,start_offset,end_offset]")
    parser.add_argument("--export-root", default=None, help="Ruta raíz export (fuera del repo)")
    parser.add_argument("--out", default=None, help="Archivo de salida JSON (stdout si omitido)")
    args = parser.parse_args()

    # Parse spans si se proveen
    spans_list: list[N2Span] | None = None
    if args.spans is not None:
        try:
            spans_data = json.loads(args.spans)
            spans_list = [
                N2Span(page=s[0], start_offset=s[1], end_offset=s[2])
                for s in spans_data
            ]
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            print(f"ERROR: spans inválidos: {e}", file=sys.stderr)
            return 1

    try:
        result = export_n2_j1(args.text, spans_list, args.export_root)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    output_json = json.dumps(result, indent=2, sort_keys=False, ensure_ascii=False)

    # Validación de ruta de salida confinada JV1-B3
    # El archivo debe escribirse fuera del reposorio, sin symlink traversal
    if args.out:
        from pathlib import Path
        out_path = Path(args.out)
        # Si la ruta es absoluta y fuera del repositorio, permitirla
        if out_path.is_absolute():
            if out_path.is_relative_to(str(REPO_ROOT)):
                print("ERROR: output path must be outside repository (JV1-B3 confined)", file=sys.stderr)
                return 1
            try:
                _create_private_output(out_path, output_json + "\n")
            except (OSError, ValueError) as e:
                print(f"ERROR: cannot create private output file: {e}", file=sys.stderr)
                return 1
        else:
            # Rutas relativas: error — debe ser absoluta y fuera del repo
            print("ERROR: output path must be absolute and outside repository (JV1-B3 confined)", file=sys.stderr)
            return 1
    else:
        # Sin --out: usar stdout
        print(output_json + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
