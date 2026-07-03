# C2Pro — Consensus Committee Review

**A meta-review of 7 synthesis reports (ChatGPT, Gemini, GLM-5.1, Kimi, Kimi-Perplexity, Claude, Grok), under strict evidence-first rules.**

**Date:** 14 June 2026 **Committee standard:** A claim is not true because reports repeat it. Every load-bearing claim is graded **VERIFIED / PROBABLE / PLAUSIBLE / SPECULATIVE / REJECTED**. **Committee's unfair advantage:** This board re-cloned the repository in full this session (`git fetch --unshallow`, 740 commits) and checked the contested claims against code. Where a report and the code disagree, the code wins. **Mandate compliance:** Per the committee rules, this document performs _consensus formation, not roadmap generation_. **No final roadmap is produced.** Candidate items are listed with evidence strength only (Phase 5).

> **Headline correction that reframes the whole exercise.** Multiple syntheses built conclusions on the claim that the repo was _re-initialized in May 2026 with 225K LOC in one month_ ("AI-velocity debt", "impossible manually → re-init"). **This is REJECTED by evidence.** True history: first commit **2025-12-29**, continuous, **90 commits in the first 30 days**, 740 total. The "1 month / 121 commits" figure originated in Claude's _first_ report (a `--depth 50` shallow-clone artifact) and propagated because reports deferred to "Claude had the full clone." This is the committee rules' central warning made flesh: **authority is not evidence.** GLM-5.1's "Jan 2026 / ~6 months" was correct and was wrongly flagged by others as a possible hallucination.

---

## Phase 1 — Report Quality Assessment

Scores are 1–5 (5 = best); **Hallucination Risk** is inverted (5 = highest risk). These grade the **synthesis** documents, not the original first-pass reports.

|Synthesis|Evidence|Repo Aware|Tech Depth|Arch Rigor|Product|Security|Actionability|Halluc. Risk|
|---|--:|--:|--:|--:|--:|--:|--:|--:|
|**GLM-5.1**|5|5|4|4|4|4|5|1|
|**Claude**|5|5|4|4|3|5|4|2|
|**Kimi-cloud**|4|4|4|4|4|4|5|2|
|**Kimi-Perplexity**|4|4|3|3|4|4|4|2|
|**Gemini**|3|3|3|3|4|4|4|3|
|**ChatGPT**|4|4|5|4|5|4|4|2|
|**Grok**|2|2|2|2|3|2|3|3|

**Per-report notes (strongest / weakest / unique):**

- **GLM-5.1 — strongest synthesis overall.** _Strong:_ per-report scorecards; a "claims requiring verification" table _with shell commands_; correctly resolves AI-Design (Kimi 3 vs ChatGPT 6.2 → ~5) and Security (4 beats 7). _Weak:_ recommends consolidating toward **`modules/coherence`** — **backwards** (the canonical, actively-developed engine is `src/coherence/`; `modules/` is legacy feeding `analysis/`). _Unique:_ the cleanest evidence-tiering discipline of the set.
- **Claude — strong, and the only synthesis that self-corrected its own prior error** (opened with a §0 retraction of 121→740). _Weak:_ thin on go-to-market; the correction did **not** propagate to peers, who cited Claude's _uncorrected first report_. _Unique:_ the schedule-leg bug (`TASK-BCK-064` → product is bi-dimensional) and "honest-null as moat."
- **Kimi-cloud — most thorough, well-organized.** _Strong:_ explicit per-report reject lists; correctly resolves the "engine exists" contradiction in Claude's favour. _Weak:_ **propagated the re-init error** ("225K LOC in 1 month is impossible → re-init") and flagged GLM's _correct_ Jan-2026 date as "POSSIBLE HALLUCINATION." _Unique:_ sharpest articulation of the metric-dependent completeness split (backend 70% / product-value 40% / enterprise 20%).
- **Kimi-Perplexity — good evidence-tiering with citations** (though the cited S3 URLs are expired/broken). _Weak:_ **propagated re-init**; could **not retrieve Gemini's content** ("contenido completo no recuperado") yet still synthesized — a transparency plus but a coverage gap. _Unique:_ explicitly labels which findings are "verifiable in code" vs "verified in backlog."
- **Gemini — dramatic turnaround.** Its first-pass hallucinated a different product; its **synthesis self-flags that failure** ("evalúa el proyecto equivocado") and is competent. _Weak:_ presents unverified specifics as hard evidence — e.g. "**500s active in production** = evidencia dura" (it's a backlog item with log-correlation blocked) and prescribes a Clerk `set_config('request.jwt.claims')` auth fix **as if verified**. _Unique:_ the only synthesis to draw an explicit phased architecture diagram.
- **ChatGPT — deepest technical/product content, but it did not actually synthesize.** Its "synthesis" is its **first report recycled verbatim** (same "738 commits / 1 star" line, same scorecard). _Strong:_ the richest verified findings (CI `continue-on-error`, ISC license, `SKIP_HITL`, synthetic-clause model, Evidence-Graph framing). _Weak:_ a meta-task failure (no cross-report reconciliation); overstates "coverage is meaningless" (it's `0` in 2 places, but 70 in 5 and 90 in 2). _Unique:_ "Evidence Graph Platform" target architecture.
- **Grok — thinnest and least rigorous** (1,184 words). _Strong:_ correctly flags "monolithic = Speculative" (good epistemic caution). _Weak:_ keeps its first-pass "Security 8.5/10" then "compromises" to 6.5 without engaging the leaked `service_role` key; repeats the false "single-model, no fallback." _Unique:_ the only one to explicitly average toward a mid security score as a negotiated compromise (a process the committee rejects — compromise is not evidence).

---

## Phase 2 — Cross-Report Comparison

### Universal Agreement — Confidence HIGH (multiple reports **and** repo evidence)

|#|Finding|Committee grade|
|---|---|---|
|1|`.env.staging` committed with real `service_role` + JWT secret + DB URL (history `cc9d080`)|**VERIFIED**|
|2|Repo hygiene is a red flag: `.mypy_cache` (1,418 files ≈29%), temp dirs, transcripts, HVPNL PDF, dual lockfile|**VERIFIED**|
|3|License is incoherent: `package.json`=ISC, README=Proprietary, no `LICENSE` file|**VERIFIED**|
|4|Bus factor = 1 (one human + heavy AI-agent co-dev: 114 commits authored by "Claude")|**VERIFIED**|
|5|Not investable / not production-ready _as-is_|**VERIFIED** (judgement on verified facts)|
|6|Coherence Score is the product's differentiator and most-engineered component|**VERIFIED**|
|7|Backend more mature than frontend; observability not wired (Sentry DSN absent)|**VERIFIED**|
|8|Architectural duplication (two `core/`, two `ai/`, `coherence/` vs `modules/coherence/`, two migration systems)|**VERIFIED**|

### Emerging Consensus — Confidence MEDIUM (multiple reports, partial evidence)

|#|Finding|Committee grade / caveat|
|---|---|---|
|9|v1→v2 coherence cutover incomplete; shadow-mode burns tokens|**PROBABLE** — shadow infra confirmed; exact % and current cost unmeasured|
|10|Reposition as "Contract-to-Procurement Intelligence"; moat = Evidence Graph + domain, not the LLM|**PROBABLE** (strategy, not a repo fact)|
|11|**"No AI eval framework / prompt registry"**|⚠️ **PARTIALLY REJECTED** — `evals/` + `run_evals.py` + **100-case golden corpus** + `golden-corpus-evals.yml` CI **exist**. Real gap is narrower: prompt _versioning_/A-B and whether evals gate accuracy. A near-unanimous claim the code contradicts.|
|12|Live 500s on alerts/stakeholders (`TASK-BCK-051`)|**PROBABLE** — in backlog as P0; "currently active in prod" is **unverified** (log access was blocked)|

### Significant Disagreements

**D1 — Commit count / repo age.** _A (ChatGPT/GLM):_ 738 / ~6 months. _B (Claude-first, propagated):_ 121 / 1 month / re-init. **Evidence:** full history = **740, from 2025-12-29, continuous.** **Committee: Lean A (resolved).** B is REJECTED.

**D2 — Does the coherence engine exist?** _A (everyone except Kimi):_ yes, sophisticated. _B (Kimi):_ "theoretical / unimplemented." **Evidence:** `scoring.py` (897 LOC, exponential-decay, floor/ceiling, source-weighting). **Committee: Lean A (resolved).**

**D3 — AI-Design score.** _A (GLM 8 / Claude 7):_ strong. _B (Kimi 3):_ weakest area. **Evidence:** engine is strong; prompt-versioning/A-B genuinely thin; evals exist (100 cases). **Committee: ~6.5/10 for the shipping engine; ~4/10 for the deferred multi-agent platform.** Lean A.

**D4 — Security score.** _A (Kimi/GLM/Grok 7–8.5):_ good practices (RLS/PII/42 tests). _B (Claude/ChatGPT 4–4.7):_ a committed `service_role` key caps it. **Committee: Lean B —** a live god-key is disqualifying until rotated; **4/10 now, ~7/10 after rotation+purge.**

**D5 — Investable today?** _A (majority: no)._ _B (Gemini/GLM/Grok: conditionally yes)._ **Committee: Lean A.** Dissent preserved: B is defensible _only_ re-defined as "pre-seed on founder-market fit," not institutional.

**D6 — LLM cache tenant isolation.** _A (ChatGPT):_ cache excludes tenant → cross-tenant leak risk. _B (committee finding):_ `cache_keys.py` + `cache_invalidation.py` reference tenant (PR #151 namespacing). **Committee: Undecided, leaning B for the coherence path** — the content-hash LLM cache may still be a separate question. Needs a 15-min code trace.

**D7 — Frontend maturity.** _A (Kimi):_ "shell, no routes." _B (Claude):_ 52.7K LOC, 34 routes. _C (GLM):_ "30% complete." **Committee: Lean B for _existence_ (not a shell), Lean C for _completeness_.** A is REJECTED.

**D8 — Checkpointer in-memory fallback.** _A (ChatGPT/GLM/Claude):_ silent degradation risk. **Evidence:** `MemorySaver` fallback **VERIFIED** in `analysis/.../workflow.py` — but gated on "SQLite / postgres pkg missing." **Committee: mechanism VERIFIED; production data-loss impact Undecided** (depends on deploy config). _Minority charitable read preserved:_ it may be a benign dev/test path, not a prod risk.

---

## Phase 3 — Hallucination Audit

|Claim|Source report(s)|Risk|Reason / committee finding|
|---|---|---|---|
|Repo "re-initialized May 2026; 225K LOC in 1 month"|Claude-first → Kimi-cloud, Kimi-Perplexity|🔴 High|**REJECTED.** Continuous history from 2025-12-29; 90 commits in first 30 days.|
|"No eval framework / `evals/` empty"|Kimi, Kimi-Perplexity|🔴 High|**REJECTED.** 100-case golden corpus + `run_evals.py` + CI eval workflow exist.|
|"Single-model dependency, no fallback"|Kimi, Grok|🟠 Med|**Misleading.** A model router exists (`MODEL_ROUTER_USAGE.md`). Provider _failover_ may still be absent — narrow that to "no failover."|
|"Cache excludes tenant → cross-tenant leak"|ChatGPT|🟠 Med|**Likely outdated.** Coherence cache keys/invalidation reference tenant (PR #151).|
|"500s active in production = hard evidence"|Gemini-synthesis|🟠 Med|**Overstated.** Backlog P0; live status unverified (log access blocked).|
|Auth fix prescribed as fact: Clerk via `set_config('request.jwt.claims')`|Gemini-synthesis|🟡 Low-Med|**Assumption chain.** Plausible architecture, presented as verified. Auth canonical (Clerk vs Supabase) is itself unresolved.|
|Original "Command & Control agent-OS / WASM / Temporal / agent mesh"|Gemini-first|🔴 High|**REJECTED** (wrong product). _Note: Gemini's synthesis already retracted this._|
|"738 commits, 1 star, 0 forks"|ChatGPT|🟢 Low|Commit count VERIFIED (≈740); star/fork are web-scraped, not repo facts.|
|"Any GPT-4+LangChain dev replicates in 2 weeks"|Kimi|🟡 Low-Med|**Speculative / probably wrong** — discounts 27 deterministic evaluators + domain model + ADR-009.|
|Consolidate toward `modules/coherence`|GLM-synthesis|🟡 Low|**Backwards.** Canonical is `src/coherence/` (recent commits, wired in `main.py`).|
|TAM "$12B / $15B / $50B"|Gemini, Kimi, GLM, others|🟡 Low|**Speculative.** No market study; do not use as planning input.|

### Recommendations To Discard (must not drive planning)

1. The **"re-initialization" framing** — factually false; it distorts the technical-debt narrative.
2. **Gemini-first's distributed-agent-OS stack** (WASM sandbox, Temporal, agent mesh, race-condition fixes) — wrong product.
3. **GLM's "consolidate toward `modules/`"** — invert it; `coherence/` is canonical.
4. **Gemini's prescribed Clerk auth migration** — unverified; the auth direction is an open question, not a settled fact.
5. **All TAM figures** as inputs to prioritization.
6. **"Defer Gates 6–8 until after PMF"** (Kimi-first) — security/observability are pilot prerequisites; the synthesizers already rejected this and the committee concurs.
7. **Negotiated/averaged scores** (Grok's "compromise to 6.5 security") — compromise is not evidence.

---

## Phase 4 — Confidence-Based Findings

### Tier 1 — High Confidence (verified this session; should drive decisions)

- `.env.staging` real secrets in history (`service_role`, JWT, DB).
- Hygiene debt: `.mypy_cache` 1,418 files, temp dirs, 10 transcripts, HVPNL PDF, dual lockfile.
- License contradiction (ISC vs Proprietary vs no `LICENSE`); no `SECURITY.md`.
- CI `continue-on-error: true` (3 workflows) + `cov-fail-under=0` (2 places; 70/90 elsewhere).
- HITL/mock bypass flags `C2PRO_SKIP_HITL` / `C2PRO_AI_MOCK` present.
- Bus factor 1 + 114 commits authored by "Claude"; history continuous from 2025-12-29 (740 commits).
- Coherence engine is real and sophisticated (`scoring.py`, 897 LOC).
- **Schedule dimension does not feed scoring** (`TASK-BCK-064`) → product is currently **bi-dimensional**.
- **Celery worker + API run in the same container** (`start.sh`, explicit comment) — VERIFIED.
- **Checkpointer `MemorySaver` fallback exists** (`analysis/.../workflow.py`) — VERIFIED (impact = Tier 2).
- Dead modules `gamification/`, `golden/` (0 refs in `main.py`); `procurement/` wired-but-flagged.
- **Eval harness + 100-case golden corpus exist** (contra the "no evals" consensus).
- Frontend is real: 52.7K LOC, 34 routes (not a shell); maturity uneven.

### Tier 2 — Medium Confidence (needs validation before it drives decisions)

- Does the `MemorySaver` fallback trigger in **production**, or only dev/SQLite? (deploy-config dependent)
- Is the **content-hash LLM cache** tenant-isolated, or only the coherence cache? (cross-tenant correctness)
- Are the alerts/stakeholders **500s live right now**? (`TASK-BCK-051`, log access was blocked)
- Exact **v1→v2 cutover %** and current shadow-mode token cost.
- **Canonical auth**: Clerk vs Supabase (both present).
- **Quality** of the 4,574 Python tests (count ≠ coverage value).
- Whether the **golden corpus actually measures coherence accuracy** vs structural correctness.

### Tier 3 — Low Confidence (interesting, unproven; preserve, don't act)

- _Minority, credible:_ the higher-value buyer is the **lender/insurer**, not the contractor (Kimi).
- _Minority, credible:_ 3-D coherence is fundamentally a **graph problem**, not an LLM problem (Kimi) — relevant to a future v3, not now.
- Coherence Score as an **industry standard / API / MCP server**; **data flywheel** moat.
- **EU patent-forfeiture** impact of public disclosure (legal inference; not adjudicated).
- Blackboard pattern / skill-registry as **extractable products** (Kimi-Perplexity).

---

## Phase 5 — Candidate Roadmap Items (NOT a roadmap)

Items graded by evidence strength only. **No sequencing, no commitment** — per mandate.

|Candidate item|Evidence strength|Impact|Effort|Confidence|
|---|---|---|---|---|
|Rotate + purge `.env.staging` secrets|**VERIFIED**|Critical|Low|High|
|Remove HVPNL PDF from history|**VERIFIED**|High|Low|High|
|De-junk repo (caches/temp/transcripts/lockfile)|**VERIFIED**|Med|Low|High|
|Resolve license + add `LICENSE`/`SECURITY.md`|**VERIFIED**|High|Low|High|
|Wire schedule into scoring (`TASK-BCK-064`)|**VERIFIED (bug in own backlog)**|Critical|**Unknown (bug vs redesign — see Q1)**|High on need, low on effort|
|Block `SKIP_HITL`/`AI_MOCK` in prod|**VERIFIED (flags exist)**|High|Low|High|
|Split Celery into its own container|**VERIFIED (`start.sh`)**|High|Med|High|
|Remove `continue-on-error` on real gates; raise `cov=0`|**VERIFIED**|Med|Low|High|
|Consolidate engines toward **`coherence/`** (retire `modules/`)|**VERIFIED (duplication)**|High|High|Med (coupling to `analysis/`)|
|Wire Sentry / observability|**VERIFIED (absent)**|High|Low|High|
|Remove dead `gamification/`+`golden/`|**VERIFIED**|Low|Low|High|
|Add provider failover (multi-LLM)|**PARTIAL** (router exists, failover unclear)|Med|Med|Med|
|Tenant-scope the content-hash LLM cache|**PLAUSIBLE**|High-if-real|Low|**Validate first**|
|Prompt registry / versioning + A-B|**PROBABLE (genuine gap)**|High|Med|Med|
|Fail-closed checkpointer in prod|**PLAUSIBLE**|High-if-real|Low|**Validate first**|

### Items Requiring Validation Before Entering Any Roadmap

- **Anything premised on the checkpointer prod-fallback or the cache cross-tenant leak** → confirm at code/runtime first; both may already be benign.
- **The deferred multi-agent platform** (RACI/RFQ/procurement/WBS flows) → schema-coupled to `analysis/`; needs an explicit _freeze-vs-migrate_ ADR before any work.
- **Auth consolidation direction** → do not pick Clerk-vs-Supabase until the active path is confirmed.
- **All product/GTM bets** (ICP, pricing, integrations, MCP) → Product Discovery, not engineering planning.

---

## Phase 6 — Expert Committee Review

**CTO** — _Agrees:_ the Tier-1 P0s are unambiguous; the bones are good. _Challenges:_ "not production-ready" is right, but the reports conflate _verified_ blockers (secrets, schedule-bug) with _unverified_ ones (prod fallback, live 500s). _Needs:_ one runtime trace + the deploy config. _Prioritizes:_ secrets purge, then schedule-bug, then container split.

**Principal Engineer** — _Agrees:_ dual-generation architecture is the core debt. _Challenges:_ GLM's "consolidate toward `modules/`" — it's backwards; and "no evals" is false. _Needs:_ import graph from `analysis/` → `modules/` to scope the migration. _Prioritizes:_ the freeze-vs-migrate ADR before any consolidation code.

**Product Lead** — _Agrees:_ the schedule-leg bug makes the headline claim false today — credibility risk in every demo. _Challenges:_ every TAM number; the "industry standard" framing. _Needs:_ 3 design-partner conversations and a willingness-to-pay signal. _Prioritizes:_ making "tri-dimensional" true, then a synthetic-doc demo.

**Security Lead** — _Agrees:_ the leaked `service_role` key is disqualifying; 4/10 until rotated. _Challenges:_ the "good practices → 7/10" scores that ignore the incident; also the "cross-tenant cache leak" stated as fact. _Needs:_ confirmation the cache and RLS hold at runtime; whether the repo is currently public (patent + exposure). _Prioritizes:_ rotate→purge→gate, then cache/RLS runtime test.

**AI Systems Architect** — _Agrees:_ the engine (honest-null, exponential decay, 27 evaluators, 100 golden cases) is genuinely differentiated. _Challenges:_ Kimi's 3/10 and "no RAG/evals" — refuted by code. _Needs:_ the golden corpus's _accuracy_ numbers (does it measure coherence quality or just structure?). _Prioritizes:_ prompt versioning + wiring evals as a blocking gate.

---

## Phase 7 — Questions for Repository Verification (max 15)

Smallest set that resolves the most remaining uncertainty (many earlier questions are already answered above).

1. **`TASK-BCK-064`: is the schedule-into-scoring gap a wiring bug (hours) or an ingestion redesign (weeks)?** — gates the entire "make it tri-dimensional" timeline.
2. **Is the GitHub repo currently public?** — one bit; instantly sets the EU-patent urgency and exposure scope.
3. **Were the `.env.staging` credentials live-prod or a discarded test env?** — sets rotation urgency vs full breach investigation.
4. **Does the `MemorySaver` checkpointer fallback trigger under the production deploy, or only dev/SQLite?** — decides if it's a P0 data-loss risk or a non-issue.
5. **Is the content-hash LLM cache tenant-isolated at runtime?** — decides if there's a real cross-tenant correctness/leak bug.
6. **Are the alerts/stakeholders 500s reproducible in the current build?** — confirms/closes `TASK-BCK-051`.
7. **What % of scoring traffic still flows through v1, and what is shadow-mode's monthly token cost?** — sizes the cutover and the bleed.
8. **Which auth path is actually active end-to-end — Clerk or Supabase?** — unblocks identity/SSO decisions.
9. **Does the 100-case golden corpus measure coherence _accuracy_ (precision/recall vs ground truth), or only structural/schema correctness?** — sets the true AI-reliability score.
10. **Does `analysis/` import `modules/` in ways that block retiring `modules/coherence/`?** — scopes the consolidation.
11. **Is HVPNL a real client relationship (NDA) or a test fixture?** — confidentiality vs hygiene.
12. **Is there an IP-assignment/vesting agreement covering all (human + agent-driven) contributions?** — investment prerequisite.

---

## Phase 8 — Consensus Maturity Score

|Area|Committee Confidence|
|---|--:|
|Architecture (structure understood; duplication & canonical engine confirmed)|**80%**|
|Product (problem clear; the headline claim is provably incomplete today)|**55%**|
|Security (posture understood; one verified critical, several runtime unknowns)|**65%**|
|AI Design (engine verified strong; accuracy of evals unmeasured)|**60%**|
|Maintainability (debt well-characterized)|**80%**|
|Scalability (one verified anti-pattern; no load evidence)|**45%**|
|Roadmap (P0 track clear; product/scaling track unvalidated)|**40%**|

### Overall Consensus Confidence: **62%**

Rationale: the **facts** are now high-confidence (Tier 1 is largely verified), but several **operational/runtime** behaviours and the **product direction** remain open, capping aggregate confidence in the low-60s.

---

# Final Output

## What We Know (verified)

A continuously-developed (~5.5-month, 740-commit), solo-plus-AI-agent codebase with a genuinely sophisticated coherence engine, a real frontend, a 100-case eval harness, and multi-tenant RLS — undermined by a **committed live `service_role` key**, **~29% cache-file repo bloat**, an **incoherent license**, a **schedule dimension that doesn't reach the score** (so "tri-dimensional" is currently false), **Celery+API in one container**, **HITL bypass flags**, and **dead/duplicated modules**.

## What We Think We Know (probable, unverified)

The v1→v2 cutover is incomplete and shadow-mode bleeds tokens; the checkpointer falls back to memory and the content-hash cache _may_ not be tenant-isolated (both **possibly benign — must check**); there are/were live 500s on two endpoints; the real moat is the evaluator/domain IP, not the LLM.

## What We Do Not Know Yet (critical unknowns)

Whether the schedule fix is hours or weeks; whether the repo is public (patent clock); whether the fallback/cache issues are real in prod; the **actual coherence accuracy** of the engine; the canonical auth path; and any market/willingness-to-pay signal.

## What Must Be Verified Next (highest priority)

(1) One **end-to-end runtime trace** on a representative EPC document set — it resolves Q4–Q6 and Q9 simultaneously. (2) The binary **"is the repo public?"** (3) The **`analysis/`→`modules/` import graph** to scope consolidation.

## Committee Verdict

**→ Requires Runtime Investigation** (with **Product Discovery** as a co-requisite for the strategy layer).

**Justification.** The committee deliberately distinguishes two tracks. The **verified P0 remediation track** (rotate/purge secrets, de-junk, fix license, fix the `TASK-BCK-064` schedule bug, split Celery, harden CI, wire Sentry, kill dead modules) rests entirely on Tier-1 evidence and is **already ready for detailed planning** — it does not need more investigation. But the committee **cannot responsibly green-light the product or scaling roadmap** without runtime evidence: the highest-severity _open_ risks (prod checkpointer fallback, cross-tenant cache behaviour, live 500s) and the single most important _strategic_ number (the engine's actual coherence accuracy) are all **runtime properties**, not static-code properties — and the static-code questions that _could_ be answered have largely been answered this session. Choosing "Ready for Detailed Planning" outright would manufacture false certainty about operational and market reality; choosing "Requires Code-Level Investigation" would understate how much code-level work is already done. Runtime + discovery is the honest binding constraint.

---

# Consensus Delta

**The single piece of new evidence that would most increase committee confidence:** a **logged, end-to-end runtime trace of one real (anonymized) EPC evaluation** — upload → parse → extract → score → render — captured with the production-equivalent config. One such trace would, in a single stroke, resolve the largest cluster of Tier-2 unknowns: whether the **schedule dimension contributes**, whether the **checkpointer falls back to memory** under real conditions, whether the **cache isolates tenants**, whether **500s occur**, and — most valuably — what the engine's **actual coherence output and accuracy** look like on a real document rather than a fixture. That trace would move Product, AI-Design, Security, and Scalability confidence simultaneously, lifting overall consensus confidence from ~62% toward the ~85% needed to commit a real roadmap.

_One-bit adjunct of disproportionate value:_ confirming **whether the repository is currently public**, which instantly settles the EU-patent-urgency question that three reports raised but none could resolve.

---

_This committee review assessed 7 synthesis documents against a full re-clone of the repository performed this session. Its central methodological finding is that several syntheses propagated a verification error by deferring to apparent authority ("Claude had the full clone") rather than to evidence — the precise failure mode the committee rules were written to prevent. The error has been corrected here against ground truth._