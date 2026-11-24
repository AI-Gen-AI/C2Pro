"""B3 liability contract. Pure accounting, no provider or ledger I/O."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

VERSION = "b3-liability-v1"
SCHEMA = "b3-ledger-v2"


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False, default=str).encode()).hexdigest()


def money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid liability amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid liability amount")
    return amount


@dataclass(frozen=True)
class LiabilityReceiptV1:
    version: str
    ledger_scope: str
    tenant_id: str | None
    reservation_id: str
    provider: str | None
    alias: str | None
    currency: str
    reserved_usd: str
    settled_usd: str | None
    exposure_usd: str
    state: str
    resolution: str | None
    evidence_refs: tuple[str, ...]
    blocking_reason: str | None
    snapshot_hash: str
    attribution_reason: str | None
    receipt_hash: str = ""

    def blocks(self, key: str, tenant_id: str | None = None) -> bool:
        if not self.blocking_reason:
            return False
        if self.tenant_id is not None and tenant_id is not None and self.tenant_id != tenant_id:
            return False
        return not self.alias or not self.provider or key == f"{self.alias}:{self.provider}"


@dataclass(frozen=True)
class LiabilitySnapshotV1:
    version: str
    ledger_scope: str
    snapshot_hash: str
    receipts: tuple[LiabilityReceiptV1, ...]

    @property
    def exposure_usd(self) -> Decimal:
        return sum((money(r.exposure_usd) for r in self.receipts), Decimal(0))


def _identity(event: dict[str, Any], ordinal: int) -> tuple[str | None, str]:
    tenant = event.get("tenant_id")
    if tenant is not None and (not isinstance(tenant, str) or not tenant.strip()):
        raise ValueError("invalid tenant identity")
    rid = event.get("id")
    if isinstance(rid, str) and rid.strip() and not rid.startswith("UNATTRIBUTED:"):
        return tenant, rid
    if event.get("ev") == "reserve" and rid is None:
        return None, f"UNATTRIBUTED:{ordinal}"
    raise ValueError("ambiguous reservation identity")


def _key(event: dict[str, Any]) -> tuple[str | None, str | None]:
    key = event.get("key")
    if isinstance(key, str) and ":" in key:
        alias, provider = key.split(":")[:2]
        if alias and provider:
            return alias, provider
    return None, None


def _proven_not_sent(row: dict[str, Any]) -> bool:
    return (row["ev"] == "fail" and row.get("schema") == SCHEMA
            and row.get("release") == "request_not_sent"
            and row.get("error") == "RequestNotSent")


def _receipt(scope: str, snap: str, identity: tuple[str | None, str],
             rows: list[dict[str, Any]]) -> LiabilityReceiptV1:
    tenant, rid = identity
    reserves = [r for r in rows if r["ev"] == "reserve"]
    done = [r for r in rows if r["ev"] == "done"]
    if not reserves or rows[0]["ev"] != "reserve":
        raise ValueError("settlement or release without matching reservation")
    amounts = {money(r["est_usd"]) for r in reserves}
    settled = {money(r["usd"]) for r in done}
    keys = {_key(r) for r in reserves}
    alias, provider = next(iter(keys)) if len(keys) == 1 else (None, None)
    providers = {r.get("provider") for r in rows if r.get("provider") is not None}
    models = {r.get("model") for r in rows if r.get("model") is not None}
    if len(providers) > 1 or (provider and providers and provider not in providers):
        raise ValueError("contradictory provider identity")
    if len(models) > 1:
        raise ValueError("contradictory model identity")
    reserve_conflict = len(amounts) > 1 or len(keys) > 1 or len({digest(r) for r in reserves}) > 1
    receipts = {r.get("message_id") for r in done}
    if done and any(not isinstance(r, str) or not r.strip() for r in receipts):
        raise ValueError("invalid settlement receipt")
    releases = [r for r in rows if _proven_not_sent(r)]
    release = all(r.get("schema") == SCHEMA for r in reserves) and bool(releases)
    ambiguous = any(r["ev"] == "unknown" or
                    (r["ev"] == "fail" and not _proven_not_sent(r)) for r in rows)
    uncertain = any(r["ev"] in ("unknown", "fail") for r in rows)
    contradictory = len(settled) > 1 or len(receipts) > 1 or (bool(done) and release)
    reserved = max(amounts)
    actual = max(settled) if settled else None
    if contradictory or reserve_conflict:
        state = "SETTLED" if done else "UNKNOWN"
        exposure = max(reserved, actual or Decimal(0)) if reserve_conflict else (actual or Decimal(0))
        reason = "CONFLICTING_SETTLEMENT" if contradictory else "CONFLICTING_RESERVATION"
        resolution = None
    elif actual is not None:
        state, exposure, reason, resolution = "SETTLED", actual, None, "BILLED"
    elif release and not ambiguous:
        state, exposure, reason, resolution = "SETTLED", Decimal(0), None, "PROVEN_NOT_SENT"
        actual = Decimal(0)
    else:
        state = "UNKNOWN" if uncertain else "RESERVED"
        exposure, reason, resolution = reserved, "UNRECONCILED_CALL", None
    result = LiabilityReceiptV1(
        VERSION, scope, tenant, rid, provider, alias, "USD", str(reserved),
        None if actual is None else str(actual), str(exposure), state, resolution,
        tuple(sorted({digest(r) for r in rows})), reason, snap,
        "UNATTRIBUTED" if tenant is None else None)
    return replace(result, receipt_hash=digest(asdict(result)))


def liability_snapshot(events: list[dict[str, Any]], *, ledger_scope: str) -> LiabilitySnapshotV1:
    """Reduce one complete snapshot. Invalid input raises; never return zero on error."""
    if not isinstance(ledger_scope, str) or not ledger_scope.strip():
        raise ValueError("ledger scope required")
    snap = digest({"version": VERSION, "scope": ledger_scope, "events": events})
    groups: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for ordinal, event in enumerate(events):
        if event.get("schema") not in (None, SCHEMA):
            raise ValueError("unknown ledger schema")
        if event.get("ev") == "refused":
            continue
        if event.get("ev") not in ("reserve", "done", "unknown", "fail"):
            raise ValueError("unknown ledger event")
        if event.get("ledger_scope", ledger_scope) != ledger_scope:
            raise ValueError("ledger scope mismatch")
        groups.setdefault(_identity(event, ordinal), []).append(event)
    return LiabilitySnapshotV1(VERSION, ledger_scope, snap,
                               tuple(_receipt(ledger_scope, snap, key, rows)
                                     for key, rows in groups.items()))


def b3_liability(events: list[dict[str, Any]], *, ledger_scope: str,
                 tenant_id: str | None, reservation_id: str) -> LiabilityReceiptV1:
    snapshot = liability_snapshot(events, ledger_scope=ledger_scope)
    for receipt in snapshot.receipts:
        if (receipt.tenant_id, receipt.reservation_id) == (tenant_id, reservation_id):
            return receipt
    raise ValueError("reservation absent from snapshot")


def verify_receipt(receipt: LiabilityReceiptV1, snapshot: LiabilitySnapshotV1) -> None:
    """Caller must obtain the authoritative snapshot under its admission lock."""
    if (snapshot.version != VERSION or receipt.version != VERSION
            or receipt.ledger_scope != snapshot.ledger_scope
            or receipt.snapshot_hash != snapshot.snapshot_hash
            or receipt not in snapshot.receipts
            or digest(asdict(replace(receipt, receipt_hash=""))) != receipt.receipt_hash):
        raise ValueError("invalid liability receipt")
