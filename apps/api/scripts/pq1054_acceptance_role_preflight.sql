-- #1054 PRE-MIGRATION catalog preflight for c2pro_prod_acceptance_ro.
-- Run with psql as an owner-level role BEFORE migration. No anchor table is required.
-- Prints no row data and never prints the protected tenant id:
--   psql "$DSN" -f apps/api/scripts/pq1054_acceptance_role_preflight.sql
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

\echo '== 3. relations the role can read, and whether its approved RESTRICTIVE read policy binds it'
\echo '   (the anchor table itself is excluded: the role must read its own binding)'
\echo '   bound = pq1054_acceptance_tenant_bound (12 tenant relations) or'
\echo '           pq939_acceptance_project_readonly (9 project-only tables); any other relation aborts'
SELECT n.nspname, c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity,
       has_table_privilege('c2pro_prod_acceptance_ro', c.oid, 'SELECT') AS table_select,
       EXISTS (SELECT 1 FROM pg_policy p
                WHERE p.polrelid = c.oid AND NOT p.polpermissive
                  AND p.polcmd IN ('r', '*')
                  AND 'c2pro_prod_acceptance_ro'::regrole = ANY (p.polroles)
                  AND p.polname IN ('pq1054_acceptance_tenant_bound',
                                    'pq939_acceptance_project_readonly')) AS bound
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

\echo '== 5b. roles the role is a member of (expect none: aborts the migration)'
\echo '   inherited or reachable with SET ROLE, either way the policies bound TO the role stop applying'
SELECT g.rolname AS parent_role,
       pg_has_role('c2pro_prod_acceptance_ro', g.oid, 'USAGE') AS inherits_privileges
  FROM pg_roles g
 WHERE g.rolname <> 'c2pro_prod_acceptance_ro'
   AND pg_has_role('c2pro_prod_acceptance_ro', g.oid, 'MEMBER')
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

ROLLBACK;
