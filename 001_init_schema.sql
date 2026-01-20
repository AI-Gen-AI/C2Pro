-- Migration: 001_init_schema.sql
-- Description: Initial schema for C2Pro with multi-tenant security.

-- 1. Enable required extensions
-- pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";
-- vector for future AI embedding capabilities
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA "extensions";

-- 2. Core Table Definitions

-- Tenants Table: Represents a single customer organization (B2B).
CREATE TABLE public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    settings JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.tenants IS 'Stores organizations (tenants) using the SaaS platform.';

-- Users Table: Stores public user data, linked to a tenant.
CREATE TABLE public.users (
    id UUID PRIMARY KEY, -- References auth.users.id
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- CRITICAL: Ensures an email can only be associated with a tenant once.
    CONSTRAINT unique_tenant_email UNIQUE (tenant_id, email)
);
COMMENT ON TABLE public.users IS 'Stores user-specific data, linked to a tenant and Supabase auth.';

-- Projects Table: Core entity for contract analysis. Belongs to a tenant.
CREATE TABLE public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.projects IS 'Represents a single analysis project, owned by a tenant.';

-- Documents Table: Stores references to uploaded contract files. Belongs to a project.
CREATE TABLE public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    storage_url TEXT NOT NULL,
    is_encrypted BOOLEAN NOT NULL DEFAULT false,
    file_name TEXT,
    file_size_bytes BIGINT,
    created_at TIMESTAMTz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.documents IS 'References to uploaded files associated with a project.';


-- 3. Automatic User Sync with Supabase Auth
-- This function runs when a new user signs up. It copies the user from `auth.users`
-- to `public.users` and assigns them to the tenant specified in their metadata.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER -- Has the permissions to write to public.users
AS $$
BEGIN
  INSERT INTO public.users (id, tenant_id, email, first_name, last_name, role)
  VALUES (
    new.id,
    (new.raw_user_meta_data->>'tenant_id')::uuid,
    new.email,
    new.raw_user_meta_data->>'first_name',
    new.raw_user_meta_data->>'last_name',
    new.raw_user_meta_data->>'role'
  );
  RETURN new;
END;
$$;

-- Create the trigger that fires after a new user is created in Supabase Auth
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

COMMENT ON FUNCTION public.handle_new_user IS 'Automatically populates the public.users table when a new user signs up in Supabase Auth.';


-- 4. Row Level Security (RLS) Policies - GATE 1

-- Helper function to get the tenant_id from the current user's JWT
CREATE OR REPLACE FUNCTION auth.get_tenant_id()
RETURNS UUID
LANGUAGE sql STABLE
AS $$
  SELECT (auth.jwt()->>'tenant_id')::uuid
$$;

-- Enable RLS on all tables
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Tenants Policy: Users can only see their own tenant's record.
CREATE POLICY "Tenant isolation for tenants"
ON public.tenants
FOR ALL
USING (id = auth.get_tenant_id());

-- Users Policy: Users can only see other users within their own tenant.
CREATE POLICY "Tenant isolation for users"
ON public.users
FOR ALL
USING (tenant_id = auth.get_tenant_id());

-- Projects Policy: Users can only interact with projects belonging to their tenant.
CREATE POLICY "Tenant isolation for projects"
ON public.projects
FOR ALL
USING (tenant_id = auth.get_tenant_id());

-- Documents Policy: Users can only interact with documents whose parent project belongs to their tenant.
-- This requires a subquery or JOIN to check the parent project's tenant_id.
CREATE POLICY "Tenant isolation for documents"
ON public.documents
FOR ALL
USING (
  EXISTS (
    SELECT 1
    FROM public.projects p
    WHERE p.id = documents.project_id AND p.tenant_id = auth.get_tenant_id()
  )
);

COMMENT ON POLICY "Tenant isolation for documents" ON public.documents IS 'Ensures users can only access documents belonging to projects within their own tenant.';


-- 5. Performance Indexes
-- Create indexes on all foreign key and tenant_id columns for fast RLS checks and queries.
CREATE INDEX idx_users_tenant_id ON public.users(tenant_id);
CREATE INDEX idx_projects_tenant_id ON public.projects(tenant_id);
CREATE INDEX idx_documents_project_id ON public.documents(project_id);

-- End of migration script
