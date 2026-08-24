# C2Pro VPS Development Control Plan v1

**Status:** OWNER APPROVED / IMPLEMENTATION PLAN
**Date:** 2026-08-24
**Repository:** `AI-Gen-AI/C2Pro`
**Approved baseline:** `main@be9603be6b40da135123aee6e1489365378e163e`
**Purpose:** migrate C2Pro development execution from the local PC to the VPS and activate a governed multi-agent coding system based on the AI-Gen AF-DEV/MR-DEV execution plane.

---

## 1. Owner decision

The target is not to copy the current C2Pro agent-control implementation to the VPS unchanged. The current `core/supervisor.py`, `blackboard.json`, `C2PRO_MASTER_BACKLOG.md`, category backlogs, schemas and agent instructions are treated as **legacy governance inputs to audit and reconcile**, not automatically as the future canonical development control plane.

The target operating model is:

```text
Owner / high-level instruction
        |
        v
C2Pro Development Orchestrator (ROLE, not model)
        |
        +-- validates campaign/work authority
        +-- creates compact WORK envelope
        +-- assigns role
        +-- selects eligible worker
        +-- manages retry / fallback / handoff
        +-- requests independent review
        +-- resolves bounded findings
        +-- validates evidence + CI
        +-- approves PR when policy allows
        |
        v
AI-Gen AF-DEV-01 governed execution plane
        |
        v
AI-Gen MR-DEV-01 DEVELOPMENT_ONLY route authority
        |
        +-- PRINCIPAL: Claude Code
        +-- PRINCIPAL: Codex
        +-- SUBORDINATE: Gemini CLI
        +-- SUBORDINATE: Antigravity
        +-- SUBORDINATE: OpenCode
        |
        v
isolated job-local clone / branch / sandbox
        |
        v
tests + evidence + independent review
        |
        v
PR approval gate
        |
        v
deterministic merge gate / human merge initially
```

The design must minimize owner interruptions. The owner authorizes a bounded campaign or work package once; the orchestrator proceeds autonomously inside that envelope and escalates only material exceptions.

---

## 2. Core principles

### 2.1 Role identity is independent from model identity

Tasks are assigned to a **role**, never permanently to Claude, Codex, Gemini, Antigravity or OpenCode.

Canonical task identity:

```text
WORK_ID + ROLE + BASE_SHA + SCOPE + ACCEPTANCE_CRITERIA
```

Worker selection is replaceable runtime state. If a model reaches a token/quota/session limit, another eligible worker can continue the same WORK_ID using a compact handoff without redefining the task.

### 2.2 Claude and Codex are principal workers

Initial authority hierarchy:

- **Claude Code:** principal worker.
- **Codex:** principal worker.
- **Gemini CLI:** subordinate/challenger/specialist.
- **Antigravity:** subordinate/challenger/workspace specialist.
- **OpenCode:** subordinate execution harness with separately governed provider/model routes.

Claude and Codex are peers at the authority layer. Either may act as implementation lead or independent review lead depending on the task.

### 2.3 No self-approval for material work

For material changes:

```text
implementation_principal != review_principal
```

Examples:

```text
Claude implements -> Codex independently reviews
Codex implements  -> Claude independently reviews
```

A subordinate worker may implement bounded changes, but promotion requires review/acceptance by an eligible principal according to policy.

### 2.4 Orchestrator is a role, not a model

The Development Orchestrator owns workflow state and authority decisions. Preferred worker may initially be Claude, with Codex fallback, but orchestration identity remains independent of vendor/model.

The orchestrator must be able to:

- create bounded work envelopes;
- select or replace workers;
- continue after provider/token exhaustion;
- launch tests and reviewers;
- request challenger review when warranted;
- remediate non-material findings inside approved scope;
- approve a PR when all gates pass;
- escalate only conditions outside delegated authority.

### 2.5 AI-Gen provides the execution security boundary

C2Pro must not duplicate AF-DEV/MR-DEV.

C2Pro owns product-development state and role/task semantics. AI-Gen AF-DEV-01 owns isolated execution; MR-DEV-01 owns DEVELOPMENT_ONLY model-route authority.

No C2Pro coding worker may gain Product Runtime authority from repository access.

### 2.6 Context must be hot/cold and token-efficient

The future control plane must not load historical execution detail into every agent session.

**Hot context:** only current state, current work, dependencies, applicable architecture constraints and required evidence.

**Cold context:** Git history, merged PRs, CI artifacts, archived tasks, old debates, historical detailed backlogs.

Git/GitHub/CI are the primary historical evidence stores. They should be referenced rather than duplicated.

---

## 3. Current-state findings to correct

### 3.1 `C2PRO_MASTER_BACKLOG.md`

The file currently states that it is a pending-work index, but still contains substantial completed history, certificates, PR closure details and long task descriptions. This makes it expensive as an always-loaded control surface.

Target: compact active queue/index only, or replace with a smaller machine-readable work queue after reconciliation.

### 3.2 `blackboard.json`

The current blackboard persists completed tasks with detailed file lists, timestamps, test logs and narrative outcomes. That duplicates Git/PR/CI evidence and makes session context grow over time.

Target: deprecate it as permanent canonical state. If a session state store remains useful, it must contain only active/short-lived state and be safely discardable/reconstructable.

### 3.3 `core/supervisor.py`

The current supervisor can invoke CLIs through direct subprocess execution from the repository base directory. This is incompatible with the target AF-DEV model because a coding worker must execute in an isolated job-local workspace, not directly in the canonical checkout.

Target: replace raw CLI execution with an AF-DEV job request/adaptor boundary.

### 3.4 `CHANGELOG.md`

The changelog currently includes extensive engineering implementation detail. Target use is release/product change communication, not exhaustive internal execution history.

Detailed implementation evidence belongs in commits, PRs, CI and evidence references.

### 3.5 Role/model drift

Existing docs/configuration contain different historical role-to-model assignments. Since the target system is role-first, model mappings must move to a compact routing policy and cease to be embedded as permanent task ownership.

---

## 4. Target control structure

Proposed logical structure (exact paths may be adjusted during C2PRO-DEV-00 audit):

```text
.c2pro/
├── control/
│   ├── current.yaml
│   ├── work-queue.yaml
│   └── routing.yaml
├── roles/
│   ├── orchestrator.yaml
│   ├── implementation.yaml
│   ├── reviewer.yaml
│   ├── qa.yaml
│   ├── security.yaml
│   └── specialist.yaml
├── work/
│   └── WORK-xxxx.yaml
├── handoff/
│   └── WORK-xxxx.yaml
└── evidence/
    └── WORK-xxxx.yaml
```

Rules:

- no historical task corpus in `current.yaml`;
- no raw CI logs in control YAML;
- no model-specific task identity;
- no secrets in repository YAML;
- completed work may be removed from the active queue after immutable Git/PR/evidence references exist;
- architecture constraints are referenced, not copied repeatedly.

---

## 5. Work envelope contract

Every material development job must contain at least:

```yaml
work_id: C2P-DEV-XXXX
campaign_id: optional
role: implementation_lead
base_sha: exact_sha
branch: bounded_branch
scope: []
out_of_scope: []
allowed_tools: []
forbidden_paths: []
acceptance_criteria: []
required_tests: []
evidence_required: []
review_policy: independent_principal
worker_selection:
  preferred: null
  fallback: []
timeout_resource_policy: ref
```

Worker selection may change while all invariant task fields remain unchanged.

---

## 6. Handoff contract for token/quota/provider exhaustion

A handoff must be compact and sufficient for continuation without replaying the full conversation.

Minimum fields:

```yaml
work_id: C2P-DEV-XXXX
role: implementation_lead
base_sha: exact_sha
current_head: exact_sha
current_worker: claude_code
handoff_reason: quota_exhausted
completed:
  - bounded fact
remaining:
  - bounded action
files_changed:
  - path
required_tests_remaining:
  - command_or_suite
known_findings: []
forbidden_scope_reminder: []
next_worker: codex
```

The replacement worker must not silently broaden scope or reset the baseline.

---

## 7. Review and multi-LLM feedback model

The default is **independent review + synthesis**, not unrestricted debate.

### Review policy by risk

```text
TRIVIAL
  -> focused tests
  -> principal review optional by policy

NORMAL
  -> independent principal review mandatory

MATERIAL
  -> independent principal review
  -> optional subordinate challenger

ARCHITECTURE / SECURITY / HIGH BLAST RADIUS
  -> independent principal review
  -> challenger review
  -> orchestrator synthesis
```

When implementation and review disagree materially, the orchestrator may open one directed adjudication round. Open-ended model-to-model debate is not the default because it can consume substantial context without proportional value.

Review output must be compact and typed:

```yaml
verdict: PASS | PASS_WITH_FINDINGS | BLOCK
blocking: []
non_blocking: []
architecture_drift: false
security_concern: false
scope_deviation: false
recommended_action: approve | remediate | escalate
```

---

## 8. Campaign authorization and owner interruption policy

The owner should authorize bounded campaigns rather than individual micro-actions.

Example authority:

```yaml
campaign_id: C2PRO-DEV-CAMPAIGN-001
objective: migrate_and_operate_governed_vps_development
allowed_roles:
  - orchestrator
  - implementation_lead
  - reviewer
  - qa
allowed_workers:
  principal: [claude_code, codex]
  subordinate: [gemini_cli, antigravity, opencode]
authority:
  create_isolated_branch: true
  modify_scoped_code: true
  run_tests: true
  retry: true
  switch_worker: true
  request_reviews: true
  remediate_in_scope_findings: true
  open_pr: true
  approve_pr: true
forbidden:
  direct_main_mutation: true
  production_runtime: true
  secrets: true
  unapproved_architecture_change: true
  destructive_data_migration: true
  autonomous_unbounded_spend: true
```

### Escalation conditions

The orchestrator should interrupt the owner only for conditions such as:

- architecture change outside approved design;
- scope expansion;
- production/deployment authority;
- secret/credential changes;
- destructive or consequential data migration;
- budget/spend outside profile;
- unresolved material conflict between reviewers;
- security finding requiring a policy decision;
- acceptance criteria that cannot be satisfied;
- product decision not derivable from existing authorization.

Routine branch creation, edits, tests, retries, worker switching, review requests and in-scope remediation should not require repeated owner approval.

---

## 9. PR approval and merge boundary

The orchestrator may eventually produce `PR_APPROVED` when all required conditions are satisfied:

```text
implementation_lead != independent_review_lead
required CI = GREEN
required tests = PASS
blocking findings = 0
scope deviation = NONE
forbidden paths = untouched
campaign authority = valid
```

Initial rollout:

```text
Orchestrator PR_APPROVED -> Human merge
```

Later, after qualification:

```text
Orchestrator PR_APPROVED
        |
        v
Deterministic Merge Gate
        |
        +-- exact PR/head
        +-- authority active
        +-- CI green
        +-- required review
        +-- no blocked files/findings
        v
bounded auto-merge for pre-authorized low/medium risk classes
```

The LLM should not itself be the final mechanical enforcement boundary for merging.

---

## 10. Worker authority hierarchy

### Principal workers

#### Claude Code
Eligible initially for:

- orchestrator role;
- implementation lead;
- architecture/planning;
- independent review;
- security review;
- AI-domain implementation/review.

#### Codex
Eligible initially for:

- orchestrator fallback;
- implementation lead;
- backend/refactoring;
- infrastructure/DevOps;
- independent review;
- test/remediation work.

### Subordinate workers

#### Gemini CLI
Initial purpose:

- QA;
- broad-context inspection;
- frontend specialist;
- challenger review;
- bounded implementation after qualification.

#### Antigravity
Must be qualified as an execution surface independent from Gemini CLI. No inherited entitlement/qualification is assumed.

Initial purpose:

- workspace-wide analysis;
- challenger review;
- bounded specialist implementation.

#### OpenCode
OpenCode is an execution harness, not one model identity. Provider/model routes behind OpenCode remain separately qualified and auditable.

Initial purpose:

- bounded implementation;
- specialist/challenger work;
- cost/capability alternative when explicitly routed.

Subordinate work cannot be promoted without the required principal review/gate.

---

## 11. VPS target

C2Pro development execution moves to the VPS, while the PC/iPhone become operator interfaces.

Conceptual layout:

```text
VPS
├── canonical C2Pro Development checkout (workers do not modify directly)
├── AF-DEV job workspaces
│   ├── job-001
│   ├── job-002
│   └── ...
├── development worker identities / sandboxes
├── evidence/results
└── Development-only route authority
```

The PC remains useful for IDE/Remote SSH and manual inspection, but is no longer the execution dependency for coding agents.

---

## 12. Implementation work breakdown

### C2PRO-DEV-00 — Governance and context audit

**Goal:** determine what is genuinely useful in the current agent/backlog/supervisor system before migration.

Tasks:

1. inventory `agents.md`, `CLAUDE.md`, `.claude/`, `.gemini/`, `.codex`, `roles/`, `core/supervisor.py`, `core/models.yaml`, `core/session_config.json`, `blackboard.json`, `C2PRO_MASTER_BACKLOG.md`, `backlogs/`, `schemas/`, `skills/`, `skill_registry.yaml`, `CHANGELOG.md`;
2. identify duplicate sources of truth;
3. measure/context-estimate the files routinely loaded by agents;
4. identify rules still necessary for product safety (tenant isolation, architecture, TDD, etc.);
5. identify historical/process rules that can move to cold storage;
6. define KEEP / REWRITE / DEPRECATE / ARCHIVE disposition;
7. produce no functional product changes.

**Exit gate:** approved compact control design and migration map.

### C2PRO-DEV-01 — Minimal YAML control model

**Goal:** implement the smallest viable hot-state representation.

Tasks:

1. define schemas for current state, queue, work envelope, handoff and evidence references;
2. ensure completed history is not retained in hot state;
3. ensure state is reconstructable from Git/PR/evidence;
4. add validation tests;
5. define archival/deprecation path for legacy blackboard/backlog structures.

**Exit gate:** deterministic parse/validation and context-size target met.

### C2PRO-DEV-02 — Role model and authority hierarchy

**Goal:** separate role authority from worker/model identity.

Tasks:

1. define orchestrator, implementation lead, reviewer, QA, security and specialist roles;
2. define principal vs subordinate worker ceilings;
3. define no-self-approval rule;
4. define worker fallback/handoff policy;
5. define escalation conditions;
6. define risk classes and review policy.

**Exit gate:** same work envelope can move between Claude/Codex without changing task identity.

### C2PRO-DEV-03 — Claude/Codex principal worker readiness

**Goal:** make Claude Code and Codex the first operational principal workers on the VPS.

Tasks:

1. inventory installation/auth/session state;
2. install/update only if required;
3. bind separate worker execution identities/surfaces where required;
4. verify non-interactive invocation contract;
5. verify isolated read-only job;
6. verify bounded write/commit job;
7. verify no canonical-main mutation;
8. verify Runtime and secret denial;
9. verify timeout/resource limits;
10. record exact qualification evidence.

**Exit gate:** both workers individually qualified for bounded Development work.

### C2PRO-DEV-04 — Development Orchestrator role

**Goal:** replace the ineffective legacy supervisor behavior with role-driven orchestration.

Tasks:

1. define orchestrator state machine;
2. accept high-level work/campaign request;
3. create validated work envelope;
4. assign principal worker;
5. support fallback worker/handoff;
6. launch review/test stages;
7. synthesize findings;
8. retry/remediate inside authority;
9. stop/escalate outside authority;
10. emit compact final status.

**Exit gate:** synthetic campaign executes end-to-end without owner micro-approval.

### C2PRO-DEV-05 — AF-DEV integration

**Goal:** C2Pro never launches raw coding CLIs directly in canonical checkout.

Tasks:

1. replace direct supervisor subprocess execution path;
2. translate C2Pro work envelope to AF-DEV job envelope;
3. create isolated job-local clone/branch;
4. bind worker and sandbox policy;
5. collect result/evidence;
6. return normalized completion/handoff to C2Pro control.

**Exit gate:** no coding worker writes directly to canonical C2Pro development checkout.

### C2PRO-DEV-06 — MR-DEV direct Claude/Codex routes

**Goal:** authorize and qualify Development-only direct routes for both principals.

Tasks:

1. exact route/access-surface records;
2. route qualification evidence;
3. entitlement/session validation without credential disclosure;
4. kill-switch tests;
5. provider/token failure typing;
6. budget/usage boundaries where applicable;
7. fallback from one principal to the other without task identity loss.

**Exit gate:** at least Claude and Codex can be invoked end-to-end through AF-DEV + MR-DEV.

### C2PRO-DEV-07 — First real C2Pro workload

**Goal:** prove the system on a real but bounded repository task.

Selection rules:

- no production deploy;
- low/medium blast radius;
- clear tests and acceptance criteria;
- enough substance to exercise implementation/review/handoff.

**Exit gate:** isolated implementation, tests, evidence and PR produced.

### C2PRO-DEV-08 — Principal cross-review

**Goal:** prove Claude/Codex reciprocal independent review.

Tasks:

1. implementation by one principal;
2. blind/independent review by the other where feasible;
3. typed findings;
4. bounded remediation;
5. reviewer recheck;
6. evidence that implementation principal did not self-approve.

**Exit gate:** cross-review qualification PASS.

### C2PRO-DEV-09 — PR approval gate

**Goal:** allow orchestrator to produce a machine-verifiable `PR_APPROVED` state.

Tasks:

1. define approval schema;
2. verify CI/test requirements;
3. verify independent review;
4. verify campaign authority;
5. verify no forbidden files/scope drift;
6. generate deterministic approval artifact;
7. keep final merge human-controlled initially.

**Exit gate:** PR readiness can be accepted without owner reviewing every intermediate step.

### C2PRO-DEV-10 — Subordinate worker qualification

**Goal:** add Gemini CLI, Antigravity and OpenCode incrementally without principal authority.

Tasks per worker:

1. independent execution-surface registration;
2. authentication/entitlement evidence;
3. non-interactive/headless viability;
4. isolated job qualification;
5. exact capability scope;
6. resource/network limits;
7. failure/disable path;
8. principal promotion-review requirement.

Antigravity and Gemini CLI must remain separate surfaces. OpenCode provider/model routes must remain separate from the harness identity.

**Exit gate:** each subordinate can contribute safely under principal review.

### C2PRO-DEV-11 — Selective multi-LLM challenger policy

**Goal:** obtain multiple-model feedback where it materially improves quality without creating debate loops.

Tasks:

1. define trigger classes;
2. issue diff/task-focused challenger prompts;
3. normalize findings;
4. orchestrator synthesis;
5. permit one directed adjudication round for material disagreement;
6. measure added value/cost before broadening use.

**Exit gate:** challenger path demonstrated on at least one material task with bounded token/context cost.

### C2PRO-DEV-12 — Bounded autonomous campaign execution

**Goal:** owner gives a high-level bounded objective and receives final results without approving routine next steps.

Tasks:

1. campaign authority schema;
2. campaign lifecycle;
3. automatic work decomposition within bounded scope;
4. principal/subordinate assignment;
5. retries and handoffs;
6. multiple PR management if needed;
7. escalation-only owner interaction;
8. campaign completion evidence;
9. optional later deterministic auto-merge policy for qualified low/medium-risk classes.

**Exit gate:** one real campaign completes with owner interaction limited to authorization and genuinely material escalations.

---

## 13. Execution order

Two tracks may proceed in parallel after C2PRO-DEV-00 starts:

```text
CONTROL TRACK                         VPS WORKER TRACK
C2PRO-DEV-00 audit                   Claude inventory/qualification prep
        |                             Codex inventory/qualification prep
C2PRO-DEV-01 minimal YAML                    |
        |                                     |
C2PRO-DEV-02 roles/authority                  |
        |                                     |
C2PRO-DEV-04 orchestrator <-------- C2PRO-DEV-03 principals
        |                                     |
        +------------- C2PRO-DEV-05 AF-DEV ---+
                              |
                       C2PRO-DEV-06 MR-DEV
                              |
                       C2PRO-DEV-07 real work
                              |
                       C2PRO-DEV-08 cross-review
                              |
                       C2PRO-DEV-09 approval
                              |
                       C2PRO-DEV-10 subordinates
                              |
                       C2PRO-DEV-11 challengers
                              |
                       C2PRO-DEV-12 campaigns
```

Do not activate autonomous product changes before C2PRO-DEV-00/01/02 define the new control semantics and the AF-DEV/MR-DEV boundary is respected.

---

## 14. Immediate next step

The first execution step after this plan is merged is:

**C2PRO-DEV-00 — Governance and context audit.**

It must be read-only with respect to product behavior. The audit should produce:

- authoritative inventory;
- context/token-cost diagnosis;
- KEEP / REWRITE / DEPRECATE / ARCHIVE matrix;
- proposed compact YAML schemas;
- migration dependencies;
- exact next implementation slice.

The owner should then be guided through the implementation one bounded step at a time, while the design progressively reduces manual approval frequency rather than increasing it.

---

## 15. Definition of success

The migration is successful when the owner can issue a bounded high-level development objective and the system can, without repeated micro-approvals:

1. create the correct work envelope;
2. select Claude or Codex as principal;
3. continue with the other principal if tokens/quota/provider fail;
4. use Gemini/Antigravity/OpenCode as bounded specialists/challengers;
5. execute only in isolated AF-DEV workspaces;
6. obtain independent review;
7. remediate findings inside scope;
8. run required tests/CI;
9. produce compact evidence;
10. approve a PR under machine-enforced policy;
11. escalate only material authority/product/security decisions;
12. preserve Product Runtime separation and no direct agent mutation of `main`.
