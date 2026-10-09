# C2PRO-DEV-03 — R0–R2 current readiness reconciliation (read-only)

**Date:** 2026-10-09
**Canonical task / tracking:** C2PRO-DEV-03 / #674
**Related downstream task:** C2PRO-DEV-14 / #991
**State:** OBSERVED_PARTIAL / EXECUTION_NOT_AUTHORIZED
**Authority effect:** NONE. This document does not promote DEV-03, start DEV-14, assign a worker, amend routes, grant provider authority or claim qualification.

## Evidence boundaries

This is a current, bounded R0–R2 inventory derived from canonical repository source at the exact pins below and non-secret VPS metadata obtained from a read-only operator session. It does **not** represent a job-bound worker invocation, independent principal review, execution-binding receipt, or a negative-boundary test. Route status, model qualification and user CLI login are intentionally kept separate.

| Source | Immutable pin / interpretation |
| --- | --- |
| C2Pro GitHub main | `0de6b6ff2b38e6b3ad9b8c63a9e58e1b2c140fce`, after #992 and #993 |
| AI-Gen 2SB GitHub main | `9467a1a42fdc04147f4783f9fdadcbd1132731d1` |
| C2Pro control | `.c2pro/control/current.yaml`: `reconciled_idle`, `active_work: []`, `next_eligible_work: C2PRO-DEV-03` |
| DEV-14 effective envelope | `.c2pro/work/C2PRO-DEV-14.yaml`: registered `ready`, `worker_selection.selected: null` |
| C2Pro DEV-03 contract | `docs/architecture/development/c2pro-dev-03-principal-worker-readiness-v2.md`, §§4A–8 |
| AI-Gen authoritative routing | `ai-gen-agent-os/control-plane/agent_factory/policies/academy-role-routing-v1.yaml` at 2SB pin above |
| AI-Gen development MASTER | `ai-gen-agent-os/validation/master-development-task-control-v1.yaml`: global `execution_authorized: false`, bounded Academy model, no standing provider authority |

**Baseline warning:** `current.yaml` records a historical `baseline.main_sha` distinct from the new `main` tip. This is not a valid reason to mutate hot control silently. An independently reconciled exact-SHA active WORK change is necessary before implementation.

## DEV-03R1 — read-only VPS CLI/host observations

Observed host session: Linux `6.8.0-137-generic x86_64`; inspection user `aigenadmin` (NOT a verified `aigen-codex` or `aigen-claude` worker job identity). `bwrap`, `unshare`, `timeout`, `git`, `python3` executables present. Presence alone does not prove namespace isolation, negative boundary tests, timeout enforcement, or provider routing.

| CLI | Active command | Resolved executable | Version | Active target SHA-256 | Typed auth under inspection user |
| --- | --- | --- | --- | --- | --- |
| Codex | `/srv/c2pro/toolchain/bin/codex` | `/srv/c2pro/toolchain/npm/lib/node_modules/@openai/codex/bin/codex.js` | `0.157.0` | `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70` | UNKNOWN |
| Claude Code | `/srv/c2pro/toolchain/node/v22.23.2/bin/claude` | `/srv/c2pro/toolchain/node/v22.23.2/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe` | `2.1.295` | `4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358` | AUTHENTICATED (inspection-user session only) |

Codex binary target owner/group: `aigenadmin:aigenadmin`, file mode `775`. Claude target owner/group: `aigenadmin:aigenadmin`, mode `755`. No token, session content, credential ID, environment data or CLI login output is copied here. `UNKNOWN` is not a claim of broken authentication; neither reported state proves a provider call or governed worker identity.

## DEV-03R2 — canonical role / route mapping

| Academy role or purpose | Observed route / canonical state | Decision for C2Pro |
| --- | --- | --- |
| `ENGINEERING_ORCHESTRATOR` | `UNQUALIFIED_FAIL_CLOSED` | Cannot select a provider/model as C2Pro DEV-14 orchestrator on this evidence |
| `IMPLEMENTATION_LEAD` | `UNQUALIFIED_FAIL_CLOSED` | Cannot silently map C2Pro implementation-lead role to another Academy role |
| `BACKEND_ENGINEER` | `CODEX_OPENAI_DEFAULT`, `QUALIFIED_LIVE`, route health `AVAILABLE` | Capability exists, but it is role-specific; provider invocation, workspace/job and fresh authority still unproven |
| `SOFTWARE_ARCHITECT` | Claude `QUALIFIED_BOUNDED`, read-only ceiling | Can be a separately bounded review/design candidate only after fresh job authorization; no code writes |
| `SYSTEM_COHERENCE_REVIEWER` | Claude `QUALIFIED_BOUNDED`, read-only ceiling | Potential distinct assurance stage; NOT inherited qualification for `INDEPENDENT_REVIEW_LEAD` |
| `INDEPENDENT_REVIEW_LEAD` | AI-Gen `NVIDIA_NEMOTRON3_SUPER` qualified, but C2Pro classifies OpenCode/Nemotron as subordinate | Cannot satisfy C2Pro independent **principal** gate by relabeling |
| `ADVERSARIAL_CHALLENGER` | `UNQUALIFIED_FAIL_CLOSED` | Required architecture challenger route needs distinct valid control evidence |

The route file marks Claude health `AVAILABLE` only for **decision-only** bounded selection. Its catalog separately sets `live_invocation_authorized: false`, so do not equate the health value with permission to invoke. Current AgentOS MASTER also prohibits inferred global execution authority.

## Gating assessment

- **R0:** baselines and file references bound above — OBSERVED.
- **R1:** host/binary inventory and typed inspection-user auth — PARTIAL. Actual principal OS identity, executable context under the worker account, live endpoint smoke and resource/isolation receipts are NOT TESTED.
- **R2:** per-role route registry and separation of concerns reconciled — OBSERVED; compatible C2Pro orchestration + independent principal review qualification NOT ESTABLISHED.
- **R3–R8:** NOT EXECUTED. No live Codex/Claude provider attempt, no fresh one-job authority consumed, no test implementation, no negative-boundary proof, no handoff, no immutable `SessionExecutionBindingV1` or `ExecutionLifecycleReceiptV1`, and no approved review-to-merge gate.

**Outcome:** `DEV03_R0_R2=PARTIAL_RECONCILED`; `DEV03_PROVIDER_INVOCATIONS=0`; `DEV14_IMPLEMENTATION=BLOCKED_ROUTE_AND_WORK_AUTHORITY`; `DEV14_ACCEPTED=FALSE`; `PROD_VALIDATED=NOT_CLAIMED`.

## Minimum forward contract (no waiver)

1. Under #674, resolve principal routing via a **separately reviewed and explicitly bounded role qualification**. If splitting DEV-14 into an orchestrator-controlled campaign plus role-specific Codex coding and Claude coherence-review stages, register that mapping independently; don't rename an unqualified role to get a green result. C2Pro independent principal review must remain satisfied, or promotion stays blocked.
2. In the governed Agent Factory process, perform an endpoint preflight **only after authorization** and issue a fresh single-job, consumed provider/workspace authority to the *selected* compatible worker and requested role. Verify executor OS identity, actual executable target, bound workspace, exact route/model and no standing authority.
3. Produce the R3–R8 durable binding/receipt chain, deny cases (main, Runtime, secrets, cross-workspace, stale SHA), timeout results, independent principal review and typed terminal state. Escalate incompatible routes without role laundering.
4. Independently approve an effective C2Pro `current.yaml` transition referencing a valid DEV-14 envelope refreshed to its exact authorized base SHA, with a registered worktree matching the active branch. `active_work` must not be filled by this report.
5. Only then execute DEV-14.2 RED→GREEN, DEV-14.3 and DEV-14.4 audit-before-enforce. Preserve independent Product MASTER acceptance and human merge.

**No-go:** direct-main edits, credential reads/exports, ad-hoc CLI provider invocations, bypass of `.c2pro` or Agent Academy, retroactive evidence, Product ACCEPTED/PROD_VALIDATED promotion.
