# Migration Plan: Lovable to Next.js

## Overview
Migrating UI components from `apps/web-lovable` (React + Vite) to `apps/web` (Next.js 14) to consolidate development.

## Phase 1: Dependencies Installation

### Required npm packages to install in apps/web:
```bash
cd apps/web

# PDF handling
npm install pdfjs-dist@5.4.530 react-pdf@10.3.0

# Resizable panels
npm install react-resizable-panels@2.1.9

# Additional Radix UI components
npm install @radix-ui/react-accordion \
  @radix-ui/react-alert-dialog \
  @radix-ui/react-aspect-ratio \
  @radix-ui/react-avatar \
  @radix-ui/react-checkbox \
  @radix-ui/react-collapsible \
  @radix-ui/react-context-menu \
  @radix-ui/react-dropdown-menu \
  @radix-ui/react-hover-card \
  @radix-ui/react-label \
  @radix-ui/react-menubar \
  @radix-ui/react-navigation-menu \
  @radix-ui/react-popover \
  @radix-ui/react-progress \
  @radix-ui/react-radio-group \
  @radix-ui/react-scroll-area \
  @radix-ui/react-separator \
  @radix-ui/react-slider \
  @radix-ui/react-switch \
  @radix-ui/react-toast \
  @radix-ui/react-toggle \
  @radix-ui/react-toggle-group \
  @radix-ui/react-tooltip

# UI utilities
npm install sonner@1.7.4 \
  cmdk@1.1.1 \
  vaul@0.9.9 \
  embla-carousel-react@8.6.0 \
  recharts@2.15.4 \
  date-fns@3.6.0 \
  input-otp@1.4.2
```

## Phase 2: shadcn/ui Components to Copy

### From apps/web-lovable/src/components/ui/ to apps/web/components/ui/:

**Priority 1 (Required for Evidence Viewer):**
- resizable.tsx
- skeleton.tsx
- separator.tsx
- alert.tsx
- alert-dialog.tsx
- dropdown-menu.tsx
- checkbox.tsx
- textarea.tsx
- label.tsx
- scroll-area.tsx
- toast.tsx / toaster.tsx / use-toast.ts
- sonner.tsx
- tooltip.tsx
- document-tabs.tsx (custom)
- recent-documents.tsx (custom)

**Priority 2 (Required for Dashboard):**
- progress.tsx
- avatar.tsx
- chart.tsx (for recharts integration)
- skeleton.tsx

**Priority 3 (Nice to have):**
- accordion.tsx
- breadcrumb.tsx
- calendar.tsx
- carousel.tsx
- collapsible.tsx
- command.tsx
- context-menu.tsx
- drawer.tsx
- form.tsx
- hover-card.tsx
- input-otp.tsx
- menubar.tsx
- navigation-menu.tsx
- pagination.tsx
- popover.tsx
- radio-group.tsx
- slider.tsx
- switch.tsx
- toggle.tsx
- toggle-group.tsx

## Phase 3: PDF Viewer Components

### Directory structure to create:
```
apps/web/components/pdf/
├── PDFViewer.tsx
├── HighlightLayer.tsx
├── HighlightSearchBar.tsx
└── pdf-viewer.css
```

### Types to copy:
```
apps/web/types/
├── highlight.ts
├── document.ts
└── backend.ts (if not exists)
```

### Utils to copy:
```
apps/web/lib/
└── exportUtils.ts
```

## Phase 4: Custom Hooks Migration

### Hooks to migrate from apps/web-lovable/src/hooks/:
- useProjectDocuments.ts
- useDocumentEntities.ts
- useDocumentAlerts.ts
- useDocumentBlob.ts
- useHighlightSearch.ts
- useRecentDocuments.ts
- useViewerPersistence.ts

### Location in Next.js:
```
apps/web/hooks/
└── [all hooks above]
```

**Important:** These hooks need to be adapted to:
1. Use Next.js API routes instead of mock data
2. Use real backend endpoints from apps/api
3. Handle "use client" directive for client-side hooks

## Phase 5: Dashboard Components

### Components to copy:
```
apps/web-lovable/src/components/dashboard/
├── GaugeChart.tsx → apps/web/components/dashboard/
├── KPICards.tsx → apps/web/components/dashboard/
├── ActivityTimeline.tsx → apps/web/components/dashboard/
├── TopAlertsCard.tsx → apps/web/components/dashboard/
└── RecentProjectsCard.tsx → apps/web/components/dashboard/
```

### Data files:
```
apps/web-lovable/src/data/mockData.ts → apps/web/lib/mockData.ts (temporary)
```

## Phase 6: Evidence Viewer Migration

### Steps:
1. Copy full page component:
   - apps/web-lovable/src/pages/EvidenceViewer.tsx →
   - apps/web/app/(app)/projects/[id]/evidence/page.tsx

2. Add "use client" directive at top
3. Adapt imports for Next.js structure
4. Replace mock data with real API calls
5. Add project ID from Next.js params

## Phase 7: Dashboard Page Update

### Steps:
1. Copy dashboard page logic from apps/web-lovable/src/pages/Dashboard.tsx
2. Update apps/web/app/(app)/page.tsx
3. Add "use client" directive
4. Integrate with real backend API for KPIs

## Phase 8: API Integration

### Backend endpoints needed:
```
GET /api/v1/projects/{id}/documents - list documents
GET /api/v1/documents/{id}/entities - get entities/highlights
GET /api/v1/documents/{id}/alerts - get document alerts
GET /api/v1/documents/{id}/download - download PDF blob
GET /api/v1/projects/{id}/stats - get project KPIs
GET /api/v1/projects/{id}/activities - get recent activities
```

### Create API client helpers in:
```
apps/web/lib/api/documents.ts
apps/web/lib/api/projects.ts
```

## Migration Order

1. ✅ Install dependencies
2. ✅ Copy Priority 1 UI components
3. ✅ Copy PDF viewer components and CSS
4. ✅ Copy types
5. ✅ Migrate hooks (adapted for Next.js)
6. ✅ Migrate Evidence Viewer page
7. ✅ Copy Dashboard components
8. ✅ Update Dashboard page
9. ✅ Create API client wrappers
10. ✅ Test all migrated components
11. ✅ Remove mock data dependencies

## Post-Migration

- Keep apps/web-lovable for UI prototyping
- Sync new designs manually from Lovable to Next.js
- Document component API differences between both apps

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
