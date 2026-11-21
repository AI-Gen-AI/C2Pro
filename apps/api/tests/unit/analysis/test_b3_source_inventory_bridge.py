"""B3 read-only pipeline smoke: actual optional candidate adapters, no AI or DB."""
from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

from src.analysis.application.b3_source_inventory_bridge import (
    B3Revision,
    B3SourceBridgeError,
    assemble_b3_source_inventory,
)
from src.documents.adapters.parsers.docling_optional_table_sidecar import (
    build_optional_table_sidecar,
)
from src.documents.adapters.parsers.mpxj_schedule_candidate_adapter import (
    ScheduleSourceScope,
    parse_verified_mpxj_candidates,
)


class FakeTask:
    def getName(self): return "Commissioning complete"
    def getUniqueID(self): return "T-001"
    def getStart(self): return "2027-06-01T00:00"
    def getFinish(self): return "2027-08-12T00:00"
    def getPredecessors(self): return []
    def getDuration(self): return "P72D"
    def getMilestone(self): return True
    def getWBS(self): return "2.6.1"


class FakeProject:
    def getTasks(self): return [FakeTask()]
    def getCalendars(self): return []
    def getResources(self): return []


TENANT = UUID(int=11)
PROJECT = UUID(int=12)


def rev(n: int, payload: bytes) -> B3Revision:
    return B3Revision(TENANT, PROJECT, UUID(int=n), UUID(int=n+100),
                      hashlib.sha256(payload).hexdigest())


CONTRACT = rev(31, b"synthetic-pdf-binary")
SCHEDULE = rev(32, b"synthetic-xer-file")
BUDGET = rev(33, b"synthetic-xlsx")


def input_bundle():
    pdf = build_optional_table_sidecar(
        physical_pdf_sha256=CONTRACT.blob_sha256,
        baseline_blocks=[
            {"page": 1, "text": "Contract price USD 1,000,000", "bbox": [0,0,50,30]},
            {"page": 2, "text": "Completion date set by Annex C", "bbox": [0,0,50,30]},
        ],
        total_pdf_pages=2,
        docling_candidate={
            "state": "CANDIDATE_UNVALIDATED", "trusted_promotions": 0,
            "source": {"sha256": CONTRACT.blob_sha256},
            "coverage": {"pages_reported": 2, "docling_layout_sequence_available": False},
            "tables": [{
                "source_locator": "docling:table:0",
                "locations": [{"page": 1, "bbox": [3,4,30,40]}],
                "rows": 2, "columns": 2,
                "cells": [{"text":"Amount","row_start":0,"col_start":0}],
            }],
        },
    )
    native = parse_verified_mpxj_candidates(
        source_bytes=b"synthetic-xer-file",
        expected_sha256=SCHEDULE.blob_sha256,
        file_extension=".xer",
        scope=ScheduleSourceScope(TENANT,PROJECT,SCHEDULE.document_id,SCHEDULE.revision_id),
        reader=lambda path: FakeProject(),
    )
    rows = [SimpleNamespace(
        tenant_id=TENANT,project_id=PROJECT,document_id=BUDGET.document_id,
        revision_id=BUDGET.revision_id,source_locator="BOQ!row:2",
        amount=400000,currency="USD",wbs_node_id=None)]
    return pdf,native,rows


class B3SourceInventoryTests(unittest.TestCase):
    def test_three_real_adapters_shapes_as_projectgraph_source_refs(self):
        pdf,native,rows=input_bundle()
        data=assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
             schedule_revision=SCHEDULE,native_schedule=native,budget_revision=BUDGET,budget_rows=rows)
        self.assertEqual([x["family"] for x in data["structured_source_refs"]],
                         ["contract","schedule","budget"])
        self.assertEqual([x.get("observed_source_rows") for x in data["structured_source_refs"]],
                         [None,1,1])
        self.assertEqual(data["advisory_docling_tables"],1)
        self.assertEqual(data["unresolved_inputs"],[])
        self.assertEqual(data["trusted_promotions"],0)
        self.assertFalse(data["effects_allowed"])
        self.assertIsNone(data["coherence_score"])
        self.assertNotIn("baseline_text",str(data))
        self.assertNotIn("Contract price USD",str(data))
        self.assertEqual(data["projectgraph_scoring"],"BLOCKED_NO_TRUSTED_PROJECTION")
        self.assertEqual(data["n12_status"],"NOT_RUN_BY_BRIDGE")

    def test_no_schedule_or_budget_is_not_a_green_pass(self):
        pdf,_,_=input_bundle()
        d=assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf)
        self.assertEqual(d["source_count"],1)
        self.assertIn("NATIVE_SCHEDULE_CANDIDATES",d["unresolved_inputs"])
        self.assertIn("BUDGET_SOURCE",d["unresolved_inputs"])
        self.assertIsNone(d["coherence_score"])

    def test_wrong_pdf_sha_rejected(self):
        pdf,_,_=input_bundle()
        pdf["physical_pdf_sha256"]="0"*64
        with self.assertRaisesRegex(B3SourceBridgeError,"contract source SHA"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf)

    def test_wrong_schedule_revision_or_project_rejected(self):
        pdf,native,rows=input_bundle()
        with self.assertRaisesRegex(B3SourceBridgeError,"scope mismatch"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=replace(SCHEDULE,revision_id=UUID(int=999)),native_schedule=native)
        with self.assertRaisesRegex(B3SourceBridgeError,"mixed tenant"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=replace(SCHEDULE,tenant_id=UUID(int=999)),native_schedule=native)

    def test_unauthorized_wbs_or_automatic_promotion_rejected(self):
        pdf,native,_=input_bundle()
        native["activities"][0]["wbs_node_id"]=UUID(int=21)
        with self.assertRaisesRegex(B3SourceBridgeError,"unapproved WBS"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=SCHEDULE,native_schedule=native)
        native["activities"][0]["wbs_node_id"]=None
        native["trusted_promotions"]=1
        with self.assertRaisesRegex(B3SourceBridgeError,"authority"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=SCHEDULE,native_schedule=native)

    def test_cross_tenant_budget_row_rejected(self):
        pdf,native,rows=input_bundle()
        rows[0].tenant_id=UUID(int=100)
        with self.assertRaisesRegex(B3SourceBridgeError,"budget row lineage"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=SCHEDULE,native_schedule=native,budget_revision=BUDGET,budget_rows=rows)

    def test_budget_row_duplicate_rejected(self):
        pdf,native,rows=input_bundle()
        with self.assertRaisesRegex(B3SourceBridgeError,"duplicate budget"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=SCHEDULE,native_schedule=native,budget_revision=BUDGET,budget_rows=rows*2)

    def test_unexpected_schedule_source_hash_rejected(self):
        pdf,native,_=input_bundle()
        native["source"]["sha256"]="f"*64
        with self.assertRaisesRegex(B3SourceBridgeError,"schedule format or SHA"):
            assemble_b3_source_inventory(contract_revision=CONTRACT,contract_sidecar=pdf,
                schedule_revision=SCHEDULE,native_schedule=native)

    def test_invalid_native_extension_rejected_at_parser(self):
        with self.assertRaisesRegex(Exception,"unsupported native schedule format"):
            parse_verified_mpxj_candidates(source_bytes=b"a",expected_sha256=hashlib.sha256(b"a").hexdigest(),
               file_extension=".pdf",
               scope=ScheduleSourceScope(TENANT,PROJECT,SCHEDULE.document_id,SCHEDULE.revision_id),
               reader=lambda path: FakeProject())

    def test_docling_partial_order_safe_sidecar_does_not_delete_text(self):
        pdf,_,_=input_bundle()
        self.assertFalse(pdf["docling_raw_order_complete"])
        self.assertEqual(pdf["docling_table_status"],"ADVISORY_ONLY")
        self.assertEqual(pdf["baseline_text"],"Contract price USD 1,000,000\n\nCompletion date set by Annex C")
        self.assertFalse(pdf["docling_extra_text_accepted_into_n2"])


if __name__ == "__main__":
    unittest.main()
