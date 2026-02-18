# C2Pro Complete Development Flow - Figma Design System
**Version:** 2.0
**Date:** 2026-02-18
**Status:** 🔄 In Development
**Project URL:** https://www.figma.com/design/AOkZSMoQXt3dI8FOJ3AjCD/C2Pro

---

## 📋 Table of Contents

1. [Development Flow Overview](#development-flow-overview)
2. [Design System Specifications](#design-system-specifications)
3. [Stage 1: Authentication & Onboarding](#stage-1-authentication--onboarding)
4. [Stage 2: Dashboard & Navigation](#stage-2-dashboard--navigation)
5. [Stage 3: Project Management](#stage-3-project-management)
6. [Stage 4: Document Management](#stage-4-document-management)
7. [Stage 5: Coherence Analysis](#stage-5-coherence-analysis)
8. [Stage 6: Evidence Chain](#stage-6-evidence-chain)
9. [Stage 7: Alerts & Notifications](#stage-7-alerts--notifications)
10. [Stage 8: Stakeholders Management](#stage-8-stakeholders-management)
11. [Stage 9: RACI Matrix](#stage-9-raci-matrix)
12. [Figma Organization Structure](#figma-organization-structure)
13. [Implementation Checklist](#implementation-checklist)

---

## Development Flow Overview

### 🎯 Complete User Journey Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                    C2PRO DEVELOPMENT FLOW STAGES                    │
└─────────────────────────────────────────────────────────────────────┘

STAGE 1: AUTHENTICATION & ONBOARDING
├─ 1.1: Login Page
├─ 1.2: Registration Page
├─ 1.3: Organization Setup
└─ 1.4: Welcome Onboarding

STAGE 2: DASHBOARD & NAVIGATION
├─ 2.1: Main Dashboard
├─ 2.2: Sidebar Navigation
├─ 2.3: Top Navigation Bar
└─ 2.4: User Profile Menu

STAGE 3: PROJECT MANAGEMENT
├─ 3.1: Projects List (Browse)
├─ 3.2: Create Project Modal
├─ 3.3: Project Detail Page
├─ 3.4: Project Settings
└─ 3.5: Bulk Actions

STAGE 4: DOCUMENT MANAGEMENT
├─ 4.1: Document Upload Page
├─ 4.2: Document Library
├─ 4.3: PDF Viewer with Annotations
├─ 4.4: OCR Processing Status
└─ 4.5: Document Details

STAGE 5: COHERENCE ANALYSIS
├─ 5.1: Coherence Score Dashboard
├─ 5.2: Category Breakdown View
├─ 5.3: Analysis Details
├─ 5.4: Score Reasoning (LLM)
└─ 5.5: Radar Chart Visualization

STAGE 6: EVIDENCE CHAIN
├─ 6.1: Evidence Viewer
├─ 6.2: Chain Visualization (Contract→WBS→Schedule→BOM)
├─ 6.3: Bidirectional Navigation
├─ 6.4: Recommended Actions
└─ 6.5: Evidence History & Notes

STAGE 7: ALERTS & NOTIFICATIONS
├─ 7.1: Alerts Dashboard
├─ 7.2: Alert Filtering & Search
├─ 7.3: Alert Detail Modal
├─ 7.4: Resolution Workflow
└─ 7.5: Activity Log

STAGE 8: STAKEHOLDERS MANAGEMENT
├─ 8.1: Stakeholders List
├─ 8.2: Power/Interest Matrix
├─ 8.3: Stakeholder Detail Panel
├─ 8.4: AI Extraction Results
└─ 8.5: RACI Responsibilities

STAGE 9: RACI MATRIX
├─ 9.1: RACI Matrix View (WBS × Stakeholders)
├─ 9.2: Cell Editor with Validations
├─ 9.3: AI Rationale Explanation
├─ 9.4: Approval Workflow
└─ 9.5: Matrix Export (Excel/PDF)

ADMIN & SETTINGS
├─ 10.1: Organization Settings
├─ 10.2: User Management
├─ 10.3: Audit Logs
└─ 10.4: Integration Settings
```

### 🔄 User Flow Diagram

```
START
  ↓
LOGIN / REGISTER (Stage 1)
  ↓
ONBOARDING → ORG SETUP
  ↓
DASHBOARD (Stage 2) ←─────────────────────────┐
  ↓                                             │
BROWSE PROJECTS (Stage 3) ←┐                   │
  ↓                        │                   │
CREATE PROJECT ─────────→ │                   │
  ↓                        │                   │
PROJECT DETAIL PAGE ←──────┤                   │
  ↓                        │                   │
UPLOAD DOCUMENTS (Stage 4) │                   │
  ↓                        │                   │
DOCUMENT LIBRARY ──────────┤                   │
  ↓                        │                   │
COHERENCE ANALYSIS (Stage 5)                   │
  ↓                        │                   │
VIEW EVIDENCE CHAIN (Stage 6)                  │
  ↓                        │                   │
CHECK ALERTS (Stage 7) ────┤                   │
  ↓                        │                   │
MANAGE STAKEHOLDERS (Stage 8)                  │
  ↓                        │                   │
CONFIGURE RACI (Stage 9) ──┤                   │
  ↓                        │                   │
EXPORT / SHARE RESULTS ────┤                   │
  ↓                        │                   │
LOOP TO DASHBOARD ─────────┼───────────────────┘
  ↓
END
```

---

## Design System Specifications

### 🎨 Color Palette

#### Primary Colors
| Color | Hex Code | Usage | RGB |
|-------|----------|-------|-----|
| Primary Blue | `#0066CC` | Actions, links, primary buttons, active states | 0, 102, 204 |
| Success Green | `#00AA00` | Good scores (81-100), success states, completed status | 0, 170, 0 |
| Warning Yellow | `#FFAA00` | Fair scores (61-80), warnings, pending status | 255, 170, 0 |
| Error Red | `#CC0000` | Poor scores (0-60), critical alerts, errors | 204, 0, 0 |
| Neutral Gray | `#666666` | Text, borders, disabled states | 102, 102, 102 |

#### Severity Colors
| Severity | Color | Hex Code | Usage |
|----------|-------|----------|-------|
| Critical | Red | `#CC0000` | Urgent action required |
| High | Yellow | `#FFAA00` | Important, needs attention |
| Medium | Blue | `#0066CC` | Standard issue |
| Low | Light Gray | `#999999` | Minor, informational |

#### Status Colors
| Status | Color | Hex Code |
|--------|-------|----------|
| Active/Open | Blue | `#0066CC` |
| Completed/Resolved | Green | `#00AA00` |
| Draft/Pending | Gray | `#CCCCCC` |
| Archived | Dark Gray | `#333333` |

#### Neutral Scale
- **Background**: `#FFFFFF` (White)
- **Surface**: `#F5F5F5` (Light Gray)
- **Border**: `#E0E0E0` (Medium Gray)
- **Text Primary**: `#222222` (Dark Gray)
- **Text Secondary**: `#666666` (Medium Gray)
- **Text Disabled**: `#999999` (Light Gray)

### 📐 Typography

**Font Family:**
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

**Font Sizes & Weights:**

| Level | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| H1 | 32px | Bold (700) | 1.2 (38px) | Page titles, hero sections |
| H2 | 24px | Bold (700) | 1.2 (29px) | Section headings |
| H3 | 20px | Semibold (600) | 1.3 (26px) | Subsections |
| H4 | 16px | Semibold (600) | 1.4 (22px) | Card titles |
| Body Large | 16px | Regular (400) | 1.5 (24px) | Main content |
| Body | 14px | Regular (400) | 1.5 (21px) | Standard text |
| Body Small | 12px | Regular (400) | 1.5 (18px) | Secondary text |
| Caption | 12px | Regular (400) | 1.4 (17px) | Labels, hints |
| Tiny | 10px | Regular (400) | 1.3 (13px) | Badges, tags |

### 📏 Spacing System

**Base Unit:** 8px (all spacing is a multiple of 8px)

| Spacing | Value | Usage |
|---------|-------|-------|
| XS | 4px | Tight spacing between inline elements |
| S | 8px | Padding in small components, tight spacing |
| M | 16px | Standard padding in cards, spacing between sections |
| L | 24px | Padding in large components, spacing between major sections |
| XL | 32px | Large spacing between page sections |
| XXL | 48px | Extra large spacing |

**Component Spacing:**
- **Card Padding**: 24px (L)
- **Card Margin Gap**: 16px (M)
- **Section Gap**: 32px (XL)
- **Input Height**: 40px
- **Input Padding**: 12px (horizontal), 10px (vertical)
- **Button Height**: 40px (default), 32px (small)
- **Button Padding**: 12px × 24px
- **Icon Size**: 20px (default)

### 🎯 Corner Radius

| Size | Value | Usage |
|------|-------|-------|
| Small | 4px | Buttons, inputs, badges |
| Medium | 8px | Cards, modals |
| Large | 12px | Panels, large containers |
| Circle | 50% | Avatars, profile pictures |

### 🌟 Shadows & Elevation

| Level | Box Shadow | Usage | Elevation |
|-------|-----------|-------|-----------|
| Low | `0 1px 3px rgba(0, 0, 0, 0.12)` | Cards, subtle elevation | 1 |
| Medium | `0 4px 6px rgba(0, 0, 0, 0.16)` | Modals, popovers | 2 |
| High | `0 8px 16px rgba(0, 0, 0, 0.20)` | Dropdowns, notifications | 3 |
| Extra High | `0 12px 24px rgba(0, 0, 0, 0.25)` | Full-screen modals | 4 |

### 🔤 Icon System

**Icon Library:** Lucide React
**Font Size:** 20px (default)

| Size | Value | Usage |
|------|-------|-------|
| Small | 16px | Inline icons, badges |
| Medium | 20px | Default, most UI icons |
| Large | 24px | Primary action icons |
| XLarge | 32px | Hero icons, large buttons |

**Common Icons Used:**
- `Menu`, `X` - Navigation & close
- `ChevronDown`, `ChevronUp`, `ChevronRight` - Expandable sections
- `Settings`, `Sliders` - Configuration
- `FileText`, `Upload`, `Download` - Document operations
- `AlertCircle`, `AlertTriangle` - Warnings & errors
- `CheckCircle`, `X Circle` - Status indicators
- `Bell` - Notifications
- `Users`, `User` - People management
- `Grid3x3`, `List` - View toggles
- `Search`, `Filter` - Search & filtering
- `Plus`, `Trash2`, `Edit2` - CRUD operations

### ⚡ Component Specifications

#### Buttons

**Primary Button (Default Action)**
- Background: `#0066CC` (Primary Blue)
- Text Color: `#FFFFFF` (White)
- Padding: 12px × 24px
- Height: 40px
- Border Radius: 4px
- Font: 14px, Semibold
- Hover: Background darkens to `#0052A3`
- Active: Background darkens further to `#003E7A`
- Disabled: Background `#CCCCCC`, Text `#999999`

**Secondary Button**
- Background: `#F5F5F5` (Light Gray)
- Text Color: `#222222` (Dark Gray)
- Padding: 12px × 24px
- Border: 1px solid `#E0E0E0`
- Height: 40px
- Border Radius: 4px
- Hover: Background `#EBEBEB`

**Danger Button**
- Background: `#CC0000` (Error Red)
- Text Color: `#FFFFFF` (White)
- Padding: 12px × 24px
- Height: 40px
- Hover: Background darkens

**Button Sizes:**
- **Large**: 48px height, 16px × 32px padding
- **Default**: 40px height, 12px × 24px padding
- **Small**: 32px height, 8px × 16px padding

#### Input Fields

**Text Input**
- Border: 1px solid `#E0E0E0`
- Border Radius: 4px
- Padding: 12px (horizontal), 10px (vertical)
- Height: 40px
- Font: 14px, Regular
- Focus: Border color changes to `#0066CC`, shadow `0 0 0 3px rgba(0, 102, 204, 0.1)`
- Placeholder: `#999999` text color
- Disabled: Background `#F5F5F5`, Border `#CCCCCC`

**Select Dropdown**
- Similar to text input
- Dropdown arrow icon on the right
- Focus: Same as text input

#### Cards

**Default Card**
- Background: `#FFFFFF` (White)
- Border: 1px solid `#E0E0E0`
- Border Radius: 8px
- Padding: 24px
- Shadow: Low elevation `0 1px 3px rgba(0, 0, 0, 0.12)`
- Margin Gap: 16px

**Elevated Card**
- Same as default but with Medium elevation shadow

#### Tables

**Table Header**
- Background: `#F5F5F5` (Light Gray)
- Border Bottom: 1px solid `#E0E0E0`
- Font: 12px, Semibold
- Text Color: `#222222`
- Padding: 12px

**Table Rows**
- Border Bottom: 1px solid `#E0E0E0`
- Padding: 16px 12px
- Alternating backgrounds: None (clean look)
- Hover: Background `#F9F9F9`
- Height: 48px (default)

#### Badges & Tags

**Badge (Status)**
- Padding: 4px × 8px
- Border Radius: 4px
- Font: 10px, Semibold
- Height: 20px

Badge Types:
- **Success**: Background `#00AA00`, Text `#FFFFFF`
- **Warning**: Background `#FFAA00`, Text `#222222`
- **Error**: Background `#CC0000`, Text `#FFFFFF`
- **Info**: Background `#0066CC`, Text `#FFFFFF`
- **Default**: Background `#E0E0E0`, Text `#222222`

#### Modals & Dialogs

**Modal Container**
- Background: `#FFFFFF`
- Border Radius: 8px
- Shadow: High elevation
- Max Width: 600px (standard)
- Padding: 32px
- Overlay: `rgba(0, 0, 0, 0.5)` (50% opacity dark overlay)

**Modal Header**
- Border Bottom: 1px solid `#E0E0E0`
- Padding Bottom: 16px
- Margin Bottom: 24px
- Font: 20px, Bold

**Modal Footer**
- Border Top: 1px solid `#E0E0E0`
- Padding Top: 16px
- Margin Top: 32px
- Alignment: Right-aligned buttons

#### Breadcrumbs

- Font: 12px, Regular
- Color: `#666666`
- Separator: `/` (gray text)
- Active Item: `#0066CC` (primary blue)
- Hover: Underline on links

#### Alerts & Messages

**Alert Container**
- Border Radius: 8px
- Padding: 16px
- Border Left: 4px solid (color varies)
- Icon: 20px, on the left
- Font: 14px, Regular

Alert Types:
- **Success**: Border `#00AA00`, Icon green, Background light green `#F0FFF0`
- **Warning**: Border `#FFAA00`, Icon yellow, Background light yellow `#FFFFF0`
- **Error**: Border `#CC0000`, Icon red, Background light red `#FFF0F0`
- **Info**: Border `#0066CC`, Icon blue, Background light blue `#F0F7FF`

---

## Stage 1: Authentication & Onboarding

### 1.1 Login Page

**Route:** `/login`
**Purpose:** User authentication
**Mobile Support:** Yes (responsive)

**Screen Layout:**
- **Header**: C2Pro logo + "Contract Intelligence Platform" tagline
- **Form Section**:
  - Email input field
  - Password input field
  - "Remember me" checkbox
  - "Forgot password?" link
  - "Sign In" button (primary)
  - "Don't have an account? Register" link
- **Footer**: Terms of Service + Privacy Policy links

**Interactions:**
- Form validation on blur
- Show/hide password toggle
- Loading state on "Sign In" button
- Error messages below fields
- Redirect to dashboard on successful login

**Components Used:**
- Input fields (email, password)
- Checkbox
- Primary button
- Links
- Form validation UI

---

### 1.2 Registration Page

**Route:** `/register`
**Purpose:** New user/organization registration

**Screen Layout:**
- **Header**: C2Pro logo
- **Form Section**:
  - Organization name input
  - First name input
  - Last name input
  - Email input
  - Password input (with strength indicator)
  - Confirm password input
  - Terms checkbox
  - "Create Account" button
  - "Already have account? Sign In" link
- **Right Side** (Desktop only): Benefits/features list

**Interactions:**
- Real-time password strength indicator
- Confirm password validation
- Email verification step
- Create organization workspace
- Multi-step form (optional)

**Components Used:**
- Input fields
- Password strength meter
- Checkbox
- Primary button
- Links

---

### 1.3 Organization Setup

**Route:** `/onboarding/org-setup`
**Purpose:** Configure organization settings

**Screen Layout:**
- **Progress Indicator**: Step 1 of 3
- **Form Section**:
  - Organization name (pre-filled)
  - Industry dropdown
  - Organization size dropdown
  - Country/Region selector
  - Logo upload
  - Website URL (optional)
  - Next button
  - Skip button

**Interactions:**
- Logo preview
- Dropdown selections
- Form validation
- Progress tracking

**Components Used:**
- Input fields
- Dropdowns
- File upload
- Buttons
- Progress indicator

---

### 1.4 Welcome Onboarding

**Route:** `/onboarding/welcome`
**Purpose:** Guide user through key features

**Screen Layout (Multi-step):**

**Step 1: Welcome**
- Hero image/illustration
- Welcome message
- Key features list (3-4 items)
- "Get Started" button

**Step 2: Dashboard Overview**
- Feature explanation
- Screenshot/illustration
- "Next" button

**Step 3: Upload Documents**
- Feature explanation
- File type examples
- "Complete Setup" button

**Interactions:**
- Step navigation (previous/next)
- Skip onboarding option
- Video tutorial links (future)

**Components Used:**
- Illustrations
- Cards
- Buttons
- Progress indicator

---

## Stage 2: Dashboard & Navigation

### 2.1 Main Dashboard

**Route:** `/dashboard`
**Purpose:** Executive overview with key metrics

**Screen Layout:**

**Top Section:**
- Organization name + logo
- AI Budget tracker (visual progress bar)
- Date range selector
- Quick filters

**Quick Stats Cards (4 cards):**
1. Total Projects: Large number + trend
2. Active Documents: Large number + trend
3. Critical Alerts: Large number + color-coded
4. Team Members: Large number + small avatars

**Main Content:**

**Section 1: Recent Projects**
- Table with columns: Project Name, Status, Coherence Score, Last Updated
- Show 5-6 most recent projects
- "View All" link
- Sortable columns

**Section 2: Critical Alerts**
- Card-based list of 3-5 critical alerts
- Alert type icon
- Alert title + brief description
- Severity badge
- "Resolve" quick action
- "View All" link

**Section 3: Analytics**
- Coherence Score Distribution (pie chart)
- AI Usage Tracking (bar chart showing daily usage)
- Cost projection

**Footer:**
- Useful links (docs, support, feedback)

**Interactions:**
- Clickable project rows (go to project detail)
- Drill-down on alerts (show detail modal)
- Responsive grid layout for mobile
- Refresh data option
- Export dashboard option

**Components Used:**
- Stats cards
- Tables
- Charts (pie, bar)
- Alerts
- Badges
- Buttons

---

### 2.2 Sidebar Navigation

**Display:** Left sidebar, collapsible on mobile

**Navigation Items:**
1. **Dashboard** - Home icon + "Dashboard"
2. **Projects** - Folder icon + "Projects"
3. **Documents** - FileText icon + "Documents"
4. **Coherence** - Target icon + "Coherence"
5. **Evidence** - Link icon + "Evidence"
6. **Alerts** - Bell icon + "Alerts"
7. **Stakeholders** - Users icon + "Stakeholders"
8. **RACI** - Grid icon + "RACI Matrix"

**Bottom Section:**
- Divider
- Settings - Sliders icon + "Settings"
- Help - HelpCircle icon + "Help"
- Logout - LogOut icon + "Logout"

**Interactions:**
- Highlight active route
- Collapse/expand sidebar (mobile)
- Hover effects on items
- Smooth transitions

**Components Used:**
- Navigation list
- Icons
- Badges (for notifications)
- Collapse/expand toggle

---

### 2.3 Top Navigation Bar

**Display:** Across top of page

**Left Section:**
- Menu icon (mobile only)
- Breadcrumbs (current page hierarchy)

**Center Section:**
- Search bar (global search across projects/documents)

**Right Section:**
- Notifications bell icon (with badge showing count)
- User avatar dropdown
- Organization switcher (if multi-org)

**Interactions:**
- Search autocomplete
- Notification dropdown
- User profile menu

**Components Used:**
- Search input
- Icon buttons
- Breadcrumbs
- Dropdown menu

---

### 2.4 User Profile Menu

**Trigger:** Click on user avatar

**Menu Items:**
- User name (display as header)
- Email address
- Divider
- "Profile Settings"
- "Organization Settings"
- "Preferences"
- Divider
- "Documentation"
- "Report Bug"
- Divider
- "Logout"

**Interactions:**
- Click items to navigate
- Close menu on selection or click outside

**Components Used:**
- Dropdown menu
- Menu items with icons
- Dividers

---

## Stage 3: Project Management

### 3.1 Projects List (Browse)

**Route:** `/projects`
**Purpose:** Browse and manage all projects

**Screen Layout:**

**Top Section:**
- Page title "Projects"
- Search box (full-text search)
- Filter button (opens filter panel)
- View toggle buttons (Table/Card view)
- "Create Project" primary button

**Filter Panel (collapsible):**
- Status filter (dropdown: All, Active, Archived)
- Score range slider (0-100)
- Document count (min/max)
- Date range picker
- Apply/Reset buttons

**Main Content:**

**Table View:**
- Columns: Project Name, Status, Coherence Score, Documents, Users, Last Updated, Actions
- Row height: 48px
- Hover effects on rows
- Pagination: Show 10/25/50 rows per page
- Total count at bottom

**Card View (mobile):**
- Cards in 2x grid (1x on mobile)
- Project name
- Status badge
- Coherence score with gauge
- Quick action buttons

**Interactions:**
- Click row to go to project detail
- Click on score to open analysis
- Bulk actions checkbox
- Sort by clicking headers
- Filter + search combination
- Pagination controls

**Components Used:**
- Search input
- Filter panel with controls
- Table with pagination
- Status badges
- Score gauge
- Action buttons

---

### 3.2 Create Project Modal

**Trigger:** Click "Create Project" button

**Modal Layout:**
- **Header**: "Create New Project" + Close button
- **Form**:
  - Project name input (required)
  - Project description (textarea, optional)
  - Industry dropdown
  - Client name input
  - Project manager selector (dropdown)
  - Start date picker
  - Expected end date picker
  - Budget input (optional)
  - Team members selector (multi-select)
- **Footer**: "Create" button + "Cancel" button

**Interactions:**
- Form validation on submit
- Date pickers with calendar UI
- Multi-select with search
- Loading state on create
- Success notification on create
- Close modal and go to project detail

**Components Used:**
- Input fields
- Dropdowns
- Date pickers
- Multi-select
- Buttons
- Modal

---

### 3.3 Project Detail Page

**Route:** `/projects/:id`
**Purpose:** View and manage individual project

**Screen Layout:**

**Header Section:**
- Project name (large)
- Status badge
- Coherence score (large gauge)
- Quick actions (Edit, Archive, Delete)
- Breadcrumbs: Dashboard > Projects > [Project Name]

**Tabs/Navigation:**
1. **Overview** (default)
2. **Analysis**
3. **Documents**
4. **Evidence**
5. **Alerts**
6. **Settings**

**Tab 1: Overview**
- Project info cards:
  - Status: [Current Status]
  - Client: [Client Name]
  - Project Manager: [Name] + Avatar
  - Start Date: [Date]
  - End Date: [Date]
  - Budget: [Amount]

- Key Metrics:
  - Coherence Score (large gauge)
  - Category breakdown (bar chart or cards)
  - Documents count
  - Team members count

- Recent Activity:
  - Timeline of recent actions
  - Document uploads
  - Score updates
  - Team member additions

**Tab 2: Analysis**
- Link to Stage 5 (Coherence Analysis)

**Tab 3: Documents**
- Link to Stage 4 (Document Management)

**Tab 4: Evidence**
- Link to Stage 6 (Evidence Chain)

**Tab 5: Alerts**
- Link to Stage 7 (Alerts)

**Tab 6: Settings**
- Project name (editable)
- Description (editable)
- Team members (add/remove)
- Delete project button (danger zone)

**Interactions:**
- Tab navigation
- Edit inline fields
- Open modals for team management
- Navigate to sub-pages

**Components Used:**
- Tabs
- Info cards
- Gauge charts
- Buttons
- Forms
- Timeline

---

### 3.4 Project Settings

**Route:** `/projects/:id/settings`
**Purpose:** Configure project settings

**Screen Layout:**
- Page title: "Project Settings"
- Settings sections:

**Section 1: Basic Info**
- Project name (editable input)
- Description (editable textarea)
- Save button

**Section 2: Team Management**
- Team members list (table)
- Columns: Name, Email, Role, Actions
- Add member button (opens modal)
- Remove member button (confirmation)

**Section 3: Integrations**
- Connected integrations list
- Add integration button
- Configuration options

**Section 4: Danger Zone**
- Archive project button (warning)
- Delete project button (danger)
- Confirmation modals

**Interactions:**
- Inline editing
- Add/remove team members
- Confirmation dialogs for destructive actions

**Components Used:**
- Input fields
- Textareas
- Tables
- Buttons
- Modals
- Alerts

---

### 3.5 Bulk Actions

**Trigger:** Select multiple projects using checkboxes

**UI:**
- Checkbox on each row
- "Select All" checkbox in header
- Bulk action bar appears at bottom/top showing:
  - Count of selected items
  - Action buttons: "Archive", "Delete", "Export"
  - "Clear Selection" button

**Interactions:**
- Bulk archive with confirmation
- Bulk delete with confirmation
- Bulk export (CSV/PDF)

**Components Used:**
- Checkboxes
- Bulk action bar
- Buttons
- Confirmation dialogs

---

## Stage 4: Document Management

### 4.1 Document Upload Page

**Route:** `/projects/:id/documents/upload`
**Purpose:** Upload project documents

**Screen Layout:**

**Header:**
- Page title: "Upload Documents"
- Breadcrumb: Dashboard > Projects > [Project] > Documents

**Upload Section:**
- **Drag & Drop Zone**:
  - Large drop area with icon
  - "Drag files here or click to browse"
  - Supported formats: PDF, DOC, DOCX, XLSX, CSV, TXT
  - Max file size: 50MB

- **File List (uploading)**:
  - File name
  - Progress bar per file
  - Cancel button (while uploading)

- **File List (completed)**:
  - File name
  - File size
  - Upload time
  - Status: "Uploaded" ✓
  - Document type selector (dropdown)
  - Delete button

**Bottom Section:**
- "Finish" button (go to library)
- "Upload More" button (add more files)

**Interactions:**
- Drag and drop functionality
- Click to browse files
- Progress bars while uploading
- Document type assignment
- Delete files before finishing
- Batch upload

**Components Used:**
- Drag and drop zone
- Progress bars
- File list
- Dropdowns
- Buttons

---

### 4.2 Document Library

**Route:** `/projects/:id/documents`
**Purpose:** Browse and manage documents

**Screen Layout:**

**Top Section:**
- Page title: "Documents"
- Search box
- Filter button (by type, date, status)
- View toggle (Table/Grid)
- "Upload Document" button

**Filter Panel:**
- Document type (checkbox list)
- Upload date range
- Processing status
- Apply/Reset buttons

**Main Content:**

**Table View:**
- Columns: Document Name, Type, Size, Upload Date, Status, Actions
- Row hover effects
- Pagination

**Grid View (alternative):**
- Document cards in grid (3-4 columns on desktop, responsive)
- Document icon based on type
- Document name
- File size
- Upload date
- Status badge
- Quick action buttons

**Status Indicators:**
- "Uploaded" - Blue badge
- "Processing" - Yellow badge with spinner
- "Ready" - Green badge
- "Error" - Red badge with error message

**Interactions:**
- Click document to open PDF viewer
- Right-click for context menu (download, delete, rename)
- Bulk delete
- Quick preview on hover

**Components Used:**
- Search input
- Filter panel
- Table/Grid toggle
- Cards
- Badges
- Status indicators
- Buttons

---

### 4.3 PDF Viewer with Annotations

**Route:** `/projects/:id/documents/:docId`
**Purpose:** View and annotate documents

**Screen Layout:**

**Left Panel (60% width):**
- PDF page display
- Zoom controls (-, +, fit to width, fit to page)
- Navigation (page X of Y)
- Search within document

**Right Panel (40% width - collapsible):**
- **Annotations Section**:
  - List of all annotations
  - Annotation type badge
  - Comment text
  - Highlighted text preview
  - Edit/Delete buttons
  - Time created

- **Document Info Section**:
  - File name
  - File size
  - Upload date
  - Document type
  - Processing status

**Header:**
- Page title: "Document - [File Name]"
- Breadcrumb navigation
- Download button
- Close button

**Toolbar (above PDF):**
- Highlight text button (toggle)
- Add annotation button
- Search button
- Full screen button
- Rotate left/right buttons

**Interactions:**
- Text highlighting (yellow, multiple colors)
- Click to add annotations
- Drag to select text
- Search within document
- Jump to annotation from list
- Zoom and pan
- Page navigation (arrow keys)
- Multi-document tabs (if multiple open)

**Components Used:**
- PDF renderer
- Highlighting UI
- Annotation panel
- Zoom controls
- Search input
- Buttons

---

### 4.4 OCR Processing Status

**Display:** Modal or status page during document processing

**Status Indicator:**
- File name
- Processing progress (percentage)
- Progress bar
- Status messages:
  - "Extracting text..."
  - "Analyzing structure..."
  - "Processing tables..."
  - "OCR complete!"

- Cancel button (if processing can be cancelled)

**Post-Processing:**
- ✓ Text extraction: Complete
- ✓ Structure analysis: Complete
- ✓ Table extraction: Complete
- Status: Ready for analysis

**Interactions:**
- Monitor progress in background
- Show toast notification on completion
- Allow cancellation

**Components Used:**
- Progress bar
- Status messages
- Spinner
- Buttons

---

### 4.5 Document Details

**Route:** `/projects/:id/documents/:docId/details`
**Purpose:** View document metadata

**Screen Layout:**

**Info Section:**
- Document name (editable)
- Document type (editable dropdown)
- Upload date
- File size
- Processing status
- Last modified date
- Uploaded by

**Content Preview:**
- Extracted text preview (first 200 words)
- Structure overview (headings, sections)
- Key terms/entities extracted

**Associations:**
- Linked project
- Referenced in alerts (count + link)
- Referenced in evidence chains
- Referenced in coherence rules

**Actions:**
- Download original file
- Delete document
- Rename document
- Re-process document (OCR)
- View in PDF viewer

**Interactions:**
- Inline editing
- Confirmation dialogs
- Navigate to related content

**Components Used:**
- Input fields
- Dropdowns
- Info cards
- Preview panels
- Buttons
- Links

---

## Stage 5: Coherence Analysis

### 5.1 Coherence Score Dashboard

**Route:** `/projects/:id/coherence`
**Purpose:** View overall coherence score and analysis

**Screen Layout:**

**Header:**
- Page title: "Coherence Analysis"
- Project name
- Last updated: [Date & Time]
- Refresh button

**Main Section:**

**Large Score Gauge (centered):**
- Current coherence score (0-100)
- Large circular gauge visualization
- Color-coded based on score:
  - 81-100: Green
  - 61-80: Yellow
  - 0-60: Red
- Score label below: "Good", "Fair", "Poor"
- Historical trend indicator (up/down arrow)

**Key Insights:**
- Brief AI-generated summary of coherence status
- 2-3 main findings in bullet points
- Links to detailed analysis

**Quick Navigation Cards (3 cards):**
1. **Category Breakdown** - Click to see detailed breakdown
2. **Recommended Actions** - Click to see actionable recommendations
3. **Rule Analysis** - Click to see individual rule results

**Interactions:**
- Click gauge to zoom in on score details
- Click insight cards to navigate
- Hover for tooltips

**Components Used:**
- Gauge chart
- Info cards
- Summary text
- Buttons
- Links

---

### 5.2 Category Breakdown View

**Route:** `/projects/:id/coherence/breakdown`
**Purpose:** View coherence by category

**Screen Layout:**

**Header:**
- Page title: "Coherence Breakdown by Category"
- Overall score summary

**Category Cards (in grid or list):**

**For Each Category (e.g., "Contract Consistency"):**
- Category name
- Category score (large number)
- Progress bar showing score
- Status badge (Good/Fair/Poor)
- Number of rules in category
- Click to expand/see details

**Expanded Category Details:**
- Individual rules within category
- Rule name
- Rule score/status
- Brief description
- Evidence counts
- Status indicator (passed/failed/warning)

**Comparison Chart:**
- Horizontal bar chart comparing all categories
- One bar per category
- Color-coded by score
- Shows target vs. actual

**Interactions:**
- Expand/collapse categories
- Sort categories (by score, by name, by impact)
- View rule details
- Navigate to rule analysis

**Components Used:**
- Cards
- Progress bars
- Bar charts
- Badges
- Collapse/expand controls
- Buttons

---

### 5.3 Analysis Details

**Route:** `/projects/:id/coherence/analysis`
**Purpose:** Deep dive into coherence analysis

**Screen Layout:**

**Left Panel (30%) - Navigation:**
- Category list (clickable)
- Currently selected category highlighted
- Filter: Show all / Show failed / Show passed

**Right Panel (70%) - Category Details:**

**Category Header:**
- Category name + Icon
- Category score + Gauge
- Number of rules
- Last analyzed: [Date]

**Rules List:**
For each rule:
- Rule name
- Rule ID
- Status: ✓ Passed / ⚠ Warning / ✗ Failed
- Score contribution
- Brief description
- Evidence count
- Expand button

**Rule Details (when expanded):**
- Full rule description
- Methodology
- Evidence found (count)
- Sample evidence (first 2-3)
- Affected documents
- AI analysis/explanation
- Recommended actions

**Interactions:**
- Select category from list
- Expand/collapse rules
- View evidence for each rule
- Navigate to document evidence
- View AI reasoning

**Components Used:**
- Sidebar navigation
- Category cards
- Rules list
- Status badges
- Evidence panels
- Expand/collapse controls
- Links

---

### 5.4 Score Reasoning (LLM)

**Display:** Modal or detail panel

**Trigger:** Click on score explanation or "AI Reasoning" button

**Content:**

**LLM Analysis:**
- "Based on analysis of [X documents], here's why the coherence score is [Y]:"
- Narrative explanation (2-3 paragraphs)
- Key findings bullet list
- Risk assessment
- Confidence level: [80% confident]

**Evidence Support:**
- Top 3-5 pieces of evidence supporting the score
- Each with:
  - Evidence description
  - Source document
  - Link to document section
  - Relevance score

**Recommendations:**
- Top 3-5 recommended actions to improve score
- Each with:
  - Action description
  - Expected impact (score improvement estimate)
  - Effort level (Low/Medium/High)
  - Priority

**Interactions:**
- Click evidence to navigate to document
- Click recommendation to drill down
- Close modal

**Components Used:**
- Modal
- Text content
- Lists
- Evidence cards
- Links
- Buttons

---

### 5.5 Radar Chart Visualization

**Display:** Optional advanced view

**Route:** `/projects/:id/coherence/radar`
**Purpose:** Multi-dimensional visualization of coherence

**Visualization:**
- 6-8 point radar chart
- Each point represents a category
- Inner circle: Current score
- Outer circle: Target score (100)
- Color-coded segments
- Hoverable points with tooltips

**Legend:**
- Category name : [Score]
- Color coding explained

**Additional Views:**
- Toggle between radar chart and category list
- Download chart as PNG/SVG
- Compare with previous analysis (overlay)

**Interactions:**
- Hover for tooltips
- Click on category to navigate to breakdown
- Zoom in/out
- Download chart

**Components Used:**
- Radar chart library
- Legend
- Interactive controls
- Buttons

---

## Stage 6: Evidence Chain

### 6.1 Evidence Viewer

**Route:** `/projects/:id/evidence`
**Purpose:** Visualize complete traceability chain

**Screen Layout:**

**Header:**
- Page title: "Evidence Chain"
- Project name
- Last updated: [Date]
- Reset view button

**Main Visualization Area:**

**Horizontal Chain Visualization:**
```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ CONTRACT │──▶│   WBS    │──▶│ SCHEDULE │──▶│   BOM    │──▶│STAKEHLDS│
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

Each node contains:
- Stage icon
- Stage label
- Item count (e.g., "3 clauses", "12 tasks")
- Hoverable for quick preview

**Below Chain: Detail Panel**

**Active Node Details:**
- Node name/type
- Icon representation
- List of items in this node
- For each item:
  - Item name/ID
  - Status indicator
  - Connections to other nodes

**Bidirectional Navigation:**
- Previous button (to navigate to previous node)
- Next button (to navigate to next node)
- Direct node selection (click on chain nodes)

**Evidence Connections:**
- Visualize links between items across stages
- Click item to see connections
- Highlight connected items

**Interactions:**
- Click on chain node to navigate
- Click on item in list to select
- Expand items to see subitems
- View connections
- Navigate backwards and forwards

**Components Used:**
- Chain visualization
- Detail panels
- Lists
- Icons
- Navigation buttons
- Links

---

### 6.2 Chain Visualization (Contract→WBS→Schedule→BOM)

**Detailed Stage Breakdown:**

**Stage 1: CONTRACT (Clauses)**
- List of contract clauses
- Clause number/ID
- Clause summary
- Relevance score
- Linked WBS items (count)

**Stage 2: WBS (Work Breakdown Structure)**
- WBS hierarchy tree
- Work package name
- Responsibility
- Duration estimate
- Linked contract clauses (count)
- Linked schedule tasks (count)

**Stage 3: SCHEDULE (Timeline/Cronograma)**
- Scheduled tasks
- Task ID
- Duration
- Predecessor/successor
- Resource assignment
- Linked WBS items (count)
- Linked BOM items (count)

**Stage 4: BOM (Bill of Materials)**
- Material/resource items
- Quantity
- Unit cost
- Availability status
- Linked schedule tasks (count)

**Stage 5: STAKEHOLDERS**
- Stakeholder list
- Role/responsibility
- Power/interest level
- Notifications/alerts count

**Visualization Features:**
- Flow arrows between stages
- Mismatch indicators (red flags)
- Hover tooltips with detailed info
- Click to expand/collapse
- Filter by status/type

**Interactions:**
- Select items to trace through chain
- Highlight path from contract to stakeholders
- View connection details
- Filter chain by criteria

**Components Used:**
- Tree visualization
- Flow diagram
- Lists
- Icons
- Tooltips
- Filter controls

---

### 6.3 Bidirectional Navigation

**Forward Navigation:**
- "Next Stage" button
- Go from Contract → WBS → Schedule → BOM → Stakeholders
- Load data for each stage
- Update detail panel

**Backward Navigation:**
- "Previous Stage" button
- Go from Stakeholders → BOM → Schedule → WBS → Contract
- Load data for each stage
- Update detail panel

**Direct Selection:**
- Click on any chain node to jump to that stage
- Load all items for that stage
- Reset detail panel

**Breadcrumb Navigation:**
- Show current path: Contract > Clause #5 > WBS > Task #12
- Click any breadcrumb to jump back

**History:**
- Keep track of navigation path
- Allow "back" and "forward" buttons (like browser)
- Show visited nodes

**Interactions:**
- Use Previous/Next buttons
- Click chain nodes
- Click breadcrumbs
- Use browser back/forward

**Components Used:**
- Buttons
- Breadcrumbs
- Navigation arrows
- Chain visualization
- History stack

---

### 6.4 Recommended Actions

**Display:** Panel within evidence viewer or separate modal

**Content:**

**Priority List:**
- Numbered list of recommended actions
- For each action:
  - Action title
  - Description
  - Severity/priority (Critical/High/Medium/Low)
  - Affected items count
  - Effort estimate (Low/Medium/High)
  - Estimated time to resolve
  - AI confidence level
  - "Learn More" link

**Action Categories:**
- Documentation gaps
- Timeline misalignments
- Cost discrepancies
- Responsibility gaps
- Resource shortages

**Bulk Actions:**
- "Mark as Resolved" (for action)
- "Assign to Team Member"
- "Add to Backlog"

**Interactions:**
- Expand action to see details
- Click on affected items to navigate
- Mark action as completed
- Assign action to team member
- Add action to project backlog

**Components Used:**
- Action cards
- Priority badges
- Lists
- Buttons
- Assignments dropdown
- Links

---

### 6.5 Evidence History & Notes

**Display:** Tab or collapsible section in evidence viewer

**History Section:**
- Timeline of changes to evidence chain
- For each change:
  - Date & time
  - User who made change
  - Type of change (added, updated, deleted)
  - What was changed
  - User avatar
  - Timestamp

**Notes Section:**
- Collaborative notes on evidence chain
- Note entry form:
  - Text editor
  - Mention users with @
  - Attach files
  - Add button

- Note list:
  - Commenter name/avatar
  - Note text
  - Timestamp
  - Edit/delete buttons (if own note)
  - Like/reaction buttons

**Audit Trail:**
- View complete history of all evidence changes
- Filter by date, user, type
- Export as CSV

**Interactions:**
- Add notes
- Edit own notes
- Delete own notes
- React to notes
- Filter history
- Export audit trail

**Components Used:**
- Timeline
- Text editor
- Comments section
- Buttons
- Filters
- Avatar images

---

## Stage 7: Alerts & Notifications

### 7.1 Alerts Dashboard

**Route:** `/alerts`
**Purpose:** Centralized alert management

**Screen Layout:**

**Header:**
- Page title: "Alerts & Notifications"
- Date range selector
- Refresh button

**Quick Stats (3 cards):**
1. **Critical Alerts**: Large number + color (red)
2. **High Priority**: Large number + color (yellow)
3. **Resolved**: Large number + color (green)

**Filter Bar:**
- Search by alert title
- Severity filter dropdown (All / Critical / High / Medium / Low)
- Status filter (All / Open / Resolved / Ignored)
- Type filter (Category selection)
- Project filter (Project selection)
- Date range (Last 7 days / 30 days / Custom)
- Apply Filters button

**Main Alert List:**

**Each Alert Row Contains:**
- Severity badge (color-coded)
- Alert title
- Brief description
- Affected project/document
- Create date
- Status badge
- Quick actions (View, Resolve, Ignore)

**List Features:**
- Sortable columns (by severity, date, status)
- Pagination
- Bulk actions (mark as read, resolve, delete)
- Checkbox for bulk selection

**Mobile View:**
- Card-based layout
- Swiped actions (reveal resolve/ignore)

**Interactions:**
- Click alert to open detail modal
- Sort by column headers
- Filter with multiple criteria
- Bulk mark as resolved
- Quick action buttons
- Paginate through alerts

**Components Used:**
- Stats cards
- Filter panels
- Alert list/table
- Badges
- Buttons
- Checkboxes
- Pagination

---

### 7.2 Alert Filtering & Search

**Filter Panel (collapsible):**

**Filters Available:**
1. **Severity**:
   - Checkboxes: Critical, High, Medium, Low
   - All (default)

2. **Status**:
   - Checkboxes: Open, Resolved, Ignored, Acknowledged
   - All (default)

3. **Type**:
   - Checkboxes for each alert type (Contract, Schedule, Budget, etc.)
   - All (default)

4. **Project**:
   - Dropdown select (single or multi)
   - Search within projects

5. **Date Range**:
   - Quick options: Last 24h, Last 7d, Last 30d, Custom
   - Custom date range picker (from/to)

6. **Assignee**:
   - Dropdown select
   - Show unassigned option

**Search Box:**
- Real-time search as you type
- Search in: Alert title, description, project name
- Clear button
- Search suggestions/autocomplete

**Active Filters Display:**
- Show selected filters as chips/tags
- Click X to remove filter
- "Clear All" button

**Preset Filters:**
- "My Open Alerts"
- "Critical Priority"
- "This Week's Alerts"
- Save custom filter

**Interactions:**
- Check/uncheck filter options
- Multi-select filters
- Apply filters button
- Reset all filters
- Save filter as preset
- Delete saved preset

**Components Used:**
- Filter panel
- Checkboxes
- Dropdowns
- Date pickers
- Search input
- Chips/Tags
- Buttons

---

### 7.3 Alert Detail Modal

**Trigger:** Click on alert in list

**Modal Layout:**

**Header:**
- Alert title (large)
- Close button
- Severity badge (color-coded)
- Alert ID
- Created date & time

**Main Content:**

**Alert Summary:**
- Alert description (full text)
- Alert type/category
- Affected project name (link to project)
- Affected document(s) (if applicable)
- Impact assessment

**Evidence Section:**
- Evidence supporting this alert
- For each piece of evidence:
  - Evidence description
  - Source (document name, section)
  - Link to evidence in document
  - Relevance score

**Recommended Actions:**
- Action 1: [Description] - [Effort level]
- Action 2: [Description] - [Effort level]
- Action 3: [Description] - [Effort level]
- View all actions link

**Assignment:**
- Currently assigned to: [User name] or "Unassigned"
- Assign to dropdown (select team member)
- Add watchers (multi-select)

**Status & Resolution:**

**Status Selector:**
- Current: [Open/Resolved/Ignored]
- Change to: Dropdown with options
- If Resolving: Show resolution notes field
- Save button

**Resolution Notes:**
- Text area for notes
- By: [Current user]
- Date: [Date]
- Add Note button

**Activity Log:**
- Timeline of all activity on this alert
- Status changes
- Assignments
- Notes/comments

**Footer:**
- "Resolve" button (primary)
- "Ignore" button
- "Mark as Read" button
- "Delete" button (danger)

**Interactions:**
- Change status
- Assign to team member
- Add notes
- View evidence (navigate to document)
- Resolve alert
- Ignore alert
- View full activity log

**Components Used:**
- Modal
- Badge
- Dropdown selects
- Text area
- Buttons
- Activity timeline
- Evidence cards
- Links

---

### 7.4 Resolution Workflow

**Step 1: Alert Acknowledgment**
- "Mark as Acknowledged" button
- Updates status to "Acknowledged"
- Shows acknowledgment timestamp

**Step 2: Assignment**
- "Assign to" dropdown
- Optionally add watchers
- Send notification to assignee

**Step 3: Investigation**
- View evidence
- Navigate to documents
- View recommendations
- Add notes during investigation

**Step 4: Resolution**
- Set status to "Resolved"
- Add resolution notes: "What was done to resolve"
- Optional: Upload attachment (proof of resolution)
- Save resolution

**Step 5: Verification**
- Set final status: "Verified" or "Closed"
- Mark as complete

**Step 6: Archive**
- After certain period (configurable), auto-archive
- Or manually archive alert

**Status Flow:**
```
Open → Acknowledged → Assigned → Investigating → Resolved → Verified → Archived
```

**Interactions:**
- Update status
- Add notes at each step
- Change assignment
- Reopen if needed
- View complete resolution history

**Components Used:**
- Status buttons
- Assignment dropdown
- Notes section
- Activity log
- Buttons

---

### 7.5 Activity Log

**Display:** Bottom section of alert detail modal

**Activity Timeline:**
For each activity:
- Timeline dot (color-coded by type)
- Activity type icon (status change, assignment, note, etc.)
- Activity description
- User who performed action (with avatar)
- Timestamp
- Expandable details

**Activity Types:**
- **Status Change**: "Alert status changed from [old] to [new]"
- **Assignment**: "[User] was assigned to this alert"
- **Comment**: "[User] left a note: [note preview]"
- **Alert Update**: "[Field] was updated"
- **View History**: When someone viewed the alert

**Filters:**
- Filter by activity type
- Filter by user
- Date range

**Features:**
- Newest first (default)
- Oldest first
- Full timestamps on hover
- Click to expand activity details

**Interactions:**
- View full activity timeline
- Filter activities
- Sort by date
- Expand activity details
- View user profile (click avatar)

**Components Used:**
- Timeline component
- Activity cards
- Icons
- Avatars
- Timestamps
- Filter controls

---

## Stage 8: Stakeholders Management

### 8.1 Stakeholders List

**Route:** `/projects/:id/stakeholders`
**Purpose:** View and manage project stakeholders

**Screen Layout:**

**Header:**
- Page title: "Stakeholders"
- Search box (search by name, role)
- View toggle (Table/Matrix/List)
- "Add Stakeholder" button
- "Import from CSV" button

**Filter Options:**
- Role filter (dropdown)
- Power level (High/Medium/Low)
- Interest level (High/Medium/Low)
- Status (Active/Inactive)

**Table View (default):**

**Columns:**
- Name
- Role/Title
- Organization
- Power Level (1-5 scale)
- Interest Level (1-5 scale)
- Contact Email
- Phone
- Status badge
- Actions (View, Edit, Delete)

**Row Features:**
- Click row to open detail panel
- Hover shows quick actions
- Pagination at bottom
- Sort by column headers

**List View (alternative):**
- Card-based layout
- Name, role, organization, contact info
- Power/interest indicators
- Action buttons

**Interactions:**
- Click stakeholder for detail panel
- Click "Add Stakeholder" to add new
- Import CSV for bulk add
- Edit/delete actions
- Filter stakeholders
- Search stakeholders

**Components Used:**
- Search input
- Filter dropdowns
- Table/List/Grid toggle
- Stakeholder cards/rows
- Buttons
- Action menus

---

### 8.2 Power/Interest Matrix

**Route:** `/projects/:id/stakeholders/matrix`
**Purpose:** Visualize stakeholders on power/interest grid

**Screen Layout:**

**2x2 Matrix Visualization:**
```
                    ┌─────────────────────────────────┬─────────────────────────────────┐
                    │     HIGH POWER / LOW INTEREST   │     HIGH POWER / HIGH INTEREST  │
                    │      (Keep Satisfied)           │      (Manage Closely)           │
                    │                                 │                                 │
POWER (INFLUENCE)   │ • Approvers                     │ • Project Sponsor               │
                    │ • Finance Directors             │ • Project Manager               │
                    │ • Department Heads              │ • CTO/CEO                       │
                    ├─────────────────────────────────┼─────────────────────────────────┤
                    │    LOW POWER / LOW INTEREST     │    LOW POWER / HIGH INTEREST    │
                    │      (Monitor)                  │      (Keep Informed)            │
                    │                                 │                                 │
                    │ • Occasional users              │ • Project team members          │
                    │ • External consultants          │ • Department staff              │
                    │                                 │ • Affected end users            │
                    └─────────────────────────────────┴─────────────────────────────────┘
                                INTEREST (IMPACT)
```

**Stakeholder Positioning:**
- Each stakeholder shown as bubble/circle
- Position based on power (Y axis) and interest (X axis)
- Bubble size represents influence/importance
- Color-coded by role or department
- Drag to reposition (if editable)
- Hover shows name, role, details

**Legend:**
- Color coding explanation
- Bubble size legend

**Quadrant Labels:**
- "Keep Satisfied" (Top-Left)
- "Manage Closely" (Top-Right)
- "Monitor" (Bottom-Left)
- "Keep Informed" (Bottom-Right)

**Axis Labels:**
- X-axis: "Interest Level" (Low → High)
- Y-axis: "Power/Influence" (Low → High)

**Interactions:**
- Click stakeholder bubble to open detail panel
- Drag bubbles to reposition (if editable mode)
- Hover for tooltip with stakeholder info
- Click quadrant label for recommendations
- Filter stakeholders
- Download matrix as image

**Components Used:**
- Scatter plot/bubble chart
- Tooltips
- Drag and drop
- Legend
- Buttons
- Filter controls

---

### 8.3 Stakeholder Detail Panel

**Trigger:** Click on stakeholder from list or matrix

**Panel Layout:**

**Header:**
- Stakeholder name (large)
- Avatar/profile picture
- Job title
- Organization
- Status badge

**Basic Info:**
- Email: [email]
- Phone: [phone]
- Office: [location]
- Department: [dept]
- Reports to: [manager name]

**Power/Interest Profile:**
- Power level slider visual (1-5)
- Interest level slider visual (1-5)
- Quadrant position indicator
- Suggested engagement strategy

**Responsibilities:**
- List of RACI responsibilities
- Tasks assigned
- Committees/groups
- Authority areas

**Communication:**
- Preferred contact method (email/phone)
- Notification preferences
- Last contact date
- Communication history

**AI Analysis:**
- AI-extracted information from documents
- Confidence level
- Inferred interests
- Implicit needs
- Risk factors

**Related Items:**
- Projects involved in (count)
- Documents referenced
- Alerts assigned
- RACI matrix rows

**Actions:**
- Edit button
- Delete button
- Add to group button
- Send notification button
- View RACI button

**Interactions:**
- Edit stakeholder information
- Update power/interest levels
- View related content
- Send messages/notifications
- Close panel

**Components Used:**
- Detail panel
- Avatar image
- Info cards
- Sliders
- Lists
- Buttons
- Links

---

### 8.4 AI Extraction Results

**Display:** Within stakeholder detail panel or separate tab

**AI Analysis Section:**

**Extracted Information:**
- Name: [Extracted from documents]
- Title/Role: [Extracted from documents]
- Organization: [Extracted from documents]
- Department: [Extracted from documents]
- Contact info: [Extracted from documents]
- Reporting structure: [Extracted from documents]

**Confidence Scores:**
- For each extracted field: [0-100%] confidence
- Visual indicator (green/yellow/red)
- Low confidence items flagged for review

**Evidence Sources:**
- Document 1: Reference quote
- Document 2: Reference quote
- Document 3: Reference quote
- Click to jump to document

**Inferred Information:**
- Interests (from contract references): [List]
- Risks/concerns (from mentions): [List]
- Influence level: [Calculated from mentions/approvals]
- Dependencies: [Other stakeholders affected]

**Recommendations:**
- Suggested power level: [1-5]
- Suggested interest level: [1-5]
- Engagement strategy: [Recommendation]
- Communication frequency: [Suggestion]

**Actions:**
- Accept extraction
- Edit extracted fields
- Reject and re-extract
- Mark field as manual
- Manual override

**Interactions:**
- Review extracted information
- Click sources to view evidence
- Edit fields
- Accept or reject extraction
- Save changes

**Components Used:**
- Info cards
- Confidence badges
- Evidence references
- Edit inputs
- Buttons

---

### 8.5 RACI Responsibilities

**Display:** Panel showing stakeholder's RACI assignments

**Content:**

**RACI Summary:**
- Responsible: [List of tasks]
- Accountable: [List of tasks]
- Consulted: [List of tasks]
- Informed: [List of tasks]

**Task List:**
For each responsibility:
- Task/WBS item name
- RACI role (R/A/C/I)
- Project name
- Status
- Due date
- View button (navigate to RACI matrix)

**Statistics:**
- Total assignments: X
- Responsibility load: Low/Medium/High
- Critical tasks: X
- Overdue tasks: X

**Interactions:**
- Filter by RACI role
- Sort by status/date
- View in RACI matrix
- Remove assignment
- Edit assignment

**Components Used:**
- Lists
- Badges
- Statistics cards
- Buttons
- Links

---

## Stage 9: RACI Matrix

### 9.1 RACI Matrix View (WBS × Stakeholders)

**Route:** `/projects/:id/raci`
**Purpose:** Interactive RACI responsibility assignment matrix

**Screen Layout:**

**Header:**
- Page title: "RACI Matrix"
- Project name
- Last updated: [Date]
- View mode toggle (Edit/View)
- Export button

**Matrix Structure:**
- **Rows (Y-axis):** WBS items (Work packages, tasks)
- **Columns (X-axis):** Stakeholders
- **Cells:** RACI role assignment (R/A/C/I)

**Matrix Visualization:**

```
                │ Stakeholder 1│ Stakeholder 2│ Stakeholder 3│
────────────────┼──────────────┼──────────────┼──────────────┤
WBS Item 1      │      R       │      A       │              │
────────────────┼──────────────┼──────────────┼──────────────┤
WBS Item 2      │      C       │      R       │      I       │
────────────────┼──────────────┼──────────────┼──────────────┤
WBS Item 3      │              │      C       │      A       │
────────────────┼──────────────┼──────────────┼──────────────┤
```

**Color Coding:**
- R (Responsible): Green
- A (Accountable): Blue
- C (Consulted): Yellow
- I (Informed): Gray
- Empty: White

**Matrix Features:**
- Scrollable (horizontal for many stakeholders)
- Freeze first column (WBS items)
- Row totals: Assignment count per WBS
- Column totals: Assignment count per stakeholder
- Filter rows (by status, type)
- Filter columns (by power/interest)

**Issues/Warnings Display:**
- Red highlighting for missing assignments
- Warning icon for multiple Accountables
- Missing Responsible indicator
- Conflict indicators

**Interactions:**
- Click cell to edit assignment
- Drag to reposition stakeholders/tasks
- Expand/collapse WBS hierarchy
- Filter rows and columns
- View validation issues
- Export matrix

**Components Used:**
- Table/Grid component
- Color-coded cells
- Scrollable container
- Filter controls
- Validation indicators
- Buttons

---

### 9.2 Cell Editor with Validations

**Trigger:** Click on matrix cell

**Editor Display:**

**Current Assignment:**
- Shows current RACI role (R/A/C/I/Empty)
- Shows who assigned it
- Shows when assigned

**Role Selection:**
- Radio buttons or toggle:
  - ⭕ Responsible
  - ⭕ Accountable
  - ⭕ Consulted
  - ⭕ Informed
  - ⭕ None (empty)

**Validations (Real-time):**
- "Each task must have exactly one Accountable" → ⚠️ Warning if violated
- "Responsible should exist if Accountable exists" → ⚠️ Suggestion
- "One person per role recommended" → ⚠️ Information
- Stakeholder has many responsibilities → ⚠️ Capacity warning

**AI Recommendations:**
- "AI suggests: [Role] based on stakeholder expertise"
- Confidence: [80%]
- Reasoning: [Brief explanation]
- Accept recommendation button

**Change History:**
- Previous assignment: [Role] by [User] on [Date]
- Old assignment shown for reference

**Actions:**
- Save button
- Cancel button
- Clear assignment button
- View AI reasoning button

**Interactions:**
- Select role from radio buttons
- See validations in real-time
- Accept AI recommendation
- Save or cancel
- View change history

**Components Used:**
- Radio buttons
- Validation messages
- AI recommendations
- Change history
- Buttons

---

### 9.3 AI Rationale Explanation

**Display:** Modal or side panel when viewing cell

**Trigger:** Click "View AI Reasoning" or "Why this assignment?"

**Content:**

**AI Recommendation:**
- "Based on stakeholder expertise and project structure, AI recommends:"
- **Assignment:** [Role]
- **Confidence:** [85%]

**Reasoning:**

**Factor 1: Expertise Match**
- Stakeholder has skills in: [List]
- Task requires: [List]
- Match score: [80%]

**Factor 2: Responsibility Level**
- Stakeholder's current responsibility load: [X tasks assigned]
- Capacity available: [Y additional tasks]
- Load factor: [Medium]

**Factor 3: Authority/Power**
- Task requires authority level: [High]
- Stakeholder power level: [High (4/5)]
- Authority match: [Good fit]

**Factor 4: Interest/Involvement**
- Stakeholder interest in this area: [High (4/5)]
- Task involves stakeholder's department: Yes
- Interest alignment: [Good]

**Factor 5: Organizational Structure**
- Stakeholder's organizational role: [Title]
- Task responsibility level: [Senior]
- Organizational alignment: [Good]

**Alternative Suggestions:**
1. Alternative assignment: [Role] → Stakeholder 2 (confidence: 65%)
   - Reasoning: Secondary expertise in area

2. Alternative assignment: [Role] → Stakeholder 3 (confidence: 55%)
   - Reasoning: Related department

**Sources:**
- Extracted from contract clauses
- Historical RACI patterns
- Organizational chart analysis
- Stakeholder skill assessment

**Interactions:**
- View reasoning
- Accept recommendation
- Select alternative
- Close panel

**Components Used:**
- Modal/panel
- Text content
- Reasoning cards
- Confidence indicators
- Alternative suggestions
- Buttons

---

### 9.4 Approval Workflow

**Status Indicators:**
- Draft: Matrix is being configured
- Pending Review: Ready for stakeholder review
- Approved: Finalized
- Archived: Previous version

**Current Status Display:**
- "Status: [Draft/Pending Review/Approved]"
- Last modified: [Date & User]
- Status badges

**Approval Process:**

**Step 1: Prepare Matrix**
- Configure all assignments
- Resolve all validation issues
- View the matrix

**Step 2: Submit for Review**
- "Submit for Review" button
- Adds status "Pending Review"
- Sends notification to approvers

**Step 3: Stakeholder Review**
- Stakeholders review their rows
- Can accept or request changes
- Add comments

**Step 4: Approval**
- Approvers review comments
- Approve matrix (if valid)
- Or send back for revision

**Step 5: Finalize**
- "Approve" button (admin/manager only)
- Matrix status: "Approved"
- Locked from editing (unless override)

**Comments & Feedback:**
- Review comments panel
- Timeline of submissions
- Feedback from stakeholders
- Request changes dialog

**Interactions:**
- Submit for review
- Review stakeholder feedback
- Request changes
- Approve matrix
- Lock/unlock for editing
- View history

**Components Used:**
- Status badge
- Buttons
- Comments section
- Timeline
- Dialog modals
- Notifications

---

### 9.5 Matrix Export (Excel/PDF)

**Trigger:** Click "Export" button in matrix header

**Export Options Modal:**

**Format Selection:**
- ⭕ Microsoft Excel (.xlsx)
- ⭕ PDF Document
- ⭕ CSV (comma-separated values)

**Content Options:**
- ☑ Matrix data (assignments)
- ☑ Validation report (issues)
- ☑ AI recommendations
- ☑ Comments and notes
- ☑ Change history

**Layout Options (for PDF):**
- ⭕ Landscape (default for wide matrix)
- ⭕ Portrait
- ⭕ Fit to page
- ⭕ Multi-page

**Additional Options:**
- Include legend
- Include statistics
- Include stakeholder contact info
- Include project info header
- Professional styling

**Filename:**
- Default: "RACI_Matrix_[ProjectName]_[Date].xlsx"
- Customizable text field

**Actions:**
- "Export" button → Download file
- "Preview" button → Show preview
- "Cancel" button

**Export Formats Details:**

**Excel Format:**
- Sheet 1: RACI Matrix
- Sheet 2: Validation Report
- Sheet 3: AI Recommendations
- Sheet 4: Change History
- Color-coded cells
- Frozen headers
- Summaries

**PDF Format:**
- Professional layout
- Color-coded legend
- Stakeholder list (on separate page)
- Validation report
- Statistics summary
- Project information header

**CSV Format:**
- Comma-separated values
- Can import into other tools
- Plain text format

**Interactions:**
- Select format
- Select content to include
- Choose layout options
- Preview export
- Download file

**Components Used:**
- Radio buttons
- Checkboxes
- Text input
- Dropdown
- Preview area
- Buttons

---

## Figma Organization Structure

### 🗂️ Recommended Figma File Organization

```
C2Pro Design System (Main File)
├── 📄 Cover Page (Project Overview)
├── 📐 Design System
│   ├── Colors
│   │   ├── Primary Colors
│   │   ├── Severity Colors
│   │   ├── Status Colors
│   │   └── Neutral Scale
│   ├── Typography
│   │   ├── Heading Styles
│   │   ├── Body Styles
│   │   └── Special Styles
│   ├── Components
│   │   ├── Buttons (Primary, Secondary, Danger, Sizes)
│   │   ├── Inputs (Text, Select, Checkbox, Radio)
│   │   ├── Cards
│   │   ├── Tables
│   │   ├── Badges & Tags
│   │   ├── Modals
│   │   ├── Breadcrumbs
│   │   ├── Alerts
│   │   └── Icons
│   └── Spacing & Layout
│       ├── Grid System
│       ├── Spacing Scale
│       ├── Shadows
│       └── Border Radius
│
├── 🎯 Stage 1: Authentication & Onboarding
│   ├── 1.1 Login Page
│   ├── 1.2 Registration Page
│   ├── 1.3 Organization Setup
│   └── 1.4 Welcome Onboarding
│
├── 📊 Stage 2: Dashboard & Navigation
│   ├── 2.1 Main Dashboard
│   ├── 2.2 Sidebar Navigation
│   ├── 2.3 Top Navigation Bar
│   └── 2.4 User Profile Menu
│
├── 📁 Stage 3: Project Management
│   ├── 3.1 Projects List
│   ├── 3.2 Create Project Modal
│   ├── 3.3 Project Detail Page
│   ├── 3.4 Project Settings
│   └── 3.5 Bulk Actions
│
├── 📄 Stage 4: Document Management
│   ├── 4.1 Document Upload Page
│   ├── 4.2 Document Library
│   ├── 4.3 PDF Viewer with Annotations
│   ├── 4.4 OCR Processing Status
│   └── 4.5 Document Details
│
├── 📈 Stage 5: Coherence Analysis
│   ├── 5.1 Coherence Score Dashboard
│   ├── 5.2 Category Breakdown View
│   ├── 5.3 Analysis Details
│   ├── 5.4 Score Reasoning (LLM)
│   └── 5.5 Radar Chart Visualization
│
├── 🔗 Stage 6: Evidence Chain
│   ├── 6.1 Evidence Viewer
│   ├── 6.2 Chain Visualization
│   ├── 6.3 Bidirectional Navigation
│   ├── 6.4 Recommended Actions
│   └── 6.5 Evidence History & Notes
│
├── 🚨 Stage 7: Alerts & Notifications
│   ├── 7.1 Alerts Dashboard
│   ├── 7.2 Alert Filtering & Search
│   ├── 7.3 Alert Detail Modal
│   ├── 7.4 Resolution Workflow
│   └── 7.5 Activity Log
│
├── 👥 Stage 8: Stakeholders Management
│   ├── 8.1 Stakeholders List
│   ├── 8.2 Power/Interest Matrix
│   ├── 8.3 Stakeholder Detail Panel
│   ├── 8.4 AI Extraction Results
│   └── 8.5 RACI Responsibilities
│
├── 📊 Stage 9: RACI Matrix
│   ├── 9.1 RACI Matrix View
│   ├── 9.2 Cell Editor with Validations
│   ├── 9.3 AI Rationale Explanation
│   ├── 9.4 Approval Workflow
│   └── 9.5 Matrix Export
│
├── 🔧 Admin & Settings
│   ├── Organization Settings
│   ├── User Management
│   ├── Audit Logs
│   └── Integration Settings
│
├── 🎨 Interactive Prototypes
│   ├── User Flow - Happy Path
│   ├── User Flow - Document Analysis
│   ├── User Flow - RACI Configuration
│   └── User Flow - Alert Resolution
│
├── 📱 Responsive Breakpoints
│   ├── Desktop (1440px)
│   ├── Tablet (768px)
│   └── Mobile (375px)
│
└── 📚 Documentation & Notes
    ├── Design Decisions
    ├── Interaction Patterns
    ├── Accessibility Guidelines
    ├── Animation Specifications
    └── Handoff Notes
```

### Component Library Structure

Create a component library within Figma:

**Location:** `/Design System/Components`

**Component Categories:**

1. **Buttons**
   - Primary / Default / Hover / Active / Disabled
   - Secondary / Default / Hover / Active / Disabled
   - Danger / Default / Hover / Active / Disabled
   - Sizes: Large, Default, Small
   - With Icons: Leading, Trailing, Both

2. **Inputs**
   - Text Input / Default / Focus / Error / Disabled
   - Email Input
   - Password Input
   - Select/Dropdown
   - Textarea
   - Checkbox
   - Radio Button
   - Toggle Switch
   - Date Picker
   - File Upload

3. **Cards**
   - Default Card
   - Elevated Card
   - With Header
   - With Footer
   - Stats Card
   - Alert Card

4. **Tables**
   - Header Row
   - Data Row
   - Hover State
   - Selected Row
   - Pagination Controls

5. **Navigation**
   - Sidebar Item / Default / Active / Hover
   - Breadcrumbs
   - Tabs
   - Dropdown Menu
   - Pagination

6. **Feedback**
   - Alert / Success / Warning / Error / Info
   - Badge / Success / Warning / Error / Info
   - Toast Notification
   - Progress Bar
   - Spinner/Loading

7. **Modals & Dialogs**
   - Modal Container
   - Dialog Box
   - Confirmation Dialog
   - Loading Modal

8. **Data Visualization**
   - Gauge Chart
   - Bar Chart
   - Pie Chart
   - Radar Chart
   - Trend Indicator

9. **Avatar & User**
   - Avatar / Small / Medium / Large
   - User Profile Card
   - Team Member Row

10. **Icons** (all used icons from Lucide)

---

## Implementation Checklist

### Phase 1: Design System Setup
- [ ] Create Figma file with main structure
- [ ] Set up color styles and palette
- [ ] Create typography styles (all sizes)
- [ ] Set up spacing token system
- [ ] Create component library
- [ ] Document design system in Figma

### Phase 2: Stage 1 - Authentication (Week 1)
- [ ] Login Page wireframe
- [ ] Registration Page wireframe
- [ ] Organization Setup wireframe
- [ ] Welcome Onboarding wireframes
- [ ] Mobile responsive versions
- [ ] Interactive prototype (login flow)

### Phase 3: Stage 2 - Dashboard (Week 1-2)
- [ ] Main Dashboard wireframe
- [ ] Dashboard components (stats cards, charts)
- [ ] Sidebar Navigation
- [ ] Top Navigation Bar
- [ ] User Profile Menu
- [ ] Responsive layouts
- [ ] Interactive prototype (navigation)

### Phase 4: Stage 3 - Projects (Week 2)
- [ ] Projects List wireframe
- [ ] Create Project Modal
- [ ] Project Detail Page
- [ ] Project Settings
- [ ] Bulk Actions UI
- [ ] Mobile responsive versions
- [ ] Interactive prototype (project navigation)

### Phase 5: Stage 4 - Documents (Week 3)
- [ ] Document Upload Page
- [ ] Document Library
- [ ] PDF Viewer with Annotations
- [ ] OCR Processing Status
- [ ] Document Details
- [ ] Mobile responsive versions
- [ ] Interactive prototype (document workflow)

### Phase 6: Stage 5 - Coherence Analysis (Week 3-4)
- [ ] Coherence Score Dashboard
- [ ] Category Breakdown View
- [ ] Analysis Details
- [ ] LLM Reasoning Display
- [ ] Radar Chart View
- [ ] Mobile responsive versions
- [ ] Interactive prototype (analysis flow)

### Phase 7: Stage 6 - Evidence Chain (Week 4)
- [ ] Evidence Viewer wireframe
- [ ] Chain Visualization
- [ ] Navigation controls
- [ ] Recommended Actions panel
- [ ] History & Notes section
- [ ] Mobile responsive versions
- [ ] Interactive prototype (evidence flow)

### Phase 8: Stage 7 - Alerts (Week 5)
- [ ] Alerts Dashboard
- [ ] Filter & Search UI
- [ ] Alert Detail Modal
- [ ] Resolution Workflow
- [ ] Activity Log
- [ ] Mobile responsive versions
- [ ] Interactive prototype (alert management)

### Phase 9: Stage 8 - Stakeholders (Week 5-6)
- [ ] Stakeholders List
- [ ] Power/Interest Matrix
- [ ] Stakeholder Detail Panel
- [ ] AI Extraction Results
- [ ] RACI Responsibilities view
- [ ] Mobile responsive versions
- [ ] Interactive prototype (stakeholder management)

### Phase 10: Stage 9 - RACI Matrix (Week 6-7)
- [ ] RACI Matrix View
- [ ] Cell Editor
- [ ] AI Rationale Modal
- [ ] Approval Workflow
- [ ] Export Options
- [ ] Mobile responsive versions
- [ ] Interactive prototype (RACI flow)

### Phase 11: Advanced & Polish (Week 7-8)
- [ ] Complete user journey prototypes
- [ ] Animation specifications
- [ ] Accessibility review (WCAG 2.1 AA)
- [ ] Design handoff documentation
- [ ] Component inventory
- [ ] Design tokens documentation
- [ ] CSS variables mapping

### Phase 12: Documentation & Handoff
- [ ] Create design documentation
- [ ] Write component specifications
- [ ] Create interaction patterns guide
- [ ] Developer handoff document
- [ ] Accessibility guidelines
- [ ] Performance considerations
- [ ] Export specifications (SVG, PNG)

---

## Next Steps

1. **Open Figma:** Navigate to https://www.figma.com/design/AOkZSMoQXt3dI8FOJ3AjCD/C2Pro
2. **Create Pages:** Set up the file structure as recommended above
3. **Start with Design System:** Create color styles, typography, and components first
4. **Build Screens:** Follow the implementation checklist phase by phase
5. **Create Prototypes:** Connect screens with interactive prototypes
6. **Document:** Add annotations and specifications for developers
7. **Iterate:** Gather feedback and refine designs based on testing

---

**Document Version:** 2.0
**Last Updated:** 2026-02-18
**Status:** Ready for Figma Implementation
