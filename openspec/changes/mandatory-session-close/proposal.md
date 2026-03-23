# Proposal: Mandatory Session Close Protocol

## Intent

Require every agent session to execute a deterministic close sequence before any final `done`, `listo`, or `completed` response is returned. This prevents memory loss, missing handoff notes, and silent task drift.

## Scope

### In Scope

- Define a mandatory session-close protocol for agent and orchestrator workflows.
- Specify the minimum close sequence artifacts and ordering.
- Define failure behavior when close steps cannot complete.

### Out of Scope

- Implementing tool-level enforcement in the CLI or runtime.
- Backfilling historical sessions that already ended without closure.

## Approach

Add a new OpenSpec change describing session lifecycle requirements. The protocol will make session closure a blocking condition for final completion responses and require a persisted summary, task status update, and explicit close acknowledgment.

## Affected Areas

| Area                                                                       | Impact | Description                                        |
| -------------------------------------------------------------------------- | ------ | -------------------------------------------------- |
| `openspec/changes/mandatory-session-close/proposal.md`                     | New    | Defines intent and policy boundaries               |
| `openspec/changes/mandatory-session-close/specs/session-lifecycle/spec.md` | New    | Specifies required session-close behavior          |
| Agent workflow/governance docs                                             | Future | Will need updates to align prompts and enforcement |

## Risks

| Risk                                | Likelihood | Mitigation                                             |
| ----------------------------------- | ---------- | ------------------------------------------------------ |
| Extra workflow overhead             | Med        | Keep close sequence short and standardized             |
| Agents skip protocol under pressure | Med        | Treat missing close sequence as an incomplete session  |
| Duplicate summaries across layers   | Low        | Define one canonical close sequence and artifact order |

## Rollback Plan

If the protocol proves too heavy, revert this change and replace it with a lighter advisory workflow while preserving the session-summary template for optional use.

## Dependencies

- Existing Engram session summary and session end capabilities.
- Orchestrator and agent instruction files that govern final responses.

## Success Criteria

- [ ] A spec defines when a session is considered closable.
- [ ] Final completion responses are prohibited before the close sequence runs.
- [ ] Failure behavior is defined for blocked or partial session-close attempts.
