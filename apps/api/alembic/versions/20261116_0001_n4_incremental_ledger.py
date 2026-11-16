"""C2Pro V4 WBS 2.2/2.5/2.6: isolated incremental N4 provenance and budget.

Revision ID: 20261116_0001
Revises: 20261104_0001

Additive only. No runtime switchover, no approved risks, no pilot writes.
Every table has FORCE RLS and public Data API roles are denied by default.
"""
from __future__ import annotations

from alembic import op

revision = "20261116_0001"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261116000100_n4_incremental_ledger.sql"

_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"

_UPGRADE_TABLES: tuple[str, ...] = (
    """
CREATE TABLE public.n4_extraction_runs (
    run_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    document_revision_id uuid NOT NULL,
    source_sha256 char(64) NOT NULL,
    config_sha256 char(64) NOT NULL,
    generation bigint NOT NULL,
    fencing_token bigint NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'PREPARING',
    total_windows integer NOT NULL,
    budget_cap_usd numeric(16,6) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_n4_runs_tenant_run UNIQUE (tenant_id, run_id),
    CONSTRAINT uq_n4_runs_identity UNIQUE
        (tenant_id, document_revision_id, source_sha256, config_sha256, generation),
    CONSTRAINT fk_n4_runs_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE NO ACTION,
    CONSTRAINT fk_n4_runs_revision FOREIGN KEY
        (document_revision_id, document_id, project_id, tenant_id)
        REFERENCES public.document_revisions
        (revision_id, document_id, project_id, tenant_id) ON DELETE NO ACTION,
    CONSTRAINT ck_n4_runs_sha CHECK
        (source_sha256 ~ '^[a-f0-9]{64}$' AND config_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT ck_n4_runs_generation CHECK (generation > 0 AND fencing_token >= 0),
    CONSTRAINT ck_n4_runs_windows CHECK (total_windows > 0),
    CONSTRAINT ck_n4_runs_budget CHECK (budget_cap_usd > 0),
    CONSTRAINT ck_n4_runs_status CHECK (status IN
        ('PREPARING','RUNNING','PARTIAL','BLOCKED','FAILED','COMPLETE'))
)""",
    """
CREATE TABLE public.n4_extraction_windows (
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    ordinal integer NOT NULL,
    core_start integer NOT NULL,
    core_end integer NOT NULL,
    context_start integer NOT NULL,
    context_end integer NOT NULL,
    context_sha256 char(64) NOT NULL,
    findings_sha256 char(64) NULL,
    status varchar(16) NOT NULL DEFAULT 'PENDING',
    committed_at timestamptz NULL,
    PRIMARY KEY (tenant_id, run_id, ordinal),
    CONSTRAINT fk_n4_windows_run FOREIGN KEY (tenant_id, run_id)
        REFERENCES public.n4_extraction_runs (tenant_id, run_id) ON DELETE CASCADE,
    CONSTRAINT ck_n4_windows_bounds CHECK
        (ordinal >= 0 AND context_start >= 0 AND core_start >= context_start
         AND core_end > core_start AND context_end >= core_end),
    CONSTRAINT ck_n4_windows_sha CHECK
        (context_sha256 ~ '^[a-f0-9]{64}$'
         AND (findings_sha256 IS NULL OR findings_sha256 ~ '^[a-f0-9]{64}$')),
    CONSTRAINT ck_n4_windows_result CHECK
        (status <> 'EXAMINED' OR findings_sha256 IS NOT NULL),
    CONSTRAINT ck_n4_windows_status CHECK (status IN
        ('PENDING','CLAIMED','EXAMINED','FAILED','BLOCKED'))
)""",
    """
CREATE TABLE public.n4_candidate_findings (
    finding_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    window_ordinal integer NOT NULL,
    finding_key char(64) NOT NULL,
    source_refs jsonb NOT NULL,
    claim jsonb NOT NULL,
    candidate_state varchar(16) NOT NULL DEFAULT 'PROPOSED',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_n4_finding_tenant_id UNIQUE (tenant_id, finding_id),
    CONSTRAINT uq_n4_finding_dedupe UNIQUE (tenant_id, run_id, finding_key),
    CONSTRAINT fk_n4_findings_window FOREIGN KEY
        (tenant_id, run_id, window_ordinal)
        REFERENCES public.n4_extraction_windows (tenant_id, run_id, ordinal)
        ON DELETE CASCADE,
    CONSTRAINT ck_n4_finding_key CHECK (finding_key ~ '^[a-f0-9]{64}$'),
    CONSTRAINT ck_n4_finding_source CHECK (jsonb_typeof(source_refs) = 'array'),
    CONSTRAINT ck_n4_finding_claim CHECK (jsonb_typeof(claim) = 'object'),
    CONSTRAINT ck_n4_candidate_proposed CHECK (candidate_state = 'PROPOSED')
)""",
    """
CREATE TABLE public.n4_budget_buckets (
    tenant_id uuid NOT NULL,
    scope_kind varchar(16) NOT NULL,
    scope_id uuid NOT NULL,
    period_key varchar(16) NOT NULL,
    cap_usd numeric(16,6) NOT NULL,
    reserved_usd numeric(16,6) NOT NULL DEFAULT 0,
    spent_usd numeric(16,6) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, scope_kind, scope_id, period_key),
    CONSTRAINT ck_n4_budget_scope CHECK
        (scope_kind IN ('TENANT','PROJECT','DOCUMENT','RUN')),
    CONSTRAINT ck_n4_budget_period CHECK (length(btrim(period_key)) > 0),
    CONSTRAINT ck_n4_budget_nonnegative CHECK
        (cap_usd > 0 AND reserved_usd >= 0 AND spent_usd >= 0)
)""",
    """
CREATE TABLE public.n4_usage_reservations (
    reservation_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    window_ordinal integer NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    bucket_scopes jsonb NOT NULL,
    reserved_usd numeric(16,6) NOT NULL,
    spent_usd numeric(16,6) NULL,
    status varchar(16) NOT NULL DEFAULT 'RESERVED',
    model_name varchar(120) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    settled_at timestamptz NULL,
    CONSTRAINT uq_n4_usage_tenant_id UNIQUE (tenant_id, reservation_id),
    CONSTRAINT uq_n4_usage_idempotency UNIQUE (tenant_id, run_id, idempotency_key),
    CONSTRAINT fk_n4_usage_window FOREIGN KEY
        (tenant_id, run_id, window_ordinal)
        REFERENCES public.n4_extraction_windows (tenant_id, run_id, ordinal)
        ON DELETE RESTRICT,
    CONSTRAINT ck_n4_usage_status CHECK
        (status IN ('RESERVED','SETTLED','UNKNOWN','CANCELED')),
    CONSTRAINT ck_n4_usage_amount CHECK
        (reserved_usd > 0 AND (spent_usd IS NULL OR spent_usd >= 0)),
    CONSTRAINT ck_n4_usage_scopes CHECK
        (jsonb_typeof(bucket_scopes) = 'array'
         AND jsonb_array_length(bucket_scopes) = 4),
    CONSTRAINT ck_n4_usage_settled CHECK
        ((status = 'SETTLED') = (spent_usd IS NOT NULL))
)""",
)

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX ix_n4_runs_project ON public.n4_extraction_runs "
    "(tenant_id, project_id, document_id, created_at DESC)",
    "CREATE INDEX ix_n4_windows_status ON public.n4_extraction_windows "
    "(tenant_id, run_id, status)",
    "CREATE INDEX ix_n4_findings_run ON public.n4_candidate_findings "
    "(tenant_id, run_id, window_ordinal)",
    "CREATE INDEX ix_n4_usage_run_status ON public.n4_usage_reservations "
    "(tenant_id, run_id, status)",
)

TABLES = (
    "n4_extraction_runs",
    "n4_extraction_windows",
    "n4_candidate_findings",
    "n4_budget_buckets",
    "n4_usage_reservations",
)


def _rls_statements() -> tuple[str, ...]:
    statements: list[str] = []
    for table in TABLES:
        qname = f"public.{table}"
        statements.extend((
            f"ALTER TABLE {qname} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {qname} FORCE ROW LEVEL SECURITY",
            f"CREATE POLICY n4_{table}_select ON {qname} FOR SELECT USING ({_TENANT})",
            f"CREATE POLICY n4_{table}_insert ON {qname} FOR INSERT WITH CHECK ({_TENANT})",
        ))
        if table != "n4_candidate_findings":
            statements.append(
                f"CREATE POLICY n4_{table}_update ON {qname} "
                f"FOR UPDATE USING ({_TENANT}) WITH CHECK ({_TENANT})"
            )
        statements.append(f"REVOKE ALL ON TABLE {qname} FROM PUBLIC")
    return tuple(statements)


REVOKE_EXPOSED_ROLES = """
DO $do$
DECLARE r text; t text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            FOREACH t IN ARRAY ARRAY[
                'n4_extraction_runs','n4_extraction_windows',
                'n4_candidate_findings','n4_budget_buckets','n4_usage_reservations'
            ] LOOP
                EXECUTE 'REVOKE ALL ON TABLE public.' || quote_ident(t) ||
                        ' FROM ' || quote_ident(r);
            END LOOP;
        END IF;
    END LOOP;
END $do$
"""

UPGRADE_STATEMENTS = _UPGRADE_TABLES + INDEX_STATEMENTS + _rls_statements() + (REVOKE_EXPOSED_ROLES,)


def supabase_sql() -> str:
    header = (
        "-- C2Pro V4 WBS2.2/2.5/2.6 incremental N4 ledger; additive, no runtime activation.\n"
        "-- Mirror of apps/api/alembic/versions/20261116_0001_n4_incremental_ledger.py.\n"
    )
    return header + "\n" + "\n\n".join(x.strip() + ";" for x in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for sql in UPGRADE_STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    # Fail closed: never discard funded attempts, candidate provenance or any
    # completed window during downgrade, even if only a different tenant's
    # rows exist. Use an owner/migrator role, never a tenant-filtered view.
    for table in reversed(TABLES):
        op.execute(
            f"DO $do$ BEGIN "
            f"PERFORM set_config('row_security','off',true); "
            f"IF EXISTS (SELECT 1 FROM public.{table} LIMIT 1) THEN "
            f"RAISE EXCEPTION 'Cannot downgrade populated N4 ledger: {table}'; "
            f"END IF; END $do$"
        )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")
