# UX Implementation - Quick Reference & Checklist

**For:** Development Team  
**Source:** MASTER_PLAN_v1.0.md

---

## TL;DR - What's Missing

**Critical Gap:** Backend has WBS & Procurement (100%) → Frontend has nothing (0%)

**Goal:** Build two tracks simultaneously:

1. **Real Features** - Working WBS & Procurement for actual users
2. **Demo Mode** - Full-featured showcase with mock data

---

## User Journey Priority

### Journey 1: First-Time Project Setup (30 min goal)

**Must Work:** Upload → Extract → Generate WBS → Refine → Generate BOM → Procurement Plan

### Journey 2: Weekly Project Review (15 min goal)

**Must Work:** Dashboard → WBS Check → Procurement Status → Alert Review

### Journey 3: Alert Resolution (10 min goal)

**Must Work:** Alert → View Details → Navigate to Item → Fix → Resolve → See Score Update

---

## Critical User Stories (Don't Miss These!)

### WBS - Final User

- Filter by completion status (0%, 1-99%, 100%)
- Search by name, code, or description
- Color-coded by alert severity
- Expand/collapse all levels
- See linked contract clauses
- Export to PDF/Excel

### WBS - Tenant Admin

- Bulk import from Excel/CSV
- Copy from template project
- Undo last 3 actions
- Bulk edit (multi-select)
- Auto-generate codes with custom prefixes
- Lock items once procurement starts

### Procurement - Final User

- Attach PDF purchase orders
- Running total vs budget
- Filter by delivery status
- See linked WBS item context
- Compare estimated vs actual costs

### Procurement - Tenant Admin

- Supplier database management
- What-if scenario testing
- Auto-generate PO PDFs
- Bulk update incoterms

---

## Week-by-Week Checklist

### Week 1: Foundation

**Backend (@backend-tdd)**

- [ ] `GET /projects/{id}/wbs` - Returns tree structure
- [ ] `POST /projects/{id}/wbs/items` - Create WBS item
- [ ] `PATCH /projects/{id}/wbs/items/{id}` - Update WBS item
- [ ] `DELETE /projects/{id}/wbs/items/{id}` - Delete WBS item
- [ ] `POST /projects/{id}/wbs/items/{id}/move` - Move item (drag & drop)
- [ ] `GET /projects/{id}/procurement/bom` - Get BOM
- [ ] `POST /projects/{id}/procurement/lead-times` - Calculate lead times
- [ ] `GET /projects/{id}/procurement/plan` - Get procurement plan

**Frontend (@frontend-tdd)**

- [ ] Create `DemoModeProvider` context
- [ ] Implement toggle: `?demo=true` query param
- [ ] Create mock data structure (Torre Skyline)
- [ ] Set up feature flags by role

**QA (@qa-agent)**

- [ ] Contract tests for all new endpoints
- [ ] Validate OpenAPI spec

---

### Week 2: WBS Module

**Components to Build:**

- [ ] `WBSTree` - Recursive tree component
- [ ] `WBSItemCard` - Individual item display
- [ ] `WBSItemDetail` - Detail panel
- [ ] `WBSCCodeEditor` - Code input with validation
- [ ] `WBSCoverageIndicator` - Coverage progress bar
- [ ] `WBSAlertBadge` - Rule violation badges (R11, R12, R13)

**Page:**

- [ ] `/projects/[id]/wbs` - Full WBS page

**Features:**

- [ ] Tree expand/collapse
- [ ] Drag & drop (Tenant Admin only)
- [ ] Create new item (auto-generate code)
- [ ] Edit item properties
- [ ] Delete item (with cascade warning)
- [ ] View linked clauses
- [ ] Show alerts per item

**By Role:**

- **Final User:** View only ✅
- **Tenant Admin:** Full CRUD ✅
- **C2Pro Admin:** Full CRUD ✅

---

### Week 3: Procurement Module

**Components to Build:**

- [ ] `BOMTable` - Sortable table with costs
- [ ] `LeadTimeCalculator` - Incoterm calculator widget
- [ ] `LeadTimeCard` - Individual result display
- [ ] `ProcurementGantt` - Timeline visualization
- [ ] `CriticalPathOverlay` - Highlight critical items
- [ ] `IncotermSelector` - Dropdown with descriptions
- [ ] `ProcurementAlertList` - R14 late order alerts
- [ ] `RiskIndicator` - Low/Medium/High/Critical badges

**Page:**

- [ ] `/projects/[id]/procurement` - Tabbed interface

**Tabs:**

1. **BOM** - Material list with WBS mapping
2. **Lead Times** - Calculator + results
3. **Plan** - Gantt chart with order dates
4. **Alerts** - Procurement alerts

**Features:**

- [ ] View BOM generated from WBS
- [ ] Calculate lead times (all 11 incoterms)
- [ ] See customs clearance estimates
- [ ] View procurement plan timeline
- [ ] Identify critical path
- [ ] Get late order alerts (R14)
- [ ] Export to PDF/Excel

**By Role:**

- **Final User:** View only ✅
- **Tenant Admin:** Manage (adjust, override) ✅
- **C2Pro Admin:** Full control ✅

---

### Week 4: Demo Mode & Polish

**Demo Mode:**

- [ ] Rich mock dataset (Torre Skyline project)
- [ ] Works offline (no API calls)
- [ ] All features interactive
- [ ] Realistic data (47 WBS items, full BOM)
- [ ] Alert scenarios included
- [ ] Mobile-optimized views

**Polish:**

- [ ] Remove mock data from Project Overview
- [ ] Connect to real API endpoints
- [ ] Add loading states
- [ ] Add error boundaries
- [ ] Mobile responsive check
- [ ] Accessibility audit (WCAG 2.2)
- [ ] Performance optimization

**Exports:**

- [ ] WBS to Excel
- [ ] WBS to PDF
- [ ] BOM to CSV
- [ ] Procurement plan to PDF

**Docs:**

- [ ] User guide for WBS
- [ ] User guide for Procurement
- [ ] Demo mode documentation

---

## Critical Paths

### 1. WBS Tree Rendering

**Challenge:** Recursive tree with 4 levels (1, 1.1, 1.1.1, 1.1.1.1)  
**Solution:**

- Virtualized list for performance (>100 items)
- Lazy load children on expand
- Memoize components

### 2. Drag & Drop

**Challenge:** Moving items in hierarchy without creating cycles  
**Solution:**

- Validate move server-side
- Visual indicators for valid drop zones
- Prevent drop if would exceed level 4

### 3. Gantt Chart

**Challenge:** Timeline visualization with many items  
**Solution:**

- Use existing library (vis-timeline or similar)
- Virtualized scrolling
- Zoom levels (month/week/day)

### 4. Mobile UX

**Challenge:** Complex tree/table on small screens  
**Solution:**

- Bottom sheets for detail views
- Collapsible panels
- Swipe gestures
- Simplified views

---

## File Structure

```
apps/web/
├── app/
│   └── (dashboard)/
│       └── projects/
│           └── [id]/
│               ├── wbs/
│               │   └── page.tsx          # NEW
│               ├── procurement/
│               │   └── page.tsx          # NEW
│               ├── documents/
│               ├── analysis/
│               ├── coherence/
│               └── evidence/
├── components/
│   ├── wbs/                              # NEW
│   │   ├── WBSTree.tsx
│   │   ├── WBSItemCard.tsx
│   │   ├── WBSItemDetail.tsx
│   │   ├── WBSCCodeEditor.tsx
│   │   ├── WBSCoverageIndicator.tsx
│   │   └── WBSAlertBadge.tsx
│   └── procurement/                      # NEW
│       ├── BOMTable.tsx
│       ├── LeadTimeCalculator.tsx
│       ├── LeadTimeCard.tsx
│       ├── ProcurementGantt.tsx
│       ├── CriticalPathOverlay.tsx
│       ├── IncotermSelector.tsx
│       ├── ProcurementAlertList.tsx
│       └── RiskIndicator.tsx
├── hooks/
│   ├── useWbs.ts                         # NEW
│   ├── useWbsPermissions.ts              # NEW
│   ├── useProcurement.ts                 # NEW
│   └── useProcurementPermissions.ts      # NEW
├── stores/
│   ├── wbsStore.ts                       # NEW
│   └── procurementStore.ts               # NEW
├── lib/
│   └── api/
│       └── generated/                    # Orval generates from OpenAPI
├── mocks/
│   └── demo/
│       ├── torre-skyline.ts              # NEW
│       └── demo-provider.tsx             # NEW
└── types/
    ├── wbs.ts                            # NEW
    └── procurement.ts                    # NEW
```

---

## API Endpoints Quick Reference

### WBS Endpoints

```
GET    /projects/{id}/wbs                    # Get tree
POST   /projects/{id}/wbs/items              # Create item
GET    /projects/{id}/wbs/items/{id}         # Get details
PATCH  /projects/{id}/wbs/items/{id}         # Update item
DELETE /projects/{id}/wbs/items/{id}         # Delete item
POST   /projects/{id}/wbs/items/{id}/move    # Move item
POST   /projects/{id}/wbs/validate           # Run validation
```

### Procurement Endpoints

```
GET    /projects/{id}/procurement/bom                    # Get BOM
POST   /projects/{id}/procurement/bom                    # Regenerate BOM
POST   /projects/{id}/procurement/lead-times             # Calculate lead times
PATCH  /projects/{id}/procurement/lead-times/{bomItemId} # Update lead time params
GET    /projects/{id}/procurement/plan                   # Get procurement plan
POST   /projects/{id}/procurement/plan                   # Generate plan
PATCH  /projects/{id}/procurement/plan/items/{id}/status # Update item status
```

---

## Permission Matrix

| Feature         | Final User | Tenant Admin | C2Pro Admin |
| --------------- | ---------- | ------------ | ----------- |
| **WBS**         |
| View Tree       | ✅         | ✅           | ✅          |
| View Details    | ✅         | ✅           | ✅          |
| Create Item     | ❌         | ✅           | ✅          |
| Edit Item       | ❌         | ✅           | ✅          |
| Delete Item     | ❌         | ✅           | ✅          |
| Move Item       | ❌         | ✅           | ✅          |
| **Procurement** |
| View BOM        | ✅         | ✅           | ✅          |
| View Lead Times | ✅         | ✅           | ✅          |
| View Plan       | ✅         | ✅           | ✅          |
| Calculate LT    | ❌         | ✅           | ✅          |
| Regenerate BOM  | ❌         | ✅           | ✅          |
| Adjust Plan     | ❌         | ✅           | ✅          |
| Update Status   | ❌         | ✅           | ✅          |

---

## Mock Data Highlights (Torre Skyline)

### Project Stats

- **Name:** Torre Skyline
- **Type:** 25-story mixed-use tower
- **Budget:** €45,000,000
- **WBS Items:** 47
- **BOM Items:** 23
- **Coherence Score:** 78

### WBS Sample

```
1 Preliminaries
  1.1 Site Setup
    1.1.1 Site Office (€150k, 100%)
    1.1.2 Security & Fencing (€75k, 100%)

2 Substructure
  2.1 Foundation
    2.1.1 Excavation (€800k, 85%)
    2.1.2 Piling Works (€2.5M, 60%)
    2.1.3 Foundation Slab
      2.1.3.1 Reinforcement (€450k, 30%)
      2.1.3.2 Concrete Pour (€380k, 0%)
```

### Procurement Alert

- **Rule:** R14 (Late Order)
- **Severity:** Critical
- **Message:** Steel Rebar order deadline in 2 days
- **Action:** Order immediately or risk foundation delay

---

## Testing Checklist

### Unit Tests

- [ ] WBSTree renders all 4 levels
- [ ] WBSItemCard displays correct data
- [ ] Code validation accepts valid codes (1.1.1.1)
- [ ] Code validation rejects invalid codes
- [ ] BOMTable sorts correctly
- [ ] LeadTimeCalculator computes accurately

### Integration Tests

- [ ] Create WBS item → appears in tree
- [ ] Move item → updates hierarchy
- [ ] Delete item → removes from tree
- [ ] Generate BOM → creates items from WBS
- [ ] Calculate lead times → returns results

### E2E Tests

- [ ] Full flow: Create project → Add WBS → Generate BOM → Calculate LT → View Plan
- [ ] Demo mode works offline
- [ ] Role-based permissions enforced
- [ ] Mobile navigation works
- [ ] Exports generate files

### Accessibility

- [ ] Keyboard navigation (Tab, Arrow keys, Enter)
- [ ] Screen reader labels
- [ ] Color contrast (WCAG AA)
- [ ] Focus indicators

---

## Common Issues & Solutions

### Issue: Tree performance with 100+ items

**Solution:** Use `react-window` for virtualization

### Issue: Drag & drop feels laggy

**Solution:** Debounce drag events, use `react-beautiful-dnd`

### Issue: Gantt chart too wide on mobile

**Solution:** Horizontal scroll with sticky left column

### Issue: API calls fail in demo mode

**Solution:** Intercept with MSW or mock at Orval level

### Issue: Permission checks everywhere

**Solution:** Create wrapper components:

```tsx
<TenantAdminOnly>
  <DeleteButton />
</TenantAdminOnly>
```

---

## Success Criteria

### Week 1

- [ ] All 8 API endpoints return 200
- [ ] Demo mode toggle works
- [ ] Contract tests pass

### Week 2

- [ ] Final User can view WBS tree
- [ ] Tenant Admin can CRUD items
- [ ] Mobile view is usable

### Week 3

- [ ] Final User can view procurement data
- [ ] Tenant Admin can manage procurement
- [ ] Gantt displays critical path

### Week 4

- [ ] Demo mode works without backend
- [ ] Project overview shows real data
- [ ] All exports functional
- [ ] E2E tests pass

---

## Questions?

- **Backend API issues?** → @backend-tdd
- **Frontend components?** → @frontend-tdd
- **Test failures?** → @qa-agent
- **Documentation?** → @docs-agent
- **Security concerns?** → @security-agent

**Master Plan:** `docs/plans/ux-implementation/MASTER_PLAN_v1.0.md`

- Section 3: User Journey Maps
- Section 4: Enhanced User Stories (20+)
- Section 5: Cross-Module Navigation
- Section 6: Mobile-First Use Cases
- Section 7: Demo Scenarios
- Section 8: API Contracts
- Section 10: Implementation Roadmap

**OpenAPI Spec:** `docs/plans/ux-implementation/openapi-wbs-procurement.yaml`  
**Architecture:** `docs/plans/ux-implementation/ARCHITECTURE_DIAGRAMS.md`

---

**Status:** Ready to Execute 🚀
