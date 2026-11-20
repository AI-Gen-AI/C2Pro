# F2 — Confidential EPC cross-document study — sanitized public summary

**Date:** 2026-11-20  
**Status:** PASS_LIMITED · research evidence, not production validation  
**Branch:** `research/c2pro-integration-open-source-20261120`

## Data separation
A real, historical, **single-project** multi-document corpus was examined in an operator-authorized private Windows lab. **No underlying private documents, OCR text, prices, excerpts, supplier identifiers, PO identifiers, source hashes, or source file paths belong in this public repository.** Detailed results and provenance are kept in a restricted Google Drive folder and in the original owner's local lab. Other agents must request authorized access, never fabricate artifacts.

## Verified technical observations
1. **Scheduling:** Two native project-plan files were imported successfully by MPXJ; SHA equality established they were byte-identical duplicates. One unique schedule contained 118 task records, 169 predecessor links, 10 milestones and 2 calendars. The importer reported populated dates and no duplicate unique identifiers. No independent verification of baselines, calendars, critical path or schedule authority was performed.
2. **Budget/quantities:** Two separate workbooks of the same project were compared at explicit row/cell ranges. Five matched equipment categories agreed in count, unit mass and extended mass, including matched totals. **Status: CANDIDATE_MATCH**; the workbooks may share a common data source, and approval/contractual authority was not verified.
3. **PDF coverage:** Ten selected PDF documents were preflighted; three had no extractable text. Five scanned pages from two document types were processed using **local-only Tesseract OCR**, preserving page-linked word coordinates privately. Output quality has not been independently audited.
4. **Commercial chain:** A further ten scanned pages covering supplier commercial documentation and purchasing records were recovered with local OCR. An equipment-rating reference was found across technical specification, technical offer, commercial offer and purchasing record of the same supplier. A separate acknowledgment could **not** be linked with adequate independent evidence. Neither a valid PO nor specification compliance was certified.
5. **Cross-document scheduling gap:** The tested schedule lacked an explicit text label for the targeted equipment category. Mapping requires a WBS or item-ID crosswalk validated by a project-domain reviewer; **do not force string-based matches**.
6. **No trusted-state effects:** No source candidate has entered ProjectGraph trusted, N4/N12, HITL, Health, Alerts, or Coherence Score. No deployment or merge.

## Outcome / next gates
- **GO** for continued offline adapter research only.
- **NO-GO** for product integration, contractual compliance conclusion, procurement action or release until an independent oracle verifies document authority, OCR/page anchors, technical attributes beyond headline capacity, schedule-to-asset WBS mapping, revisions and completeness.
- Use source-defined `EvidenceRef`, `DocumentRevision`, `ScheduleActivity`, `CostLine`, `OfferLine`, `PurchaseOrder`, `Coverage` and `DiscrepancyCandidate` adapters; preserve unassessed/untrusted statuses.
- Keep the detailed corpus manifest, document bytes and all confidential OCR evidence **outside the public repository**.

## Security correction
The C2Pro repository was verified **public**. This research branch was force-with-lease reset to its last commit before internal inventory/filenames were added; no private document bytes were ever committed. **Historical orphaned Git objects or caches may remain accessible by old commit SHA; this ref reset is not a verified purge.** Do not re-add private identifiers. Full historical object removal requires separate repository owner/GitHub Support handling as appropriate.
