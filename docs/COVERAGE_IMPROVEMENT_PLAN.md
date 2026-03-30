# Plan to Reach 70% Document Adapter Coverage

> **Governance Note:** This document is a technical planning artifact. Active task ownership and completion state must be tracked in `C2PRO_MASTER_BACKLOG.md`.

## Current Coverage: 37%

## Gap Analysis

| Module                                 | Current | Target | Gap  | Priority |
| -------------------------------------- | ------- | ------ | ---- | -------- |
| excel_file_parser.py                   | 16%     | 70%    | -54% | P0       |
| documents_entity_extraction_service.py | 16%     | 70%    | -54% | P0       |
| sqlalchemy_document_repository.py      | 20%     | 70%    | -50% | P0       |
| composite_file_parser.py               | 28%     | 70%    | -42% | P1       |
| rag_service.py                         | 28%     | 70%    | -42% | P1       |
| local_file_storage_service.py          | 35%     | 70%    | -35% | P2       |
| bc3_file_parser.py                     | 44%     | 70%    | -26% | P2       |
| sqlalchemy_rag_ingestion_service.py    | 46%     | 70%    | -24% | P2       |
| router.py                              | 51%     | 70%    | -19% | P2       |
| pdf_file_parser.py                     | 60%     | 70%    | -10% | P3       |

## Implementation Plan

### Phase 1: Lowest Coverage Modules (P0)

#### 1. Excel Parser - Target: 70%

**Gap**: 54% (16% → 70%)

```
tests/unit/adapters/documents/
└── test_excel_parser.py (NEW)
```

**Tests to add:**

```python
# test_excel_parser.py
class TestExcelParser:
    def test_parse_budget_success():
        # Mock openpyxl, test budget parsing

    def test_parse_schedule_success():
        # Mock openpyxl, test schedule parsing

    def test_parse_invalid_file():
        # Test error handling

    def test_parse_empty_rows():
        # Test edge case

    def test_parse_with_formulas():
        # Test formula handling

    def test_parse_multiple_sheets():
        # Test multi-sheet handling
```

**Est. tests**: 6-8 tests

#### 2. Entity Extraction Service - Target: 70%

**Gap**: 54% (16% → 70%)

```
tests/unit/adapters/documents/
└── test_entity_extraction.py (NEW)
```

**Tests to add:**

```python
# test_entity_extraction.py
class TestDocumentsEntityExtraction:
    def test_extract_stakeholders_from_contract():
        # Mock stakeholder use case, test extraction

    def test_extract_wbs_from_schedule():
        # Mock WBS use case, test extraction

    def test_extract_bom_from_budget():
        # Mock BOM use case, test extraction

    def test_extract_returns_summary():
        # Test return dict structure

    def test_extract_handles_empty_document():
        # Test edge case

    def test_extract_handles_parse_error():
        # Test error handling
```

**Est. tests**: 6-8 tests

#### 3. Document Repository - Target: 70%

**Gap**: 50% (20% → 70%)

```
tests/unit/adapters/documents/
└── test_document_repository.py (NEW)
```

**Tests to add:**

```python
# test_document_repository.py
class TestSqlAlchemyDocumentRepository:
    @pytest.mark.asyncio
    async def test_create_document():
        # Mock session, test create

    @pytest.mark.asyncio
    async def test_get_by_id():
        # Mock session, test get_by_id

    @pytest.mark.asyncio
    async def test_list_by_project():
        # Mock session, test list

    @pytest.mark.asyncio
    async def test_update_document():
        # Mock session, test update

    @pytest.mark.asyncio
    async def test_delete_document():
        # Mock session, test delete

    @pytest.mark.asyncio
    async def test_tenant_filter():
        # Test tenant isolation

    @pytest.mark.asyncio
    async def test_clause_operations():
        # Test clause CRUD
```

**Est. tests**: 8-10 tests

### Phase 2: Medium Coverage (P1)

#### 4. Composite Parser - Target: 70%

**Gap**: 42% (28% → 70%)

Add tests for:

- parse_document_file with different document types
- error handling for unsupported formats
- delegation to correct parser

**Est. tests**: 4-6 tests

#### 5. RAG Service - Target: 70%

**Gap**: 42% (28% → 70%)

Add tests for:

- rag_service.py query methods
- context retrieval
- error handling

**Est. tests**: 4-6 tests

### Phase 3: High Coverage (P2)

#### 6-9. Other Modules

Add targeted tests for:

- BC3 parser: 2-4 tests (44% → 70%)
- RAG ingestion: 2-4 tests (46% → 70%)
- Storage: 2-4 tests (35% → 70%)
- Router: 4-6 tests (51% → 70%)

### Phase 4: Final Push (P3)

#### 10. PDF Parser

Add tests for:

- OCR fallback
- Layout extraction
- Error handling

**Est. tests**: 2-4 tests

## Test Summary

| Phase     | Module              | New Tests | Coverage Gain |
| --------- | ------------------- | --------- | ------------- |
| P0        | Excel Parser        | 8         | +5%           |
| P0        | Entity Extraction   | 8         | +5%           |
| P0        | Document Repository | 10        | +8%           |
| P1        | Composite Parser    | 6         | +3%           |
| P1        | RAG Service         | 6         | +3%           |
| P2        | Others              | 16        | +5%           |
| P3        | PDF Parser          | 4         | +1%           |
| **Total** |                     | **58**    | **30%**       |

## Timeline Estimate

| Phase     | Effort      | Tests  |
| --------- | ----------- | ------ |
| P0        | 4 hours     | 26     |
| P1        | 2 hours     | 12     |
| P2        | 2 hours     | 16     |
| P3        | 1 hour      | 4      |
| **Total** | **9 hours** | **58** |

## Success Criteria

- [ ] All 58 new tests added
- [ ] All tests pass
- [ ] Coverage >= 70%
- [ ] No regression in existing tests

Current backlog rule:

- If any of the success criteria are still open in reality, the corresponding work must exist in `C2PRO_MASTER_BACKLOG.md`.
- Do not use this file as the authoritative execution tracker.

## Files to Create

```
tests/unit/adapters/documents/
├── test_excel_parser.py           # NEW
├── test_entity_extraction.py     # NEW
├── test_document_repository.py   # NEW
├── test_composite_parser_adv.py  # NEW
├── test_rag_service_adv.py       # NEW
└── test_storage_adv.py          # NEW
```

---

**Created**: 2026-03-27  
**Status**: Historical plan; refer to `C2PRO_MASTER_BACKLOG.md` for active status
