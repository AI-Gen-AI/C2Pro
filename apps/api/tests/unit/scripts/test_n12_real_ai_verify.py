"""No provider calls during N12 runner validation."""

from __future__ import annotations

import pytest

from scripts import n12_real_ai_verify


@pytest.mark.asyncio
async def test_one_call_runner_refuses_mock_mode(monkeypatch):
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    with pytest.raises(RuntimeError, match="N12_PROVIDER_MUST_BE_REAL"):
        await n12_real_ai_verify.run()


def test_n12_runner_uses_same_versioned_fixture():
    from scripts import n4_n12_real_ai_eval

    fixture = n4_n12_real_ai_eval.load_fixture()
    assert len(fixture["contract"]["clauses"]) == 9
    assert len(n4_n12_real_ai_eval._adversarial_risks(fixture)) == 8
    assert n4_n12_real_ai_eval.FIXTURE_SHA256 == (
        "6206d62492e786b2b97902cb59f19ba36f3bd996184470e5aecc3009cdf2c8eb"
    )
