"""C3a: wherever ClauseORM is mapped, its revision FK target is mapped too (TS-UT-C3A-ORM-001).

``clauses (revision_id, document_id, tenant_id)`` references ``document_revisions``.
A process that imports the documents models -- or calls ``init_db`` -- without the
temporal models must still be able to configure the mappers; otherwise the first
ORM query (e.g. the E2E seed's ``db.get(Tenant, ...)``) raises
``NoReferencedTableError``. Each check runs in a clean interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3]


def _run(code: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "ENVIRONMENT": "test",
        "JWT_SECRET_KEY": "test-secret-key-min-32-chars-required-for-testing-purposes-only",
    }
    return subprocess.run(
        [sys.executable, "-c", code], cwd=API_ROOT, env=env, capture_output=True, text=True,
        timeout=120, check=False,
    )


def test_importing_the_clause_model_registers_its_revision_fk_target() -> None:
    result = _run(
        "from src.documents.adapters.persistence.models import ClauseORM\n"
        "from src.core.database import Base\n"
        "assert 'document_revisions' in Base.metadata.tables\n"
        "print('ok')\n"
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_init_db_model_registry_configures_mappers() -> None:
    result = _run(
        "import asyncio\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "from src.core.database import close_db, init_db\n"
        "async def main():\n"
        "    await init_db()\n"
        "    try:\n"
        "        configure_mappers()\n"
        "    finally:\n"
        "        await close_db()\n"
        "asyncio.run(main())\n"
        "print('ok')\n"
    )
    assert result.returncode == 0, result.stderr[-2000:]
