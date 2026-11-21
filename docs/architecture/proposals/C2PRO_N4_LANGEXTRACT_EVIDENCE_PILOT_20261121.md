# C2Pro N4 ↔ LangExtract — isolated evidence-bridge pilot (2026-11-21)

**Status: DRAFT / EXPERIMENTAL / NO PRODUCT DEPLOYMENT.**  
**Parent:** N4-only PR #1276 → VS-1 PR #1279 → per-document scope PR #1283.  
**Source:** proprietary 38-page ABB supply agreement, original PDF SHA256
`ce332621c0754642c3332c8130f372471306d9d5c013d0d40b455fd7713b77aa`.
The complete source, model prompts, quotes and outputs remain private on the AI-GEN VPS.
Only non-confidential aggregate evidence and synthetic tests are published here.

## Hypothesis and architecture

LangExtract 1.7.2 can provide independently located, source-offset-bearing
contractual spans. **N4 still reads the entire supplied source window** to
interpret risks, including exceptions outside the extracted spans. The evidence
bridge can either:

1. Attach verified LangExtract spans to an already completed N4 response
   without spending another inference; or
2. For an N4 quote that did not match the exact source, optionally supply
   LangExtract's **non-exhaustive evidence index** in ONE further N4 prompt
   after explicit budget/operator checks.

Neither the sidecar nor the index validates risk semantics. Textual co-location
does not prove entailment. They do **not** modify the canonical N4 provider
ledger, project source, citations, HITL state or Coherence Score.

### Implementation

- `apps/api/src/analysis/application/n4_langextract_evidence_pilot.py`:
  strictly validate LangExtract source offsets and verbatim correspondence,
  build a complete bounded evidence index without top-N pruning, join N4
  source quotes to unique physical spans, and distinguish
  `EXACT_SOURCE_MATCH`, `WHITESPACE_REFLOW_MATCH` and
  `LAYOUT_REFLOW_MATCH_UNVERIFIED`.
- `advise_evidence_index_reprompt()` is an **advisory**, not an automatic
  invocation: with all quotes exact, the recommendation is `SIDECAR_ONLY`.
  It never charges, retries or changes an existing extraction.
- `apps/api/tests/unit/analysis/test_n4_langextract_evidence_pilot.py`:
  synthetic-only checks for invalid offsets, tampered text, ambiguity,
  layout masks, missing/malformed quotes, no silent top-N truncation and
  immutable trust status.
- Optional source layout intervals must be produced and checked by the caller,
  never inferred from a model. The pilot uses page-marker/header text obtained
  from the original PDF extraction. A layout-reflow match is explicitly
  **UNVERIFIED** and cannot become an N4 literal citation automatically.

## Real ABB observations — identical article text and same model family

Both historical N4 and LangExtract generations used the OpenCode
`deepseek-v4.1-flash-free` route. The new bridge replays those genuine
LangExtract annotations and makes a fresh N4 model call only when requested.
No synthetic contract replaced the ABB in the functional experiment.

| Metric | Article 7 baseline N4 | Article 7 + evidence-index N4 | Article 28 baseline N4 | Article 28 + evidence-index N4 |
|---|---:|---:|---:|---:|
| N4 hypotheses | 6 | 7 | 10 | No usable result |
| Exact quotes accepted by strict N4 parser | 0/6 | 6/7 | 10/10 | Not assessed |
| All N4 quotes uniquely located after authorized *layout-only* reflow | 6/6 | 7/7 | 10/10 | Not assessed |
| Independently anchored LangExtract spans | 4 | 4 (reused) | 7 | 7 (reused) |
| N4 hypotheses co-located with ≥1 LangExtract span | 4/6 | 4/7 | 10/10 | Not assessed |
| N4 model duration | ~26 s | ~32 s | ~51 s | Timeout after 155 s |

**Key finding A:** In Article 7 the evidence index improved literal N4 quoting
from 0/6 to 6/7. The remaining quote straddles a physical PDF page footer/
header. It is lexically located after removal of verified layout artifacts
but must not be silently promoted to an exact citation.

**Key finding B:** Two of six baseline Article 7 risk hypotheses had **no
LangExtract co-located span**. Filtering N4's input to LangExtract results
would therefore risk omitting material content. The full source stays in N4.

**Key finding C:** In Article 28 N4 already had 10/10 exact citations; the
optional index-triggered second generation timed out at 155 seconds.
**Defaulting to two inference calls is not justified.** Reuse existing N4
output and attach LangExtract spans as sidecar-only when all quotes are exact.

These are partial functional measurements, NOT quality acceptance. More
hypotheses may reflect duplication; a literal span does not prove that the
risk interpretation is legally correct, complete, material, or unique.

## Decision / promotion criteria

**Recommendation: SELECTIVE EVIDENCE SIDECAR, NOT MANDATORY CHAINING.**

- Keep original full-window N4 analysis and its explicit limitation/exceptions.
- Validate LangExtract offsets against immutable original source with page
  provenance; never accept a normalized quote as if it were literally copied.
- If N4 quotes are already exact: **do not rerun N4**, attach LangExtract
  structured facts for review and potential UI references only.
- If N4 quotes are unverified: show the discrepancy and allow at most one
  separately authorized, budgeted evidence-index prompt. Never auto retry
  uncertain provider receipts.
- Preserve **all** original N4 risk hypotheses even if LangExtract finds
  no matching span; flag them for review rather than dropping them.
- Before product integration: exercise all 38 contract pages and annexes,
  independently adjudicate semantic precision/recall against a held-out gold
  set, check cross-page source-to-PDF mapping, runtime versioning, cost/latency,
  N12 handling and UI user-visible citations.
- **No UAT deployment, product migration, HITL approval, score change or
  assertion of full ABB contractual recall** follows from this experiment.

## Local-only evidence

Private location:
`/home/aigenadmin/aigen-hybrid-pilot/private-n4-quality/abb-005a-20261121/n4_langextract_integrated_20261121/`.

Source provenance and raw provider responses are restricted; do not publish
contract text, signatories, identity numbers or raw prompt files to GitHub.
