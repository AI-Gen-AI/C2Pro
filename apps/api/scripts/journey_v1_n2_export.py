"""B0 · JV1-N2-EXPORT: offline; canonical export blocked pending N2 contract.

Local synthetic validation and descriptor-anchored output helpers only.
The public exporter refuses every request until a trusted N2 contract
provides verifiable source provenance and anonymization evidence.

Fuente: plan #1285, §6.3; alineado a n4_typed_evidence_v2.py y JV1-B3.
No se admiten datos de contratos reales, PII real ni APIs pagadas.
No canonical N2 export is enabled.
"""

# La paridad N2 canónica y los recibos de recepción están gestionados por el
# contrato N2 externo. Esta proyección sintética no puede afirmar equivalencia
# canónica, recepción, tenant, documento, revisión ni anonimización sin esa
# prueba firmada del propietario N2.
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
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
    text: str                # Local normalization only; not anonymization


def make_n2_projection(text: str, spans: list[N2Span] | None = None) -> N2Projection:
    """Local synthetic projection helper; not a receipt or export authorization."""
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
            if any(type(value) is not int for value in (s.page, s.start_offset, s.end_offset)):
                raise ValueError("span page and offsets must be integers")
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


def _verify_directory_chain(fds: list[int], components: tuple[str, ...]) -> None:
    """Check that the anchored directories still match the named chain."""
    for index, component in enumerate(components):
        named = os.stat(component, dir_fd=fds[index], follow_symlinks=False)
        held = os.fstat(fds[index + 1])
        if not stat.S_ISDIR(named.st_mode) or (
            named.st_dev, named.st_ino
        ) != (held.st_dev, held.st_ino):
            raise ValueError("output parent directory changed during creation")


def _create_private_output(path: Path, content: str) -> None:
    """Create via anchored descriptors; reject substituted parents.

    Parent symlinks cannot redirect descriptor-relative open. A changed
    named chain observed before or after creation causes refusal. This is
    a local filesystem primitive, not authority to export untrusted text.
    """
    if path.anchor != "/" or path.is_relative_to(REPO_ROOT):
        raise ValueError("output path must be absolute and outside repository (JV1-B3 confined)")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ValueError("secure no-symlink output creation is unavailable")
    components = path.parts[1:]
    if not components or any(component in ("", ".", "..") for component in components):
        raise ValueError("output path contains unsafe components")

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fds = [os.open("/", flags)]
    created_fd: int | None = None
    created = False
    try:
        for component in components[:-1]:
            fds.append(os.open(component, flags, dir_fd=fds[-1]))
        _verify_directory_chain(fds, components[:-1])
        created_fd = os.open(
            components[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=fds[-1],
        )
        created = True
        _verify_directory_chain(fds, components[:-1])
        os.fchmod(created_fd, 0o600)
        with os.fdopen(created_fd, "w", encoding="utf-8") as output:
            created_fd = None
            output.write(content)
        _verify_directory_chain(fds, components[:-1])
    except (OSError, ValueError, TypeError, NotImplementedError):
        if created:
            os.unlink(components[-1], dir_fd=fds[-1])
        raise
    finally:
        if created_fd is not None:
            os.close(created_fd)
        for fd in reversed(fds):
            os.close(fd)


# ──────────────────────────────────────────────────────────────────
# Exportador N2 offline (formato JSON canonical, trazaable)
# ──────────────────────────────────────────────────────────────────
def export_n2_j1(
    text: str,
    spans: list[N2Span] | None = None,
    export_root: str | None = None,
) -> dict[str, Any]:
    """Reject export until N2 provides verified provenance and anonymization.

    This interface cannot verify a canonical N2 receipt yet. Raw text and
    a locally computed hash are insufficient. Reject every caller input
    without emitting a payload, including synthetic text. Local synthetic
    helper tests do not confer export permission.
    """
    private = Path.home() / "c2pro-jv1-private" if export_root is None else Path(export_root)
    _private_root(private)
    make_n2_projection(text, spans)
    raise ValueError(
        f"{BLOCKED_BY_N2_CONTRACT}: verified canonical N2 provenance and anonymization required"
    )


# ──────────────────────────────────────────────────────────────────
# CLI principal
# ──────────────────────────────────────────────────────────────────
def main() -> int:
    """Reject unverified export requests without emitting their contents."""
    import argparse
    parser = argparse.ArgumentParser(description="JV1-N2-EXPORT: blocked pending canonical N2 receipt")
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
        except (json.JSONDecodeError, IndexError, TypeError, KeyError):
            print("ERROR: spans inválidos", file=sys.stderr)
            return 1

    if args.out:
        out_path = Path(args.out)
        if out_path.anchor != "/" or out_path.is_relative_to(REPO_ROOT):
            print("ERROR: output path must be absolute and outside repository (JV1-B3 confined)", file=sys.stderr)
            return 1
    try:
        result = export_n2_j1(args.text, spans_list, args.export_root)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    output_json = json.dumps(result, indent=2, sort_keys=False, ensure_ascii=False)

    # Future verified exports must use the confined local writer.
    # El archivo debe escribirse fuera del reposorio, sin symlink traversal
    if args.out:
        out_path = Path(args.out)
        # Si la ruta es absoluta y fuera del repositorio, permitirla
        if out_path.is_absolute():
            if out_path.is_relative_to(str(REPO_ROOT)):
                print("ERROR: output path must be outside repository (JV1-B3 confined)", file=sys.stderr)
                return 1
            try:
                _create_private_output(out_path, output_json + "\n")
            except (OSError, ValueError, TypeError, NotImplementedError) as e:
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
