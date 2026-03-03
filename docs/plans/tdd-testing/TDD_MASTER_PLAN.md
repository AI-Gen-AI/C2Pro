# C2Pro UX Implementation - TDD Testing Master Plan

**Planner:** @planner-agent  
**Based on:** MASTER_PLAN_v1.0.md, PRODUCT_SUMMARY.md  
**Date:** 2026-02-15  
**Status:** Ready for QA Agent Execution

---

## Executive Summary

This document provides a comprehensive **Test-Driven Development (TDD)** plan for the WBS Management and Procurement Intelligence modules. Following strict TDD principles:

- **RED Phase:** Write failing tests first (ImportError or assertion failure)
- **GREEN Phase:** Write minimal code to pass (fake-it pattern)
- **REFACTOR Phase:** Improve structure only after tests pass

**Test Coverage Strategy:**

- **Unit Tests:** Domain logic, component behavior (80%+ coverage)
- **Integration Tests:** API contracts, cross-module communication
- **E2E Tests:** Complete user journeys (3 critical paths)
- **Contract Tests:** API/frontend alignment
- **Accessibility Tests:** WCAG 2.2 AA compliance
- **Mobile Tests:** Touch targets, offline mode, responsive design

---

## TDD Principles Applied

### 1. Test-First Development Flow

```
User Story → Write Failing Test → Implement → Pass → Refactor → Next Story
```

**Example:**

```
Story: "Filter WBS by completion status"
↓
Test: expect(filterWBSByStatus(items, 'in-progress')).toHaveLength(15)
  → FAILS (function doesn't exist)
↓
Implement: const filterWBSByStatus = (items, status) => items.filter(...)
  → PASSES
↓
Refactor: Extract to custom hook useWBSFilter
↓
Commit: "feat(wbs): add status filtering with tests"
```

### 2. Fake-It Pattern (Green Phase)

**First Implementation (Fake):**

```typescript
// Just return expected result, no real logic
const calculateLeadTime = () => ({
  totalDays: 69,
  orderByDate: "2025-03-07",
  riskLevel: "medium",
});
```

**Triangulation (Add More Tests):**

```typescript
test("calculates production days", () => {
  expect(calculateLeadTime({ productionDays: 45 }).productionDays).toBe(45);
});

test("calculates transit days", () => {
  expect(calculateLeadTime({ transitDays: 12 }).transitDays).toBe(12);
});
```

**Real Implementation:**

```typescript
const calculateLeadTime = (params) => ({
  totalDays:
    params.productionDays +
    params.transitDays +
    params.customsDays +
    params.bufferDays,
  orderByDate: calculateOrderDate(params.requiredOnSite, totalDays),
  riskLevel: determineRiskLevel(totalDays, params.bufferDays),
});
```

### 3. Test Suite ID Traceability

Every test file must include Test Suite ID from `C2PRO_TEST_SUITES_INDEX_v1.1.md`:

```typescript
/**
 * TS-UAD-WBS-TREE-001 - WBS Tree Component Tests
 *
 * Tests for:
 * - Recursive tree rendering
 * - Expand/collapse functionality
 * - Selection handling
 */
```

---

## Test Suite Architecture

### 1. Test Directory Structure

```
apps/api/tests/
├── modules/
│   ├── wbs/                              # NEW
│   │   ├── domain/
│   │   │   ├── test_wbs_item_entity.py   # TS-UD-WBS-001
│   │   │   ├── test_wbs_hierarchy.py     # TS-UD-WBS-002
│   │   │   └── test_wbs_validation.py    # TS-UD-WBS-003
│   │   ├── application/
│   │   │   ├── test_create_wbs_item.py   # TS-UA-WBS-001
│   │   │   ├── test_update_wbs_item.py   # TS-UA-WBS-002
│   │   │   └── test_move_wbs_item.py     # TS-UA-WBS-003
│   │   └── adapters/
│   │       ├── test_wbs_repository.py    # TS-UAD-WBS-001
│   │       └── test_wbs_api.py           # TS-E2E-WBS-001
│   └── procurement/                       # NEW
│       ├── domain/
│       │   ├── test_bom_item.py          # TS-UD-PROC-001
│       │   ├── test_lead_time_calc.py    # TS-UD-PROC-002
│       │   └── test_procurement_plan.py  # TS-UD-PROC-003
│       ├── application/
│       │   ├── test_generate_bom.py      # TS-UA-PROC-001
│       │   ├── test_calculate_lead_time.py # TS-UA-PROC-002
│       │   └── test_generate_plan.py     # TS-UA-PROC-003
│       └── adapters/
│           ├── test_procurement_repository.py
│           └── test_procurement_api.py
├── integration/
│   ├── test_wbs_procurement_contract.py  # Cross-module integration
│   └── test_demo_mode_offline.py         # Demo mode tests
└── e2e/
    ├── journeys/
    │   ├── test_journey_1_setup.py       # TS-E2E-J1-001
    │   ├── test_journey_2_review.py      # TS-E2E-J2-001
    │   └── test_journey_3_resolution.py  # TS-E2E-J3-001
    └── demo/
        ├── test_delayed_foundation.py    # TS-E2E-DEMO-001
        ├── test_budget_surprise.py       # TS-E2E-DEMO-002
        └── test_procurement_crisis.py    # TS-E2E-DEMO-003

apps/web/tests/
├── components/
│   ├── wbs/
│   │   ├── WBSTree.test.tsx              # TS-UAD-WBS-TREE-001
│   │   ├── WBSItemCard.test.tsx          # TS-UAD-WBS-CARD-001
│   │   └── WBSItemDetail.test.tsx        # TS-UAD-WBS-DETAIL-001
│   └── procurement/
│       ├── BOMTable.test.tsx             # TS-UAD-PROC-TABLE-001
│       ├── LeadTimeCalculator.test.tsx   # TS-UAD-PROC-CALC-001
│       └── ProcurementGantt.test.tsx     # TS-UAD-PROC-GANTT-001
├── hooks/
│   ├── useWbs.test.ts                    # TS-UAD-WBS-HOOK-001
│   ├── useProcurement.test.ts            # TS-UAD-PROC-HOOK-001
│   └── usePermissions.test.ts            # TS-UAD-PERM-HOOK-001
├── integration/
│   ├── api-contracts.test.ts             # Contract tests
│   └── cross-module-navigation.test.tsx  # Navigation tests
├── e2e/
│   ├── journeys/
│   │   ├── journey-1-setup.spec.ts       # Playwright
│   │   ├── journey-2-review.spec.ts
│   │   └── journey-3-resolution.spec.ts
│   └── mobile/
│       ├── touch-targets.spec.ts
│       ├── offline-mode.spec.ts
│       └── responsive.spec.ts
└── accessibility/
    ├── wbs-a11y.test.ts                  # axe-core tests
    └── procurement-a11y.test.ts
```

---

## TDD Execution Roadmap

### Week 1: Foundation - RED Phase

**Goal:** Write all failing tests before writing any implementation code

**RED Phase Activities:**

1. **Contract Tests First** - Define API schemas
2. **Unit Tests** - Domain logic tests
3. **Component Tests** - React component behavior
4. **Integration Tests** - Cross-module navigation
5. **E2E Tests** - Complete user journeys

**Expected State:** All tests FAIL (this is correct for RED phase)

### Week 2-3: Implementation - GREEN Phase

**Goal:** Make all tests pass with minimal code

**GREEN Phase Activities:**

1. Implement fake responses first
2. Add real logic incrementally
3. Triangulate with more test cases
4. Keep all tests passing

**Expected State:** All tests PASS

### Week 4: Refactoring - REFACTOR Phase

**Goal:** Improve code quality while keeping tests green

**REFACTOR Activities:**

1. Extract reusable hooks
2. Optimize performance
3. Improve accessibility
4. Add mobile optimizations

**Expected State:** All tests still PASS, code is cleaner

---

## Test Case Inventory

### Total Test Cases by Phase

| Phase      | Backend Tests | Frontend Tests | E2E Tests | Total |
| ---------- | ------------- | -------------- | --------- | ----- |
| **Week 1** | 45            | 60             | 15        | 120   |
| **Week 2** | 80            | 120            | 30        | 230   |
| **Week 3** | 60            | 80             | 20        | 160   |
| **Week 4** | 20            | 40             | 10        | 70    |
| **TOTAL**  | 205           | 300            | 75        | 580   |

### Test Coverage Targets

| Category                 | Target  | Minimum |
| ------------------------ | ------- | ------- |
| **Line Coverage**        | 90%     | 80%     |
| **Branch Coverage**      | 85%     | 75%     |
| **Function Coverage**    | 95%     | 85%     |
| **E2E Journey Success**  | 100%    | 100%    |
| **Accessibility (WCAG)** | 100% AA | 100% A  |
| **Mobile Responsive**    | 95%     | 90%     |

---

## Critical Test Suites by Priority

### P0 - Must Have (Block Release)

1. **TS-E2E-J1-001** - First-Time Project Setup Journey
2. **TS-E2E-J2-001** - Weekly Project Review Journey
3. **TS-E2E-J3-001** - Alert Resolution Journey
4. **TS-CT-API-001** - API Contract Tests
5. **TS-A11Y-001** - Accessibility Compliance

### P1 - Should Have (Required for Production)

1. **TS-UD-WBS-001** - WBS Domain Logic
2. **TS-UA-WBS-001** - WBS Use Cases
3. **TS-UD-PROC-001** - Procurement Domain
4. **TS-UA-PROC-001** - Procurement Use Cases
5. **TS-UAD-WBS-TREE-001** - WBS Tree Component

### P2 - Nice to Have (Post-Release)

1. **TS-E2E-DEMO-001** - Demo Scenario Tests
2. **TS-INT-OFFLINE-001** - Offline Mode Tests
3. **TS-PERF-001** - Performance Benchmarks
4. **TS-SEC-001** - Security Penetration Tests

---

## Test Dependencies

### Execution Order

```
1. Contwract Tests (Define API)
   ↓
2. Domain Unit Tests (Backend logic)
   ↓
3. Use Case Tests (Backend orchestration)
   ↓
4. Repository Tests (DB integration)
   ↓
5. API Integration Tests (Full backend)
   ↓
6. Component Unit Tests (Frontend)
   ↓
7. Hook/Store Tests (Frontend state)
   ↓
8. Cross-Module Integration Tests
   ↓
9. E2E Journey Tests (Full flow)
   ↓
10. Accessibility Tests
   ↓
11. Mobile Responsive Tests
```

---

## Next Sections

See the following files for detailed test specifications:

1. **TDD_WEEK1_TESTS.md** - Phase 1: Foundation Tests (RED Phase)
2. **TDD_WEEK2_TESTS.md** - Phase 2: WBS Module Tests
3. **TDD_WEEK3_TESTS.md** - Phase 3: Procurement Module Tests
4. **TDD_WEEK4_TESTS.md** - Phase 4: E2E & Refactoring Tests
5. **TDD_MOCK_DATA.md** - Mock data specifications for tests
6. **TDD_TEST_UTILS.md** - Test utilities and helpers

---

**Status:** Ready for QA Agent Execution  
**Next Step:** Begin with TDD_WEEK1_TESTS.md - Foundation Phase
