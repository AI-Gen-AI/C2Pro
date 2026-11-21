"""B4 isolated source-comparison regression (synthetic; no real EPC UAT).

The mocked artifact and quote resolver are NOT evidence of an actual N4/N12
success. This checks that the EXISTING comparators can emit two provisional
findings with both immutable pointers and without affecting authority or Score.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from types import SimpleNamespace
from uuid import UUID

from src.analysis.application.b3_source_inventory_bridge import (
    B3SourceBridgeError,
    assemble_b3_source_inventory,
)
from src.analysis.application.b4_provisional_source_preview import (
    preview_b4_provisional_comparison,
)
from src.analysis.domain.contracts import DocumentArtifact
from tests.unit.analysis.test_b3_source_inventory_bridge import (
    BUDGET,
    CONTRACT,
    PROJECT,
    SCHEDULE,
    TENANT,
    input_bundle,
)


def canonical_unit(family, revision, payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), default=str, allow_nan=False)
    return {
        "family": family, "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(revision.document_id),
        "revision_id": str(revision.revision_id),
        "blob_hash": revision.blob_sha256,
        "source_locator": payload["source_locator"],
        "unit_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "payload": payload,
    }


def n2_quote(text, locator):
    return {
        "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(CONTRACT.document_id),
        "revision_id": str(CONTRACT.revision_id),
        "doc_type": "contract",
        "source_quote": text,
        "source_quote_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_locator": locator,
    }


def fixture():
    pdf, native, _ = input_bundle()
    budget_total = SimpleNamespace(
        tenant_id=TENANT, project_id=PROJECT,
        document_id=BUDGET.document_id, revision_id=BUDGET.revision_id,
        source_locator="BOQ!row:2", amount=1300000, currency="USD",
        description="EXPLICIT TOTAL",
    )
    packet = assemble_b3_source_inventory(
        contract_revision=CONTRACT, contract_sidecar=pdf,
        schedule_revision=SCHEDULE, native_schedule=native,
        budget_revision=BUDGET, budget_rows=[budget_total],
    )
    assert native["activities"][0]["end_source_local"] == "2027-08-12T00:00"
    # Research fixture: a verified use case would need to attest this
    # date-only normalization from the original selected revision.
    units = [
        canonical_unit("schedule", SCHEDULE, {
            "kind": "activity",
            "source_locator": native["activities"][0]["source_locator"],
            "task": native["activities"][0]["task"],
            "end_date": "2027-08-12",
        }),
        canonical_unit("budget", BUDGET, {
            "kind": "declared_total", "source_locator": budget_total.source_locator,
            "total": "1300000", "currency": "USD",
            "source_total_kind": "EXPLICIT_DECLARED_TOTAL",
            "source_total_review": "REQUIRES_REVIEW",
        }),
    ]
    quotes = [
        n2_quote("Contractual completion date: 2027-05-12", "chunk:0:12"),
        n2_quote("Contract price USD 1,000,000", "chunk:1:20"),
    ]
    # Synthetic object stands in for what a REAL trusted repository must load.
    artifacts = [DocumentArtifact(
        document_id=str(CONTRACT.document_id),
        document_revision_id=str(CONTRACT.revision_id),
        doc_type="contract",
    )]
    return packet, units, quotes, artifacts


def check(packet, units, quotes, artifacts):
    return preview_b4_provisional_comparison(
        packet=packet, tenant_id=TENANT, project_id=PROJECT,
        trusted_document_artifacts=artifacts,
        source_units=units, source_quotes=quotes,
    )


class B4SourceComparisonPreviewTests(unittest.TestCase):
    def test_two_provisional_discrepancies_with_both_sources_and_no_score(self):
        packet, units, quotes, artifacts = fixture()
        result = check(packet, units, quotes, artifacts)
        self.assertEqual(result["status"], "PROVISIONAL_SOURCE_OBSERVATIONS")
        self.assertEqual(result["source_unit_checksums_valid"], 2)
        self.assertEqual(result["original_source_attestation"], "NOT_PERFORMED_BY_B4_PREVIEW")
        findings = {finding["rule_id"]: finding for finding in result["findings"]}
        self.assertEqual(set(findings), {"DET-CRS-SCHDEAD", "DET-CRS-NEGMARGIN"})
        self.assertEqual(findings["DET-CRS-SCHDEAD"]["compared_values"]["overrun_days"], 92)
        self.assertEqual(findings["DET-CRS-NEGMARGIN"]["compared_values"]["difference"], 300000.0)
        for finding in findings.values():
            self.assertEqual(finding["state"], "PROVISIONAL")
            self.assertEqual(len(finding["sources"]), 2)
            self.assertTrue(all(s.get("revision_id") for s in finding["sources"]))
            self.assertFalse(finding["scored"])
            self.assertTrue(finding["requires_human_review"])
        self.assertIsNone(result["coherence_score"])
        self.assertEqual(result["trusted_promotions"], 0)
        self.assertEqual(result["snapshots_written"], 0)
        self.assertEqual(result["alerts_written"], 0)
        self.assertEqual(result["n12_assessment"], "NOT_RUN_BY_B4")

    def test_without_trusted_contract_artifact_no_comparison(self):
        packet, units, quotes, _ = fixture()
        result = check(packet, units, quotes, [])
        self.assertEqual(result["status"], "NOT_ASSESSED")
        self.assertEqual(result["findings"], [])
        self.assertIn("TRUSTED_CONTRACT_ARTIFACT_UNAVAILABLE", result["not_assessed_reasons"])

    def test_budget_without_explicit_source_total_is_rejected(self):
        packet, units, quotes, artifacts = fixture()
        units[1]["payload"]["source_total_kind"] = "SUM_OF_LINES"
        with self.assertRaisesRegex(B3SourceBridgeError, "checksum"):
            check(packet, units, quotes, artifacts)
        units[1] = canonical_unit("budget", BUDGET, {
            **units[1]["payload"], "source_total_kind": "SUM_OF_LINES",
        })
        with self.assertRaisesRegex(B3SourceBridgeError, "explicit source-row"):
            check(packet, units, quotes, artifacts)

    def test_wrong_project_or_revised_blob_never_enters_comparator(self):
        packet, units, quotes, artifacts = fixture()
        units[0]["project_id"] = str(UUID(int=909))
        with self.assertRaisesRegex(B3SourceBridgeError, "revision, project or blob"):
            check(packet, units, quotes, artifacts)
        packet, units, quotes, artifacts = fixture()
        units[0]["blob_hash"] = "f" * 64
        with self.assertRaisesRegex(B3SourceBridgeError, "revision, project or blob"):
            check(packet, units, quotes, artifacts)

    def test_quote_hash_and_revision_are_required(self):
        packet, units, quotes, artifacts = fixture()
        quotes[0]["source_quote"] += " unauthorised append"
        with self.assertRaisesRegex(B3SourceBridgeError, "content hash"):
            check(packet, units, quotes, artifacts)
        packet, units, quotes, artifacts = fixture()
        quotes[0]["revision_id"] = str(UUID(int=999))
        with self.assertRaisesRegex(B3SourceBridgeError, "selected contract revision"):
            check(packet, units, quotes, artifacts)

    def test_foreign_contract_artifact_is_refused(self):
        packet, units, quotes, artifacts = fixture()
        artifacts = [artifacts[0].model_copy(update={"document_revision_id": "wrong-revision"})]
        with self.assertRaisesRegex(B3SourceBridgeError, "selected revision"):
            check(packet, units, quotes, artifacts)

    def test_no_comparable_quote_fails_to_not_assessed_without_fake_pass(self):
        packet, units, _, artifacts = fixture()
        result = check(packet, units, [], artifacts)
        self.assertEqual(result["status"], "NOT_ASSESSED")
        self.assertEqual(result["findings"], [])
        self.assertIn("CONTRACT_COMPLETION_OR_SCHEDULE_NOT_UNAMBIGUOUS", result["not_assessed_reasons"])
        self.assertIn("CONTRACT_PRICE_OR_BUDGET_TOTAL_NOT_UNAMBIGUOUS", result["not_assessed_reasons"])
        self.assertIsNone(result["coherence_score"])


if __name__ == "__main__":
    unittest.main()
