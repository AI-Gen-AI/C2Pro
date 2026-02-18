# C2Pro - Figma User Flows & Interaction Patterns
**Version:** 1.0 | **Date:** 2026-02-18 | **Status:** Ready for Figma

---

## Flow 1: First-Time User Onboarding

```
[Landing/Login]
      │
      ▼
[Register Page]
  · Organization name
  · Email + Password
  · Accept terms
      │
      ▼
[Email Verification] ──→ [Check Email Screen]
      │
      ▼
[Organization Setup] (Step 1/3)
  · Industry, size, country
      │
      ▼
[Invite Team] (Step 2/3)
  · Add team member emails (optional)
      │
      ▼
[Welcome Tour] (Step 3/3)
  · Feature highlights
      │
      ▼
[DASHBOARD] ◄────── Main Entry Point
```

---

## Flow 2: Core Analysis Workflow (Happy Path)

```
[DASHBOARD]
      │  Click "New Project"
      ▼
[Create Project Modal]
  · Name, type, client
  · Assign team
      │  Save
      ▼
[Project Detail Page]
  · Overview tab (empty state)
      │  Click "Upload Documents"
      ▼
[Document Upload]
  · Drag & drop contract PDF
  · Drag & drop schedule file
  · Drag & drop budget file
      │  Upload Complete
      ▼
[OCR Processing]
  · Progress indicator
  · "Processing..." state
      │  Processing Complete
      ▼
[Document Library]
  · Shows 3 documents: ✓ Ready
      │  Click "Run Analysis"
      ▼
[Coherence Analysis Loading]
  · Spinner + "Analyzing..."
      │  Analysis Complete
      ▼
[COHERENCE SCORE DASHBOARD]
  · Large gauge: Score 74/100
  · Summary: "3 inconsistencies found"
      │
      ├──→ Click "View Breakdown"
      │         │
      │         ▼
      │    [Category Breakdown]
      │    · Contracts: 85
      │    · Schedule: 70
      │    · Budget: 68
      │
      ├──→ Click "View Evidence"
      │         │
      │         ▼
      │    [Evidence Chain Viewer]
      │    · Contract → WBS → Schedule → BOM
      │
      └──→ Click "View Alerts" (3 critical)
                │
                ▼
           [Alerts Dashboard]
           · Alert 1: Critical
           · Alert 2: High
           · Alert 3: Medium
                │  Click Alert 1
                ▼
           [Alert Detail Modal]
           · Description + Evidence
           · Recommended Actions
                │  Resolve
                ▼
           [Alert Resolved] ✓
```

---

## Flow 3: RACI Configuration Flow

```
[Project Detail Page]
      │  Click "Stakeholders" tab
      ▼
[Stakeholders List] (empty state first time)
      │  Click "Extract from Documents"
      ▼
[AI Extraction Loading]
  · "Extracting stakeholders..."
      │
      ▼
[AI Results Review]
  · List of extracted stakeholders
  · Confidence scores per stakeholder
  · Accept / Edit / Reject each
      │  Accept All / Save
      ▼
[Stakeholders List] (populated)
  · 8 stakeholders shown
      │
      ├──→ Click "Power/Interest Matrix"
      │         │
      │         ▼
      │    [Matrix View]
      │    · Bubbles positioned
      │    · Drag to reposition
      │
      └──→ Click "Configure RACI"
                │
                ▼
           [RACI Matrix] (empty state)
           · WBS items as rows
           · Stakeholders as columns
                │  Click "Auto-generate RACI"
                ▼
           [AI RACI Generation]
           · Loading: "Generating assignments..."
                │
                ▼
           [RACI Matrix] (AI filled)
           · Cells populated with R/A/C/I
           · Validation warnings shown
                │  Review cells
                ▼
           [Cell Editor]
           · Edit individual assignments
           · See AI rationale
           · Resolve validations
                │  All valid
                ▼
           [Submit for Review]
                │
                ▼
           [Approval Workflow]
           · Notify stakeholders
           · Track approvals
                │  All approved
                ▼
           [RACI Approved ✓]
                │  Click "Export"
                ▼
           [Export Options Modal]
           · Select: Excel/PDF
           · Download
```

---

## Flow 4: Alert Investigation & Resolution

```
[ALERTS DASHBOARD]
  · Stats: 5 Critical, 12 High, 8 Medium
      │  Filter: "Critical Only"
      ▼
[Filtered Alert List]
  · 5 Critical alerts shown
      │  Click first alert
      ▼
[Alert Detail Modal]
  · Title: "Budget mismatch in Section 3.2"
  · Severity: Critical
  · Evidence: Contract clause vs. BOM item
      │
      ├──→ Click "View in Document"
      │         │
      │         ▼
      │    [PDF Viewer]
      │    · Highlighted clause
      │    · Annotation panel open
      │         │  Back
      │         ▼
      │    [Alert Detail Modal]
      │
      └──→ Click "View Evidence Chain"
                │
                ▼
           [Evidence Viewer]
           · Contract → WBS → Schedule → BOM
           · Mismatch highlighted in red
                │  Back
                ▼
           [Alert Detail Modal]
                │  Assign to: John Doe
                ▼
           [Assignment Notification]
           · John Doe notified by email
                │  Add resolution note
                ▼
           [Notes: "Fixed in contract amendment v2.1"]
                │  Click "Resolve"
                ▼
           [Alert Resolved ✓]
           · Status: Resolved
           · Timestamp: [now]
           · Toast: "Alert resolved successfully"
```

---

## Flow 5: Document Deep-Dive Flow

```
[DOCUMENTS PAGE]
      │  Click document: "Contract_v3.pdf"
      ▼
[PDF Viewer]
  · Full PDF displayed
  · Right panel: Document Info
      │
      ├──→ Enable Highlight Mode
      │         │  Select text
      │         ▼
      │    [Annotation Created]
      │    · Yellow highlight
      │    · Annotation panel opens
      │    · Add note/comment
      │
      ├──→ Search in document
      │         │  Type: "payment terms"
      │         ▼
      │    [Search Results]
      │    · 3 matches highlighted
      │    · Navigate between matches
      │
      └──→ Click annotation in list
                │
                ▼
           [Jump to highlighted section]
           · Scroll to location
           · Pulse animation
```

---

## Screen State Specifications

### Empty States

Each screen has a specific empty state design:

| Screen | Empty State | CTA |
|--------|-------------|-----|
| Projects List | Illustration + "No projects yet" | "Create your first project" |
| Documents | Illustration + "No documents uploaded" | "Upload your first document" |
| Alerts | ✓ Icon + "No alerts - looking good!" | "View Analysis" |
| Stakeholders | Illustration + "No stakeholders found" | "Extract from Documents" |
| RACI Matrix | Grid icon + "RACI not configured" | "Start Configuration" |
| Evidence Chain | Chain icon + "No evidence available" | "Run Analysis" |

### Loading States

| Action | Loading UI | Duration |
|--------|------------|----------|
| Login | Button spinner | Until response |
| Document upload | Progress bar per file | Until upload complete |
| OCR processing | Full-page progress | 30-120 seconds |
| AI analysis | Spinner + status text | 30-180 seconds |
| RACI generation | Skeleton + spinner | 60-120 seconds |
| Page navigation | Skeleton screens | Until data loads |

### Error States

| Error Type | UI | Action |
|------------|-----|--------|
| Network error | Banner + "Try again" button | Retry |
| Upload failed | File shows error badge | Remove + retry |
| Analysis failed | Error card + reason | Contact support |
| Session expired | Modal + redirect to login | Re-login |
| 404 Not found | Full page 404 UI | Go to dashboard |
| 500 Server error | Full page 500 UI | Retry / report |

---

## Interaction Patterns

### Toast Notifications

| Event | Type | Message | Duration |
|-------|------|---------|----------|
| Project created | Success | "Project created successfully" | 3s |
| Document uploaded | Success | "Document uploaded and processing" | 3s |
| Alert resolved | Success | "Alert marked as resolved" | 3s |
| RACI saved | Success | "RACI matrix saved" | 3s |
| Assignment sent | Info | "Notification sent to [Name]" | 3s |
| Error | Error | "[Specific error message]" | 5s |

**Toast Position:** Bottom-right corner
**Animation:** Slide in from right, fade out

### Confirmation Dialogs

Required for destructive actions:

| Action | Title | Message | Buttons |
|--------|-------|---------|---------|
| Delete project | "Delete Project?" | "This will delete all data permanently." | [Cancel] [Delete] |
| Archive project | "Archive Project?" | "Project will be hidden but data preserved." | [Cancel] [Archive] |
| Delete document | "Delete Document?" | "This document will be permanently deleted." | [Cancel] [Delete] |
| Delete stakeholder | "Remove Stakeholder?" | "This stakeholder will be removed." | [Cancel] [Remove] |
| Clear RACI | "Clear Matrix?" | "All RACI assignments will be cleared." | [Cancel] [Clear] |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Global search |
| `Ctrl/Cmd + N` | New project |
| `Escape` | Close modal/panel |
| `Ctrl/Cmd + S` | Save current form |
| `Ctrl/Cmd + Z` | Undo last action |
| `?` | Show keyboard shortcuts |
| `←` `→` | Navigate evidence chain |
| `+` `-` | Zoom in/out PDF viewer |

---

## Animation Specifications

### Transitions

| Element | Type | Duration | Easing |
|---------|------|----------|--------|
| Page navigation | Fade | 150ms | ease-in-out |
| Modal open | Scale + fade | 200ms | ease-out |
| Modal close | Scale + fade | 150ms | ease-in |
| Dropdown open | Slide down | 150ms | ease-out |
| Toast appear | Slide + fade | 200ms | ease-out |
| Toast dismiss | Fade | 200ms | ease-in |
| Sidebar collapse | Slide | 250ms | ease-in-out |
| Tab switch | Fade | 150ms | ease-in-out |

### Chart Animations

| Chart | Animation | Duration |
|-------|-----------|----------|
| Gauge chart | Rotation from 0 | 800ms, ease-out |
| Bar chart | Grow from bottom | 600ms, stagger 50ms |
| Pie/Donut chart | Draw arc | 800ms, ease-out |
| Radar chart | Scale from center | 700ms, ease-out |
| Progress bar | Width from 0 | 500ms, ease-out |

---

## Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | < 768px | Single column, collapsed sidebar, stacked cards |
| Tablet | 768-1024px | Sidebar hidden (hamburger), 2-column grid |
| Desktop | 1024-1440px | Full sidebar visible, 3-column grid |
| Wide | > 1440px | Max-width 1440px, centered content |

### Mobile-Specific Patterns

| Desktop Feature | Mobile Adaptation |
|-----------------|-------------------|
| Sidebar navigation | Bottom tab bar |
| Multi-column tables | Card-based list |
| Side-by-side panels | Stacked panels + tabs |
| Hover tooltips | Long-press or tap-to-reveal |
| Context menus | Swipe actions |
| Multiple columns | Horizontal scroll |
| Modal (large) | Full-screen bottom sheet |

---

**Last Updated:** 2026-02-18
