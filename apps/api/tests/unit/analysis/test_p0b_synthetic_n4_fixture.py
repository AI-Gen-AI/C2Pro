"""Test-only rehearsal fixture: does not represent genuine N4 AI output."""
from tests.e2e_seed.p0b_synthetic_n4 import proposed_fixture_risks


def test_fixture_matches_only_exact_public_contract_source() -> None:
    sample = (
        "SAMPLE CONSTRUCTION CONTRACT\n"
        "The total contract price is EUR 2,400,000 and is fixed.\n"
        "Liquidated damages of EUR 3,000 per calendar day shall apply."
    )
    proposal = proposed_fixture_risks(sample)
    assert len(proposal) == 1
    assert proposal[0]["source_quote"] in sample
    assert proposed_fixture_risks(sample.replace("3,000", "2,000")) == []
    assert proposed_fixture_risks("PRIVATE CONTRACT with unknown material") == []
