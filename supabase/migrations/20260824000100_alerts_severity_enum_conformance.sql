-- TASK-P0a-004: conform public.alerts.severity from character varying to the
-- alertseverity enum. Mirrors Alembic revision 20260824_0001 (authoritative).
--
-- Out-of-band production drift left alerts.severity as character varying(20)
-- while the canonical schema + ORM define it as the alertseverity enum, so the
-- ORM's ::alertseverity comparisons raised
-- "operator does not exist: character varying = alertseverity" (HTTP 500).
--
-- Guarded / idempotent: no-op when the column is already public.alertseverity
-- (fresh and CLI-applied databases land here); converts ONLY from the exact
-- diagnosed drift shape (character varying(20), NOT NULL, no default) — any other
-- varchar shape or type aborts rather than normalising an unapproved state;
-- requires the target enum to be public.alertseverity (schema-qualified) with
-- exactly the canonical labels {critical,high,medium,low}; rejects NULL/non-label
-- values before any DDL (single transaction => no partial mutation); bounds
-- lock_timeout; preserves NOT NULL / no-default; rebuilds ix_alerts_severity
-- automatically. The dependent security_invoker view public.v_project_alerts is
-- captured (definition + owner + grants), dropped, and recreated with its ACL and
-- owner restored EXACTLY as captured (privileges introduced by CREATE VIEW or
-- schema default privileges are stripped; a mismatch raises and rolls back).

DO $$
DECLARE
    v_udt            text;
    v_udt_schema     text;
    v_len            integer;
    v_nullable       text;
    v_default        text;
    v_labels         text[];
    v_bad            text;
    v_viewdef        text;
    v_owner          text;
    v_owner_after    text;
    v_grants         jsonb := '[]'::jsonb;
    v_grants_after   text;
    v_grants_expected text;
    v_has_view       boolean := false;
    r                record;
    g                jsonb;
BEGIN
    PERFORM set_config('lock_timeout', '5000', true);

    SELECT udt_name, udt_schema, character_maximum_length, is_nullable, column_default
      INTO v_udt, v_udt_schema, v_len, v_nullable, v_default
      FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    END IF;

    IF v_udt_schema = 'public' AND v_udt = 'alertseverity' THEN
        RAISE NOTICE 'alerts.severity already conforms to public.alertseverity; no-op';
        RETURN;
    END IF;

    IF v_udt <> 'varchar' THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %.%; expected character varying(20) or public.alertseverity',
            v_udt_schema, v_udt;
    END IF;
    IF v_len IS DISTINCT FROM 20 OR v_nullable <> 'NO' OR v_default IS NOT NULL THEN
        RAISE EXCEPTION
            'alerts.severity is character varying but not the diagnosed drift shape '
            '(length=%, is_nullable=%, default=%); expected varchar(20) NOT NULL with no default '
            '- aborting rather than normalising an unapproved state',
            v_len, v_nullable, v_default;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'alertseverity' AND t.typtype = 'e'
    ) THEN
        RAISE EXCEPTION 'public.alertseverity enum type is missing; cannot conform alerts.severity';
    END IF;
    SELECT array_agg(e.enumlabel ORDER BY e.enumlabel)
      INTO v_labels
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      JOIN pg_namespace n ON n.oid = t.typnamespace
     WHERE n.nspname = 'public' AND t.typname = 'alertseverity';
    IF v_labels IS DISTINCT FROM ARRAY['critical', 'high', 'low', 'medium'] THEN
        RAISE EXCEPTION
            'public.alertseverity labels % differ from the canonical set {critical,high,medium,low}',
            v_labels;
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

        FOR r IN
            SELECT DISTINCT grantee
              FROM information_schema.role_table_grants
             WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
        LOOP
            IF r.grantee = 'PUBLIC' THEN
                EXECUTE 'REVOKE ALL ON public.v_project_alerts FROM PUBLIC';
            ELSIF v_owner IS NULL OR r.grantee <> v_owner THEN
                EXECUTE format('REVOKE ALL ON public.v_project_alerts FROM %I', r.grantee);
            END IF;
        END LOOP;
        FOR g IN SELECT value FROM jsonb_array_elements(v_grants) LOOP
            EXECUTE format('GRANT %s ON public.v_project_alerts TO %s%s',
                g->>'priv',
                CASE WHEN g->>'grantee' = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(g->>'grantee') END,
                CASE WHEN g->>'grantable' = 'YES' THEN ' WITH GRANT OPTION' ELSE '' END);
        END LOOP;

        -- Non-owner grant parity (owner verified separately by identity below).
        SELECT string_agg(grantee || '|' || privilege_type || '|' || is_grantable, ','
                          ORDER BY grantee, privilege_type)
          INTO v_grants_after
          FROM information_schema.role_table_grants
         WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
           AND (v_owner IS NULL OR grantee <> v_owner);
        SELECT string_agg((value->>'grantee') || '|' || (value->>'priv') || '|' || (value->>'grantable'), ','
                          ORDER BY (value->>'grantee'), (value->>'priv'))
          INTO v_grants_expected
          FROM jsonb_array_elements(v_grants)
         WHERE (v_owner IS NULL OR (value->>'grantee') <> v_owner);
        IF v_grants_after IS DISTINCT FROM v_grants_expected THEN
            RAISE EXCEPTION 'v_project_alerts non-owner grant set changed on recreate; expected [%] got [%]',
                v_grants_expected, v_grants_after;
        END IF;

        SELECT pg_get_userbyid(relowner) INTO v_owner_after
          FROM pg_class WHERE oid = 'public.v_project_alerts'::regclass;
        IF v_owner_after IS DISTINCT FROM v_owner THEN
            RAISE EXCEPTION 'v_project_alerts owner changed on recreate; expected % got %',
                v_owner, v_owner_after;
        END IF;
    END IF;
END $$;
