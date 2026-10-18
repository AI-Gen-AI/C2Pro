# PQ-HITL-09.1 — Golden baseline SDD and RED audit

**Task:** `PQ-HITL-09.1` (parent Product Control `PQ-HITL-09`, [#945](https://github.com/AI-Gen-AI/C2Pro/issues/945)); **GOAL:** founded source → human decisions → exact candidate → truthful product state.  
**Status:** TEST SPECIFICATION / NOT PRODUCT ACCEPTANCE; **Date:** 2026-10-08.  
**Authority:** [Product Master](../../validation/product/c2pro-master-product-control-v1.yaml) and [programme #936](https://github.com/AI-Gen-AI/C2Pro/issues/936). This bounded QA work does not create a new WBS, implement runtime fixes, change DB state or grant product trust.

## WHAT — falsifiable contract, before implementation

Freeze a deterministic, synthetic set of contract inputs/expectations with versions and explanatory negative cases, so later code changes cannot retroactively redefine success. The unit suite verifies source locators and corpus integrity. Deliberately failing behavior is **documented as xfail(strict=True)**, not misrepresented as tested/accepted. An xfail is a RED baseline, not a PASS or an automated approval.

**Scope:** 10 synthetic cases under `apps/api/tests/fixtures/pq_hitl_09_contract_golden_v1.json`, consumed by `apps/api/tests/unit/analysis/domain/test_pq_hitl_09_golden_baseline.py`. No LLM/network/real customer PDFs; where wording matches existing sample, original source is `apps/web/src/tests/e2e/test-data/pj01/contract-a.source.txt`. Otherwise text is explicitly invented synthetic negative.

| Case | Expected fixture result | Negative / forbidden inference |
|---|---|---|
| Q01 Correct §5.2 | Contractor bears cost; fourteen days after written notice; quote locates | Never call cost or deadline unspecified |
| Q02 Ordinary terms | However, Conversely, LD and valid risk title are language | Never flag placeholder/corruption merely because unfamiliar |
| Q03 Truly illegible marker | Source integrity requires human review | Never invent original unreadable obligations |
| Q04 Invented clause wording | Verifier UNVERIFIED | No Employer payment obligation from made-up quote |
| Q05 Partial excerpt | Missing quote cannot prove clause absent | No corruption/absence for incomplete source |
| Q06 Missing source | SOURCE_UNAVAILABLE | No validated Madrid forum |
| Q07 Repeated quote | AMBIGUOUS | No unique fabricated source span |
| Q08 Multi-clause §§6.1/6.3/6.4 | Distinct liability, termination and governing law evidence | Never collapse distinct legal effects into one locator |
| Q09 Injection within document | Located as untrusted text only | Never obey auto-approval instruction from source |
| Q10 Exact literal without PDF | Verified text span, page/bbox remain null | Never fabricate page geometry |

**Ancillary states:** An independent, explicitly **SYNTHETIC / NOT PJ-01** source sentence states EUR 132,500, 5% retention **of the agreed total contract value**, and 183 calendar days. The deterministic test parses those numeric values from that source before calculating EUR 6,625; none are attributed to the PJ-01 contract. 183 days is stated duration, not recalculated schedule. Confidence per finding null is NOT 0.9 just because artifact confidence is 0.9. A=9/B=7 are synthetic historical/proposed counts even when zero current TRUSTED; this corpus intentionally does not impersonate the live production rows or their IDs.

## HOW — governed test-only implementation

- **Implementation role:** QA/test author in a single branch. No runtime module, schema, frontend, source algorithm or test/CI waiver.
- **Tests always green or expected RED:** corpus validity, quote spans, clause facts, arithmetic and revision/UNKNOWN expectations. Explicit xfail(STRICT) tests demonstrate two existing implementation failures: (a) `OK` with located critic quality concern still passes on `main` (#960 draft addresses), (b) missing risk confidence is promoted to a default 0.9 (#938/#953 workload HOLD). Promotion to GREEN in future dedicated tasks must remove xfail and meet independent end-to-end checks.
- **Supported model reply contract:** RED #01.1 uses only the current `status`+`notes` fields: an `OK` answer containing a source-grounded critical concern. The existing status evaluator clears such notes; subsequent 01.1 code must fail closed. Typed `observations` have their own PR #960 tests. An unsupported field is never the sole reason for expected failure.
- **Status metrics:** number of negative cases and known RED probes. Do not invent false-positive rate or real model accuracy from deterministic fixtures. Later #09.2/.3 will measure actual end-to-end outputs and thresholds.
- **Reviewer roles:** separate principal reviewer and independent QA/security as appropriate; preserve SHA/required CI; no self-review and no fake PROD_VALIDATED.
- **Exit of 09.1:** versioned immutable synthetic fixture, 10 cases, deterministically passing *fixture/locator contract* plus documented expected RED runtime probes, exact-head CI and principal independent review. `09.1` remains `MERGED_UNACCEPTED` after a simple merge until MASTER reconciler accepts the SDD evidence.
- **Separate repairs:** #960 belongs `PQ-HITL-01.1`; #953 confidence belongs `PQ-HITL-02.2`; A9/B7 operator projection belongs `PQ-HITL-03.1`. This task is not allowed to fix them opportunistically.

## Safety constraints

No production authentication, tenant/customer data, synthetic revision B replay/approval, role grants, deploy, S2 retry or Product Control promotion. Static JSON is fixture evidence, not authority for real risk semantics. A located quotation does not prove a model's legal interpretation.

The next dependencies are product tasks `PQ-HITL-01.1`, `01.2`, `02.1`, `02.2`, `03.1`, `04.1` as individually specified. Do not substitute merge counts for the finished professional workflow.
