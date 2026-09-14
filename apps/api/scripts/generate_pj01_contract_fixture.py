#!/usr/bin/env python
"""Render the PJ-01 Contract A fixture PDF from its committed source text.

TS-UT-PJ01-FIXTURE-002 (generator half).

The PDF is a derived artifact: ``contract-a.source.txt`` is the reviewable source, and this
script turns it into a text-layer PDF whose parsed structure matches what ingestion expects:
one PDF text block per paragraph, so ``PDFFileParser`` + ``_split_contract_into_clauses``
persist one clause per ``n. - TITLE`` article.

Usage (from the repository root):

    python apps/api/scripts/generate_pj01_contract_fixture.py          # rewrite the PDF
    python apps/api/scripts/generate_pj01_contract_fixture.py --check  # fail on drift

``--check`` compares parser-visible text blocks, not bytes, so a PyMuPDF upgrade that only
changes PDF serialisation does not register as fixture drift.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "test-data" / "pj01"
SOURCE_TEXT = FIXTURE_DIR / "contract-a.source.txt"
PDF_OUTPUT = FIXTURE_DIR / "contract-a.pdf"

PAGE_WIDTH = 595  # A4, points
PAGE_HEIGHT = 842
MARGIN = 56
FONT_SIZE = 10
PARAGRAPH_GAP = 12


def _paragraphs(source_text: str) -> list[str]:
    return [paragraph.strip() for paragraph in source_text.strip().split("\n\n") if paragraph.strip()]


def render_contract_pdf(source_text: str) -> bytes:
    """Render one text box per paragraph; deterministic for a given PyMuPDF version."""
    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    top = MARGIN
    for paragraph in _paragraphs(source_text):
        rect = fitz.Rect(MARGIN, top, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)
        remaining = page.insert_textbox(rect, paragraph, fontsize=FONT_SIZE, fontname="helv")
        if remaining < 0:  # nothing was written: start a new page
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            top = MARGIN
            rect = fitz.Rect(MARGIN, top, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)
            remaining = page.insert_textbox(rect, paragraph, fontsize=FONT_SIZE, fontname="helv")
            if remaining < 0:
                raise ValueError("a contract paragraph is taller than one page")
        top += (rect.height - remaining) + PARAGRAPH_GAP
    document.set_metadata({})
    data = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    document.close()
    return data


def text_blocks(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Parser-visible structure: (page, block text) in reading order."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(pdf_bytes)
        handle.flush()
        document = fitz.open(handle.name)
        blocks: list[tuple[int, str]] = []
        for page_number, page in enumerate(document, start=1):
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                text = " ".join(
                    "".join(span["text"] for span in line.get("spans", [])) for line in block.get("lines", [])
                ).strip()
                if text:
                    blocks.append((page_number, text))
        document.close()
    return blocks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed PDF drifted from the source")
    args = parser.parse_args(argv)

    rendered = render_contract_pdf(SOURCE_TEXT.read_text(encoding="utf-8"))
    if args.check:
        if not PDF_OUTPUT.exists() or text_blocks(PDF_OUTPUT.read_bytes()) != text_blocks(rendered):
            print(f"FIXTURE DRIFT: {PDF_OUTPUT} does not match {SOURCE_TEXT}; regenerate it.", file=sys.stderr)
            return 1
        print("PJ-01 Contract A fixture is up to date.")
        return 0

    PDF_OUTPUT.write_bytes(rendered)
    print(f"wrote {PDF_OUTPUT} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
