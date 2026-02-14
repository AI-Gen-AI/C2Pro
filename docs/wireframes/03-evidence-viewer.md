# Evidence Viewer - Wireframe

**View:** Evidence Viewer
**Route:** `/projects/{id}/evidence` or triggered from Alert detail
**Purpose:** Visualize the full traceability chain from Contract Clause → WBS → BOM with bidirectional navigation

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  ◀ Back to Alerts            Hospital Central EPC Project                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Alert Context ───────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  🔴  CRITICAL: Date Mismatch - Contract vs Schedule                   │  │
│  │                                                                        │  │
│  │  Contract deadline differs from schedule end date by 15 days.         │  │
│  │  This could result in penalty charges and claims.                     │  │
│  │                                                                        │  │
│  │  Detected: January 21, 2026 at 14:23                                  │  │
│  │  Rule: R1 - Contract/Schedule Date Alignment                          │  │
│  │                                                                        │  │
│  │  [Mark as Resolved]  [Add Note]  [Escalate]                           │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Evidence Chain ──────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  1️⃣  CONTRACT CLAUSE                                             │ │  │
│  │  │  ─────────────────────────────────────────────────────────────   │ │  │
│  │  │                                                                   │ │  │
│  │  │  📄 Main Construction Contract - Clause 4.2                       │ │  │
│  │  │     "Execution Deadline"                                          │ │  │
│  │  │                                                                   │ │  │
│  │  │  "The Contractor shall complete all works by June 30, 2026.     │ │  │
│  │  │   Any delay beyond this date will result in liquidated damages  │ │  │
│  │  │   of €50,000 per day up to a maximum of €2,000,000."            │ │  │
│  │  │                                                                   │ │  │
│  │  │  📍 Source: contract_hospital_central_2026.pdf, Page 12, Line 8  │ │  │
│  │  │                                                                   │ │  │
│  │  │  Penalty Rate: €50,000/day  │  Max Penalty: €2,000,000          │ │  │
│  │  │  Contract Date: June 30, 2026                                    │ │  │
│  │  │                                                                   │ │  │
│  │  │  [View Full Contract] [View PDF at Location]                     │ │  │
│  │  │                                                                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                   │                                    │  │
│  │                                   │ linked by                          │  │
│  │                                   │ "requires completion of"           │  │
│  │                                   ▼                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  2️⃣  WBS ITEMS (3)                                                │ │  │
│  │  │  ─────────────────────────────────────────────────────────────   │ │  │
│  │  │                                                                   │ │  │
│  │  │  ▸ 1.0 Hospital Main Building                                    │ │  │
│  │  │    ├─ 1.1 Foundation & Structure          [80% Complete]         │ │  │
│  │  │    ├─ 1.2 Mechanical Systems               [45% Complete]         │ │  │
│  │  │    └─ 1.3 Finishes & Commissioning         [10% Complete]         │ │  │
│  │  │                                                                   │ │  │
│  │  │    Budget: €8,500,000  │  Timeline: Jan 2026 - Jun 2026          │ │  │
│  │  │    Critical Path: Yes  │  Responsible: Construction Manager      │ │  │
│  │  │                                                                   │ │  │
│  │  │  📍 Source: Generated from contract scope of work                 │ │  │
│  │  │                                                                   │ │  │
│  │  │  [View WBS Tree] [View Schedule]                                  │ │  │
│  │  │                                                                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                   │                                    │  │
│  │                                   │ requires                           │  │
│  │                                   ▼                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  3️⃣  SCHEDULE ACTIVITIES (5)                                      │ │  │
│  │  │  ─────────────────────────────────────────────────────────────   │ │  │
│  │  │                                                                   │ │  │
│  │  │  Act-101  Foundation Excavation       Jan 15 - Feb 10  ✅ Done   │ │  │
│  │  │  Act-102  Concrete Structure          Feb 11 - Apr 15  🔵 Active│ │  │
│  │  │  Act-103  MEP Installation            Apr 16 - Jun 10  ⏸ Pending│ │  │
│  │  │  Act-104  Interior Finishes           Jun 11 - Jul 05  ⏸ Pending│ │  │
│  │  │  Act-105  Final Commissioning         Jul 06 - Jul 15  ⏸ Pending│ │  │
│  │  │                                                ────────            │ │  │
│  │  │                                        Schedule End: July 15, 2026│ │  │
│  │  │                                                                   │ │  │
│  │  │  ⚠️  MISMATCH: Schedule end (Jul 15) is 15 days after contract   │ │  │
│  │  │      deadline (Jun 30). Potential penalty: €750,000               │ │  │
│  │  │                                                                   │ │  │
│  │  │  📍 Source: project_schedule_v3.xlsx, Sheet "Main Building"       │ │  │
│  │  │                                                                   │ │  │
│  │  │  [View Gantt Chart] [View Critical Path]                          │ │  │
│  │  │                                                                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                   │                                    │  │
│  │                                   │ needs materials                    │  │
│  │                                   ▼                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  4️⃣  BOM ITEMS (12)                                               │ │  │
│  │  │  ─────────────────────────────────────────────────────────────   │ │  │
│  │  │                                                                   │ │  │
│  │  │  Top Critical Items:                                              │ │  │
│  │  │                                                                   │ │  │
│  │  │  BOM-1205  HVAC Chillers (2 units)                               │ │  │
│  │  │            Lead Time: 90 days  │  Order by: Mar 10, 2026         │ │  │
│  │  │            Status: Not Ordered  ⚠️ Risk: 5 days until due        │ │  │
│  │  │                                                                   │ │  │
│  │  │  BOM-1206  Emergency Generators (3 units)                        │ │  │
│  │  │            Lead Time: 120 days  │  Order by: Feb 15, 2026        │ │  │
│  │  │            Status: On Order ✅  │  Arrival: Jun 05, 2026          │ │  │
│  │  │                                                                   │ │  │
│  │  │  BOM-1207  Surgical Lighting Systems                             │ │  │
│  │  │            Lead Time: 60 days  │  Order by: Apr 10, 2026         │ │  │
│  │  │            Status: Not Ordered  │  Risk: Medium                  │ │  │
│  │  │                                                                   │ │  │
│  │  │  [View All BOM Items] [View Procurement Plan]                     │ │  │
│  │  │                                                                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                   │                                    │  │
│  │                                   │ affects                            │  │
│  │                                   ▼                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  5️⃣  STAKEHOLDERS IMPACTED (4)                                    │ │  │
│  │  │  ─────────────────────────────────────────────────────────────   │ │  │
│  │  │                                                                   │ │  │
│  │  │  👤 Carlos Martínez - Project Manager (ACCOUNTABLE)              │ │  │
│  │  │     Power: High  │  Interest: High  │  Status: Notified          │ │  │
│  │  │                                                                   │ │  │
│  │  │  👤 Ana García - Client Representative (INFORMED)                │ │  │
│  │  │     Power: High  │  Interest: High  │  Status: Pending           │ │  │
│  │  │                                                                   │ │  │
│  │  │  👤 Miguel Rodríguez - Planning Manager (RESPONSIBLE)            │ │  │
│  │  │     Power: Medium  │  Interest: High  │  Status: Notified        │ │  │
│  │  │                                                                   │ │  │
│  │  │  👤 Laura Fernández - Procurement Manager (CONSULTED)            │ │  │
│  │  │     Power: Medium  │  Interest: Medium  │  Status: Notified      │ │  │
│  │  │                                                                   │ │  │
│  │  │  [Notify All] [View Stakeholder Map]                              │ │  │
│  │  │                                                                   │ │  │
│  │  └───────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Recommended Actions ─────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  1. 📅  Revise schedule to complete by June 30, 2026                  │  │
│  │         (Requires acceleration of 15 days)                            │  │
│  │                                                                        │  │
│  │  2. 📝  Request contract amendment to extend deadline                 │  │
│  │         (Submit change request to client)                             │  │
│  │                                                                        │  │
│  │  3. 💰  Reserve contingency for potential penalties                   │  │
│  │         (Reserve €750,000 in risk budget)                             │  │
│  │                                                                        │  │
│  │  4. 👥  Schedule urgent meeting with client and PMO                   │  │
│  │         (Discuss mitigation options)                                  │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ History & Notes ─────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  💬  Carlos Martínez - 2 hours ago                                    │  │
│  │      "I've contacted the client to discuss acceleration options.      │  │
│  │       Meeting scheduled for Friday."                                  │  │
│  │                                                                        │  │
│  │  💬  Miguel Rodríguez - 5 hours ago                                   │  │
│  │      "Reviewing schedule to identify tasks that can be fast-tracked." │  │
│  │                                                                        │  │
│  │  ─────────────────────────────────────────────────────────────────   │  │
│  │                                                                        │  │
│  │  [Add Note]                                                            │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Alert Context Panel
**Summary of the issue:**
- **Severity Icon**: 🔴 Critical, 🟡 High, 🔵 Medium, ⚪ Low
- **Alert Title**: Brief description
- **Alert Description**: Detailed explanation of the issue
- **Detection Info**: When detected, which rule triggered
- **Actions**:
  - Mark as Resolved
  - Add Note
  - Escalate
  - Assign to User

### 2. Evidence Chain
**Visual representation of the traceability flow:**

#### Step 1: Contract Clause
- **Document Icon**: 📄 Visual indicator
- **Clause Reference**: Clause number and title
- **Clause Text**: Relevant excerpt (highlighted)
- **Source Location**: Document name, page, line
- **Extracted Metadata**:
  - Penalty rates
  - Key dates
  - Financial impacts
  - Requirements
- **Actions**:
  - View Full Contract
  - View PDF at Location (scroll to clause)
  - Copy Clause Reference

#### Step 2: WBS Items
- **Hierarchy Tree**: Visual tree structure
- **Progress Indicators**: Percentage complete per item
- **Metrics**:
  - Budget allocation
  - Timeline
  - Critical path indicator
  - Responsible person
- **Source**: Where WBS was generated from
- **Actions**:
  - View WBS Tree
  - View Schedule
  - Edit WBS Item

#### Step 3: Schedule Activities
- **Activity List**: Chronological list of activities
- **Activity Details**:
  - Activity ID and name
  - Start and end dates
  - Status (Done, Active, Pending)
- **Mismatch Indicator**: Highlighted discrepancy
- **Impact Calculation**: Financial or schedule impact
- **Source**: Excel file, sheet name
- **Actions**:
  - View Gantt Chart
  - View Critical Path
  - Edit Schedule

#### Step 4: BOM Items
- **Material List**: Critical materials needed
- **Item Details**:
  - Item code and description
  - Lead time
  - Order by date
  - Status (Not Ordered, On Order, Delivered)
  - Risk indicator
- **Actions**:
  - View All BOM Items
  - View Procurement Plan
  - Create Purchase Order

#### Step 5: Stakeholders Impacted
- **Stakeholder Cards**: People who need to be informed
- **Stakeholder Details**:
  - Name and role
  - RACI role (Accountable, Responsible, Consulted, Informed)
  - Power and Interest levels
  - Notification status
- **Actions**:
  - Notify All
  - View Stakeholder Map
  - Send Individual Notification

### 3. Recommended Actions Panel
**AI-generated recommendations:**
- **Numbered List**: Priority-ordered actions
- **Action Type Icons**:
  - 📅 Schedule
  - 📝 Documentation
  - 💰 Financial
  - 👥 People
- **Action Description**: What to do
- **Sub-text**: Why or how to do it

### 4. History & Notes
**Collaboration space:**
- **Note Cards**: User comments with timestamp
- **User Attribution**: Who wrote each note
- **Add Note**: Text area to add new notes
- **Attachments**: Optional file attachments (future)

---

## Navigation Flow

### Entry Points
1. **From Alert**: Click alert in Dashboard or Alerts page
2. **From Project Detail**: View Evidence button
3. **From Search**: Direct link to evidence chain

### Bidirectional Navigation
```
Contract Clause ⇄ WBS Item ⇄ Schedule Activity ⇄ BOM Item ⇄ Stakeholder
```

**Click any item to:**
- Expand details
- Navigate to related items
- View in original context
- Edit (if permissions allow)

### Exit Points
1. **Back Button**: Return to previous view
2. **Project Link**: Go to project detail
3. **Breadcrumb Navigation**: Navigate hierarchy

---

## Interactions

### Primary Actions
1. **View Document at Location**: Opens PDF viewer scrolled to exact clause
2. **Navigate Chain**: Click on any entity to see its connections
3. **Mark as Resolved**: Close alert with resolution note
4. **Notify Stakeholder**: Send notification to specific person
5. **Add Note**: Collaborate with comments

### Secondary Actions
1. **Copy Reference**: Copy clause/WBS/BOM reference to clipboard
2. **Export Evidence**: Download evidence chain as PDF
3. **Create Task**: Generate action item from recommendation
4. **Escalate**: Flag for management attention

### Hover States
- **Hover Clause**: Show full text in tooltip
- **Hover WBS**: Show budget and timeline details
- **Hover Activity**: Show dependencies and progress
- **Hover BOM**: Show supplier and cost details
- **Hover Stakeholder**: Show contact information

---

## Responsive Behavior

### Desktop (>1200px)
- Full vertical chain layout
- All details visible
- Side panels for actions

### Tablet (768px - 1200px)
- Vertical chain with collapsible sections
- Expand/collapse each evidence step
- Bottom drawer for actions

### Mobile (<768px)
- Accordion-style chain
- One section expanded at a time
- Swipe between evidence steps
- Floating action button

---

## Visual Design

### Connection Lines
- **Visual Flow**: Arrows connecting evidence steps
- **Relationship Labels**: Text describing connection type
- **Animated**: Subtle animation on page load

### Highlighting
- **Mismatches**: Red highlight for discrepancies
- **Matches**: Green checkmark for aligned items
- **Warnings**: Yellow for potential issues

### Color Coding
- **Critical Path**: Red outline
- **On Track**: Green outline
- **At Risk**: Yellow outline
- **Complete**: Gray outline

---

## Data Integrity

### Source Attribution
**Every piece of evidence shows:**
- Original document name
- Page number (for PDFs)
- Sheet name (for Excel)
- Line number (for text)
- Timestamp of extraction
- Confidence score (AI extraction)

### Version Control
**Track document versions:**
- Document version number
- Last modified date
- Link to version history
- Warning if document updated since extraction

---

## Accessibility

- **ARIA Labels**: All chain steps and connections
- **Keyboard Navigation**:
  - Tab through evidence steps
  - Arrow keys to navigate chain
  - Enter to expand/collapse
- **Screen Reader**:
  - Describe relationships
  - Read evidence details
  - Announce actions
- **Focus Management**: Clear visual focus
- **Color Blind**: Patterns in addition to colors

---

## Performance Optimization

### Lazy Loading
- Load evidence on demand
- Progressive disclosure
- Virtualize long lists

### Caching
- Cache evidence chains
- Invalidate on document update
- Pre-fetch related items

---

## Future Enhancements
- [ ] Interactive graph visualization (D3.js)
- [ ] 3D relationship viewer
- [ ] Timeline view of evidence evolution
- [ ] Evidence comparison (before/after)
- [ ] AI explanation of relationships
- [ ] Export to multiple formats
- [ ] Collaborative annotations
- [ ] Evidence templates
- [ ] Custom evidence chains
- [ ] Integration with project chat

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
