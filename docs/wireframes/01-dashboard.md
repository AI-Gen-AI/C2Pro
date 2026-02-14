# Dashboard - Wireframe

**View:** Main Dashboard
**Route:** `/dashboard`
**Purpose:** Executive overview of all projects with key metrics and coherence scores

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ☰  C2PRO                                                    [User] [Settings]│
├─────────────────────────────────────────────────────────────────────────────┤
│  Dashboard   Projects   Documents   Alerts   Stakeholders   RACI            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Organization Name ──────────────────────────────────────────────────┐   │
│  │  Subscription: Professional  │  AI Budget: $45.20 / $50.00 (90%)    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Quick Stats ─────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │  │
│  │   │  Active   │  │ Documents │  │   Alerts  │  │   Users   │        │  │
│  │   │ Projects  │  │  Analyzed │  │   Open    │  │  Active   │        │  │
│  │   │           │  │           │  │           │  │           │        │  │
│  │   │    12     │  │    156    │  │    23     │  │     8     │        │  │
│  │   └───────────┘  └───────────┘  └───────────┘  └───────────┘        │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Recent Projects ─────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Project Name          Type      Status      Score   Updated          │  │
│  │  ──────────────────────────────────────────────────────────────────   │  │
│  │  Hospital Central      EPC       Active       [85]   2 hours ago      │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                │  │
│  │                                                                        │  │
│  │  Port Expansion        Maritime  Active       [67]   5 hours ago      │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                                   │  │
│  │                                                                        │  │
│  │  Industrial Plant      Chemical  Active       [92]   1 day ago        │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛         │  │
│  │                                                                        │  │
│  │  Office Complex        Building  Draft        [--]   3 days ago       │  │
│  │                                                                        │  │
│  │  Highway Extension     Civil     Completed    [88]   1 week ago       │  │
│  │  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                     │  │
│  │                                                                        │  │
│  │                          [View All Projects →]                         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Critical Alerts ──────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  🔴  Date mismatch: Contract end vs Schedule (Hospital Central)        │ │
│  │       Contract deadline: 2026-06-30 | Schedule end: 2026-07-15         │ │
│  │       [View Details →]                                                  │ │
│  │                                                                         │ │
│  │  🟡  Budget overrun risk: Material costs (Port Expansion)              │ │
│  │       Estimated: $2.3M | Budgeted: $2.0M (+15%)                        │ │
│  │       [View Details →]                                                  │ │
│  │                                                                         │ │
│  │  🔴  Missing stakeholder approval (Industrial Plant)                   │ │
│  │       Critical BOM items require HSE Officer approval                  │ │
│  │       [View Details →]                                                  │ │
│  │                                                                         │ │
│  │                              [View All Alerts →]                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─ Coherence Score Distribution ────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │   Score Range         Projects         %                              │  │
│  │   ─────────────────────────────────────────                           │  │
│  │   90-100 (Excellent)  ████░░░░░░░   3     25%                         │  │
│  │   80-89  (Good)       ███████░░░░   5     42%                         │  │
│  │   70-79  (Fair)       ██░░░░░░░░░   2     17%                         │  │
│  │   60-69  (Poor)       ██░░░░░░░░░   2     17%                         │  │
│  │   0-59   (Critical)   ░░░░░░░░░░░   0      0%                         │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ AI Usage This Month ─────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │   ┌─────────────────────────────────────────────────────────────┐    │  │
│  │   │ $50                                                           │    │  │
│  │   │      ╱─╲                                                      │    │  │
│  │   │     ╱   ╲                                                     │    │  │
│  │   │    ╱     ╲                           Budget Limit ─ ─ ─ ─ ─  │    │  │
│  │   │   ╱       ╲___                                               │    │  │
│  │   │  ╱            ───╲                                           │    │  │
│  │   │ ╱                 ─╲___                                      │    │  │
│  │   │╱                       ───╲                                  │    │  │
│  │ $0└─────────────────────────────────────────────────────────────┘    │  │
│  │    Jan 1      Jan 7      Jan 14     Jan 21     Jan 28                │  │
│  │                                                                        │  │
│  │   Current: $45.20 (90%) │ Remaining: $4.80 │ [View Details]          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Header Bar
- **Logo & Brand**: C2PRO branding
- **User Menu**: Avatar, name, settings dropdown
- **Global Actions**: Quick access to notifications, settings

### 2. Navigation Bar
- **Primary Navigation**: Dashboard, Projects, Documents, Alerts, Stakeholders, RACI
- **Active State**: Current view highlighted

### 3. Organization Info Bar
- **Organization Name**: Current tenant
- **Subscription Plan**: Plan type (Free, Professional, Enterprise)
- **AI Budget**: Visual indicator of monthly AI spending vs limit

### 4. Quick Stats Cards
Four metric cards showing:
- **Active Projects**: Count of projects in active status
- **Documents Analyzed**: Total documents processed
- **Alerts Open**: Number of unresolved alerts
- **Users Active**: Active users in the organization

### 5. Recent Projects Table
- **Project Name**: Clickable link to project detail
- **Type**: Project category (EPC, Civil, Building, etc.)
- **Status**: Draft, Active, Completed, Archived
- **Coherence Score**: 0-100 with visual gauge/bar
  - Red (0-60): Critical
  - Yellow (61-80): Fair/Good
  - Green (81-100): Excellent
- **Last Updated**: Relative time
- **Score Bar**: Visual horizontal bar showing score value
- **View All Link**: Navigate to full projects list

### 6. Critical Alerts Panel
- **Alert Cards**: Top 3-5 most critical alerts
  - **Severity Icon**: 🔴 Critical, 🟡 High, 🔵 Medium
  - **Alert Title**: Brief description
  - **Alert Details**: Key information (dates, amounts, etc.)
  - **Action Button**: View Details link
- **View All Link**: Navigate to alerts page

### 7. Coherence Score Distribution
- **Bar Chart**: Visual distribution of projects by score range
  - 90-100: Excellent
  - 80-89: Good
  - 70-79: Fair
  - 60-69: Poor
  - 0-59: Critical
- **Count & Percentage**: Shows number and percentage of projects in each range

### 8. AI Usage Chart
- **Line Chart**: Daily AI spending over the month
- **Budget Line**: Horizontal line showing monthly limit
- **Metrics**: Current spend, remaining budget, percentage used
- **View Details Link**: Navigate to detailed cost breakdown

---

## Interactions

### Primary Actions
1. **Click Project Name**: Navigate to project detail view
2. **Click Alert**: Navigate to alert detail with evidence viewer
3. **View All Projects**: Navigate to projects list page
4. **View All Alerts**: Navigate to alerts page
5. **View AI Details**: Navigate to observability dashboard

### Secondary Actions
1. **Filter/Sort Projects**: In-table filtering (future enhancement)
2. **Resolve Alert**: Quick resolve from dashboard (future enhancement)
3. **Export Dashboard**: PDF/CSV export (future enhancement)

### Real-time Updates
- **Auto-refresh**: Dashboard data updates every 30 seconds
- **Live Notifications**: New alerts appear with toast notification
- **Score Changes**: Visual animation when scores update

---

## Responsive Behavior

### Desktop (>1200px)
- Full layout as shown
- Side-by-side cards and charts

### Tablet (768px - 1200px)
- Stats cards: 2x2 grid
- Projects table: Horizontal scroll
- Charts: Full width, stacked

### Mobile (<768px)
- Stats cards: Vertical stack
- Projects: Card view (not table)
- Charts: Simplified, touch-optimized
- Sidebar navigation: Hamburger menu

---

## Design Notes

### Color Scheme
- **Primary**: Blue (#0066CC) - Actions, links
- **Success**: Green (#00AA00) - Good scores (81-100)
- **Warning**: Yellow (#FFAA00) - Fair scores (61-80)
- **Error**: Red (#CC0000) - Poor/Critical scores (0-60)
- **Neutral**: Gray (#666666) - Text, borders

### Typography
- **Headings**: Bold, 18-24px
- **Body**: Regular, 14-16px
- **Small**: 12px for metadata

### Spacing
- **Card Padding**: 24px
- **Card Gap**: 16px
- **Section Gap**: 32px

---

## Accessibility

- **ARIA Labels**: All interactive elements
- **Keyboard Navigation**: Full keyboard support
- **Screen Reader**: Proper heading hierarchy
- **Color Contrast**: WCAG AA compliant
- **Focus Indicators**: Clear focus states

---

## Future Enhancements
- [ ] Custom dashboard layouts
- [ ] Widget configuration
- [ ] Export to PDF/Excel
- [ ] Dashboard templates
- [ ] Real-time collaboration indicators

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
