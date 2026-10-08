"""PQ-HITL-04C: a finding fingerprint alone is NOT source membership."""

from copy import deepcopy

import pytest

from src.modules.hitl.domain.finding_source_membership import (
    FindingSourceNotBound,
    risk_source_item_id,
    verify_risk_source_membership,
)


def _candidate():
    return {
        "extracted_risks": [
            {
                "title": "Liquidated damages",
                "description": "LD capped at 10 percent",
                "category": "LEGAL",
                "severity": "HIGH",
            },
            {
                "title": "Rectification",
                "description": "Contractor bears cost of rectification within 14 days",
                "category": "QUALITY",
                "severity": "MEDIUM",
            },
        ],
    }


def test_exact_persisted_risk_item_and_ordinal_locate_once():
    payload = _candidate()
    item_id = risk_source_item_id(payload["extracted_risks"][1])
    result = verify_risk_source_membership(
        payload, source_item_id=item_id, ordinal=1
    )
    assert result.source_item_id == item_id
    assert result.ordinal == 1
    assert result.source_kind == "RISK"
    assert result.source_digest == item_id.split(":")[-1]


@pytest.mark.parametrize("ordinal", [-1, 2, 99])
def test_out_of_range_ordinal_fails_closed(ordinal: int):
    payload = _candidate()
    item_id = risk_source_item_id(payload["extracted_risks"][0])
    with pytest.raises(FindingSourceNotBound):
        verify_risk_source_membership(
            payload, source_item_id=item_id, ordinal=ordinal
        )


def test_changed_item_cannot_reuse_historical_fingerprint():
    payload = _candidate()
    old_id = risk_source_item_id(payload["extracted_risks"][0])
    changed = deepcopy(payload)
    changed["extracted_risks"][0]["severity"] = "LOW"
    with pytest.raises(FindingSourceNotBound):
        verify_risk_source_membership(
            changed, source_item_id=old_id, ordinal=0
        )


def test_duplicate_risks_are_distinct_by_ordinal_but_not_invented():
    payload = _candidate()
    payload["extracted_risks"].append(deepcopy(payload["extracted_risks"][0]))
    source = risk_source_item_id(payload["extracted_risks"][0])
    assert verify_risk_source_membership(
        payload, source_item_id=source, ordinal=0
    ).ordinal == 0
    assert verify_risk_source_membership(
        payload, source_item_id=source, ordinal=2
    ).ordinal == 2
    with pytest.raises(FindingSourceNotBound):
        verify_risk_source_membership(
            payload, source_item_id=source, ordinal=1
        )


@pytest.mark.parametrize("payload", [
    {},
    {"extracted_risks": None},
    {"extracted_risks": {"not": "a list"}},
    {"extracted_risks": ["fabricated string"]},
])
def test_absent_or_malformed_risk_array_is_not_source_evidence(payload):
    with pytest.raises(FindingSourceNotBound):
        verify_risk_source_membership(
            payload,
            source_item_id="risk-sha256:" + "0" * 64,
            ordinal=0,
        )


def test_wrong_id_or_human_supplied_title_never_verifies():
    payload = _candidate()
    for fake_id in ("Liquidated damages", "risk-sha256:" + "0" * 64, ""):
        with pytest.raises(FindingSourceNotBound):
            verify_risk_source_membership(payload, source_item_id=fake_id, ordinal=0)


def test_source_digest_is_stable_for_semantically_identical_dict_order():
    risk = _candidate()["extracted_risks"][0]
    reordered = dict(reversed(list(risk.items())))
    assert risk_source_item_id(risk) == risk_source_item_id(reordered)
