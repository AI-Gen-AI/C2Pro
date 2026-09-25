"""Convert analyses.status and alerts.status from varchar to their enum types.

Revision ID: 20260814_0001
Revises: 20260813_0001
Create Date: 2026-08-13

The ORM maps these via SQLEnum(AnalysisStatus) / SQLEnum(AlertStatus), so queries
cast the parameter to ::analysisstatus / ::alertstatus. The DB columns were
character varying, so every status filter failed with:

    operator does not exist: character varying = analysisstatus   (HTTP 500)

which broke the analysis/coherence stream and the alerts flow. Three
security_invoker RLS views depend on these columns (v_coherence_breakdown,
v_project_alerts, v_project_summary), so they are captured, dropped, and
recreated (re-applying security_invoker) around the ALTERs.

Idempotent: no-op when already converted (applied directly to the shared DB).
Both tables were empty at migration time.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0001"
down_revision: str | None = "20260813_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MIGRATE_SQL = """
DO $$
DECLARE d_coh text; d_ale text; d_sum text;
BEGIN
  IF (SELECT udt_name FROM information_schema.columns
      WHERE table_name = 'analyses' AND column_name = 'status') = 'analysisstatus' THEN
    RETURN;  -- already converted
  END IF;
  SELECT pg_get_viewdef('v_coherence_breakdown'::regclass, true) INTO d_coh;
  SELECT pg_get_viewdef('v_project_alerts'::regclass, true) INTO d_ale;
  SELECT pg_get_viewdef('v_project_summary'::regclass, true) INTO d_sum;
  DROP VIEW v_project_summary;
  DROP VIEW v_project_alerts;
  DROP VIEW v_coherence_breakdown;
  ALTER TABLE analyses ALTER COLUMN status DROP DEFAULT;
  ALTER TABLE analyses ALTER COLUMN status TYPE analysisstatus USING status::analysisstatus;
  ALTER TABLE alerts ALTER COLUMN status DROP DEFAULT;
  ALTER TABLE alerts ALTER COLUMN status TYPE alertstatus USING status::alertstatus;
  EXECUTE 'CREATE VIEW v_coherence_breakdown AS ' || d_coh;
  EXECUTE 'ALTER VIEW v_coherence_breakdown SET (security_invoker = true)';
  EXECUTE 'CREATE VIEW v_project_alerts AS ' || d_ale;
  EXECUTE 'ALTER VIEW v_project_alerts SET (security_invoker = true)';
  EXECUTE 'CREATE VIEW v_project_summary AS ' || d_sum;
  EXECUTE 'ALTER VIEW v_project_summary SET (security_invoker = true)';
END $$;
"""


def upgrade() -> None:
    op.get_bind().execute(sa.text(_MIGRATE_SQL))


def downgrade() -> None:
    # Intentionally irreversible: reverting enum -> varchar is not required and the
    # extra values are harmless.
    pass
