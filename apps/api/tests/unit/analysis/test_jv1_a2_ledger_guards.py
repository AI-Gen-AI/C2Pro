"""JV1-A2 ledger guards that need no database (run in the unit CI job).

* ``retryable_windows`` rejects an invalid ``max_attempts`` before any query.
* L1-owned PostgreSQL fixtures take the budget period from the PostgreSQL
  clock (the only month ``reserve_call`` accepts) instead of a hard-coded
  month that would turn the suites red when the month changes.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.n4_incremental_store import retryable_windows

API = Path(__file__).resolve().parents[3]
STORE = API / "src/analysis/adapters/persistence/n4_incremental_store.py"
PG = API / "tests/integration/analysis"
# Test files owned by L1 (store/runner); other owners' suites are reported to L0.
L1_PG_FILES = (
    "test_n4_ledger_retries_pg.py",
    "test_n4_incremental_store_pg.py",
    "test_n4_window_runner_pg.py",
    "test_n4_inherit_budget_scopes_pg.py",
    "test_v41_n4_recovery_progress_ops_pg.py",
)
DB_MONTH_SQL = "to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM')"
# A deliberately PAST month used only to prove a stale period is refused.
STALE_MONTH_ALLOWED = {"2025-11"}
_MONTH_LITERAL = re.compile(r"""['"](20\d\d-\d\d)['"]""")


@pytest.mark.parametrize("bad", [0, -1, True, "3", 1.5, None])
async def test_retryable_windows_rejects_invalid_max_attempts(bad):
    with pytest.raises(ValueError, match="max_attempts"):
        await retryable_windows(None, tenant_id=uuid4(), run_id=uuid4(), max_attempts=bad)


@pytest.mark.parametrize("name", L1_PG_FILES)
def test_l1_pg_fixtures_have_no_hard_coded_budget_month(name):
    months = set(_MONTH_LITERAL.findall((PG / name).read_text(encoding="utf-8")))
    assert months <= STALE_MONTH_ALLOWED, f"{name} hard-codes {sorted(months)}"


def test_period_helper_uses_the_same_db_clock_as_reserve_call():
    assert DB_MONTH_SQL in STORE.read_text(encoding="utf-8")
    helper = (PG / "test_n4_incremental_store_pg.py").read_text(encoding="utf-8")
    assert DB_MONTH_SQL in helper
    assert "def _db_period(" in helper
