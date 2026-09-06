# CRITICAL BACKLOG REQUIREMENT (SINGLE-WRITER CONTROL PLANE ALIGNED)

## ⚠️ MANDATORY WORKER RULE — READ-ONLY LEGACY FILES ⚠️

**This rule governs ALL implementation, QA, and review workers under the single-writer control plane.**

---

## The Rule

**Ordinary implementation and review workers MUST NOT mutate legacy control files:**
- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/*.md`
- `blackboard.json`

These files are **read-only cold references**. Workers must never update them directly.

Only the **Planner / Master Orchestrator** has write authority to mutate the canonical planning state and control files under `.c2pro/`.

---

## Worker Invariants & Workflow

### 1. Read-Only Legacy References
Do NOT require reading the full legacy backlogs by default. Normal worker bootstrap consumes only:
- Current `.c2pro/` control envelope required by routing
- Assigned `.c2pro/work/<work_id>.yaml`
- Role-specific instructions
- Directly relevant code/spec context

### 2. Discovered Work & Evidence (Structured RETURN)
If you complete a task or discover new work/risks:
- **Do NOT update legacy markdown/JSON backlogs.**
- **Do NOT commit result files to the repository.**
- **DO provide structured evidence in your PR-body / standard output.** You must use the fenced YAML block matching the `c2pro-implementation-result-v1` schema as the transport.

### 3. Completion is Non-Canonical
A task's completion is **NOT canonical** until it undergoes review, CI verification, is merged, and is reconciled on the master branch by the Master/Planner reconciler.

---

## Structured Worker Result (c2pro-implementation-result-v1)

When returning evidence, include a fenced YAML block in your PR/output matching this structure exactly:

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
  - summary of key findings
residual_risks:
  - any remaining minor risks
recommendation: approve
pr_url: null
```
```

---

## Enforcement

This single-writer contract is enforced by:
1. Automated validations in `core/supervisor.py` (which bypass legacy Markdown checks for new control tasks).
2. Project and role-level rules.
3. CI/CD validation gates that parse and validate the returned result blocks.
