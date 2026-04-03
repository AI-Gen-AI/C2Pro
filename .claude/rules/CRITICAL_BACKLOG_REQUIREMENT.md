# CRITICAL BACKLOG REQUIREMENT

## ⚠️ MANDATORY REQUIREMENT - READ FIRST ⚠️

**This is a MUST HAVE requirement that MUST be followed for ALL work on this project.**

---

## The Rule

**EVERY new task created or updated MUST be reflected in `C2PRO_MASTER_BACKLOG.md`**

This is NON-NEGOTIABLE. No exceptions.

---

## What This Means

### When Creating Implementation Plans

If you create ANY implementation plan document that breaks work into subtasks (like `LANGSMITH_INTEGRATION_PLAN.md`), you MUST:

1. ✅ Add EVERY subtask from the plan to `C2PRO_MASTER_BACKLOG.md`
2. ✅ Include the task ID, priority, dependency, description, and source reference
3. ✅ Update the Change Log with the date and summary of what was added
4. ✅ Verify ALL tasks are in the backlog before considering the work complete

### When Marking Tasks Complete

When you complete ANY task:

1. ✅ Update the task status in `C2PRO_MASTER_BACKLOG.md` from `[ ]` to `[x]`
2. ✅ Add verification details in the task description (what was implemented, test results, etc.)
3. ✅ Update the Change Log with the completion date and summary
4. ✅ Mark any dependent tasks that are now unblocked

### When Creating New Tasks During Implementation

If you discover new tasks while implementing:

1. ✅ Immediately add them to `C2PRO_MASTER_BACKLOG.md`
2. ✅ Assign appropriate priority (P0, P1, P2, P3)
3. ✅ Link to parent task if applicable
4. ✅ Update the Change Log

---

## Why This Matters

`C2PRO_MASTER_BACKLOG.md` is the **single source of truth** for all project work.

- Product managers use it to track progress
- Developers use it to know what to work on
- Stakeholders use it for status updates
- Auditors use it for traceability

If a task is not in the backlog, **it does not exist** from a project management perspective.

---

## Verification Checklist

Before marking ANY work as complete, verify:

- [ ] All new tasks from implementation plans are in `C2PRO_MASTER_BACKLOG.md`
- [ ] All completed tasks are marked `[x]` with verification details
- [ ] Change Log is updated with today's date
- [ ] No orphaned tasks exist in planning docs without backlog entries

---

## Example: Correct Process

### ❌ WRONG (Incomplete)

1. Create `LANGSMITH_INTEGRATION_PLAN.md` with 32 tasks
2. Add first 8 tasks to backlog
3. Stop and move on to other work

**Problem**: 24 tasks are missing from the backlog!

### ✅ CORRECT (Complete)

1. Create `LANGSMITH_INTEGRATION_PLAN.md` with 32 tasks
2. Add ALL 32 tasks to `C2PRO_MASTER_BACKLOG.md` (TASK-1119 through TASK-1150)
3. Update Change Log with summary
4. Verify every task from the plan has a backlog entry
5. Only then consider the planning work complete

---

## Related Files

- **Backlog**: `C:\Users\esus_\Documents\AI\ZTWQ\c2pro\C2PRO_MASTER_BACKLOG.md`
- **This Rule**: `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md`

---

## Enforcement

This requirement is enforced by:

1. Project rules in `.claude/rules/`
2. Agent instructions in `.claude/agents/`
3. Manual code review before merging
4. Automated checks in CI/CD (future)

---

**Remember**: If you create tasks, they MUST be in the backlog. No exceptions. Ever.

---

*Last Updated*: 2026-04-03
*Severity*: **CRITICAL**
*Violation Impact*: Work becomes invisible to project tracking, causing confusion and missed deliverables
