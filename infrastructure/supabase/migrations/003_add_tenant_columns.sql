-- Add missing columns to tenants table for test environment
-- This aligns the database schema with the SQLAlchemy models

-- Create enum type for subscription plans
DO $$ BEGIN
    CREATE TYPE subscriptionplan AS ENUM ('free', 'starter', 'professional', 'enterprise');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add columns to tenants table
ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS slug VARCHAR(100),
ADD COLUMN IF NOT EXISTS subscription_plan subscriptionplan DEFAULT 'free',
ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'active',
ADD COLUMN IF NOT EXISTS subscription_started_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS ai_budget_monthly FLOAT DEFAULT 50.0,
ADD COLUMN IF NOT EXISTS ai_spend_current FLOAT DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS ai_spend_last_reset TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS max_projects INTEGER DEFAULT 5,
ADD COLUMN IF NOT EXISTS max_users INTEGER DEFAULT 3,
ADD COLUMN IF NOT EXISTS max_storage_gb INTEGER DEFAULT 10,
ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Update existing rows to have a slug (generate from name)
UPDATE tenants
SET slug = lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))
WHERE slug IS NULL;

-- Now make slug NOT NULL and UNIQUE
ALTER TABLE tenants
ALTER COLUMN slug SET NOT NULL;

-- Add unique constraint and index for slug
DO $$ BEGIN
    ALTER TABLE tenants ADD CONSTRAINT tenants_slug_key UNIQUE (slug);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS ix_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS ix_tenants_subscription ON tenants(subscription_plan, subscription_status);
CREATE INDEX IF NOT EXISTS ix_tenants_created ON tenants(created_at);

-- Update user table to add missing columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255),
ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS phone VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_activity TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}';

-- Create enum type for user roles
DO $$ BEGIN
    CREATE TYPE userrole AS ENUM ('admin', 'user', 'viewer', 'api');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Rename role column to match enum (if needed)
ALTER TABLE users
DROP COLUMN IF EXISTS role CASCADE;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS role userrole DEFAULT 'user';

-- Create indexes for users
CREATE INDEX IF NOT EXISTS ix_users_tenant_email ON users(tenant_id, email);
CREATE INDEX IF NOT EXISTS ix_users_tenant_role ON users(tenant_id, role);
CREATE INDEX IF NOT EXISTS ix_users_last_login ON users(last_login);

-- ===================================
-- UPDATE PROJECTS TABLE
-- ===================================

-- Create enum types for projects
DO $$ BEGIN
    CREATE TYPE projectstatus AS ENUM ('draft', 'active', 'completed', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE projecttype AS ENUM ('construction', 'engineering', 'industrial', 'infrastructure', 'other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add columns to projects table
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS code VARCHAR(50),
ADD COLUMN IF NOT EXISTS estimated_budget FLOAT,
ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'EUR',
ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_analysis_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS project_metadata JSONB DEFAULT '{}';

-- Drop old status column if it exists (VARCHAR) and add enum version
DO $$ BEGIN
    ALTER TABLE projects DROP COLUMN IF EXISTS status CASCADE;
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS status projectstatus DEFAULT 'draft';
EXCEPTION
    WHEN OTHERS THEN null;
END $$;

-- Drop old project_type column if it exists (VARCHAR) and add enum version
DO $$ BEGIN
    ALTER TABLE projects DROP COLUMN IF EXISTS project_type CASCADE;
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_type projecttype DEFAULT 'construction';
EXCEPTION
    WHEN OTHERS THEN null;
END $$;
