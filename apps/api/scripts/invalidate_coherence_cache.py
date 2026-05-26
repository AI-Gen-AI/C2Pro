"""
One-shot coherence cache purge script for Phase G deploy (ADR-009 §G).

Connects to Redis using the application settings and invokes the canonical
invalidation handlers from ``src.coherence.cache_invalidation``.

Usage
-----
    # Dry-run: count matching keys and show a sample, but do NOT unlink
    python apps/api/scripts/invalidate_coherence_cache.py --dry-run

    # Apply: actually UNLINK all matching keys
    python apps/api/scripts/invalidate_coherence_cache.py --apply

    # Scope to a single tenant (dry-run)
    python apps/api/scripts/invalidate_coherence_cache.py --dry-run --tenant-id <UUID>

    # Scope to a single tenant (apply)
    python apps/api/scripts/invalidate_coherence_cache.py --apply --tenant-id <UUID>

Exit codes
----------
    0  Success (or dry-run completed).
    1  Argument error.
    2  Redis connection failure.

Safe to run multiple times — returns 0 even when no keys match.

References
----------
- ADR-009 §G
- Spec §6  docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Dry-run helper
# ---------------------------------------------------------------------------

_LOG_INTERVAL = 1000  # log progress every N keys scanned


async def _dry_run(redis_client, pattern: str, sample_limit: int = 10) -> int:
    """Scan *pattern* and count matches without deleting. Returns count."""
    count = 0
    samples: list[str] = []

    async for key in redis_client.scan_iter(match=pattern, count=500):
        count += 1
        if len(samples) < sample_limit:
            samples.append(key if isinstance(key, str) else key.decode())
        if count % _LOG_INTERVAL == 0:
            logger.info("dry_run_progress", pattern=pattern, keys_found=count)

    if samples:
        logger.info("dry_run_sample", pattern=pattern, sample=samples)

    return count


# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------


async def main() -> int:
    """Entry point — returns exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Phase G coherence cache purge script (ADR-009 §G). "
            "Requires --dry-run or --apply."
        )
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Print key count + sample without unlinking.",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Actually UNLINK all matching coherence cache keys.",
    )
    parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Scope purge to a single tenant UUID. Omit to purge all tenants.",
    )

    args = parser.parse_args()

    # Validate optional tenant UUID early
    tenant_id: UUID | None = None
    if args.tenant_id is not None:
        try:
            tenant_id = UUID(args.tenant_id)
        except ValueError:
            logger.error("invalid_tenant_id", value=args.tenant_id)
            return 1

    # Import here so the sys.path manipulation (if any) happens before src imports
    import redis.asyncio as redis

    from src.config import settings

    redis_url: str | None = getattr(settings, "redis_url", None)
    if not redis_url:
        logger.error("redis_url_not_configured")
        return 2

    redis_client = redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=10,
        socket_timeout=10,
    )

    try:
        pong = await redis_client.ping()
        if not pong:
            logger.error("redis_ping_failed")
            return 2
    except Exception as exc:
        logger.error("redis_connection_error", error=str(exc))
        return 2

    try:
        if tenant_id is not None:
            # Tenant-scoped pattern covers both versions
            from src.coherence.cache_invalidation import on_flag_flip

            if args.dry_run:
                from src.coherence.cache_keys import tenant_all_versions_prefix

                v1_prefix, v2_prefix = tenant_all_versions_prefix(tenant_id=tenant_id)
                c1 = await _dry_run(redis_client, v1_prefix)
                c2 = await _dry_run(redis_client, v2_prefix)
                total = c1 + c2
                logger.info(
                    "dry_run_complete",
                    tenant_id=str(tenant_id),
                    keys_found=total,
                )
            else:
                total = await on_flag_flip(redis_client, tenant_id=tenant_id)
                logger.info(
                    "purge_complete",
                    tenant_id=str(tenant_id),
                    keys_unlinked=total,
                )
        else:
            # Global purge of coherence:*
            from src.coherence.cache_invalidation import on_deploy

            if args.dry_run:
                total = await _dry_run(redis_client, "coherence:*")
                logger.info("dry_run_complete", pattern="coherence:*", keys_found=total)
            else:
                total = await on_deploy(redis_client)
                logger.info("purge_complete", pattern="coherence:*", keys_unlinked=total)

        return 0

    except Exception as exc:
        logger.error("purge_failed", error=str(exc))
        return 2

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
