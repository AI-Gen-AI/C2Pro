"""Enroll (or unenroll) a pilot tenant in the coherence detection + canary flags.

Enables the per-tenant flags that gate the new, cost-bearing coherence capabilities so a
single pilot tenant can be observed before widening (shadow -> canary -> GA):

- ``coherence_canonical_canary``  : the expert-calibrated canonical scorer on /evaluate
- ``coherence_llm_crosscheck``    : the LLM cross-clause contradiction depth pass

Both default OFF for every other tenant, so this is a bounded, reversible rollout step.

Usage (from apps/api, with the venv active and .env pointing at the target DB):
    python scripts/enroll_coherence_pilot.py <tenant_uuid>            # enroll (enable)
    python scripts/enroll_coherence_pilot.py <tenant_uuid> --off      # roll back (disable)
    python scripts/enroll_coherence_pilot.py <tenant_uuid> --dry-run  # print, do not write

The deterministic detection floor (CROSS-LEGAL/SCOPE heuristics) and the identity
comparator are always on and need no flag.
"""
from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from src.alerts.adapters.persistence.tenant_repository import (  # noqa: E402
    SqlAlchemyTenantRepository,
)
from src.config import get_settings  # noqa: E402
from src.core import database as db  # noqa: E402
from src.core.feature_flags.tenant_flags_service import TenantFlagsService  # noqa: E402

_FLAGS = ("coherence_canonical_canary", "coherence_llm_crosscheck")


async def _run(tenant_id: UUID, enable: bool, dry_run: bool) -> None:
    action = "ENABLE" if enable else "DISABLE"
    if dry_run:
        for flag in _FLAGS:
            print(f"[dry-run] would {action} {flag} for tenant {tenant_id}")
        return

    await db.init_db()
    try:
        async with db.get_session_with_tenant(tenant_id) as session:
            service = TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=get_settings(),
            )
            for flag in _FLAGS:
                await service.set_flag(tenant_id, flag, enable)
                print(f"{action}D {flag} for tenant {tenant_id}")
    finally:
        await db.close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant_id", type=UUID, help="UUID of the pilot tenant")
    parser.add_argument("--off", action="store_true", help="disable the flags (roll back)")
    parser.add_argument("--dry-run", action="store_true", help="print the actions without writing")
    args = parser.parse_args()
    asyncio.run(_run(args.tenant_id, enable=not args.off, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
