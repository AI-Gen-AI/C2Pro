"""Extract candidate penalty clauses from local contract files for the precision gate (#1136).

Input files stay outside the repository (public pliegos from the Plataforma de Contratación del Sector
Público or any other source the owner provides). Supported: ``.txt``/``.md``; ``.pdf`` through the
``pdftotext`` CLI; ``.docx`` through ``python-docx`` when installed. Output is JSONL for ``prelabel.py``;
ids are ``<prefix>-<n>`` and ``source`` is the anonymised provenance given on the command line, so no
contract or file name is written.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PENALTY_WORDS = re.compile(
    r"penalidad|penalizaci|demora|retraso|liquidated damages|delay damages|late(?:ness)? penalt|penalty",
    re.IGNORECASE,
)
FIGURE = re.compile(
    r"\d[\d.,]*\s*(?:%|por\s*100|por\s*mil|euros?|€)|\bper\s+(?:day|cent)|por\s+cada", re.IGNORECASE
)
SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-ZÁÉÍÓÚÑ0-9(])")
MIN_CHARS, MAX_CHARS = 40, 900


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        if shutil.which("pdftotext") is None:
            raise SystemExit("pdftotext is required to read PDF files")
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True
        )
        return result.stdout
    if suffix == ".docx":
        try:
            import docx
        except ImportError as error:
            raise SystemExit("python-docx is required to read .docx files") from error
        return "\n".join(paragraph.text for paragraph in docx.Document(str(path)).paragraphs)
    raise SystemExit(f"unsupported file type: {suffix}")


def guess_lang(text: str) -> str:
    spanish = len(
        re.findall(
            r"\b(?:el|la|los|las|del|por|de|se|que|penalidad|retraso|día|días)\b", text, re.I
        )
    )
    english = len(
        re.findall(r"\b(?:the|of|shall|per|day|delay|damages|contractor|penalty)\b", text, re.I)
    )
    if spanish and english and min(spanish, english) * 3 > max(spanish, english):
        return "mixed"
    return "es" if spanish >= english else "en"


def candidates(text: str) -> list[str]:
    """Paragraphs (or sentence groups) that name a penalty and carry a figure, whitespace-normalised."""
    found: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        pieces = [block] if len(block) <= MAX_CHARS else SENTENCE_END.split(block)
        for piece in pieces:
            if (
                MIN_CHARS <= len(piece) <= MAX_CHARS
                and PENALTY_WORDS.search(piece)
                and FIGURE.search(piece)
            ):
                found.append(piece)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--out", type=Path, required=True, help="candidates JSONL (outside the repository)"
    )
    parser.add_argument(
        "--source", required=True, help='anonymised provenance, e.g. "PCAP/ES/2020-2024"'
    )
    parser.add_argument("--prefix", required=True, help='id prefix, e.g. "es-pcsp"')
    args = parser.parse_args(argv)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for path in args.files:
        for clause in candidates(read_text(path)):
            if clause in seen:
                continue
            seen.add(clause)
            rows.append(
                {
                    "id": f"{args.prefix}-{len(rows) + 1:04d}",
                    "text": clause,
                    "lang": guess_lang(clause),
                    "source": args.source,
                    "family": "unclassified",
                }
            )
    args.out.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    print(f"{len(rows)} candidate clauses from {len(args.files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
