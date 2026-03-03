# C2Pro Frontend Testing Plan
## Comprehensive QA Strategy for Next.js Application

> **Expert QA Analysis**: This document establishes a complete testing strategy for the C2Pro frontend application, following industry best practices and modern testing methodologies.

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Tech Stack Analysis](#tech-stack-analysis)
3. [Testing Strategy Overview](#testing-strategy-overview)
4. [Test Pyramid](#test-pyramid)
5. [Detailed Testing Plans](#detailed-testing-plans)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Tooling & Configuration](#tooling--configuration)
8. [Success Metrics](#success-metrics)

---

## Executive Summary

### Current State
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Testing Status**: ⚠️ No existing frontend tests
- **Backend Coverage**: ✅ ~185 tests (70%+ coverage)

### Testing Goals
- Achieve **80%+ code coverage** across all layers
- Implement **CI/CD integration** for automated testing
- Establish **zero-regression policy** for critical paths
- Enable **continuous quality monitoring**

### Priority Levels
🔴 **Critical** - Must implement first (2-3 weeks)
🟡 **High** - Core functionality (3-4 weeks)
🟢 **Medium** - Enhanced coverage (4-6 weeks)
⚪ **Low** - Nice to have (6+ weeks)

---

## Tech Stack Analysis

### Detected Technologies
```
Frontend Framework: Next.js (App Router)
Language: TypeScript/TSX
Styling: TailwindCSS (likely)
State Management: TBD (React Query/Zustand/Context?)
API Client: Custom (/lib/api-client.ts)
Auth: Custom JWT (/lib/auth.ts)
```

### Application Structure
```
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (app)/
│   │   ├── layout.tsx
│   │   ├── page.tsx (dashboard home)
│   │   └── projects/
│   │       ├── page.tsx (list)
│   │       ├── new/page.tsx
│   │       └── [id]/
│   │           ├── page.tsx (detail)
│   │           ├── analysis/page.tsx
│   │           └── documents/page.tsx
│   ├── api/[...proxy]/route.ts
│   └── layout.tsx (root)
└── lib/
    ├── api-client.ts
    ├── auth.ts
    └── utils.ts
```

---

## Testing Strategy Overview

### 🎯 Test Pyramid Approach

```
                    /\
                   /  \
                  /E2E \         10% - Critical user journeys
                 /------\
                /        \
               /Integration\    30% - Page flows & API integration
              /------------\
             /              \
            /  Unit Tests    \  60% - Components, hooks, utilities
           /------------------\
```

### Testing Layers

#### 1️⃣ **Unit Tests** (60% of tests)
- React components in isolation
- Custom hooks
- Utility functions
- Form validation logic
- State management logic

#### 2️⃣ **Integration Tests** (30% of tests)
- Page-level components
- API client integration
- Authentication flows
- Form submissions
- Navigation flows

#### 3️⃣ **End-to-End Tests** (10% of tests)
- Critical user journeys
- Multi-page workflows
- Real browser interactions
- Database state verification

---

## Test Pyramid

### Layer 1: Unit Tests (60%) - 🔴 Critical Priority

**Target**: ~150-180 unit tests

#### A. Component Tests
Test individual React components in isolation using React Testing Library.

**Authentication Components** (15 tests):
```typescript
// Login Form Component
- ✅ Renders email and password fields
- ✅ Shows validation errors for invalid email
- ✅ Shows validation errors for short password
- ✅ Disables submit button while submitting
- ✅ Calls onSubmit with correct data
- ✅ Shows error message on failed login
- ✅ Redirects to dashboard on successful login

// Register Form Component (8 tests)
- ✅ All form fields render correctly
- ✅ Password strength indicator works
- ✅ Password confirmation validation
- ✅ Terms acceptance required
- ✅ Company name validation
- ✅ Successful registration flow
- ✅ Duplicate email error handling
- ✅ Form reset after error
```

**Project Components** (25 tests):
```typescript
// ProjectCard Component (8 tests)
- ✅ Displays project name, code, and status
- ✅ Shows coherence score with correct color
- ✅ Renders status badge with correct color
- ✅ Click navigates to project detail
- ✅ Shows project type icon
- ✅ Displays truncated description
- ✅ Shows "No description" when empty
- ✅ Accessibility: proper ARIA labels

// ProjectList Component (8 tests)
- ✅ Renders empty state when no projects
- ✅ Renders list of projects correctly
- ✅ Pagination controls work correctly
- ✅ Loading state shows skeleton
- ✅ Error state shows error message
- ✅ Search input filters projects
- ✅ Status filter works correctly
- ✅ Sorting by different fields

// ProjectForm Component (9 tests)
- ✅ All form fields render
- ✅ Required field validation
- ✅ Project code format validation
- ✅ Budget validation (numeric, positive)
- ✅ Date picker works correctly
- ✅ Project type dropdown
- ✅ Auto-generated code option
- ✅ Save draft functionality
- ✅ Submit creates project
```

**Dashboard Components** (12 tests):
```typescript
// StatsCard Component (4 tests)
- ✅ Displays title and value
- ✅ Shows trend indicator (up/down/neutral)
- ✅ Renders icon correctly
- ✅ Click handler works

// ProjectsTable Component (8 tests)
- ✅ Renders table headers
- ✅ Displays project rows
- ✅ Row click navigates to detail
- ✅ Action menu works (edit, delete, archive)
- ✅ Bulk selection checkbox
- ✅ Sort by column
- ✅ Empty state
- ✅ Loading state
```

**UI Components** (20 tests):
```typescript
// Button Component (6 tests)
- ✅ Renders with correct text
- ✅ Handles click events
- ✅ Disabled state works
- ✅ Loading state shows spinner
- ✅ Different variants (primary, secondary, danger)
- ✅ Different sizes (sm, md, lg)

// Modal Component (5 tests)
- ✅ Opens and closes correctly
- ✅ Click outside closes modal
- ✅ ESC key closes modal
- ✅ Focus trap works
- ✅ Body scroll lock when open

// Toast/Notification (4 tests)
- ✅ Shows success toast
- ✅ Shows error toast
- ✅ Auto-dismiss after timeout
- ✅ Manual dismiss works

// FileUpload Component (5 tests)
- ✅ Drag and drop works
- ✅ File picker works
- ✅ File type validation
- ✅ File size validation
- ✅ Multiple file upload
```

#### B. Custom Hooks Tests (18 tests)
```typescript
// useAuth Hook (6 tests)
- ✅ Returns null when not authenticated
- ✅ Returns user when authenticated
- ✅ Login updates auth state
- ✅ Logout clears auth state
- ✅ Token refresh works automatically
- ✅ Redirects to login on 401

// useProjects Hook (6 tests)
- ✅ Fetches projects on mount
- ✅ Loading state during fetch
- ✅ Error state on failed fetch
- ✅ Pagination works correctly
- ✅ Filters apply correctly
- ✅ Refetch on create/update/delete

// useDebounce Hook (2 tests)
- ✅ Debounces value changes
- ✅ Cleanup on unmount

// useLocalStorage Hook (4 tests)
- ✅ Reads from localStorage
- ✅ Writes to localStorage
- ✅ Handles JSON parsing errors
- ✅ Syncs across tabs
```

#### C. Utility Function Tests (25 tests)
```typescript
// api-client.ts (10 tests)
- ✅ GET request with auth header
- ✅ POST request with body
- ✅ PUT request updates resource
- ✅ DELETE request
- ✅ Handles 401 and redirects to login
- ✅ Handles 403 forbidden
- ✅ Handles 404 not found
- ✅ Handles 500 server error
- ✅ Retry logic on network error
- ✅ Request/response interceptors

// auth.ts (8 tests)
- ✅ getToken returns token from localStorage
- ✅ setToken stores token
- ✅ removeToken clears token
- ✅ isAuthenticated checks token validity
- ✅ decodeToken extracts user info
- ✅ isTokenExpired checks expiration
- ✅ refreshToken calls refresh endpoint
- ✅ getUser returns user from token

// utils.ts (7 tests)
- ✅ formatCurrency formats correctly
- ✅ formatDate handles different formats
- ✅ truncateText with ellipsis
- ✅ getCoherenceScoreColor returns correct color
- ✅ getStatusColor returns correct color
- ✅ validateEmail regex works
- ✅ cn (classnames) merges correctly
```

#### D. Validation & Form Logic Tests (15 tests)
```typescript
// Form Validators (15 tests)
- ✅ Email validation (valid/invalid formats)
- ✅ Password strength validation
- ✅ Required field validation
- ✅ Min/max length validation
- ✅ Numeric field validation
- ✅ URL validation
- ✅ Date range validation
- ✅ File type validation
- ✅ Custom validation rules
- ✅ Async validation (email uniqueness)
```

---

### Layer 2: Integration Tests (30%) - 🟡 High Priority

**Target**: ~75-90 integration tests

#### A. Page Integration Tests (35 tests)

**Authentication Pages** (8 tests):
```typescript
// Login Page Integration
- ✅ Full login flow with API mock
- ✅ Redirects to dashboard on success
- ✅ Shows error message on failure
- ✅ "Remember me" checkbox persists

// Register Page Integration
- ✅ Full registration flow
- ✅ Creates user and tenant
- ✅ Redirects to onboarding
- ✅ Handles duplicate email error
```

**Project Pages** (15 tests):
```typescript
// Projects List Page
- ✅ Loads and displays projects from API
- ✅ Pagination works with API
- ✅ Search filters projects via API
- ✅ Status filter updates URL and fetches
- ✅ Create new project button navigates

// Project Detail Page
- ✅ Loads project details from API
- ✅ Shows 404 for non-existent project
- ✅ Edit button opens edit form
- ✅ Delete button shows confirmation

// Project Create/Edit Page
- ✅ Form submission creates project
- ✅ Form submission updates project
- ✅ Validation errors from API displayed
- ✅ Cancel button navigates back
- ✅ Auto-save draft functionality

// Project Analysis Page
- ✅ Displays coherence analysis
- ✅ Shows document discrepancies
```

**Dashboard Page** (5 tests):
```typescript
// Dashboard Integration
- ✅ Loads user stats on mount
- ✅ Loads recent projects
- ✅ Stats cards show correct data
- ✅ Quick actions work
- ✅ Notifications display
```

#### B. Navigation & Routing Tests (10 tests)
```typescript
// Navigation Tests
- ✅ Unauthenticated user redirects to login
- ✅ Authenticated user can access dashboard
- ✅ Sidebar navigation works
- ✅ Breadcrumbs show correct path
- ✅ Back button navigation
- ✅ Deep link to project works
- ✅ 404 page for invalid routes
- ✅ URL state persistence (filters, pagination)
- ✅ Route guards work correctly
- ✅ Nested route rendering
```

#### C. API Integration Tests (15 tests)
```typescript
// API Client Integration
- ✅ Authentication endpoints
  - Login, Register, Logout, Refresh Token
- ✅ Projects endpoints
  - List, Create, Read, Update, Delete
- ✅ Document endpoints
  - Upload, Download, Delete
- ✅ Analysis endpoints
  - Trigger analysis, Get results
- ✅ User profile endpoints
  - Get profile, Update profile
- ✅ Error handling for all endpoints
- ✅ Loading states during requests
- ✅ Optimistic updates
```

#### D. Form Flow Tests (12 tests)
```typescript
// Multi-step Forms
- ✅ Registration multi-step form
- ✅ Project creation wizard
- ✅ Document upload flow
- ✅ Settings update flow
- ✅ Form state persistence
- ✅ Validation across steps
- ✅ Navigate between steps
- ✅ Submit final step
- ✅ Error recovery
- ✅ Unsaved changes warning
- ✅ Auto-save functionality
- ✅ Resume interrupted flow
```

#### E. Authentication Flow Tests (8 tests)
```typescript
// Auth Flow Integration
- ✅ Login → Dashboard flow
- ✅ Register → Onboarding → Dashboard
- ✅ Logout clears state and redirects
- ✅ Token refresh on expired token
- ✅ Remember me functionality
- ✅ Password reset flow (if implemented)
- ✅ Session timeout handling
- ✅ Concurrent tab logout sync
```

---

### Layer 3: End-to-End Tests (10%) - 🟡 High Priority

**Target**: ~25-30 E2E tests

#### Critical User Journeys (12 tests)
```typescript
// Journey 1: New User Onboarding
- ✅ Register → Verify Email → Create First Project → Upload Documents

// Journey 2: Daily Project Manager Workflow
- ✅ Login → View Dashboard → Check Alerts → Open Project → Review Analysis

// Journey 3: Project Creation & Document Upload
- ✅ Create Project → Set Details → Upload Contract → Upload Schedule → Run Analysis

// Journey 4: Coherence Analysis Review
- ✅ Open Project → View Coherence Score → Drill into Discrepancies → Export Report

// Journey 5: Team Collaboration
- ✅ Invite Team Member → Assign Project → Review Changes → Approve

// Journey 6: Account Management
- ✅ Login → Settings → Update Profile → Change Password → Logout

// Journey 7: Error Recovery
- ✅ Failed Upload → Retry → Success
- ✅ Session Expired → Redirect to Login → Login → Return to Page

// Journey 8: Multi-tenant Isolation
- ✅ User A Cannot Access User B's Projects

// Journey 9: Search & Filter
- ✅ Search Projects → Apply Filters → Sort → Open Project

// Journey 10: Mobile Responsiveness
- ✅ Login on Mobile → Navigate Dashboard → View Project
```

#### Performance Tests (6 tests)
```typescript
// Load Performance
- ✅ Dashboard loads in < 2 seconds
- ✅ Project list with 100 items loads in < 3 seconds
- ✅ Document upload < 10MB completes in < 5 seconds
- ✅ Analysis results load in < 5 seconds

// Stress Tests
- ✅ Multiple concurrent document uploads
- ✅ Rapid navigation doesn't break state
```

#### Cross-Browser Tests (6 tests)
```typescript
// Browser Compatibility
- ✅ Chrome (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Edge (latest)
- ✅ Mobile Safari (iOS)
- ✅ Mobile Chrome (Android)
```

---

## Detailed Testing Plans

### 🔴 Phase 1: Critical Path Testing (Week 1-2)

#### Priority 1: Authentication (5 days)
```bash
□ Setup testing environment (Vitest + RTL)
□ Write unit tests for auth utilities
□ Write component tests for login/register
□ Write integration tests for auth flow
□ Write E2E test for complete auth journey
```

**Files to Create**:
```
apps/web/__tests__/
├── unit/
│   ├── lib/
│   │   ├── auth.test.ts
│   │   └── api-client.test.ts
│   └── components/
│       ├── LoginForm.test.tsx
│       └── RegisterForm.test.tsx
├── integration/
│   └── pages/
│       ├── login.test.tsx
│       └── register.test.tsx
└── e2e/
    └── auth.spec.ts
```

#### Priority 2: Projects CRUD (5 days)
```bash
□ Unit tests for project components
□ Integration tests for project pages
□ E2E tests for project creation flow
□ E2E tests for project update/delete
```

**Files to Create**:
```
apps/web/__tests__/
├── unit/
│   └── components/
│       ├── ProjectCard.test.tsx
│       ├── ProjectList.test.tsx
│       └── ProjectForm.test.tsx
├── integration/
│   └── pages/
│       ├── projects-list.test.tsx
│       ├── project-detail.test.tsx
│       └── project-create.test.tsx
└── e2e/
    └── projects.spec.ts
```

---

### 🟡 Phase 2: Core Features (Week 3-4)

#### Priority 3: Dashboard & Navigation (4 days)
```bash
□ Dashboard component tests
□ Navigation component tests
□ Layout component tests
□ Sidebar and breadcrumb tests
```

#### Priority 4: Document Management (4 days)
```bash
□ File upload component tests
□ Document list component tests
□ Document viewer tests
□ Upload flow integration tests
```

#### Priority 5: Analysis Features (4 days)
```bash
□ Coherence score components
□ Analysis results components
□ Alert/warning components
□ Discrepancy detail tests
```

---

### 🟢 Phase 3: Enhanced Coverage (Week 5-6)

#### Priority 6: Forms & Validation (3 days)
```bash
□ All form field components
□ Validation utility tests
□ Form state management tests
□ Multi-step form tests
```

#### Priority 7: UI Components Library (3 days)
```bash
□ Button, Input, Select tests
□ Modal, Dialog, Drawer tests
□ Toast, Alert, Badge tests
□ Table, Pagination tests
```

#### Priority 8: Advanced Features (3 days)
```bash
□ Search functionality tests
□ Filter and sort tests
□ Export functionality tests
□ Notification system tests
```

---

### ⚪ Phase 4: Quality Assurance (Week 7+)

#### Priority 9: Non-Functional Testing
```bash
□ Accessibility (a11y) tests with axe-core
□ Visual regression tests with Percy/Chromatic
□ Performance tests with Lighthouse CI
□ Security tests (XSS, CSRF prevention)
```

#### Priority 10: Edge Cases & Error Scenarios
```bash
□ Network error handling
□ Offline mode (if applicable)
□ Timeout handling
□ Race condition tests
□ Memory leak tests
```

---

## Tooling & Configuration

### Recommended Test Stack

```json
{
  "devDependencies": {
    // Test Runners
    "vitest": "^1.0.0",              // Fast unit test runner
    "@playwright/test": "^1.40.0",   // E2E testing

    // Testing Libraries
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.1.0",
    "@testing-library/user-event": "^14.5.0",

    // Mocking & Utilities
    "msw": "^2.0.0",                 // API mocking
    "@faker-js/faker": "^8.0.0",     // Test data generation

    // Coverage & Reporting
    "@vitest/coverage-v8": "^1.0.0",
    "@vitest/ui": "^1.0.0",

    // Visual & A11y Testing
    "@axe-core/playwright": "^4.8.0", // Accessibility
    "@percy/playwright": "^1.0.0",    // Visual regression

    // Utilities
    "happy-dom": "^12.0.0",           // DOM environment
    "@types/testing-library__jest-dom": "^6.0.0"
  }
}
```

### Configuration Files to Create

#### 1. `vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        '.next/',
        '**/*.config.*',
        '**/types/**',
        '**/*.d.ts',
      ],
      statements: 80,
      branches: 75,
      functions: 80,
      lines: 80,
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
})
```

#### 2. `vitest.setup.ts`
```typescript
import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

// Mock environment variables
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1'
```

#### 3. `playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './__tests__/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
```

#### 4. `__tests__/helpers/test-utils.tsx`
```typescript
import { render, RenderOptions } from '@testing-library/react'
import { ReactElement } from 'react'

// Add custom providers (Auth, Theme, etc.)
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>
}

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
```

#### 5. `__tests__/mocks/handlers.ts` (MSW)
```typescript
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Auth handlers
  http.post('/api/v1/auth/login', () => {
    return HttpResponse.json({
      user: { id: '1', email: 'test@example.com' },
      tokens: { access_token: 'mock-token' },
    })
  }),

  // Projects handlers
  http.get('/api/v1/projects', () => {
    return HttpResponse.json({
      items: [
        { id: '1', name: 'Test Project', status: 'draft' }
      ],
      total: 1,
      page: 1,
      page_size: 20,
    })
  }),
]
```

---

## Success Metrics

### Coverage Targets
```
Unit Tests:        80%+ code coverage
Integration Tests: 75%+ critical paths covered
E2E Tests:         100% happy paths covered
Visual Regression: 100% pages covered
Accessibility:     0 critical violations
```

### Quality Gates (CI/CD)
```bash
✅ All tests must pass
✅ Coverage thresholds met
✅ No new accessibility violations
✅ Performance budget maintained:
   - First Contentful Paint < 1.5s
   - Time to Interactive < 3.0s
   - Lighthouse Score > 90
```

### Test Execution Time Targets
```
Unit tests:        < 30 seconds
Integration tests: < 2 minutes
E2E tests:         < 10 minutes
Total suite:       < 15 minutes
```

---

## Implementation Roadmap

### Week 1-2: Foundation (🔴 Critical)
- [ ] Setup test infrastructure (Vitest, Playwright, MSW)
- [ ] Create test utilities and helpers
- [ ] Setup CI/CD pipeline for tests
- [ ] Write authentication tests (30 tests)
- [ ] **Deliverable**: Auth flow fully tested

### Week 3-4: Core Features (🟡 High)
- [ ] Projects CRUD tests (50 tests)
- [ ] Dashboard tests (20 tests)
- [ ] Navigation tests (15 tests)
- [ ] **Deliverable**: Core app functionality tested

### Week 5-6: Components & Forms (🟢 Medium)
- [ ] UI component library tests (40 tests)
- [ ] Form validation tests (25 tests)
- [ ] Document management tests (20 tests)
- [ ] **Deliverable**: 80% code coverage achieved

### Week 7-8: Quality & Polish (⚪ Low)
- [ ] Visual regression tests (all pages)
- [ ] Accessibility audit and fixes
- [ ] Performance optimization
- [ ] Cross-browser testing
- [ ] **Deliverable**: Production-ready test suite

---

## Test Examples

### Example 1: Unit Test (Component)
```typescript
// __tests__/unit/components/ProjectCard.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/tests/helpers/test-utils'
import { ProjectCard } from '@/components/ProjectCard'

describe('ProjectCard', () => {
  const mockProject = {
    id: '1',
    name: 'Test Project',
    code: 'TEST-001',
    status: 'active',
    coherence_score: 85,
  }

  it('renders project information correctly', () => {
    render(<ProjectCard project={mockProject} />)

    expect(screen.getByText('Test Project')).toBeInTheDocument()
    expect(screen.getByText('TEST-001')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
  })

  it('navigates to project detail on click', async () => {
    const { user } = render(<ProjectCard project={mockProject} />)
    const mockPush = vi.fn()

    vi.mocked(useRouter).mockReturnValue({ push: mockPush })

    await user.click(screen.getByRole('article'))

    expect(mockPush).toHaveBeenCalledWith('/projects/1')
  })
})
```

### Example 2: Integration Test (Page)
```typescript
// __tests__/integration/pages/projects-list.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/tests/helpers/test-utils'
import { server } from '@/tests/mocks/server'
import { http, HttpResponse } from 'msw'
import ProjectsPage from '@/app/(app)/projects/page'

describe('Projects List Page', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/projects', () => {
        return HttpResponse.json({
          items: [
            { id: '1', name: 'Project 1', status: 'active' },
            { id: '2', name: 'Project 2', status: 'draft' },
          ],
          total: 2,
        })
      })
    )
  })

  it('loads and displays projects from API', async () => {
    render(<ProjectsPage />)

    // Loading state
    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    // Wait for projects to load
    await waitFor(() => {
      expect(screen.getByText('Project 1')).toBeInTheDocument()
      expect(screen.getByText('Project 2')).toBeInTheDocument()
    })
  })

  it('filters projects by status', async () => {
    const { user } = render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText('Project 1')).toBeInTheDocument()
    })

    // Click status filter
    await user.click(screen.getByRole('combobox', { name: /status/i }))
    await user.click(screen.getByRole('option', { name: /active/i }))

    // Should only show active projects
    await waitFor(() => {
      expect(screen.getByText('Project 1')).toBeInTheDocument()
      expect(screen.queryByText('Project 2')).not.toBeInTheDocument()
    })
  })
})
```

### Example 3: E2E Test (User Journey)
```typescript
// __tests__/e2e/project-creation.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Project Creation Journey', () => {
  test('user can create a new project from scratch', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('[name="email"]', 'test@example.com')
    await page.fill('[name="password"]', 'TestPassword123!')
    await page.click('button[type="submit"]')

    // Navigate to projects
    await expect(page).toHaveURL('/dashboard')
    await page.click('text=Projects')

    // Click create new project
    await page.click('text=New Project')
    await expect(page).toHaveURL('/projects/new')

    // Fill form
    await page.fill('[name="name"]', 'New Construction Project')
    await page.fill('[name="code"]', 'CONS-2024-001')
    await page.selectOption('[name="project_type"]', 'construction')
    await page.fill('[name="location"]', 'Madrid, Spain')
    await page.fill('[name="budget_planned"]', '1000000')

    // Submit
    await page.click('button:has-text("Create Project")')

    // Verify success
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+$/)
    await expect(page.locator('h1')).toContainText('New Construction Project')

    // Verify toast notification
    await expect(page.locator('[role="alert"]')).toContainText('Project created successfully')
  })
})
```

---

## Best Practices

### 1. Test Naming Convention
```typescript
describe('ComponentName', () => {
  it('does something when condition', () => {
    // test
  })
})
```

### 2. AAA Pattern (Arrange-Act-Assert)
```typescript
it('test description', () => {
  // Arrange - Setup test data
  const mockData = { ... }

  // Act - Execute the functionality
  render(<Component data={mockData} />)

  // Assert - Verify the result
  expect(screen.getByText('...')).toBeInTheDocument()
})
```

### 3. DRY with Test Factories
```typescript
// __tests__/factories/project.factory.ts
export const createMockProject = (overrides = {}) => ({
  id: faker.string.uuid(),
  name: faker.company.name(),
  code: faker.string.alphanumeric(8).toUpperCase(),
  status: 'draft',
  ...overrides,
})
```

### 4. Test Isolation
```typescript
beforeEach(() => {
  // Reset state before each test
  cleanup()
  vi.clearAllMocks()
})
```

### 5. Accessibility-First Testing
```typescript
// Prefer semantic queries
screen.getByRole('button', { name: /submit/i })
screen.getByLabelText(/email address/i)

// Instead of
screen.getByTestId('submit-button')
```

---

## Continuous Improvement

### Monthly Reviews
- Review test failures and flakiness
- Update coverage targets
- Refactor slow tests
- Update documentation

### Quarterly Goals
- Reduce test execution time by 10%
- Increase coverage by 5%
- Eliminate all flaky tests
- Zero critical bugs in production

---

## Resources & References

### Documentation
- [Vitest Docs](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Docs](https://playwright.dev/)
- [MSW Documentation](https://mswjs.io/)

### Learning Resources
- Kent C. Dodds - "Testing JavaScript"
- Test Trophy Testing Philosophy
- React Testing Best Practices

---

## Appendix

### A. Test File Naming Conventions
```
Component tests:    ComponentName.test.tsx
Hook tests:         useHookName.test.ts
Utility tests:      utilityName.test.ts
Page tests:         page-name.test.tsx
E2E tests:          feature-name.spec.ts
```

### B. Git Commit Messages
```
test: add unit tests for ProjectCard component
test: add integration tests for project creation flow
test: add e2e tests for authentication journey
test: fix flaky test in project list
test: update snapshots after UI changes
```

### C. CI/CD Pipeline Integration
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm ci
      - run: npm run test:unit
      - run: npm run test:coverage

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm ci
      - run: npx playwright install
      - run: npm run test:e2e
```

---

**Document Version**: 1.0
**Last Updated**: January 2026
**Author**: Expert QA Engineer
**Status**: Ready for Implementation 🚀
