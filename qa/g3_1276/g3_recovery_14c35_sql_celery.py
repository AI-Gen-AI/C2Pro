"""Exact-SHA 14c35b7f0b8933a4ff0b4f330f3941073809ff24 regression entrypoint.
Imports the shared unmodified G3 coverage, only mode differs.
Run exclusively under the guarded ephemeral PostgreSQL bootstrap.
"""
import asyncio
from g3_shared_sql_celery import run_g3

if __name__ == "__main__":
    asyncio.run(run_g3(manual_recovery=True))
