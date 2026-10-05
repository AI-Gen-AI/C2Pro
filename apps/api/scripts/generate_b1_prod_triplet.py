#!/usr/bin/env python3
"""Generate bounded non-customer fixtures for #867 B1-12 qualification.

The fixture intentionally contains two semantically different findings:

1. TRUE INCONSISTENCY — retention is 15%, above the deterministic 10% ceiling.
   A reviewer can truthfully APPROVE this finding as a genuine inconsistency.

2. TRUE FALSE POSITIVE — the contract price is EUR 2,400,000 EXCLUDING VAT,
   while the budget declared total is EUR 2,904,000 INCLUDING 21% VAT.
   The live cross-document comparator compares stated_total to contract_total
   without tax-basis normalization and therefore sees a 21% mismatch/negative
   margin. The documents themselves explicitly prove the figures reconcile on
   the same net basis: 2,904,000 - 504,000 VAT = 2,400,000.

The schedule is a valid ordinary schedule input but is not relied upon to create
either review assertion. All content is synthetic and repository-owned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import fitz
from openpyxl import Workbook

FIXED_TIME = datetime(2026, 10, 6, tzinfo=UTC)
CONTRACT_NET_EUR = 2_400_000.00
VAT_RATE = 0.21
VAT_EUR = CONTRACT_NET_EUR * VAT_RATE
BUDGET_GROSS_EUR = CONTRACT_NET_EUR + VAT_EUR

CONTRACT_SOURCE = """B1-12 SYNTHETIC CONSTRUCTION CONTRACT

1. - CONTRACT PRICE
The fixed Contract Price is EUR 2,400,000 excluding VAT. VAT at the applicable 21 percent rate is payable in addition to the Contract Price and is not part of the net Contract Price.

2. - RETENTION
Retention shall be fifteen percent (15%) of each certified payment. This intentionally exceeds the normal C2Pro deterministic policy ceiling and is a genuine contractual risk for this qualification fixture.

3. - PAYMENT
Certified invoices are payable within thirty (30) calendar days.

4. - PROGRAMME
The Works commence on 1 June 2025 and the contractual completion date is 31 December 2025.

5. - SCOPE
The Contractor shall execute demolition, structural reinforcement, mechanical and electrical installation, finishes, testing, commissioning and handover.

6. - QUALITY
The Works shall comply with ISO 9001 and applicable EN standards. Inspection and testing records shall be maintained.

7. - SYNTHETIC QUALIFICATION NOTE
This document is synthetic, contains no customer data, and is used only for governed C2Pro production qualification.
"""

# Net construction lines deliberately sum to the contract net price. VAT is a
# separate line so the budget gross total is economically reconcilable but the
# current total-only comparator still observes a 21% apparent overrun.
BUDGET_ROWS = (
    ("Demolition and enabling works", 1, 300_000.00, 300_000.00, "gl"),
    ("Structural steel reinforcement", 1, 700_000.00, 700_000.00, "gl"),
    ("Mechanical and electrical installation", 1, 800_000.00, 800_000.00, "gl"),
    ("Finishes, testing and handover", 1, 600_000.00, 600_000.00, "gl"),
    ("VAT 21% on net contract works", 1, VAT_EUR, VAT_EUR, "tax"),
)
NET_BUDGET_ROWS_TOTAL = sum(row[3] for row in BUDGET_ROWS[:-1])
BUDGET_ROWS_TOTAL = sum(row[3] for row in BUDGET_ROWS)

SCHEDULE_ROWS = (
    ("Mobilisation and demolition", "2025-06-01", "2025-07-15", 45, "1", ""),
    ("Structural works", "2025-07-16", "2025-09-30", 77, "2", "1"),
    ("MEP installation", "2025-10-01", "2025-11-30", 61, "3", "2"),
    ("Finishes and completion", "2025-12-01", "2025-12-31", 31, "4", "3"),
)

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 56
FONT_SIZE = 10
PARAGRAPH_GAP = 12


def _prepare(workbook: Workbook, title: str) -> None:
    workbook.properties.title = title
    workbook.properties.subject = "C2Pro B1-12 production qualification synthetic fixture"
    workbook.properties.creator = "AI-Gen C2Pro"
    workbook.properties.created = FIXED_TIME.replace(tzinfo=None)
    workbook.properties.modified = FIXED_TIME.replace(tzinfo=None)


def _paragraphs(source_text: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in source_text.strip().split("\n\n")
        if paragraph.strip()
    ]


def generate_contract(path: Path) -> None:
    """Render a text-layer PDF with one parser-visible block per paragraph."""
    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    top = MARGIN
    for paragraph in _paragraphs(CONTRACT_SOURCE):
        rect = fitz.Rect(MARGIN, top, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)
        remaining = page.insert_textbox(
            rect, paragraph, fontsize=FONT_SIZE, fontname="helv"
        )
        if remaining < 0:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            top = MARGIN
            rect = fitz.Rect(MARGIN, top, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)
            remaining = page.insert_textbox(
                rect, paragraph, fontsize=FONT_SIZE, fontname="helv"
            )
            if remaining < 0:
                document.close()
                raise ValueError("contract paragraph exceeds one page")
        top += (rect.height - remaining) + PARAGRAPH_GAP
    document.set_metadata({})
    path.write_bytes(document.tobytes(garbage=4, deflate=True, no_new_id=True))
    document.close()


def generate_budget(path: Path) -> None:
    workbook = Workbook()
    _prepare(workbook, "B1 Synthetic Gross Budget")
    sheet = workbook.active
    sheet.title = "Budget"
    sheet.append(["Item", "Quantity", "Unit Price", "Total", "Unit"])
    for row in BUDGET_ROWS:
        sheet.append(list(row))
    sheet.append(["TOTAL PRESUPUESTO", None, None, BUDGET_GROSS_EUR, None])
    workbook.save(path)
    workbook.close()


def generate_schedule(path: Path) -> None:
    workbook = Workbook()
    _prepare(workbook, "B1 Synthetic Schedule")
    sheet = workbook.active
    sheet.title = "Schedule"
    sheet.append(["Task", "Start Date", "End Date", "Duration", "WBS", "Predecessors"])
    for row in SCHEDULE_ROWS:
        sheet.append(list(row))
    workbook.save(path)
    workbook.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    contract = output / "b1-contract.pdf"
    budget = output / "b1-budget.xlsx"
    schedule = output / "b1-schedule.xlsx"
    generate_contract(contract)
    generate_budget(budget)
    generate_schedule(schedule)

    manifest = {
        "schema": "c2pro-b1-prod-fixtures/v2",
        "fixture_class": "synthetic_non_customer",
        "contract": {
            "path": str(contract),
            "net_contract_price_eur": CONTRACT_NET_EUR,
            "vat_basis": "excluded",
            "retention_pct": 15.0,
            "sha256": sha256(contract),
        },
        "budget": {
            "path": str(budget),
            "net_works_eur": NET_BUDGET_ROWS_TOTAL,
            "vat_eur": VAT_EUR,
            "vat_rate": VAT_RATE,
            "declared_gross_total_eur": BUDGET_GROSS_EUR,
            "sha256": sha256(budget),
        },
        "schedule": {
            "path": str(schedule),
            "completion_date": "2025-12-31",
            "sha256": sha256(schedule),
        },
        "review_truth": {
            "genuine_inconsistency": {
                "expected_rule_id": "DET-BUD-RETENTION",
                "reason": "Contract explicitly requires 15% retention; deterministic maximum is 10%.",
            },
            "false_positive": {
                "candidate_rule_ids": ["DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"],
                "reason": (
                    "Contract total is explicitly net of VAT while the budget total is explicitly gross. "
                    "Subtracting the 21% VAT line reconciles exactly to EUR 2,400,000."
                ),
            },
        },
    }
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
