-- Check for Orphaned Records
-- Used in CE-24: Foreign Key Constraint Verification

\echo '=== Checking for Orphaned Records ==='

\echo '\n--- Users without valid tenant ---'
SELECT COUNT(*) as orphaned_users
FROM users u
LEFT JOIN tenants t ON u.tenant_id = t.id
WHERE t.id IS NULL;

\echo '\n--- Projects without valid tenant ---'
SELECT COUNT(*) as orphaned_projects
FROM projects p
LEFT JOIN tenants t ON p.tenant_id = t.id
WHERE t.id IS NULL;

\echo '\n--- Documents without valid project ---'
SELECT COUNT(*) as orphaned_documents
FROM documents d
LEFT JOIN projects p ON d.project_id = p.id
WHERE p.id IS NULL;

\echo '\n--- Clauses without valid document ---'
SELECT COUNT(*) as orphaned_clauses
FROM clauses c
LEFT JOIN documents d ON c.document_id = d.id
WHERE d.id IS NULL;

\echo '\n--- Analyses without valid project ---'
SELECT COUNT(*) as orphaned_analyses
FROM analyses a
LEFT JOIN projects p ON a.project_id = p.id
WHERE p.id IS NULL;

\echo '\n--- Alerts without valid analysis ---'
SELECT COUNT(*) as orphaned_alerts
FROM alerts al
LEFT JOIN analyses a ON al.analysis_id = a.id
WHERE a.id IS NULL;

\echo '\n--- Extractions without valid document ---'
SELECT COUNT(*) as orphaned_extractions
FROM extractions e
LEFT JOIN documents d ON e.document_id = d.id
WHERE d.id IS NULL;

\echo '\n--- Stakeholders without valid project ---'
SELECT COUNT(*) as orphaned_stakeholders
FROM stakeholders s
LEFT JOIN projects p ON s.project_id = p.id
WHERE p.id IS NULL;

\echo '\n--- WBS Items without valid project ---'
SELECT COUNT(*) as orphaned_wbs_items
FROM wbs_items w
LEFT JOIN projects p ON w.project_id = p.id
WHERE p.id IS NULL;

\echo '\n--- BOM Items without valid project ---'
SELECT COUNT(*) as orphaned_bom_items
FROM bom_items b
LEFT JOIN projects p ON b.project_id = p.id
WHERE p.id IS NULL;

\echo '\n=== Expected: All counts should be 0 ==='
