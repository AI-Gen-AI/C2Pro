"""#713 truthful document evidence provenance tests."""
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from src.core.tasks.ingestion_tasks import (
    _build_text_block_index,
    _extract_contract_clauses,
)
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser


def _long_clause(prefix: str, suffix: str = "") -> str:
    return (
        f"{prefix} The contractor shall provide all required deliverables, "
        f"records, notices and supporting documentation within the agreed period. {suffix}"
    )


def test_build_text_block_index_matches_double_newline_flattening() -> None:
    blocks = [
        {"text": "alpha", "page": 1, "bbox": (1.0, 2.0, 3.0, 4.0)},
        {"text": "bravo", "page": 1, "bbox": (5.0, 6.0, 7.0, 8.0)},
        {"text": "charlie", "page": 2, "bbox": (9.0, 10.0, 11.0, 12.0)},
    ]

    index = _build_text_block_index(blocks)

    assert [(item["start_offset"], item["end_offset"]) for item in index] == [
        (0, 5),
        (7, 12),
        (14, 21),
    ]
    assert "\n\n".join(block["text"] for block in blocks)[14:21] == "charlie"
    assert all(item["normalized"] is False for item in index)


def test_single_page_single_block_clause_preserves_real_bbox_and_revision() -> None:
    revision_id = uuid4()
    text = _long_clause("1.-")
    blocks = [{"text": text, "page": 3, "bbox": (10.0, 20.0, 300.0, 90.0)}]

    clauses = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=text,
        parsed_payload={"text_blocks": blocks},
        revision_id=revision_id,
    )

    assert len(clauses) == 1
    clause = clauses[0]
    assert clause.text_start_offset == 0
    assert clause.text_end_offset == len(text.rstrip())
    location = clause.extracted_entities["evidence_location"]
    assert location == {
        "revision_id": str(revision_id),
        "page_number": 3,
        "page_numbers": [3],
        "bbox": [10.0, 20.0, 300.0, 90.0],
        "normalized": False,
    }


def test_same_page_multiblock_clause_keeps_page_without_fake_union_bbox() -> None:
    first = _long_clause("1.-")
    second = "Additional supporting records remain part of the same contractual obligation."
    blocks = [
        {"text": first, "page": 2, "bbox": (1.0, 2.0, 200.0, 40.0)},
        {"text": second, "page": 2, "bbox": (1.0, 50.0, 220.0, 90.0)},
    ]
    parsed_text = "\n\n".join(block["text"] for block in blocks)

    clause = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=parsed_text,
        parsed_payload={"text_blocks": blocks},
        revision_id=uuid4(),
    )[0]

    location = clause.extracted_entities["evidence_location"]
    assert location["page_number"] == 2
    assert location["page_numbers"] == [2]
    assert location["bbox"] is None


def test_cross_page_clause_never_claims_one_exact_page_or_bbox() -> None:
    first = _long_clause("1.-")
    second = "The same obligation continues on the following page without a new clause heading."
    blocks = [
        {"text": first, "page": 1, "bbox": (1.0, 2.0, 200.0, 40.0)},
        {"text": second, "page": 2, "bbox": (1.0, 10.0, 220.0, 50.0)},
    ]
    parsed_text = "\n\n".join(block["text"] for block in blocks)

    clause = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=parsed_text,
        parsed_payload={"text_blocks": blocks},
        revision_id=uuid4(),
    )[0]

    location = clause.extracted_entities["evidence_location"]
    assert location["page_numbers"] == [1, 2]
    assert location["page_number"] is None
    assert location["bbox"] is None


def test_duplicate_clause_text_keeps_distinct_source_offsets() -> None:
    repeated = _long_clause("1.-")
    parsed_text = f"{repeated}\n\n{repeated}"
    blocks = [
        {"text": repeated, "page": 1, "bbox": (1.0, 1.0, 100.0, 30.0)},
        {"text": repeated, "page": 2, "bbox": (1.0, 1.0, 100.0, 30.0)},
    ]

    clauses = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=parsed_text,
        parsed_payload={"text_blocks": blocks},
        revision_id=uuid4(),
    )

    assert len(clauses) == 2
    assert clauses[0].text_start_offset == 0
    assert clauses[1].text_start_offset == len(repeated) + 2
    assert clauses[0].extracted_entities["evidence_location"]["page_number"] == 1
    assert clauses[1].extracted_entities["evidence_location"]["page_number"] == 2


def test_clause_without_source_blocks_has_honest_null_location() -> None:
    text = _long_clause("1.-")

    clause = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=text,
        parsed_payload={"text_blocks": []},
        revision_id=uuid4(),
    )[0]

    location = clause.extracted_entities["evidence_location"]
    assert location["page_numbers"] == []
    assert location["page_number"] is None
    assert location["bbox"] is None



@pytest.mark.asyncio
async def test_sample_contract_fixture_proves_parser_to_clause_provenance() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    fixture = repo_root / "apps/web/src/tests/e2e/test-data/sample-contract.pdf"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        "f0bc7170cf002570be58f9225f9affc534720a4756fa1da39ae7ad328d63a9b9"
    )

    blocks = await PDFFileParser().extract_text_and_offsets(fixture)
    scope_block = next(
        block for block in blocks if "1. SCOPE OF WORK" in str(block.get("text", ""))
    )
    assert scope_block["page"] == 1
    assert isinstance(scope_block["bbox"], tuple)
    assert len(scope_block["bbox"]) == 4
    assert any(float(value) > 1.0 for value in scope_block["bbox"])

    parsed_text = "\n\n".join(
        str(block["text"]) for block in blocks if isinstance(block.get("text"), str)
    ).strip()
    revision_id = uuid4()
    clauses = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=parsed_text,
        parsed_payload={"text_blocks": blocks},
        revision_id=revision_id,
    )

    assert clauses
    located = [
        clause
        for clause in clauses
        if clause.extracted_entities["evidence_location"]["page_numbers"]
    ]
    assert located
    assert all(
        clause.extracted_entities["evidence_location"]["revision_id"]
        == str(revision_id)
        for clause in located
    )
    exact_geometry = [
        clause.extracted_entities["evidence_location"]
        for clause in located
        if clause.extracted_entities["evidence_location"]["bbox"] is not None
    ]
    assert exact_geometry
    assert all(location["normalized"] is False for location in exact_geometry)



def test_explicit_normalized_geometry_is_preserved_for_future_producers() -> None:
    revision_id = uuid4()
    text = _long_clause("1.-")
    blocks = [
        {
            "text": text,
            "page": 4,
            "bbox": (0.1, 0.2, 0.5, 0.08),
            "normalized": True,
        }
    ]

    clause = _extract_contract_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=text,
        parsed_payload={"text_blocks": blocks},
        revision_id=revision_id,
    )[0]

    location = clause.extracted_entities["evidence_location"]
    assert location["bbox"] == [0.1, 0.2, 0.5, 0.08]
    assert location["normalized"] is True
