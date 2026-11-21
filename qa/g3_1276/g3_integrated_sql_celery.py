"""Exact-SHA 8a84f9ebcd54928347171cef0cc80f34ca3fb949 regression entrypoint.
Imports the shared unmodified G3 coverage, only mode differs.
Run exclusively under the guarded ephemeral PostgreSQL bootstrap.
"""
import asyncio
from g3_shared_sql_celery import run_g3

if __name__ == "__main__":
    asyncio.run(run_g3(manual_recovery=False))
