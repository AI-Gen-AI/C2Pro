# LangGraph Orchestration Audit Report

**Date:** 2026-03-21
**Auditor:** Senior Backend Engineer
**Task:** B-3 LangGraph Checkpointer (AUDIT-TASK-3.1)

---

## Executive Summary

The C2Pro LangGraph document analysis workflow is **OPERATIONAL** with PostgreSQL checkpointing correctly configured. The AI-powered risk extraction produces high-quality results with proper citation validation. However, the **coherence scoring always returns 100%** due to a design gap where analysis context is not passed to the scoring engine.

### Overall Status: PASS (with recommendations)

| Component | Status | Notes |
|-----------|--------|-------|
| LangGraph Workflow | **PASS** | 17-node workflow executing correctly |
| PostgreSQL Checkpointer | **PASS** | Checkpoints persisted, migrations v1-9 complete |
| Risk Extraction | **PASS** | AI extracts categorized risks with citations |
| WBS Extraction | **PASS** | Works for technical_spec documents |
| Coherence Scoring | **NEEDS WORK** | Always returns 100 (see findings) |
| Document Upload Integration | **NEEDS WORK** | Does not trigger LangGraph |

---

## Detailed Findings

### 1. LangGraph Checkpointer - WORKING

**Evidence:**
```sql
-- Checkpoint tables exist
SELECT * FROM checkpoint_migrations;
 v
---
 1-9 (migrations complete)

-- Checkpoints being stored
SELECT thread_id, checkpoint_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 5;
 22222222-2222-2222-2222-222222222222 | 1f124d01-6262-68cf-8011-454fcc5be433
 ...
```

**Configuration:**
- Uses `AsyncPostgresSaver` from `langgraph-checkpoint-postgres`
- Connection pool: `psycopg_pool.AsyncConnectionPool` with min_size=0, max_size=10
- Tables: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`

**Code Location:** `apps/api/src/analysis/adapters/graph/workflow.py:186-232`

### 2. LangGraph Workflow - WORKING

**Test Results:**
```bash
POST /api/v1/analyze
Response: 7 risks extracted, analysis persisted, citations validated
```

**Workflow Nodes (N1-N16):**
- N1: document_ingestion - PASS
- N2: pii_anonymizer - PASS
- N3: router - PASS (contract/technical_spec/budget classification)
- N4: risk_extractor - PASS (AI-powered with retry)
- N5: wbs_extractor - PASS
- N6: stakeholder_extractor - PASS
- N7: raci_generator - PASS
- N8: coherence_scorer - NEEDS WORK (always 100)
- N9: budget_parser - PASS
- N10: knowledge_graph - PASS
- N11: decision_intelligence - PASS
- N12: critique - PASS (retry mechanism working)
- N13/14: human_interrupt - PASS
- N15: citation_validator - PASS (7/7 citations verified)
- N16: final_assembler - PASS
- N17: save_to_db - PASS

### 3. Risk Extraction Quality - EXCELLENT

**Sample Output:**
```json
{
  "risks": [
    {
      "category": "SCHEDULE",
      "title": "Retraso en obtención de permisos",
      "probability": "HIGH",
      "impact": "HIGH",
      "risk_score": 9,
      "source_quote": "Retraso en permisos"
    },
    {
      "category": "FINANCIAL",
      "title": "Penalizaciones por retraso",
      "probability": "MEDIUM",
      "impact": "HIGH",
      "risk_score": 6,
      "source_quote": "0.1% del valor total"
    },
    // ... 5 more risks
  ]
}
```

**Verification:**
- All 7 risks persisted to `alerts` table with proper severity mapping
- Citation validation passed (7/7)

### 4. Coherence Scoring - ALWAYS 100 (BUG)

**Root Cause Analysis:**

The `coherence_scorer_node` (N8) calls:
```python
service = CoherenceCalculationService()
result = service.calculate_coherence(
    project_id=UUID(project_id),
    bom_items=[],            # EMPTY
    document_count=1,
    # All boolean flags DEFAULT TO TRUE
)
```

The `CoherenceRulesEngine.evaluate()` starts all categories at 100:
```python
scores: dict[str, int] = {category: 100 for category in self._CATEGORIES}
```

Violations are only triggered when:
- `scope_defined=False` (default True)
- `schedule_within_contract=False` (default True)
- `technical_consistent=False` (default True)
- `legal_compliant=False` (default True)
- `quality_standard_met=False` (default True)

**Since all flags default to True, no violations are detected = 100% coherence.**

### 5. Document Upload Pipeline - SEPARATE FROM LANGGRAPH

**Critical Finding:**

The document upload flow (`POST /api/v1/documents`) triggers:
- Celery task `process_document_async`
- `DocumentsEntityExtractionService` (rule-based, NOT AI)
- Extracts emails for stakeholders, schedule items for WBS, budget items for BOM

**This does NOT invoke the LangGraph workflow.**

The LangGraph analysis requires:
- Explicit call to `POST /api/v1/analyze` with document text
- OR trigger from frontend after upload

---

## Recommendations

### Priority 1: Fix Coherence Scoring (High Impact)

**Option A:** Derive coherence flags from extracted analysis:
```python
async def coherence_scorer_node(state: ProjectState) -> ProjectState:
    risks = state.get("extracted_risks", [])
    wbs = state.get("extracted_wbs", [])

    # Derive flags from analysis
    has_schedule_risks = any(r.get("category") == "SCHEDULE" for r in risks)
    has_financial_risks = any(r.get("category") == "FINANCIAL" for r in risks)

    service = CoherenceCalculationService()
    result = service.calculate_coherence(
        project_id=UUID(project_id),
        bom_items=state.get("bom_items", []),
        document_count=1,
        schedule_within_contract=not has_schedule_risks,
        # etc.
    )
```

**Option B:** Use risk severity distribution for scoring:
- HIGH risks: -15 points each
- MEDIUM risks: -5 points each
- LOW risks: -2 points each
- Start at 100, subtract penalties

### Priority 2: Integrate LangGraph with Document Upload

Add option to trigger LangGraph analysis after document parsing:
```python
# In ingestion_tasks.py after parsing
if settings.auto_analyze_documents:
    await run_orchestration(
        initial_state={...},
        thread_id=str(document.project_id)
    )
```

### Priority 3: Monitor Checkpointer Health

Add health check for checkpointer pool:
```python
@app.get("/health/langgraph")
async def langgraph_health():
    return {
        "checkpointer": "ready" if _checkpointer_ready else "initializing",
        "pool_size": _checkpointer_pool._pool.getconn_count() if _checkpointer_pool else 0
    }
```

---

## Test Evidence

### 1. Successful Analysis Request
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"project_id": "...", "document_text": "..."}'
```

### 2. Database Verification
```sql
-- Analysis persisted
SELECT * FROM analyses WHERE id = '590e1aa7-ae13-4e62-852c-994a78639938';
-- 7 alerts_count, status=completed

-- Alerts created
SELECT title, severity, category FROM alerts WHERE analysis_id = '...';
-- 7 rows: 3 high, 3 medium, 1 critical
```

### 3. Checkpoint Verification
```sql
SELECT COUNT(*) FROM checkpoints WHERE thread_id = '22222222-2222-2222-2222-222222222222';
-- 15+ checkpoints stored for single analysis run
```

---

## Conclusion

The LangGraph orchestration core is **production-ready** for risk extraction and document analysis. The PostgreSQL checkpointer is correctly configured and persisting workflow state.

The coherence scoring requires immediate attention as the current implementation provides no value (always 100%). The recommended fix involves deriving coherence flags from the actual analysis results rather than using static defaults.

**Audit Status:** PASSED with recommendations

---

*Report generated: 2026-03-21 02:50 UTC*
