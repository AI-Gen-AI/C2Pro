# TDD Testing Master Plan - Quick Reference

**For:** QA Agent, Backend-TDD Agent, Frontend-TDD Agent  
**Status:** Ready for Execution

---

## TDD Workflow Overview

```
Week 1 (RED)    →   Week 2-3 (GREEN)   →   Week 4 (REFACTOR)
Write Tests          Make Tests Pass         Optimize Code
(FAILING)            (PASSING)               (Still PASSING)
     ↓                    ↓                       ↓
  Contract Tests     Fake-It Pattern          Extract Hooks
  Schema Tests       Minimal Logic            Performance
  Interface Tests    Incremental Build        Clean Code
```

---

## Critical Test Suites

### P0 - Must Pass Before Release

| Suite ID      | Name                     | Type     | Count | Owner         |
| ------------- | ------------------------ | -------- | ----- | ------------- |
| TS-E2E-J1-001 | Project Setup Journey    | E2E      | 15    | @qa-agent     |
| TS-E2E-J2-001 | Weekly Review Journey    | E2E      | 12    | @qa-agent     |
| TS-E2E-J3-001 | Alert Resolution Journey | E2E      | 10    | @qa-agent     |
| TS-CT-API-001 | API Contract Tests       | Contract | 25    | @backend-tdd  |
| TS-A11Y-001   | Accessibility Tests      | A11y     | 20    | @frontend-tdd |

### P1 - Required for Production

| Suite ID            | Name                  | Type      | Count | Owner         |
| ------------------- | --------------------- | --------- | ----- | ------------- |
| TS-UD-WBS-001       | WBS Domain Logic      | Unit      | 30    | @backend-tdd  |
| TS-UA-WBS-001       | WBS Use Cases         | Unit      | 25    | @backend-tdd  |
| TS-UAD-WBS-TREE-001 | WBS Tree Component    | Component | 20    | @frontend-tdd |
| TS-UD-PROC-001      | Procurement Domain    | Unit      | 25    | @backend-tdd  |
| TS-UA-PROC-001      | Procurement Use Cases | Unit      | 20    | @backend-tdd  |

---

## Test Execution Commands

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

## Test Coverage Requirements

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

## RED Phase Guidelines

### Writing Failing Tests

**DO:**

- ✅ Write test before implementation
- ✅ Test one thing per test case
- ✅ Use descriptive test names
- ✅ Include assertions for error cases
- ✅ Mock external dependencies

**DON'T:**

- ❌ Skip failing tests
- ❌ Write implementation first
- ❌ Test multiple concerns
- ❌ Ignore error paths
- ❌ Use real databases

### Example RED Phase Test

```python
def test_create_wbs_item_generates_code():
    """RED: Test before implementation - should FAIL"""
    # Arrange
    request = CreateWBSItemRequest(name="Test Item")
    use_case = CreateWBSItemUseCase(mock_repo)

    # Act
    result = use_case.execute(request)

    # Assert - This will FAIL until implemented
    assert result.code is not None  # FAILS: AttributeError
    assert result.code == "1"       # FAILS: code not generated
```

---

## GREEN Phase Guidelines

### Making Tests Pass

**Step 1: Fake It**

```python
def execute(self, request):
    # Just return hardcoded value to pass test
    return WBSItem(
        id=str(uuid4()),
        code="1",  # Hardcoded
        name=request.name,
        level=1
    )
```

**Step 2: Triangulate**

```python
# Add more test cases to force generalization
def test_create_second_root_item():
    # Should generate "3" if "1" and "2" exist
    ...

def test_create_child_item():
    # Should generate "1.1" if parent is "1"
    ...
```

**Step 3: Real Implementation**

```python
def execute(self, request):
    if request.parent_id:
        parent = self.repo.get_by_id(request.parent_id)
        siblings = self.repo.get_children(parent.id)
        code = self._generate_child_code(parent.code, siblings)
    else:
        existing = self.repo.get_root_items()
        code = self._generate_root_code(existing)

    return WBSItem(..., code=code, ...)
```

---

## REFACTOR Phase Guidelines

### Safe Refactoring

**DO:**

- ✅ Keep all tests passing
- ✅ Extract reusable components
- ✅ Rename for clarity
- ✅ Optimize performance
- ✅ Add comments

**DON'T:**

- ❌ Change test assertions
- ❌ Remove tests without reason
- ❌ Refactor without tests
- ❌ Change behavior

### Refactoring Checklist

- [ ] All tests still pass
- [ ] Code coverage maintained
- [ ] No lint errors
- [ ] Performance benchmarks improved
- [ ] Documentation updated

---

## Mock Data Reference

### WBS Mock Data Structure

```typescript
export const mockWBSItem = {
  id: "wbs-001",
  code: "2.1.3.1",
  name: "Reinforcement",
  description: "Steel rebar installation",
  level: 4,
  parentId: "wbs-parent-001",
  projectId: "proj-001",
  startDate: "2025-05-01",
  endDate: "2025-05-15",
  budget: { amount: 450000, currency: "EUR" },
  completion: 45,
  linkedClauses: ["clause-001", "clause-002"],
  children: [],
  alerts: [{ rule: "R12", severity: "high", message: "No budget allocated" }],
};

export const mockWBSHierarchy = [
  {
    id: "1",
    code: "1",
    name: "Preliminaries",
    level: 1,
    children: [
      {
        id: "1.1",
        code: "1.1",
        name: "Site Setup",
        level: 2,
        children: [
          {
            id: "1.1.1",
            code: "1.1.1",
            name: "Site Office",
            level: 3,
            completion: 100,
            children: [],
          },
        ],
      },
    ],
  },
  // ... more items
];
```

### Procurement Mock Data

```typescript
export const mockBOMItem = {
  id: "bom-001",
  wbsItemId: "wbs-002-1-3-1",
  material: "Steel Rebar Grade B500B",
  quantity: 1250,
  unit: "tonnes",
  unitCost: { amount: 850, currency: "EUR" },
  totalCost: { amount: 1062500, currency: "EUR" },
  supplier: "ArcelorMittal",
  incoterm: "CIF",
  supplierLocation: "Germany",
  customsRequired: false,
};

export const mockLeadTimeResult = {
  bomItemId: "bom-001",
  productionDays: 45,
  transitDays: 12,
  customsDays: 0,
  bufferDays: 7,
  totalDays: 69,
  requiredOnSite: "2025-05-15",
  orderByDate: "2025-03-07",
  riskLevel: "medium",
  incoterm: "CIF",
};

export const mockProcurementPlan = [
  {
    id: "plan-001",
    bomItemId: "bom-001",
    material: "Steel Rebar Grade B500B",
    quantity: 1250,
    orderDate: "2025-03-07",
    deliveryDate: "2025-05-08",
    requiredOnSite: "2025-05-15",
    status: "planned",
    isOnCriticalPath: true,
  },
  // ... more items
];
```

---

## Common Issues & Solutions

### Issue: Test is Flaky

**Solution:**

- Use `async/await` consistently
- Mock timers properly
- Wait for DOM updates
- Avoid race conditions

```typescript
// Bad
expect(screen.getByText("Loading")).toBeInTheDocument();

// Good
await waitFor(() => {
  expect(screen.getByText("Loaded")).toBeInTheDocument();
});
```

### Issue: Test Fails on CI but Passes Locally

**Solution:**

- Check timezone settings
- Mock Date.now()
- Use fixed test data
- Increase timeouts

```typescript
// Mock dates
jest.useFakeTimers();
jest.setSystemTime(new Date("2025-01-15"));

// Cleanup
afterAll(() => {
  jest.useRealTimers();
});
```

### Issue: Can't Test Async Operations

**Solution:**

- Use `waitFor` from testing-library
- Mock API calls
- Use `findBy` queries (auto-wait)

```typescript
// Bad
const button = screen.getByText("Save"); // May not exist yet

// Good
const button = await screen.findByText("Save"); // Waits up to 1s
```

---

## Test Utilities

### Backend Test Fixtures

```python
# conftest.py

@pytest.fixture
def mock_wbs_repo():
    repo = Mock()
    repo.get_by_id.return_value = MockWBSItem()
    repo.save.return_value = MockWBSItem()
    return repo

@pytest.fixture
def test_client():
    from src.main import app
    return TestClient(app)
```

### Frontend Test Utilities

```typescript
// test-utils.tsx

import { render as rtlRender } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function render(ui, { providerProps, ...options } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return rtlRender(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>,
    options
  );
}

// Mock service worker setup
export { server } from './mocks/server';
```

---

## Reporting & Metrics

### Daily Test Metrics

```bash
# Generate test report
pytest --html=report.html --self-contained-html

# Coverage badge
pytest --cov-report=xml
# Upload to codecov
```

### Weekly Review Checklist

- [ ] All P0 tests passing
- [ ] Coverage above minimum thresholds
- [ ] No flaky tests
- [ ] E2E journey tests passing
- [ ] Accessibility tests passing
- [ ] Mobile tests passing

---

## Next Steps

1. **Week 1:** @qa-agent writes all contract tests (RED Phase)
2. **Week 2:** @backend-tdd + @frontend-tdd make tests pass (GREEN Phase)
3. **Week 3:** Continue implementation + add procurement tests
4. **Week 4:** @qa-agent runs E2E + @backend-tdd/@frontend-tdd refactor

---

## Resources

- **Master Plan:** `docs/plans/ux-implementation/MASTER_PLAN_v1.0.md`
- **Week 1 Tests:** `docs/plans/tdd-testing/TDD_WEEK1_TESTS.md`
- **Week 2 Tests:** `docs/plans/tdd-testing/TDD_WEEK2_TESTS.md`
- **API Spec:** `docs/plans/ux-implementation/openapi-wbs-procurement.yaml`
- **Architecture:** `docs/plans/ux-implementation/ARCHITECTURE_DIAGRAMS.md`

---

**Status:** Ready for Execution 🚀  
**Total Tests:** 580+ planned  
**Target Coverage:** 90% lines, 85% branches  
**Timeline:** 4 weeks

_All agents: Begin with Week 1 RED Phase tests_
