# Documentation Structure - MUST FOLLOW

> **2026-09-26 control-plane override:** current execution state is canonical under `.c2pro/`; product lifecycle state is canonical in the product-control YAML/Markdown pair. `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` are read-only legacy/cold references. Any older instruction below that implies writing current task state to those legacy files is superseded by this rule.

## ⚠️ CRITICAL RULE - NO EXCEPTIONS ⚠️

**NEVER create additional task-specific documentation files.**

This is MANDATORY to:
- Avoid unnecessary work
- Keep context unified
- Maintain single source of truth
- Prevent documentation sprawl

---

## The Rule

**ALL task documentation MUST go in exactly TWO locations:**

1. **`backlogs/BCK_*.md`** - Task specifications, completion status, implementation details
2. **`blackboard/SESSION_*.md`** - Active session work, scratch notes, temporary analysis

**NEVER create files like:**
- ❌ `TASK-BCK-027_ORCHESTRATION_AUDIT_REPORT.md`
- ❌ `TASK-BCK-026_ALERT_UNIFICATION_PLAN.md`
- ❌ `FEATURE_XYZ_IMPLEMENTATION_GUIDE.md`
- ❌ Any other task-specific standalone files

---

## Correct Approach

### For Task Documentation
```
✅ Add to backlogs/BCK_BACKEND.md under the task section
✅ Include all findings, decisions, and implementation details inline
✅ Update completion checklists directly in the backlog
```

### For Session Work
```
✅ Use blackboard/SESSION_*.md for active work
✅ Consolidate findings back into backlogs/ when task completes
✅ Delete or archive session notes after consolidation
```

---

## Why This Matters

1. **Context Efficiency**: All task info in one place = faster lookups
2. **No Duplication**: Single source of truth for each task
3. **Less Noise**: Fewer files = clearer project structure
4. **Token Savings**: Claude doesn't need to read multiple files for one task
5. **Maintenance**: Updates happen in one place, not scattered across files

---

## Examples

### ❌ WRONG - Multiple Files
```
TASK-BCK-027/
├── ORCHESTRATION_AUDIT_REPORT.md (485 lines)
├── IMPLEMENTATION_PLAN.md (320 lines)
└── COMPLETION_SUMMARY.md (150 lines)

backlogs/BCK_BACKEND.md:
- Brief reference to external files
```

**Problem**: 955 lines scattered across 3 files + backlog. Context fragmented.

### ✅ CORRECT - Unified Documentation
```
backlogs/BCK_BACKEND.md:
#### TASK-BCK-027: Orchestration System Reconciliation

**Implementation Status**: ✅ Completed (Module Deleted)

**Audit Finding**:
- core/ai/orchestration/ had ZERO production usage
- analysis/adapters/graph/ is active N1-N17 pipeline
- No overlap - different purposes
- Decision: DELETE unused module instead of consolidating

**Files Deleted**:
- apps/api/src/core/ai/orchestration/ (4 files)
- apps/api/tests/unit/core/ai/orchestration/ (3 files)

**Verification**: 85/85 core AI tests passing

**Checklist**:
- [x] Audit completed
- [x] Module deleted
- [x] Tests passing
```

**Result**: All information in one place, ~150 lines total in backlog.

---

## Enforcement

This rule is enforced by:
1. ✅ Project rules in `.claude/rules/DOCUMENTATION_STRUCTURE.md`
2. ✅ Manual review before marking tasks complete
3. ✅ Claude session instructions (this file)

**Violation = Immediate correction required**

---

## Related Rules

- `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md` - legacy backlog/blackboard files are read-only; current control writes go through `.c2pro`
- This file - durable current execution evidence belongs in authorized work envelopes/PR evidence; legacy backlog/blackboard files are not write targets

---

*Last Updated*: 2026-04-06
*Severity*: **CRITICAL**
*Violation Impact*: Wasted effort, context fragmentation, maintenance burden
