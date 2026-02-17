# C2Pro TDD Test Registry - Consolidated & Ordered

**Generated:** 2026-02-15  
**Source:** TDD_MASTER_PLAN.md, TDD_WEEK1_TESTS.md, TDD_WEEK2_TESTS.md, TDD_QUICK_REFERENCE.md  
**Status:** Ready for Execution

---

## 📋 Test Execution Summary

| Phase        | Week | Tests    | Goal                | Status         |
| ------------ | ---- | -------- | ------------------- | -------------- |
| **RED**      | 1    | 45+      | Write failing tests | 🟡 Pending     |
| **GREEN**    | 2    | 80+      | Make tests pass     | ⏳ Not Started |
| **GREEN**    | 3    | 60+      | Procurement module  | ⏳ Not Started |
| **REFACTOR** | 4    | 20+      | Optimize code       | ⏳ Not Started |
| **TOTAL**    | 1-4  | **580+** | Full coverage       | ⏳ Not Started |

**Target Coverage:** 90% lines, 85% branches, 95% functions

---

## 🔴 WEEK 1: RED Phase (Foundation)

_Execution Order: 1-11 | Goal: All tests initially FAILING_

| Order | Test ID                   | Name                                   | Type        | Owner         | File Location                                                 | Priority |
| ----- | ------------------------- | -------------------------------------- | ----------- | ------------- | ------------------------------------------------------------- | -------- |
| 1     | **TS-CT-WBS-API-001**     | WBS API Contract Tests                 | Contract    | @backend-tdd  | `tests/modules/wbs/adapters/test_wbs_api_contract.py`         | P0       |
| 2     | **TS-UD-WBS-001**         | WBS Item Entity Domain Tests           | Unit        | @backend-tdd  | `tests/modules/wbs/domain/test_wbs_item_entity.py`            | P1       |
| 3     | **TS-UAD-WBS-TREE-001**   | WBS Tree Component Contract Tests      | Component   | @frontend-tdd | `apps/web/components/wbs/__tests__/WBSTree.contract.test.tsx` | P1       |
| 4     | **TS-UAD-WBS-CARD-001**   | WBS Item Card Component Tests          | Component   | @frontend-tdd | `apps/web/components/wbs/__tests__/WBSItemCard.test.tsx`      | P1       |
| 5     | **TS-UAD-WBS-DETAIL-001** | WBS Item Detail Component Tests        | Component   | @frontend-tdd | `apps/web/components/wbs/__tests__/WBSItemDetail.test.tsx`    | P1       |
| 6     | **TS-INT-NAV-001**        | Cross-Module Navigation Contract Tests | Integration | @qa-agent     | `apps/web/tests/integration/navigation.contract.test.tsx`     | P1       |
| 7     | **TS-CT-API-001**         | Global API Contract Tests              | Contract    | @backend-tdd  | `tests/contract/test_api_contracts.py`                        | P0       |
| 8     | **TS-E2E-J1-001**         | First-Time Project Setup Journey       | E2E         | @qa-agent     | `apps/web/tests/e2e/journeys/journey-1-setup.spec.ts`         | P0       |
| 9     | **TS-E2E-J2-001**         | Weekly Project Review Journey          | E2E         | @qa-agent     | `apps/web/tests/e2e/journeys/journey-2-review.spec.ts`        | P0       |
| 10    | **TS-E2E-J3-001**         | Alert Resolution Journey               | E2E         | @qa-agent     | `apps/web/tests/e2e/journeys/journey-3-resolution.spec.ts`    | P0       |
| 11    | **TS-A11Y-001**           | Accessibility Compliance Tests         | A11y        | @frontend-tdd | `apps/web/tests/accessibility/wbs-a11y.test.ts`               | P0       |

### Week 1 Test Details

#### TS-CT-WBS-API-001: WBS API Contract Tests (10 tests)

- `test_get_wbs_returns_correct_schema`
- `test_get_wbs_handles_missing_project`
- `test_create_wbs_item_requires_name`
- `test_create_wbs_item_validates_code_format`
- `test_create_wbs_item_auto_generates_code`
- `test_move_wbs_item_prevents_circular_reference`
- `test_move_wbs_item_enforces_max_depth`
- `test_delete_wbs_item_with_children_requires_cascade`
- `test_delete_wbs_item_cascade_removes_children`
- `test_update_wbs_item_validates_budget`
- `test_wbs_response_includes_tenant_isolation`

#### TS-UD-WBS-001: WBS Item Entity Domain Tests (10 tests)

- `test_create_wbs_item_with_valid_code`
- `test_create_wbs_item_with_invalid_code_raises_error`
- `test_code_level_consistency`
- `test_generate_code_for_root_item`
- `test_generate_code_for_child_item`
- `test_cannot_exceed_maximum_depth`
- `test_completion_percentage_validation`
- `test_budget_money_value_object`
- `test_wbs_item_immutability`
- `test_is_ancestor_of`

#### TS-UAD-WBS-TREE-001: WBS Tree Component Contract Tests (10 tests)

- `should accept and render items prop`
- `should call onSelect callback when item is clicked`
- `should render empty state when items is empty array`
- `should filter items when filter prop is provided`
- `should filter items by searchQuery`
- `should disable editing when readOnly is true`
- `should expand items specified in expandedItems prop`
- `should call onExpand when expand button clicked`

#### TS-INT-NAV-001: Cross-Module Navigation Contract Tests (6 tests)

- `should display linked procurement items in WBS detail`
- `should navigate to procurement tab when procurement link clicked`
- `should display affected entities in alert detail`
- `should navigate to entity when clicked in alert detail`
- `should navigate to category detail when coherence score clicked`
- `should search across all modules`

---

## 🟢 WEEK 2: GREEN Phase (WBS Module)

_Execution Order: 12-25 | Goal: Make Week 1 tests PASS_

| Order | Test ID                   | Name                              | Type      | Owner         | File Location                                                           | Priority |
| ----- | ------------------------- | --------------------------------- | --------- | ------------- | ----------------------------------------------------------------------- | -------- |
| 12    | **TS-UAD-WBS-FILTER-001** | WBS Filter by Status Tests        | Hook      | @frontend-tdd | `apps/web/hooks/__tests__/useWbsFilter.test.ts`                         | P1       |
| 13    | **TS-UAD-WBS-SEARCH-001** | WBS Search Tests                  | Hook      | @frontend-tdd | `apps/web/hooks/__tests__/useWbsSearch.test.ts`                         | P1       |
| 14    | **TS-UAD-WBS-COLOR-001**  | WBS Alert Color Coding Tests      | Component | @frontend-tdd | `apps/web/components/wbs/__tests__/WBSAlertBadge.test.tsx`              | P1       |
| 15    | **TS-UA-WBS-CRUD-001**    | WBS CRUD Use Cases Tests          | Unit      | @backend-tdd  | `tests/modules/wbs/application/test_wbs_crud.py`                        | P1       |
| 16    | **TS-UD-WBS-002**         | WBS Hierarchy & Code Tests        | Unit      | @backend-tdd  | `tests/modules/wbs/domain/test_wbs_hierarchy.py`                        | P1       |
| 17    | **TS-UD-WBS-003**         | WBS Validation Rules Tests        | Unit      | @backend-tdd  | `tests/modules/wbs/domain/test_wbs_validation.py`                       | P1       |
| 18    | **TS-MOB-WBS-001**        | WBS Mobile Contract Tests         | Mobile    | @frontend-tdd | `apps/web/tests/mobile/wbs-mobile.contract.test.tsx`                    | P1       |
| 19    | **TS-A11Y-WBS-001**       | WBS Accessibility Contract Tests  | A11y      | @frontend-tdd | `apps/web/tests/accessibility/wbs-a11y.contract.test.tsx`               | P1       |
| 20    | **TS-UAD-WBS-HOOK-001**   | useWbs Hook Tests                 | Hook      | @frontend-tdd | `apps/web/hooks/__tests__/useWbs.test.ts`                               | P1       |
| 21    | **TS-UAD-PROC-TABLE-001** | BOM Table Component Tests         | Component | @frontend-tdd | `apps/web/components/procurement/__tests__/BOMTable.test.tsx`           | P1       |
| 22    | **TS-UAD-PROC-CALC-001**  | Lead Time Calculator Tests        | Component | @frontend-tdd | `apps/web/components/procurement/__tests__/LeadTimeCalculator.test.tsx` | P1       |
| 23    | **TS-UAD-PROC-GANTT-001** | Procurement Gantt Component Tests | Component | @frontend-tdd | `apps/web/components/procurement/__tests__/ProcurementGantt.test.tsx`   | P1       |
| 24    | **TS-UAD-PROC-HOOK-001**  | useProcurement Hook Tests         | Hook      | @frontend-tdd | `apps/web/hooks/__tests__/useProcurement.test.ts`                       | P1       |
| 25    | **TS-UAD-PERM-HOOK-001**  | usePermissions Hook Tests         | Hook      | @frontend-tdd | `apps/web/hooks/__tests__/usePermissions.test.ts`                       | P1       |

### Week 2 Test Details

#### TS-UAD-WBS-FILTER-001: WBS Filter by Status Tests (7 tests) - 🔴 RED Phase Complete

**Status:** Failing tests written, awaiting GREEN phase implementation  
**Last Updated:** 2026-02-17  
**Tests:** 7 tests (originally 6 + 1 added for completeness)

- [x] `should filter not-started items (completion = 0%)`
- [x] `should filter in-progress items (completion = 1-99%)`
- [x] `should filter complete items (completion = 100%)`
- [x] `should update URL query params when filter changes`
- [x] `should read filter from URL on mount`
- [x] `should persist filter in localStorage`
- [x] `should combine multiple filters`
- [x] `should clear filter and show all items` (additional test)
- [x] `should return all items when no filter is set` (additional test)
- [x] `should handle empty items array` (additional test)

#### TS-UAD-WBS-SEARCH-001: WBS Search Tests (7 tests)

- `should search by name (case insensitive)`
- `should search by code`
- `should search by description`
- `should highlight matching text`
- `should debounce search input`
- `should show "no results" message`
- `should fuzzy search with typos`

#### TS-UAD-WBS-COLOR-001: WBS Alert Color Coding Tests (5 tests)

- `should render none alerts with correct styling`
- `should render low alerts with correct styling`
- `should render medium alerts with correct styling`\n- `should render high alerts with correct styling`
- `should render critical alerts with correct styling`
- `should meet WCAG AA color contrast`
- `should show count when multiple alerts`
- `should show icon based on severity`

#### TS-UA-WBS-CRUD-001: WBS CRUD Use Cases Tests (10 tests)

- **Create Tests:**
  - `test_create_generates_code_for_root_item`
  - `test_create_generates_child_code`
  - `test_create_validates_max_depth`
- **Move Tests:**
  - `test_move_updates_code_and_level`
  - `test_move_prevents_circular_reference`
  - `test_move_updates_all_descendant_codes`
- **Delete Tests:**
  - `test_delete_without_cascade_fails_if_has_children`
  - `test_delete_with_cascade_removes_all_descendants`
  - `test_delete_updates_parent_completion`

#### TS-MOB-WBS-001: WBS Mobile Contract Tests (6 tests)

- `should have touch targets minimum 44px`
- `should support swipe right to mark complete`
- `should use bottom sheet for detail view on mobile`
- `should support pinch to zoom on Gantt`
- `should cache data for offline mode`
- `should queue actions when offline`

#### TS-A11Y-WBS-001: WBS Accessibility Contract Tests (7 tests)

- `should have no accessibility violations`
- `should have proper ARIA tree structure`
- `should support keyboard navigation`
- `should have sufficient color contrast`
- `should announce state changes to screen readers`
- `should have accessible labels for all interactive elements`

---

## 🟡 WEEK 3: GREEN Phase (Procurement Module)

_Execution Order: 26-40_

| Order | Test ID                | Name                                     | Type        | Owner           | Priority |
| ----- | ---------------------- | ---------------------------------------- | ----------- | --------------- | -------- |
| 26    | **TS-UD-PROC-001**     | BOM Item Entity Domain Tests             | Unit        | @backend-tdd    | P1       |
| 27    | **TS-UD-PROC-002**     | BOM Validation Rules Tests               | Unit        | @backend-tdd    | P1       |
| 28    | **TS-UD-PROC-003**     | Lead Time Calculator Tests               | Unit        | @backend-tdd    | P1       |
| 29    | **TS-UA-PROC-001**     | Generate BOM Use Case Tests              | Unit        | @backend-tdd    | P1       |
| 30    | **TS-UA-PROC-002**     | Calculate Lead Time Use Case Tests       | Unit        | @backend-tdd    | P1       |
| 31    | **TS-UA-PROC-003**     | Generate Procurement Plan Use Case Tests | Unit        | @backend-tdd    | P1       |
| 32    | **TS-INT-DB-WBS-001**  | WBS Repository + DB Integration          | Integration | @backend-tdd    | P1       |
| 33    | **TS-INT-DB-BOM-001**  | BOM Repository + DB Integration          | Integration | @backend-tdd    | P1       |
| 34    | **TS-INT-MOD-WBS-001** | WBS → Procurement Integration            | Integration | @backend-tdd    | P1       |
| 35    | **TS-E2E-DEMO-001**    | Demo: Delayed Foundation Scenario        | E2E         | @qa-agent       | P2       |
| 36    | **TS-E2E-DEMO-002**    | Demo: Budget Surprise Scenario           | E2E         | @qa-agent       | P2       |
| 37    | **TS-E2E-DEMO-003**    | Demo: Procurement Crisis Scenario        | E2E         | @qa-agent       | P2       |
| 38    | **TS-PERF-001**        | Performance Benchmark Tests              | Performance | @qa-agent       | P2       |
| 39    | **TS-INT-OFFLINE-001** | Offline Mode Tests                       | Integration | @frontend-tdd   | P2       |
| 40    | **TS-SEC-001**         | Security Penetration Tests               | Security    | @security-agent | P2       |

---

## 🟢 WEEK 4: REFACTOR Phase

_Execution Order: 41-45 | Goal: Optimize while keeping tests GREEN_

| Order | Test ID             | Name                         | Type     | Owner         | Priority |
| ----- | ------------------- | ---------------------------- | -------- | ------------- | -------- |
| 41    | **TS-REFACTOR-001** | Component Extraction Tests   | Refactor | @frontend-tdd | P2       |
| 42    | **TS-REFACTOR-002** | Hook Optimization Tests      | Refactor | @frontend-tdd | P2       |
| 43    | **TS-REFACTOR-003** | Performance Regression Tests | Refactor | @qa-agent     | P2       |
| 44    | **TS-REFACTOR-004** | Code Quality Tests           | Refactor | @backend-tdd  | P2       |
| 45    | **TS-REFACTOR-005** | Final E2E Validation         | E2E      | @qa-agent     | P0       |

---

## 📊 Priority Classification

### P0 - Must Pass (Block Release)

| Test ID         | Name                             | Week |
| --------------- | -------------------------------- | ---- |
| TS-E2E-J1-001   | First-Time Project Setup Journey | 1    |
| TS-E2E-J2-001   | Weekly Project Review Journey    | 1    |
| TS-E2E-J3-001   | Alert Resolution Journey         | 1    |
| TS-CT-API-001   | API Contract Tests               | 1    |
| TS-A11Y-001     | Accessibility Compliance Tests   | 1    |
| TS-REFACTOR-005 | Final E2E Validation             | 4    |

### P1 - Required for Production

| Test ID             | Name                     | Week |
| ------------------- | ------------------------ | ---- |
| TS-UD-WBS-001       | WBS Domain Logic         | 1    |
| TS-UA-WBS-001       | WBS Use Cases            | 1    |
| TS-UAD-WBS-TREE-001 | WBS Tree Component       | 1    |
| TS-UD-PROC-001      | Procurement Domain       | 3    |
| TS-UA-PROC-001      | Procurement Use Cases    | 3    |
| TS-UAD-PROC-001     | Procurement Components   | 2    |
| TS-INT-DB-WBS-001   | WBS Repository + DB      | 3    |
| TS-INT-MOD-WBS-001  | Cross-Module Integration | 3    |

### P2 - Nice to Have (Post-Release)

| Test ID            | Name                       | Week |
| ------------------ | -------------------------- | ---- |
| TS-E2E-DEMO-001    | Demo Scenario Tests        | 3    |
| TS-E2E-DEMO-002    | Demo: Budget Surprise      | 3    |
| TS-E2E-DEMO-003    | Demo: Procurement Crisis   | 3    |
| TS-INT-OFFLINE-001 | Offline Mode Tests         | 3    |
| TS-PERF-001        | Performance Benchmarks     | 3    |
| TS-SEC-001         | Security Penetration Tests | 3    |

---

## 🎯 Test Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  WEEK 1 (RED PHASE) - Days 1-7                                  │
│  ├─ 1. Contract Tests (TS-CT-WBS-API-001)                       │
│  ├─ 2. Domain Unit Tests (TS-UD-WBS-001)                        │
│  ├─ 3. Component Contracts (TS-UAD-WBS-TREE-001)                │
│  ├─ 4. Navigation Contracts (TS-INT-NAV-001)                    │
│  └─ 5. E2E Journey Contracts (TS-E2E-J1/2/3-001)                │
│  Status: ALL TESTS FAILING ✅                                   │
├─────────────────────────────────────────────────────────────────┤
│  WEEK 2 (GREEN PHASE) - Days 8-14                               │
│  ├─ 6. Filter Tests (TS-UAD-WBS-FILTER-001)                     │
│  ├─ 7. Search Tests (TS-UAD-WBS-SEARCH-001)                     │
│  ├─ 8. Color Coding (TS-UAD-WBS-COLOR-001)                      │
│  ├─ 9. CRUD Use Cases (TS-UA-WBS-CRUD-001)                      │
│  ├─ 10. Mobile Tests (TS-MOB-WBS-001)                           │
│  └─ 11. A11y Tests (TS-A11Y-WBS-001)                            │
│  Status: ALL TESTS PASSING ✅                                   │
├─────────────────────────────────────────────────────────────────┤
│  WEEK 3 (GREEN PHASE) - Days 15-21                              │
│  ├─ 12. Procurement Domain (TS-UD-PROC-001)                     │
│  ├─ 13. Procurement Use Cases (TS-UA-PROC-001)                  │
│  ├─ 14. Repository Integration (TS-INT-DB-XXX)                  │
│  └─ 15. Cross-Module Integration (TS-INT-MOD-XXX)               │
│  Status: ALL TESTS PASSING ✅                                   │
├─────────────────────────────────────────────────────────────────┤
│  WEEK 4 (REFACTOR PHASE) - Days 22-28                           │
│  ├─ 16. Extract Reusable Hooks                                  │
│  ├─ 17. Optimize Performance                                    │
│  ├─ 18. Improve Accessibility                                   │
│  ├─ 19. Add Mobile Optimizations                                │
│  └─ 20. Final E2E Validation                                    │
│  Status: ALL TESTS STILL PASSING ✅                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Test Execution Commands

### Backend Tests

```bash
# Run all WBS tests
pytest tests/modules/wbs -v

# Run specific suite
pytest tests/modules/wbs/domain/test_wbs_item_entity.py -v

# Run with coverage
pytest tests/modules/wbs --cov=src.wbs --cov-report=html

# Run contract tests only
pytest tests/modules/wbs/adapters/test_wbs_api_contract.py -v

# Watch mode (auto-run on changes)
ptw tests/modules/wbs
```

### Frontend Tests

```bash
# Run all component tests
npm test -- --testPathPattern="components/wbs"

# Run with coverage
npm test -- --coverage --collectCoverageFrom="components/wbs/**/*.tsx"

# Run specific test file
npm test -- WBSTree.test.tsx

# Run in watch mode
npm test -- --watch

# Run E2E tests
npm run test:e2e

# Run accessibility tests
npm test -- --testPathPattern="accessibility"
```

### All Tests

```bash
# Backend
pytest apps/api/tests --cov --cov-report=term-missing

# Frontend
npm test -- --coverage --watchAll=false

# E2E
npm run test:e2e

# Contract tests (both sides)
pytest tests/contract && npm run test:contract
```

---

## 📈 Coverage Requirements

### Minimum Coverage (Blocks PR)

- **Lines:** 80%
- **Branches:** 75%
- **Functions:** 85%

### Target Coverage (Goal)

- **Lines:** 90%
- **Branches:** 85%
- **Functions:** 95%

### Exemptions

- Auto-generated code (Orval, OpenAPI)
- Type definitions/interfaces
- index.ts re-export files

---

## ✅ Checklist by Phase

### Week 1 RED Phase Checklist

- [ ] WBS API schema validation (10 tests)
- [ ] Error response contracts (validation, 404, 400)
- [ ] Domain entity contracts (10 tests)
- [ ] Use case input/output contracts
- [ ] WBSTree prop interface (10 tests)
- [ ] WBSItemCard rendering contract
- [ ] Event handler contracts (onSelect, onExpand)
- [ ] State management contracts
- [ ] Cross-module navigation patterns (6 tests)
- [ ] API-to-frontend data flow
- [ ] State synchronization contracts

**Expected State at End of Week 1:**

- ✅ All contract tests written
- ✅ All tests FAILING (correct for RED phase)
- ✅ Test utilities and mocks created
- ✅ CI pipeline configured to run tests
- ⏳ Ready for GREEN phase (Week 2)

### Week 2 GREEN Phase Checklist

- [ ] Create WBS item with auto-generated code
- [ ] Create child item inherits parent code
- [ ] Validate maximum depth (level 4)
- [ ] Move item updates code and level
- [ ] Prevent circular references
- [ ] Delete with cascade removes descendants
- [ ] Delete without cascade fails if has children
- [ ] Filter by completion status
- [ ] Search by name/code/description
- [ ] Color-code by alert severity
- [ ] Keyboard navigation (Arrow keys, Tab, Enter)
- [ ] Touch targets minimum 44px
- [ ] Swipe gestures on mobile
- [ ] ARIA tree structure
- [ ] No accessibility violations

**Expected State at End of Week 2:**

- ✅ All Week 1 contract tests PASSING
- ✅ All Week 2 WBS tests PASSING
- ✅ WBS module functional
- ✅ Mobile responsive
- ✅ Accessible (WCAG AA)
- ⏳ Ready for Procurement (Week 3)

---

## 📚 References

- **Master Plan:** `docs/plans/tdd-testing/TDD_MASTER_PLAN.md`
- **Week 1 Tests:** `docs/plans/tdd-testing/TDD_WEEK1_TESTS.md`
- **Week 2 Tests:** `docs/plans/tdd-testing/TDD_WEEK2_TESTS.md`
- **Quick Reference:** `docs/plans/tdd-testing/TDD_QUICK_REFERENCE.md`
- **Backend Context:** `apps/api/AGENTS.md`
- **Architecture:** `context/PLAN_ARQUITECTURA_v2.1.md`

---

**Status:** Ready for Execution 🚀  
**Total Tests:** 580+ planned  
**Target Coverage:** 90% lines, 85% branches  
**Timeline:** 4 weeks  
**Next Step:** Begin Week 1 RED Phase with TS-CT-WBS-API-001

---

_Last Updated: 2026-02-15_  
_Maintained by: @planner-agent_
