"""B3 ProjectGraph candidate-only preview regression / optional real-graph smoke.

Unittest with injected graph for guards. Set B3_RUN_ACTUAL_GRAPH=1 to
exercise build_project_graph() with no DB, AI, real files or writes.
"""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from uuid import UUID

from src.analysis.application.b3_source_inventory_bridge import (
    B3SourceBridgeError, assemble_b3_source_inventory,
)
from src.analysis.application.b3_project_graph_preview import (
    preview_b3_sources_in_project_graph,
)
from tests.unit.analysis.test_b3_source_inventory_bridge import CONTRACT, PROJECT, TENANT, BUDGET, SCHEDULE, input_bundle


def packet():
    pdf, native, rows = input_bundle()
    return assemble_b3_source_inventory(
        contract_revision=CONTRACT, contract_sidecar=pdf,
        schedule_revision=SCHEDULE, native_schedule=native,
        budget_revision=BUDGET, budget_rows=rows,
    )


class StubGraph:
    def __init__(self, *, outcome="ok"):
        self.outcome = outcome
        self.last = None

    async def ainvoke(self, state):
        self.last = state
        if self.outcome == "empty":
            return {**state, "node_results": []}
        result = {
            **state,
            "node_results": [
                SimpleNamespace(node="load_current_artifacts", status="ok"),
                SimpleNamespace(node="align_entities", status="ok"),
            ],
        }
        if self.outcome == "promote":
            result["artifacts"] = [object()]
        elif self.outcome == "score":
            result["coherence_result"] = {"overall_score": 99}
        elif self.outcome == "snapshot":
            result["snapshot_id"] = UUID(int=102)
        elif self.outcome == "failed":
            result["node_results"].append(SimpleNamespace(node="health", status="failed"))
        return result


class B3PreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_readonly_inventory_reaches_graph_without_scoring(self):
        g = StubGraph()
        result = await preview_b3_sources_in_project_graph(
            packet=packet(), tenant_id=TENANT, project_id=PROJECT,
            graph_factory=lambda: g,
        )
        self.assertEqual(result["source_families"], ["contract", "schedule", "budget"])
        self.assertIsNone(result["coherence_score"])
        self.assertEqual(g.last["artifacts"], [])
        self.assertEqual(g.last["structured_source_units"], [])
        self.assertEqual(g.last["canonical_materialization_status"], "no_trusted_artifacts")
        self.assertNotIn("snapshot_repository", g.last)
        self.assertNotIn("alert_correlation_runner", g.last)

    async def test_mismatched_tenant_and_extra_scoring_field_rejected(self):
        p = packet()
        p["tenant_id"] = str(UUID(int=999))
        with self.assertRaisesRegex(B3SourceBridgeError, "tenant/project"):
            await preview_b3_sources_in_project_graph(
                packet=p, project_id=PROJECT, tenant_id=TENANT, graph_factory=StubGraph,
            )
        p = packet()
        p["coherence_score"] = 100
        with self.assertRaisesRegex(B3SourceBridgeError, "trusted authority"):
            await preview_b3_sources_in_project_graph(
                packet=p, project_id=PROJECT, tenant_id=TENANT, graph_factory=StubGraph,
            )

    async def test_duplicate_or_unscoped_source_reference_rejected(self):
        p = packet()
        p["structured_source_refs"].append(p["structured_source_refs"][0].copy())
        p["source_count"] = len(p["structured_source_refs"])
        with self.assertRaisesRegex(B3SourceBridgeError, "duplicate"):
            await preview_b3_sources_in_project_graph(
                packet=p, project_id=PROJECT, tenant_id=TENANT, graph_factory=StubGraph,
            )
        p = packet()
        p["structured_source_refs"][1]["role"] = "TRUSTED"
        with self.assertRaisesRegex(B3SourceBridgeError, "scope or authority"):
            await preview_b3_sources_in_project_graph(
                packet=p, project_id=PROJECT, tenant_id=TENANT, graph_factory=StubGraph,
            )

    async def test_rejects_graph_scoring_promotion_snapshot_and_failed_nodes(self):
        for outcome in ("promote", "score", "snapshot", "failed", "empty"):
            with self.subTest(outcome=outcome):
                with self.assertRaises(B3SourceBridgeError):
                    await preview_b3_sources_in_project_graph(
                        packet=packet(), project_id=PROJECT, tenant_id=TENANT,
                        graph_factory=lambda: StubGraph(outcome=outcome),
                    )

    @unittest.skipUnless(
        os.environ.get("B3_RUN_ACTUAL_GRAPH") == "1",
        "explicit isolated real-node preview smoke only",
    )
    async def test_actual_compiled_read_only_graph_only_two_nodes(self):
        result = await preview_b3_sources_in_project_graph(
            packet=packet(), project_id=PROJECT, tenant_id=TENANT,
        )
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["source_revision_count"], 3)
        self.assertEqual(result["node_statuses"]["load_current_artifacts"], "ok")
        self.assertEqual(result["node_statuses"]["align_entities"], "ok")
        self.assertEqual(set(result["node_statuses"]), {"load_current_artifacts", "align_entities"})
        self.assertNotIn("cross_doc_coherence", result["node_statuses"])
        self.assertNotIn("write_snapshot", result["node_statuses"])
        self.assertNotIn("alert_correlation", result["node_statuses"])
        self.assertIsNone(result["coherence_score"])


if __name__ == "__main__":
    unittest.main()
