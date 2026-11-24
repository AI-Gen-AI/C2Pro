"""Executable producer fixtures shared with B5; no paid calls."""
from dataclasses import replace
from decimal import Decimal

import pytest
from b3_liability import b3_liability, liability_snapshot, verify_receipt

R = {"ev": "reserve", "id": "r", "est_usd": "0.25", "key": "C1:anthropic"}
D = {"ev": "done", "id": "r", "usd": "0.07", "message_id": "mock"}


def snap(*rows):
    return liability_snapshot(list(rows), ledger_scope="B3")


@pytest.mark.parametrize("rows, expected", [
    ([R, {"ev": "fail", "id": "r", "error": error}], "0.25")
    for error in ("TimeoutError", "HTTP429", "HTTP529")
] + [
    ([R, {"ev": "unknown", "id": "r"}], "0.25"),
    ([R, {"ev": "fail", "id": "r", "schema": "b3-ledger-v2",
          "release": "request_not_sent"}], "0.25"),
    ([R, D, D], "0.07"),
    ([R, D, dict(D, usd="0.05")], "0.07"),
    ([R, dict(D, usd="0.05"), D], "0.07"),
    ([R, R], "0.25"),
])
def test_original_b3_financial_cases(rows, expected):
    assert snap(*rows).exposure_usd == Decimal(expected)


def test_original_retry_block():
    result = snap(R, {"ev": "fail", "id": "r", "error": "TimeoutError"})
    assert result.receipts[0].blocks("C1:anthropic")


def test_snapshot_identity_and_receipt():
    a, b = dict(R, tenant_id="a"), dict(R, tenant_id="b")
    result = snap(a, b, R)
    assert result.exposure_usd == Decimal("0.75")
    assert {r.tenant_id for r in result.receipts} == {"a", "b", None}
    receipt = b3_liability([a, b, R], ledger_scope="B3", tenant_id="a", reservation_id="r")
    verify_receipt(receipt, result)
    assert not receipt.blocks("C1:anthropic", "b")
    assert result.receipts[2].attribution_reason == "UNATTRIBUTED"
    assert result.receipts[2].blocks("C1:anthropic", "b")
    assert result == snap(a, b, R)
    assert result.snapshot_hash != snap(a, b).snapshot_hash


@pytest.mark.parametrize("change", [
    {"exposure_usd": "0"}, {"version": "unknown"}, {"tenant_id": "b"},
    {"snapshot_hash": "bad"}, {"receipt_hash": "bad"}, {"ledger_scope": "other"},
])
def test_invalid_receipt(change):
    result = snap(R)
    with pytest.raises(ValueError, match="invalid liability receipt"):
        verify_receipt(replace(result.receipts[0], **change), result)


def test_conflicting_settlement_blocks_admission():
    result = snap(R, D, dict(D, usd="0.05"))
    receipt = result.receipts[0]
    assert receipt.blocking_reason == "CONFLICTING_SETTLEMENT"
    assert receipt.blocks("C1:anthropic")
    assert result.exposure_usd == Decimal("0.07")


def test_proven_not_sent_and_unknown():
    r = dict(R, schema="b3-ledger-v2")
    f = {"ev": "fail", "id": "r", "schema": "b3-ledger-v2",
         "release": "request_not_sent", "error": "RequestNotSent"}
    assert snap(r, f).receipts[0].resolution == "PROVEN_NOT_SENT"
    assert snap(r, f).exposure_usd == Decimal(0)
    assert snap(r, f, {"ev": "unknown", "id": "r"}).exposure_usd == Decimal("0.25")
    assert snap(r, f, {"ev": "fail", "id": "r", "error": "TimeoutError"}).exposure_usd == Decimal("0.25")
    assert snap(r, f, D).receipts[0].blocking_reason == "CONFLICTING_SETTLEMENT"


@pytest.mark.parametrize("rows", [
    [dict(R, est_usd="-1")], [dict(R, est_usd="bad")],
    [dict(R, est_usd="Infinity")], [dict(R, tenant_id="")],
    [dict(R, id="")], [dict(R, ledger_scope="other")],
    [dict(R, ev="unrecognized")], [dict(R, schema="v99")], [D], [D, R], [R, dict(D, message_id=None)],
    [R, dict(D, provider="openai")],
    [dict(R, model="a"), dict(D, model="b")],
])
def test_bad_ledger_fails_closed(rows):
    with pytest.raises(ValueError):
        snap(*rows)


def test_absent_reservation_and_scope():
    with pytest.raises(ValueError, match="absent"):
        b3_liability([R], ledger_scope="B3", tenant_id="a", reservation_id="r")
    with pytest.raises(ValueError, match="scope"):
        liability_snapshot([R], ledger_scope="")


def test_decimal_precision():
    r = dict(R, est_usd="0.1234567890123456789")
    assert snap(r).exposure_usd == Decimal("0.1234567890123456789")

def test_empty_alias_key_blocks_all():
    assert snap(dict(R, key=":anthropic")).receipts[0].blocks("C2:openai")
