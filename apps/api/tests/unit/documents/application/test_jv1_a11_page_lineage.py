"""A11: revision-pinned physical PDF page visibility with synthetic sources only."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.documents.adapters.parsers import pdf_file_parser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.application.page_span_lineage import (
    read_revision_page_spans,
    record_revision_page_spans,
)


def _payload() -> dict:
    return {
        "file_format": ".pdf",
        "text_blocks": [
            {"text": "Artigo 1. Preço.", "page": 9, "bbox": (0, 0, 70, 10)},
            {"text": "Anexo A. Prazos.", "page": 21, "ocr": True},
        ],
        "document_coverage": {
            "status": "UNVERIFIED",
            "origin": "pdf_file_parser",
            "source_inventory": {"inspection_available": True, "source_pages": 55},
            "page_analysis": [
                {"page": 9, "status": "NATIVE_TEXT"},
                {"page": 21, "status": "OCR_ONLY", "reason": "no_native_text"},
                {"page": 55, "status": "OCR_UNAVAILABLE", "reason": "no_native_text"},
            ],
        },
    }


def test_revision_page_spans_exact_offsets_and_unreadable_pages() -> None:
    rid = uuid4()
    payload = _payload()
    text = "Artigo 1. Preço.\n\nAnexo A. Prazos."
    metadata: dict = {"parsed_text": text, "parsed_text_revision_id": str(rid)}
    record_revision_page_spans(metadata, parsed_payload=payload, parsed_text=text,
                               revision_id=rid, blob_hash="a" * 64)
    entry = metadata["parsed_text_page_spans_by_revision"][str(rid)]
    assert entry["status"] == "OBSERVED_ONLY"
    assert [(r["page"], r["start_offset"], r["end_offset"], r["method"]) for r in entry["spans"]] == [
        (9, 0, len("Artigo 1. Preço."), "NATIVE"),
        (21, len("Artigo 1. Preço.\n\n"), len(text), "OCR"),
    ]
    assert any(p["page"] == 55 and p["status"] == "OCR_UNAVAILABLE" for p in entry["pages"])
    assert "Artigo 1" not in repr(entry)
    revision = SimpleNamespace(revision_id=rid, blob_hash="a" * 64)
    assert read_revision_page_spans(metadata, parsed_text=text, revision=revision) == entry
    assert read_revision_page_spans(metadata, parsed_text=text + "!", revision=revision) is None
    assert read_revision_page_spans(metadata, parsed_text=text, revision=SimpleNamespace(
        revision_id=uuid4(), blob_hash="a" * 64)) is None


def test_page_spans_refuse_misaligned_text_and_unverified_page_count() -> None:
    rid = uuid4()
    payload = _payload()
    metadata: dict = {}
    record_revision_page_spans(metadata, parsed_payload=payload,
                               parsed_text="Different document", revision_id=rid,
                               blob_hash="b" * 64)
    entry = metadata["parsed_text_page_spans_by_revision"][str(rid)]
    assert entry["status"] == "TEXT_ALIGNMENT_UNVERIFIED"
    assert entry["spans"] == []
    assert read_revision_page_spans(metadata, parsed_text="Different document",
                                   revision=SimpleNamespace(revision_id=rid,
                                                            blob_hash="b" * 64)) is None


@pytest.mark.asyncio
async def test_sparse_image_page_appends_ocr_without_discarding_native(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF mock")
    parser = PDFFileParser()
    native = {"text": "Annex B short caption.", "page": 1, "bbox": (1, 2, 3, 4)}
    page = MagicMock()
    page.get_images.return_value = [(1,)]
    page.rect.width = 100
    page.rect.height = 200
    document = MagicMock(page_count=1)
    document.load_page.return_value = page
    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", True)
    with patch.object(pdf_file_parser.fitz, "open", return_value=document),          patch.object(parser, "_extract_page_text_blocks", return_value=[native]),          patch.object(parser, "_ocr_page", return_value="OCR additional text from picture.") as ocr:
        rows = await parser.extract_text_and_offsets(pdf)
    assert len(rows) == 2
    assert rows[0] == native
    assert rows[1]["ocr"] is True
    assert rows[1]["page"] == 1
    assert rows.page_diagnostics[0]["status"] == "OCR_AUGMENTED"
    assert rows.page_diagnostics[0]["reason"] == "sparse_native_text"
    ocr.assert_called_once()


@pytest.mark.asyncio
async def test_unreadable_image_page_records_explicit_failure(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF mock")
    parser = PDFFileParser()
    page = MagicMock()
    page.get_images.return_value = [(1,)]
    document = MagicMock(page_count=1)
    document.load_page.return_value = page
    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", False)
    with patch.object(pdf_file_parser.fitz, "open", return_value=document),          patch.object(parser, "_extract_page_text_blocks", return_value=[]):
        rows = await parser.extract_text_and_offsets(pdf)
    assert rows == []
    assert rows.page_diagnostics == [
        {"page": 1, "status": "OCR_UNAVAILABLE", "reason": "no_native_text",
         "has_images": True, "native_chars": 0, "ocr_chars": 0}
    ]


def test_a11_clause_rows_retains_physical_page_without_fake_ocr_bbox() -> None:
    """A clause anchored to OCR page 21 cannot inherit a whole-page rectangle."""
    from src.core.tasks.ingestion_tasks import _extract_contract_clauses

    native = "1.- Preço e obrigações financeiras do contrato."
    annex = "Anexo 2. Prazos e garantias vinculantes."
    text = native + "\n\n" + annex
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
        parsed_text=text,
        parsed_payload={
            "text_blocks": [
                {"text": native, "page": 9, "bbox": (1, 2, 120, 24)},
                {"text": annex, "page": 21, "ocr": True,
                 "bbox": (0, 0, 595, 842)},
            ]
        },
    )
    assert [c.clause_code for c in clauses] == ["1", "2"]
    assert [(c.text_start_offset, c.text_end_offset) for c in clauses] == [
        (0, len(native)),
        (len(native) + 2, len(text)),
    ]
    assert [c.extracted_entities["evidence_location"]["page_number"] for c in clauses] == [
        9, 21,
    ]
    assert clauses[1].extracted_entities["evidence_location"]["bbox"] is None
    assert clauses[1].full_text == annex


@pytest.mark.asyncio
async def test_a11_graph_receives_revision_bound_page_lineage_without_l3_schema_edit(
    monkeypatch,
) -> None:
    """Existing n4_source_identity channel survives Graph state validation."""
    from src.core.tasks import ingestion_tasks
    from src.documents.application.document_coverage import (
        record_revision_document_coverage,
        record_revision_parsed_text_digest,
    )

    tenant, project, docid, rid = (uuid4() for _ in range(4))
    blob_hash = "a" * 64
    payload = _payload()
    text = "Artigo 1. Preço.\n\nAnexo A. Prazos."
    metadata = {"parsed_text": text, "parsed_text_revision_id": str(rid)}
    record_revision_document_coverage(metadata, parsed_payload=payload,
                                      revision_id=rid, blob_hash=blob_hash)
    record_revision_parsed_text_digest(metadata, parsed_text=text, revision_id=rid)
    record_revision_page_spans(metadata, parsed_payload=payload, parsed_text=text,
                               revision_id=rid, blob_hash=blob_hash)
    revision = SimpleNamespace(revision_id=rid, blob_hash=blob_hash,
                               tenant_id=tenant, project_id=project, document_id=docid)
    document = SimpleNamespace(id=docid, tenant_id=tenant, project_id=project,
                               document_type=SimpleNamespace(value="contract"),
                               document_metadata=metadata, filename="synthetic.pdf")
    states: list[dict] = []

    class Orchestrator:
        async def run(self, initial_state, *, thread_id):
            states.append(initial_state)
            return {"analysis_id": None, "human_approval_required": False}

    async def claim(**kwargs):
        return None

    monkeypatch.setattr(ingestion_tasks.processing_authority, "current_authority",
                        lambda: SimpleNamespace(revision_id=rid))
    monkeypatch.setattr(ingestion_tasks.checkpoint_lineage, "analysis_thread_id",
                        lambda **kwargs: "test-a11-thread")
    monkeypatch.setattr(ingestion_tasks, "claim_review_lineage_for_current_attempt", claim)
    await ingestion_tasks._run_analysis_graph_best_effort(
        orchestrator=Orchestrator(), document=document, parsed_text=text,
        tenant_id=tenant, document_id=docid, source_revision=revision,
    )
    identity = states[-1]["n4_source_identity"]
    assert identity["physical_page_lineage"]["spans"][1]["page"] == 21
    assert identity["physical_page_lineage"]["pages"][-1]["status"] == "OCR_UNAVAILABLE"
    a9_map = identity["a9_physical_page_map"]
    assert a9_map["schema_version"] == "a11-a9-physical-page-map-v1"
    assert [row["page"] for row in a9_map["spans"]] == [9, 21]
    assert any(row["page"] == 55 and row["reason"] == "OCR_UNAVAILABLE"
               for row in a9_map["excluded_pages"])
    assert a9_map["original_document_completeness_certified"] is False
    await ingestion_tasks._run_analysis_graph_best_effort(
        orchestrator=Orchestrator(), document=document, parsed_text=text,
        tenant_id=tenant, document_id=docid,
        source_revision=SimpleNamespace(**{**vars(revision), "revision_id": uuid4()}),
    )
    assert states[-1]["n4_source_identity"] is None


@pytest.mark.asyncio
async def test_a11_composite_pdf_propagates_safe_page_diagnostics(tmp_path) -> None:
    from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
    from src.documents.adapters.parsers.pdf_file_parser import PDFExtractionBlocks

    parser = MagicMock()
    blocks = PDFExtractionBlocks()
    blocks.append({"text": "Anexo A — texto sintético", "page": 9})
    blocks.page_diagnostics.append({
        "page": 9, "status": "NATIVE_TEXT", "reason": "none",
        "has_images": False, "native_chars": 23, "ocr_chars": 0,
    })
    parser.extract_text_and_offsets = MagicMock()
    from unittest.mock import AsyncMock
    parser.extract_text_and_offsets = AsyncMock(return_value=blocks)
    adapter = CompositeFileParser(bc3_parser=MagicMock(), excel_parser=MagicMock(),
                                  pdf_parser=parser)
    with patch(
        "src.documents.adapters.parsers.composite_file_parser.inspect_pdf_source_inventory",
        return_value={"inspection_available": True, "source_pages": 9, "limitations": []},
    ):
        payload = await adapter.parse_document_file(
            SimpleNamespace(file_format=".pdf"), tmp_path / "synthetic.pdf"
        )
    assert payload["document_coverage"]["page_analysis"][0]["page"] == 9
    assert payload["document_coverage"]["page_analysis"][0]["status"] == "NATIVE_TEXT"
    assert payload["document_coverage"]["status"] == "UNVERIFIED"
    assert not any("Anexo A" in repr(item)
                   for item in payload["document_coverage"]["page_analysis"])


@pytest.mark.asyncio
async def test_physical_pdf_pages_9_21_55_have_distinct_outcomes(tmp_path, monkeypatch) -> None:
    """True PDF page numbering, including an image page OCR cannot read.

    This is a generated synthetic PDF, not a private contract or OCR API call.
    """
    from io import BytesIO

    import fitz
    from PIL import Image

    from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

    pdf = tmp_path / "synthetic-55-pages.pdf"
    image = Image.new("RGB", (24, 24), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    source = fitz.open()
    for index in range(55):
        page = source.new_page()
        if index == 8:
            page.insert_text((72, 72), "Artigo 9. Preco contratual sintético.")
        if index in {20, 54}:
            page.insert_image(fitz.Rect(50, 50, 120, 120), stream=output.getvalue())
    source.save(pdf)
    source.close()

    parser = PDFFileParser()
    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", True)

    def simulate_ocr(page, ordinal, *, diagnostic=None):
        if ordinal == 20:
            return "Anexo 21. Obrigações de entrega."
        if diagnostic is not None:
            diagnostic["outcome"] = "failed"
        return None

    with patch.object(parser, "_ocr_page", side_effect=simulate_ocr):
        adapter = CompositeFileParser(bc3_parser=MagicMock(), excel_parser=MagicMock(),
                                      pdf_parser=parser)
        payload = await adapter.parse_document_file(
            SimpleNamespace(file_format=".pdf"), pdf
        )
    blocks = payload["text_blocks"]
    assert any(b["page"] == 9 and b.get("ocr") is not True for b in blocks)
    assert any(b["page"] == 21 and b.get("ocr") is True for b in blocks)
    assert not any(b["page"] == 55 for b in blocks)
    coverage = payload["document_coverage"]
    states = {r["page"]: r for r in coverage["page_analysis"]}
    assert states[9]["status"] == "NATIVE_TEXT"
    assert states[21]["status"] == "OCR_ONLY"
    assert states[55]["status"] == "OCR_FAILED"
    assert 55 in coverage["source_inventory"]["pages_without_extracted_text"]
    assert 55 in coverage["source_inventory"]["pages_ocr_failed"]
    assert coverage["status"] == "UNVERIFIED"



def test_a11_cross_page_clause_has_page_range_but_no_fake_single_page() -> None:
    """One contractual clause spanning physical pages cannot pretend one exact page."""
    from src.core.tasks.ingestion_tasks import _extract_contract_clauses

    first = "Cláusula 5. A parte contratante deverá observar todas as referências."
    next_page = "A continuação do mesmo artigo exige o cumprimento do Anexo B."
    text = first + "\n\n" + next_page
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
        parsed_text=text,
        parsed_payload={"text_blocks": [
            {"text": first, "page": 9, "bbox": (0, 0, 140, 40)},
            {"text": next_page, "page": 21, "bbox": (0, 0, 130, 40)},
        ]},
    )
    assert len(clauses) == 1
    location = clauses[0].extracted_entities["evidence_location"]
    assert location["page_number"] is None
    assert location["page_numbers"] == [9, 21]
    assert location["bbox"] is None
    assert clauses[0].full_text == text


@pytest.mark.asyncio
async def test_a11_sync_parse_persists_revision_pin_without_docx_page_fiction(
    monkeypatch,
) -> None:
    """The synchronous ingestion route stores actual PDF geometry by revision."""
    from unittest.mock import AsyncMock

    from src.documents.application.parse_document_use_case import ParseDocumentUseCase
    from src.documents.domain.models import DocumentType

    tenant, project, docid, rid = (uuid4() for _ in range(4))
    text = "Artigo 1. Preço.\n\nAnexo A. Prazos."
    payload = _payload()
    document = SimpleNamespace(
        id=docid, project_id=project, tenant_id=tenant,
        document_type=DocumentType.CONTRACT,
        file_format=".pdf", filename="synthetic.pdf", document_metadata={},
    )
    revision = SimpleNamespace(revision_id=rid, blob_hash="a" * 64)
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=document)
    repository.update_status = AsyncMock()
    repository.update_metadata = AsyncMock()
    repository.commit = AsyncMock()
    revision_repo = MagicMock()
    revision_repo.get_current = AsyncMock(return_value=revision)
    file_parser = MagicMock()
    file_parser.parse_document_file = AsyncMock(return_value=payload)
    extract = MagicMock()
    extract.extract_entities_from_document = AsyncMock()
    rag = MagicMock()
    rag.ingest_document_chunks = AsyncMock()
    monkeypatch.setattr(
        "src.documents.application.parse_document_use_case.fetch_source_file",
        AsyncMock(return_value=Path("/tmp/fictional-a11.pdf")),
    )
    await ParseDocumentUseCase(
        document_repository=repository, storage_service=MagicMock(),
        file_parser_service=file_parser, entity_extraction_service=extract,
        rag_ingestion_service=rag, revision_repository=revision_repo,
    ).execute(tenant, docid, uuid4())
    metadata = repository.update_metadata.await_args.args[2]
    assert metadata["parsed_text"] == text
    entry = metadata["parsed_text_page_spans_by_revision"][str(rid)]
    assert entry["spans"][0]["page"] == 9
    assert entry["spans"][1]["page"] == 21
    assert entry["pages"][-1]["status"] == "OCR_UNAVAILABLE"
    assert "Artigo 1" not in repr(entry)
