# Projects List - Wireframe

**View:** Projects List
**Route:** `/projects`
**Purpose:** Comprehensive view of all projects with advanced filtering, search, and bulk actions

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  Dashboard   Projects   Documents   Alerts   Stakeholders   RACI            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Projects ─────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  ┌─────────────────────────────────────────────────────────────┐   │     │
│  │  │  🔍 Search projects...                                       │   │     │
│  │  │                                                              │   │     │
│  │  └─────────────────────────────────────────────────────────────┘   │     │
│  │                                                                     │     │
│  │  ┌─ Filters ──────────────────────────────────────────────────┐   │     │
│  │  │                                                             │   │     │
│  │  │  Status: [ All ▼ ]  Type: [ All ▼ ]  Score: [ All ▼ ]     │   │     │
│  │  │                                                             │   │     │
│  │  │  Date: [ Last 30 days ▼ ]     [Reset Filters]             │   │     │
│  │  │                                                             │   │     │
│  │  └─────────────────────────────────────────────────────────────┘   │     │
│  │                                                                     │     │
│  │  ┌─ Actions ──────────────────────────────────────────────────┐   │     │
│  │  │  [+ New Project]        [Export CSV]      [Bulk Actions ▼] │   │     │
│  │  └─────────────────────────────────────────────────────────────┘   │     │
│  │                                                                     │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─ Results (25 projects) ────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ☑  Project Name         Type      Status    Score    Alerts  Updated │ │
│  │  ─────────────────────────────────────────────────────────────────────│ │
│  │                                                                         │ │
│  │  ☑  Hospital Central     EPC       Active     [85]     3       2h ago │ │
│  │      Madrid, Spain                           ┗━━━━━━━━━━━━━━━━━━━━┛  │ │
│  │      Budget: €12.5M  |  Start: Jan 2026  |  End: Jun 2026             │ │
│  │      [View] [Edit] [Archive]                                           │ │
│  │                                                                         │ │
│  │  ☑  Port Expansion       Maritime  Active     [67]     8       5h ago │ │
│  │      Valencia, Spain                         ┗━━━━━━━━━━━━┛          │ │
│  │      Budget: €45.0M  |  Start: Dec 2025  |  End: Dec 2026             │ │
│  │      [View] [Edit] [Archive]                                           │ │
│  │                                                                         │ │
│  │  ☑  Industrial Plant     Chemical  Active     [92]     1       1d ago │ │
│  │      Tarragona, Spain                        ┗━━━━━━━━━━━━━━━━━━━━━━┛│ │
│  │      Budget: €28.3M  |  Start: Oct 2025  |  End: Apr 2027             │ │
│  │      [View] [Edit] [Archive]                                           │ │
│  │                                                                         │ │
│  │  ☐  Office Complex       Building  Draft     [--]     0       3d ago │ │
│  │      Barcelona, Spain                                                  │ │
│  │      Budget: €8.7M   |  Start: --        |  End: --                   │ │
│  │      [View] [Edit] [Delete]                                            │ │
│  │                                                                         │ │
│  │  ☐  Highway Extension    Civil     Complete  [88]     0       1w ago │ │
│  │      Andalucía, Spain                        ┗━━━━━━━━━━━━━━━━━━━┛   │ │
│  │      Budget: €92.0M  |  Start: Jan 2024  |  End: Dec 2025             │ │
│  │      [View] [Report] [Archive]                                         │ │
│  │                                                                         │ │
│  │  ☐  Solar Farm           Energy    Active     [78]     4       2d ago │ │
│  │      Zaragoza, Spain                         ┗━━━━━━━━━━━━━━━┛       │ │
│  │      Budget: €15.2M  |  Start: Feb 2026  |  End: Aug 2026             │ │
│  │      [View] [Edit] [Archive]                                           │ │
│  │                                                                         │ │
│  │  ☐  Water Treatment      Municipal Active     [81]     2       4h ago │ │
│  │      Sevilla, Spain                          ┗━━━━━━━━━━━━━━━━━┛     │ │
│  │      Budget: €6.3M   |  Start: Mar 2026  |  End: Sep 2026             │ │
│  │      [View] [Edit] [Archive]                                           │ │
│  │                                                                         │ │
│  │  ─────────────────────────────────────────────────────────────────────│ │
│  │                                                                         │ │
│  │  ◀ Previous    Page 1 of 3    Next ▶                                   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Search Bar
- **Search Input**: Full-text search across project name, description, code
- **Search Icon**: Visual indicator
- **Autocomplete**: Suggestions as user types (future enhancement)
- **Clear Button**: Quick clear search

### 2. Filters Section
**Collapsible filter panel with:**

#### Status Filter
- All (default)
- Draft
- Active
- Completed
- Archived
- On Hold

#### Type Filter
- All (default)
- EPC (Engineering, Procurement, Construction)
- Civil
- Building
- Maritime
- Chemical
- Energy
- Municipal
- Oil & Gas
- Mining

#### Score Filter
- All (default)
- Excellent (90-100)
- Good (80-89)
- Fair (70-79)
- Poor (60-69)
- Critical (0-59)
- Not Analyzed

#### Date Range Filter
- Last 7 days
- Last 30 days (default)
- Last 90 days
- Last year
- All time
- Custom range (date picker)

#### Reset Button
- Clear all filters at once
- Return to default view

### 3. Actions Bar
**Primary Actions:**
- **New Project**: Opens project creation modal/page
- **Export CSV**: Download project list as CSV
- **Bulk Actions**: Dropdown menu for:
  - Archive selected
  - Delete selected
  - Change status
  - Export selected

### 4. Results Table
**Table Columns:**

#### Checkbox
- Select individual projects
- Select all (header checkbox)
- Used for bulk actions

#### Project Name
- Primary identifier
- Clickable link to project detail
- Subtitle: Location/site

#### Type
- Project category
- Color-coded badges

#### Status
- Current project status
- Color-coded badges:
  - Draft: Gray
  - Active: Blue
  - Completed: Green
  - Archived: Dark gray

#### Coherence Score
- 0-100 numeric value
- Visual bar indicator
- Color coding:
  - Red (0-60)
  - Yellow (61-80)
  - Green (81-100)
- "--" for not analyzed

#### Alerts
- Count of open alerts
- Clickable badge
- Red badge if critical alerts present

#### Updated
- Relative timestamp
- Last modification time

#### Metadata Row (expandable)
- **Budget**: Estimated project budget with currency
- **Start Date**: Project start date
- **End Date**: Project completion date

#### Action Buttons
**Contextual based on status:**
- **Draft**: View, Edit, Delete
- **Active**: View, Edit, Archive
- **Completed**: View, Report, Archive
- **Archived**: View, Restore

### 5. Pagination
- **Previous/Next Buttons**: Navigate pages
- **Page Indicator**: Current page / total pages
- **Items per page**: 25, 50, 100 (dropdown)

---

## Project Card View (Mobile)

```
┌───────────────────────────────────┐
│ ☑  Hospital Central               │
│    Madrid, Spain                  │
│                                   │
│    EPC  │  Active  │  Score: 85  │
│    ┗━━━━━━━━━━━━━━━━━━━━━━┛     │
│                                   │
│    💰 €12.5M                      │
│    📅 Jan 2026 - Jun 2026         │
│    🔔 3 alerts                    │
│                                   │
│    [View Project]                 │
├───────────────────────────────────┤
│ ☐  Port Expansion                 │
│    Valencia, Spain                │
│                                   │
│    Maritime  │  Active  │  67     │
│    ┗━━━━━━━━━━┛                  │
│                                   │
│    💰 €45.0M                      │
│    📅 Dec 2025 - Dec 2026         │
│    🔔 8 alerts                    │
│                                   │
│    [View Project]                 │
└───────────────────────────────────┘
```

---

## Interactions

### Primary Actions
1. **Click Project Name**: Navigate to project detail page
2. **Click Score Bar**: View coherence analysis summary
3. **Click Alerts Badge**: Navigate to project alerts filtered view
4. **Check Checkbox**: Select project for bulk action
5. **Click Action Button**: Execute project-specific action

### Filtering & Search
1. **Type in Search**: Real-time filter results
2. **Select Filter Option**: Apply filter, update results count
3. **Reset Filters**: Clear all filters, return to default
4. **Apply Multiple Filters**: Combine filters (AND logic)

### Bulk Actions
1. **Select Multiple Projects**: Check multiple checkboxes
2. **Select Bulk Action**: Choose action from dropdown
3. **Confirm Action**: Modal confirmation for destructive actions
4. **Execute**: Process selected projects

### Sorting
**Click column header to sort:**
- Project Name (A-Z / Z-A)
- Type (alphabetical)
- Status (alphabetical)
- Score (high to low / low to high)
- Alerts (most to least / least to most)
- Updated (newest / oldest)

**Visual indicator:** ▲ ▼ arrows in header

---

## Responsive Behavior

### Desktop (>1200px)
- Full table layout
- All columns visible
- Side-by-side filters

### Tablet (768px - 1200px)
- Table with horizontal scroll
- Hide less important columns
- Collapsible filters

### Mobile (<768px)
- Card view (not table)
- Stacked filters
- Bottom sheet for bulk actions

---

## Empty States

### No Projects
```
┌───────────────────────────────────┐
│                                   │
│          📋                       │
│                                   │
│     No projects yet               │
│                                   │
│     Get started by creating       │
│     your first project            │
│                                   │
│     [+ Create Project]            │
│                                   │
└───────────────────────────────────┘
```

### No Search Results
```
┌───────────────────────────────────┐
│                                   │
│          🔍                       │
│                                   │
│     No projects found             │
│                                   │
│     Try adjusting your filters    │
│     or search terms               │
│                                   │
│     [Reset Filters]               │
│                                   │
└───────────────────────────────────┘
```

---

## Design Notes

### Status Badges
- **Draft**: Gray background, dark text
- **Active**: Blue background, white text
- **Completed**: Green background, white text
- **Archived**: Dark gray background, light text
- **On Hold**: Orange background, white text

### Type Badges
- **EPC**: Purple
- **Civil**: Blue
- **Building**: Teal
- **Maritime**: Navy
- **Chemical**: Orange
- **Energy**: Yellow
- **Municipal**: Green
- **Other**: Gray

### Score Visualization
- **Bar**: Horizontal progress bar
- **Width**: Proportional to score value
- **Color**:
  - 0-60: Red (#CC0000)
  - 61-80: Yellow (#FFAA00)
  - 81-100: Green (#00AA00)
- **Hover**: Show exact numeric value

### Alerts Badge
- **Normal**: Gray badge with count
- **Critical**: Red badge with count
- **Pulse**: Animation for new alerts

---

## Performance Optimization

### Virtualization
- Load only visible rows (10-25 at a time)
- Lazy load as user scrolls
- Improves performance for large lists

### Caching
- Cache filter results
- Cache search queries
- Invalidate on create/update/delete

### Debouncing
- Search input: 300ms debounce
- Filter changes: Immediate

---

## Accessibility

- **ARIA Labels**: Table headers, buttons, filters
- **Keyboard Navigation**:
  - Tab through interactive elements
  - Enter to select/activate
  - Space to check/uncheck
- **Screen Reader**:
  - Announce filter changes
  - Announce results count
  - Describe score values
- **Focus Management**: Clear focus indicators
- **Contrast**: WCAG AA compliant

---

## Future Enhancements
- [ ] Column customization (show/hide columns)
- [ ] Save custom filter presets
- [ ] Inline editing (quick edit mode)
- [ ] Kanban view toggle
- [ ] Advanced search with query builder
- [ ] Export to multiple formats (PDF, Excel, JSON)
- [ ] Batch upload/import projects
- [ ] Project templates
- [ ] Favorites/bookmarks
- [ ] Project tags/labels
