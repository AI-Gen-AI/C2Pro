-- C2Pro Test Database Initialization
-- Sets up permissions for the test user

-- Create test user
CREATE USER nonsuperuser WITH PASSWORD 'test';

-- Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE c2pro_test TO nonsuperuser;

-- Grant all privileges on the public schema
GRANT ALL PRIVILEGES ON SCHEMA public TO nonsuperuser;

-- Grant all on existing tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nonsuperuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nonsuperuser;

-- Grant all on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nonsuperuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nonsuperuser;

-- Allow nonsuperuser to create tables
GRANT CREATE ON SCHEMA public TO nonsuperuser;

-- Allow nonsuperuser to create extensions (needed for some PostgreSQL features)
ALTER USER nonsuperuser WITH CREATEROLE;
