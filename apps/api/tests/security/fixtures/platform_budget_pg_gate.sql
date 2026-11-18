-- #1274 P0: run ONLY under pg_virtualenv with disposable PostgreSQL.
-- Source fixtures are synthetic; role creation + drops occur only in cluster's lifecycle.
\set ON_ERROR_STOP on
CREATE ROLE c2pro_platform_budget_reader NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE c2pro_budget_fixture_login LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE c2pro_customer_fixture_login LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT c2pro_platform_budget_reader TO c2pro_budget_fixture_login;
-- Disposable credentials, valid only while pg_virtualenv cluster exists.
ALTER ROLE c2pro_budget_fixture_login PASSWORD 'fixture-only-1274-pg16';
ALTER ROLE c2pro_customer_fixture_login PASSWORD 'fixture-only-1274-pg16';
\setenv PGPASSWORD fixture-only-1274-pg16

CREATE TABLE public.tenants (
  id uuid PRIMARY KEY, name text NOT NULL, slug text NOT NULL,
  is_active boolean NOT NULL, updated_at timestamptz NOT NULL,
  ai_budget_monthly numeric(16,6) NOT NULL,
  ai_spend_current numeric(16,6) NOT NULL,
  ai_spend_reserved_usd numeric(16,6) NOT NULL,
  private_notes text NOT NULL
);
CREATE TABLE public.n4_budget_buckets (
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  scope_kind text NOT NULL, scope_id uuid NOT NULL, period_key text NOT NULL,
  cap_usd numeric(16,6) NOT NULL, spent_usd numeric(16,6) NOT NULL,
  reserved_usd numeric(16,6) NOT NULL, internal_provider_key text NOT NULL,
  PRIMARY KEY (tenant_id, scope_kind, scope_id, period_key)
);
CREATE TABLE public.documents (id uuid PRIMARY KEY, tenant_id uuid, secret_text text NOT NULL);
INSERT INTO public.tenants VALUES
  ('00000000-0000-0000-0000-0000000000a1','Fixture EPC Alpha','alpha',true,now(),5,1,.5,'SYNTHETIC-SECRET-A'),
  ('00000000-0000-0000-0000-0000000000b2','Fixture EPC Beta','beta',true,now(),12,2,1,'SYNTHETIC-SECRET-B');
INSERT INTO public.n4_budget_buckets VALUES
  ('00000000-0000-0000-0000-0000000000a1','TENANT','00000000-0000-0000-0000-0000000000a1',to_char(now() AT TIME ZONE 'UTC','YYYY-MM'),5,1,.5,'SYNTHETIC-PROVIDER-A'),
  ('00000000-0000-0000-0000-0000000000b2','TENANT','00000000-0000-0000-0000-0000000000b2',to_char(now() AT TIME ZONE 'UTC','YYYY-MM'),12,2,1,'SYNTHETIC-PROVIDER-B');
INSERT INTO public.documents VALUES
  ('00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-0000000000a1','SYNTHETIC-DOC-NOT-DISCLOSABLE');
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE public.n4_budget_buckets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.n4_budget_buckets FORCE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_budget_tenants_read ON public.tenants
  FOR SELECT TO c2pro_platform_budget_reader USING (true);
CREATE POLICY platform_budget_buckets_read ON public.n4_budget_buckets
  FOR SELECT TO c2pro_platform_budget_reader USING (scope_kind='TENANT');
-- Synthetic customer principal bound to tenant A, no self-assertable GUC.
CREATE POLICY customer_own_tenant ON public.tenants
  FOR SELECT TO c2pro_customer_fixture_login
  USING (id='00000000-0000-0000-0000-0000000000a1');
CREATE POLICY customer_own_bucket ON public.n4_budget_buckets
  FOR SELECT TO c2pro_customer_fixture_login
  USING (tenant_id='00000000-0000-0000-0000-0000000000a1');
GRANT SELECT (id,name,slug,is_active,updated_at,ai_budget_monthly,ai_spend_current,ai_spend_reserved_usd)
 ON public.tenants TO c2pro_platform_budget_reader;
GRANT SELECT (tenant_id,scope_kind,scope_id,period_key,cap_usd,spent_usd,reserved_usd)
 ON public.n4_budget_buckets TO c2pro_platform_budget_reader;
GRANT SELECT (id,name,slug) ON public.tenants TO c2pro_customer_fixture_login;
GRANT SELECT (tenant_id,scope_kind,scope_id,period_key,cap_usd)
 ON public.n4_budget_buckets TO c2pro_customer_fixture_login;

\connect - c2pro_budget_fixture_login
DO $$
DECLARE n integer; denied boolean; p record;
BEGIN
  SELECT rolcanlogin AS canlogin,rolsuper AS su,rolbypassrls AS bypass,
         rolcreaterole AS cr,rolcreatedb AS cd,
         pg_has_role(current_user,'c2pro_platform_budget_reader','member') AS member,
         session_user=current_user AS equal_user
    INTO p FROM pg_roles WHERE rolname=current_user;
  IF NOT (p.canlogin AND NOT p.su AND NOT p.bypass AND NOT p.cr AND NOT p.cd AND p.member AND p.equal_user)
  THEN RAISE EXCEPTION 'FAIL unauthorized budget principal'; END IF;
  IF has_schema_privilege(current_user,'public','CREATE')
     OR has_database_privilege(current_user,current_database(),'CREATE')
     OR has_table_privilege(current_user,'public.tenants','INSERT,UPDATE,DELETE')
     OR has_table_privilege(current_user,'public.n4_budget_buckets','INSERT,UPDATE,DELETE')
  THEN RAISE EXCEPTION 'FAIL role has write/create'; END IF;
  IF NOT has_column_privilege(current_user,'public.tenants','ai_budget_monthly','SELECT')
     OR NOT has_column_privilege(current_user,'public.n4_budget_buckets','cap_usd','SELECT')
     OR has_column_privilege(current_user,'public.tenants','private_notes','SELECT')
     OR has_column_privilege(current_user,'public.n4_budget_buckets','internal_provider_key','SELECT')
     OR has_table_privilege(current_user,'public.documents','SELECT')
  THEN RAISE EXCEPTION 'FAIL incorrect column scope'; END IF;
  SELECT count(*) INTO n FROM public.tenants;
  IF n <> 2 THEN RAISE EXCEPTION 'FAIL platform cross-tenant read'; END IF;
  SELECT count(*) INTO n FROM public.n4_budget_buckets WHERE scope_kind='TENANT';
  IF n <> 2 THEN RAISE EXCEPTION 'FAIL budget bucket coverage'; END IF;
  denied:=false;
  BEGIN PERFORM private_notes FROM public.tenants; EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL private notes leak'; END IF;
  denied:=false;
  BEGIN PERFORM internal_provider_key FROM public.n4_budget_buckets; EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL provider secret leak'; END IF;
  denied:=false;
  BEGIN PERFORM secret_text FROM public.documents; EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL document leak'; END IF;
  denied:=false;
  BEGIN UPDATE public.tenants SET ai_budget_monthly=50 WHERE id='00000000-0000-0000-0000-0000000000a1';
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL tenant cap update allowed'; END IF;
  denied:=false;
  BEGIN UPDATE public.n4_budget_buckets SET cap_usd=50 WHERE tenant_id='00000000-0000-0000-0000-0000000000a1';
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL bucket cap update allowed'; END IF;
  denied:=false;
  BEGIN EXECUTE 'CREATE TABLE public.cap_escalation(x integer)';
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL schema CREATE allowed'; END IF;
  RAISE NOTICE 'PG_CAPABILITY_PASS: 2 synthetic tenants and buckets; confidential cols/docs/write/CREATE denied';
END $$;
\connect - c2pro_customer_fixture_login
DO $$
DECLARE n integer; denied boolean;
BEGIN
  SELECT count(*) INTO n FROM public.tenants;
  IF n<>1 THEN RAISE EXCEPTION 'FAIL customer tenant RLS'; END IF;
  SELECT count(*) INTO n FROM public.tenants WHERE id='00000000-0000-0000-0000-0000000000b2';
  IF n<>0 THEN RAISE EXCEPTION 'FAIL customer accessed second tenant'; END IF;
  SELECT count(*) INTO n FROM public.n4_budget_buckets WHERE tenant_id='00000000-0000-0000-0000-0000000000b2';
  IF n<>0 THEN RAISE EXCEPTION 'FAIL customer accessed second budget bucket'; END IF;
  IF pg_has_role(current_user,'c2pro_platform_budget_reader','member')
  THEN RAISE EXCEPTION 'FAIL customer gained platform role'; END IF;
  denied:=false;
  BEGIN PERFORM ai_budget_monthly FROM public.tenants;
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'FAIL customer read platform budget'; END IF;
  RAISE NOTICE 'PG_TENANT_ISOLATION_PASS: 1 own tenant only; no platform budget privilege';
END $$;
