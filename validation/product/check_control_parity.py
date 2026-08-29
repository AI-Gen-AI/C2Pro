#!/usr/bin/env python3
"""Deterministic VALUE-parity + status-enum guard for the C2Pro product-control plane.

The YAML (``c2pro-master-product-control-v1.yaml``) is the machine source of truth.
The Markdown (``docs/product/00-c2pro-master-product-control-v1.md``) carries an
explicitly delimited CANONICAL-CONTROL block that is GENERATED from the YAML.

This checker (control-integrity, review fixes 1 & 2):
  1. parses the YAML,
  2. validates every ADR/WBS status against the per-field ``status_enums`` (no
     free-form / compound machine-state values),
  3. extracts the exact critical values from the parsed YAML,
  4. parses the MD canonical block and compares value-by-value.
A contradictory or missing MD value FAILS (exit 1). A status outside its enum FAILS.

Modes:
  python check_control_parity.py           # validate enums + compare MD<->YAML (default)
  python check_control_parity.py --emit     # print the canonical block generated from YAML
                                            # (paste between the MD markers to regenerate)

Only dependency beyond stdlib is PyYAML (already a declared project dep).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_YAML = _ROOT / "validation" / "product" / "c2pro-master-product-control-v1.yaml"
_MD = _ROOT / "docs" / "product" / "00-c2pro-master-product-control-v1.md"

_BLOCK_START = "<!-- CANONICAL-CONTROL:START"
_BLOCK_END = "<!-- CANONICAL-CONTROL:END"

_WBS_IDS = [
    "PWBS-ACT-HEALTH", "PWBS-COHERENCE-XDOC", "PWBS-TEMPORAL-CHANGE",
    "PWBS-ALERTS-ACTIONS-HITL", "PWBS-PROJECT-CONTROLS", "PWBS-PROCUREMENT",
    "PWBS-EXEC-REPORTING", "PWBS-OPS-TRUST",
]


# ── helpers ───────────────────────────────────────────────────────────────────
def _s(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


def load_yaml(path: Path = _YAML) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _adr_row(doc: dict, prefix: str) -> dict:
    for row in doc["adr_realization"]:
        if str(row.get("adr", "")).startswith(prefix):
            return row
    raise KeyError(f"ADR row {prefix} not found")


def _wbs_row(doc: dict, wid: str) -> dict:
    for row in doc["product_wbs"]:
        if row.get("id") == wid:
            return row
    raise KeyError(f"WBS row {wid} not found")


# ── (fix 2) enum validation ───────────────────────────────────────────────────
def validate_enums(doc: dict) -> list[str]:
    problems: list[str] = []
    enums = doc["status_enums"]
    design = set(enums["design_status"])
    real = set(enums["realization_status"])
    dep = set(enums["deployment_status"])
    prod = set(enums["prod_validation_status"])
    work = set(enums["work_status"])
    union_rd = real | dep

    def _chk(where: str, field: str, value: object, allowed: set[str]) -> None:
        if value is None:
            problems.append(f"{where}: missing '{field}'")
        elif _s(value) not in allowed:
            problems.append(f"{where}: '{field}'='{value}' not in {sorted(allowed)}")

    for row in doc["adr_realization"]:
        adr = row.get("adr", "?")
        _chk(f"adr[{adr}]", "design_status", row.get("design_status"), design)
        _chk(f"adr[{adr}]", "realization_status", row.get("realization_status"), real)
        _chk(f"adr[{adr}]", "deployment_status", row.get("deployment_status"), dep)
        _chk(f"adr[{adr}]", "prod_validation_status", row.get("prod_validation_status"), prod)
        for tk, tv in (row.get("subtracks") or {}).items():
            if isinstance(tv, dict):
                for f, allowed in (("realization_status", real), ("deployment_status", dep), ("prod_validation_status", prod)):
                    if f in tv:
                        _chk(f"adr[{adr}].subtrack[{tk}]", f, tv[f], allowed)

    p0b = doc.get("p0b_vertical_contract") or {}
    slice_allowed = set(enums["slice_status"])
    residual_allowed = set(enums["residual_status"])
    slice_ids = {_s(sl.get("id")) for sl in (p0b.get("slices") or [])}

    for sl in p0b.get("slices") or []:
        sid = sl.get("id", "?")
        _chk(f"p0b.slice[{sid}]", "slice_status", sl.get("slice_status"), slice_allowed)
        if "status" in sl:
            problems.append(
                f"p0b.slice[{sid}]: legacy free-form 'status' present; use validated 'slice_status'"
            )

    residuals = p0b.get("residuals")
    if not residuals:
        problems.append("p0b_vertical_contract: no 'residuals' registered (open residuals must be explicit)")
    for res in residuals or []:
        rid = res.get("id", "?")
        _chk(f"p0b.residual[{rid}]", "status", res.get("status"), residual_allowed)
        blocks = _s(res.get("blocks", ""))
        if not blocks:
            problems.append(f"p0b.residual[{rid}]: missing 'blocks'")
        elif blocks not in slice_ids:
            problems.append(f"p0b.residual[{rid}]: 'blocks'='{blocks}' is not a known P0b slice id")
        else:
            blocked = next(sl for sl in p0b["slices"] if _s(sl.get("id")) == blocks)
            if _s(blocked.get("slice_status")) != "BLOCKED":
                problems.append(
                    f"p0b.residual[{rid}]: blocks '{blocks}' but that slice is "
                    f"'{blocked.get('slice_status')}', not BLOCKED"
                )

    for row in doc["product_wbs"]:
        wid = row.get("id", "?")
        _chk(f"wbs[{wid}]", "realization_status", row.get("realization_status"), real)
        _chk(f"wbs[{wid}]", "work_status", row.get("work_status"), work)
        for tk, tv in (row.get("subtracks") or {}).items():
            _chk(f"wbs[{wid}].subtrack[{tk}]", "value", tv, union_rd)
    return problems


# ── (fix 1) exact critical-value extraction from the parsed YAML ──────────────
def extract_canonical(doc: dict) -> dict[str, str]:
    pp = doc["production_position"]
    ns = doc["north_star"]
    cr = doc["coherence_runtime_reconciliation"]
    lc = doc["legacy_coverage"]
    p0b = doc["p0b_vertical_contract"]
    a018, a024 = _adr_row(doc, "ADR-018"), _adr_row(doc, "ADR-024")

    canon: dict[str, str] = {
        "reconciled_against_main_sha": _s(pp["reconciled_against_main_sha"]),
        "deployed_runtime_sha": _s(pp["deployed_runtime_sha"]),
        "reliability_operability_baseline": _s(pp["reliability_operability_baseline"]),
        "product_value_delivered": _s(pp["product_value_delivered"]),
        "current_product_wedge_id": _s(ns["current_product_wedge_id"]),
        "coherence.global_authoritative_cutover": _s(cr["global_authoritative_cutover"]),
        "legacy_coverage.unmapped_open_legacy_items": _s(lc["unmapped_open_legacy_items"]),
        "adr.ADR-018.realization": _s(a018["realization_status"]),
        "adr.ADR-018.deployment": _s(a018["deployment_status"]),
        "adr.ADR-018.prod_validation": _s(a018["prod_validation_status"]),
        "adr.ADR-024.realization": _s(a024["realization_status"]),
        "adr.ADR-024.deployment": _s(a024["deployment_status"]),
        "adr.ADR-024.prod_validation": _s(a024["prod_validation_status"]),
        "p0b.done_digest": hashlib.sha256(_norm(p0b["done_definition"]).encode()).hexdigest()[:16],
        "p0b.invariant_ids": ",".join(_s(x) for x in p0b["invariant_ids"]),
    }
    for sl in p0b["slices"]:
        canon[f"p0b.slice.{_s(sl['id'])}.status"] = _s(sl["slice_status"])
    canon["p0b.residual_ids"] = ",".join(_s(r["id"]) for r in p0b["residuals"])
    for res in p0b["residuals"]:
        rid = _s(res["id"])
        canon[f"p0b.residual.{rid}.status"] = _s(res["status"])
        canon[f"p0b.residual.{rid}.blocks"] = _s(res["blocks"])
    for wid in _WBS_IDS:
        row = _wbs_row(doc, wid)
        canon[f"wbs.{wid}.realization"] = _s(row["realization_status"])
        canon[f"wbs.{wid}.work_status"] = _s(row["work_status"])
    return canon


def render_block(canon: dict[str, str]) -> str:
    lines = [
        f"{_BLOCK_START} (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->",
        "```control",
    ]
    lines += [f"{k}={v}" for k, v in canon.items()]
    lines += ["```", f"{_BLOCK_END} -->"]
    return "\n".join(lines)


def parse_md_block(md_text: str) -> dict[str, str]:
    start = md_text.find(_BLOCK_START)
    end = md_text.find(_BLOCK_END)
    if start == -1 or end == -1 or end < start:
        return {}
    body = md_text[start:end]
    out: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if "=" in line and not line.startswith("<!--") and not line.startswith("```"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def compare(yaml_canon: dict[str, str], md_canon: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if not md_canon:
        return ["MD canonical-control block missing or unparseable (markers not found)"]
    for k, yv in yaml_canon.items():
        if k not in md_canon:
            problems.append(f"MD missing canonical key '{k}' (YAML='{yv}')")
        elif md_canon[k] != yv:
            problems.append(f"VALUE DRIFT '{k}': YAML='{yv}' MD='{md_canon[k]}'")
    for k in md_canon:
        if k not in yaml_canon:
            problems.append(f"MD extra canonical key '{k}' not in YAML")
    return problems


# ── orchestration ─────────────────────────────────────────────────────────────
def run(yaml_path: Path = _YAML, md_path: Path = _MD) -> list[str]:
    doc = load_yaml(yaml_path)
    problems = validate_enums(doc)
    problems += compare(extract_canonical(doc), parse_md_block(md_path.read_text(encoding="utf-8")))
    return problems


def main(argv: list[str]) -> int:
    if "--emit" in argv:
        print(render_block(extract_canonical(load_yaml())))
        return 0
    problems = run()
    if problems:
        print("PARITY FAIL — control-integrity violations:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    n = len(extract_canonical(load_yaml()))
    print(f"PARITY OK — enums valid + {n} critical values match MD<->YAML exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
