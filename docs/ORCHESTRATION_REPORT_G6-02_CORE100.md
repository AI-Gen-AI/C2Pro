# Orchestration Report: G6-02 Core-100 Nightly Dataset

**Date**: 2026-03-28
**Gate**: 6 - AI/LLM Reliability and Evaluation
**Task**: `G6-02-EX-01` - Expand to Core-100 dataset for nightly runs
**Status**: ✅ Complete

---

## Governance Note

This report is completion evidence for `G6-02-EX-01`.

Open and future work for the golden dataset program is tracked only in `C2PRO_MASTER_BACKLOG.md`.

---

## Executive Summary

The golden regression corpus has been expanded from the original Spanish-only Core-25 baseline to a Core-100 nightly dataset. The nightly set now includes real source references from **Spain, USA, Kuwait, and Saudi Arabia** and is wired into the existing loader and regression runner without changing the execution contract.

**Nightly dataset metrics**
- 100 validated golden cases
- Difficulty distribution: Easy `20`, Medium `30`, Hard `30`, Expert `20`
- Geographic coverage: Spain, USA, Kuwait, Saudi Arabia
- 100/100 mock nightly regression cases executed successfully

---

## What Changed

### Dataset expansion

- Retained the original Core-25 baseline cases
- Added **75** new JSON cases under `apps/api/src/golden/cases/`
- Expanded the nightly corpus with real-file references drawn from:
  - `docs/assets/samples/España/`
  - `docs/assets/samples/USA/`
  - `docs/assets/samples/Kuwait/`
  - `docs/assets/samples/Arabia Saudi/`

### Validation contract

- Updated the dataset validation tests to enforce a **Core-100** count
- Added nightly coverage checks for the four supported sample geographies
- Updated loader integration tests to validate the new nightly distribution

---

## Dataset Distribution

| Difficulty | Total |
|------------|-------|
| Easy | 20 |
| Medium | 30 |
| Hard | 30 |
| Expert | 20 |

| Country | Coverage |
|---------|----------|
| Spain | Present in baseline and nightly expansion |
| USA | Present in nightly expansion |
| Kuwait | Present in nightly expansion |
| Saudi Arabia | Present in nightly expansion |

The nightly tests enforce that every supported geography contributes at least 10 cases.

---

## Source Projects Used In Expansion

Representative real-project folders used for the new nightly cases:

- `docs/assets/samples/USA/O - Souther California Edison Energy Storage System`
- `docs/assets/samples/USA/O-011139 Salt River Project SRP Energy Storage System`
- `docs/assets/samples/USA/O-XXXXXX BESS Guam project`
- `docs/assets/samples/USA/P-Delaney-Colorado River 500 KV AC Transmission Line`
- `docs/assets/samples/USA/P-Mount Solar Signal PV`
- `docs/assets/samples/Kuwait/O-009984 4P 400 kV OHTL Subiya Power Station-Al Zour SS`
- `docs/assets/samples/Kuwait/P-008247 4P 132kV OHTL Shagaya`
- `docs/assets/samples/Kuwait/P-008788 OHTL 300-132-33 kV Tender #62`
- `docs/assets/samples/Kuwait/P-00XXXX RA-212 project - Combined Group l`
- `docs/assets/samples/Kuwait/Importacion en Kuwait`
- `docs/assets/samples/Arabia Saudi/O-010716 Construction of Jeddah Prince Fawaz Housing Substation`
- `docs/assets/samples/Arabia Saudi/P-APM Jeddah`
- `docs/assets/samples/Arabia Saudi/P-HHR Meca-Medina`
- `docs/assets/samples/Arabia Saudi/P-SE Jeddah`
- `docs/assets/samples/Arabia Saudi/P-Technical Buildings (Dimetronic)`
- `docs/assets/samples/España/O-010160 Hospital Averroes`
- `docs/assets/samples/España/O-Proyecto Waste to Biofuels SE 66-6 kV Sevilla`
- `docs/assets/samples/España/P-006328 Fasa Renault -Sevilla`
- `docs/assets/samples/España/P-009192 Señaliz. y comunicaciones LAV La Roda-Pobla de Lena`
- `docs/assets/samples/España/P-009604 LAV Monforte-Murcia`

---

## Verification

Validated locally on 2026-03-28 with:

```bash
PYTHONPATH=apps/api/src pytest apps/api/tests/golden/test_core25_validation.py apps/api/tests/golden/test_golden_loader.py -q
PYTHONPATH=apps/api/src python -m golden.runner --mock --output json --output-file apps/api/golden-core100-results.json
```

Observed result:
- Validation suite passed
- Loader integration suite passed
- Mock nightly regression loaded **100** cases and completed successfully

---

## Follow-On Work

`G6-02-EX-01` is complete. Remaining roadmap items:

- `G6-02-EX-02` Build Extended-300 dataset for calibration
- `G6-02-EX-03` Add LLM judge evaluator with rate limiting

---

## References

| Document | Path |
|----------|------|
| Master Backlog | `C2PRO_MASTER_BACKLOG.md` |
| Original Core-25 Report | `docs/ORCHESTRATION_REPORT_G6-02_CORE25.md` |
| Golden Framework Report | `docs/ORCHESTRATION_REPORT_G6-02.md` |
| Case Creation Guidelines | `docs/CASE_CREATION_GUIDELINES.md` |
| Validation Tests | `apps/api/tests/golden/test_core25_validation.py` |
| Loader Tests | `apps/api/tests/golden/test_golden_loader.py` |
