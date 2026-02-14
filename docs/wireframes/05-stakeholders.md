# Stakeholders Map - Wireframe

**View:** Stakeholder Management
**Route:** `/projects/{id}/stakeholders`
**Purpose:** Visual power/interest matrix with stakeholder classification, extraction, and management

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  ◀ Back to Project          Hospital Central EPC Project                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Stakeholders ─────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌─ Actions ───────────────────────────────────────────────────────┐  │ │
│  │  │  [🤖 Extract from Documents]  [+ Add Manually]  [Export CSV]    │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ┌─ View Toggle ───────────────────────────────────────────────────┐  │ │
│  │  │  [● Matrix View]  [○ List View]  [○ Org Chart]                  │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Power / Interest Matrix ──────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  Power                                                                  │ │
│  │    ▲                                                                    │ │
│  │    │                                                                    │ │
│  │  H │ ┌─────────────────────────┬─────────────────────────┐            │ │
│  │  I │ │  KEEP SATISFIED (3)     │  KEY PLAYERS (5)        │            │ │
│  │  G │ │                         │                         │            │ │
│  │  H │ │  👤 Juan Torres         │  👤 Carlos Martínez    │            │ │
│  │    │ │     Legal Counsel       │     Project Manager     │            │ │
│  │    │ │                         │     🎯 Accountable      │            │ │
│  │    │ │  👤 Patricia López      │                         │            │ │
│  │    │ │     CFO                 │  👤 Ana García          │            │ │
│  │    │ │                         │     Client Rep          │            │ │
│  │    │ │  👤 Ricardo Vega        │     🎯 Informed         │            │ │
│  │    │ │     HSE Officer         │                         │            │ │
│  │    │ │     🎯 Consulted        │  👤 Miguel Rodríguez    │            │ │
│  │    │ │                         │     Planning Manager    │            │ │
│  │    │ │                         │     🎯 Responsible      │            │ │
│  │    │ │                         │                         │            │ │
│  │    │ │                         │  👤 Carmen Sánchez      │            │ │
│  │    │ │                         │     Quality Manager     │            │ │
│  │    │ │                         │     🎯 Consulted        │            │ │
│  │    │ │                         │                         │            │ │
│  │    │ │                         │  👤 Dr. Elena Morales   │            │ │
│  │    │ │                         │     Hospital Director   │            │ │
│  │    ├─┼─────────────────────────┼─────────────────────────┤            │ │
│  │    │ │  MONITOR (4)            │  KEEP INFORMED (6)      │            │ │
│  │    │ │                         │                         │            │ │
│  │  L │ │  👤 Pedro Ramírez       │  👤 Laura Fernández    │            │ │
│  │  O │ │     IT Coordinator      │     Procurement Mgr     │            │ │
│  │  W │ │                         │     🎯 Responsible      │            │ │
│  │    │ │  👤 Sofia Martín        │                         │            │ │
│  │    │ │     Admin Assistant     │  👤 Luis Gómez          │            │ │
│  │    │ │                         │     Electrical Eng      │            │ │
│  │    │ │  👤 Roberto Díaz        │     🎯 Responsible      │            │ │
│  │    │ │     Facilities Mgr      │                         │            │ │
│  │    │ │                         │  👤 María Jiménez       │            │ │
│  │    │ │  👤 Isabel Núñez        │     HVAC Specialist     │            │ │
│  │    │ │     Comms Manager       │                         │            │ │
│  │    │ │                         │  👤 Antonio Ruiz        │            │ │
│  │    │ │                         │     Site Supervisor     │            │ │
│  │    │ │                         │                         │            │ │
│  │    │ │                         │  👤 Beatriz Ortega      │            │ │
│  │    │ │                         │     Document Control    │            │ │
│  │    │ │                         │                         │            │ │
│  │    │ │                         │  👤 Javier Castro       │            │ │
│  │    │ │                         │     Safety Inspector    │            │ │
│  │    │ └─────────────────────────┴─────────────────────────┘            │ │
│  │    │                                                                   │ │
│  │    └────────────────────────────────────────────────────────────────▶ │ │
│  │                           LOW                   HIGH         Interest  │ │
│  │                                                                         │ │
│  │  ┌─ Legend ────────────────────────────────────────────────────────┐  │ │
│  │  │  🎯 RACI Role    │  ✅ Verified    │  🤖 Auto-extracted         │  │ │
│  │  │  📧 Email Sent   │  ⚠️ Missing Info │  📱 Phone Available        │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  💡 Tip: Drag stakeholders to adjust their position in the matrix      │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Stakeholder Detail (shown on click) ─────────────────────────────────┐  │
│  │                                                                         │  │
│  │  👤 Carlos Martínez                                         [X] Close   │  │
│  │     Project Manager - Hospital Central EPC                             │  │
│  │                                                                         │  │
│  │  ┌─ Basic Information ────────────────────────────────────────────┐   │  │
│  │  │  Name: Carlos Martínez González                               │   │  │
│  │  │  Role: Project Manager                                        │   │  │
│  │  │  Organization: BuildCo S.A.                                   │   │  │
│  │  │  Department: Project Management Office                        │   │  │
│  │  │                                                                │   │  │
│  │  │  📧 c.martinez@buildco.es                                     │   │  │
│  │  │  📱 +34 600 123 456                                           │   │  │
│  │  │                                                                │   │  │
│  │  │  Status: ✅ Verified manually                                 │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌─ Classification ───────────────────────────────────────────────┐   │  │
│  │  │  Power Level:    ███████████░░░░░  High (9/10)                │   │  │
│  │  │  Interest Level: ████████████████  High (10/10)               │   │  │
│  │  │                                                                │   │  │
│  │  │  Quadrant: 🎯 KEY PLAYER (Manage Closely)                     │   │  │
│  │  │                                                                │   │  │
│  │  │  Communication Preference: Email + Weekly Meetings            │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌─ RACI Responsibilities (8 WBS items) ─────────────────────────┐   │  │
│  │  │                                                                │   │  │
│  │  │  WBS 1.0  Hospital Main Building          [A] Accountable     │   │  │
│  │  │  WBS 1.1  Foundation & Structure          [A] Accountable     │   │  │
│  │  │  WBS 1.2  Mechanical Systems              [A] Accountable     │   │  │
│  │  │  WBS 1.3  Finishes & Commissioning        [A] Accountable     │   │  │
│  │  │  WBS 2.0  Emergency Department            [A] Accountable     │   │  │
│  │  │  WBS 3.0  Parking Structure               [C] Consulted       │   │  │
│  │  │  WBS 4.0  Landscaping                     [I] Informed        │   │  │
│  │  │  WBS 5.0  Medical Equipment               [C] Consulted       │   │  │
│  │  │                                                                │   │  │
│  │  │  [View Full RACI Matrix →]                                    │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌─ Implicit Needs (AI-inferred) ────────────────────────────────┐   │  │
│  │  │                                                                │   │  │
│  │  │  🎯 Primary Concerns:                                          │   │  │
│  │  │     • Meeting contractual deadlines                           │   │  │
│  │  │     • Budget control and cost management                      │   │  │
│  │  │     • Client satisfaction and relationship                    │   │  │
│  │  │                                                                │   │  │
│  │  │  📊 Risk Tolerance: Low (based on penalty clauses emphasis)   │   │  │
│  │  │  ⏰ Time vs Cost Priority: Time (penalties > cost)            │   │  │
│  │  │                                                                │   │  │
│  │  │  📍 Inferred from: Contract Clause 1.4, 4.2, 5.1              │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌─ Alerts & Notifications (3) ──────────────────────────────────┐   │  │
│  │  │                                                                │   │  │
│  │  │  🔴 Date Mismatch: Contract vs Schedule     [View]            │   │  │
│  │  │     Sent: 2 hours ago  │  Status: Read ✅                     │   │  │
│  │  │                                                                │   │  │
│  │  │  🔵 WBS Item Without Budget                 [View]            │   │  │
│  │  │     Sent: 2 days ago   │  Status: Acknowledged ✅             │   │  │
│  │  │                                                                │   │  │
│  │  │  🟡 Material Lead Time Risk                 [View]            │   │  │
│  │  │     Pending  │  Will send tomorrow                            │   │  │
│  │  │                                                                │   │  │
│  │  │  [View All Alerts →]                                           │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌─ Source & Confidence ──────────────────────────────────────────┐   │  │
│  │  │  Extracted from: contract_hospital_central_2026.pdf            │   │  │
│  │  │  Source Clause: Clause 1.2 "Project Organization"             │   │  │
│  │  │  Extraction Date: January 15, 2026                            │   │  │
│  │  │  AI Confidence: 95%                                            │   │  │
│  │  │  Manually Verified: ✅ Yes (by Admin on Jan 16, 2026)         │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                         │  │
│  │  [Edit Stakeholder]  [Send Notification]  [Export vCard]  [Delete]     │  │
│  │                                                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Actions Bar
**Primary actions:**
- **Extract from Documents**: Launch AI extraction from contracts/org charts
- **Add Manually**: Manual stakeholder creation form
- **Export CSV**: Download stakeholder list

### 2. View Toggle
**Three view modes:**
- **Matrix View** (default): Power/Interest grid
- **List View**: Tabular list with all details
- **Org Chart**: Hierarchical organization chart (future)

### 3. Power/Interest Matrix

#### Four Quadrants

**Top-Right: KEY PLAYERS (High Power, High Interest)**
- **Strategy**: Manage Closely
- **Color**: Green background
- **Priority**: Highest
- **Actions**: Active engagement, frequent updates

**Top-Left: KEEP SATISFIED (High Power, Low Interest)**
- **Strategy**: Keep Satisfied
- **Color**: Blue background
- **Priority**: High
- **Actions**: Keep informed, don't overload

**Bottom-Right: KEEP INFORMED (Low Power, High Interest)**
- **Strategy**: Keep Informed
- **Color**: Yellow background
- **Priority**: Medium
- **Actions**: Regular updates, consult on specifics

**Bottom-Left: MONITOR (Low Power, Low Interest)**
- **Strategy**: Monitor
- **Color**: Gray background
- **Priority**: Low
- **Actions**: Minimal effort, general updates

#### Stakeholder Cards (in matrix)
Each stakeholder appears as a draggable card:
- **Avatar**: 👤 Icon or photo
- **Name**: Full name
- **Role**: Job title
- **RACI Badge**: 🎯 Primary RACI role
- **Status Indicator**:
  - ✅ Verified
  - 🤖 Auto-extracted
  - ⚠️ Missing info

#### Drag & Drop
- **Move Stakeholders**: Drag to reposition
- **Reclassify**: Updates power/interest levels
- **Visual Feedback**: Ghosted outline while dragging
- **Snap to Grid**: Aligns to quadrant boundaries

### 4. Legend
**Icon explanations:**
- 🎯 RACI Role assigned
- ✅ Manually verified
- 🤖 Auto-extracted by AI
- 📧 Email notification sent
- ⚠️ Missing contact information
- 📱 Phone number available

### 5. Stakeholder Detail Panel

#### Basic Information
- **Full Name**: First and last name
- **Role**: Job title
- **Organization**: Company/entity
- **Department**: Department/division
- **Contact**:
  - Email address
  - Phone number
  - Office location (optional)
- **Status**: Verification status

#### Classification
- **Power Level**: 1-10 slider with visual bar
- **Interest Level**: 1-10 slider with visual bar
- **Quadrant**: Auto-calculated from power/interest
- **Communication Preference**: How they prefer to be contacted

#### RACI Responsibilities
- **List of WBS Items**: All WBS items assigned to this stakeholder
- **RACI Role per Item**: R, A, C, or I
- **Count**: Total assignments
- **Link**: View full RACI matrix

#### Implicit Needs (AI-inferred)
- **Primary Concerns**: Top 3-5 concerns based on contract analysis
- **Risk Tolerance**: High, Medium, Low
- **Time vs Cost Priority**: Which matters more
- **Source**: Contract clauses used for inference

#### Alerts & Notifications
- **Alert List**: Alerts relevant to this stakeholder
- **Notification Status**: Sent, Read, Acknowledged, Pending
- **Action Links**: View alert details
- **Summary**: Count of open/resolved alerts

#### Source & Confidence
- **Extraction Source**: Document where stakeholder was found
- **Source Clause**: Specific contract clause
- **Extraction Date**: When AI extracted
- **AI Confidence**: Percentage (0-100%)
- **Manual Verification**: Who verified and when

#### Actions
- **Edit Stakeholder**: Update information
- **Send Notification**: Send email/SMS
- **Export vCard**: Download contact card
- **Delete**: Remove stakeholder (with confirmation)

---

## Stakeholder Extraction Flow

```
1. Click "Extract from Documents"
     ↓
2. Extraction Modal Opens
   ┌─────────────────────────────────────────┐
   │ Extract Stakeholders from Documents     │
   │                                         │
   │ Select document sources:                │
   │ ☑ Main Construction Contract            │
   │ ☑ Org Chart (if uploaded)               │
   │ ☐ Meeting Minutes                       │
   │ ☐ Email Correspondence                  │
   │                                         │
   │ Extraction settings:                    │
   │ ☑ Extract names and roles               │
   │ ☑ Extract contact information           │
   │ ☑ Infer power and interest              │
   │ ☑ Classify by department                │
   │                                         │
   │ [Cancel] [Start Extraction]             │
   └─────────────────────────────────────────┘
     ↓
3. AI Processing (with progress bar)
     ↓
4. Results Modal
   ┌─────────────────────────────────────────┐
   │ Extraction Complete: 18 stakeholders    │
   │                                         │
   │ ✅ 12 with full contact info            │
   │ ⚠️  6 with partial info                 │
   │                                         │
   │ Review and confirm:                     │
   │                                         │
   │ ☑ Carlos Martínez - PM  (Conf: 95%)    │
   │ ☑ Ana García - Client   (Conf: 92%)    │
   │ ☐ Juan [Last name?] - ? (Conf: 65%)    │
   │ ...                                     │
   │                                         │
   │ [Cancel] [Import Selected]              │
   └─────────────────────────────────────────┘
     ↓
5. Stakeholders added to matrix
   Auto-positioned based on classification
```

---

## List View Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Stakeholder Name    Role           Org        Power  Interest  RACI  Status│
│  ───────────────────────────────────────────────────────────────────────────│
│  👤 Carlos Martínez  Project Mgr    BuildCo    High   High      A     ✅    │
│  👤 Ana García       Client Rep     Hospital   High   High      I     ✅    │
│  👤 Miguel Rodríguez Planning Mgr   BuildCo    High   High      R     ✅    │
│  👤 Laura Fernández  Procurement    BuildCo    Low    High      R     🤖    │
│  👤 Ricardo Vega     HSE Officer    BuildCo    High   Low       C     ✅    │
│  ...                                                                         │
│                                                                              │
│  [Export CSV]  [Bulk Edit]  [Send Notifications]                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Interactions

### Primary Actions
1. **Click Stakeholder Card**: Open detail panel
2. **Drag Stakeholder**: Reposition in matrix
3. **Extract from Documents**: AI-powered extraction
4. **Add Manually**: Create new stakeholder
5. **Send Notification**: Email/SMS to stakeholder

### Secondary Actions
1. **Edit Classification**: Adjust power/interest
2. **Verify Stakeholder**: Mark as manually verified
3. **Export List**: Download as CSV/vCard
4. **Filter by Department**: Show specific departments
5. **Search**: Find stakeholder by name

### Matrix Interactions
- **Hover Card**: Show quick preview tooltip
- **Click Card**: Open detail panel
- **Drag Card**: Move to new quadrant
- **Right-click**: Context menu (Edit, Delete, Notify)

---

## Responsive Behavior

### Desktop (>1200px)
- Full matrix layout
- Side panel for details
- Drag and drop enabled

### Tablet (768px - 1200px)
- Simplified matrix
- Modal for details
- Touch-optimized drag

### Mobile (<768px)
- List view only (matrix too complex)
- Cards with expand/collapse
- Swipe gestures

---

## Quadrant Strategies (Help Text)

### KEY PLAYERS
**When to engage:**
- Project initiation and planning
- Major decisions
- Change requests
- Risk mitigation
- Monthly steering meetings

**Communication:**
- Weekly status updates
- Immediate notification of issues
- Direct access to project manager

### KEEP SATISFIED
**When to engage:**
- Major milestones
- Budget changes
- Contract amendments
- Quarterly reviews

**Communication:**
- Monthly summary reports
- Notification of significant changes
- On-demand meetings

### KEEP INFORMED
**When to engage:**
- Progress updates
- Schedule changes
- Technical decisions in their area
- Weekly coordination meetings

**Communication:**
- Weekly progress reports
- Task-specific updates
- Email notifications

### MONITOR
**When to engage:**
- General project updates
- Final completion

**Communication:**
- Monthly newsletters
- Public announcements
- Low-priority notifications

---

## Automated Classification Rules

**AI uses these factors to classify:**

### Power (Authority/Influence)
- **High**: CEO, Project Sponsor, Client Representative, Legal Signatory
- **Medium**: Department Heads, Project Manager, Senior Engineers
- **Low**: Team Members, Specialists, Support Staff

### Interest (Involvement/Impact)
- **High**: Project Manager, Team Leads, Quality Manager, affected by outcomes
- **Medium**: Supporting roles, occasional involvement
- **Low**: Awareness only, minimal impact

### Adjustments Based On:
- Approval thresholds in contract
- Frequency of mention in documents
- RACI role assignments
- Department criticality
- Budget authority

---

## Notifications System

### Notification Types
1. **Alert Notification**: New coherence alert
2. **Status Update**: Project milestone reached
3. **Action Required**: Approval needed
4. **Information**: General update

### Notification Channels
- **Email**: Primary channel
- **SMS**: For urgent critical issues
- **In-app**: Dashboard notification badge
- **Slack/Teams**: If integrated (future)

### Notification Preferences
**Per stakeholder:**
- Channel preference
- Frequency (Immediate, Daily Digest, Weekly)
- Severity filter (Critical only, High+, All)

---

## Accessibility

- **ARIA Labels**: All matrix quadrants and cards
- **Keyboard Navigation**:
  - Tab through stakeholders
  - Arrow keys to move in matrix
  - Enter to open detail
- **Screen Reader**:
  - Announce quadrant
  - Read power/interest levels
  - Describe RACI roles
- **Focus Management**: Clear visual focus
- **Color Blind**: Patterns + text labels

---

## Future Enhancements
- [ ] Org chart visualization (hierarchical tree)
- [ ] Stakeholder network graph (relationships)
- [ ] Influence mapping (who influences whom)
- [ ] Historical tracking (power/interest over time)
- [ ] Sentiment analysis (from communications)
- [ ] Meeting scheduler integration
- [ ] Automated communication templates
- [ ] Stakeholder engagement score
- [ ] Conflict identification
- [ ] Succession planning (backup contacts)

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
