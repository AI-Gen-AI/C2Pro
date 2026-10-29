"""Unit guard for S2 independent PG verifier's browser evidence envelope."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.verify_s2_triplet_pg import FAMILIES, NEGATIVES, local_test_dsn, source_trace

FIXTURES = Path(__file__).resolve().parents[4] / "web" / "src" / "tests" / "e2e" / "test-data" / "triplet"
MANIFEST = json.loads((FIXTURES / "triplet.manifest.json").read_text())


def make_browser_report():
    project = str(uuid4())
    sources = [
        {
            "filename": name, "type": kind,
            "documentId": str(uuid4()), "revisionId": str(uuid4()),
            "sha256": MANIFEST["sha256"][name],
        }
        for name, kind in FAMILIES.items()
    ]
    negatives = {
        "projectId": project, "unchangedDocuments": 4,
        "results": [
            {"filename": name, "expected": status, "actual": status}
            for name, status in NEGATIVES.items()
        ],
    }
    annotations = [
        {"type": "s2-source-ledger", "description": json.dumps({"projectId": project, "sources": sources})},
        {"type": "s2-negative-uploads", "description": json.dumps(negatives)},
    ]
    test = {
        "projectName": "triplet-journey", "status": "expected",
        "results": [{"status": "passed", "annotations": annotations}],
    }
    return {
        "suites": [{
            "title": "triplet-user-journey.spec.ts", "suites": [],
            "specs": [{"file": "triplet-user-journey.spec.ts", "tests": [test]}],
        }]
    }


def test_accepts_four_exact_fixtures_and_genesis_ids():
    report = make_browser_report()
    project, sources = source_trace(report, MANIFEST, FIXTURES)
    assert project
    assert {row[0] for row in sources} == set(FAMILIES)
    assert {row[1] for row in sources} == set(FAMILIES.values())
    assert len({row[2] for row in sources}) == 4
    assert len({row[3] for row in sources}) == 4


@pytest.mark.parametrize("fault", ["wrong_type", "duplicate_revision", "negative_accepted", "wrong_hash", "not_passed"])
def test_fails_closed_on_false_browser_claims(fault):
    report = make_browser_report()
    test = report["suites"][0]["specs"][0]["tests"][0]
    annotations = test["results"][0]["annotations"]
    ledger = json.loads(annotations[0]["description"])
    negative = json.loads(annotations[1]["description"])
    if fault == "wrong_type":
        ledger["sources"][3]["type"] = "specification"
    elif fault == "duplicate_revision":
        ledger["sources"][3]["revisionId"] = ledger["sources"][0]["revisionId"]
    elif fault == "wrong_hash":
        ledger["sources"][3]["sha256"] = "0" * 64
    elif fault == "negative_accepted":
        negative["results"][0]["actual"] = 202
    else:
        test["results"][0]["status"] = "failed"
    annotations[0]["description"] = json.dumps(ledger)
    annotations[1]["description"] = json.dumps(negative)
    with pytest.raises(ValueError, match="S2_INDEPENDENT_PG_FAIL"):
        source_trace(report, MANIFEST, FIXTURES)


def test_db_target_guards_production():
    with pytest.raises(ValueError, match="isolated localhost"):
        local_test_dsn("postgresql://prod.example.com:5432/c2pro_prod")
    with pytest.raises(ValueError, match="isolated localhost"):
        local_test_dsn("postgresql://localhost:5433/postgres")
    assert local_test_dsn("postgresql://postgres:postgres@localhost:5433/c2pro_test").startswith(
        "postgresql+asyncpg://"
    )
