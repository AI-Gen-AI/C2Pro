"""TS-UD-ANL-WBS-002: WBS extraction preserves explicit schedule attributes."""

from __future__ import annotations

from datetime import date

from src.analysis.adapters.ai.tools.wbs_extraction_tool import (
    WBSExtractionInput,
    WBSExtractionTool,
    WBSItemOutput,
)
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


def test_wbs_tool_derives_parent_only_from_an_emitted_valid_code() -> None:
    """N5 preserves a real hierarchy without creating a grouping node."""
    parent = WBSItemOutput(code="2", name="Electrical", item_type="work_package")
    child = WBSItemOutput(code="2.1", name="Cabling", item_type="activity")
    result = ToolResult(
        data=[parent, child], status=ToolStatus.SUCCESS, success=True,
        model_used="test-model", input_tokens=0, output_tokens=0,
        cost_usd=0.0, latency_ms=0.0,
    )

    state = WBSExtractionTool(
        anthropic_wrapper=object(), prompt_manager=object()
    ).inject_output_into_state({}, result)

    assert state["extracted_wbs"] == [
        {
            "code": "2", "name": "Electrical", "description": None,
            "item_type": "work_package", "confidence": None,
            "budget_allocated": None, "start_date": None, "end_date": None,
            "predecessor_id": None, "status": None, "parent_code": None, "level": 0,
        },
        {
            "code": "2.1", "name": "Cabling", "description": None,
            "item_type": "activity", "confidence": None,
            "budget_allocated": None, "start_date": None, "end_date": None,
            "predecessor_id": None, "status": None, "parent_code": "2", "level": 1,
        },
    ]


def test_wbs_tool_leaves_orphan_code_without_an_invented_parent() -> None:
    """A missing direct parent stays absent instead of becoming a synthetic WBS node."""
    orphan = WBSItemOutput(
        code="9.1", name="Unsupported child", item_type="activity", parent_code="9"
    )
    result = ToolResult(
        data=[orphan], status=ToolStatus.SUCCESS, success=True,
        model_used="test-model", input_tokens=0, output_tokens=0,
        cost_usd=0.0, latency_ms=0.0,
    )

    state = WBSExtractionTool(
        anthropic_wrapper=object(), prompt_manager=object()
    ).inject_output_into_state({}, result)

    assert state["extracted_wbs"][0]["parent_code"] is None
    assert state["extracted_wbs"][0]["level"] == 1


def test_wbs_tool_keeps_fat_source_date_unchanged() -> None:
    """N5 must not replace a source-stated FAT date with an inferred milestone."""
    item = WBSItemOutput(
        code="6", name="Factory acceptance test", item_type="activity", end_date="2027-06-10"
    )

    assert item.end_date == date(2027, 6, 10)


def test_wbs_tool_corrects_declared_cross_parent_to_direct_emitted_parent() -> None:
    result = ToolResult(
        data=[
            WBSItemOutput(code="1", name="Root", item_type="deliverable"),
            WBSItemOutput(code="1.1", name="Sibling", item_type="work_package"),
            WBSItemOutput(code="1.2", name="Direct parent", item_type="work_package"),
            WBSItemOutput(
                code="1.2.1",
                name="Child",
                item_type="activity",
                parent_code="1.1",
            ),
        ],
        status=ToolStatus.SUCCESS,
        success=True,
        model_used="test-model",
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        latency_ms=0.0,
    )

    state = WBSExtractionTool(
        anthropic_wrapper=object(), prompt_manager=object()
    ).inject_output_into_state({}, result)

    child = next(item for item in state["extracted_wbs"] if item["code"] == "1.2.1")
    assert child["parent_code"] == "1.2"


def test_wbs_prompt_marks_uncorroborated_technical_details_for_human_review() -> None:
    _, prompt = WBSExtractionTool()._build_default_prompt(
        WBSExtractionInput(document_text="technical source"),
        False,
    )

    assert prompt is not None
    assert "revisión humana" in prompt
    assert "validación semántica" in prompt


def test_unassessed_wbs_confidence_cannot_default_to_ninety_percent() -> None:
    item = WBSItemOutput(code="SCH-003", name="Steel", item_type="activity")
    assert item.confidence is None

    tool = WBSExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    result = ToolResult(
        data=[item], status=ToolStatus.SUCCESS, success=True,
        model_used="test-model", input_tokens=0, output_tokens=0,
        cost_usd=0.0, latency_ms=0.0,
    )
    state = tool.inject_output_into_state({}, result)
    assert state["extracted_wbs"][0]["confidence"] is None
    assert state["confidence_score"] is None
