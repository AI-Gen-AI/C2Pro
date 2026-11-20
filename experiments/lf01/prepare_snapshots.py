#!/usr/bin/env python3
"""Prepare LF-01 strictly sanitized snapshots from EXISTING local artifacts.

Never invokes N4, model inference, production APIs, or network. Raw contract text,
source citations, run IDs, tenant IDs, receipts, and hashes remain on the VPS.
Files written here are **aggregates**, not the original evidence.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def check_int(data: dict, key: str, minimum=0) -> int:
    value = data[key]
    if type(value) is not int or value < minimum:
        raise ValueError(f"Expected nonnegative integer in field {key}")
    return value

def build_real(metrics: dict, packet: dict) -> dict:
    count = check_int(metrics, "candidate_count")
    total = check_int(metrics, "total_windows", minimum=1)
    checked = check_int(metrics, "verified_literal_candidates")
    unchecked = check_int(metrics, "unverified_literal_candidates")
    windows = metrics["candidates_per_window"]
    if checked + unchecked != count:
        raise ValueError("Inconsistent verified/unverified candidate totals")
    if len(windows) != total or set(windows) != {str(i) for i in range(total)}:
        raise ValueError("Noncontiguous historical window counts")
    if sum(windows[str(i)] for i in range(total)) != count:
        raise ValueError("Per-window candidate counts do not total all findings")
    if packet["candidate_count"] != count:
        raise ValueError("Packet and offline metrics candidate counts disagree")
    if packet["n12_status"] != metrics["n12_status"]:
        raise ValueError("N12 status mismatch")
    safe_blockers = {
        "N4_PARTIAL_SOURCE_COVERAGE",
        "N12_REAL_PROVIDER_NOT_EXECUTED",
        "NO_IMMUTABLE_CANDIDATE_ARTIFACT_OR_AUTHENTICATED_REVIEW",
        "NO_HUMAN_DECISIONS",
        "USER_94_PAGE_PDF_NOT_ATTESTED",
    }
    blocker_codes = [b if b in safe_blockers else "UNKNOWN_PRIVATE_BLOCKER"
                     for b in packet["blockers"]]
    return {
        "blocker_codes":blocker_codes,
        "data_class":"REAL_OFFLINE_AGGREGATED",
        "source":"SEC_N4_T05_offline_recovery_20261120",
        "evidence_kind":"prior_execution_reconciliation_not_new_inference",
        "original_artifacts_remain_on_private_VPS":True,
        "privacy":"aggregate_only_no_contract_text_no_identifiers_no_credentials",
        "document":{
            "family":"SEC_public_EPC_exhibit",
            "exhibit_pages":check_int(metrics,"source_pdf_pages_reported"),
            "user_pdf_94_pages_attested":False},
        "N1_N2":{
            "processing_windows_historical":total,
            "original_windows_state_reconstructible":bool(metrics["historical_window_states_reconstructible"]),
            "literal_verified_in_N2":checked,
            "literal_unverified_in_N2":unchecked,
            "pdf_original_citation_attestation":"NOT_GENERALIZED"},
        "N3":{"status":"NOT_VERIFIED_IN_THIS_EVIDENCE"},
        "N4":{
            "status":packet["n4_status"],"candidate_count":count,
            "window_counts":[windows[str(i)] for i in range(total)],
            "distinct_receipts":check_int(metrics,"distinct_provider_receipt_ids")},
        "N12":{"status":packet["n12_status"],"reviewed_candidates":0},
        "HITL":{
            "status":"NOT_RECORDED",
            "approved":check_int(metrics,"approved_human_decisions"),
            "pending_review_candidates":check_int(metrics,"pending_human_decisions")},
        "ProjectGraph":{"status":metrics["projectgraph_status"],"promoted_candidates":0},
        "N8_Coherence":{"status":"NO_VERIFIED_SCORE_CHANGE",
                         "score_change":packet.get("coherence_score_change")},
        "UI":{"status":"NOT_VERIFIED_BY_THIS_OFFLINE_PACKET"},
        "Budget_Schedule_Tech_Annexes":{"status":"NO_CROSS_DOCUMENT_MAPPING_ATTESTED"},
        "blocker_count":len(packet["blockers"]),
        "interpretation":"N4 partial proposals exist; N12 and downstream publishing do not have verified completion; N2 literal verification is not PDF citation certification",
    }

def build_synthetic() -> dict:
    return {
        "data_class":"SYNTHETIC_DESIGNED",
        "source":"LF01_fictional_fixture_v1",
        "evidence_kind":"not_a_real_execution",
        "document":{"family":"artificial_EPC_contract_plus_budget_schedule_spec_annex","pages":12},
        "N1_N2":{"processing_windows_historical":6,"processed":3,
                 "blocked":[3],"unprocessed":[4,5]},
        "N3":{"status":"DESIGNED_ONLY"},
        "N4":{"status":"PARTIAL","candidate_count":4,"window_counts":[1,2,1,0,0,0],
              "unresolved_refs":2},
        "N12":{"status":"NOT_STARTED","reviewed_candidates":0},
        "HITL":{"status":"NOT_STARTED","approved":0},
        "ProjectGraph":{"status":"NOT_PROMOTED","promoted_candidates":0},
        "N8_Coherence":{"status":"UNCHANGED"},
        "UI":{"status":"NO_PUBLISHED_RESULTS"},
        "Budget_Schedule_Tech_Annexes":{"status":"LINKS_DESIGNED_NOT_EVALUATED"},
        "blocker_reason":"synthetic provider timeout at window 4",
        "blocker_codes":["SYNTHETIC_PROVIDER_TIMEOUT"],
        "interpretation":"intentional illustration of loss of visibility between persisted N4 proposals and downstream interfaces",
    }

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--real-metrics",type=Path,required=True)
    p.add_argument("--real-packet",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    a.output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    metrics=json.loads(a.real_metrics.read_text())
    packet=json.loads(a.real_packet.read_text())
    for filename,data in [
        ("real_offline_aggregate.json",build_real(metrics,packet)),
        ("synthetic_partial_scenario.json",build_synthetic())
    ]:
        path=a.output_dir/filename
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
        path.chmod(0o600)
        print(filename,"prepared",data["data_class"])
    print("No raw evidence, prompts, private references or secrets copied")

if __name__=="__main__":
    main()
