"""TS-UD-ANL-WBS-002: WBS extraction preserves explicit schedule attributes."""

from __future__ import annotations

from datetime import date

from src.analysis.adapters.ai.tools.wbs_extraction_tool import WBSExtractionTool, WBSItemOutput
from src.analysis.adapters.graph.nodes import _wbs_contract_payload
from src.core.ai.tools import ToolResult, ToolStatus


def test_wbs_item_output_keeps_optional_schedule_fields() -> None:
    """TS-UD-ANL-WBS-002: downstream schedule persistence receives typed facts."""
    item = WBSItemOutput(
        code="SCH-001",
        name="Foundation",
        item_type="activity",
        start_date="2026-01-01",
        end_date="2026-04-15",
        predecessor_id="SCH-000",
        status="delayed",
    )

    assert item.start_date == date(2026, 1, 1)
    assert item.end_date == date(2026, 4, 15)
    assert item.predecessor_id == "SCH-000"
    assert item.status == "delayed"


def test_wbs_contract_payload_keeps_schedule_dependency_and_status() -> None:
    """TS-UD-ANL-WBS-002: N5 must not discard schedule facts emitted by the tool."""
    payload = _wbs_contract_payload(
        {
            "code": "SCH-002",
            "name": "Structure",
            "start_date": "2026-04-01",
            "end_date": "2026-08-01",
            "predecessor_id": "SCH-001",
            "status": "delayed",
        }
    )

    assert payload["predecessor_id"] == "SCH-001"
    assert payload["status"] == "delayed"


def test_wbs_tool_payload_serializes_schedule_dates_for_n5_contract() -> None:
    """TS-UD-ANL-WBS-002: tool dates reach N5 as JSON-compatible contract values."""
    tool_item = WBSItemOutput(
        code="SCH-002",
        name="Structure",
        item_type="activity",
        start_date="2026-04-01",
        end_date="2026-08-01",
        predecessor_id="SCH-001",
        status="delayed",
    )

    result = ToolResult(
        data=[tool_item],
        status=ToolStatus.SUCCESS,
        success=True,
        model_used="test-model",
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        latency_ms=0.0,
    )
    tool = WBSExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    state = tool.inject_output_into_state({}, result)
    payload = _wbs_contract_payload(state["extracted_wbs"][0])

    assert payload["start_date"] == "2026-04-01"
    assert payload["end_date"] == "2026-08-01"
