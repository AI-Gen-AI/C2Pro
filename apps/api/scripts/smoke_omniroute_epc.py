#!/usr/bin/env python3
"""Eight one-shot, synthetic EPC functional checks through OmniRoute.

No production documents, no automatic retries, no persistence of secrets.
HTTP 200 alone is NOT a pass: all expected EPC facts and sources must match.
Usage: cd apps/api && python scripts/smoke_omniroute_epc.py --all
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.adapters.ai.omniroute_pilot import (  # noqa: E402
    PILOT_MODELS,
    OmniRoutePilotClient,
    OmniRoutePilotError,
)

# An upstream 429 on this provider led OmniRoute to issue 12 outbound
# attempts from ONE client-side request on 2026-11-09.
# Keep it explicit-only until real availability is demonstrated.
SUSPENDED_FROM_DEFAULT = frozenset({"openrouter"})

EXPECTED = {
    "delay_days": 31,
    "over_budget_eur": 200000,
    "evidence": ["CONTRATO-1", "CRONOGRAMA-1", "PRESUPUESTO-1"],
}
SYSTEM = (
    "Eres un analista de proyecto EPC. Responde SOLO JSON con las claves "
    "delay_days, over_budget_eur, evidence. No inventes cifras ni fuentes."
)
CONTEXT = (
    "CONTRATO-1: fecha de finalización 2026-09-30; precio total 1000000 EUR.\n"
    "CRONOGRAMA-1: fecha de finalización 2026-10-31.\n"
    "PRESUPUESTO-1: coste presupuestado 1200000 EUR.\n"
    "Calcula los días de retraso frente al contrato y el sobrecoste EUR frente "
    "al precio contractual. Cita los identificadores de los TRES documentos "
    "en una lista evidence. Sin explicación: exclusivamente JSON."
)


def is_correct(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("delay_days") == EXPECTED["delay_days"]
        and type(value.get("delay_days")) is int
        and value.get("over_budget_eur") == EXPECTED["over_budget_eur"]
        and type(value.get("over_budget_eur")) is int
        and isinstance(value.get("evidence"), list)
        and set(value["evidence"]) == set(EXPECTED["evidence"])
        and len(value["evidence"]) == 3
    )


async def check_one(
    provider: str, key: str, base_url: str, timeout: float
) -> dict[str, object]:
    model = PILOT_MODELS[provider]
    row: dict[str, object] = {"provider": provider, "model": model}
    t0 = time.monotonic()
    try:
        client = OmniRoutePilotClient(
            base_url=base_url, api_key=key, model=model, timeout_seconds=timeout
        )
        output = await client.extract_json(SYSTEM, CONTEXT, "epc_synthetic_evaluation")
        row["result"] = "PASS_EPC_SYNTHETIC" if is_correct(output) else "FAIL_EPC_FACTS"
    except OmniRoutePilotError as exc:
        row["result"] = "FAIL_" + exc.kind.upper()
        if exc.status is not None:
            row["http_status"] = exc.status
    except Exception as exc:
        row["result"] = "FAIL_LOCAL_" + type(exc).__name__
    row["elapsed_ms"] = round((time.monotonic() - t0) * 1000)
    return row


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Run all eligible routes, excluding availability-blocked models.")
    parser.add_argument("--only", default="", help="Comma-separated route names from --list.")
    parser.add_argument("--list", action="store_true", help="List the 8 routes and exit without network.")
    parser.add_argument("--base-url", default="http://127.0.0.1:20128")
    parser.add_argument("--timeout", type=float, default=40.0)
    args = parser.parse_args()

    if args.list:
        for provider, model in PILOT_MODELS.items():
            print(f"{provider}: {model}")
        return 0

    if args.all and args.only:
        parser.error("--all and --only cannot be combined.")
    providers = (
        [name for name in PILOT_MODELS if name not in SUSPENDED_FROM_DEFAULT]
        if args.all or not args.only
        else [x.strip() for x in args.only.split(",") if x.strip()]
    )
    if args.all or not args.only:
        print("SUSPENDED_FROM_DEFAULT: " + ",".join(sorted(SUSPENDED_FROM_DEFAULT)))
        print("To test a suspended provider intentionally, select it with --only.")
    if not providers or len(set(providers)) != len(providers) or any(
        x not in PILOT_MODELS for x in providers
    ):
        parser.error("Select distinct providers from --list.")

    key = os.environ.get("C2PRO_OMNIROUTE_API_KEY", "").strip()
    if not key:
        if not sys.stdin.isatty():
            print("ERROR: use an interactive terminal for hidden API-key entry.")
            return 2
        key = getpass.getpass("Clave CLIENTE de OmniRoute existente (oculta): ").strip()
    if not key:
        print("ERROR: empty OmniRoute client key; no requests sent.")
        return 2

    print(f"C2PRO_EPC_SYNTHETIC total_routes={len(providers)} client_requests_at_most={len(providers)}")
    print("NOTE: OmniRoute may retry one client request multiple times upstream on HTTP 429.")
    rows: list[dict[str, object]] = []
    for provider in providers:
        row = await check_one(provider, key, args.base_url, args.timeout)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    passes = sum(x["result"] == "PASS_EPC_SYNTHETIC" for x in rows)
    print(f"C2PRO_EPC_RESULT passed={passes} tested={len(rows)}")
    print("NOT_PRODUCTION_UAT: synthetics only; no live project or tenant, HITL or citation audit.")
    return 0 if passes == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
