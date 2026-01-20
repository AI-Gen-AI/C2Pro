#!/usr/bin/env python3
"""
csv_to_md_backlog.py
Convierte el backlog CSV de C2Pro a Markdown (LLM-safe) para VS Code + Git.

Uso:
  python scripts/csv_to_md_backlog.py \
    --input  /ruta/C2PRO_CRONOGRAMA_MAESTRO_v1.0.csv \
    --output docs/BACKLOG_COMPLETO.md \
    --details

Notas:
- El MD generado es determinista (orden estable) para que los diffs sean limpios.
- No modifica el CSV; solo genera el MD.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd


DEFAULT_COLUMNS = [
    "ID",
    "Nombre",
    "Semana",
    "Fecha_Inicio",
    "Fecha_Fin",
    "Prioridad",
    "Story_Points",
    "Dominio",
    "CTO_Gate",
    "Estado",
    "Riesgo",
    "Asignado",
    "Dependencias",
    "Entregable",
]


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalize_nan(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _md_escape_pipes(text: str) -> str:
    # Evita romper tablas Markdown
    return text.replace("|", r"\|")


def _to_md_table(df: pd.DataFrame, columns: List[str]) -> str:
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return "_(Sin columnas para mostrar)_\n"

    header = "| " + " | ".join(cols) + " |\n"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |\n"

    rows = []
    for _, r in df[cols].iterrows():
        vals = []
        for c in cols:
            v = _normalize_nan(r.get(c))
            v = _md_escape_pipes(v)
            vals.append(v if v else "—")
        rows.append("| " + " | ".join(vals) + " |")

    return header + sep + "\n".join(rows) + "\n"


def _sprint_sort_key(s: str) -> tuple:
    """
    Ordena Sprint 0, Sprint 1, Sprint 2... si el nombre contiene número.
    Si no, orden alfabético como fallback.
    """
    s_clean = (s or "").strip()
    # intenta extraer número
    import re
    m = re.search(r"(\d+)", s_clean)
    if m:
        return (0, int(m.group(1)), s_clean.lower())
    return (1, 9999, s_clean.lower())


def generate_markdown(df: pd.DataFrame, include_details: bool) -> str:
    required = {"ID", "Nombre", "Sprint"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV no tiene columnas requeridas: {sorted(missing)}")

    # Normaliza columnas clave
    for col in ["Fecha_Inicio", "Fecha_Fin"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": ""})

    # Orden determinista
    sort_cols = [c for c in ["Sprint", "Fecha_Inicio", "ID"] if c in df.columns]
    df_sorted = df.sort_values(sort_cols, kind="mergesort")

    sprints = sorted(df_sorted["Sprint"].dropna().unique().tolist(), key=_sprint_sort_key)

    out = []
    out.append("# 📋 C2PRO — BACKLOG COMPLETO\n")
    out.append("> **Fuente única de verdad:** CSV del cronograma/backlog\n")
    out.append(f"> **Generado automáticamente:** {_now_iso()}\n")
    out.append("> **Formato:** Markdown LLM-safe (orden determinista, diffs limpios)\n")
    out.append("\n---\n")

    out.append("## Reglas para edición por LLM (no romper Git)\n")
    out.append("- ❌ No cambiar `ID`\n")
    out.append("- ❌ No reordenar tareas manualmente en el MD (el script reordena)\n")
    out.append("- ✅ Cambios permitidos en el CSV: `Estado`, fechas, notas, asignaciones\n")
    out.append("- ✅ Regenerar el MD después de cambios en CSV\n")
    out.append("\n---\n")

    out.append("## Leyenda de estado (recomendación)\n")
    out.append("- ⏳ Pendiente\n- 🟠 En progreso\n- ✅ Completado\n- ⛔ Bloqueado\n")
    out.append("\n---\n")

    for sp in sprints:
        sdf = df_sorted[df_sorted["Sprint"] == sp].copy()

        # Tabla del sprint
        out.append(f"## {sp}\n\n")
        out.append(_to_md_table(sdf, DEFAULT_COLUMNS))
        out.append("\n")

        if include_details:
            # Bloques por tarea (útil para LLMs y revisión humana)
            detail_cols = [
                "ID",
                "Nombre",
                "Semana",
                "Fecha_Inicio",
                "Fecha_Fin",
                "Prioridad",
                "Story_Points",
                "Estado",
                "Dominio",
                "CTO_Gate",
                "Dependencias",
                "Asignado",
                "Riesgo",
                "Entregable",
                "Criterio_Aceptacion",
            ]
            present = [c for c in detail_cols if c in sdf.columns]

            out.append("### Detalle por ítem\n\n")
            for _, row in sdf.sort_values(["Fecha_Inicio", "ID"], kind="mergesort").iterrows():
                tid = _normalize_nan(row.get("ID"))
                name = _normalize_nan(row.get("Nombre"))
                out.append(f"#### {tid} — {name}\n\n")

                # Lista de campos en bullets (más tolerante que tabla)
                for c in present:
                    if c in ("ID", "Nombre"):
                        continue
                    v = _normalize_nan(row.get(c))
                    if not v:
                        v = "—"
                    out.append(f"- **{c}:** {v}\n")

                out.append("\n")

        out.append("---\n")

    out.append("\n<!-- Generated by csv_to_md_backlog.py | Do not edit manually: edit the CSV and regenerate -->\n")
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Ruta al CSV fuente")
    parser.add_argument("--output", required=True, help="Ruta al MD generado")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Incluye bloque 'Detalle por ítem' para cada tarea",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        raise SystemExit(f"Input no existe: {in_path}")

    df = pd.read_csv(in_path)

    md = generate_markdown(df, include_details=args.details)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    print(f"[OK] Generado: {out_path} (items: {len(df)})")


if __name__ == "__main__":
    main()
