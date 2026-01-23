# RACI Matrix - Wireframe

**View:** RACI Matrix Viewer/Editor
**Route:** `/projects/{id}/raci`
**Purpose:** Interactive responsibility assignment matrix showing WBS items vs Stakeholders with human-in-loop approval workflow

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  ◀ Back to Project          Hospital Central EPC Project                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ RACI Matrix ──────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌─ Actions & Status ──────────────────────────────────────────────┐  │ │
│  │  │                                                                  │  │ │
│  │  │  Status: 🤖 Auto-generated (Requires Review)                    │  │ │
│  │  │                                                                  │  │ │
│  │  │  [🤖 Generate RACI]  [✅ Approve All]  [📝 Edit Mode]  [Export] │  │ │
│  │  │                                                                  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ┌─ Matrix Legend ─────────────────────────────────────────────────┐  │ │
│  │  │  R = Responsible (Does the work)                                │  │ │
│  │  │  A = Accountable (Ultimately answerable, approves)              │  │ │
│  │  │  C = Consulted (Provides input, two-way communication)          │  │ │
│  │  │  I = Informed (Kept updated, one-way communication)             │  │ │
│  │  │                                                                  │  │ │
│  │  │  🟢 Approved  │  🟡 Pending Review  │  🔵 Modified              │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Filters & View Options ───────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  WBS Level: [● All] [○ Level 1-2] [○ Critical Path Only]              │ │
│  │                                                                         │ │
│  │  Stakeholders: [Show All (18)] ☐ Key Players Only  ☐ External Only    │ │
│  │                                                                         │ │
│  │  Highlight: [None ▼] [No Accountable] [Multiple Accountable] [Gaps]   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ RACI Matrix ───────────────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  ┌────────────────────┬──────┬──────┬──────┬──────┬──────┬──────┬────┐ ││
│  │  │ WBS Item           │Carlos│ Ana  │Miguel│Laura │Ricardo│Carmen│... │ ││
│  │  │                    │ PM   │Client│Plann │Procur│ HSE  │Quality│    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │▸ 1.0 Hospital Main │  A   │  I   │  R   │  C   │  C   │  C   │... │ ││
│  │  │     Building   🟡  │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │    │ ││
│  │  │     Budget: €8.5M  │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │  ├─ 1.1 Foundation │  A   │  I   │  R   │  -   │  C   │  I   │... │ ││
│  │  │  │   & Structure 🟢│ 🟢   │ 🟢   │ 🟢   │      │ 🟢   │ 🟢   │    │ ││
│  │  │  │   Budget: €2.1M │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │  ├─ 1.2 Mechanical │  A   │  I   │  R   │  R   │  C   │  C   │... │ ││
│  │  │  │   Systems   🟡  │ 🟢   │ 🟢   │ 🟡   │ 🟡   │ 🟢   │ 🟢   │    │ ││
│  │  │  │   Budget: €3.8M │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │  └─ 1.3 Finishes & │  A   │  C   │  R   │  -   │  I   │  C   │... │ ││
│  │  │     Commissioning🔵│ 🔵   │ 🔵   │ 🟢   │      │ 🟢   │ 🔵   │    │ ││
│  │  │     Budget: €2.6M  │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │▸ 2.0 Emergency     │  A   │  I   │  R   │  C   │  C   │  C   │... │ ││
│  │  │     Department  🟡 │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │    │ ││
│  │  │     Budget: €5.2M  │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │  ├─ 2.1 Trauma     │  C   │  I   │  R   │  R   │  A   │  C   │... │ ││
│  │  │  │   Rooms     🟢  │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │    │ ││
│  │  │  │   Budget: €2.8M │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │  └─ 2.2 Medical    │  A   │  C   │  R   │  R   │  C   │  A   │... │ ││
│  │  │     Equipment   ⚠️ │ 🟡   │ 🟡   │ 🟡   │ 🟡   │ 🟡   │ 🟡   │    │ ││
│  │  │     Budget: €2.4M  │      │      │      │      │      │      │    │ ││
│  │  │                    │     ⚠️ Warning: 2 Accountable roles!          │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │▸ 3.0 Parking       │  C   │  I   │  A   │  R   │  C   │  I   │... │ ││
│  │  │     Structure   🟢 │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │    │ ││
│  │  │     Budget: €3.1M  │      │      │      │      │      │      │    │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │▸ 4.0 Landscaping   │  I   │  I   │  C   │  R   │  I   │  I   │... │ ││
│  │  │              ⚠️    │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │ 🟢   │    │ ││
│  │  │     Budget: €0.8M  │      │      │      │      │      │      │    │ ││
│  │  │                    │     ⚠️ Warning: No Accountable role!           │ ││
│  │  ├────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤ ││
│  │  │▸ 5.0 Medical       │  C   │  A   │  I   │  A   │  I   │  R   │... │ ││
│  │  │     Equipment   🟡 │ 🟢   │ 🟡   │ 🟢   │ 🟡   │ 🟢   │ 🟡   │    │ ││
│  │  │     Budget: €4.2M  │      │      │      │      │      │      │    │ ││
│  │  └────────────────────┴──────┴──────┴──────┴──────┴──────┴──────┴────┘ ││
│  │                                                                          ││
│  │  💡 Click any cell to edit assignments │ Right-click for bulk actions    ││
│  │                                                                          ││
│  │  ┌─ Summary Statistics ──────────────────────────────────────────────┐ ││
│  │  │                                                                    │ ││
│  │  │  Total WBS Items: 15  │  Approved: 8  │  Pending: 5  │  Issues: 2 │ ││
│  │  │                                                                    │ ││
│  │  │  Issues:                                                           │ ││
│  │  │  ⚠️  2 items with multiple Accountable roles                       │ ││
│  │  │  ⚠️  1 item without Accountable role                               │ ││
│  │  │  ⚠️  3 items with no Responsible role                              │ ││
│  │  │                                                                    │ ││
│  │  │  [View Issue Report] [Fix Automatically]                           │ ││
│  │  │                                                                    │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                                                                          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ Cell Detail (shown on click) ─────────────────────────────────────────┐ │
│  │                                                                          │ │
│  │  WBS 1.2: Mechanical Systems → Carlos Martínez              [X] Close   │ │
│  │                                                                          │ │
│  │  ┌─ Current Assignment ───────────────────────────────────────────────┐│ │
│  │  │  Role: [A] Accountable                                             ││ │
│  │  │  Status: 🟢 Approved                                               ││ │
│  │  │  Assigned: Jan 16, 2026 (Auto-generated)                           ││ │
│  │  │  Approved by: Admin on Jan 17, 2026                                ││ │
│  │  └─────────────────────────────────────────────────────────────────────┘│ │
│  │                                                                          │ │
│  │  ┌─ Edit Assignment ──────────────────────────────────────────────────┐│ │
│  │  │  New Role: [Accountable ▼]                                         ││ │
│  │  │            ├─ Responsible                                          ││ │
│  │  │            ├─ Accountable (current)                                ││ │
│  │  │            ├─ Consulted                                            ││ │
│  │  │            ├─ Informed                                             ││ │
│  │  │            └─ None (remove)                                        ││ │
│  │  │                                                                     ││ │
│  │  │  Reason for change (optional):                                     ││ │
│  │  │  [_________________________________________________]                ││ │
│  │  │                                                                     ││ │
│  │  │  ☐ Apply to all child WBS items                                   ││ │
│  │  │  ☐ Notify stakeholder of change                                   ││ │
│  │  └─────────────────────────────────────────────────────────────────────┘│ │
│  │                                                                          │ │
│  │  ┌─ AI Rationale ─────────────────────────────────────────────────────┐│ │
│  │  │  Carlos Martínez was assigned as Accountable because:              ││ │
│  │  │                                                                     ││ │
│  │  │  1. Role: Project Manager with overall project accountability      ││ │
│  │  │  2. Contract Clause 1.2 lists PM as responsible for deliverables   ││ │
│  │  │  3. Budget authority: Approval threshold €500K (WBS budget: €3.8M) ││ │
│  │  │  4. Historical pattern: Accountable for similar WBS items          ││ │
│  │  │                                                                     ││ │
│  │  │  Confidence: 92%                                                    ││ │
│  │  │  Source: Clause 1.2, Organization Chart, Budget Matrix             ││ │
│  │  └─────────────────────────────────────────────────────────────────────┘│ │
│  │                                                                          │ │
│  │  ┌─ Related Information ──────────────────────────────────────────────┐│ │
│  │  │  Contract Clause: 1.4 "Project Management Responsibilities"        ││ │
│  │  │  Budget Allocation: €3.8M (Phase 1, Line Item B-102)               ││ │
│  │  │  Schedule: Activity Act-203 to Act-215 (60 days)                   ││ │
│  │  │  Critical Path: Yes                                                ││ │
│  │  │                                                                     ││ │
│  │  │  [View Contract Clause] [View Budget] [View Schedule]              ││ │
│  │  └─────────────────────────────────────────────────────────────────────┘│ │
│  │                                                                          │ │
│  │  [Save Changes] [Cancel]                                                 │ │
│  │                                                                          │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Actions & Status Bar
**Top-level controls:**

#### Status Indicator
- **Auto-generated**: 🤖 Generated by AI, needs review
- **Approved**: ✅ All assignments approved
- **Partially Approved**: 🟡 Some approved, some pending
- **Modified**: 🔵 Manual edits made after approval

#### Action Buttons
- **Generate RACI**: Trigger AI generation from WBS and stakeholders
- **Approve All**: Bulk approve all pending assignments
- **Edit Mode**: Toggle inline editing
- **Export**: Download as Excel/CSV/PDF

### 2. Matrix Legend
**RACI Definitions:**
- **R - Responsible**: Does the work, executes tasks
- **A - Accountable**: Ultimately answerable, signs off, approves (only ONE per WBS item)
- **C - Consulted**: Provides input, expertise, two-way communication
- **I - Informed**: Kept updated, receives information, one-way communication

**Status Colors:**
- 🟢 **Green**: Approved by user
- 🟡 **Yellow**: Pending review (AI-generated)
- 🔵 **Blue**: Modified after approval
- 🔴 **Red**: Invalid (multiple A's, no A, etc.)

### 3. Filters & View Options

#### WBS Level Filter
- **All**: Show all WBS items (default)
- **Level 1-2**: Show only top 2 levels
- **Critical Path Only**: Show only critical path items

#### Stakeholder Filter
- **Show All**: Display all stakeholders
- **Key Players Only**: Filter to high power/interest
- **External Only**: Show only external stakeholders
- **By Department**: Filter by department

#### Highlight Options
- **None**: Normal view
- **No Accountable**: Highlight rows missing A role
- **Multiple Accountable**: Highlight rows with >1 A role
- **Gaps**: Highlight empty cells that should have assignments
- **Conflicts**: Show potential role conflicts

### 4. RACI Matrix Table

#### Column Headers
**Stakeholder Columns:**
- **Name**: First name
- **Role**: Job title (abbreviated)
- **Avatar**: Small photo/icon (optional)
- **Sortable**: Click to reorder

**Fixed Left Column:**
- **WBS Code and Name**
- **Budget**: Estimated budget
- **Status Icon**: 🟢🟡🔵⚠️
- **Expand/Collapse**: ▸ for hierarchy

#### Matrix Cells
**Each cell shows:**
- **RACI Letter**: R, A, C, I, or dash (-)
- **Status Indicator**: Color dot (🟢🟡🔵)
- **Hover**: Show rationale tooltip
- **Click**: Open edit modal
- **Right-click**: Context menu

#### Row Types
**Parent WBS Items:**
- **Bold text**
- **Indentation**: Level 1, 2, 3, 4
- **Expand icon**: ▸ to show/hide children
- **Aggregate status**: Worst status of children

**Child WBS Items:**
- **Normal text**
- **Indented**: Visual hierarchy
- **Individual status**

#### Warnings & Validations
**Inline warnings appear below row:**
- ⚠️ Multiple Accountable roles
- ⚠️ No Accountable role
- ⚠️ No Responsible role
- ⚠️ Critical path item unassigned

### 5. Summary Statistics Panel
**Key metrics:**
- **Total WBS Items**: Count
- **Approved**: Count and percentage
- **Pending**: Count and percentage
- **Issues**: Count of validation errors

**Issue List:**
- **Issue Type**: Description
- **Count**: How many affected
- **Actions**: View details, auto-fix

### 6. Cell Detail Modal

#### Current Assignment Section
- **Role**: Current RACI letter
- **Status**: Approval status
- **Timestamp**: When assigned
- **Approver**: Who approved (if approved)

#### Edit Assignment Section
- **Role Dropdown**: Change RACI letter or remove
- **Reason Field**: Optional explanation
- **Cascade Option**: Apply to child items
- **Notification**: Notify stakeholder checkbox

#### AI Rationale
**Why this assignment was made:**
- **Numbered reasons**: 3-5 bullet points
- **Confidence score**: 0-100%
- **Source references**: Contract clauses, documents

#### Related Information
**Contextual data:**
- **Contract Clause**: Relevant clause
- **Budget**: Amount and line item
- **Schedule**: Timeline and activities
- **Critical Path**: Yes/No

**Action Links:**
- View source documents
- Navigate to evidence
- See full context

---

## RACI Generation Flow

```
1. Click "Generate RACI"
     ↓
2. Confirmation Modal
   ┌─────────────────────────────────────────┐
   │ Generate RACI Matrix                    │
   │                                         │
   │ This will create RACI assignments for:  │
   │                                         │
   │ • 15 WBS items                          │
   │ • 18 stakeholders                       │
   │                                         │
   │ Based on:                               │
   │ ☑ Contract responsibilities             │
   │ ☑ Stakeholder roles and departments     │
   │ ☑ Budget approval thresholds            │
   │ ☑ Organizational hierarchy               │
   │                                         │
   │ ⚠️  This will overwrite existing        │
   │     assignments. Continue?              │
   │                                         │
   │ [Cancel] [Generate]                     │
   └─────────────────────────────────────────┘
     ↓
3. AI Processing (with progress)
     ↓
4. Results: Matrix populated with 🟡 (pending)
     ↓
5. User reviews and approves cell by cell
     or uses "Approve All"
```

---

## Validation Rules

### Rule 1: Exactly One Accountable
**Each WBS item must have exactly ONE "A"**
- Error if 0 Accountable
- Error if 2+ Accountable
- Warning shown inline

### Rule 2: At Least One Responsible
**Each WBS item should have at least ONE "R"**
- Warning if 0 Responsible
- OK to have multiple Responsible

### Rule 3: Accountable Cannot Be Responsible
**Same person should not be both A and R**
- Warning (not error)
- Best practice violation

### Rule 4: No Self-Consultation
**Person cannot consult themselves**
- If R or A, should not also be C
- Warning shown

### Rule 5: Critical Items Must Be Assigned
**Critical path items require all RACI roles**
- Error if any role missing
- Blocking validation

---

## Interactions

### Primary Actions
1. **Click Cell**: Open detail modal for editing
2. **Generate RACI**: AI-powered generation
3. **Approve**: Mark cell as approved
4. **Edit Role**: Change RACI letter
5. **Export**: Download matrix

### Secondary Actions
1. **Bulk Approve**: Approve row or column
2. **Copy Row**: Duplicate RACI pattern
3. **Filter**: Show subset of matrix
4. **Sort**: Reorder stakeholders
5. **Search**: Find specific stakeholder/WBS

### Keyboard Shortcuts
- **Tab**: Move to next cell
- **Shift+Tab**: Move to previous cell
- **Arrow Keys**: Navigate cells
- **R/A/C/I**: Quick assign role
- **Delete**: Remove assignment
- **Enter**: Open detail modal
- **Ctrl+S**: Save all changes

### Context Menu (Right-click)
- **Edit Assignment**
- **Copy to Children**
- **Clear Assignment**
- **Approve**
- **View Rationale**
- **Notify Stakeholder**

---

## Approval Workflow

### Individual Cell Approval
```
1. Review AI assignment and rationale
2. Click cell to open detail
3. Verify assignment is correct
4. Click "Approve" or edit and save
5. Cell turns green 🟢
```

### Bulk Approval
```
1. Review entire matrix
2. Click "Approve All" button
3. Confirmation modal appears
4. All pending cells turn green 🟢
5. Matrix status: "Approved"
```

### Modification After Approval
```
1. Approved cell (green)
2. User makes edit
3. Cell turns blue 🔵 (modified)
4. Requires re-approval (optional workflow)
```

---

## Export Formats

### Excel Export
- **Sheet 1**: RACI Matrix (with colors)
- **Sheet 2**: Stakeholder List
- **Sheet 3**: WBS List
- **Sheet 4**: Validation Issues

### CSV Export
- Simple table format
- RACI letters only
- No colors or formatting

### PDF Export
- Professional formatted report
- Cover page with summary
- Matrix with legend
- Issue list appendix

---

## Responsive Behavior

### Desktop (>1200px)
- Full matrix visible
- Side-scroll for many stakeholders
- Modal for cell details

### Tablet (768px - 1200px)
- Simplified columns
- Horizontal scroll
- Bottom sheet for details

### Mobile (<768px)
- List view (not matrix)
- Card per WBS item
- Show assigned stakeholders
- Tap to edit

---

## Color Coding

### Status Colors
- **Green (#00AA00)**: Approved
- **Yellow (#FFAA00)**: Pending review
- **Blue (#0066CC)**: Modified
- **Red (#CC0000)**: Validation error

### Role Colors (optional)
- **R (Blue)**: Responsible
- **A (Purple)**: Accountable
- **C (Orange)**: Consulted
- **I (Gray)**: Informed

---

## Accessibility

- **ARIA Labels**: All cells and headers
- **Keyboard Navigation**: Full matrix navigation
- **Screen Reader**:
  - Announce row and column
  - Read RACI role
  - Describe approval status
- **Focus Management**: Clear cell focus
- **Color Blind**: Letters + patterns

---

## Performance Optimization

### Large Matrices
- **Virtualization**: Render only visible rows
- **Lazy Loading**: Load data on scroll
- **Pagination**: 50 rows per page option

### Caching
- Cache RACI data locally
- Invalidate on edit
- Background sync

---

## Future Enhancements
- [ ] RACI templates by project type
- [ ] Historical comparison (before/after)
- [ ] Workload analysis (how many R's per person)
- [ ] Conflict detection (overloaded stakeholders)
- [ ] Integration with HR systems
- [ ] Auto-escalation for unassigned items
- [ ] Mobile-optimized list view
- [ ] Collaborative editing (real-time)
- [ ] Version control (RACI history)
- [ ] Custom role types (beyond RACI)
- [ ] AI suggestions based on changes
- [ ] Gantt-style timeline view
