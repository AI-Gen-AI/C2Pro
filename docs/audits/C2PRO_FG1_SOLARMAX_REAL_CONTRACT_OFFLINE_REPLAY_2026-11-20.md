# C2Pro FG-1 — SolarMax 94-page real-contract quality gate (offline replay)

**Date:** 2026-11-20 · **Verdict: FAIL for contractual-quality acceptance of the archived real-AI result; current N4 runtime NOT VERIFIED.**

This is a reproducible offline reassessment of an **existing real Claude Sonnet CLI** N4/N12 result from November 10, **not a fresh inference** on PR #1279 and **not** evidence of a complete production journey. Do not mix with the passing **FG-1a PASS_LIMITED** result for display/auth/persistence of synthetic findings.

## Inputs and identity

| Evidence | Identity / status |
|---|---|
| PDF | `solarmax_ex991_original.pdf`, 94 pages, SHA-256 `e58a128e01348aa3c77e4a101861a6ebcdc0e303e599314c85bde3aa2ec7d63d` |
| Recovered source | 227,449 chars, 538 parser blocks, SHA-256 `388023400312a96a7b81f2ffb1cdcf843909360a8d3024d1c75489ffd1bf847e` |
| Prior executable | C2Pro CORE `fcf5bcba73c98dfa6c9890439ad87dd15f91b8a6`, *not* #1279 |
| Archived inference | `live_claude_n4_n12_result_v1.json` and `live_claude_n4_n12_verification_v1.json` in restricted QA VPS path; 15 real N4 candidates, N12 `UNASSESSED`, 5 source-cited critique observations |
| Quotation check | All 15 risk title+clause+quote hashes match the archived separate literal-verification record. They were located in the **parsed source** at the time; original PDF page mapping was **not freshly reattested** here. |
| Independent source preflight | 9 of 9 clause anchors present in the PDF by prior verifier. Pages 9, 21 and 55 gave no extracted text. Contract exhibits C/D/E needed for cross-document verification are absent. |
| New provider activity | 0 calls; **$0 newly spent**; no PG writes, no approvals, no HITL, no Score changes |
| Restricted VPS report | `/home/aigenadmin/qa_evidence/solarmax-real-pdf-20261110/fg1_offline_oracle_reassessment_20261120.json`; SHA-256 `1b37a03f327cf3348d3818bc1ed2b8fac73ef1b0bc5a5e04232e49b60f267a6a` |

The prior Sonnet CLI execution incurred $0.81899 when run on November 10; this is **historical**, not a cost of today's validation. It used a full-source `RiskExtractionTool` and is not the current compact-window production N4 bridge.

## Clause-level outcome (11 focal gates, not a recall denominator)

| Gate | Actual source | N4 archived outcome | Reason for qualification |
|---|---|---|---|
| SM-01 | p76 §9.6 | **PARTIAL** | N4 description flags `ten percent (5%)`, but its own quoted evidence omits the contradiction. N12 identifies the gap. |
| SM-02 | p36 §2.5.5 | **PARTIAL** | N4 description contains daily LDs $5k/$10k/$20k and cap, but its quote omits rates/cap; N12 flags this. |
| SM-03 | p35 §2.5.1 | **NOT ATTESTED** | No direct N4 finding on guaranteed completion dates in Exhibit C-1; §1.3 generic exhibit risk does not substitute. |
| SM-04 | p52 §3.1 | **DETECTED / NOT CERTIFIED** | Price USD 122,350,571 and change orders identified in analysis; no independent legal/materiality sign-off. |
| SM-05 | p52 §3.2.1 | **NOT ATTESTED** | No direct N4 finding concerning the payment milestone Table D-2 dependency. |
| SM-06 | p70 §8.2 | **DETECTED / NOT CERTIFIED** | Liability cap and fraud, third-party and insurance carve-outs cited; interpretation remains unassessed by expert. |
| SM-07 | p81 §12.1.1 | **INDIRECT** | N4 §12.1.5 warranty entry is not direct evidence of §12.1.1 scope. |
| SM-08 | p92 §14.14.1 | **NOT ATTESTED** | No direct confidentiality-clause finding. |
| SM-09 | p76 §9.6 | **PARTIAL / NOT ATTESTED** | 2% demobilization cap present in interpretation but absent in the corresponding literal evidence. |
| SM-10 | p9/p21/p55 | **SAFETY FLAGGED** | Three text-empty PDF pages; N12 remains UNASSESSED. No false full-coverage claim. |
| SM-11 | Exhibits C/D/E | **SAFETY FLAGGED** | Missing independent schedule/budget/technical annexes. No cross-document inference certified. |

**Other material missing direct N4 candidates** found by N12: §4.3.1 (Outside NTP / automatic termination / LD 5% under conditions) and Article 13 (insurance obligations and financial limits). N12 observations are not trusted findings or approvals.

### Gate verdict and limits

**FAIL / do not accept contract quality.** At least **three directly checkable source obligations** have no direct N4 reference (SM-03, SM-05, SM-08); others have insufficient quotation coverage. Additional material terms (§4.3.1 and Art. 13) are absent as direct N4 candidates, despite N12 identifying them. The two correct safety abstentions are necessary but cannot compensate for these omissions.

This is a **focused, non-exhaustive benchmark**; it does **not** estimate general N4 precision/recall or prove how a different prompt/model behaves. A literal quote proves a source match, **not** that the risk is correct, complete or financially quantified. There was **no** fresh verification of page coordinates against the binary in this replay and **no** adjudication by an independent EPC contract specialist.

## Relationship to VS-1 and next acceptance gate

- FG-1a [#1279](https://github.com/AI-Gen-AI/C2Pro/pull/1279) PASS_LIMITED on 2026-11-20 demonstrates *display/auth/API/PG* **for synthetic candidates**. It does not cure N4 extraction omissions.
- **Stop scope expansion**. Fix or assess the small number of known semantics/evidence gaps in the N4 prompt/output contract without replacing the engine solely because the framework is different.
- A **new production-path N4 quality test** still needs the current compact-window bridge, revision-pinned source, page-accurate citations, independent oracle/held-out contract, verified cost authorization and tenant-isolated test environment. Only then can N12 and cross-document claims be evaluated.
- Preserve `N4_BILLABLE=STOP`, `N12_BILLABLE=STOP`, `MERGE=STOP`, `UAT_DEPLOY=STOP` until the relevant owner/CORE gates are explicitly lifted. The current offline replay **does not change** those decisions.
