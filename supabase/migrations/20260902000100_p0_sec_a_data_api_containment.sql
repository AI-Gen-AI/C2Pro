-- P0-SEC-A: contain external Supabase Data API access to the public schema.
--
-- GENERATED FILE -- DO NOT EDIT BY HAND.
-- Canonical source: apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py
-- Regenerate with:  python apps/api/scripts/generate_p0_sec_a_mirror.py
-- Parity is enforced by apps/api/tests/security/test_p0_sec_a_containment.py
--
-- Audit record: blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM anon, authenticated, PUBLIC;

REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM anon, authenticated, PUBLIC;

DROP POLICY IF EXISTS "checkpoints_select" ON public.checkpoints;

DROP POLICY IF EXISTS "checkpoint_blobs_select" ON public.checkpoint_blobs;

DROP POLICY IF EXISTS "checkpoint_writes_select" ON public.checkpoint_writes;

DROP POLICY IF EXISTS "checkpoint_migrations_select" ON public.checkpoint_migrations;

DO $$
            BEGIN
                IF to_regclass('public.evidence_claims') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.evidence_claims ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.evidence_extraction_events') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.evidence_extraction_events ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.category_centroids') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.category_centroids ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.project_snapshots_2026_06') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.project_snapshots_2026_06 ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.project_snapshots_2026_07') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.project_snapshots_2026_07 ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.project_snapshots_2026_08') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.project_snapshots_2026_08 ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
            BEGIN
                IF to_regclass('public.project_snapshots_default') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.project_snapshots_default ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;

DO $$
DECLARE
    rec record;
BEGIN
    -- Driven from pg_default_acl rather than a hard-coded owner list: the set of
    -- roles holding default privileges in `public` is environment-specific
    -- (production shows `postgres` and `supabase_admin`), and a fixed list
    -- silently misses any other owner, leaving the recurrence engine running for
    -- it. Selecting only entries that actually grant to an external role keeps
    -- this the minimal delta.
    FOR rec IN
        SELECT DISTINCT pg_get_userbyid(d.defaclrole) AS owner, d.defaclobjtype AS objtype
          FROM pg_default_acl d
          JOIN pg_namespace n ON n.oid = d.defaclnamespace
         WHERE n.nspname = 'public'
           AND d.defaclobjtype IN ('r', 'S')
           AND EXISTS (
               SELECT 1 FROM aclexplode(d.defaclacl) a
                WHERE a.grantee = 0
                   OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
           )
    LOOP
        IF NOT pg_has_role(current_user, rec.owner, 'USAGE') THEN
            RAISE NOTICE USING MESSAGE =
                'P0-SEC-A: skipped default privileges for role ' || rec.owner ||
                ' (migration role is not a member). Close it at platform level.';
            CONTINUE;
        END IF;
        IF rec.objtype = 'r' THEN
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public REVOKE ALL ON TABLES'
                    ' FROM anon, authenticated, PUBLIC';
        ELSE
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public REVOKE ALL ON SEQUENCES'
                    ' FROM anon, authenticated, PUBLIC';
        END IF;
    END LOOP;
END $$;
