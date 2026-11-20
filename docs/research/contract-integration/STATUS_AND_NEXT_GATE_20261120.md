> **Actualización B2 — 20/11/2026:** LangExtract **ya fue ejecutado con LLM real en el VPS**, dentro de `lx.extract()`, usando NVIDIA Nemotron 3.5 Bolt, dos ventanas originales N4 y dos pasadas con segmentación interna. **16 llamadas lógicas, 141 candidatos, 80 citas literales exactas; segunda pasada: +26 candidatos, solo +1 span exacto único y +20.705 tokens.** No equivale a *recall* ni a un comparador N4 v2 con el mismo modelo. [Informe B2](B2_VPS_REAL_LANGEXTRACT_NATIVE_20261120.md). Se conserva todo en rama experimental sin merge, UAT ni producción.

# C2Pro Contract Intelligence — I-C01/I-C02 integration checkpoint

Date: 2026-11-20. Status: OPTIONAL ADAPTERS IMPLEMENTED AND TESTED. N4/N12 SEMANTIC ACCURACY NOT PROVEN.

## Workstream boundary
Contracts are now an independent integration effort, separate from MPXJ schedules and from the historical private-file classification work. No personal or historical project document is required for this implementation stage. The source branch is based on main SHA 299aaf19, not the currently active pilot SHA 916808c5 (#1276). No merge, production upload, or API activation.

## Implemented
1. Docling structural candidate adapter at apps/api/src/documents/adapters/parsers/docling_contract_candidate_adapter.py: immutable PDF SHA check, project/tenant/document/revision scope, text/table/cell extraction with page/bbox provenance, explicit missing coverage and candidate-only status.
2. Source-conserving bounded window packet at apps/api/src/documents/adapters/parsers/docling_contract_window_packet.py: keeps every parsed source character, separates different text items, records source offsets and pages, marks split text and unverified reading order.
3. Tests: 12 + 10 unit tests PASS. Actual local Docling 2.151.1 on synthetic 2-page contract: PASS, five anchored items, two 512-char windows and 623 input chars preserved. Actual local synthetic annex: PASS, one table, five anchored items, one window and 405 input chars preserved.
4. Evidence JSON: docs/research/contract-integration/evidence/docling_contract_adapter_native_smoke.json.

## Explicitly NOT yet implemented
No invocation of N4/N12, no contractual obligation/typed fact/risk interpretation, no independent contractual oracle, no authenticated PDF original-source attestation, no comprehensive annex verification, no HITL approval, no ProjectGraph, Health, Alerts or Score changes, no API/router/UI integration. A syntactically anchored fragment is not proof of sound legal interpretation.

## Next gate
- Reconcile current pilot #1276 and active branches by SHA, not historical main.
- Build optional revision-authorized bridge to native N4 inputs, preserving pages/tables/source lineage and all-source coverage. Never manufacture N12 source attestation from Docling's own claims.
- Run A/B against existing PyMuPDF/Tesseract parser on identical synthetic PDFs; evaluate page/table/cell recall, evidence traceability, latency, omissions and source order.
- Separately validate N4 and N12 against a held-out independent legal/EPC oracle for critical omissions, citations, false positives and multi-document changes.
- Keep all outputs untrusted and user-visible only as candidates until approved.

## Independent QA and corrections
Gemini QA job 1e4a7b063a9e94f39de2f10111866572 initially returned FAIL: (1) text/table order, (2) two-dimensional tables, (3) multipage page provenance, and (4) word/number splitting. All four findings were addressed in the isolated branch using Docling.iterate_items, explicit table rows, full page lists, and token-boundary-aware windows that fail closed on unbreakable tokens. 22/22 unit tests PASS and a second native Docling smoke on two synthetic PDFs PASS. The focused independent QA rerun (job c958360504c426d2c176abd8d5579929) completed with **PASS_LIMITED**: all four original findings repaired for structural preparation. Four residual blockers to direct N4 integration remain: no partial degradation when a layout item is unsequenced; no semantic overlap between windows; complex merged table cells fail closed; table column alignment not verified. See QA_REVIEW_AFTER_FIX_20261120.md. N4/N12 semantics remain NOT_TESTED.
Codex N4/N12 bridge planner job 1112e70647c45598a01f7de43a8d50ee exited -25 without a completed deliverable. We do NOT claim a planner architecture review completed.
Next priority is integration with N4/N12 on pinned current SHA; structural source extraction is not yet semantic contract intelligence.

## Other workstreams
Schedule / MPXJ: research/c2pro-integration-open-source-20261120, 10 unit PASS + native smoke PASS, still not live API integration.
Historical documents: private separate workstream, not part of this effort.
