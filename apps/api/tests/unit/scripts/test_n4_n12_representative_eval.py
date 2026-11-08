"""Production-profile fixture review; no provider calls or writable tenants."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts import n4_n12_real_ai_eval as old
from scripts import n4_n12_representative_eval as trial


def test_representative_n4_uses_same_prellm_graph_preparation() -> None:
    from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionTool

    fixture = old.load_fixture()
    source = old._source_text(fixture)
    tool = RiskExtractionTool()
    real_seam = tool.extract_input_from_state(
        {
            "document_text": source,
            "anonymized_text": source,
            "pii_anonymization_complete": True,
        }
    )
    candidate = trial.prepare_graph_n4_input(tool, source)
    assert candidate.document_text == real_seam.document_text
    assert candidate.max_risks == 20
    assert candidate.filter_relevant is True
    coverage = trial.input_coverage(source, candidate.document_text, fixture)
    assert coverage["source_clauses_retained"] == 9
    assert coverage["source_clause_ids_retained"] == [f"EPC-{i:02d}" for i in range(1, 10)]
    assert coverage["n2_mode"] == "synthetic_projection_not_real_anonymizer"


def test_preparation_does_not_fallback_to_raw_source_on_empty_n2_projection() -> None:
    class EmptyN2Tool:
        def extract_input_from_state(self, state):
            assert state["pii_anonymization_complete"] is True
            return SimpleNamespace(document_text="")

    with pytest.raises(RuntimeError, match="N4_NO_LLM_SOURCE_CONTEXT"):
        trial.prepare_graph_n4_input(EmptyN2Tool(), "secret content")


def test_real_route_is_sonnet_unlike_previous_economic_haiku_profile() -> None:
    from src.core.ai.model_router import AITaskType, get_model_router

    routing = get_model_router()
    standard = routing.select_model_with_budget_mode(
        task_type=AITaskType.COMPLEX_EXTRACTION, low_budget_mode=False
    )
    economy = routing.select_model_with_budget_mode(
        task_type=AITaskType.COMPLEX_EXTRACTION, low_budget_mode=True
    )
    assert standard.name == trial.REQUIRED_MODEL == "claude-sonnet-4-6"
    assert standard.max_tokens == trial.MAX_OUTPUT_TOKENS == 8192
    assert economy.name == "claude-haiku-4-5-20251001"
    assert economy.max_tokens == 4096
    assert trial.MAX_CALLS == 3 and trial.MAX_USD == 1.0


def representative_success() -> dict:
    fixture = old.load_fixture()
    source = old._source_text(fixture)
    clauses = {c["id"]: c["text"] for c in fixture["contract"]["clauses"]}
    n4 = old.score_n4(
        fixture,
        [
            {
                "category": item["category"],
                "source_quote": clauses[item["clause_id"]],
                "source_quote_status": "VERIFIED",
            }
            for item in fixture["n4_oracle"]["expected_risks"]
        ],
    )
    assert n4["true_positives"] == 9
    notes = (
        "EPC-04 defect obligation omitted. EPC-07 liability cap omitted. "
        "EPC-05 incorrect financial hardship and currency fluctuation excluded. "
        + " ".join(f"{ref}: “{clauses[ref][:125]}”" for ref in ("EPC-04", "EPC-05", "EPC-07"))
    )
    raw_findings = [
        {
            "clause_ref": ref,
            "issue_type": "contradiction" if ref == "EPC-05" else "omission",
            "source_quote": clauses[ref][:125],
            "explanation": "Grounded reference for testing only",
        }
        for ref in ("EPC-04", "EPC-05", "EPC-07")
    ]
    adversarial = {
        **old.score_n12(notes, source),
        **old.score_n12_structured_provenance({"findings": raw_findings}, source),
        "status": "UNASSESSED",
        "human_approval_required": True,
        "semantic_approval": False,
    }
    assert adversarial["critique_citation_validity"]
    chained = {
        "status": "UNASSESSED",
        "human_approval_required": True,
        "model_findings_unverified": 0,
        "model_findings_payload_valid": True,
        "model_findings_submitted": 0,
        "model_findings_source_verified": 0,
        "critique_invalid_quoted_citations": 0,
        "parse_failure_type": None,
        "response_sha256": "a" * 64,
        "model_declared_status": "OK",
        "model_neutral_ok_notes": True,
        "semantic_approval": False,
    }
    return {
        "n4": n4,
        "n12_adversarial": adversarial,
        "n12_chained": chained,
        "provider": {
            "calls": 3,
            "completed_calls": 3,
            "failed_calls": 0,
            "estimated_cost_usd": 0.17,
            "models": ["claude-sonnet-4-6"],
            "call_breakdown": [{"stop_reason": "end_turn"}] * 3,
        },
        "input_coverage": {"fixture_clauses": 9, "source_clauses_retained": 9},
    }


def test_technical_gates_pass_only_with_all_source_grounded_results() -> None:
    assert all(trial.verify_technical_gate(representative_success()).values())


@pytest.mark.parametrize(
    ("axis", "mutate"),
    [
        ("n4_nine_source_risks", lambda r: r["n4"].update(true_positives=8, omissions=1)),
        ("n4_nine_source_risks", lambda r: r["n4"].update(false_positives=1)),
        ("n4_source_prepared", lambda r: r["input_coverage"].update(source_clauses_retained=8)),
        ("provider_bounded", lambda r: r["provider"].update(estimated_cost_usd=1.001)),
        (
            "provider_bounded",
            lambda r: r["provider"]["call_breakdown"][0].update(stop_reason="max_tokens"),
        ),
        ("provider_bounded", lambda r: r["provider"].update(models=["claude-haiku-4-5-20251001"])),
        (
            "n12_adversarial_grounded",
            lambda r: r["n12_adversarial"].update(model_findings_unverified=1),
        ),
        (
            "n12_adversarial_grounded",
            lambda r: r["n12_adversarial"].update(human_approval_required=False),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(model_findings_unverified=1),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(semantic_approval=True),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(model_findings_payload_valid=False),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(critique_invalid_quoted_citations=1),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(parse_failure_type="JSONDecodeError"),
        ),
        ("n12_chained_no_invented_source", lambda r: r["n12_chained"].update(response_sha256=None)),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(model_declared_status="RETRY"),
        ),
        (
            "n12_chained_no_invented_source",
            lambda r: r["n12_chained"].update(model_neutral_ok_notes=False),
        ),
    ],
)
def test_gates_fail_closed(axis, mutate) -> None:
    report = deepcopy(representative_success())
    mutate(report)
    assert trial.verify_technical_gate(report)[axis] is False


def test_n4_fingerprints_contain_offsets_and_hashes_not_model_prose() -> None:
    fixture = old.load_fixture()
    source = old._source_text(fixture)
    clause = fixture["contract"]["clauses"][0]
    fingerprint = trial.n4_citation_fingerprints(
        [
            {
                "category": "SCHEDULE",
                "source_quote_status": "VERIFIED",
                "source_quote": clause["text"],
            }
        ],
        source,
    )[0]
    assert fingerprint["category"] == "SCHEDULE"
    assert fingerprint["normalized_start"] is not None
    assert fingerprint["normalized_end"] > fingerprint["normalized_start"]
    assert fingerprint["normalized_quote_characters"] > 80
    assert clause["text"] not in str(fingerprint)
    assert (
        trial.n4_citation_fingerprints(
            [
                {
                    "category": "LEGAL",
                    "source_quote_status": "NOT_FOUND_IN_DOCUMENT",
                    "source_quote": "A fictional risk.",
                }
            ],
            source,
        )[0]["normalized_start"]
        is None
    )


def test_evaluator_reports_oracle_failure_without_skipping_independent_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import json

    report = {
        "fixture_id": "synthetic",
        "profile": "normal_core_sonnet_8192",
        "gates": {"n4_nine_source_risks": False},
        "provider": {"completed_calls": 3, "estimated_cost_usd": 0.15},
    }

    async def fake_run() -> dict:
        return report

    output = tmp_path / "report.json"
    monkeypatch.setattr(trial, "run", fake_run)
    monkeypatch.setattr(trial, "RESULT_PATH", output)
    assert trial.main() == 0
    assert json.loads(output.read_text())["gates"]["n4_nine_source_risks"] is False
