-- =====================================================
-- Migration: create_tenant_and_owner RPC
-- Date: 2026-01-14
-- Notes: backend-only tenant creation via service_role
-- =====================================================

CREATE OR REPLACE FUNCTION public.create_tenant_and_owner(
    p_tenant_name text,
    p_tenant_slug text,
    p_owner_id uuid
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
SET row_security = off
AS $$
DECLARE
    v_tenant_id uuid;
    v_email text;
    v_first_name text;
    v_last_name text;
BEGIN

    IF p_owner_id IS NULL THEN
        RAISE EXCEPTION 'Owner id is required';
    END IF;

    IF p_tenant_name IS NULL OR length(trim(p_tenant_name)) = 0 THEN
        RAISE EXCEPTION 'Invalid tenant name';
    END IF;

    IF p_tenant_slug IS NULL OR p_tenant_slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$' THEN
        RAISE EXCEPTION 'Invalid tenant slug';
    END IF;

    IF EXISTS (SELECT 1 FROM public.tenants WHERE slug = p_tenant_slug) THEN
        RAISE EXCEPTION 'Tenant slug already exists: %', p_tenant_slug;
    END IF;

    IF auth.role() <> 'service_role' THEN
        RAISE EXCEPTION 'Only service_role can create tenants';
    END IF;

    SELECT u.email,
           u.raw_user_meta_data ->> 'first_name',
           u.raw_user_meta_data ->> 'last_name'
      INTO v_email, v_first_name, v_last_name
      FROM auth.users u
     WHERE u.id = p_owner_id;

    IF v_email IS NULL THEN
        RAISE EXCEPTION 'Owner user not found: %', p_owner_id;
    END IF;

    INSERT INTO public.tenants (name, slug)
    VALUES (p_tenant_name, p_tenant_slug)
    RETURNING id INTO v_tenant_id;

    INSERT INTO public.users (
        id,
        tenant_id,
        email,
        first_name,
        last_name,
        role,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        p_owner_id,
        v_tenant_id,
        v_email,
        v_first_name,
        v_last_name,
        'owner',
        true,
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE
    SET tenant_id = EXCLUDED.tenant_id,
        email = EXCLUDED.email,
        first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        role = 'owner',
        is_active = true,
        updated_at = NOW();

    RETURN v_tenant_id;
END;
$$;

COMMENT ON FUNCTION public.create_tenant_and_owner(text, text, uuid)
    IS 'Backend-only RPC: create tenant and assign owner in public.users (service_role only).';

REVOKE ALL ON FUNCTION public.create_tenant_and_owner(text, text, uuid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.create_tenant_and_owner(text, text, uuid) FROM anon;
REVOKE EXECUTE ON FUNCTION public.create_tenant_and_owner(text, text, uuid) FROM authenticated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION public.create_tenant_and_owner(text, text, uuid) TO service_role;
    END IF;
END $$;
