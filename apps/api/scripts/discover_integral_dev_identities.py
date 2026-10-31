#!/usr/bin/env python
"""READ-ONLY discovery of an EXISTING Clerk DEVELOPMENT identity usable as identity B of the integral S1-S8 UAT.

It answers: "is there already a synthetic Development user that could be B, without creating anything?"

* Every Clerk call is a GET (``ReadOnlyClerk`` refuses any other method). Production keys are refused.
* The user inventory is read COMPLETELY (paginated, cross-checked with Clerk's own count). If it cannot be
  completed the verdict is INVENTORY_INCOMPLETE and nothing is concluded from the partial view.
* Only users AUTHORISED as synthetic test accounts are ever considered: ``publicMetadata``/``privateMetadata``
  ``c2pro_synthetic: true``, a Clerk test address (``+clerk_test``), or a domain listed in the
  ``INTEGRAL_SYNTHETIC_EMAIL_DOMAINS`` variable. Every other user is discarded unexamined (no membership lookup).
* A candidate is VALID when it has exactly one Organization membership, that Organization and tenant differ from
  A's, and the tenant is a valid UUID.
* It prints counts, discard reasons and pseudonyms only (sha256 prefixes) -- never an email, a Clerk id or a key.

Exit 0 = a complete inventory was produced (see ``verdict``); 1 = INVENTORY_INCOMPLETE or refused.
Verdicts: DEV_B_AVAILABLE, DEV_B_PREPARABLE (synthetic users without an Organization),
NO_AUTHORISED_CANDIDATE (new synthetic identity needed), INVENTORY_INCOMPLETE.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

FAILED, READY = 1, 0


def _load_sibling(name: str) -> Any:
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_preflight = _load_sibling("preflight_integral_identities")
_is_uuid = _preflight._is_uuid
_pseudonym = _preflight._pseudonym
_load_provisioner = _preflight._load_provisioner

PAGE = 100
MAX_PAGES = (
    200  # 20 000 users; beyond this the inventory is declared incomplete rather than guessed
)


class ReadOnlyClerk:
    """The only Clerk client of this script: GET or nothing."""

    def __init__(self, client: httpx.Client, base: str) -> None:
        self._client = client
        self._base = base

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.request("GET", f"{self._base}{path}", params=params)
        if response.status_code >= 400:
            raise RuntimeError(f"Clerk GET {path} failed with {response.status_code}")
        return response.json()

    def request(self, method: str, *_: Any, **__: Any) -> Any:  # pragma: no cover - guard
        raise RuntimeError(f"discovery is read-only: {method} is refused")


def _unwrap(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        data = payload.get("data", [])
        return list(data) if isinstance(data, list) else []
    return list(payload) if isinstance(payload, list) else []


def emails_of(user: dict[str, Any]) -> list[str]:
    return [
        str(e.get("email_address") or "").strip().lower()
        for e in (user.get("email_addresses") or [])
        if e.get("email_address")
    ]


def is_authorised_synthetic(user: dict[str, Any], domains: frozenset[str]) -> bool:
    """Pure: may this account be used for synthetic tests? Anything not positively marked is NOT."""
    for key in ("public_metadata", "private_metadata", "unsafe_metadata"):
        if (user.get(key) or {}).get("c2pro_synthetic") is True:
            return True
    for email in emails_of(user):
        if "+clerk_test@" in email or email.rsplit("@", 1)[-1] in domains:
            return True
    return False


def read_inventory(
    fetch_page: Callable[[int], list[dict[str, Any]]], total: int | None
) -> tuple[list[dict[str, Any]], bool]:
    """Pure-ish: read every page. Returns (users, complete). Complete = Clerk's count was matched exactly."""
    users: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        batch = fetch_page(page * PAGE)
        users.extend(batch)
        if len(batch) < PAGE:
            break
    else:
        return users, False
    ids = {str(u.get("id")) for u in users}
    return users, total is not None and len(users) == total and len(ids) == len(users)


def classify_candidate(
    memberships: list[dict[str, Any]], a_org: str, a_tenant: str
) -> tuple[str, dict[str, str]]:
    """Pure: (reason, identifiers). Reason VALID is the only usable one."""
    if not memberships:
        return "ZERO_MEMBERSHIP_PREPARABLE", {}
    if len(memberships) > 1:
        return "MULTIPLE_MEMBERSHIPS", {}
    org = memberships[0].get("organization") or {}
    org_id = str(org.get("id") or "")
    tenant = str((org.get("public_metadata") or {}).get("tenant_id") or "")
    if not org_id:
        return "MEMBERSHIP_WITHOUT_ORGANIZATION", {}
    if not tenant:
        return "ORGANIZATION_WITHOUT_TENANT", {}
    if not _is_uuid(tenant):
        return "TENANT_NOT_UUID", {}
    if org_id == a_org:
        return "SHARES_ORGANIZATION_WITH_A", {}
    if tenant == a_tenant:
        return "SHARES_TENANT_WITH_A", {}
    return "VALID", {"organization": org_id, "tenant": tenant}


def build_receipt(
    *,
    complete: bool,
    listed: int,
    counted: int | None,
    discards: Counter[str],
    candidates: list[dict[str, Any]],
    a_known: bool,
    unmarked_pseudonyms: list[str] | None = None,
) -> dict[str, Any]:
    valid = [c for c in candidates if c["reason"] == "VALID"]
    preparable = [c for c in candidates if c["reason"] == "ZERO_MEMBERSHIP_PREPARABLE"]
    if not complete:
        verdict = "INVENTORY_INCOMPLETE"
    elif valid:
        verdict = "DEV_B_AVAILABLE"
    elif preparable:
        verdict = "DEV_B_PREPARABLE"
    else:
        verdict = "NO_AUTHORISED_CANDIDATE"
    unmarked = discards.get("NOT_AUTHORISED_SYNTHETIC", 0)
    # Creation is only the conclusion when NO other user could be authorised: existing but unmarked users are an
    # owner decision (mark one as synthetic, or confirm none may be used) before anything is created.
    creation_required = verdict == "NO_AUTHORISED_CANDIDATE" and a_known and unmarked == 0
    next_step = {
        "DEV_B_AVAILABLE": "select the valid candidate and set INTEGRAL_CLERK_DEV_B_EMAIL",
        "DEV_B_PREPARABLE": "authorise the preparation of the candidate's Organization (integral-prepare-dev-b)",
        "INVENTORY_INCOMPLETE": "repeat the read-only discovery; no conclusion is drawn",
        "NO_AUTHORISED_CANDIDATE": (
            "a new synthetic identity is needed"
            if creation_required
            else "owner decision: mark one unmarked user as synthetic (publicMetadata c2pro_synthetic=true or "
            "INTEGRAL_SYNTHETIC_EMAIL_DOMAINS) or confirm none may be used; then repeat"
        ),
    }[verdict]
    # The vocabulary of the owner's brief: a candidate, creation (only after a complete search with NO unmarked
    # account left to qualify), or an inventory that cannot be concluded (including accounts nobody has qualified).
    if verdict in {"DEV_B_AVAILABLE", "DEV_B_PREPARABLE"}:
        outcome = "DEV_B_CANDIDATE_FOUND"
    elif creation_required:
        outcome = "DEV_B_CREATION_REQUIRED"
    else:
        outcome = "INVENTORY_INCOMPLETE"
    return {
        "verdict": verdict,
        "outcome": outcome,
        "unmarked_users": unmarked,
        "unmarked_pseudonyms": sorted(unmarked_pseudonyms or []),
        "next_step": next_step,
        "inventory": {
            "complete": complete,
            "users_listed": listed,
            "users_counted_by_clerk": counted,
        },
        "identity_a_resolved": a_known,
        "discard_reasons": dict(sorted(discards.items())),
        "candidates": candidates,
        "creation_required": creation_required,
    }


def main() -> int:
    provisioner = _load_provisioner()
    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    publishable = os.getenv("CLERK_PUBLISHABLE_KEY") or os.getenv(
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
    )
    if not secret_key:
        print("FAIL: CLERK_SECRET_KEY is required.", file=sys.stderr)
        return FAILED
    try:
        environment = provisioner.require_development_instance(secret_key, publishable)
    except provisioner.FixtureError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return FAILED
    domains = frozenset(
        d.strip().lower().lstrip("@")
        for d in os.getenv("INTEGRAL_SYNTHETIC_EMAIL_DOMAINS", "").split(",")
        if d.strip()
    )
    email_a = os.getenv("E2E_CLERK_USER_EMAIL", provisioner.DEFAULT_E2E_EMAIL).strip().lower()
    discards: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    unmarked: list[str] = []
    a_user = a_org = a_tenant = ""
    try:
        with httpx.Client(timeout=30.0, headers={"Authorization": f"Bearer {secret_key}"}) as http:
            clerk = ReadOnlyClerk(http, provisioner.CLERK_API_BASE)
            counted_payload = clerk.get("/users/count")
            counted = (
                counted_payload.get("total_count") if isinstance(counted_payload, dict) else None
            )
            users, complete = read_inventory(
                lambda offset: _unwrap(
                    clerk.get(
                        "/users", {"limit": PAGE, "offset": offset, "order_by": "+created_at"}
                    )
                ),
                int(counted) if isinstance(counted, int) else None,
            )
            a_matches = [u for u in users if email_a in emails_of(u)]
            if len(a_matches) == 1:
                a_user = str(a_matches[0].get("id") or "")
                a_ms = _unwrap(
                    clerk.get(f"/users/{a_user}/organization_memberships", {"limit": PAGE})
                )
                if len(a_ms) == 1:
                    a_o = a_ms[0].get("organization") or {}
                    a_org = str(a_o.get("id") or "")
                    a_tenant = str((a_o.get("public_metadata") or {}).get("tenant_id") or "")
            for user in users if complete else []:
                uid = str(user.get("id") or "")
                if uid == a_user:
                    discards["IS_IDENTITY_A"] += 1
                    continue
                if not is_authorised_synthetic(user, domains):
                    discards["NOT_AUTHORISED_SYNTHETIC"] += 1
                    # Pseudonym only (sha256 prefix of the primary email): the owner can recognise their own
                    # account by hashing it, and nothing is examined about an account nobody has qualified.
                    unmarked.append(_pseudonym((emails_of(user) or [""])[0]))
                    continue
                ms = _unwrap(clerk.get(f"/users/{uid}/organization_memberships", {"limit": PAGE}))
                reason, ids = classify_candidate(ms, a_org, a_tenant)
                candidates.append(
                    {
                        "reason": reason,
                        "user": _pseudonym(uid),
                        "email_pseudonym": _pseudonym((emails_of(user) or [""])[0]),
                        "organization": _pseudonym(ids.get("organization")),
                        "tenant": _pseudonym(ids.get("tenant")),
                    }
                )
    except (RuntimeError, httpx.HTTPError) as exc:
        print(json.dumps({"verdict": "INVENTORY_INCOMPLETE", "error": str(exc)[:160]}))
        return FAILED
    receipt = build_receipt(
        complete=complete,
        listed=len(users),
        counted=int(counted) if isinstance(counted, int) else None,
        discards=discards,
        candidates=candidates,
        a_known=bool(a_org and a_tenant),
        unmarked_pseudonyms=unmarked,
    )
    receipt["clerk_environment"] = environment
    receipt["synthetic_domains_configured"] = len(domains)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return READY if complete else FAILED


if __name__ == "__main__":
    sys.exit(main())
