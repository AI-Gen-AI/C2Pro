#!/usr/bin/env python
"""Build the deterministic P0c semantic no-change probe from Contract B.

The derived PDF has identical parser-visible text to Contract B but different
bytes because it carries a bounded metadata marker. The script verifies both
properties before writing output.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = (
    REPO_ROOT
    / "apps/web/src/tests/e2e/test-data/pj01/contract-b.pdf"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "apps/web/playwright/.prod-p0c/contract-c-semantic-no-change.pdf"
)


def _blocks(pdf_bytes: bytes) -> list[tuple[int, str]]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(pdf_bytes)
        handle.flush()
        doc = fitz.open(handle.name)
        result: list[tuple[int, str]] = []
        for page_no, page in enumerate(doc, start=1):
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                text = " ".join(
                    "".join(span["text"] for span in line.get("spans", []))
                    for line in block.get("lines", [])
                ).strip()
                if text:
                    result.append((page_no, text))
        doc.close()
        return result


def build() -> tuple[str, str]:
    source = DEFAULT_SOURCE.resolve(strict=True)
    output = DEFAULT_OUTPUT.resolve(strict=False)
    if source != DEFAULT_SOURCE.resolve():
        raise RuntimeError("canonical source path resolution failed")
    if output.parent != DEFAULT_OUTPUT.parent.resolve():
        raise RuntimeError("canonical output path resolution failed")

    original = source.read_bytes()
    doc = fitz.open(stream=original, filetype="pdf")
    doc.set_metadata(
        {
            "subject": "C2Pro P0c semantic no-change probe v1",
            "keywords": "PJ01-P0C-NO-CHANGE",
        }
    )
    derived = doc.tobytes(garbage=4, deflate=True, no_new_id=True)
    doc.close()

    original_sha = hashlib.sha256(original).hexdigest()
    derived_sha = hashlib.sha256(derived).hexdigest()
    if original_sha == derived_sha:
        raise RuntimeError("derived no-change fixture must be byte-distinct")
    if _blocks(original) != _blocks(derived):
        raise RuntimeError("derived no-change fixture changed parser-visible text")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(derived)
    return original_sha, derived_sha


def main() -> int:
    original_sha, derived_sha = build()
    print("P0C_NO_CHANGE_FIXTURE=PASS")
    print(f"source_sha256={original_sha}")
    print(f"derived_sha256={derived_sha}")
    print(f"output={DEFAULT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
