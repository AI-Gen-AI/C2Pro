# Proposal: OpenSpec Bootstrap v2

## Intent

Stabilize OpenSpec bootstrap verification so process-only changes can be validated without relying on unrelated full app test suites that are currently flaky or environment-dependent.

## Scope

### In Scope

- Add a lightweight OpenSpec compliance verification path for change artifacts.
- Define explicit mapping from bootstrap scenarios to executable checks.
- Add a docs-first verify command and reporting format for process changes.

### Out of Scope

- Fixing unrelated frontend/backend product test failures.
- Replacing existing full-suite CI gates for runtime code changes.

## Approach

Create a v2 bootstrap change with focused verification assets: a small compliance script/checklist runner, scenario-to-check traceability, and a dedicated verify workflow for `openspec/changes/*` documentation changes. Keep existing OpenSpec structure and `config.yaml` rules as the source of truth.

## Affected Areas

| Area                                                            | Impact   | Description                                              |
| --------------------------------------------------------------- | -------- | -------------------------------------------------------- |
| `openspec/changes/openspec-bootstrap-v2/proposal.md`            | New      | Defines intent, scope, and rollout for v2 bootstrap      |
| `openspec/changes/openspec-bootstrap-v2/specs/openspec/spec.md` | New      | Specifies compliance automation and docs-verify behavior |
| `openspec/changes/openspec-bootstrap-v2/tasks.md`               | New      | Tracks phased implementation and verification            |
| `openspec/config.yaml`                                          | Modified | Adds/clarifies verify rules for process-only changes     |
| `apps/web/package.json` (or workspace scripts)                  | Modified | Adds a lightweight OpenSpec verify command               |

## Risks

| Risk                                                   | Likelihood | Mitigation                                                           |
| ------------------------------------------------------ | ---------- | -------------------------------------------------------------------- |
| New verify flow drifts from policy rules               | Med        | Read rules directly from `openspec/config.yaml` and fail on mismatch |
| Team confusion between full and docs-only verification | Med        | Document clear trigger conditions and required command in tasks/spec |
| False confidence from shallow checks                   | Low        | Keep traceability matrix from each scenario to a concrete check      |

## Rollback Plan

If v2 verification causes confusion or misses defects, revert v2 workflow files and script changes, then return to manual checklist validation used in `openspec-bootstrap` while redesigning the verify strategy.

## Dependencies

- Existing `openspec-bootstrap` artifacts and verification report findings.
- `openspec/config.yaml` governance rules.

## Success Criteria

- [ ] Every v2 bootstrap spec scenario maps to an executable check or deterministic validation step.
- [ ] Process-only OpenSpec changes can be verified with a dedicated command that does not require full product suites.
- [ ] Reviewers can produce a pass/fail report with traceable evidence for artifact presence and rule compliance.
