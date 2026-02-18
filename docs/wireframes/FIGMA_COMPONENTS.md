# C2Pro - Figma Component Specifications
**Version:** 1.0 | **Date:** 2026-02-18

---

## Component Library Reference

All components are organized in Figma using Auto Layout and component variants.
Each component has: Default, Hover, Active, Disabled, and Focus states.

---

## 1. BUTTONS

### Primary Button
```
┌─────────────────────────┐
│  [Icon?]   Label Text   │  H: 40px | Padding: 12px 24px
└─────────────────────────┘  Background: #0066CC | Text: #FFFFFF
                             Radius: 4px | Font: 14px 600
```
**Variants:** Default | Hover (#0052A3) | Active (#003E7A) | Disabled (#CCCCCC) | Loading (spinner)
**Sizes:** Large (48px) | Default (40px) | Small (32px)
**With Icons:** Leading | Trailing | Icon Only

### Secondary Button
```
┌─────────────────────────┐
│  [Icon?]   Label Text   │  H: 40px | Padding: 12px 24px
└─────────────────────────┘  Background: #F5F5F5 | Border: #E0E0E0
                             Text: #222222 | Radius: 4px
```
**Variants:** Default | Hover (#EBEBEB) | Active | Disabled | Loading

### Danger Button
```
┌─────────────────────────┐
│  [Icon?]   Label Text   │  H: 40px | Background: #CC0000
└─────────────────────────┘  Text: #FFFFFF | Radius: 4px
```
**Variants:** Default | Hover (#A30000) | Active | Disabled

### Ghost/Link Button
```
  Label Text              No background, just text
```
**Variants:** Default (#0066CC) | Hover (underline) | Active | Disabled

---

## 2. INPUT FIELDS

### Text Input
```
Label Text
┌──────────────────────────────┐
│ Placeholder text          [X]│  H: 40px | Padding: 12px
└──────────────────────────────┘  Border: #E0E0E0 | Radius: 4px
Helper text / Error text
```
**States:** Default | Focus (blue border) | Error (red border + message) | Disabled | Success (green)
**Types:** Text | Email | Password (toggle show/hide) | Number | URL

### Select Dropdown
```
Label Text
┌──────────────────────────────┐
│ Selected option         [▼] │  H: 40px
└──────────────────────────────┘
```
**Dropdown Panel:**
```
┌──────────────────────────────┐
│ Option 1                     │
│ Option 2  ← selected         │  Max-height: 240px
│ Option 3                     │  Overflow: scroll
└──────────────────────────────┘
```

### Textarea
```
Label Text
┌──────────────────────────────┐
│                              │
│ Placeholder...               │  H: 80-120px | Resizable
│                              │
└──────────────────────────────┘
```

### Checkbox
```
☑ Label text                   H: 20px | Check: #0066CC
☐ Label text                   Unchecked: border #E0E0E0
                               Indeterminate: — dash state
```

### Radio Button
```
⦿ Option A                     Selected: #0066CC filled
○ Option B                     Unselected: border #E0E0E0
○ Option C
```

### Toggle Switch
```
|●──────| ON                   W: 44px H: 24px
|──────●| OFF                  Thumb: white circle
                               ON: #0066CC | OFF: #CCCCCC
```

### Search Input
```
┌─[🔍]────────────────────[X]─┐
│ Search...                    │  H: 40px
└──────────────────────────────┘
```
**With autocomplete dropdown:**
```
┌──────────────────────────────┐
│ 🔍 Search...                 │
└──────────────────────────────┘
┌──────────────────────────────┐
│ Result 1                     │
│ Result 2  ← highlighted      │  Autocomplete panel
│ Result 3                     │
└──────────────────────────────┘
```

---

## 3. CARDS

### Default Card
```
┌─────────────────────────────────┐
│ Card Title                      │  Padding: 24px
│ ─────────────────────────────   │  Border: 1px #E0E0E0
│                                 │  Radius: 8px
│ Card content goes here          │  Shadow: Low elevation
│                                 │
└─────────────────────────────────┘
```

### Stats Card
```
┌─────────────────────────────────┐
│ [Icon] Label                    │  W: flex | H: 120px
│                                 │  Used in dashboard
│ 1,234                      ▲12% │  Number: 32px Bold
│                                 │  Trend: green/red
└─────────────────────────────────┘
```

### Project Card (for card view)
```
┌─────────────────────────────────┐
│ PROJECT NAME                    │
│ Status Badge | Type             │  W: flex | H: auto
│                                 │  Used in projects list
│ [====Gauge====] 74/100          │
│                                 │
│ Docs: 8  |  Alerts: 3           │
│ Last updated: 2h ago            │
│ ─────────────────────────────   │
│ [View]           [⋯ More]       │
└─────────────────────────────────┘
```

### Alert Card
```
┌─[RED LEFT BAR]──────────────────┐
│ 🔴 CRITICAL   Alert Title       │  Left border: 4px colored
│                                 │  Color = severity color
│ Brief description of the alert  │
│ Project: [Name] | 2h ago        │
│ ─────────────────────────────   │
│ [Resolve]     [View Details]    │
└─────────────────────────────────┘
```

---

## 4. TABLES

### Table Structure
```
┌──┬──────────────────┬──────┬──────┬────────────┬────────┐
│☐ │ Name             │ Type │ Score│ Updated    │ Actions│  Header: bg #F5F5F5
├──┼──────────────────┼──────┼──────┼────────────┼────────┤  Font: 12px 600
│☐ │ Project Alpha    │ Infra│  85  │ 2h ago     │ ...    │  Row H: 48px
├──┼──────────────────┼──────┼──────┼────────────┼────────┤  Hover: #F9F9F9
│☐ │ Project Beta     │ Civil│  72  │ 1d ago     │ ...    │  Border: #E0E0E0
└──┴──────────────────┴──────┴──────┴────────────┴────────┘
                                                  [Showing 1-10 of 24]
```

### Pagination
```
[←] [1] [2] [3] ... [8] [→]         Showing X-Y of Z
Show: [10 ▼] per page
```

### Sortable Column Headers
```
┌─────────────────┐
│ Name          ▲ │  Arrow up = sorted ascending
│ Score         ▽ │  Arrow down = sorted descending
│ Updated         │  No arrow = unsorted
└─────────────────┘
```

---

## 5. NAVIGATION COMPONENTS

### Sidebar
```
┌──────────────────┐
│ C2Pro            │  W: 240px (expanded) | 64px (collapsed)
│ Logo + Brand     │  Background: #222222 or #FFFFFF
├──────────────────┤
│ 🏠 Dashboard     │  Active: blue left border + text
│ 📁 Projects      │  Hover: bg tint
│ 📄 Documents     │  Icon: 20px
│ 📊 Coherence     │  Text: 14px 500
│ 🔗 Evidence      │
│ 🚨 Alerts     [3]│  Notification badge (red circle)
│ 👥 Stakeholders  │
│ 📊 RACI          │
├──────────────────┤
│ ⚙️ Settings      │  Bottom section
│ ❓ Help          │
│ ⏏ Logout        │
└──────────────────┘
```

### Breadcrumbs
```
Dashboard / Projects / Project Alpha / Evidence
            ↑clickable links             ↑current page
```
Font: 12px | Color: #666666 | Active: #0066CC | Separator: /

### Tabs
```
┌──────────┬──────────┬──────────┬──────────┐
│ Overview │ Analysis │Documents │  Alerts  │  Active: blue border bottom
├──────────┴──────────┴──────────┴──────────┤  Hover: bg tint
│  Active tab content                        │  Inactive: gray text
└────────────────────────────────────────────┘
```

### Dropdown Menu
```
         ┌────────────────────┐
         │ 👤 Profile Settings│
         │ 🏢 Organization    │  W: 200px
         │ ⚙️ Preferences     │  Shadow: high elevation
         │ ─────────────────  │  Radius: 8px
         │ 📖 Documentation   │
         │ 🐛 Report Bug      │
         │ ─────────────────  │
         │ ⏏️ Logout          │
         └────────────────────┘
```

---

## 6. BADGES & STATUS

### Status Badges
```
┌──────────┐  Background colors:
│ CRITICAL │  Critical: #CC0000 bg, #FFFFFF text
└──────────┘  High: #FFAA00 bg, #222222 text
              Medium: #0066CC bg, #FFFFFF text
              Low: #E0E0E0 bg, #222222 text
              Good: #00AA00 bg, #FFFFFF text
```

### Score Indicator
```
[████████░░░░] 74/100    Color = score range
                         81-100: #00AA00
                         61-80: #FFAA00
                         0-60: #CC0000
```

### RACI Role Badge
```
[R] Responsible  → Green bg
[A] Accountable  → Blue bg
[C] Consulted    → Yellow bg
[I] Informed     → Gray bg
```

---

## 7. DATA VISUALIZATION COMPONENTS

### Coherence Gauge
```
        ╭──────╮
      ╱  74/100 ╲        Semi-circular gauge
    ╱    FAIR    ╲       Color = score range
   ╰──────────────╯      Arc fills from left
```
- Min value: 0 | Max value: 100
- Arc: 270° sweep
- Indicator: pointer or filled arc
- Label: score + category text below

### Category Bar Chart
```
Contracts  [████████████████████░░░░░░░░░░] 85
Schedule   [████████████░░░░░░░░░░░░░░░░░░] 60
Budget     [██████████████████░░░░░░░░░░░░] 72

           0          50         100
```
- Horizontal bars
- Color-coded (green/yellow/red based on score)
- Labels on left, values on right
- Category name above or left

### Radar Chart
```
         Contracts
            ●
          ╱   ╲
Evidence●       ●Schedule
         ╲   ╱
          ●   ●
        Budget  Stakeholders
```
- 5-8 axes
- Inner polygon = current scores
- Outer circle = 100 (target)
- Color fill: semi-transparent blue
- Points: blue dots

### Trend Indicators
```
▲ +12%  (green, going up = good)
▼ -5%   (red, going down = bad)
● 0%    (neutral)
```

---

## 8. MODALS & OVERLAYS

### Modal Template
```
╔═══════════════════════════════════════╗
║ Modal Title                      [X] ║  Overlay: rgba(0,0,0,0.5)
║ ─────────────────────────────────── ║  W: 600px max | Radius: 8px
║                                       ║  Padding: 32px
║ Modal content goes here               ║
║                                       ║
║ Supporting text or form fields        ║
║                                       ║
║ ─────────────────────────────────── ║
║                  [Cancel] [Confirm]  ║
╚═══════════════════════════════════════╝
```

### Alert Messages (inline)
```
┌─[✓]──────────────────────────────────┐
│ Success: Your changes have been saved.│  Left icon + color border
└──────────────────────────────────────┘

┌─[⚠]──────────────────────────────────┐
│ Warning: Review the highlighted items.│
└──────────────────────────────────────┘

┌─[✗]──────────────────────────────────┐
│ Error: Could not save your changes.   │
└──────────────────────────────────────┘
```

### Toast Notification (position: bottom-right)
```
                    ┌──────────────────────────┐
                    │ ✓ Project saved!      [X]│  W: 320px
                    └──────────────────────────┘  Animation: slide in
```

---

## 9. SPECIALIZED COMPONENTS

### Coherence Score Card
```
┌─────────────────────────────────────┐
│ COHERENCE SCORE          [Refresh]  │
│                                     │
│         ╭────────╮                  │
│       ╱   74/100  ╲                │
│     ╱     FAIR     ╲               │
│    ╰────────────────╯              │
│                                     │
│  ▲ +3 from last analysis           │
│  Last analyzed: 2 hours ago         │
│  [View Breakdown]    [View Evidence]│
└─────────────────────────────────────┘
```

### Evidence Chain Node
```
┌───────────────────────────────┐
│ [📄] CONTRACT                 │  For each stage
│  3 clauses | 2 mismatches 🔴 │  in the evidence chain
│                               │
│  ──────────────────▶          │  Arrow connects to next
└───────────────────────────────┘
```

### Power/Interest Matrix Cell
```
                 LOW INTEREST │ HIGH INTEREST
                 ─────────────┼──────────────
HIGH POWER       [Keep Satis] │ [Manage Close]
                              │
LOW POWER        [Monitor]    │ [Keep Informed]
```

### RACI Cell (matrix)
```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│              │   │ R            │   │ A ⚠          │
│    (empty)   │   │ Responsible  │   │ Accountable  │
│              │   │              │   │ + Warning    │
└──────────────┘   └──────────────┘   └──────────────┘
     No assign        Green fill          Blue fill + warning
```

### File Upload Zone
```
┌─────────────────────────────────────────────┐
│                                              │
│           ↑  Drag files here                │  Dashed border
│           ─  or click to browse             │  Center content
│                                              │
│  Supported: PDF, DOCX, XLSX, CSV, TXT       │
│  Max size: 50MB per file                    │
│                                              │
└─────────────────────────────────────────────┘
```
**States:**
- Default: Dashed border, neutral
- Hover: Solid border, blue tint
- Dragging over: Blue border + background tint
- Uploading: Progress bars visible

### Stakeholder Bubble (for matrix)
```
  ●  PM Johnson      Filled circle
                     Size = influence level
                     Color = department/role
                     On hover: tooltip with details
```

---

## 10. ICONS REFERENCE (Lucide React)

### Navigation Icons
| Icon | Name | Usage |
|------|------|-------|
| 🏠 | `Home` | Dashboard nav |
| 📁 | `FolderOpen` | Projects |
| 📄 | `FileText` | Documents |
| 📊 | `BarChart2` | Coherence |
| 🔗 | `Link2` | Evidence |
| 🔔 | `Bell` | Alerts |
| 👥 | `Users` | Stakeholders |
| ⊞ | `Grid3x3` | RACI Matrix |
| ⚙️ | `Settings` | Settings |

### Action Icons
| Icon | Name | Usage |
|------|------|-------|
| ➕ | `Plus` | Add/Create |
| ✏️ | `Pencil` | Edit |
| 🗑️ | `Trash2` | Delete |
| ⬇️ | `Download` | Export |
| ⬆️ | `Upload` | Import |
| 🔍 | `Search` | Search |
| 🔽 | `Filter` | Filter |
| ↕️ | `ArrowUpDown` | Sort |
| ⋯ | `MoreHorizontal` | More options |

### Status Icons
| Icon | Name | Usage |
|------|------|-------|
| ✓ | `CheckCircle` | Success |
| ⚠️ | `AlertTriangle` | Warning |
| ✗ | `XCircle` | Error |
| ℹ️ | `Info` | Information |
| ⟳ | `RefreshCw` | Refresh |
| ⏳ | `Clock` | Pending/Time |

### File Icons
| Icon | Name | Usage |
|------|------|-------|
| 📄 | `FileText` | Document |
| 📊 | `FileSpreadsheet` | Excel/CSV |
| 📋 | `FileCheck` | Verified document |
| 📁 | `FolderOpen` | Folder |

---

**Total Components to Create in Figma:** ~80+ component variants

**Figma Organization:**
- Use "Component" feature for reusable parts
- Use "Variant" feature for different states
- Use "Auto Layout" for responsive components
- Use "Style" feature for colors and typography
- Use "Frame" for page layouts

**Last Updated:** 2026-02-18
