-- TS-DB-MIG-REC-006
-- Procurement feature-table compatibility surface

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wbsitemtype') THEN
        CREATE TYPE wbsitemtype AS ENUM ('deliverable', 'work_package', 'activity');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bomcategory') THEN
        CREATE TYPE bomcategory AS ENUM ('material', 'equipment', 'service', 'consumable');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'procurementstatus') THEN
        CREATE TYPE procurementstatus AS ENUM ('pending', 'requested', 'ordered', 'in_transit', 'delivered', 'cancelled');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS procurement_budget_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    code VARCHAR NOT NULL UNIQUE,
    amount NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS procurement_wbs_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    code VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    level INTEGER NOT NULL,
    description TEXT NULL,
    parent_code VARCHAR NULL,
    item_type wbsitemtype NULL,
    budget_allocated NUMERIC(10, 2) NULL,
    budget_spent NUMERIC(10, 2) NOT NULL DEFAULT 0,
    planned_start TIMESTAMPTZ NULL,
    planned_end TIMESTAMPTZ NULL,
    actual_start TIMESTAMPTZ NULL,
    actual_end TIMESTAMPTZ NULL,
    source_clause_id UUID NULL,
    version INTEGER NOT NULL DEFAULT 1,
    wbs_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fk_procurement_wbs_parent
        FOREIGN KEY (parent_code)
        REFERENCES procurement_wbs_items(code)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_procurement_wbs_project
    ON procurement_wbs_items(project_id);

CREATE TABLE IF NOT EXISTS procurement_bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    item_name VARCHAR NOT NULL,
    quantity NUMERIC(10, 2) NOT NULL,
    wbs_item_id UUID NULL,
    item_code VARCHAR NULL,
    description TEXT NULL,
    category bomcategory NULL,
    unit VARCHAR NULL,
    unit_price NUMERIC(10, 2) NULL,
    total_price NUMERIC(10, 2) NULL,
    currency VARCHAR NOT NULL DEFAULT 'EUR',
    supplier VARCHAR NULL,
    lead_time_days INTEGER NULL,
    production_time_days INTEGER NULL,
    transit_time_days INTEGER NULL,
    incoterm VARCHAR NULL,
    contract_clause_id UUID NULL,
    budget_item_id UUID NULL,
    procurement_status procurementstatus NOT NULL DEFAULT 'pending',
    bom_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fk_procurement_bom_wbs
        FOREIGN KEY (wbs_item_id)
        REFERENCES procurement_wbs_items(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_procurement_bom_budget
        FOREIGN KEY (budget_item_id)
        REFERENCES procurement_budget_items(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_procurement_bom_project
    ON procurement_bom_items(project_id);

ALTER TABLE procurement_budget_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_budget_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_procurement_budget_items ON procurement_budget_items;
CREATE POLICY tenant_isolation_procurement_budget_items ON procurement_budget_items
    FOR ALL
    USING (FALSE)
    WITH CHECK (FALSE);

ALTER TABLE procurement_wbs_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_wbs_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_procurement_wbs_items ON procurement_wbs_items;
CREATE POLICY tenant_isolation_procurement_wbs_items ON procurement_wbs_items
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

ALTER TABLE procurement_bom_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_bom_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_procurement_bom_items ON procurement_bom_items;
CREATE POLICY tenant_isolation_procurement_bom_items ON procurement_bom_items
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );
