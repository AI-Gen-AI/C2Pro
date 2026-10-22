-- #1054 read-only preflight/verification for c2pro_prod_acceptance_ro.
-- Run with psql as an owner-level role; it reads only catalogs and the anchor.
-- Prints no row data and never prints the protected tenant id:
--   psql "$DSN" -v expected_tenant="$PROD_ACCEPTANCE_EXPECTED_TENANT_ID" \
--        -f apps/api/scripts/pq1054_acceptance_role_preflight.sql
\set ON_ERROR_STOP on
BEGIN READ ONLY;

\echo '== 1. role attributes (expect login, not super, not bypassrls)'
SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolinherit
  FROM pg_roles WHERE rolname = 'c2pro_prod_acceptance_ro';

\echo '== 2. members of the role (an RLS-subject member that inherits aborts the migration)'
SELECT m.rolname AS member, m.rolsuper, m.rolbypassrls,
       pg_has_role(m.oid, 'c2pro_prod_acceptance_ro', 'USAGE') AS inherits_privileges,
       pg_has_role(m.oid, 'c2pro_prod_acceptance_ro', 'MEMBER') AS is_member
  FROM pg_auth_members am
  JOIN pg_roles m ON m.oid = am.member
 WHERE am.roleid = 'c2pro_prod_acceptance_ro'::regrole;

\echo '== 3. relations the role can read, and whether a RESTRICTIVE read policy binds it'
\echo '   (the anchor table itself is excluded: the role must read its own binding)'
SELECT n.nspname, c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity,
       has_table_privilege('c2pro_prod_acceptance_ro', c.oid, 'SELECT') AS table_select,
       EXISTS (SELECT 1 FROM pg_policy p
                WHERE p.polrelid = c.oid AND NOT p.polpermissive
                  AND p.polcmd IN ('r', '*')
                  AND 'c2pro_prod_acceptance_ro'::regrole = ANY (p.polroles)) AS bound
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
   AND NOT (n.nspname = 'c2pro_security' AND c.relname = 'acceptance_tenant_binding')
   AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
   AND (has_table_privilege('c2pro_prod_acceptance_ro', c.oid, 'SELECT')
        OR has_any_column_privilege('c2pro_prod_acceptance_ro', c.oid, 'SELECT'))
 ORDER BY 1, 2;

\echo '== 4. relations owned by the role (expect none)'
SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relowner = 'c2pro_prod_acceptance_ro'::regrole;

\echo '== 5. SECURITY DEFINER functions the role may call (expect none: aborts the migration)'
SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS args,
       pg_get_userbyid(p.proowner) AS owner
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE p.prosecdef
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
   AND has_function_privilege('c2pro_prod_acceptance_ro', p.oid, 'EXECUTE')
   AND has_schema_privilege('c2pro_prod_acceptance_ro', n.oid, 'USAGE')
 ORDER BY 1, 2;

\echo '== 5b. roles whose privileges the role inherits (their grants count as its own)'
SELECT g.rolname AS inherited_role
  FROM pg_roles g
 WHERE g.rolname <> 'c2pro_prod_acceptance_ro'
   AND pg_has_role('c2pro_prod_acceptance_ro', g.oid, 'USAGE')
 ORDER BY 1;

\echo '== 5c. default privileges granting future tables to the role (expect none: aborts the migration)'
SELECT coalesce(n.nspname, '*') AS schema, pg_get_userbyid(d.defaclrole) AS creator,
       CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee
  FROM pg_default_acl d
  LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
 CROSS JOIN LATERAL aclexplode(d.defaclacl) a
 WHERE d.defaclobjtype = 'r' AND a.privilege_type = 'SELECT'
   AND (a.grantee = 0 OR pg_has_role('c2pro_prod_acceptance_ro', a.grantee, 'USAGE'))
 ORDER BY 1, 2, 3;

\echo '== 6. anchor row (expect exactly one, matching the expected tenant and approved project)'
SELECT count(*) AS anchor_rows,
       bool_and(tenant_id::text = :'expected_tenant') AS tenant_matches,
       bool_and(project_id = 'e7c6031f-cd9e-4642-a5ea-35a0207ceaeb'::uuid) AS project_matches,
       bool_and(EXISTS (SELECT 1 FROM public.projects p
                         WHERE p.id = b.project_id AND p.tenant_id = b.tenant_id)) AS project_in_tenant
  FROM c2pro_security.acceptance_tenant_binding b;

ROLLBACK;
