"""TS-COH-BUD-RECON-004: deterministic contract total extraction for coherence."""

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
