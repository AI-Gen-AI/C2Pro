"""P0 parser observations: aggregate facts, not claims of source completeness."""

from uuid import uuid4

from src.documents.application.document_coverage import (
    record_revision_document_coverage,
    summarize_parser_observations,
)


def test_contract_parser_observations_do_not_expose_source_text() -> None:
    payload = {
        "text_blocks": [
            {"text": "CLAUSE SECRET A", "page": 1},
            {"text": "CLAUSE SECRET B", "page": 2},
            {"text": "   ", "page": 3},
        ],
        "document_coverage": {"status": "UNVERIFIED", "origin": "pdf_file_parser"},
    }
    observations = summarize_parser_observations(payload)

    assert observations == {
        "text_blocks": {
            "count": 2,
            "characters": len("CLAUSE SECRET A") + len("CLAUSE SECRET B"),
            "parser_page_labels": [1, 2],
        }
    }
    assert "SECRET" not in repr(observations)


def test_schedule_rows_distinguish_parsed_data_from_source_locators() -> None:
    observations = summarize_parser_observations({
        "schedule": [
            {"task": "Milestone", "source_locator": "Plan!2", "predecessors": "A1"},
            {"task": "Procurement", "predecessors": None},
            {"task": None},
        ]
    })
    assert observations == {
        "schedule": {
            "parsed_rows": 3,
            "rows_with_source_locator": 1,
            "rows_with_task": 2,
            "rows_with_predecessors": 1,
        }
    }


def test_budget_lines_do_not_claim_total_or_sheet_coverage() -> None:
    class BudgetRows(list):
        stated_total = None
        declared_total_rows = []

    rows = BudgetRows([
        {"item": "Transformer", "source_locator": "Budget!4"},
        {"item": "Cable"},
    ])
    observations = summarize_parser_observations({"budget": rows})
    assert observations == {
        "budget": {
            "parsed_line_items": 2,
            "items_with_source_locator": 1,
            "declared_total_rows": 0,
            "has_declared_total": False,
        }
    }
    assert "expected_rows" not in repr(observations)


def test_budget_bc3_chapter_count_is_not_partida_count() -> None:
    observations = summarize_parser_observations({
        "budget": {"chapters": [{"code": "A"}, {"code": "B"}]}
    })
    assert observations == {
        "budget": {
            "parsed_chapters": 2,
            "chapter_line_item_counts_known": False,
            "has_declared_total": False,
        }
    }


def test_revision_coverage_preserves_parser_status_and_is_idempotent() -> None:
    revision = uuid4()
    metadata = {}
    payload = {
        "text_blocks": [{"text": "EPC clause 1", "page": 1}],
        "document_coverage": {
            "status": "PARTIAL",
            "origin": "pdf_file_parser",
            "limitations": ["page_not_read"],
        },
    }
    for _ in range(2):
        record_revision_document_coverage(
            metadata,
            parsed_payload=payload,
            revision_id=revision,
            blob_hash="sha256:fixture",
        )

    assert len(metadata["document_coverage_by_revision"]) == 1
    value = metadata["document_coverage_by_revision"][str(revision)]
    assert value["status"] == "PARTIAL"
    assert value["blob_hash"] == "sha256:fixture"
    assert value["parser_observations"]["text_blocks"]["count"] == 1
    assert "EPC clause" not in repr(metadata)


def test_zero_rows_remain_explicit_without_claiming_complete() -> None:
    assert summarize_parser_observations({"text_blocks": [], "schedule": []}) == {
        "text_blocks": {"count": 0, "characters": 0, "parser_page_labels": []},
        "schedule": {
            "parsed_rows": 0,
            "rows_with_source_locator": 0,
            "rows_with_task": 0,
            "rows_with_predecessors": 0,
        },
    }
