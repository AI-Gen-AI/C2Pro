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
import re
import sys
from pathlib import Path

import yaml

import validate_qualification_evidence as qualification_evidence

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

_QUALIFICATION_LANES = ("P0b", "P0c", "P0d")
_EXPECTED_QUALIFICATION_TARGETS = {
    "P0b": [
        {"kind": "adr", "id": "ADR-024", "field": "prod_validation_status", "promote_to": "PROD_VALIDATED"},
        {"kind": "p0b_slice", "id": "P0b-L4-5", "field": "slice_status", "promote_to": "DONE"},
    ],
    "P0c": [
        {"kind": "adr", "id": "ADR-015", "field": "prod_validation_status", "promote_to": "PROD_VALIDATED"},
        {"kind": "adr", "id": "ADR-016", "field": "prod_validation_status", "promote_to": "PROD_VALIDATED"},
    ],
    "P0d": [
        {
            "kind": "wbs_subtrack",
            "id": "PWBS-EXEC-REPORTING",
            "subtrack": "current_state",
            "field": "prod_validation_status",
            "promote_to": "PROD_VALIDATED",
        },
    ],
}


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
def _validate_residuals(
    p0b: dict,
    residual_allowed: set[str],
    blocking_allowed: set[str],
    slice_ids: set[str],
) -> list[str]:
    """Validate the P0b residual registry, including the schema-v5 blocking model.

    A residual declares whether it CURRENTLY gates a slice. Before v5 every residual was
    forced to name a blocked slice, so real-but-non-blocking work could only be registered
    by claiming a blocker it does not have.

    - BLOCKING     => 'blocks' is required, must name a real slice, and that slice must
                      itself be BLOCKED.
    - NON_BLOCKING => 'blocks' must be ABSENT. Not null, not empty: a present-but-blank
                      key still reads as an edge to a reviewer scanning the YAML.
    """
    problems: list[str] = []
    residuals = p0b.get("residuals")
    if not residuals:
        problems.append("p0b_vertical_contract: no 'residuals' registered (open residuals must be explicit)")
        return problems

    for res in residuals:
        rid = res.get("id", "?")
        where = f"p0b.residual[{rid}]"
        if res.get("status") is None:
            problems.append(f"{where}: missing 'status'")
        elif _s(res.get("status")) not in residual_allowed:
            problems.append(
                f"{where}: 'status'='{res.get('status')}' not in {sorted(residual_allowed)}"
            )

        blocking = _s(res.get("blocking", ""))
        if res.get("blocking") is None:
            problems.append(f"{where}: missing 'blocking'")
        elif blocking not in blocking_allowed:
            problems.append(
                f"{where}: 'blocking'='{res.get('blocking')}' not in {sorted(blocking_allowed)}"
            )

        if blocking == "BLOCKING":
            problems.extend(_validate_blocking_edge(where, res, p0b, slice_ids))
        elif blocking == "NON_BLOCKING" and "blocks" in res:
            problems.append(f"{where}: NON_BLOCKING residual must omit 'blocks' entirely")
    return problems


def _validate_blocking_edge(where: str, res: dict, p0b: dict, slice_ids: set[str]) -> list[str]:
    """A BLOCKING residual must name a real slice that is itself currently BLOCKED."""
    blocks = _s(res.get("blocks", ""))
    if not blocks:
        return [f"{where}: BLOCKING residual is missing 'blocks'"]
    if blocks not in slice_ids:
        return [f"{where}: 'blocks'='{blocks}' is not a known P0b slice id"]
    blocked = next(sl for sl in p0b["slices"] if _s(sl.get("id")) == blocks)
    if _s(blocked.get("slice_status")) != "BLOCKED":
        return [
            f"{where}: blocks '{blocks}' but that slice is "
            f"'{blocked.get('slice_status')}', not BLOCKED"
        ]
    return []


def validate_enums(doc: dict) -> list[str]:
    problems: list[str] = []
    enums = doc["status_enums"]
    design = set(enums["design_status"])
    real = set(enums["realization_status"])
    dep = set(enums["deployment_status"])
    prod = set(enums["prod_validation_status"])
    work = set(enums["work_status"])
    union_rd = real | dep
    qualification = set(enums["qualification_status"])

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
    blocking_allowed = set(enums["residual_blocking"])
    slice_ids = {_s(sl.get("id")) for sl in (p0b.get("slices") or [])}

    for sl in p0b.get("slices") or []:
        sid = sl.get("id", "?")
        _chk(f"p0b.slice[{sid}]", "slice_status", sl.get("slice_status"), slice_allowed)
        if "status" in sl:
            problems.append(
                f"p0b.slice[{sid}]: legacy free-form 'status' present; use validated 'slice_status'"
            )

    has_next_slice = "next_slice" in p0b
    next_raw = p0b.get("next_slice")
    next_slice = _s(next_raw) if next_raw is not None else ""
    unfinished_slices = [
        sl for sl in (p0b.get("slices") or []) if _s(sl.get("slice_status")) != "DONE"
    ]
    if not has_next_slice:
        problems.append(
            "p0b_vertical_contract: missing 'next_slice' field "
            "(use null only when every P0b slice is DONE)"
        )
    elif not next_slice:
        if unfinished_slices:
            problems.append(
                "p0b_vertical_contract: 'next_slice' may be null only when every P0b slice is DONE"
            )
    elif next_slice not in slice_ids:
        problems.append(f"p0b_vertical_contract: 'next_slice'='{next_slice}' is not a known P0b slice id")
    else:
        nxt = next(sl for sl in p0b["slices"] if _s(sl.get("id")) == next_slice)
        if _s(nxt.get("slice_status")) == "DONE":
            problems.append(
                f"p0b_vertical_contract: 'next_slice'='{next_slice}' is already DONE; "
                "the next authorized action cannot be a finished slice"
            )

    problems.extend(_validate_residuals(p0b, residual_allowed, blocking_allowed, slice_ids))

    for row in doc["product_wbs"]:
        wid = row.get("id", "?")
        _chk(f"wbs[{wid}]", "realization_status", row.get("realization_status"), real)
        _chk(f"wbs[{wid}]", "work_status", row.get("work_status"), work)
        for tk, tv in (row.get("subtracks") or {}).items():
            if isinstance(tv, dict):
                for field, allowed in (
                    ("realization_status", real),
                    ("deployment_status", dep),
                    ("prod_validation_status", prod),
                ):
                    if field in tv:
                        _chk(f"wbs[{wid}].subtrack[{tk}]", field, tv[field], allowed)
            else:
                _chk(f"wbs[{wid}].subtrack[{tk}]", "value", tv, union_rd)

    lanes = ((doc.get("qualification_control") or {}).get("lanes") or {})
    for lane in _QUALIFICATION_LANES:
        row = lanes.get(lane)
        if not isinstance(row, dict):
            problems.append(f"qualification[{lane}]: missing lane mapping")
        else:
            _chk(
                f"qualification[{lane}]",
                "qualification_status",
                row.get("qualification_status"),
                qualification,
            )
    return problems


def _validate_p0b_reconciliation_binding(
    doc: dict,
    lane_row: dict,
    bundle_doc: dict,
) -> list[str]:
    """Bind the explicit P0b reconciliation record to the accepted Phase-A bundle.

    The lane's hash proves which bundle was accepted. This second binding prevents
    a later edit from claiming a different production runtime in Product Control
    while retaining the same accepted bundle.
    """
    problems: list[str] = []
    delta = doc.get("reconciliation_delta_2026_10_04_p0b")
    where = "reconciliation_delta_2026_10_04_p0b"
    if not isinstance(delta, dict):
        return [f"{where}: required for accepted P0b qualification"]

    current_main = delta.get("current_main_sha")
    reconciled = (doc.get("production_position") or {}).get("reconciled_against_main_sha")
    if current_main != reconciled:
        problems.append(
            f"{where}.current_main_sha must equal production_position.reconciled_against_main_sha"
        )

    accepted = delta.get("qualification_bundle")
    if not isinstance(accepted, dict):
        problems.append(f"{where}.qualification_bundle must be a mapping")
    else:
        if accepted.get("ref") != lane_row.get("bundle_ref"):
            problems.append(f"{where}.qualification_bundle.ref must match qualification[P0b].bundle_ref")
        if accepted.get("sha256") != lane_row.get("bundle_sha256"):
            problems.append(
                f"{where}.qualification_bundle.sha256 must match qualification[P0b].bundle_sha256"
            )
        if accepted.get("validator_verdict") != bundle_doc.get("validator_verdict"):
            problems.append(
                f"{where}.qualification_bundle.validator_verdict must match accepted bundle"
            )

    runtime = delta.get("runtime_binding")
    if not isinstance(runtime, dict):
        return problems + [f"{where}.runtime_binding must be a mapping"]

    bundle_runtime = bundle_doc.get("runtime_bindings")
    evidence_refs = bundle_doc.get("evidence_refs")
    if not isinstance(bundle_runtime, list) or not isinstance(evidence_refs, list):
        return problems

    by_plane = {
        row.get("plane"): row
        for row in bundle_runtime
        if isinstance(row, dict) and isinstance(row.get("plane"), str)
    }
    refs = {
        row.get("id"): row
        for row in evidence_refs
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }

    for delta_key, plane in (("backend", "backend"), ("frontend", "frontend")):
        claimed = runtime.get(delta_key)
        proven = by_plane.get(plane)
        if not isinstance(claimed, dict):
            problems.append(f"{where}.runtime_binding.{delta_key} must be a mapping")
            continue
        if not isinstance(proven, dict):
            problems.append(f"{where}: accepted bundle has no {plane} runtime binding")
            continue
        for field in ("provider", "commit_sha", "terminal_state"):
            if claimed.get(field) != proven.get(field):
                problems.append(
                    f"{where}.runtime_binding.{delta_key}.{field} must match accepted bundle"
                )

        evidence_id = proven.get("deployment_evidence_ref")
        evidence = refs.get(evidence_id)
        if not isinstance(evidence, dict):
            problems.append(
                f"{where}: accepted bundle deployment evidence {evidence_id!r} is missing"
            )
            continue
        ref = evidence.get("ref")
        expected_prefix = f"{proven.get('provider')}:"
        if not isinstance(ref, str) or not ref.startswith(expected_prefix):
            problems.append(
                f"{where}: accepted {plane} deployment evidence has invalid provider locator"
            )
            continue
        if claimed.get("deployment_id") != ref[len(expected_prefix):]:
            problems.append(
                f"{where}.runtime_binding.{delta_key}.deployment_id must match accepted bundle evidence"
            )
    return problems


# ── schema-v7 Product Qualification promotion guard ───────────────────────────
def _qualification_adr_row(doc: dict, target_id: str) -> dict:
    """Resolve exactly one canonical ADR family member for a qualification target."""
    rows = doc.get("adr_realization")
    if not isinstance(rows, list):
        raise KeyError("adr_realization is not a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and (
            row.get("adr") == target_id
            or (
                isinstance(row.get("adr"), str)
                and row["adr"].startswith(target_id + "-")
            )
        )
    ]
    if len(matches) != 1:
        raise KeyError(
            f"qualification ADR target {target_id} must resolve exactly once; found {len(matches)}"
        )
    return matches[0]


def _qualification_wbs_row(doc: dict, target_id: str) -> dict:
    rows = doc.get("product_wbs")
    if not isinstance(rows, list):
        raise KeyError("product_wbs is not a list")
    matches = [
        row for row in rows if isinstance(row, dict) and row.get("id") == target_id
    ]
    if len(matches) != 1:
        raise KeyError(
            f"qualification WBS target {target_id} must resolve exactly once; found {len(matches)}"
        )
    return matches[0]


def _p0b_slice(doc: dict, slice_id: str) -> dict:
    p0b = doc.get("p0b_vertical_contract")
    rows = p0b.get("slices") if isinstance(p0b, dict) else None
    if not isinstance(rows, list):
        raise KeyError("p0b_vertical_contract.slices is not a list")
    matches = [
        row for row in rows if isinstance(row, dict) and row.get("id") == slice_id
    ]
    if len(matches) != 1:
        raise KeyError(
            f"qualification P0b slice target {slice_id} must resolve exactly once; found {len(matches)}"
        )
    return matches[0]


def _qualification_target_value(doc: dict, target: dict) -> object:
    kind = target["kind"]
    if kind == "adr":
        return _qualification_adr_row(doc, target["id"])[target["field"]]
    if kind == "p0b_slice":
        return _p0b_slice(doc, target["id"])[target["field"]]
    if kind == "wbs_subtrack":
        return _qualification_wbs_row(doc, target["id"])["subtracks"][target["subtrack"]][target["field"]]
    raise KeyError(f"unsupported qualification target kind: {kind}")


def validate_qualification_control(
    doc: dict,
    *,
    root: Path = _ROOT,
    bundle_validator=None,
    bundle_loader=None,
) -> list[str]:
    """Validate compact Product-Control refs and fail closed on lifecycle promotion.

    Phase-A bundles remain evidence only. This guard makes a structurally valid,
    capability-matched PASS bundle necessary for a mapped lifecycle promotion,
    but never mutates/promotes lifecycle state itself.
    """
    problems: list[str] = []
    qc = doc.get("qualification_control")
    if not isinstance(qc, dict):
        return ["qualification_control: missing mapping"]
    qc_schema_version = qc.get("schema_version")
    if type(qc_schema_version) is not int or qc_schema_version != 1:
        problems.append("qualification_control.schema_version must be integer 1")
    if qc.get("evidence_contract") != "c2pro-product-qualification-evidence-v1":
        problems.append("qualification_control.evidence_contract must bind Phase-A v1")
    if qc.get("evidence_directory") != "evidence/product-qualification":
        problems.append("qualification_control.evidence_directory must use the fixed Phase-A directory")
    if qc.get("validator") != "validation/product/validate_qualification_evidence.py":
        problems.append("qualification_control.validator must bind the canonical Phase-A validator")

    lanes = qc.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != set(_QUALIFICATION_LANES):
        problems.append("qualification_control.lanes must contain exactly P0b, P0c and P0d")
        return problems

    if bundle_validator is None:
        bundle_validator = qualification_evidence.validate_path
    if bundle_loader is None:
        bundle_loader = qualification_evidence.load_yaml

    allowed_status = set(doc["status_enums"]["qualification_status"])
    evidence_parent = root / "evidence"
    evidence_root = evidence_parent / "product-qualification"
    evidence_path_has_symlink = any(
        component.is_symlink()
        for component in (evidence_parent, evidence_root)
    )
    expected_root = evidence_root.resolve()
    if evidence_path_has_symlink:
        problems.append(
            "qualification_control.evidence_directory path components must not be symlinks"
        )

    for lane in _QUALIFICATION_LANES:
        row = lanes[lane]
        where = f"qualification[{lane}]"
        if not isinstance(row, dict):
            problems.append(f"{where}: lane must be a mapping")
            continue
        status = row.get("qualification_status")
        status_value = status if isinstance(status, str) else ""
        if not isinstance(status, str) or status not in allowed_status:
            problems.append(f"{where}: invalid qualification_status={status!r}")

        targets = row.get("lifecycle_targets")
        if targets != _EXPECTED_QUALIFICATION_TARGETS[lane]:
            problems.append(f"{where}: lifecycle_targets do not match the canonical capability mapping")
            targets = _EXPECTED_QUALIFICATION_TARGETS[lane]

        bundle_ref = row.get("bundle_ref")
        bundle_sha = row.get("bundle_sha256")
        bundle_doc = None
        bundle_valid = False

        if status_value in {"REQUIRED", "COLLECTING"}:
            if bundle_ref is not None or bundle_sha is not None:
                problems.append(
                    f"{where}: {status} must not claim an accepted bundle_ref/bundle_sha256"
                )
        elif status_value in {"PASS", "FAIL"}:
            if not isinstance(bundle_ref, str) or not bundle_ref.strip():
                problems.append(f"{where}: {status} requires bundle_ref")
            if (
                not isinstance(bundle_sha, str)
                or not qualification_evidence.SHA256_RE.fullmatch(bundle_sha)
            ):
                problems.append(f"{where}: {status} requires a lowercase 64-hex bundle_sha256")

        if isinstance(bundle_ref, str) and bundle_ref.strip():
            rel = Path(bundle_ref)
            if (
                rel.is_absolute()
                or ".." in rel.parts
                or rel.parent != Path("evidence/product-qualification")
                or rel.suffix != ".yaml"
            ):
                problems.append(
                    f"{where}: bundle_ref must be one YAML file in evidence/product-qualification"
                )
            else:
                candidate = root / rel
                if candidate.is_symlink():
                    problems.append(f"{where}: bundle_ref must not be a symlink")
                else:
                    path = candidate.resolve()
                    if path.parent != expected_root:
                        problems.append(f"{where}: bundle_ref resolves outside the fixed evidence directory")
                    elif not path.exists() or not path.is_file():
                        problems.append(f"{where}: bundle_ref must resolve to a regular file")
                    else:
                        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                        if isinstance(bundle_sha, str) and actual_sha != bundle_sha:
                            problems.append(f"{where}: bundle_sha256 does not match bundle bytes")
                        bundle_problems = list(bundle_validator(path))
                        if bundle_problems:
                            problems.extend(
                                f"{where}: Phase-A bundle invalid: {problem}"
                                for problem in bundle_problems
                            )
                        else:
                            bundle_doc = bundle_loader(path)
                            if bundle_doc.get("capability_id") != lane:
                                problems.append(
                                    f"{where}: bundle capability_id={bundle_doc.get('capability_id')!r} "
                                    f"does not match {lane}"
                                )
                            expected_verdict = "PASS" if status_value == "PASS" else "FAIL"
                            if status_value in {"PASS", "FAIL"} and bundle_doc.get("validator_verdict") != expected_verdict:
                                problems.append(
                                    f"{where}: {status_value} requires Phase-A validator_verdict={expected_verdict}"
                                )
                            bundle_valid = (
                                bundle_doc.get("capability_id") == lane
                                and (
                                    status_value not in {"PASS", "FAIL"}
                                    or bundle_doc.get("validator_verdict") == expected_verdict
                                )
                            )
                            if (
                                lane == "P0b"
                                and status_value == "PASS"
                                and isinstance(bundle_doc.get("runtime_bindings"), list)
                            ):
                                problems.extend(
                                    _validate_p0b_reconciliation_binding(doc, row, bundle_doc)
                                )

        promoted = []
        for target in targets:
            try:
                promoted.append(
                    _s(_qualification_target_value(doc, target)) == _s(target["promote_to"])
                )
            except (KeyError, TypeError) as exc:
                problems.append(f"{where}: lifecycle target cannot be resolved: {exc}")
                promoted.append(False)

        if any(promoted):
            if not all(promoted):
                problems.append(f"{where}: mapped lifecycle targets must promote atomically")
            if status_value != "PASS":
                problems.append(f"{where}: lifecycle promotion requires qualification_status=PASS")
            if not bundle_valid:
                problems.append(f"{where}: lifecycle promotion requires a validated PASS Phase-A bundle")

    return problems


# ── (fix 1) exact critical-value extraction from the parsed YAML ──────────────
def extract_canonical(doc: dict) -> dict[str, str]:
    pp = doc["production_position"]
    qc = doc.get("qualification_control")
    if not isinstance(qc, dict):
        qc = {}
    ns = doc["north_star"]
    ps = doc["product_semantics"]
    pcm = doc["project_controls_model"]
    cr = doc["coherence_runtime_reconciliation"]
    lc = doc["legacy_coverage"]
    p0b = doc["p0b_vertical_contract"]
    a018 = _adr_row(doc, "ADR-018")
    a024 = _adr_row(doc, "ADR-024")
    a025 = _adr_row(doc, "ADR-025")
    a026 = _adr_row(doc, "ADR-026")
    a027 = _adr_row(doc, "ADR-027")
    a028 = _adr_row(doc, "ADR-028")
    pc_wbs = _wbs_row(doc, "PWBS-PROJECT-CONTROLS")

    canon: dict[str, str] = {
        "reconciled_against_main_sha": _s(pp["reconciled_against_main_sha"]),
        "deployed_runtime_sha": _s(pp["deployed_runtime_sha"]),
        "reliability_operability_baseline": _s(pp["reliability_operability_baseline"]),
        "product_value_delivered": _s(pp["product_value_delivered"]),
        "current_product_wedge_id": _s(ns["current_product_wedge_id"]),
        "coherence.global_authoritative_cutover": _s(cr["global_authoritative_cutover"]),
        "legacy_coverage.unmapped_open_legacy_items": _s(lc["unmapped_open_legacy_items"]),
        "project_controls.invariant": _s(pcm["invariant"]),
        "product_semantics.canonical_dimensions": ",".join(_s(x) for x in ps["canonical_dimensions"]),
        "wbs.PWBS-PROJECT-CONTROLS.priority": _s(pc_wbs["priority"]),
        "adr.ADR-018.design": _s(a018["design_status"]),
        "adr.ADR-018.realization": _s(a018["realization_status"]),
        "adr.ADR-018.deployment": _s(a018["deployment_status"]),
        "adr.ADR-018.prod_validation": _s(a018["prod_validation_status"]),
        "adr.ADR-024.design": _s(a024["design_status"]),
        "adr.ADR-024.realization": _s(a024["realization_status"]),
        "adr.ADR-024.deployment": _s(a024["deployment_status"]),
        "adr.ADR-024.prod_validation": _s(a024["prod_validation_status"]),
        "adr.ADR-025.design": _s(a025["design_status"]),
        "adr.ADR-025.realization": _s(a025["realization_status"]),
        "adr.ADR-025.deployment": _s(a025["deployment_status"]),
        "adr.ADR-025.prod_validation": _s(a025["prod_validation_status"]),
        "adr.ADR-026.design": _s(a026["design_status"]),
        "adr.ADR-026.realization": _s(a026["realization_status"]),
        "adr.ADR-026.deployment": _s(a026["deployment_status"]),
        "adr.ADR-026.prod_validation": _s(a026["prod_validation_status"]),
        "adr.ADR-027.design": _s(a027["design_status"]),
        "adr.ADR-027.realization": _s(a027["realization_status"]),
        "adr.ADR-027.deployment": _s(a027["deployment_status"]),
        "adr.ADR-027.prod_validation": _s(a027["prod_validation_status"]),
        "adr.ADR-028.design": _s(a028["design_status"]),
        "adr.ADR-028.realization": _s(a028["realization_status"]),
        "adr.ADR-028.deployment": _s(a028["deployment_status"]),
        "adr.ADR-028.prod_validation": _s(a028["prod_validation_status"]),
        "p0b.done_digest": hashlib.sha256(_norm(p0b["done_definition"]).encode()).hexdigest()[:16],
        "p0b.invariant_ids": ",".join(_s(x) for x in p0b["invariant_ids"]),
        "p0b.next_slice": _s(p0b.get("next_slice")) if p0b.get("next_slice") is not None else "NONE",
    }
    exec_current = _wbs_row(doc, "PWBS-EXEC-REPORTING")["subtracks"]["current_state"]
    canon["wbs.PWBS-EXEC-REPORTING.current_state.realization"] = _s(
        exec_current["realization_status"]
    )
    canon["wbs.PWBS-EXEC-REPORTING.current_state.deployment"] = _s(
        exec_current["deployment_status"]
    )
    canon["wbs.PWBS-EXEC-REPORTING.current_state.prod_validation"] = _s(
        exec_current["prod_validation_status"]
    )
    lanes = qc.get("lanes")
    lanes = lanes if isinstance(lanes, dict) else {}
    for lane in _QUALIFICATION_LANES:
        row = lanes.get(lane)
        if not isinstance(row, dict):
            canon[f"qualification.{lane}.status"] = "INVALID"
            canon[f"qualification.{lane}.bundle_ref"] = "INVALID"
            canon[f"qualification.{lane}.evidence_digest"] = "INVALID"
            canon[f"qualification.{lane}.targets_digest"] = "INVALID"
            continue
        bundle_ref = row.get("bundle_ref")
        bundle_sha = row.get("bundle_sha256")
        targets = row.get("lifecycle_targets")
        targets_digest = (
            hashlib.sha256(yaml.safe_dump(targets, sort_keys=True).encode()).hexdigest()[:16]
            if isinstance(targets, list)
            else "INVALID"
        )
        canon[f"qualification.{lane}.status"] = _s(row.get("qualification_status", "INVALID"))
        canon[f"qualification.{lane}.bundle_ref"] = _s(bundle_ref) if bundle_ref else "NONE"
        canon[f"qualification.{lane}.evidence_digest"] = (
            _s(bundle_sha)[:16] if bundle_sha else "NONE"
        )
        canon[f"qualification.{lane}.targets_digest"] = targets_digest
    for sl in p0b["slices"]:
        canon[f"p0b.slice.{_s(sl['id'])}.status"] = _s(sl["slice_status"])
    canon["p0b.residual_ids"] = ",".join(_s(r["id"]) for r in p0b["residuals"])
    for res in p0b["residuals"]:
        rid = _s(res["id"])
        canon[f"p0b.residual.{rid}.status"] = _s(res["status"])
        # `.blocking` is emitted for every residual; `.blocks` only exists for a
        # BLOCKING one, so a NON_BLOCKING residual has no blocker line to contradict.
        canon[f"p0b.residual.{rid}.blocking"] = _s(res["blocking"])
        if _s(res["blocking"]) == "BLOCKING":
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


def validate_work_package_mirror(doc: dict, md_text: str) -> list[str]:
    """Fail if a Product task's §13.6 table status/owner differs from the YAML.

    The generated canonical block covers global product states; task-level
    assignments live in the human table. Verify that table directly rather than
    treating a passing 78-value canonical block as proof of package parity.
    """
    problems: list[str] = []
    start = "### 13.6 Plan de entrega por subtareas"
    stop = "**Orden de gates y bifurcaciones:**"
    if start not in md_text or stop not in md_text.split(start, 1)[1]:
        return ["PQ-HITL work-package mirror §13.6 missing"]
    section = md_text.split(start, 1)[1].split(stop, 1)[0]
    observed: dict[str, tuple[str, str, str, str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("| PQ-HITL-"):
            continue
        cells = [value.strip() for value in line.split("|")[1:-1]]
        if len(cells) < 5:
            problems.append("PQ-HITL §13.6 malformed task row")
            continue
        task_id = cells[0].split(" / ", 1)[0].strip()
        parent = re.search(r"/ \[#(\d+)\]", cells[0])
        role_cells = [value.strip() for value in cells[2].split("·")]
        if parent is None or len(role_cells) != 3:
            problems.append(f"PQ-HITL task {task_id}: invalid issue/role/size/priority projection")
            continue
        if task_id in observed:
            problems.append(f"PQ-HITL task {task_id}: duplicate §13.6 mirror row")
            continue
        observed[task_id] = (parent.group(1), *role_cells, cells[3])

    packages = doc["product_quality_hitl_2026_10_08"]["delivery_specification"]["work_packages"]
    expected_ids = {str(row["id"]) for row in packages}
    for row in packages:
        task_id = str(row["id"])
        expected = tuple(_s(row[key]) for key in ("parent_issue", "role", "size", "priority", "status"))
        actual = observed.get(task_id)
        if actual is None:
            problems.append(f"PQ-HITL task {task_id}: missing §13.6 mirror row")
            continue
        for key, yv, mv in zip(("parent_issue", "role", "size", "priority", "status"), expected, actual):
            if yv != mv:
                problems.append(f"PQ-HITL task {task_id}: {key} VALUE DRIFT YAML='{yv}' MD='{mv}'")
    for task_id in observed.keys() - expected_ids:
        problems.append(f"PQ-HITL task {task_id}: extra §13.6 row not in YAML")
    return problems


# ── orchestration ─────────────────────────────────────────────────────────────
def run(yaml_path: Path = _YAML, md_path: Path = _MD) -> list[str]:
    doc = load_yaml(yaml_path)
    problems = validate_enums(doc)
    problems += validate_qualification_control(doc, root=yaml_path.resolve().parents[2])
    md_text = md_path.read_text(encoding="utf-8")
    problems += compare(extract_canonical(doc), parse_md_block(md_text))
    problems += validate_work_package_mirror(doc, md_text)
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
