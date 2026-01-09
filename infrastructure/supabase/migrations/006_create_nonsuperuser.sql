-- ===================================
-- Migration 006: Create Non-Superuser for Tests
-- ===================================
-- Creates a non-superuser account for RLS testing
-- Superusers bypass RLS even with FORCE enabled
-- Date: 2026-01-07

-- Create nonsuperuser if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'nonsuperuser') THEN
        CREATE USER nonsuperuser WITH PASSWORD 'test';
        RAISE NOTICE 'Created user: nonsuperuser';
    ELSE
        RAISE NOTICE 'User nonsuperuser already exists';
    END IF;
END $$;

-- Grant database connection
GRANT CONNECT ON DATABASE c2pro_test TO nonsuperuser;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO nonsuperuser;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nonsuperuser;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nonsuperuser;

-- Grant function execution
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO nonsuperuser;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nonsuperuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO nonsuperuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO nonsuperuser;

-- Verify
DO $$
DECLARE
    user_exists BOOLEAN;
    is_superuser BOOLEAN;
BEGIN
    SELECT EXISTS(SELECT 1 FROM pg_user WHERE usename = 'nonsuperuser') INTO user_exists;
    SELECT usesuper FROM pg_user WHERE usename = 'nonsuperuser' INTO is_superuser;

    IF user_exists AND NOT is_superuser THEN
        RAISE NOTICE '✓ nonsuperuser created successfully (not a superuser)';
    ELSIF user_exists AND is_superuser THEN
        RAISE WARNING 'nonsuperuser exists but is a superuser - RLS will not work!';
    ELSE
        RAISE WARNING 'nonsuperuser creation failed';
    END IF;
END $$;
