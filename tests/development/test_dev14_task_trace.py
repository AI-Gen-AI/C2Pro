from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "trace", ROOT / "scripts/development/validate_task_trace.py"
)
assert SPEC and SPEC.loader
trace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trace)

def registry():
    return trace.load_registry(ROOT)

def claim(task, parent, sdd="docs/product/pq-hitl-2026-01-delivery-spec-v1.md"):
    return {"task_id":task,"parent_issue":parent,"sdd_path":sdd,
            "acceptance_ids":[],"execution_work_id":None}

def metadata(*claims, effect="SPEC_ONLY"):
    return {"schema":"c2pro-pr-task-trace-v1","primary_task":claims[0]["task_id"],
            "task_claims":list(claims),"effect_claim":effect}

def test_canonical_parent_and_real_subtask_are_grounded():
    r=registry()
    assert r["PQ-HITL-09"]["issue"] == 945
    assert r["PQ-HITL-09.1"]["issue"] == 945
    assert r["PQ-HITL-04.6"]["issue"] == 940

def test_unknown_task_rejected():
    with pytest.raises(trace.TraceError,match="unknown"):
        trace.validate_claims(metadata(claim("PQ-HITL-99.9",945)),registry(),ROOT)

def test_parent_issue_mismatch_rejected():
    with pytest.raises(trace.TraceError,match="parent_issue"):
        trace.validate_claims(metadata(claim("PQ-HITL-09.1",940)),registry(),ROOT)

def test_defect_is_not_primary_task():
    with pytest.raises(trace.TraceError,match="unknown"):
        trace.validate_claims(metadata(claim("DEF-PQ-006",940)),registry(),ROOT)

def test_multiple_tasks_keep_separate_parents():
    m=metadata(claim("PQ-HITL-04.6",940),claim("PQ-HITL-09.1",945))
    trace.validate_claims(m,registry(),ROOT)
    m["task_claims"][1]["parent_issue"]=940
    with pytest.raises(trace.TraceError,match="parent_issue"):
        trace.validate_claims(m,registry(),ROOT)

def test_duplicate_task_claim_rejected():
    c=claim("PQ-HITL-09.1",945)
    with pytest.raises(trace.TraceError,match="duplicate"):
        trace.validate_claims(metadata(c,c),registry(),ROOT)

def test_spec_only_accepts_approved_docs_but_not_code():
    trace.validate_effect("SPEC_ONLY",["docs/architecture/development/test-sdd.md"])
    with pytest.raises(trace.TraceError,match="SPEC_ONLY"):
        trace.validate_effect("SPEC_ONLY",["apps/api/src/backend.py"])
    with pytest.raises(trace.TraceError,match="SPEC_ONLY"):
        trace.validate_effect("SPEC_ONLY",["validation/product/c2pro-master-product-control-v1.yaml"])

def test_no_work_for_implementation_is_blocked():
    with pytest.raises(trace.TraceError,match="WORK"):
        c=claim("PQ-HITL-09.1",945)
        c["acceptance_ids"]=["PQ-HITL-09.1"]
        trace.validate_claims(metadata(c,effect="IMPLEMENTATION_ONLY"),registry(),ROOT)

def test_yaml_duplicate_keys_and_blocks_rejected():
    body="\x60\x60\x60yaml\nc2pro_trace:\n  schema: x\n  schema: y\n\x60\x60\x60"
    with pytest.raises(trace.TraceError,match="duplicate"):
        trace.parse_trace(body)
    body="\x60\x60\x60yaml\nc2pro_trace: {}\n\x60\x60\x60\n\x60\x60\x60yaml\nc2pro_trace: {}\n\x60\x60\x60"
    with pytest.raises(trace.TraceError,match="multiple"):
        trace.parse_trace(body)

def test_missing_trace_is_auditable_not_false_pass():
    assert trace.audit_pr("",[],ROOT)["status"]=="MISSING_TRACE"

def test_metadata_never_promotes_product():
    with pytest.raises(trace.TraceError,match="effect_claim"):
        trace.validate_claims(metadata(claim("PQ-HITL-09.1",945),effect="PROD_VALIDATED"),registry(),ROOT)

def test_dev_work_uses_dev_namespace_not_forged_product():
    r=registry()
    assert r["C2PRO-DEV-14"]["issue"] == 991
    trace.validate_claims(metadata(claim("C2PRO-DEV-14",991,"docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")),r,ROOT)



def test_atomic_task_registry_contains_expected_count():
    r=registry()
    assert len([i for i in r if i.startswith("PQ-HITL-") and "." in i]) == 28


def test_product_work_envelope_schema_collision_free_and_closed():
    import jsonschema
    import yaml

    schema=yaml.safe_load((ROOT/".c2pro/schemas/product-work-envelope.schema.yaml").read_text())
    valid={
        "schema":"c2pro-product-work-envelope-v1", "schema_version":1,
        "work_id":"PQ-HITL-09.1","task_id":"PQ-HITL-09.1","parent_issue":945,
        "status":"prepared","base_sha":"0"*40,"branch":"feat/pq-hitl-09-1",
        "sdd_path":"docs/product/pq-hitl-2026-01-delivery-spec-v1.md",
        "acceptance_ids":["PQ-HITL-09.1"],"scope":["synthetic fixture"],
        "forbidden_paths":["secrets/**"],"assigned_to":None,"workspace_receipt":None,
    }
    jsonschema.Draft202012Validator(schema).validate(valid)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate({**valid,"work_id":"C2PRO-DEV-14"})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate({**valid,"allow_main_push":True})


def test_pre_pr_base_registry_lookup_refuses_invalid_hash_and_unknown_commit():
    with pytest.raises(trace.TraceError, match="base SHA"):
        trace.load_registry(ROOT,"malformed")
    with pytest.raises(trace.TraceError, match="source absent"):
        trace.load_registry(ROOT,"f"*40)


def test_immutable_checkout_registry_has_same_parent_and_atomic_tasks():
    # Works on a shallow GitHub checkout as well as a local full worktree.
    import subprocess
    base=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    anchored=trace.load_registry(ROOT,base)
    assert anchored["PQ-HITL-09.1"]["issue"] == 945
    assert anchored["PQ-HITL-04.6"]["issue"] == 940


def test_bad_trace_yaml_and_missing_acceptance_rejected():
    c=claim("PQ-HITL-09.1",945)
    c["acceptance_ids"]=["fixture-not-in-sdd"]
    with pytest.raises(trace.TraceError,match="acceptance_ids"):
        trace.validate_claims(metadata(c,effect="IMPLEMENTATION_ONLY"),registry(),ROOT)
    m=metadata(claim("PQ-HITL-09.1",945))
    m["unknown"]="self-authorized"
    with pytest.raises(trace.TraceError,match="schema keys"):
        trace.validate_claims(m,registry(),ROOT)


def test_audit_mode_reports_missing_and_invalid_without_authority():
    assert trace.audit_pr("No task metadata",[],ROOT)["status"]=="MISSING_TRACE"
    bad=chr(96)*3+"yaml\\nc2pro_trace:\\n  schema: fake\\n"+chr(96)*3
    assert trace.audit_pr(bad,[],ROOT)["status"] in {"MISSING_TRACE","REJECT"}


def test_owner_supervised_dev14_mapping_needs_no_agent_work_assignment():
    c=claim("C2PRO-DEV-14",991,
            "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")
    c["acceptance_ids"]=["TRACE-01","TRACE-17","TRACE-21"]
    meta=metadata(c,effect="IMPLEMENTATION_ONLY")
    meta["execution_mode"]="OWNER_SUPERVISED"
    trace.validate_claims(meta,registry(),ROOT)
    fence=chr(96)*3
    import yaml
    body=fence+"yaml\n"+yaml.safe_dump({"c2pro_trace":meta},sort_keys=False)+fence
    outcome=trace.audit_pr(body,["scripts/development/validate_task_trace.py"],ROOT)
    assert outcome["status"]=="TASK_MAPPED_PENDING_HUMAN_REVIEW"
    assert "CI does not grant" in outcome["reason"]


def test_owner_supervised_dev14_out_of_scope_rejected_even_in_audit():
    c=claim("C2PRO-DEV-14",991,
            "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")
    c["acceptance_ids"]=["TRACE-01"]
    meta=metadata(c,effect="IMPLEMENTATION_ONLY")
    meta["execution_mode"]="OWNER_SUPERVISED"
    import yaml
    fence=chr(96)*3
    body=fence+"yaml\n"+yaml.safe_dump({"c2pro_trace":meta},sort_keys=False)+fence
    result=trace.audit_pr(body,["apps/api/src/unrelated.py"],ROOT)
    assert result["status"]=="REJECT"
    assert "scope" in result["reason"]


def test_autonomous_work_mode_still_requires_real_work():
    c=claim("PQ-HITL-09.1",945)
    c["acceptance_ids"]=["PQ-HITL-09.1"]
    meta=metadata(c,effect="IMPLEMENTATION_ONLY")
    meta["execution_mode"]="AGENT_WORK"
    with pytest.raises(trace.TraceError,match="WORK"):
        trace.validate_claims(meta,registry(),ROOT)


def test_owner_supervised_invalid_acceptance_still_fails():
    c=claim("C2PRO-DEV-14",991,
            "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")
    c["acceptance_ids"]=["FAKE-ACCEPTANCE"]
    meta=metadata(c,effect="IMPLEMENTATION_ONLY")
    meta["execution_mode"]="OWNER_SUPERVISED"
    with pytest.raises(trace.TraceError,match="acceptance"):
        trace.validate_claims(meta,registry(),ROOT)



def test_owner_supervised_dev14_guarded_ci_manifest_is_scoped_exactly():
    c=claim("C2PRO-DEV-14",991,
            "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")
    c["acceptance_ids"]=["TRACE-17"]
    meta=metadata(c,effect="IMPLEMENTATION_ONLY")
    meta["execution_mode"]="OWNER_SUPERVISED"
    import yaml
    fence=chr(96)*3
    body=fence+"yaml\n"+yaml.safe_dump({"c2pro_trace":meta},sort_keys=False)+fence
    result=trace.audit_pr(body,["scripts/development/validate_task_trace.py",
            ".github/ci-pip-install-baseline.json"],ROOT)
    assert result["status"]=="TASK_MAPPED_PENDING_HUMAN_REVIEW"
    result=trace.audit_pr(body,[".github/ci-pip-install-baseline.json.unexpected"],ROOT)
    assert result["status"]=="REJECT"



def test_task_cannot_substitute_a_different_existing_sdd():
    c=claim("PQ-HITL-09.1",945,
            "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md")
    with pytest.raises(trace.TraceError,match="sdd_path"):
        trace.validate_claims(metadata(c),registry(),ROOT)


def test_agent_work_enforces_exact_base_branch_and_scoped_changed_paths(monkeypatch):
    import subprocess
    import yaml

    base=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    work={
        "schema":"c2pro-product-work-envelope-v1",
        "work_id":"PQ-HITL-09.1",
        "task_id":"PQ-HITL-09.1",
        "parent_issue":945,
        "base_sha":base,
        "branch":"feat/pq-09",
        "status":"assigned",
        "assigned_to":"codex",
        "workspace_receipt":"verified-receipt-from-base",
        "acceptance_ids":["PQ-HITL-09.1"],
        "scope":["tests/goldens/**"],
        "forbidden_paths":["tests/goldens/internal/**"]
    }
    original=trace.read_approved_source

    def fake_source(root,rel,sha):
        if rel==".c2pro/product-work/PQ-HITL-09.1.yaml":
            return yaml.safe_dump(work)
        return original(root,rel,sha)
    monkeypatch.setattr(trace,"read_approved_source",fake_source)
    c=claim("PQ-HITL-09.1",945)
    c["acceptance_ids"]=["PQ-HITL-09.1"]
    c["execution_work_id"]="PQ-HITL-09.1"
    c["work_envelope_path"]=".c2pro/product-work/PQ-HITL-09.1.yaml"
    c["workspace_evidence_ref"]="verified-receipt-from-base"
    m=metadata(c,effect="IMPLEMENTATION_ONLY")

    trace.validate_claims(m,registry(),ROOT,base,["tests/goldens/golden.py"],"feat/pq-09")
    with pytest.raises(trace.TraceError,match="forbidden"):
        trace.validate_claims(m,registry(),ROOT,base,["tests/goldens/internal/unapproved.py"],"feat/pq-09")
    with pytest.raises(trace.TraceError,match="outside assigned scope"):
        trace.validate_claims(m,registry(),ROOT,base,["apps/api/unrelated.py"],"feat/pq-09")
    with pytest.raises(trace.TraceError,match="branch"):
        trace.validate_claims(m,registry(),ROOT,base,["tests/goldens/golden.py"],"feat/wrong")
    work["base_sha"]="e"*40
    with pytest.raises(trace.TraceError,match="base_sha"):
        trace.validate_claims(m,registry(),ROOT,base,["tests/goldens/golden.py"],"feat/pq-09")


def test_spec_only_rejects_new_unregistered_document_against_immutable_base():
    import subprocess
    import yaml
    base=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    meta=metadata(claim("PQ-HITL-09.1",945))
    fence=chr(96)*3
    body=fence+"yaml\n"+yaml.safe_dump({"c2pro_trace":meta},sort_keys=False)+fence
    result=trace.audit_pr(body,["docs/architecture/development/unapproved-new-sdd.md"],ROOT,base)
    assert result["status"]=="REJECT"
    assert "pre-PR exact-path" in result["reason"]
    result=trace.audit_pr(body,["docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md"],ROOT,base)
    assert result["status"]=="PASS_SPEC"
