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
| S4 | Open an alert, follow its source link. | Link resolves to the trusted revision of the right project/tenant; a Budget/Schedule finding also links the exact original row (document, revision, `Sheet!row`, SHA-256), re-verified by the API on every read; stale or foreign pointers are refused without content. |
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

Clerk during the UAT is READ-ONLY for both identities: the preflight verifies A and B and takes the public JWKS
(validated: public RSA keys only) into the runner's temporary directory, so `CLERK_JWKS_URL` stays functional. The
Playwright project `integral-auth-preflight` then presents each identity's real JWT to the local API; the scenario
(`integral-s1-s8`) depends on it and does not start otherwise. Writing to Clerk Development is only possible in the
separate, SHA-confirmed jobs `integral-prepare-dev-a` / `integral-prepare-dev-b`; `integral_discover_dev_b` is a
read-only, paginated inventory whose receipt holds counts and pseudonyms only (outcomes `DEV_B_CANDIDATE_FOUND`,
`DEV_B_CREATION_REQUIRED`, `INVENTORY_INCOMPLETE`).

Declared limits (reported in every manifest, never hidden):

* the canonical WBS baseline is approved by the same human who submitted it (tenant A has one human), under the
  tenant setting `wbs_governance.require_distinct_approver=false` set by the seed; it is recorded as `self_approved`;
* the Budget and Schedule sources are trusted by their requester (ADR-032): tenant A carries the audited exception
  `trust_governance.structured_source_self_approval = {enabled, reason, granted_by, granted_at}` written by the seed to
  tenant A's row only; each decision is recorded as `self_approved` and the manifest reports
  `structured_trust_independence = SELF_APPROVED_NOT_INDEPENDENT`;
* granular per-finding decisions have a route (`GET /hitl/reviews/{row}/findings`, `POST .../findings/decisions`) and a review-card surface; they are PROVISIONAL (append-only ledger, never approve/reject/trust, not read by the final approval). The runner takes them through the UI when the provider yields findings; the deterministic provider extracts none, so S5 stays `PARTIAL` there and a real-AI run is what exercises them;
* the alert → source link covers the contract clause AND the original Budget row (S4 `PASS` requires a Budget pointer whose SHA-256 equals the stored revision; a Schedule pointer exists only when a finding rests on an activity);
* the verdict `NOT_ACCEPTED_UNTIL_INDEPENDENT_REVIEW` is fixed: the runner never accepts itself.

Another tenant's project answers 404 on every persisted-alerts read (an own project without alerts answers 200 with an
empty list); the runner accepts only 401/403/404 for a foreign project, never an empty 200.

Static-typing debt of `apps/api/scripts/verify_integral_s1_s8_pg.py` (outside the CI mypy ratchet, which covers `src`):
mypy reports 7 errors that PRE-DATE ADR-032, all of one kind (`dict | None` used without a guard, plus one `Any` return):
lines 234-235 (`_judge_s1`), 442 and 446 (`_judge_s6`), 531 and 536 (`_judge_s7_link`: `baseline` optional), 1016
(`_first_failure`: `Any` return). The three errors introduced by the ADR-032 chain were fixed; the
seven remain recorded here, unchanged, rather than hidden.

## Real-AI pilot UAT — preparation (NOT executed; nothing here activates a provider or creates an identity)

Purpose: ONE UAT by a pilot user over four representative documents, with a real provider and persisted evidence, so that S5
(and the evidence class `UAT_REAL`) can be judged for the first time. The deterministic rehearsal of 2026-11-02
(`DETERMINISTIC_REHEARSAL_COMPLETE_WITH_LIMITATIONS`) is not a substitute and is never counted as one.

**Blocking gates (each needs its own authorization/decision; none is solved by this preparation).**

| # | Gate | Why it blocks | Needed |
|---|---|---|---|
| G1 | Runner policy for REAL findings under `enforce` | With `C2PRO_AI_MOCK=0` the controlled candidate is off; the spec then takes the four-action scenario on the provider's findings and tries to approve, which S5-04 refuses (`409 reconciliation_blocks_approval`) because some findings stay undecided | An authorized runner change: confirm EVERY real finding (positive route), or derive Vn+1 for dismissals; the number of findings is not five and not known in advance |
| G2 | Pilot document set | The runner pins six synthetic fixtures by name and SHA-256 (`support/integral/fixtures.ts`) | Four owner-supplied documents (contract, budget, schedule, specification), sanitized, with their SHA-256 pinned BEFORE the run, and a documented right to send them to the provider (the N2 anonymizer runs before Claude, but it is not a consent) |
| G3 | Provider credentials | The job refuses `real-ai` unless the dedicated test-only secrets `S2_E2E_ANTHROPIC_API_KEY` and `S2_E2E_OPENAI_API_KEY` (embeddings) exist, and `integral_confirm_real_ai_sha` equals the full candidate SHA | The owner confirms the secrets exist and are test-only; this preparation did not read or create any secret |
| G4 | Clerk Development identities | A and B pass the read-only preflight today; S7 independence needs a SECOND human in tenant A | Creating one is an owner decision (no identity was created); without it S7 stays `PARTIAL` (`SELF_APPROVED_NOT_INDEPENDENT`) |
| G5 | Derived-candidate semantics (only if the pilot dismisses or corrects findings) | Exclusions are implemented; corrections are gated (`CORRECTIONS_RATIFIED`, which field they replace) and the review card has no "Derive candidate" action | Owner ratification of A1/A2 of the S5 audit note and a UI increment |
| G6 | CI headroom | `Backend Modules Tests` runs ~19 of its 20 minutes and timed out once at 100 % pass | A separate infrastructure task; a UAT needs a green exact-HEAD CI first |
| G7 | Open security/authority gaps | P1 SQL administrative authority NOT_VERIFIED, typed critique UNEVALUATED, independent security review PENDING | They do not block running a UAT, but they keep S5 `PARTIAL / NOT_ACCEPTED` whatever its result |

**Dispatch (when authorized, one run).** `acc01-s2-live-ai-uat.yml` with `integral_uat=true`, `integral_ai_mode=real-ai`,
`integral_confirm_real_ai_sha=<full 40-hex candidate SHA>`, preceded by the read-only identity preflight and an exact-HEAD
green CI. Isolated PostgreSQL and Redis, Clerk Development only, no Production data, no merge, no deploy.

**Cost estimate (an estimate, not a measurement).** Routing is `core/ai/model_routing.yaml`: Haiku 4.5 USD 1/5, Sonnet 4.6
USD 3/15, Opus 4.7 USD 15/75 per million input/output tokens. For four documents of 20-100 pages plus the revision B and the
rejected draft (six analyses), with the extraction, WBS/BOM generation and coherence passes, the expected range is **USD 10-40**
(most of it from the Opus-routed generation tasks), plus under USD 1 of embeddings. Recommended hard cap: USD 50 through the
tenant AI budget, and the run records `tenant_a_ai_spend` so the real figure replaces this estimate.

**Acceptance criteria (all must hold; the runner never accepts itself).**
1. HEAD, backend/worker/frontend runtime SHAs and the dispatched SHA are identical; evidence class `UAT_REAL`, not `REHEARSAL`.
2. Provider receipt: `ai_mock=false`, `worker_provider_successes >= 1`, zero provider errors, nonzero tokens, spend recorded.
3. The four pinned documents are stored with the expected SHA-256 and exactly one genesis revision each.
4. S1-S8 each `PASS` or an honestly declared `PARTIAL`; no `FAIL`/`NOT_RUN`; PostgreSQL verification all green.
5. S5: every real finding decided through the UI by the authenticated human; the approval accepted by S5-04; one resume operation
   whose authority names an active `APPROVE_CANDIDATE` grant and the reconciliation digest; the TRUSTED artifact is exactly the
   approved candidate (or its derived Vn+1 with the provenance recorded).
6. Relogin A -> B: identical persisted state and 404 in both directions.
7. A pilot-user review of the outputs (usefulness of findings, alerts and Health) recorded separately from the technical verdict;
   independent security review and S7 independent approval remain explicit open items unless they were actually performed.

## Rules

- No merge, deployment, production SQL/DDL, bypass of a human approval, or automatic change to MASTER as part of a run.
- PROPOSED is never TRUSTED: a pending document never moves a score or resolves an alert, and a verdict says so.
- Report the exact SHA, the evidence class and the run URL for every PASS; everything else is `PARTIAL` or `NOT_VERIFIED`.
