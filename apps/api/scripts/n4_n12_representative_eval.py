"""Scoped Sonnet N4/N12 assessment with actual N4 preparation seam and HITL.

Three independently governed provider calls: N4 normal routing; N12 adversarial
oracle; N12 critique of actual N4 outputs. No DB, browser, tenant, production
write or HITL approval. Persist only sanitized metrics and hashes, no LLM prose.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

from scripts import n4_n12_real_ai_eval as oracle

RESULT_PATH = oracle.API_ROOT.parent / "web/playwright-report/n4-n12-representative-evaluation.json"
REQUIRED_MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 8192
MAX_CALLS = 3
MAX_USD = 1.0


class _FailClosedSpanishPiiAnonymizer:
    """Focal-only counterpart to the production anonymizer, without regex fallback.

    Uses the SAME regexes, recognizers, confidence threshold and token
    generation algorithm as PiiAnonymizerService. Any spaCy/Presidio failure
    raises before AnthropicWrapper can reach its model transport.
    """

    def __init__(self, analyzer: Any) -> None:
        self._analyzer = analyzer

    def anonymize_document(self, text: str) -> Any:
        from src.core.privacy import anonymizer as privacy

        mapping: dict[str, str] = {}
        anonymized = text
        for index, match in enumerate(privacy.PiiAnonymizerService._EMAIL_RE.findall(text), start=1):
            token = f"<EMAIL_ADDRESS_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)
        for index, match in enumerate(privacy.PiiAnonymizerService._SPANISH_ID_RE.findall(text), start=1):
            token = f"<SPANISH_ID_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)

        try:
            results = self._analyzer.analyze(
                text=anonymized,
                language=privacy._PRESIDIO_LANGUAGE,
                entities=list(privacy._PRESIDIO_ENTITIES),
                score_threshold=privacy._PRESIDIO_SCORE_THRESHOLD,
            )
            counters: dict[str, int] = {}
            token_by_value: dict[tuple[str, str], str] = {}
            replacements: list[tuple[int, int, str]] = []
            presidio_mapping: dict[str, str] = {}
            for result in sorted(results, key=lambda row: row.start):
                value = anonymized[result.start : result.end]
                key = (result.entity_type, value)
                token = token_by_value.get(key)
                if token is None:
                    counters[result.entity_type] = counters.get(result.entity_type, 0) + 1
                    token = f"[{result.entity_type}_{counters[result.entity_type]:03d}]"
                    token_by_value[key] = token
                    presidio_mapping[token] = value
                replacements.append((result.start, result.end, token))
            for start, end, token in sorted(replacements, key=lambda row: row[0], reverse=True):
                anonymized = anonymized[:start] + token + anonymized[end:]
            mapping.update(presidio_mapping)
        except Exception as exc:
            raise RuntimeError("PII_NER_INFERENCE_FAILED") from exc

        return privacy.AnonymizedResult(anonymized_text=anonymized, mapping=mapping)


def _require_fail_closed_spanish_ner() -> _FailClosedSpanishPiiAnonymizer:
    """Preflight in the SAME Python process that issues the paid N4/N12 calls."""
    from src.core.privacy import anonymizer as privacy

    if not privacy.PRESIDIO_AVAILABLE:
        raise RuntimeError("PII_NER_NOT_AVAILABLE")
    try:
        analyzer = privacy.PiiAnonymizerService._get_analyzer()
    except Exception as exc:
        raise RuntimeError("PII_NER_PREFLIGHT_FAILED") from exc
    if analyzer is None:
        raise RuntimeError("PII_NER_NOT_AVAILABLE")
    try:
        analyzer.analyze(
            text="El contrato lo firma Juan Perez en Madrid.",
            language=privacy._PRESIDIO_LANGUAGE,
            entities=list(privacy._PRESIDIO_ENTITIES),
            score_threshold=privacy._PRESIDIO_SCORE_THRESHOLD,
        )
    except Exception as exc:
        raise RuntimeError("PII_NER_PREFLIGHT_FAILED") from exc
    return _FailClosedSpanishPiiAnonymizer(analyzer)


def prepare_graph_n4_input(tool: Any, source: str) -> Any:
    """Use the same state->input method as the real N4 graph tool.

    The synthetic source is supplied as the N2 projection. The actual N2
    anonymizer is NOT run; this is not a real-document or tenant UAT.
    """
    from src.analysis.adapters.graph.schema import ProjectState

    state = cast(
        ProjectState,
        {
            "document_text": source,
            "anonymized_text": source,
            "pii_anonymization_complete": True,
        },
    )
    result = tool.extract_input_from_state(state)
    if not result.document_text.strip():
        raise RuntimeError("N4_NO_LLM_SOURCE_CONTEXT")
    return result


def input_coverage(source: str, sent: str, fixture: dict[str, Any]) -> dict[str, Any]:
    clauses = fixture["contract"]["clauses"]
    retained = [
        str(clause["id"]) for clause in clauses if f"{clause['id']}: {clause['text']}" in sent
    ]
    return {
        "fixture_clauses": len(clauses),
        "source_clauses_retained": len(retained),
        "source_clause_ids_retained": retained,
        "source_characters": len(source),
        "prepared_characters": len(sent),
        "prepared_sha256": hashlib.sha256(sent.encode()).hexdigest(),
        "n2_mode": "synthetic_projection_not_real_anonymizer",
    }


def n4_citation_fingerprints(risks: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """Provenance offsets and digests WITHOUT persisting model prose.

    The independent gate can recover the normalized source excerpt from the
    SHA-pinned synthetic corpus and re-score the oracle. This exposes invalid
    quotations and category mismatches without storing LLM responses.
    """
    normalized_source = oracle._normalized(source)
    out: list[dict[str, Any]] = []
    for index, risk in enumerate(risks):
        quote = oracle._normalized(risk.get("source_quote"))
        status = str(risk.get("source_quote_status") or "")
        located = normalized_source.find(quote) if quote else -1
        valid_location = status == "VERIFIED" and located >= 0
        out.append(
            {
                "index": index,
                "category": str(risk.get("category") or "").upper(),
                "source_quote_status": status,
                "normalized_quote_characters": len(quote),
                "normalized_quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                "normalized_start": located if valid_location else None,
                "normalized_end": (located + len(quote)) if valid_location else None,
            }
        )
    return out


class ObservedRealCritiquePort:
    """Reuse production JSON parser and normal model routing; do not leak text."""

    def __init__(self, wrapper: Any) -> None:
        self.wrapper = wrapper
        self.payload: Any = None
        self.parse_failure_type: str | None = None
        self.response_sha256: str | None = None

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        from src.analysis.adapters.ai.anthropic_client import AIService
        from src.core.ai.anthropic_wrapper import AIRequest
        from src.core.ai.model_router import AITaskType

        response = await self.wrapper.generate(
            AIRequest(
                prompt=user_content,
                system_prompt=system_prompt,
                task_type=AITaskType.COMPLEX_EXTRACTION,
                low_budget_mode=False,
                use_cache=False,
            )
        )
        if response.model_used != REQUIRED_MODEL:
            raise RuntimeError("N12_MODEL_ROUTE_DRIFT")
        self.response_sha256 = hashlib.sha256(response.content.encode()).hexdigest()
        try:
            self.payload = AIService(wrapper=self.wrapper)._parse_json_response(response.content)
        except Exception as exc:
            self.parse_failure_type = type(exc).__name__
            raise
        return self.payload


def score_critique(
    result: Any, port: ObservedRealCritiquePort, source: str, *, evaluation: str
) -> dict[str, Any]:
    notes = result.critique_notes
    from src.analysis.domain.ai_extraction import _NEUTRAL_OK_NOTES

    raw = port.payload if isinstance(port.payload, dict) else {}
    declared = str(raw.get("status") or "").strip().upper()
    model_notes = raw.get("notes")
    neutral_ok = isinstance(model_notes, str) and (
        not model_notes.strip() or _NEUTRAL_OK_NOTES.fullmatch(model_notes.strip()) is not None
    )
    return {
        **oracle.score_n12(notes, source),
        "model_declared_status": declared,
        "model_neutral_ok_notes": neutral_ok,
        **oracle.score_n12_structured_provenance(port.payload, source),
        "evaluation": evaluation,
        "status": result.status,
        "human_approval_required": result.human_approval_required,
        "quality_state": "NOT_ASSESSED" if result.status == "UNASSESSED" else "ASSESSED",
        "response_sha256": port.response_sha256,
        "notes_sha256": hashlib.sha256(notes.encode()).hexdigest(),
        "parse_failure_type": port.parse_failure_type,
        "semantic_approval": False,
    }


def provider_trace() -> dict[str, Any]:
    """Only actual token usage and termination, never prompts or completions."""
    summary = oracle._governor_summary()
    path = os.environ.get("C2PRO_AI_GOVERNOR_LEDGER")
    if not path or not Path(path).exists():
        raise RuntimeError("GOVERNOR_LEDGER_REQUIRED")
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
    completed = [item for item in events if item.get("ev") == "done"]
    summary["call_breakdown"] = [
        {
            "model": item.get("model"),
            "output_tokens": item.get("out"),
            "input_tokens": item.get("in"),
            "stop_reason": item.get("stop_reason"),
            "estimated_cost_usd": item.get("usd"),
        }
        for item in completed
    ]
    summary["failed_calls"] = sum(item.get("ev") == "fail" for item in events)
    return summary


def verify_technical_gate(report: dict[str, Any]) -> dict[str, bool]:
    """Separate model detection, evidence and mandatory human legal review."""
    n4 = report["n4"]
    adversarial = report["n12_adversarial"]
    chained = report["n12_chained"]
    provider = report["provider"]
    coverage = report["input_coverage"]
    refs = {"EPC-04", "EPC-05", "EPC-07"}
    return {
        "provider_bounded": (
            provider["calls"] == MAX_CALLS
            and provider["completed_calls"] == MAX_CALLS
            and provider["failed_calls"] == 0
            and provider["estimated_cost_usd"] <= MAX_USD
            and provider["models"] == [REQUIRED_MODEL]
            and all(entry.get("stop_reason") == "end_turn" for entry in provider["call_breakdown"])
        ),
        "n4_source_prepared": (
            coverage["fixture_clauses"] == 9 and coverage["source_clauses_retained"] == 9
        ),
        "n4_nine_source_risks": (
            n4["true_positives"] == 9
            and n4["omissions"] == 0
            and n4["false_positives"] == 0
            and n4["invalid_citations"] == 0
        ),
        "n12_adversarial_grounded": (
            adversarial["omissions_detected"] == 2
            and adversarial["incorrect_interpretation_detected"] is True
            and adversarial["critique_citation_validity"] is True
            and adversarial["critique_invalid_quoted_citations"] == 0
            and adversarial["critique_quoted_citations"] >= 3
            and refs.issubset(set(adversarial["critique_citation_clause_refs"]))
            and adversarial["model_findings_payload_valid"] is True
            and adversarial["model_findings_submitted"] >= 3
            and adversarial["model_findings_unverified"] == 0
            and refs.issubset(set(adversarial["model_verified_clause_refs"]))
            and adversarial["status"] == "UNASSESSED"
            and adversarial["human_approval_required"] is True
        ),
        "n12_chained_no_invented_source": (
            chained["human_approval_required"] is True
            and chained["model_findings_payload_valid"] is True
            and chained["model_findings_unverified"] == 0
            and chained["model_findings_source_verified"] == chained["model_findings_submitted"]
            and chained["critique_invalid_quoted_citations"] == 0
            and chained["parse_failure_type"] is None
            and chained["response_sha256"] is not None
            and (
                (
                    chained["model_findings_submitted"] == 0
                    and chained["model_declared_status"] == "OK"
                    and chained["model_neutral_ok_notes"] is True
                )
                or (
                    chained["model_findings_submitted"] > 0
                    and chained["model_declared_status"] == "RETRY"
                )
            )
            and chained["semantic_approval"] is False
            and chained["status"] == "UNASSESSED"
        ),
    }


async def run() -> dict[str, Any]:
    if os.getenv("C2PRO_AI_MOCK") != "0":
        raise RuntimeError("REAL_AI_REQUIRED")
    if os.getenv("C2PRO_AI_GOVERNOR_MAX_CALLS") != str(MAX_CALLS):
        raise RuntimeError("GOVERNOR_CALL_CAP_NOT_3")
    if os.getenv("C2PRO_AI_GOVERNOR_MAX_USD") != "1.0":
        raise RuntimeError("GOVERNOR_BUDGET_NOT_1_USD")
    fixture = oracle.load_fixture()
    source = oracle._source_text(fixture)

    from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionTool
    from src.analysis.adapters.graph.nodes import _risk_contract_payload
    from src.analysis.application.critique_extraction_use_case import (
        CritiqueExtractionCommand,
        CritiqueExtractionUseCase,
    )
    from src.core.ai.anthropic_wrapper import AnthropicWrapper
    from src.core.ai.model_router import AITaskType, get_model_router

    standard = get_model_router().select_model_with_budget_mode(
        task_type=AITaskType.COMPLEX_EXTRACTION, low_budget_mode=False
    )
    if standard.name != REQUIRED_MODEL or standard.max_tokens != MAX_OUTPUT_TOKENS:
        raise RuntimeError("PRODUCTION_STANDARD_MODEL_ROUTE_DRIFT")
    # Mandatory same-process NER is exercised before any paid provider call.
    strict_anonymizer = _require_fail_closed_spanish_ner()
    wrapper = AnthropicWrapper(
        enable_cache=False, enable_retry=False, max_tokens_limit=MAX_OUTPUT_TOKENS
    )
    wrapper.anonymizer_service = cast(Any, strict_anonymizer)
    n4_tool = RiskExtractionTool(anthropic_wrapper=wrapper)
    prepared = prepare_graph_n4_input(n4_tool, source)
    coverage = input_coverage(source, prepared.document_text, fixture)
    if coverage["source_clauses_retained"] != 9:
        raise RuntimeError("N4_INPUT_NOT_EQUIVALENT_TO_EPC_SOURCE")

    n4_output = await n4_tool.execute(prepared, low_budget_mode=False)
    if not n4_output.success or n4_output.model_used != REQUIRED_MODEL:
        raise RuntimeError("N4_REAL_SONNET_EXECUTION_FAILED")
    risks = [
        _risk_contract_payload(n4_tool._risk_item_to_dict(item), source)
        for item in (n4_output.data or [])
    ]
    n4_scores = oracle.score_n4(fixture, risks)
    n4_scores["model"] = n4_output.model_used
    n4_scores["input_tokens"] = n4_output.input_tokens
    n4_scores["output_tokens"] = n4_output.output_tokens
    n4_scores["citation_fingerprints"] = n4_citation_fingerprints(risks, source)

    adversarial_port = ObservedRealCritiquePort(wrapper)
    adversarial_result = await CritiqueExtractionUseCase(ai=adversarial_port).execute(
        CritiqueExtractionCommand(
            extracted_risks=oracle._adversarial_risks(fixture),
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
            source_complete=None,
        )
    )
    adversarial = score_critique(
        adversarial_result, adversarial_port, source, evaluation="adversarial_fixture"
    )

    # Independent third call: N12 receives real N4 outputs, not adversarial entries.
    chained_port = ObservedRealCritiquePort(wrapper)
    chained_result = await CritiqueExtractionUseCase(ai=chained_port).execute(
        CritiqueExtractionCommand(
            extracted_risks=risks,
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
            source_complete=None,
        )
    )
    chained = score_critique(chained_result, chained_port, source, evaluation="actual_n4_output")
    chained["n4_risks_submitted"] = len(risks)

    report = {
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": oracle.FIXTURE_SHA256,
        "profile": "normal_core_sonnet_8192",
        "model": REQUIRED_MODEL,
        "ai_mock": False,
        "provider_call": "real",
        "source_seam": "RiskExtractionTool.extract_input_from_state",
        "input_coverage": coverage,
        "n4": n4_scores,
        "n12_adversarial": adversarial,
        "n12_chained": chained,
        "provider": provider_trace(),
        "limits": {"max_calls": MAX_CALLS, "max_usd": MAX_USD},
        "production_uat": False,
        "human_review_required_by_use_case": (
            adversarial_result.human_approval_required and chained_result.human_approval_required
        ),
        "hitl_pause_in_graph_tested": False,
    }
    report["gates"] = verify_technical_gate(report)
    return report


def main() -> int:
    report = asyncio.run(run())
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "fixture_id": report["fixture_id"],
                "profile": report["profile"],
                "gates": report["gates"],
                "calls": report["provider"]["completed_calls"],
                "estimated_usd": report["provider"]["estimated_cost_usd"],
            },
            sort_keys=True,
        )
    )
    # Successful execution/measurement is not successful functional QA.
    # Always let the separate, independent CI gate decide acceptance from
    # raw metrics plus the provider ledger, even when an oracle check fails.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
