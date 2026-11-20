"""Unit tests for the fail-closed Docling -> existing N4 offset bridge."""
from __future__ import annotations

import hashlib
import unittest
from dataclasses import dataclass

from src.documents.adapters.parsers.docling_n4_source_bridge import (
    DocumentN4BridgeError, project_docling_to_existing_n4,
)

@dataclass
class Window:
    ordinal: int
    source_sha256: str
    core_start: int
    core_end: int
    context_start: int
    context_end: int
    context_sha256: str
    context_text: str
    @property
    def core_text(self):
        return self.context_text[self.core_start-self.context_start:
                                 self.core_end-self.context_start]

def planner(text, *, revision_id, max_context_chars, overlap_chars):
    digest=hashlib.sha256(text.encode()).hexdigest()
    out=[]
    size=80
    for start in range(0, len(text), size):
        end=min(len(text), start+size)
        context_start=max(0,start-overlap_chars)
        context_end=min(len(text),end+overlap_chars)
        context=text[context_start:context_end]
        out.append(Window(len(out),digest,start,end,context_start,context_end,
                          hashlib.sha256(context.encode()).hexdigest(),context))
    return tuple(out)

def fixture():
    return {
      "scope":{"tenant_id":"t","project_id":"p","document_id":"d","revision_id":"r"},
      "source":{"sha256":"f"*64,"basis":"PINNED_SOURCE_BYTES","format":".pdf"},
      "state":"CANDIDATE_UNVALIDATED","trusted_promotions":0,
      "effects_allowed":False,
      "coverage":{"docling_layout_sequence_available":True},
      "reading_order":["docling:text:0","docling:table:0","docling:text:1"],
      "text_items":[
        {"source_locator":"docling:text:0","content":"Clause 9.6 delivery at FAT. "*8,
         "locations":[{"page":1}]},
        {"source_locator":"docling:text:1","content":"Annex defines price ceiling.",
         "locations":[{"page":3}]}],
      "tables":[{"source_locator":"docling:table:0","rows":2,"columns":2,
        "cells":[
           {"text":"Date","row_start":0,"col_start":0},
           {"text":"Amount","row_start":0,"col_start":1},
           {"text":"20 June","row_start":1,"col_start":0},
           {"text":"100000","row_start":1,"col_start":1}],
        "locations":[{"page":2},{"page":3}]}],
    }

def projection(c):
    return "\n\n".join([
        c["text_items"][0]["content"],
        "Date | Amount\n20 June | 100000",
        c["text_items"][1]["content"],
    ])

class SourceBridgeTests(unittest.TestCase):
    def test_existing_planner_covers_full_text_and_maps_pages(self):
        c=fixture()
        data=project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                             window_planner=planner,overlap_chars=5)
        self.assertEqual(data["n4_model_text_sha256"],
                         hashlib.sha256(projection(c).encode()).hexdigest())
        self.assertEqual(data["coverage"]["core_chars"],len(projection(c)))
        self.assertGreater(data["coverage"]["window_count"],1)
        self.assertFalse(data["n4_executed"])
        self.assertEqual(data["trusted_promotions"],0)
        self.assertIsNone(data["n12_source_attestation"])
        pages={p for w in data["window_evidence_map"] for s in w["core_evidence"]
               for p in s["pages"]}
        self.assertEqual(pages,{1,2,3})
        core_offsets=[(x["core_start"],x["core_end"]) for x in data["window_evidence_map"]]
        self.assertEqual(core_offsets[0][0],0)
        self.assertEqual(core_offsets[-1][1],len(projection(c)))

    def test_rejects_changed_n2_projection_without_offset_map(self):
        c=fixture()
        with self.assertRaisesRegex(DocumentN4BridgeError,"offset map"):
            project_docling_to_existing_n4(c,n2_safe_projection="REDACTED",
                                            window_planner=planner)

    def test_rejects_untrusted_state_with_effects(self):
        c=fixture();c["effects_allowed"]=True
        with self.assertRaisesRegex(DocumentN4BridgeError,"authority"):
            project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                            window_planner=planner)

    def test_rejects_missing_layout_instead_of_conjecture(self):
        c=fixture();c["coverage"]["docling_layout_sequence_available"]=False
        with self.assertRaisesRegex(DocumentN4BridgeError,"order"):
            project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                            window_planner=planner)

    def test_rejects_corrupt_n4_planner_source_sha(self):
        def broken(text,*,revision_id,max_context_chars,overlap_chars):
            arr=planner(text,revision_id=revision_id,
                        max_context_chars=max_context_chars,overlap_chars=overlap_chars)
            arr[0].source_sha256="0"*64
            return arr
        c=fixture()
        with self.assertRaisesRegex(DocumentN4BridgeError,"SHA"):
            project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                            window_planner=broken)

    def test_rejects_incomplete_planner_core_inventory(self):
        def broken(text,*,revision_id,max_context_chars,overlap_chars):
            return planner(text,revision_id=revision_id,
                           max_context_chars=max_context_chars,overlap_chars=overlap_chars)[:-1]
        c=fixture()
        with self.assertRaisesRegex(DocumentN4BridgeError,"lossless"):
            project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                            window_planner=broken)

    def test_no_model_call_and_no_original_pdf_attestation(self):
        c=fixture()
        r=project_docling_to_existing_n4(c,n2_safe_projection=projection(c),
                                          window_planner=planner)
        self.assertEqual(r["original_pdf_page_attestation"],"UNVERIFIED")
        self.assertTrue(all(w["status"]=="PLANNED_UNEXAMINED"
                            for w in r["window_evidence_map"]))
        self.assertTrue(all(all(not e["page_anchor_verified_against_original"]
                                for e in w["core_evidence"])
                            for w in r["window_evidence_map"]))

if __name__=="__main__":
    unittest.main()
