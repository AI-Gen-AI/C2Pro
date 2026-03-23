"""
TS-INT-DOC-PROC-003: Canonical verification asset contract tests.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_proof_scripts_use_canonical_analysis_route() -> None:
    prove_script = _read("scripts/prove_real_contract_flow.py")
    checkpointer_script = _read("scripts/test_checkpointer_e2e.py")

    assert "/api/v1/analysis/analyze" in prove_script
    assert "/api/v1/analysis/analyze" in checkpointer_script
    assert "/api/v1/analyze" not in prove_script
    assert "/api/v1/analyze" not in checkpointer_script


def test_real_contract_proof_records_stage_specific_checkpoints() -> None:
    prove_script = _read("scripts/prove_real_contract_flow.py")

    assert "uploaded" in prove_script
    assert "parsed" in prove_script
    assert "analyzed" in prove_script
    assert "checkpoints" in prove_script


def test_checked_in_openapi_uses_canonical_analysis_route() -> None:
    openapi = _read("docs/api/openapi.yaml")

    assert "/api/v1/analysis/analyze:" in openapi
    assert "/api/v1/analyze:" not in openapi
