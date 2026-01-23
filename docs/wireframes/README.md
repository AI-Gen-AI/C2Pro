# C2Pro Wireframes - Core Views

**Project:** C2Pro - Contract Intelligence Platform
**Version:** 1.0
**Created:** January 21, 2026
**Status:** ✅ Complete

---

## Overview

This directory contains detailed wireframes for the 6 core views of the C2Pro application. These wireframes define the user interface, interactions, and user experience for the MVP (Minimum Viable Product) release.

**Purpose:** Provide comprehensive UX/UI specifications for frontend development, ensuring consistent implementation across all views.

---

## Wireframe Documents

### 1. [Dashboard](./01-dashboard.md)
**Route:** `/dashboard`
**Purpose:** Executive overview with key metrics and coherence scores

**Key Features:**
- Organization info and AI budget tracking
- Quick stats cards (projects, documents, alerts, users)
- Recent projects table with coherence scores
- Critical alerts panel
- Coherence score distribution chart
- AI usage tracking chart

**Priority:** P0 (Critical)
**Complexity:** Medium

---

### 2. [Projects List](./02-projects.md)
**Route:** `/projects`
**Purpose:** Comprehensive project management with filtering and search

**Key Features:**
- Full-text search across projects
- Advanced filters (status, type, score, date)
- Bulk actions (archive, delete, export)
- Sortable table with pagination
- Card view for mobile
- Empty states

**Priority:** P0 (Critical)
**Complexity:** Medium

---

### 3. [Evidence Viewer](./03-evidence-viewer.md)
**Route:** `/projects/{id}/evidence`
**Purpose:** Visualize complete traceability chain from Contract → WBS → BOM

**Key Features:**
- Full evidence chain visualization
- Contract clause → WBS → Schedule → BOM → Stakeholders
- Bidirectional navigation
- Recommended actions
- History and notes
- Source attribution

**Priority:** P0 (Critical)
**Complexity:** High

---

### 4. [Alerts Panel](./04-alerts.md)
**Route:** `/alerts`
**Purpose:** Alert management with filtering, resolution, and notifications

**Key Features:**
- Quick stats by severity and status
- Advanced filtering and search
- Bulk actions
- Alert detail modal with evidence summary
- Resolution workflow
- Activity log
- Grouping options

**Priority:** P0 (Critical)
**Complexity:** High

---

### 5. [Stakeholders Map](./05-stakeholders.md)
**Route:** `/projects/{id}/stakeholders`
**Purpose:** Power/Interest matrix with AI-powered extraction

**Key Features:**
- Interactive Power/Interest matrix (2x2 grid)
- AI extraction from contracts and org charts
- Drag-and-drop repositioning
- Stakeholder detail panel
- RACI responsibilities view
- Implicit needs inference
- Alert notifications tracking

**Priority:** P0 (Critical)
**Complexity:** High

---

### 6. [RACI Matrix](./06-raci-matrix.md)
**Route:** `/projects/{id}/raci`
**Purpose:** Responsibility assignment matrix with human-in-loop approval

**Key Features:**
- Interactive WBS × Stakeholders matrix
- AI-generated RACI assignments
- Human-in-loop approval workflow
- Validation rules (exactly one A, at least one R)
- Cell detail with AI rationale
- Issue detection and reporting
- Export to Excel/CSV/PDF

**Priority:** P0 (Critical)
**Complexity:** Very High

---

## Design System

### Color Palette

#### Primary Colors
- **Primary Blue**: `#0066CC` - Actions, links, active states
- **Success Green**: `#00AA00` - Positive scores (81-100), success states
- **Warning Yellow**: `#FFAA00` - Fair scores (61-80), warnings
- **Error Red**: `#CC0000` - Poor scores (0-60), errors, critical alerts
- **Neutral Gray**: `#666666` - Text, borders, disabled states

#### Severity Colors
- **Critical**: `#CC0000` (Red) - Urgent action required
- **High**: `#FFAA00` (Yellow) - Important, needs attention
- **Medium**: `#0066CC` (Blue) - Standard issue
- **Low**: `#999999` (Light Gray) - Minor, informational

#### Status Colors
- **Active/Open**: `#0066CC` (Blue)
- **Completed/Resolved**: `#00AA00` (Green)
- **Draft/Pending**: `#CCCCCC` (Gray)
- **Archived**: `#333333` (Dark Gray)

### Typography

**Font Family:** System font stack for performance
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

**Font Sizes:**
- **H1 (Page Title)**: 24px, Bold
- **H2 (Section Heading)**: 20px, Bold
- **H3 (Subsection)**: 18px, Semibold
- **Body**: 14px, Regular
- **Small**: 12px, Regular
- **Tiny**: 10px, Regular

**Line Heights:**
- **Headings**: 1.2
- **Body**: 1.5
- **Compact (tables)**: 1.3

### Spacing

**Base Unit:** 8px (for consistent spacing)

- **XS**: 4px
- **S**: 8px
- **M**: 16px
- **L**: 24px
- **XL**: 32px
- **XXL**: 48px

**Component Spacing:**
- **Card Padding**: 24px (L)
- **Card Gap**: 16px (M)
- **Section Gap**: 32px (XL)
- **Input Padding**: 12px
- **Button Padding**: 12px 24px

### Icons

**Icon Library:** Lucide React (consistent, modern icons)
**Icon Sizes:**
- **Small**: 16px
- **Medium**: 20px (default)
- **Large**: 24px
- **XLarge**: 32px

### Shadows

**Elevation:**
- **Low (Cards)**: `0 1px 3px rgba(0, 0, 0, 0.12)`
- **Medium (Modals)**: `0 4px 6px rgba(0, 0, 0, 0.16)`
- **High (Dropdowns)**: `0 8px 16px rgba(0, 0, 0, 0.20)`

### Border Radius

- **Small**: 4px (buttons, inputs)
- **Medium**: 8px (cards)
- **Large**: 12px (modals)
- **Circle**: 50% (avatars)

---

## Accessibility (WCAG 2.1 AA)

### Color Contrast
- **Normal Text**: Minimum 4.5:1 contrast ratio
- **Large Text**: Minimum 3:1 contrast ratio
- **Icons**: Minimum 3:1 contrast ratio

### Keyboard Navigation
- **Tab Order**: Logical flow through interactive elements
- **Focus Indicators**: Visible outline on focused elements
- **Shortcuts**: Common actions (Ctrl+S to save, Esc to close)

### Screen Reader Support
- **ARIA Labels**: All interactive elements
- **ARIA Live Regions**: Dynamic content updates
- **Semantic HTML**: Proper heading hierarchy (H1→H2→H3)
- **Alt Text**: All images and icons

---

## Implementation Priority

### Sprint 2 (Weeks 3-4)
1. 🔄 **Evidence Viewer**: Basic chain visualization
2. 🔄 **Alerts Panel**: List and detail view

### Sprint 3 (Weeks 5-6)
3. ⏳ **Stakeholders Map**: Matrix view
4. ⏳ **RACI Matrix**: Display only (no editing)

### Sprint 4 (Weeks 7-8)
5. ⏳ **Evidence Viewer**: Full interactivity
6. ⏳ **Stakeholders**: AI extraction
7. ⏳ **RACI**: Editing and approval workflow

---

## Resources

- [C2Pro Product Roadmap](../ROADMAP_v2.3.0.md)
- [Sprint 1 Plan](../SPRINT_1_PLAN.md)
- [Sprint 1 Completed](../SPRINT_1_COMPLETED.md)
- [Chronogram Master](../C2PRO_CRONOGRAMA_MAESTRO_v1.0.csv)

---

**Status:** ✅ Complete - All 6 core view wireframes documented
**Ready for:** Frontend development (Sprint 2-4)