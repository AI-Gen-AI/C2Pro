"""A downgrade must not use a tenant-filtered empty ledger as global evidence."""

from importlib import util
from pathlib import Path


def test_downgrade_fails_closed_when_migrator_cannot_see_all_tenant_events() -> None:
    file = (
        Path(__file__).resolve().parents[4]
        / "alembic/versions/20261008_0001_hitl_finding_decisions.py"
    )
    spec = util.spec_from_file_location("hitl_downgrade_rls_hardening", file)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = module.DOWNGRADE_STATEMENTS[0]
    assert "set_config('row_security', 'off', true)" in sql
    assert sql.index("set_config('row_security'") < sql.index("IF EXISTS")
    assert "SELECT 1 FROM public.hitl_finding_decisions" in sql
    assert "RAISE EXCEPTION" in sql
    assert "cannot downgrade populated" in sql
    # No privileged bypass, RLS disable or audit purge is an acceptable repair.
    assert "DISABLE ROW LEVEL SECURITY" not in sql
    assert "TRUNCATE" not in sql
    assert "DELETE FROM" not in sql
    assert module.down_revision == "20261007_0003"
