-- Test Foreign Key Integrity
-- Used in CE-24: Foreign Key Constraint Verification

\echo '=== Testing Foreign Key Integrity ==='

\echo '\n--- Test 1: Attempt to insert user with invalid tenant (should fail) ---'
DO $$
BEGIN
  INSERT INTO users (id, email, tenant_id)
  VALUES (
    'ffffffff-ffff-ffff-ffff-ffffffffffff',
    'test@invalid.com',
    '00000000-0000-0000-0000-000000000000'
  );
  RAISE EXCEPTION 'FK constraint FAILED - invalid tenant was accepted!';
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE NOTICE 'FK constraint PASSED - invalid tenant rejected';
END $$;

\echo '\n--- Test 2: Attempt to insert project with invalid tenant (should fail) ---'
DO $$
BEGIN
  INSERT INTO projects (id, name, tenant_id)
  VALUES (
    'ffffffff-ffff-ffff-ffff-ffffffffffff',
    'Invalid Project',
    '00000000-0000-0000-0000-000000000000'
  );
  RAISE EXCEPTION 'FK constraint FAILED - invalid tenant was accepted!';
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE NOTICE 'FK constraint PASSED - invalid tenant rejected';
END $$;

\echo '\n--- Test 3: Attempt to insert document with invalid project (should fail) ---'
DO $$
BEGIN
  INSERT INTO documents (id, title, project_id, tenant_id)
  VALUES (
    'ffffffff-ffff-ffff-ffff-ffffffffffff',
    'Invalid Document',
    '00000000-0000-0000-0000-000000000000',
    (SELECT id FROM tenants LIMIT 1)
  );
  RAISE EXCEPTION 'FK constraint FAILED - invalid project was accepted!';
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE NOTICE 'FK constraint PASSED - invalid project rejected';
END $$;

\echo '\n=== All FK Integrity Tests Complete ==='
