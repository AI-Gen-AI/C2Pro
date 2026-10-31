# ACC-01 S1–S8 acceptance on one persisted project

**Purpose:** the procedure to show that one real user completes S1–S8 in ONE persisted project, and the rules for
what may be called PASS. It does not hold status: status lives in the MASTER control
(`validation/product/c2pro-master-product-control-v1.yaml`) and the canonical matrix
`apps/api/tests/fixtures/pq_hitl_09_multidoc_journey_matrix_v1.json` (where every `live_uat_status` is
`NOT_VERIFIED` until a run below records otherwise).

## Evidence classes (never mix them in a verdict)

| Class | What it proves | What it does not prove |
|---|---|---|
| **CI** (`ci.yml`) | Lint, types, unit, PostgreSQL integration, Playwright smoke with mocked routes. | Anything about a deployed environment or real AI. |
| **Local PostgreSQL** | Backend behaviour against a real database, deterministic AI. | Browser, Clerk, deployed SHAs. |
| **Nightly Full E2E** (`nightly-full-e2e.yml`) | Real browser + real local backend + Clerk E2E organisation, **deterministic AI provider** (`C2PRO_AI_MOCK=1`). With `run_pj01=true`: PJ-01 journey and independent PostgreSQL reads. | Real AI output, a deployed environment. |
| **UAT real** | The same journey against an authorised isolated environment with **real Clerk and real AI**, runtime SHAs recorded. | Production qualification (separate gate, G0 #1054). |
| **Production** | Not part of this procedure. | — |

A step is **PASS** only with evidence of the class named in the verdict, tied to an exact SHA. Otherwise
`PARTIAL` (part of the step shown) or `NOT_VERIFIED`. A merged or green PR is never a PASS of a step.

## Preparation (one project, four documents, two tenants)

1. Authorised isolated environment; record frontend and backend runtime SHAs (must equal the candidate head).
2. Tenant A user (real Clerk login). Tenant B user (second Clerk identity) with its own project — required for the
   B→A denial; without it that direction stays `NOT_RUN`.
3. Fixture files (committed synthetic fixtures only; no customer data): Contract DOCX, Budget XLSX,
   Schedule XLSX, Technical Specification DOCX, plus an unsupported format for the negative.
4. For the real-AI UAT: provider keys live in the environment secrets, never in the repository, and the run output
   (documents, findings, logs) is stored outside the repository.

## Steps and the evidence each needs

| Step | Do (browser) | Evidence to record |
|---|---|---|
| S1 | Log in with Clerk; create the project. | Session after login, project id, tenant id; tenant B cannot read the project (401/403/404). |
| S2 | Upload the four documents through the dialog; upload the unsupported file. | Four document ids with revision ids and SHA-256 of stored bytes (database read); the backend rejects the unsupported format. |
| S3 | Evaluate. | Six-dimension Health with unmeasured dimensions `null/UNKNOWN`; Score `null` with a reason when evidence is insufficient (e.g. `contract_pending_approval`, TECHNICAL unmeasured); alerts persisted; no invented value; Score and Alerts unchanged by a pending contract. |
| S4 | Open an alert, follow its source link. | Link resolves to the trusted revision of the right project/tenant; where no row-level link exists the UI states the limitation. |
| S5 | Review each item (granular), then the separate final human act; also reject one item. | Per-item decisions with decider and reason; final approval is a distinct act; the rejected item leaves no trusted artifact. |
| S6 | Upload revision B of a document; do not approve; then approve. | What Changed and Current State while B is pending (A trusted, B pending) and after approval; hashes match the fixtures. |
| S7 | Approved WBS; Budget, Schedule, Technical linked to it. | Each link names source revision, row/activity/clause locator and the approved WBS baseline and node, with the human approver. Until the canonical link writer exists this step is `PARTIAL` at best. |
| S8 | Log out, log in again. | Same documents, alerts, decisions, score state; foreign tenant denied in both directions. |

## Running it

- **Nightly (deterministic AI):** dispatch `Nightly Full E2E` on the candidate branch with `run_pj01=true`. Read the
  step results of the executable suite, the triplet journey, `Verify PJ-01 revision trace in PostgreSQL` and
  `Verify S5 rejection in PostgreSQL`. The PJ-01 `run.json` and screenshots are in the uploaded diagnostics.
- **UAT real:** run the same table by hand (or the PJ-01 harness) against the isolated environment with real Clerk
  and real AI; file the evidence outside the repository and reference it from the tracking issue.

## Integral S1–S8 runner (one executable, opt-in)

`acc01-s2-live-ai-uat.yml` carries the integral runner behind `workflow_dispatch` with `integral_uat=true`; with the
default (`false`) the workflow behaves exactly as before. Its scenario is
`apps/web/src/tests/e2e/integral-s1-s8.spec.ts` (Playwright project `integral-s1-s8`): ONE project created by Clerk
Development identity A through the wizard carries every stage; identity B (another Organization and tenant) owns a
project of its own for the denial in both directions, before and after the relogin.

| Dispatch input | Meaning |
|---|---|
| `integral_uat=true` | select the integral runner instead of the original S2 job |
| `integral_preflight_only=true` | read-only check of the two Clerk Development identities (no database, no AI) |
| `integral_ai_mode=deterministic-rehearsal` (default) | runs the whole runner with `C2PRO_AI_MOCK=1`: no paid provider key is even in the environment; the verdict is `REHEARSAL_ONLY_NOT_UAT`, never UAT |
| `integral_ai_mode=real-ai` + `integral_confirm_real_ai_sha=<full candidate SHA>` | real provider calls (`C2PRO_AI_MOCK=0`); refused unless the typed SHA equals the dispatched one |

Fail-closed rules of the runner: the job checks `HEAD == GITHUB_SHA`; backend, worker and frontend runtime SHAs are read
from the RUNNING processes (`write_integral_runtime_receipt.py`); the database is prepared only with the two tenants
(`seed_integral_uat.py`, nothing of the journey); a failure records the FIRST failing stage and the run stops there
(later stages are `NOT_RUN`, never inferred); what the product cannot do is `PARTIAL` with its reason.
`verify_integral_s1_s8_pg.py` re-reads PostgreSQL on the same project id and writes `integral-manifest.json`
(candidate/runtime SHAs, project ids, document/revision/event ids, provider call receipt, Clerk identity checks, S1–S8
verdicts, first failure). Artifacts hold JSON only: no screenshot, trace, prompt or completion.

Declared limits (reported in every manifest, never hidden):

* the canonical WBS baseline is approved by the same human who submitted it (tenant A has one human), under the
  tenant setting `wbs_governance.require_distinct_approver=false` set by the seed; it is recorded as `self_approved`;
* granular per-finding decisions have no HTTP route or UI, so they are not exercised in the browser (S5 is `PARTIAL`);
* the alert → source link is the contract clause; budget/schedule rows are named in the evidence text (S4 is `PARTIAL`);
* the verdict `NOT_ACCEPTED_UNTIL_INDEPENDENT_REVIEW` is fixed: the runner never accepts itself.

## Rules

- No merge, deployment, production SQL/DDL, bypass of a human approval, or automatic change to MASTER as part of a run.
- PROPOSED is never TRUSTED: a pending document never moves a score or resolves an alert, and a verdict says so.
- Report the exact SHA, the evidence class and the run URL for every PASS; everything else is `PARTIAL` or `NOT_VERIFIED`.
