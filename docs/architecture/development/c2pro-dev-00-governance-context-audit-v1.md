# C2PRO-DEV-00 — Governance & Context Audit v1

**Status:** AUDIT COMPLETE / OWNER PLAN IMPLEMENTATION INPUT  
**Date:** 2026-08-24  
**Repository:** `AI-Gen-AI/C2Pro`  
**Audit baseline:** `main@792de19a647fce1c1cd0c0064162db99f9a2d991`  
**Parent plan:** `docs/architecture/development/c2pro-vps-development-control-plan-v1.md`  
**Scope:** read-only audit of current development-control/context surfaces. No product behavior, runtime, deployment, credentials, branch policy or production authority changes are authorized by this document.

---

## 1. Executive decision

The current C2Pro agent-control stack contains useful engineering knowledge, but it is not suitable to migrate unchanged to the VPS as the canonical autonomous development control plane.

The main issue is not a lack of governance. It is **governance duplication and context overloading**:

- multiple overlapping agent/role instruction surfaces;
- vendor-specific instructions carrying project authority;
- persistent historical state in files that workers are instructed to read repeatedly;
- model identity mixed with role identity and route/invocation details;
- task completion duplicated across backlog, category backlog, blackboard, changelog, commits, PRs and CI;
- the current supervisor is coupled to the legacy backlog/blackboard model and can invoke CLIs directly in the repository root;
- some current instructions are stale or internally contradictory.

The transition therefore SHALL preserve product/architecture knowledge while replacing the hot development-control surface with a compact, vendor-neutral, task-scoped model.

**Target principle:**

```text
HOT = only what the current job needs to execute safely and correctly
COLD = history, completed work, detailed evidence and explanatory material retrievable by reference
```

Git, GitHub PRs, CI, ADRs and immutable evidence become the primary historical record. They must not be re-serialized into every active work context.

---

## 2. Audit findings

### F1 — `C2PRO_MASTER_BACKLOG.md` contradicts its own pending-only purpose

The file states that only pending work is tracked, yet includes completed phase certificates, ADR implementation audits, old CI results, completed epics/tasks, PR histories and detailed implementation narratives.

This is useful historical material but is inappropriate as mandatory hot context.

**Impact:** high context cost, stale-state risk, duplicated provenance.

**Disposition:** `RECONCILE_AND_SHRINK`, then `COLD_REFERENCE` for historical detail.

---

### F2 — `blackboard.json` is not ephemeral in practice

The supervisor documentation calls it ephemeral session state, but the current file persists an old session and many completed tasks. Each completed task can include:

- description;
- done criteria;
- changed files;
- timestamps;
- result narrative;
- lint/test state;
- detailed test command/results;
- follow-up notes.

Most of that already exists in commits, PRs and CI.

**Impact:** severe context duplication; handoff state is mixed with permanent history.

**Disposition:** `DEPRECATE_AS_PERMANENT_CANONICAL_STATE`.

A future ephemeral execution state MAY exist, but it must contain only active work and must be disposable/reconstructable from durable work/evidence records.

---

### F3 — `core/supervisor.py` is structurally coupled to legacy governance

The current supervisor:

- treats `blackboard.json` as execution state;
- scans `C2PRO_MASTER_BACKLOG.md` and `backlogs/*.md` to validate task IDs;
- requires completed tasks to be re-marked in Markdown backlogs;
- maps roles to model IDs through `session_config.json`;
- builds provider-specific CLI commands;
- can execute CLI subprocesses directly from the repository base directory.

This conflicts with the approved target architecture where AF-DEV controls isolated workspaces, MR-DEV controls Development-only invocation authority, and work identity is independent of the selected model.

**Disposition:** `REPLACE`, not incremental patching as the final architecture.

Useful validation concepts may be reimplemented in the new controller, but the current supervisor must not become the VPS security/execution boundary.

---

### F4 — role identity and model identity are mixed

`core/session_config.json` currently assigns concrete models to roles. `core/models.yaml` mixes:

- CLI/harness;
- vendor;
- model name;
- qualitative strengths/weaknesses;
- invocation syntax;
- timeout;
- system-prompt behavior.

This prevents clean handoff and does not represent the approved distinction:

```text
ROLE != WORKER != HARNESS/ACCESS SURFACE != PROVIDER ROUTE != MODEL != ENTITLEMENT
```

**Disposition:** both files `REWRITE/REPLACE` under the new registry/routing model.

---

### F5 — vendor-specific authority is fragmented

Current instruction/control surfaces include at least:

- root `agents.md`;
- root `CLAUDE.md`;
- `.claude/rules/*`;
- `.github/agents/*`;
- `roles/*`;
- `.gemini/settings.json`;
- `.codex`;
- skill trees.

There is no equivalent canonical `GEMINI.md` in `main`, while `CLAUDE.md` carries extensive project protocol and project-state guidance.

`CLAUDE.md` also references `llms.txt`, which is not present in the audited baseline.

**Impact:** different coding surfaces can receive different authority/context and can drift independently.

**Disposition:** central vendor-neutral authority plus **thin vendor adapters only**.

Vendor files may explain how a tool locates the canonical control contract, but must not define separate project governance.

---

### F6 — current role profiles contain valuable domain constraints but stale execution protocol

The `roles/` directory is conceptually useful. It contains domain-specific rules for backend, frontend, QA, security, review, infrastructure, etc.

However, current roles are tightly coupled to `blackboard.json`, category backlogs and model registry. At least one role contains an internal route contradiction: backend tests are both protected and included in assignable routes while the same role mandates strict TDD.

**Disposition:** `KEEP_CONCEPT / REWRITE_COMPACT`.

Preserve valid product/architecture invariants; remove historical/session mechanics and redundant prose.

---

### F7 — `.github/agents/`, `.claude/rules/agents.md` and `roles/` duplicate agent taxonomy

Multiple agent taxonomies exist with overlapping but non-identical role names and responsibilities.

**Impact:** authority ambiguity, duplicated maintenance, inconsistent model behavior.

**Disposition:** one canonical role registry. Provider/tool-specific agent definitions, if still operationally useful, should be generated/thin adapters or cold compatibility files.

---

### F8 — schema assets contain reusable validation ideas but are over-specialized to the legacy blackboard

`schemas/` contains many role-specific output schemas plus blackboard validation. Structured output is valuable and should be retained as an engineering principle.

The future control plane needs fewer, stronger contracts centered on the lifecycle rather than one large output schema per agent persona.

**Recommended future schema classes:**

1. `campaign_authorization`;
2. `work_envelope`;
3. `handoff`;
4. `review_result`;
5. `evidence_result`;
6. `routing/worker eligibility`;
7. `merge_gate_result` (later phase).

**Disposition:** `KEEP_PRINCIPLE / RECONCILE_SCHEMAS`.

---

### F9 — skills are duplicated across compatibility trees

There is an `agent_skills/` tree and a separate `skills/` compatibility structure containing provider/agent-oriented subtrees.

Skills themselves can be high-value and should not be discarded. The issue is discovery/authority duplication.

**Disposition:** `RECONCILE_TO_ONE_CANONICAL_SKILL_REGISTRY`; preserve provider adapters only where needed.

Skills must be loaded on demand by task capability, not automatically as global context.

---

### F10 — `CHANGELOG.md` is carrying engineering-journal detail

The current changelog includes exact implementation files, migrations, test counts, backlog IDs, phase internals and deferred engineering items.

That information is useful but belongs mainly in PRs, ADRs, evidence and work records.

**Disposition:** `KEEP_AND_SHRINK`.

Future changelog scope: release/user-visible behavior, compatibility, migrations/operators where materially relevant, deprecations and notable security/product changes.

---

## 3. Context footprint

The audit identified a **known subtotal of roughly 247 KB** across only these visible control families:

| Surface | Approx. bytes |
|---|---:|
| `backlogs/*.md` | 114,604 |
| `roles/*.md` | 33,822 |
| `.github/agents/*.md` | 11,583 |
| `.claude/rules/*.md` | 20,094 |
| `schemas/*` | 67,084 |
| **Subtotal** | **247,187** |

This subtotal excludes large/high-impact files such as `C2PRO_MASTER_BACKLOG.md`, `blackboard.json`, `CLAUDE.md`, `agents.md`, `CHANGELOG.md`, skill contents, architecture docs, test-index docs and source code.

A naive load of 247 KB alone can easily consume **tens of thousands of model tokens** depending on tokenizer/content. Therefore token efficiency cannot be solved only by changing file format.

The control architecture must reduce **what is loaded**, not merely serialize it more compactly.

---

## 4. Canonical classification matrix

| Current surface | Classification | Future treatment |
|---|---|---|
| `agents.md` | REWRITE | Thin vendor-neutral repository entrypoint pointing to canonical Development Control |
| `CLAUDE.md` | REWRITE | Thin Claude adapter; no independent project authority/state |
| `.claude/rules/*` | RECONCILE | Extract valid invariants; deprecate duplicate backlog/session rules |
| `.github/agents/*` | ARCHIVE_OR_ADAPTER | Keep only if a GitHub agent surface needs adapters; never independent authority |
| `roles/*` | KEEP_CONCEPT_REWRITE | Compact canonical role profiles, model-neutral |
| `core/supervisor.py` | REPLACE | New Development Orchestrator/controller integrated with AF-DEV/MR-DEV |
| `core/models.yaml` | REWRITE | Separate worker/harness identity from route/model/provider/entitlement |
| `core/session_config.json` | REPLACE | Role eligibility/routing policy, not fixed role→model mapping |
| `blackboard.json` | DEPRECATE | Archive current snapshot; future active state must be ephemeral/minimal |
| `C2PRO_MASTER_BACKLOG.md` | RECONCILE_AND_SHRINK | Extract only actionable open work; historical detail cold |
| `backlogs/*.md` | COLD_REFERENCE | Preserve until open work is reconciled; then archive/retire as hot context |
| `schemas/*` | KEEP_PRINCIPLE_REWRITE | Consolidate around work lifecycle contracts |
| `skills/` | RECONCILE | One canonical on-demand skill registry |
| `agent_skills/` | RECONCILE | Merge useful skills into canonical registry |
| `.gemini/settings.json` | KEEP_AS_ADAPTER | Tool-local settings only, zero project authority |
| `.codex` | KEEP_AS_ADAPTER_SLOT | Tool-local adapter only if required |
| `CHANGELOG.md` | KEEP_AND_SHRINK | Release/notable changes only |
| Git commits / PRs / CI | KEEP_PRIMARY_HISTORY | Primary execution history and detailed evidence provenance |
| ADRs / architecture docs | KEEP_COLD_ON_DEMAND | Load only when scope touches governed architecture |

No legacy file is to be deleted during C2PRO-DEV-00.

---

## 5. Target hot/cold context model

### 5.1 HOT — mandatory and intentionally small

A normal worker should receive only:

```text
1. campaign authorization reference / effective bounded authority
2. WORK envelope
3. role profile
4. task-scoped architecture/invariants references or extracted constraints
5. required acceptance/tests
6. handoff state if continuing another worker
7. explicit allowed/forbidden paths/tools
```

**Target:** normally single-digit KB to low tens of KB before source-code context, not hundreds of KB of governance history.

The exact byte/token ceiling will be established and tested in C2PRO-DEV-01/02; C2PRO-DEV-00 does not freeze an arbitrary hard number.

### 5.2 WARM — fetch when needed

Examples:

- relevant ADR;
- module design document;
- related open dependency;
- relevant prior PR/evidence;
- specific skill;
- test-suite contract;
- active project milestone.

### 5.3 COLD — never mandatory for every task

Examples:

- completed backlog tasks;
- full changelog history;
- old blackboard sessions;
- closed PR implementation narratives;
- old CI output;
- completed role-specific backlog entries;
- historical audits;
- superseded plans.

Cold does **not** mean deleted. It means addressable by reference and omitted from routine model context.

---

## 6. Minimum future work identity

Work must be nominative by role and stable across model changes:

```yaml
work_id: C2P-WORK-xxxx
role: implementation_lead
base_sha: <immutable SHA>
scope: [...]
out_of_scope: [...]
acceptance_criteria: [...]
required_tests: [...]
allowed_tools: [...]
forbidden_paths: [...]
review_policy: material
```

Runtime worker selection is separate:

```yaml
worker_assignment:
  current: claude_code
  eligible_fallbacks: [codex]
```

If quota/token/provider failure occurs, the next worker receives the same work identity plus a compact handoff. The task is not recreated as a new Claude/Codex task.

---

## 7. Principal/subordinate authority model confirmed by audit

### Principal workers

- Claude Code
- Codex

Both are eligible for implementation lead and independent principal review, subject to exact route qualification and task policy.

Material self-approval is forbidden:

```text
Claude implements -> Codex principal review/gate
Codex implements  -> Claude principal review/gate
```

### Subordinate/challenger workers

- Gemini CLI
- Antigravity
- OpenCode

Initially they may analyze, challenge, QA/review or perform bounded implementation when separately qualified. Their result cannot independently promote material work to approved state.

### Orchestrator

The Orchestrator is a role, not a model. Its implementation/provider may change without changing the work/campaign authority contract.

---

## 8. Multi-LLM collaboration policy

Default for material work:

```text
implementation
   -> independent principal review
   -> optional independent challenger review
   -> bounded synthesis
   -> remediation if blocking
   -> final gate
```

Open-ended conversational debate between models is not the default because it can multiply cost/context without improving the decision.

Directed model debate is reserved for material unresolved disagreement (architecture, security, acceptance interpretation, competing implementation strategies).

Review outputs should be compact and structured, e.g.:

```yaml
verdict: PASS_WITH_FINDINGS
blocking: [F1]
non_blocking: [F2]
architecture_drift: false
security_concern: false
recommended_action: remediate_F1
```

---

## 9. Owner-interruption policy

The target system should operate under bounded campaign authority rather than asking the owner for routine micro-approvals.

Within an approved campaign, the Orchestrator should be able to perform permitted operations such as:

- create isolated job branches/workspaces;
- modify in-scope code;
- run permitted tests/lint/typecheck;
- retry bounded failures;
- change eligible worker after quota/transport failure;
- request independent reviews;
- remediate blocking findings within original scope;
- open a PR;
- produce machine-verifiable `PR_APPROVED` when policy permits.

Owner escalation remains required for at least:

- scope expansion;
- architecture change outside existing authority;
- secrets/credential changes;
- production/runtime authority;
- destructive migration/data action;
- material security exception;
- budget/spend outside the approved ceiling;
- unresolved principal disagreement;
- impossible/contradictory acceptance criteria;
- consequential product decision not contained in campaign authority.

Initial merge to `main` remains human-controlled as frozen by the parent plan.

---

## 10. C2PRO-DEV-01 implementation input

C2PRO-DEV-01 shall implement the **Minimal YAML Control Model**. It should not yet rewrite all legacy files.

### Package 01-A — canonical directory skeleton

Proposed target namespace (final naming can be validated during implementation):

```text
.c2pro/
  control/
    current.yaml
    work-queue.yaml
    routing.yaml
  roles/
  work/
  handoff/
  evidence/
  schemas/
```

### Package 01-B — `current.yaml`

Must contain only current execution-control state such as:

- schema/version;
- current canonical plan;
- active campaign/work references;
- next eligible work;
- authority state;
- key base SHAs/refs;
- explicit next gate.

Must not contain completed task narratives.

### Package 01-C — `work-queue.yaml`

Only open/actionable development-control work. Minimal fields:

```text
work_id
status
priority
role
dependency
scope_ref / concise objective
campaign_ref
```

Detailed implementation history belongs elsewhere.

### Package 01-D — work-envelope schema

Must enforce stable role-based work identity and explicit scope/acceptance/BASE_SHA.

### Package 01-E — handoff schema

Must support model/provider/token exhaustion without resetting task identity. Minimum handoff should capture:

- work_id;
- from_worker;
- reason;
- current_head/ref;
- completed actions;
- pending actions;
- blocking findings;
- tests/evidence already produced;
- next recommended action.

No raw chain-of-thought is required or permitted as a continuity dependency.

### Package 01-F — evidence-reference schema

Store references/hashes/status, not full CI/log narratives by default.

### Package 01-G — legacy compatibility rule

Until reconciliation is complete:

- do not delete master backlog/category backlogs/blackboard;
- new Development Control does not infer authority from them;
- extract/reconcile active work before archiving old surfaces;
- product/architecture source-of-truth docs remain valid within their actual scope.

### Package 01-H — context budget instrumentation

Add a deterministic way to calculate/record the bytes/files included in a generated work context so that context reduction is measurable rather than subjective.

C2PRO-DEV-01 acceptance should demonstrate a sample task package that can be understood without loading the entire legacy governance corpus.

---

## 11. Ordered migration after C2PRO-DEV-00

```text
C2PRO-DEV-00  Governance/context audit                     DONE by this artifact after merge
C2PRO-DEV-01  Minimal YAML control model                  NEXT
C2PRO-DEV-02  Role and authority hierarchy                BLOCKED_BY DEV-01
C2PRO-DEV-03  Claude/Codex principal worker activation    CAN PROGRESS VPS PREP IN PARALLEL; control integration after DEV-02
C2PRO-DEV-04  Orchestrator role                           BLOCKED_BY DEV-01/02
C2PRO-DEV-05  AF-DEV integration                         BLOCKED_BY DEV-01/02/04
C2PRO-DEV-06  MR-DEV Claude/Codex routes                 GOVERNED WITH AI-GEN MR-DEV; route qualification required
C2PRO-DEV-07  First real C2Pro workload                  BLOCKED_BY governed execution + direct route
C2PRO-DEV-08  Principal cross-review                     BLOCKED_BY DEV-07
C2PRO-DEV-09  PR approval gate                           BLOCKED_BY DEV-08
C2PRO-DEV-10  Gemini/Antigravity/OpenCode qualification  AFTER principal baseline
C2PRO-DEV-11  Selective multi-LLM challenger             AFTER subordinate qualification
C2PRO-DEV-12  Bounded autonomous campaign execution      FINAL maturity gate
```

---

## 12. C2PRO-DEV-00 acceptance result

| Criterion | Result |
|---|---|
| Audit current control surfaces | PASS |
| Identify duplication/staleness | PASS |
| Classify KEEP/REWRITE/DEPRECATE/ARCHIVE | PASS |
| Define hot/warm/cold model | PASS |
| Preserve role-not-model task identity | PASS |
| Preserve Claude/Codex principal model | PASS |
| Define multi-LLM review without open-ended debate | PASS |
| Define owner escalation boundary | PASS |
| Produce actionable DEV-01 packages | PASS |
| Modify product/runtime behavior | NONE |
| Delete legacy governance | NONE |

**Audit verdict:** `C2PRO-DEV-00 = READY_FOR_DONE_ON_MERGE`.

**Next:** `C2PRO-DEV-01 — Minimal YAML Control Model`.
