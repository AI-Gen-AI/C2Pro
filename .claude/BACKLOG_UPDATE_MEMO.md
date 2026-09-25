# BACKLOG UPDATE MEMO (SINGLE-WRITER CONTROL PLANE ALIGNED)

**To**: All AI Agents working on C2Pro (Workers)
**From**: Project Guidelines
**Date**: 2026-09-06
**Subject**: MANDATORY Single-Writer Control Plane Invariant

---

## Critical Requirement

**Workers MUST NOT mutate legacy backlogs or control files.**
- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/*.md`
- `blackboard.json`

These files are **read-only cold references** for implementation, QA, and review workers.

Only the **Planner / Master Orchestrator** is permitted to write to the canonical `.c2pro` state and planning control files.

---

## Worker Guidelines

### 1. Minimal Bootstrap
Do NOT read or parse full legacy backlogs by default. Normal worker bootstrap consumes:
- Assigned `.c2pro/work/<work_id>.yaml`
- Role-specific instructions
- Relevant code/spec context

### 2. Structured RETURN
Upon task completion or discovering new tasks/risks:
- **Do NOT update legacy markdown/JSON backlogs.**
- **DO provide structured evidence (YAML result block)** matching the `c2pro-implementation-result-v1` schema in your PR-body or standard output.

---

## Structured Result Format (c2pro-implementation-result-v1)

Include this fenced YAML block in your output upon completion:

```yaml
```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-XX
base_sha: <40-hex-characters-base-sha>
head_sha: <40-hex-characters-head-sha>
branch: <your-branch-name>
files_changed:
  - path/to/changed_file.py
tests:
  - name: test_name
    status: PASS
ci_status: success
findings:
  - summary of findings
residual_risks:
  - any minor risks
recommendation: approve
pr_url: null
```
```

---

## Enforcement

Automated validations in `core/supervisor.py` enforce these invariants at runtime, bypassing legacy checks for new control tasks.
