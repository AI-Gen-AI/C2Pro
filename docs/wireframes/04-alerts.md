# Alerts Panel - Wireframe

**View:** Alerts Management
**Route:** `/alerts` or `/projects/{id}/alerts`
**Purpose:** Comprehensive view of all coherence alerts with filtering, prioritization, and bulk management

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  Dashboard   Projects   Documents   Alerts   Stakeholders   RACI            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Alerts ───────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌─ Quick Stats ───────────────────────────────────────────────────┐  │ │
│  │  │                                                                  │  │ │
│  │  │  🔴 Critical: 8   🟡 High: 15   🔵 Medium: 23   ⚪ Low: 12     │  │ │
│  │  │                                                                  │  │ │
│  │  │  📊 Open: 45  │  ✅ Resolved: 123  │  ⏳ In Progress: 13       │  │ │
│  │  │                                                                  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Filters & Search ─────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  🔍 [Search alerts...]                                                  │ │
│  │                                                                         │ │
│  │  Severity: [ All ▼ ]  Type: [ All ▼ ]  Project: [ All ▼ ]            │ │
│  │                                                                         │ │
│  │  Status: [ Open ▼ ]   Date: [ Last 7 days ▼ ]   [Reset]              │ │
│  │                                                                         │ │
│  │  ☑ Show only my alerts    ☑ Group by project                          │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Bulk Actions ─────────────────────────────────────────────────────────┐ │
│  │  ☑ Select All (45)   [Assign to...] [Mark as...] [Export] [Archive]   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Alerts List (45) ─────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☑ 🔴  Date Mismatch: Contract vs Schedule                         │ │ │
│  │  │                                                                    │ │ │
│  │  │    Hospital Central EPC  │  Rule R1  │  Created: 2h ago          │ │ │
│  │  │                                                                    │ │ │
│  │  │    Contract deadline (Jun 30) differs from schedule end (Jul 15) │ │ │
│  │  │    by 15 days. Potential penalty: €750,000                        │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: Clause 4.2, WBS 1.0, Activities Act-104 to Act-105  │ │ │
│  │  │    Assigned to: Carlos Martínez (Project Manager)                │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☑ 🟡  Budget Overrun Risk: Material Costs                         │ │ │
│  │  │                                                                    │ │ │
│  │  │    Port Expansion Maritime  │  Rule R6  │  Created: 5h ago       │ │ │
│  │  │                                                                    │ │ │
│  │  │    Total material costs (€2.3M) exceed budgeted amount (€2.0M)   │ │ │
│  │  │    by 15%. Review procurement plan or budget allocation.          │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: 23 BOM Items, Budget Line Item B-203                │ │ │
│  │  │    Assigned to: Laura Fernández (Procurement Manager)            │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☑ 🔴  Missing Stakeholder Approval                                │ │ │
│  │  │                                                                    │ │ │
│  │  │    Industrial Plant Chemical  │  Rule R20  │  Created: 1d ago    │ │ │
│  │  │                                                                    │ │ │
│  │  │    Critical BOM items require HSE Officer approval before        │ │ │
│  │  │    procurement. No stakeholder assigned with approval authority. │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: 5 BOM Items (Chemicals), WBS 2.3 Safety Systems     │ │ │
│  │  │    Unassigned                                                     │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☑ 🔵  WBS Item Without Budget Allocation                          │ │ │
│  │  │                                                                    │ │ │
│  │  │    Hospital Central EPC  │  Rule R12  │  Created: 2d ago         │ │ │
│  │  │                                                                    │ │ │
│  │  │    WBS item "1.4 Medical Equipment Installation" has no          │ │ │
│  │  │    assigned budget line items. Allocate budget or verify scope.  │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: WBS 1.4 (Budget: TBD)                               │ │ │
│  │  │    Assigned to: Ana García (Finance Manager)                     │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☑ 🟡  Material Lead Time Risk                                     │ │ │
│  │  │                                                                    │ │ │
│  │  │    Solar Farm Energy  │  Rule R14  │  Created: 3d ago            │ │ │
│  │  │                                                                    │ │ │
│  │  │    BOM item "Solar Panels (Type A)" has 90-day lead time but     │ │ │
│  │  │    optimal order date is overdue by 5 days. Expedite or adjust.  │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: BOM-4501, WBS 3.2 Panel Installation                │ │ │
│  │  │    Assigned to: Laura Fernández (Procurement Manager)            │ │ │
│  │  │                                                                    │ │ │
│  │  │    💬 1 note    │    ⏰ Due: March 20, 2026                       │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │
│  │  │ ☐ ⚪  Minor: Clause Reference Formatting                          │ │ │
│  │  │                                                                    │ │ │
│  │  │    Office Complex Building  │  Rule R17  │  Created: 5d ago      │ │ │
│  │  │                                                                    │ │ │
│  │  │    BOM item lacks proper contract clause reference. Add clause   │ │ │
│  │  │    ID for full traceability.                                     │ │ │
│  │  │                                                                    │ │ │
│  │  │    Affected: BOM-8823 (Windows & Doors)                          │ │ │
│  │  │    Assigned to: Miguel Rodríguez (Documentation)                 │ │ │
│  │  │                                                                    │ │ │
│  │  │    [View Evidence] [Assign] [Resolve] [Escalate] [Add Note]      │ │ │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ─────────────────────────────────────────────────────────────────────│ │
│  │                                                                         │ │
│  │  ◀ Previous    Page 1 of 5    Next ▶                                   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Alert Detail Modal (when clicked) ───────────────────────────────────┐  │
│  │                                                                         │  │
│  │  [X] Close                                                              │  │
│  │                                                                         │  │
│  │  🔴  Date Mismatch: Contract vs Schedule                               │  │
│  │  Hospital Central EPC Project                                          │  │
│  │                                                                         │  │
│  │  ┌─ Alert Details ──────────────────────────────────────────────────┐ │  │
│  │  │  Severity: Critical                                               │ │  │
│  │  │  Rule: R1 - Contract/Schedule Date Alignment                      │ │  │
│  │  │  Detected: January 21, 2026 at 14:23                              │ │  │
│  │  │  Status: Open                                                     │ │  │
│  │  │  Priority: P0 (Urgent)                                            │ │  │
│  │  │  Assigned to: Carlos Martínez                                     │ │  │
│  │  │  Due date: January 25, 2026                                       │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                         │  │
│  │  ┌─ Description ─────────────────────────────────────────────────────┐ │  │
│  │  │  Contract deadline differs from schedule end date by 15 days.     │ │  │
│  │  │  This discrepancy could result in liquidated damages and claims.  │ │  │
│  │  │                                                                    │ │  │
│  │  │  Financial Impact: Potential penalty of €750,000 (€50,000/day)    │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                         │  │
│  │  ┌─ Evidence Summary ───────────────────────────────────────────────┐ │  │
│  │  │  📄 Contract: Clause 4.2 - Execution Deadline (Jun 30, 2026)     │ │  │
│  │  │  📊 Schedule: Activity Act-105 ends July 15, 2026                 │ │  │
│  │  │  ⚠️  Gap: 15 days overrun                                         │ │  │
│  │  │                                                                    │ │  │
│  │  │  [View Full Evidence Chain →]                                     │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                         │  │
│  │  ┌─ Recommended Actions ────────────────────────────────────────────┐ │  │
│  │  │  1. Revise schedule to complete by June 30, 2026                  │ │  │
│  │  │  2. Request contract amendment to extend deadline                 │ │  │
│  │  │  3. Reserve contingency for potential penalties                   │ │  │
│  │  │  4. Schedule urgent meeting with client and PMO                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                         │  │
│  │  ┌─ Activity Log ───────────────────────────────────────────────────┐ │  │
│  │  │  💬 Carlos Martínez - 2 hours ago                                 │ │  │
│  │  │     "Contacted client to discuss acceleration options."           │ │  │
│  │  │                                                                    │ │  │
│  │  │  🔄 System - 5 hours ago                                          │ │  │
│  │  │     Alert created and assigned to Carlos Martínez                 │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                         │  │
│  │  [Resolve Alert] [Change Status] [Reassign] [Add Note] [Escalate]     │  │
│  │                                                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Quick Stats Bar
**Overview metrics:**
- **Severity Counts**: 🔴 Critical, 🟡 High, 🔵 Medium, ⚪ Low
- **Status Counts**: Open, Resolved, In Progress
- **Real-time Updates**: Updates as alerts are resolved

### 2. Filters & Search Panel

#### Search Bar
- **Full-text Search**: Search across alert title, description, affected items
- **Instant Results**: Filter as user types
- **Clear Button**: Quick reset

#### Filter Dropdowns
**Severity Filter:**
- All (default)
- Critical
- High
- Medium
- Low

**Type Filter (by Rule Category):**
- All (default)
- Contract/Schedule Alignment
- Contract/Budget Alignment
- Budget/Schedule Alignment
- WBS/BOM Coherence
- Stakeholder Assignment
- Lead Time Risks
- Data Quality

**Project Filter:**
- All (default)
- List of all projects (searchable dropdown)

**Status Filter:**
- Open (default)
- In Progress
- Resolved
- Archived
- All

**Date Range:**
- Today
- Last 7 days (default)
- Last 30 days
- Last 90 days
- All time
- Custom range

#### Toggle Options
- **Show only my alerts**: Filter to current user's assignments
- **Group by project**: Organize alerts by project

### 3. Bulk Actions Bar
**Available when items are selected:**
- **Select All**: Checkbox to select/deselect all
- **Assign to...**: Bulk assignment to user
- **Mark as...**: Bulk status change
- **Export**: Export selected alerts to CSV/PDF
- **Archive**: Move to archive

### 4. Alerts List

#### Alert Card
Each alert displays:

**Header:**
- **Checkbox**: For bulk selection
- **Severity Icon**: Color-coded emoji
- **Title**: Brief description of the issue

**Metadata:**
- **Project**: Project name and type
- **Rule**: Which coherence rule was triggered
- **Created**: Relative timestamp

**Description:**
- **Issue Summary**: 2-3 line explanation
- **Impact**: Financial, schedule, or quality impact

**Affected Items:**
- **Entities**: Clauses, WBS items, BOM items, Activities
- **Quick Links**: Click to view in context

**Assignment:**
- **Assigned to**: User name and role
- **Unassigned**: If no owner

**Indicators:**
- **Notes Count**: 💬 Number of comments
- **Due Date**: ⏰ When action is required
- **Attachment**: 📎 If files attached

**Actions:**
- **View Evidence**: Navigate to Evidence Viewer
- **Assign**: Change assignee
- **Resolve**: Mark as resolved with note
- **Escalate**: Flag for management
- **Add Note**: Add comment

#### Visual Hierarchy
- **Critical (Red)**: Bold border, high contrast
- **High (Yellow)**: Medium border, warm colors
- **Medium (Blue)**: Standard border, cool colors
- **Low (Gray)**: Subtle border, low contrast

### 5. Alert Detail Modal
**Expanded view when alert clicked:**

#### Alert Header
- **Close Button**: Exit modal
- **Severity and Title**: Large, prominent
- **Project Context**: Project name

#### Alert Details Section
- **All Metadata**: Full details table
- **Priority**: P0 (Urgent), P1 (High), P2 (Medium), P3 (Low)
- **SLA**: Due date/time
- **Assignment**: Current owner with avatar

#### Description Section
- **Full Description**: Complete explanation
- **Financial Impact**: Quantified if applicable
- **Schedule Impact**: Days of delay
- **Risk Assessment**: Likelihood and impact

#### Evidence Summary
- **Quick Links**: To each entity in the chain
- **Mismatch Visualization**: Side-by-side comparison
- **View Full Evidence**: Button to Evidence Viewer

#### Recommended Actions
- **Numbered List**: AI-generated suggestions
- **Actionable**: Each can be turned into a task
- **Contextual**: Based on alert type and severity

#### Activity Log
- **Chronological**: Newest first
- **User Comments**: With avatars
- **System Events**: Assignment, status changes, etc.
- **Timestamps**: Relative time

#### Action Buttons
- **Resolve Alert**: Opens resolution modal
- **Change Status**: Dropdown (Open, In Progress, Blocked, Resolved)
- **Reassign**: User picker
- **Add Note**: Text input
- **Escalate**: Flag for attention

---

## Alert Resolution Flow

```
1. Click "Resolve Alert"
     ↓
2. Resolution Modal Opens
   ┌─────────────────────────────────┐
   │ How was this resolved?          │
   │                                 │
   │ ○ Schedule adjusted             │
   │ ○ Contract amended              │
   │ ○ Budget reallocated            │
   │ ○ Issue was false positive      │
   │ ○ Other (specify)               │
   │                                 │
   │ [Add Note (required)]           │
   │                                 │
   │ ☑ Notify stakeholders           │
   │                                 │
   │ [Cancel] [Resolve]              │
   └─────────────────────────────────┘
     ↓
3. Alert marked as Resolved
   Stakeholders notified (if checked)
   Activity log updated
```

---

## Interactions

### Primary Actions
1. **Click Alert**: Open detail modal
2. **View Evidence**: Navigate to Evidence Viewer
3. **Resolve**: Complete resolution flow
4. **Assign**: Change owner
5. **Filter/Search**: Refine alert list

### Secondary Actions
1. **Add Note**: Quick comment
2. **Escalate**: Flag for attention
3. **Bulk Action**: Process multiple alerts
4. **Export**: Download alert report
5. **Sort**: Reorder list

### Real-time Updates
- **New Alerts**: Toast notification
- **Status Changes**: Live update in list
- **Assignment**: Notification to new owner
- **Resolution**: Notification to stakeholders

---

## Sorting Options

**Click column header to sort:**
- **Severity**: Critical → Low
- **Created**: Newest → Oldest
- **Priority**: P0 → P3
- **Project**: Alphabetical
- **Status**: Open → Resolved
- **Assignee**: Alphabetical
- **Due Date**: Soonest → Latest

**Visual indicator:** ▲ ▼ arrows

---

## Grouping Options

### By Project
```
▼ Hospital Central EPC (5 alerts)
  🔴 Date Mismatch: Contract vs Schedule
  🔵 WBS Item Without Budget Allocation
  ...

▼ Port Expansion Maritime (3 alerts)
  🟡 Budget Overrun Risk: Material Costs
  ...
```

### By Severity
```
▼ Critical (8 alerts)
  🔴 Date Mismatch: Contract vs Schedule
  🔴 Missing Stakeholder Approval
  ...

▼ High (15 alerts)
  🟡 Budget Overrun Risk: Material Costs
  ...
```

### By Assignee
```
▼ Carlos Martínez (12 alerts)
  🔴 Date Mismatch: Contract vs Schedule
  🔵 WBS Item Without Budget Allocation
  ...

▼ Unassigned (5 alerts)
  🔴 Missing Stakeholder Approval
  ...
```

---

## Responsive Behavior

### Desktop (>1200px)
- Full card layout
- Sidebar filters
- Modal detail view

### Tablet (768px - 1200px)
- Collapsible filters
- Card layout
- Bottom sheet detail

### Mobile (<768px)
- Top filters (bottom sheet)
- Simplified cards
- Full-screen detail

---

## Notification System

### Alert Created
**Notify:**
- Assigned user (if assigned)
- Project manager
- RACI Accountable stakeholders

### Alert Resolved
**Notify:**
- All stakeholders who were notified of creation
- Project manager
- User who created the alert (if different)

### Alert Escalated
**Notify:**
- Management team
- Project sponsor
- CTO (for critical issues)

---

## Empty States

### No Alerts
```
┌───────────────────────────────────┐
│                                   │
│          ✅                       │
│                                   │
│     All clear!                    │
│                                   │
│     No alerts for this project    │
│                                   │
└───────────────────────────────────┘
```

### No Results
```
┌───────────────────────────────────┐
│                                   │
│          🔍                       │
│                                   │
│     No alerts found               │
│                                   │
│     Try adjusting your filters    │
│                                   │
│     [Reset Filters]               │
│                                   │
└───────────────────────────────────┘
```

---

## Accessibility

- **ARIA Labels**: All interactive elements
- **Keyboard Navigation**: Full support
- **Screen Reader**: Announce severity, status
- **Focus Management**: Clear indicators
- **Color Contrast**: WCAG AA compliant
- **Alternative Text**: Icons have text labels

---

## Future Enhancements
- [ ] Alert rules customization
- [ ] Custom severity levels
- [ ] Alert templates
- [ ] Recurring alerts
- [ ] Alert subscriptions (email/Slack)
- [ ] SLA tracking and violations
- [ ] Alert analytics dashboard
- [ ] Machine learning for priority prediction
- [ ] Integration with project management tools
- [ ] Automated resolution suggestions

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
