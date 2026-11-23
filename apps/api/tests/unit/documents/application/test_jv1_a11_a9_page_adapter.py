"""A11 owner tests for A9-compatible, revision-pinned physical page projection.

A9 is not imported here: L4b owns its implementation and cross-branch tests
run in an isolated combined checkout with the published exact SHAs.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.documents.application.page_span_lineage import (
    read_a9_physical_page_map,
    record_revision_page_spans,
)


def _fixture(
    blocks: list[dict] | None = None,
    page_statuses: dict[int, str] | None = None,
    source_pages: int = 55,
):
    if blocks is None:
        blocks = [
            {"text": "Artigo 9. Pagamento de EUR 125000.", "page": 9},
            {"text": "O pagamento vence em trinta dias.", "page": 9},
            {"text": "Anexo 21. Prazo de entrega.", "page": 21, "ocr": True},
        ]
    if page_statuses is None:
        page_statuses = {9: "NATIVE_TEXT", 21: "OCR_ONLY", 55: "OCR_FAILED"}
    source = "\\n\\n".join(b["text"] for b in blocks)
    # Stable actual U+000A source separators, never a backslash + n pair.
    source = source.replace("\\n", "\n")
    revision = SimpleNamespace(revision_id=uuid4(), blob_hash="a" * 64)
    payload = {
        "file_format": ".pdf",
        "text_blocks": deepcopy(blocks),
        "document_coverage": {
            "origin": "pdf_file_parser",
            "status": "UNVERIFIED",
            "source_inventory": {
                "inspection_available": True, "source_pages": source_pages,
            },
            "page_analysis": [
                {"page": page, "status": status}
                for page, status in page_statuses.items()
            ],
        },
    }
    metadata = {"parsed_text": source, "parsed_text_revision_id": str(revision.revision_id)}
    record_revision_page_spans(
        metadata, parsed_payload=payload, parsed_text=source,
        revision_id=revision.revision_id, blob_hash=revision.blob_hash,
    )
    return metadata, source, revision


def _projection(metadata: dict, text: str, revision: object):
    return read_a9_physical_page_map(metadata, parsed_text=text, revision=revision)


def test_repeated_blocks_on_one_physical_page_are_coalesced_exactly() -> None:
    metadata, source, revision = _fixture()
    projected = _projection(metadata, source, revision)
    assert projected is not None
    assert projected["schema_version"] == "a11-a9-physical-page-map-v1"
    assert projected["status"] == "PARTIAL"
    assert projected["source_pages"] == 55
    assert projected["revision_id"] == str(revision.revision_id)
    assert projected["blob_hash"] == revision.blob_hash
    assert projected["original_document_completeness_certified"] is False
    rows = projected["spans"]
    assert rows == [
        {"page": 9, "start_offset": 0,
         "end_offset": source.index("\n\nAnexo 21.")},
        {"page": 21, "start_offset": source.index("Anexo 21."),
         "end_offset": len(source)},
    ]
    assert any(r["page"] == 55 and r["reason"] == "OCR_FAILED"
               for r in projected["excluded_pages"])
    assert "Pagamento" not in repr(projected)


def test_failed_ocr_preserves_native_text_but_excludes_page_from_locator() -> None:
    blocks = [
        {"text": "Cláusula 9. Prazos e pagamentos.", "page": 9},
        {"text": "Texto nativo curto e válido.", "page": 55},
    ]
    metadata, source, revision = _fixture(
        blocks, {9: "NATIVE_TEXT", 55: "SPARSE_OCR_FAILED"}
    )
    raw = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
    assert raw["spans"][1]["page"] == 55
    assert source.endswith("Texto nativo curto e válido.")
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert [r["page"] for r in projection["spans"]] == [9]
    assert {"page": 55, "reason": "SPARSE_OCR_FAILED"} in projection["excluded_pages"]


@pytest.mark.parametrize(
    "bad_status",
    ["OCR_FAILED", "OCR_UNAVAILABLE", "OCR_EMPTY_RESULT",
     "OCR_UNCLASSIFIED", "SPARSE_OCR_FAILED", "SPARSE_OCR_EMPTY",
     "SPARSE_TEXT_UNVERIFIED", "SUSPECT_NATIVE_TEXT_UNVERIFIED",
     "NO_DIAGNOSTIC", "TEXT_OBSERVED_UNASSESSED"],
)
def test_untrusted_page_state_never_becomes_locatable(bad_status: str) -> None:
    blocks = [{"text": "Obligaciones exigibles en anexo B.", "page": 9}]
    metadata, source, revision = _fixture(blocks, {9: bad_status}, source_pages=9)
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert projection["spans"] == []
    assert projection["status"] == "NO_LOCATABLE_PAGES"
    # A11 canonicalizes unknown/missing parser diagnostics to a safe
    # non-locatable TEXT_OBSERVED_UNASSESSED state when native text exists.
    reason = "TEXT_OBSERVED_UNASSESSED" if bad_status == "NO_DIAGNOSTIC" else bad_status
    assert {"page": 9, "reason": reason} in projection["excluded_pages"]


def test_valid_native_and_successful_mixed_ocr_both_remain_locatable() -> None:
    blocks = [
        {"text": "Native short caption.", "page": 9},
        {"text": "Additional text from image.", "page": 9, "ocr": True},
        {"text": "Anexo textual en p. 21.", "page": 21},
    ]
    metadata, source, revision = _fixture(
        blocks, {9: "OCR_AUGMENTED", 21: "NATIVE_TEXT"}, source_pages=21,
    )
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert [r["page"] for r in projection["spans"]] == [9, 21]
    assert projection["spans"][0]["end_offset"] == source.index("\n\nAnexo textual")


@pytest.mark.parametrize("wrong", ["revision", "blob", "digest", "source"])
def test_stale_revision_document_and_text_digest_fail_closed(wrong: str) -> None:
    metadata, source, revision = _fixture()
    metadata = deepcopy(metadata)
    if wrong == "revision":
        revision = SimpleNamespace(revision_id=uuid4(), blob_hash=revision.blob_hash)
    elif wrong == "blob":
        revision = SimpleNamespace(
            revision_id=revision.revision_id, blob_hash="b" * 64,
        )
    elif wrong == "digest":
        entry = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
        entry["parsed_text_sha256"] = "0" * 64
    else:
        source += " unobserved"
    assert _projection(metadata, source, revision) is None


@pytest.mark.parametrize("mutation", ["overlap", "out_of_order", "missing_row",
                                      "unverified", "invalid_page", "invalid_method",
                                      "unhashable_method", "invalid_start_type"])
def test_corrupt_block_map_fails_closed_without_inventing_coverage(
    mutation: str,
) -> None:
    metadata, source, revision = _fixture()
    metadata = deepcopy(metadata)
    raw = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
    rows = raw["spans"]
    if mutation == "overlap":
        rows[1]["start_offset"] = rows[0]["end_offset"] - 3
    elif mutation == "out_of_order":
        rows[2]["page"] = 8
    elif mutation == "missing_row":
        rows.pop(1)
    elif mutation == "unverified":
        rows[1]["page_verified"] = False
    elif mutation == "invalid_page":
        rows[1]["page"] = 56
    elif mutation == "invalid_method":
        rows[1]["method"] = "FABRICATED"
    elif mutation == "unhashable_method":
        rows[1]["method"] = []
    else:
        rows[1]["start_offset"] = "24"
    assert _projection(metadata, source, revision) is None


def test_repeated_ambiguous_literal_stays_on_two_distinct_pages() -> None:
    phrase = "La penalización se aplicará a la entrega."
    blocks = [{"text": phrase, "page": 9}, {"text": phrase, "page": 10}]
    metadata, source, revision = _fixture(
        blocks, {9: "NATIVE_TEXT", 10: "NATIVE_TEXT"}, source_pages=10,
    )
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert [r["page"] for r in projection["spans"]] == [9, 10]
    assert source.count(phrase) == 2
    # A9 owns unanchored ambiguity handling: no unique page is fabricated here.


def test_ocr_success_mismatched_block_method_fails_closed() -> None:
    blocks = [{"text": "Texto nativo con origen", "page": 9}]
    metadata, source, revision = _fixture(
        blocks, {9: "OCR_ONLY"}, source_pages=9,
    )
    assert _projection(metadata, source, revision) is None



def test_duplicate_or_missing_page_status_blocks_forged_evidence() -> None:
    metadata, source, revision = _fixture()
    raw = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
    raw["pages"].append(dict(raw["pages"][8]))  # repeated physical page
    assert _projection(metadata, source, revision) is None
    raw["pages"].pop()
    raw["pages"].pop()
    assert _projection(metadata, source, revision) is None


def test_unicode_offsets_and_whitespace_are_original_unmodified_characters() -> None:
    blocks = [
        {"text": "Cláusula 1: ação e preço €.", "page": 9},
        {"text": "Anexo 2: çã ética, custo.", "page": 9},
        {"text": "OCR: multa de 10 %.", "page": 10, "ocr": True},
    ]
    metadata, source, revision = _fixture(
        blocks, {9: "NATIVE_TEXT", 10: "OCR_ONLY"}, source_pages=10,
    )
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert projection["spans"] == [
        {"page": 9, "start_offset": 0, "end_offset": source.index("\n\nOCR:")},
        {"page": 10, "start_offset": source.index("OCR:"), "end_offset": len(source)},
    ]
    # Canonical block rows and parsed_text never change during projection.
    raw = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
    assert len(raw["spans"]) == 3
    assert "Cláusula 1:" in metadata["parsed_text"]



def test_ocr_replaced_suspect_keeps_original_raw_page_but_not_a9_page() -> None:
    blocks = [{"text": "OCR sobre página sospechosa, sin validar.", "page": 9, "ocr": True}]
    metadata, source, revision = _fixture(
        blocks, {9: "OCR_REPLACED_SUSPECT"}, source_pages=9,
    )
    raw = metadata["parsed_text_page_spans_by_revision"][str(revision.revision_id)]
    assert raw["spans"][0]["method"] == "OCR"
    assert source.startswith("OCR sobre página")
    projection = _projection(metadata, source, revision)
    assert projection is not None
    assert projection["spans"] == []
    assert projection["status"] == "NO_LOCATABLE_PAGES"
    assert {"page": 9, "reason": "OCR_REPLACED_SUSPECT"} in projection["excluded_pages"]


@pytest.mark.parametrize("state,blocks", [
    ("OCR_AUGMENTED", [{"text": "Solo texto nativo.", "page": 9}]),
    ("OCR_ONLY", [
        {"text": "Nativo no esperado.", "page": 9},
        {"text": "OCR esperado.", "page": 9, "ocr": True},
    ]),
    ("NATIVE_TEXT", [{"text": "OCR no esperado.", "page": 9, "ocr": True}]),
    ("OCR_FAILED", [{"text": "OCR no puede ser exitoso y fallido.",
                      "page": 9, "ocr": True}]),
    ("OCR_REPLACED_SUSPECT", [
        {"text": "OCR reemplazado declarado pero nativo.",
         "page": 9},
    ]),
])
def test_inconsistent_ocr_diagnostics_fail_closed(state: str, blocks: list[dict]) -> None:
    metadata, source, revision = _fixture(
        blocks, {9: state}, source_pages=9,
    )
    assert _projection(metadata, source, revision) is None
