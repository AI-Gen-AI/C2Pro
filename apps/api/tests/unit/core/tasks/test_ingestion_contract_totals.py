"""TASK-COH-BUD-RECON-006 / TS-COH-BUD-RECON-004: contract total extraction."""

import pytest

from src.core.tasks.ingestion_tasks import _build_contract_clause_data


def test_build_contract_clause_data_prefers_spanish_contract_base_total_over_guarantee() -> None:
    """TS-COH-BUD-RECON-004: contract total is captured from amount labels, not bonds."""
    parsed_text = (
        "El presupuesto base de licitacion sin impuestos asciende a 628.624.801,20 EUR. "
        "Para responder del cumplimiento se constituye una garantia definitiva por importe "
        "de 4.713.657,54 EUR."
    )
    segment = (
        "SEPTIMA: Para responder del cumplimiento se constituye una garantia definitiva "
        "por importe de 4.713.657,54 EUR."
    )

    data = _build_contract_clause_data(segment, parsed_text)

    assert data["total_amount"] == 628_624_801.20
    assert data["currency"] == "EUR"


def test_build_contract_clause_data_extracts_english_contract_price_eur() -> None:
    """TASK-COH-BUD-RECON-006: English 'Contract Price' label extracts EUR amount."""
    text = "The Contract Price shall be EUR 5,250,000 for the complete scope of works."

    data = _build_contract_clause_data(text, text)

    assert data["total_amount"] == 5_250_000.0
    assert data["currency"] == "EUR"


def test_build_contract_clause_data_extracts_inr_plain_amount() -> None:
    """TASK-COH-BUD-RECON-006: INR prefix extracted from English-label clause."""
    text = (
        "The Contract Price is INR 628,624,801 "
        "(Indian Rupees Six Hundred Twenty Eight Million only)."
    )

    data = _build_contract_clause_data(text, text)

    assert data["total_amount"] == 628_624_801.0
    assert data["currency"] == "INR"


def test_build_contract_clause_data_extracts_inr_crore_notation() -> None:
    """TASK-COH-BUD-RECON-006: crore notation expanded to base rupees."""
    text = "The total contract value is Rs. 62.86 crore including all taxes and levies."

    data = _build_contract_clause_data(text, text)

    assert data["total_amount"] == pytest.approx(62.86 * 1e7)
    assert data["currency"] == "INR"


def test_build_contract_clause_data_extracts_inr_rupee_symbol() -> None:
    """TASK-COH-BUD-RECON-006: rupee symbol resolves to INR currency."""
    text = "Lump sum contract price: ₹628,624,801 payable in three equal instalments."

    data = _build_contract_clause_data(text, text)

    assert data["total_amount"] == 628_624_801.0
    assert data["currency"] == "INR"


def test_build_contract_clause_data_largest_labeled_amount_wins() -> None:
    """TASK-COH-BUD-RECON-006: when multiple labeled amounts exist, max is chosen."""
    text = (
        "Contract Value: INR 628,624,801. "
        "Performance bond shall be INR 31,431,240 (5% of contract value)."
    )

    data = _build_contract_clause_data(text, text)

    assert data["total_amount"] == 628_624_801.0
    assert data["currency"] == "INR"
