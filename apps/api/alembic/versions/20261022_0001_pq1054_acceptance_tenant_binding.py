"""#1054: bind the production acceptance read role to one tenant and project.

Revision ID: 20261022_0001
Revises: 20261017_0001

The twelve tenant relations readable by c2pro_prod_acceptance_ro only checked
the caller-settable app.current_tenant GUC, so the role could read any tenant
by changing it. This adds, for that role alone, a RESTRICTIVE SELECT policy
on each relation bound to an owner-only anchor row. Restrictive policies AND
with the existing permissive tenant RLS: the GUC can now only narrow what the
role sees, never widen it. Without an anchor row the role reads nothing.

The synthetic tenant id is a protected secret, so the anchor row is inserted
by an owner-authorized step, not by this migration. No RLS policy is relaxed,
no grant is widened and no row is read or written by the migration.
"""

from __future__ import annotations

from alembic import op

revision = "20261022_0001"
down_revision = "20261017_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261022000100_pq1054_acceptance_tenant_binding.sql"
ROLE = "c2pro_prod_acceptance_ro"
POLICY = "pq1054_acceptance_tenant_bound"
APPROVED_PROJECT = "e7c6031f-cd9e-4642-a5ea-35a0207ceaeb"
# relation -> how its rows are bound to the anchored tenant and project.
TENANT_RELATIONS: dict[str, str] = {
    "tenants": "tenant_root",
    "projects": "project_root",
    "documents": "tenant_project",
    "document_revisions": "tenant_project",
    "document_artifacts": "tenant_project",
    "clauses": "tenant_project",
    "project_events": "tenant_project",
    "analyses": "tenant_project",
    "document_chunks": "tenant_project",
    "project_snapshots": "tenant_project",
    "review_items": "tenant_project",
    "document_processing_operations": "tenant_document",
}

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS c2pro_security"
REVOKE_SCHEMA_SQL = "REVOKE ALL ON SCHEMA c2pro_security FROM PUBLIC"
CREATE_ANCHOR_SQL = """CREATE TABLE IF NOT EXISTS c2pro_security.acceptance_tenant_binding (
    role_name name PRIMARY KEY
        CHECK (role_name = 'c2pro_prod_acceptance_ro'),
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL
        CHECK (project_id = 'e7c6031f-cd9e-4642-a5ea-35a0207ceaeb'::uuid),
    bound_at timestamptz NOT NULL DEFAULT now(),
    bound_by text NOT NULL CHECK (length(bound_by) > 0)
)
"""
REVOKE_ANCHOR_SQL = (
    "REVOKE ALL ON TABLE c2pro_security.acceptance_tenant_binding FROM PUBLIC"
)

BIND_SQL = """DO $pq1054$
DECLARE
    scoped record;
    relation_oid oid;
    role_oid oid;
    anchored_tenant text := '(SELECT b.tenant_id FROM '
        'c2pro_security.acceptance_tenant_binding b '
        'WHERE b.role_name = ''c2pro_prod_acceptance_ro'')';
    anchored_project text := '(SELECT b.project_id FROM '
        'c2pro_security.acceptance_tenant_binding b '
        'WHERE b.role_name = ''c2pro_prod_acceptance_ro'')';
    predicate text;
    required_columns name[];
    offenders text;
BEGIN
    -- Ephemeral CI databases deliberately omit the protected account.
    SELECT oid INTO role_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'c2pro_prod_acceptance_ro';
    IF role_oid IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles
         WHERE oid = role_oid
           AND rolcanlogin
           AND NOT rolsuper
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_GUARD_FAILED';
    END IF;

    -- RESTRICTIVE policies TO this role also bind every role that inherits
    -- its privileges. Refuse an RLS-subject inheriting member rather than
    -- silently confining (or exposing) an unrelated principal. A creator's
    -- ADMIN-only membership (PG16+, INHERIT FALSE) does not inherit and passes.
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS member
         WHERE member.oid <> role_oid
           AND NOT member.rolsuper
           AND NOT member.rolbypassrls
           AND pg_catalog.pg_has_role(member.oid, role_oid, 'USAGE')
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_MEMBERSHIP_GUARD_FAILED';
    END IF;

    -- An owner bypasses non-FORCE RLS entirely.
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class WHERE relowner = role_oid
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_OWNS_RELATION';
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA c2pro_security TO c2pro_prod_acceptance_ro';
    EXECUTE 'GRANT SELECT ON TABLE c2pro_security.acceptance_tenant_binding '
            'TO c2pro_prod_acceptance_ro';

    FOR scoped IN
        SELECT v.table_name, v.mode
          FROM (VALUES
            ('tenants', 'tenant_root'),
            ('projects', 'project_root'),
            ('documents', 'tenant_project'),
            ('document_revisions', 'tenant_project'),
            ('document_artifacts', 'tenant_project'),
            ('clauses', 'tenant_project'),
            ('project_events', 'tenant_project'),
            ('analyses', 'tenant_project'),
            ('document_chunks', 'tenant_project'),
            ('project_snapshots', 'tenant_project'),
            ('review_items', 'tenant_project'),
            ('document_processing_operations', 'tenant_document')
          ) AS v(table_name, mode)
    LOOP
        relation_oid := NULL;
        SELECT c.oid
          INTO relation_oid
          FROM pg_catalog.pg_class AS c
          JOIN pg_catalog.pg_namespace AS ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public'
           AND c.relname = scoped.table_name
           AND c.relkind IN ('r', 'p')
           AND c.relrowsecurity;

        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'PQ1054_REQUIRED_RLS_TABLE_GUARD_FAILED: %',
                scoped.table_name;
        END IF;

        required_columns := CASE scoped.mode
            WHEN 'tenant_root' THEN ARRAY['id']
            WHEN 'project_root' THEN ARRAY['id', 'tenant_id']
            WHEN 'tenant_project' THEN ARRAY['tenant_id', 'project_id']
            ELSE ARRAY['tenant_id', 'document_id']
        END;
        IF (
            SELECT count(*)
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
               AND attname = ANY (required_columns)
        ) <> cardinality(required_columns) THEN
            RAISE EXCEPTION 'PQ1054_REQUIRED_COLUMN_GUARD_FAILED: %',
                scoped.table_name;
        END IF;

        IF scoped.mode = 'tenant_root' THEN
            predicate := format('id = %s', anchored_tenant);
        ELSIF scoped.mode = 'project_root' THEN
            predicate := format(
                'id = %s AND tenant_id = %s', anchored_project, anchored_tenant
            );
        ELSIF scoped.mode = 'tenant_project' THEN
            predicate := format(
                'tenant_id = %s AND project_id = %s',
                anchored_tenant, anchored_project
            );
        ELSE
            predicate := format(
                'tenant_id = %s AND document_id IN (SELECT d.id FROM '
                'public.documents d WHERE d.project_id = %s)',
                anchored_tenant, anchored_project
            );
        END IF;

        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR SELECT TO %I '
            'USING (%s)',
            'pq1054_acceptance_tenant_bound',
            scoped.table_name,
            'c2pro_prod_acceptance_ro',
            predicate
        );
    END LOOP;

    -- Post-condition: every relation the role can read, by table or column
    -- grant and directly or by inheritance, must be RLS-protected with a
    -- RESTRICTIVE read policy for this role. Definer-rights views,
    -- materialized views and foreign tables bypass the caller's RLS.
    SELECT string_agg(format('%I.%I', ns.nspname, c.relname), ', ')
      INTO offenders
      FROM pg_catalog.pg_class AS c
      JOIN pg_catalog.pg_namespace AS ns ON ns.oid = c.relnamespace
     WHERE ns.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
       AND NOT (ns.nspname = 'c2pro_security'
                AND c.relname = 'acceptance_tenant_binding')
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND (pg_catalog.has_table_privilege(role_oid, c.oid, 'SELECT')
            OR pg_catalog.has_any_column_privilege(role_oid, c.oid, 'SELECT'))
       AND (c.relkind IN ('v', 'm', 'f')
            OR NOT c.relrowsecurity
            OR NOT EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_policy AS p
                 WHERE p.polrelid = c.oid
                   AND NOT p.polpermissive
                   AND p.polcmd IN ('r', '*')
                   AND role_oid = ANY (p.polroles)));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'PQ1054_UNBOUND_READABLE_RELATIONS: %', offenders;
    END IF;
END
$pq1054$
"""

UNBIND_SQL = """DO $pq1054$
DECLARE
    scoped record;
BEGIN
    FOR scoped IN
        SELECT v.table_name
          FROM (VALUES
            ('tenants'),
            ('projects'),
            ('documents'),
            ('document_revisions'),
            ('document_artifacts'),
            ('clauses'),
            ('project_events'),
            ('analyses'),
            ('document_chunks'),
            ('project_snapshots'),
            ('review_items'),
            ('document_processing_operations')
          ) AS v(table_name)
    LOOP
        IF to_regclass(format('public.%I', scoped.table_name)) IS NOT NULL THEN
            EXECUTE format(
                'DROP POLICY IF EXISTS %I ON public.%I',
                'pq1054_acceptance_tenant_bound',
                scoped.table_name
            );
        END IF;
    END LOOP;
END
$pq1054$
"""

DROP_ANCHOR_SQL = "DROP TABLE IF EXISTS c2pro_security.acceptance_tenant_binding"
DROP_SCHEMA_SQL = "DROP SCHEMA IF EXISTS c2pro_security"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    CREATE_SCHEMA_SQL,
    REVOKE_SCHEMA_SQL,
    CREATE_ANCHOR_SQL,
    REVOKE_ANCHOR_SQL,
    BIND_SQL,
)
DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    UNBIND_SQL,
    DROP_ANCHOR_SQL,
    DROP_SCHEMA_SQL,
)


def supabase_sql() -> str:
    header = (
        "-- #1054: bind the production acceptance read role to one tenant and project.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261022_0001_pq1054_acceptance_tenant_binding.py.\n"
    )
    return header + "\n" + "\n\n".join(
        statement.strip() + ";" for statement in UPGRADE_STATEMENTS
    ) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
