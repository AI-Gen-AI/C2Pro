"""Offline B3/B5 contract regression; original nine B5 expectations."""

import importlib
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

GOVERNOR = Path(__file__).resolve().parents[3] / "scripts" / "real_ai_governor"
sys.path.insert(0, str(GOVERNOR))
g = importlib.import_module("real_ai_governor")
b3 = g._producer()

r = {"ev": "reserve", "id": "r", "est_usd": 0.25, "key": "C1:anthropic", "provider": "anthropic"}


def done(v):
    return dict(
        ev="done", id="r", usd=v, model="synthetic", **{"in": 1, "out": 1, "message_id": "mock"}
    )


def fail(err):
    return {"ev": "fail", "id": "r", "error": err}


cases = [
    ("timeout", [r, fail("TimeoutError")], "0.25"),
    ("429", [r, fail("HTTP429")], "0.25"),
    ("5xx", [r, fail("HTTP529")], "0.25"),
    ("unknown", [r, {"ev": "unknown", "id": "r"}], "0.25"),
    (
        "legacy_release",
        [r, {"ev": "fail", "id": "r", "schema": "b3-ledger-v2", "release": "request_not_sent"}],
        "0.25",
    ),
    ("settled_replay", [r, done(0.07), done(0.07)], "0.07"),
    ("conflicting_settlement", [r, done(0.07), done(0.05)], "0.07"),
    ("settlement_reverse", [r, done(0.05), done(0.07)], "0.07"),
    ("duplicate_reserve_replay", [r, r.copy()], "0.25"),
]


@pytest.mark.parametrize("name,events,expected", cases, ids=[c[0] for c in cases])
def test_original_b5(name, events, expected):
    s = g.summarize(events)
    assert Decimal(str(s["spent_usd"])) + Decimal(str(s["reserved_open_usd"])) == Decimal(expected)
    assert (
        Decimal(s["exposure_usd"]) == b3.liability_snapshot(events, ledger_scope="B3").exposure_usd
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "v0"),
        ("ledger_scope", "B5"),
        ("tenant_id", "foreign"),
        ("reservation_id", "other"),
        ("currency", "EUR"),
        ("exposure_usd", "0"),
        ("snapshot_hash", "0" * 64),
        ("receipt_hash", "0" * 64),
    ],
)
def test_invalid_receipt_refuses_admission(field, value, monkeypatch, tmp_path):
    snapshot = b3.liability_snapshot([r], ledger_scope="B3")
    invalid = replace(snapshot, receipts=(replace(snapshot.receipts[0], **{field: value}),))
    monkeypatch.setattr(b3, "liability_snapshot", lambda *a, **k: invalid)
    ledger = tmp_path / "ledger.jsonl"
    g._append(ledger, r)
    monkeypatch.setattr(g, "_limits", lambda: (ledger, 10, Decimal("5")))
    before = ledger.read_bytes()
    with pytest.raises(g.GovernorRefusal, match="GOVERNOR_LIABILITY_INVALID"):
        g.reserve("haiku", 1, 1)
    assert ledger.read_bytes() == before


def test_stale_snapshot_refuses_admission(monkeypatch, tmp_path):
    stale = b3.liability_snapshot([r], ledger_scope="B3")
    ledger = tmp_path / "ledger.jsonl"
    g._append(ledger, r)
    g._append(ledger, done(0.07))
    monkeypatch.setattr(b3, "liability_snapshot", lambda *a, **k: stale)
    monkeypatch.setattr(g, "_limits", lambda: (ledger, 10, Decimal("5")))
    with pytest.raises(g.GovernorRefusal, match="GOVERNOR_LIABILITY_INVALID"):
        g.reserve("haiku", 1, 1)


@pytest.mark.parametrize("events", [[r, fail("TimeoutError")], [r, done(0.07), done(0.05)]])
def test_unreconciled_blocks_admission(events, monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    for event in events:
        g._append(ledger, event)
    monkeypatch.setattr(g, "_limits", lambda: (ledger, 10, Decimal("5")))
    with pytest.raises(g.GovernorRefusal, match="GOVERNOR_LIABILITY_UNRECONCILED"):
        g.reserve("haiku", 1, 1)
    assert [e["ev"] for e in g.read_events(ledger)] == [e["ev"] for e in events] + ["refused"]


def test_distinct_tenants_and_exact_exposure():
    events = [dict(r, tenant_id="a", est_usd="0.0000001"), dict(r, tenant_id="b", est_usd="0.25")]
    s = g.summarize(events)
    assert s["calls"] == 2
    assert Decimal(s["exposure_usd"]) == Decimal("0.2500001")


def test_duplicate_receipt_rejected(monkeypatch):
    snapshot = b3.liability_snapshot([r], ledger_scope="B3")
    invalid = replace(snapshot, receipts=snapshot.receipts * 2)
    monkeypatch.setattr(b3, "liability_snapshot", lambda *a, **k: invalid)
    with pytest.raises(ValueError, match="identity"):
        g.summarize([r])


def test_missing_receipt_rejected(monkeypatch):
    snapshot = b3.liability_snapshot([r], ledger_scope="B3")
    monkeypatch.setattr(b3, "liability_snapshot", lambda *a, **k: replace(snapshot, receipts=()))
    with pytest.raises(ValueError, match="missing"):
        g.summarize([r])


def test_exact_budget_refuses_fractional_overrun(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    g._append(ledger, r)
    g._append(ledger, done("0.2500001"))
    # Haiku one input and one output token costs exactly 0.000006.
    monkeypatch.setattr(g, "_limits", lambda: (ledger, 10, Decimal("0.250006")))
    with pytest.raises(g.GovernorRefusal, match="GOVERNOR_BUDGET_CAP"):
        g.reserve("haiku", 1, 1)


def test_concurrent_admission_serialized(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(g, "_limits", lambda: (ledger, 10, Decimal("1")))

    def admit():
        try:
            return g.reserve("haiku", 1, 1)
        except g.GovernorRefusal:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: admit(), range(2)))
    assert sum(result is not None for result in results) == 1
    assert len([e for e in g.read_events(ledger) if e["ev"] == "reserve"]) == 1
