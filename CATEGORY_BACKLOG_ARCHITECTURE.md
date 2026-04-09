# Category-Specific Backlog Architecture

**Status**: ✅ IMPLEMENTED - COMPLETE
**Version**: 2.0 (Final)
**Date**: 2026-04-04 (Implemented)
**Author**: Agent Orchestration Team

---

## ✅ Implementation Summary

**Implementation Date**: 2026-04-04
**Task ID**: TASK-INF-001

**What Was Implemented**:
1. ✅ Created `backlogs/` directory structure
2. ✅ Migrated 444 tasks from monolithic backlog to 6 category-specific files
3. ✅ Auto-categorized tasks using section-based + content-based rules
4. ✅ Renumbered tasks sequentially within categories (TASK-BCK-001, TASK-FRT-001, etc.)
5. ✅ Identified 29 cross-category tasks (UNIFY-xxx, TASK-DDD-xxx) kept in master
6. ✅ Updated all 9 role profiles to reference category-specific backlogs
7. ✅ Simplified master backlog to index + cross-category tasks + pending overview
8. ✅ Created backup: `backups/C2PRO_MASTER_BACKLOG_20260404_112755.md.bak`

**Migration Results**:
- **AI/ML Intelligence**: 78 tasks → `backlogs/AI_AI_ML_INTELLIGENCE.md`
- **Frontend**: 162 tasks → `backlogs/FRT_FRONTEND.md`
- **QA**: 96 tasks → `backlogs/QA_QUALITY_ASSURANCE.md`
- **Infrastructure**: 56 tasks → `backlogs/INF_INFRASTRUCTURE.md`
- **Backend**: 21 tasks → `backlogs/BCK_BACKEND.md`
- **DevOps**: 2 tasks → `backlogs/DEV_DEVOPS.md`
- **Cross-Category**: 29 tasks remain in master with 🔗 symbol

**Migration Script**: `scripts/migrate_to_category_backlogs.py`

**User Decisions Applied**:
- ✅ Execute migration immediately (Option A)
- ✅ Keep cross-category tasks in master (Option A)
- ✅ 2+ categories affected = cross-category (Option A)
- ✅ Simplified change log in master (major milestones only)
- ✅ Auto-categorize everything (fast, review errors later)

**Additional Enhancement**:
- ✅ Added "Pending Tasks by Category" section to master backlog (user request)
- ✅ Provides complete overview of 131 pending tasks across all categories

---

## Executive Summary (Original Architecture Proposal)

This document proposes migrating C2PRO's monolithic `C2PRO_MASTER_BACKLOG.md` (currently 730+ lines) to a **distributed category-specific backlog architecture** that improves scalability, reduces agent context overhead, and enables parallel work across domain boundaries.

**Key Benefits**:
- 📉 **Reduced Context Size**: Agents read only their category (~50-100 tasks vs 200+ tasks)
- 🚀 **Parallel Development**: No file conflicts when multiple agents work simultaneously
- 📚 **Domain Knowledge**: Category backlogs include specs, lessons learned, ADRs
- 🎯 **Focused Work**: Backend agent doesn't need to load frontend/security tasks
- 📈 **Scalability**: Linear growth per category instead of monolithic growth

---

## 1. Current State Analysis

### 1.1 Existing Structure

`C2PRO_MASTER_BACKLOG.md` already has logical categorization:

| Section | Current Name | Task Count (Est) | Maps To Role |
|---------|--------------|------------------|--------------|
| 2.1 | Backend | ~30 | backend |
| 2.2 | Frontend | ~40 | frontend |
| 2.3 | AI & Intelligence | ~80 | ai |
| 2.4 | DevOps & Infrastructure | ~30 | infra, devops |
| 2.5 | Security | ~20 | security |
| 2.6 | Testing & Quality | ~50 | qa |
| 2.7 | Architectural Refactoring | ~15 | backend, architect |
| 2.8 | Execution Phase | ~10 | qa |
| 2.9 | Agent Orchestration | ~16 | All roles (cross-category) |

**Total**: ~290 tasks across all categories

### 1.2 Problems with Monolithic Backlog

1. **Context Bloat**: Backend agent must load 290 tasks to find their 30 tasks
2. **Merge Conflicts**: Multiple agents updating same file simultaneously
3. **Poor Signal/Noise**: Relevant context buried in unrelated tasks
4. **Scalability Limits**: File will continue growing linearly with project size
5. **Slow Search**: Finding tasks requires scanning entire file

---

## 2. Proposed Architecture

### 2.1 Directory Structure

```
c2pro/
├── C2PRO_MASTER_BACKLOG.md          # Lightweight index + cross-category tasks
├── backlogs/
│   ├── BCK_BACKEND.md                # Backend tasks, specs, lessons
│   ├── FRT_FRONTEND.md               # Frontend tasks, specs, lessons
│   ├── AI_INTELLIGENCE.md            # AI/ML tasks, specs, lessons
│   ├── INF_INFRASTRUCTURE.md         # Infrastructure tasks, specs, lessons
│   ├── QA_QUALITY.md                 # QA tasks, specs, lessons
│   ├── REV_REVIEW.md                 # Code review tasks, specs, lessons
│   ├── SEC_SECURITY.md               # Security tasks, specs, lessons
│   ├── DEV_DEVOPS.md                 # DevOps tasks, specs, lessons
│   ├── PLN_PLANNING.md               # Planning tasks, specs, lessons
│   └── DOC_DOCUMENTATION.md          # Documentation tasks, specs, lessons
├── schemas/
│   └── category_backlog_schema.json  # Validation schema for category backlogs
└── roles/
    └── role_backend.md                # References backlogs/BCK_BACKEND.md
```

### 2.2 Category Prefix Mapping

| Prefix | Category | Owner Role | Description |
|--------|----------|------------|-------------|
| `BCK` | Backend | backend | API, services, repositories, domain logic |
| `FRT` | Frontend | frontend | React, Next.js, UI components, state management |
| `AI` | AI/ML | ai | LangGraph, coherence engine, embeddings, prompts |
| `INF` | Infrastructure | infra | Database, migrations, Supabase, RLS, indexes |
| `QA` | Quality Assurance | qa | Tests, coverage, CI/CD, quality gates |
| `REV` | Code Review | reviewer | Architecture audits, code quality, refactoring |
| `SEC` | Security | security | Vulnerabilities, auth, tenant isolation, CSP |
| `DEV` | DevOps | devops | Deployment, monitoring, observability, Docker |
| `PLN` | Planning | planner | Requirements, design, task breakdown |
| `DOC` | Documentation | (shared) | READMEs, specs, guides, runbooks |

### 2.3 Task ID Format

**Sequential numbering within each category**:

```
TASK-BCK-001   # First backend task
TASK-BCK-002   # Second backend task
...
TASK-FRT-001   # First frontend task
TASK-FRT-002   # Second frontend task
...
TASK-AI-001    # First AI task
```

**Rationale**:
- ✅ Easy to filter: `grep "TASK-BCK-" backlogs/BCK_BACKEND.md`
- ✅ Clear ownership at a glance
- ✅ Simple sequential numbering (no gaps, no global counter)
- ✅ Category reorganization doesn't affect other categories

---

## 3. Cross-Category Tasks

### 3.1 Special Symbol Notation

Tasks that affect multiple categories stay in `C2PRO_MASTER_BACKLOG.md` with a special symbol indicating scope:

```markdown
| Status | Priority | Task ID | Affects | Description | Source |
|--------|----------|---------|---------|-------------|--------|
| [ ]    | P0       | `UNIFY-007` | 🔗 ALL | Create automated sync script | AGENT_STRUCTURE... |
| [ ]    | P0       | `REL-RC1-01` | 🔗 QA+SEC+DEV | Execute UAT checklist | UAT_CHECKLIST.md |
| [x]    | P0       | `ARCH-001` | 🔗 BCK+FRT | Migrate to modular monolith | ARCHITECTURE_INDEX.md |
```

**Symbol Legend**:
- 🔗 `ALL` - Affects all categories
- 🔗 `BCK+FRT` - Affects backend + frontend
- 🔗 `QA+SEC+DEV` - Affects specific categories

**Naming Patterns for Cross-Category Tasks**:
- `UNIFY-xxx` - Agent orchestration / unification tasks
- `REL-xxx` - Release management tasks
- `ARCH-xxx` - Architecture-wide refactoring
- `GATE-xxx` - Quality gate / governance tasks

---

## 4. Category Backlog Template

Each `backlogs/XXX_CATEGORY.md` follows this structure:

```markdown
# [Category Name] Tasks & Knowledge Base

**Category**: [Category] ([PREFIX])
**Owner Role**: [role]
**Last Updated**: YYYY-MM-DD

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_[role].md)
- 📚 [Category Docs](../docs/[category]/)

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [ ]    | P0       | TASK-XXX-001 | None | ... | ... |
| [x]    | P0       | TASK-XXX-002 | TASK-XXX-001 | ... | ... |

**Statistics**:
- Total: X tasks
- Active: X (XX%)
- Completed: X (XX%)
- Blocked: X (XX%)

---

## 2. Specifications

### [Key Spec Area 1]
Description, conventions, standards...

### [Key Spec Area 2]
Description, conventions, standards...

---

## 3. Lessons Learned

### YYYY-MM-DD: [Lesson Title]
**Problem**: ...
**Solution**: ...
**Impact**: ...
**References**: TASK-XXX-YYY

---

## 4. Architectural Decisions

### ADR-XXX-001: [Decision Title]
**Date**: YYYY-MM-DD
**Status**: [Proposed | Accepted | Deprecated]
**Context**: ...
**Decision**: ...
**Consequences**: ...

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
|---------|-------------|--------|--------|---------|
| DEBT-XXX-001 | ... | Medium | 3 days | YYYY-MM-DD |

---

## 6. Metrics

- **Total Tasks**: X
- **Completed**: X (XX%)
- **Average Completion Time**: X days
- **Test Coverage**: XX%
- **Open Blockers**: X

---

## Change Log

| Date | Change |
|------|--------|
| YYYY-MM-DD | Initial category backlog creation |
```

---

## 5. Master Backlog Structure

`C2PRO_MASTER_BACKLOG.md` becomes a **lightweight index**:

```markdown
# C2PRO Master Backlog - Index

**Purpose**: High-level project overview and cross-category coordination
**Last Updated**: YYYY-MM-DD

---

## Quick Navigation

| Category | File | Owner | Active/Total | P0 Tasks |
|----------|------|-------|--------------|----------|
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 25/150 | 5 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 15/80 | 3 |
| AI/ML | [backlogs/AI_INTELLIGENCE.md](backlogs/AI_INTELLIGENCE.md) | ai | 10/60 | 2 |
| ... | ... | ... | ... | ... |

---

## Cross-Category Initiatives

| Status | Priority | Task ID | Affects | Description |
|--------|----------|---------|---------|-------------|
| [ ]    | P0       | UNIFY-007 | 🔗 ALL | Automated sync script |
| [ ]    | P0       | REL-RC1-01 | 🔗 QA+SEC+DEV | UAT checklist |

---

## Project Health Metrics

- **Total Tasks**: 290
- **Completed**: 200 (69%)
- **Active P0**: 15
- **Blocked**: 5
- **Average Cycle Time**: 2.5 days

---

## Release Status

### RC1 (Target: TBD)
- [ ] P0 Blockers: 3 remaining
- [ ] Gate 7 Signoff: Pending
- [ ] UAT: In Progress

---

## Change Log

[Consolidated change log from all categories]
```

---

## 6. Auto-Categorization Rules

### 6.1 Content-Based Categorization

| Pattern | Category | Example |
|---------|----------|---------|
| Source contains `apps/api/`, `repository`, `service`, `domain` | BCK | Backend code |
| Source contains `apps/web/`, `components/`, `hooks/`, `UI` | FRT | Frontend code |
| Source contains `coherence`, `embedding`, `prompt`, `LangGraph` | AI | AI/ML features |
| Source contains `alembic`, `migration`, `RLS`, `database`, `Supabase` | INF | Infrastructure |
| Source contains `test`, `coverage`, `pytest`, `playwright`, `QA` | QA | Testing |
| Source contains `security`, `auth`, `vulnerability`, `CSP` | SEC | Security |
| Source contains `docker`, `deployment`, `CI/CD`, `monitoring` | DEV | DevOps |
| Source contains `planning`, `PRD`, `design`, `architecture` (high-level) | PLN | Planning |
| Source contains `documentation`, `README`, `guide` | DOC | Documentation |

### 6.2 Source-Based Categorization

Current sections in `C2PRO_MASTER_BACKLOG.md`:

| Current Section | New Category |
|-----------------|--------------|
| 2.1 Backend | BCK |
| 2.2 Frontend | FRT |
| 2.3 AI & Intelligence | AI |
| 2.4 DevOps & Infrastructure | Split: INF (database) + DEV (deployment) |
| 2.5 Security | SEC |
| 2.6 Testing & Quality | QA |
| 2.7 Architectural Refactoring | BCK (or ARCH cross-category) |
| 2.8 Execution Phase | QA |
| 2.9 Agent Orchestration | Cross-category (keep in master) |

### 6.3 Ambiguous Cases

**Rule**: When a task clearly spans 2+ categories:
- Keep in `C2PRO_MASTER_BACKLOG.md` as cross-category
- Use 🔗 symbol with affected categories
- Use appropriate prefix (ARCH, GATE, UNIFY, REL)

**Examples**:
- RLS migration (affects BCK + INF) → `ARCH-001` in master
- E2E test suite (affects FRT + BCK + QA) → `QA-E2E-001` in QA backlog (tests are owned by QA)
- Release checklist (affects ALL) → `REL-RC1-01` in master

---

## 7. Migration Strategy

### 7.1 Phase 1: Setup (1 day)

1. Create `backlogs/` directory
2. Create category backlog templates
3. Create `schemas/category_backlog_schema.json`
4. Update `blackboard.json` schema to support category backlogs

### 7.2 Phase 2: Migration Script (2 days)

Create `scripts/migrate_to_category_backlogs.py`:

```python
# Pseudo-code
def migrate():
    master = read_master_backlog()
    categories = {
        "BCK": [], "FRT": [], "AI": [], "INF": [],
        "QA": [], "SEC": [], "DEV": [], "PLN": [], "DOC": []
    }
    cross_category = []

    for section in master.sections:
        for task in section.tasks:
            category = auto_categorize(task)
            if category == "CROSS":
                cross_category.append(task)
            else:
                # Renumber to sequential within category
                new_id = f"TASK-{category}-{next_seq_num(category)}"
                task.id = new_id
                categories[category].append(task)

    # Write category backlogs
    for cat, tasks in categories.items():
        write_category_backlog(cat, tasks)

    # Write new master with cross-category tasks only
    write_master_index(cross_category, categories)
```

### 7.3 Phase 3: Update Role Profiles (1 day)

Update each `roles/role_*.md` to reference their category backlog:

```markdown
## Referencias

- **Backlog permanente**: `backlogs/BCK_BACKEND.md` ← Category-specific backlog
- **Backlog maestro**: `C2PRO_MASTER_BACKLOG.md` ← Cross-category tasks
- **Estado de sesion**: `blackboard.json`
- **Asignacion de modelos**: `core/models.yaml`
```

### 7.4 Phase 4: Update Supervisor (1 day)

Update `core/supervisor.py` to support category backlogs:

```python
def obtener_backlog_para_rol(rol: str) -> Path:
    """Returns the backlog file path for a role."""
    category_map = {
        "backend": "backlogs/BCK_BACKEND.md",
        "frontend": "backlogs/FRT_FRONTEND.md",
        "ai": "backlogs/AI_INTELLIGENCE.md",
        # ...
    }
    return BASE_DIR / category_map.get(rol, "C2PRO_MASTER_BACKLOG.md")
```

### 7.5 Phase 5: Validation (1 day)

- Run automated tests on category backlogs
- Verify no tasks were lost in migration
- Verify task ID uniqueness across all backlogs
- Test agent workflows with new structure

**Total Migration Time**: ~5-6 days

---

## 8. Benefits Summary

| Benefit | Before | After | Impact |
|---------|--------|-------|--------|
| Context Size | 730 lines, 290 tasks | ~50-100 tasks per category | **85% reduction** |
| Agent Load Time | Load all 290 tasks | Load only relevant category | **Faster startup** |
| Merge Conflicts | Frequent (all agents → 1 file) | Rare (agents → separate files) | **Parallel work** |
| Domain Knowledge | Scattered in various docs | Consolidated in category backlog | **Better context** |
| Searchability | Scan 730 lines | Scan 50-100 lines | **5-10x faster** |
| Scalability | Linear growth (1 file) | Distributed growth (10 files) | **Sustainable** |

---

## 9. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Task gets lost in migration | Medium | High | Automated validation script + manual review |
| Agents confused by new structure | Low | Medium | Update role profiles with clear instructions |
| Cross-category task ambiguity | Medium | Low | Clear rules + manual review for edge cases |
| Backlog sync complexity | Low | Medium | Keep master as source of truth for cross-category |
| Migration script bugs | Medium | High | Extensive testing + dry-run mode + backup |

---

## 10. Open Questions for User

### Q1: Migration Timing
When should we execute the migration?
- **Option A**: Immediately (5-6 days effort)
- **Option B**: After completing UNIFY-xxx tasks (2 weeks)
- **Option C**: After RC1 release (1 month+)

### Q2: Architectural Refactoring Section
Section 2.7 (Architectural Refactoring) affects BCK+FRT. Should we:
- **Option A**: Keep as cross-category in master (`ARCH-xxx` prefix)
- **Option B**: Split tasks between BCK and FRT backlogs
- **Option C**: Create separate `backlogs/ARCH_REFACTORING.md`

### Q3: Cross-Category Task Threshold
When is a task "cross-category"?
- **Option A**: Affects 2+ categories
- **Option B**: Affects 3+ categories
- **Option C**: Affects ALL categories only

### Q4: Change Log Consolidation
Should category backlogs have:
- **Option A**: Individual change logs per category
- **Option B**: Consolidated change log in master only
- **Option C**: Both (redundant but comprehensive)

### Q5: Validation Strictness
Should migration script:
- **Option A**: Auto-categorize everything (fast, some errors)
- **Option B**: Flag ambiguous tasks for manual review (slower, accurate)
- **Option C**: Hybrid (auto-categorize 90%, manual review 10%)

---

## 11. Recommendations

Based on C2PRO's existing structure and growth trajectory, we recommend:

1. ✅ **Proceed with category-specific backlogs** - Clear benefits outweigh migration cost
2. ✅ **Sequential numbering within categories** - Simpler, cleaner than global counter
3. ✅ **Option B for Q2** - Keep cross-category in master (ARCH-xxx prefix)
4. ✅ **Option A for Q3** - 2+ categories = cross-category (more conservative)
5. ✅ **Option C for Q4** - Both change logs (redundancy aids traceability)
6. ✅ **Option B for Q5** - Manual review for ambiguous tasks (quality over speed)

---

## Next Steps

**Pending User Approval**:

1. Review this architecture document
2. Answer open questions (Q1-Q5)
3. Approve/modify category prefix mapping
4. Approve/modify cross-category notation

**After Approval**:

1. Create implementation task: `TASK-INF-001` - Implement Category Backlogs
2. Create migration script with dry-run mode
3. Execute migration with validation
4. Update all role profiles and documentation
5. Mark UNIFY-017 as "Migrate to category-specific backlogs" in UNIFY roadmap

---

**Document Status**: Ready for Review
**Reviewers**: User
**Approval Required Before**: Implementation
