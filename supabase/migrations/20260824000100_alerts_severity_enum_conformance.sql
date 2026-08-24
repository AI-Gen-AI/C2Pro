-- TASK-P0a-004: conform public.alerts.severity from character varying to the
-- alertseverity enum. Mirrors Alembic revision 20260824_0001 (authoritative).
--
-- Out-of-band production drift left alerts.severity as character varying(20)
-- while the canonical schema + ORM define it as the alertseverity enum, so the
-- ORM's ::alertseverity comparisons raised
-- "operator does not exist: character varying = alertseverity" (HTTP 500).
--
-- Guarded / idempotent: no-op when the column is already alertseverity (fresh
-- and CLI-applied databases land here), converts only from character varying,
-- requires the enum to exist, rejects NULL/non-label values before any DDL
-- (single transaction => no partial mutation), bounds lock_timeout, preserves
-- NOT NULL / no-default, and rebuilds ix_alerts_severity automatically. The
-- dependent security_invoker view public.v_project_alerts is captured (definition
-- + owner + grants), dropped, and recreated with owner, grants and
-- security_invoker = true restored (privileges never silently tightened).

DO $$
DECLARE
    v_udt      text;
    v_bad      text;
    v_viewdef  text;
    v_owner    text;
    v_grants   jsonb := '[]'::jsonb;
    v_has_view boolean := false;
    g          jsonb;
BEGIN
    PERFORM set_config('lock_timeout', '5000', true);

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertseverity') THEN
        RAISE EXCEPTION 'alertseverity enum type is missing; cannot conform alerts.severity';
    END IF;

    SELECT udt_name INTO v_udt
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    ELSIF v_udt = 'alertseverity' THEN
        RAISE NOTICE 'alerts.severity already conforms to alertseverity; no-op';
        RETURN;
    ELSIF v_udt <> 'varchar' THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %; expected character varying or alertseverity', v_udt;
    END IF;

    IF EXISTS (SELECT 1 FROM public.alerts WHERE severity IS NULL) THEN
        RAISE EXCEPTION 'alerts.severity contains NULL values; cannot cast to a NOT NULL enum';
    END IF;
    SELECT string_agg(DISTINCT severity::text, ', ')
      INTO v_bad
      FROM public.alerts
     WHERE severity::text NOT IN ('critical', 'high', 'medium', 'low');
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'alerts.severity has values outside alertseverity labels: %', v_bad;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'v_project_alerts' AND c.relkind = 'v'
    ) THEN
        v_has_view := true;
        SELECT pg_get_viewdef('public.v_project_alerts'::regclass, true) INTO v_viewdef;
        SELECT pg_get_userbyid(c.relowner) INTO v_owner
          FROM pg_class c WHERE c.oid = 'public.v_project_alerts'::regclass;
        SELECT COALESCE(
                   jsonb_agg(jsonb_build_object(
                       'grantee', grantee, 'priv', privilege_type, 'grantable', is_grantable)),
                   '[]'::jsonb)
          INTO v_grants
          FROM information_schema.role_table_grants
         WHERE table_schema = 'public' AND table_name = 'v_project_alerts';
        DROP VIEW public.v_project_alerts;
    END IF;

    ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT;
    ALTER TABLE public.alerts
        ALTER COLUMN severity TYPE public.alertseverity
        USING severity::text::public.alertseverity;

    IF v_has_view THEN
        EXECUTE 'CREATE VIEW public.v_project_alerts AS ' || v_viewdef;
        IF v_owner IS NOT NULL THEN
            EXECUTE format('ALTER VIEW public.v_project_alerts OWNER TO %I', v_owner);
        END IF;
        EXECUTE 'ALTER VIEW public.v_project_alerts SET (security_invoker = true)';
        FOR g IN SELECT value FROM jsonb_array_elements(v_grants) LOOP
            EXECUTE format('GRANT %s ON public.v_project_alerts TO %s%s',
                g->>'priv',
                CASE WHEN g->>'grantee' = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(g->>'grantee') END,
                CASE WHEN g->>'grantable' = 'YES' THEN ' WITH GRANT OPTION' ELSE '' END);
        END LOOP;
    END IF;
END $$;
