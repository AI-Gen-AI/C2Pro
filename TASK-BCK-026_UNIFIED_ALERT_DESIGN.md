# TASK-BCK-026: Unified Alert System Design

## Overview

Consolidate risk alerts (from save_to_db_node) and coherence alerts into a single unified AlertGenerator with a type discriminator.

## Current State Analysis

### Risk Alert Creation (save_to_db_node)
- **Location**: `apps/api/src/analysis/adapters/graph/nodes.py` (lines 231-297)
- **Approach**: Creates Alert objects directly in LangGraph node
- **Category**: Hardcoded `category="risk"`
- **Logic**: Simple mapping from `state["extracted_risks"]`
- **Issues**: No deduplication, no auto-resolve, no fingerprinting

### Coherence Alert Creation
- **Generator**: `apps/api/src/coherence/alert_generator.py`
  - Generates `AlertCreate` DTOs from `CoherenceRuleResult`
  - Sophisticated grouping, templating, severity mapping
  - Category values: "schedule", "financial", "legal", or None

- **Service**: `apps/api/src/coherence/services/alerts/generator.py` (`AlertGeneratorService`)
  - Fingerprinting for deduplication
  - Auto-resolve for missing violations
  - Update/reopen logic for existing alerts
  - Uses `AlertRepository` for persistence

### Current Alert Model
**File**: `apps/api/src/analysis/adapters/persistence/models.py` (lines 145-329)

**Key Fields**:
- `category: Mapped[str | None]` - Domain classification (schedule/financial/legal/risk)
- No type discriminator field currently exists

## Unified Design

### 1. Database Schema Changes

#### Add alert_type Discriminator
```python
# New field in Alert model
alert_type: Mapped[AlertType] = mapped_column(
    SQLEnum(AlertType, values_callable=lambda obj: [e.value for e in obj]),
    default=AlertType.RISK,
    nullable=False,
    index=True,
)
```

#### Alert Type Enum
```python
class AlertType(str, Enum):
    """Alert type discriminator."""
    RISK = "risk"           # From AI risk extraction
    COHERENCE = "coherence" # From coherence rule violations
    BUDGET = "budget"       # Future: Budget overruns
    WBS = "wbs"            # Future: WBS inconsistencies
```

#### Field Usage
- **alert_type**: Primary discriminator (WHERE clause filter)
  - `risk`: Alerts from AI risk extraction
  - `coherence`: Alerts from coherence rule engine
  - `budget`: Future budget-specific alerts
  - `wbs`: Future WBS-specific alerts

- **category**: Domain classification (business grouping)
  - `risk`: Generic risk (default for risk alert_type)
  - `schedule`: Timeline/dependency issues
  - `financial`: Budget/cost issues
  - `legal`: Compliance/contract issues
  - Can be null for non-categorized alerts

**Example Combinations**:
```python
# Risk alert about schedule
alert_type="risk", category="schedule"

# Coherence rule about financial issues
alert_type="coherence", category="financial"

# Generic risk without specific domain
alert_type="risk", category="risk"

# Future budget alert
alert_type="budget", category="financial"
```

### 2. Unified AlertGenerator Service

#### Enhanced AlertGenerator
**Location**: Extend existing `src/coherence/alert_generator.py`

**New Responsibilities**:
1. Accept both `CoherenceRuleResult` and risk extraction dictionaries
2. Set `alert_type` based on input source
3. Generate `AlertCreate` DTOs for both types
4. Preserve existing coherence logic (grouping, templating, severity mapping)
5. Add risk-specific generation logic

**Interface**:
```python
class AlertGenerator:
    def __init__(self, project_id: UUID, analysis_id: UUID | None = None):
        self._project_id = project_id
        self._analysis_id = analysis_id

    # Existing method - sets alert_type="coherence"
    def generate(self, rule_result: CoherenceRuleResult) -> list[AlertCreate]:
        """Generate coherence alerts from rule violations."""
        ...

    # New method - sets alert_type="risk"
    def generate_risk_alerts(self, risk_items: list[dict]) -> list[AlertCreate]:
        """Generate risk alerts from AI extraction."""
        for item in risk_items:
            severity = self._map_risk_severity(item)
            yield AlertCreate(
                project_id=self._project_id,
                analysis_id=self._analysis_id,
                alert_type=AlertType.RISK,  # NEW
                title=item.get("summary") or item.get("title") or "Risk identified",
                description=item.get("description") or "Risk detected by AI extraction.",
                severity=severity,
                category=item.get("category") or "risk",  # Domain classification
                impact_level=item.get("impact_level"),
                alert_metadata={"confidence": item.get("confidence"), "raw": item},
            )
```

#### AlertGeneratorService
**Location**: `src/coherence/services/alerts/generator.py`

**Changes**:
- No changes needed - already handles AlertCreate DTOs generically
- Fingerprinting, auto-resolve, update/reopen logic works for both types

### 3. Node Integration

#### save_to_db_node Changes
**File**: `apps/api/src/analysis/adapters/graph/nodes.py`

**Before** (lines 265-282):
```python
if state["extracted_risks"]:
    alerts = []
    for item in state["extracted_risks"]:
        severity = _map_risk_severity(item)
        alerts.append(
            Alert(
                project_id=project_id,
                analysis_id=analysis.id,
                severity=severity,
                title=item.get("summary") or item.get("title") or "Risk identified",
                description=item.get("description") or "Risk detected by AI extraction.",
                category="risk",
                impact_level=item.get("impact_level"),
                alert_metadata={"confidence": item.get("confidence"), "raw": item},
            )
        )
    await repo.add_alerts(alerts)
```

**After**:
```python
if state["extracted_risks"]:
    # Use unified AlertGenerator
    alert_generator = AlertGenerator(project_id=project_id, analysis_id=analysis.id)
    risk_alert_dtos = alert_generator.generate_risk_alerts(state["extracted_risks"])

    # Use AlertGeneratorService for persistence with deduplication
    alert_service = AlertGeneratorService(repository=repo)
    await alert_service.process_violations(
        project_id=project_id,
        violations=risk_alert_dtos,
        auto_resolve=True,  # Auto-resolve missing risks
    )
```

#### coherence_scorer_node Changes
**File**: `apps/api/src/analysis/adapters/graph/nodes_extended.py`

**Current**: Likely calls `AlertGeneratorService.process_rule_results()`
**Change**: Add `alert_type=AlertType.COHERENCE` to generated alerts

### 4. API Endpoint

#### Unified GET /api/v1/projects/{id}/alerts
**Location**: New file `apps/api/src/analysis/adapters/http/unified_alerts_router.py`

**Features**:
- Filter by `alert_type` (risk | coherence | budget | wbs)
- Filter by `category` (schedule | financial | legal | risk)
- Filter by `severity` (critical | high | medium | low)
- Filter by `status` (open | acknowledged | resolved | dismissed)
- Pagination support
- Sort by created_at, severity, status

**Query Parameters**:
```python
@router.get("/projects/{project_id}/alerts", response_model=PaginatedAlertResponse)
async def list_project_alerts(
    project_id: UUID,
    alert_type: AlertType | None = None,  # Filter by type
    category: str | None = None,          # Filter by category
    severity: AlertSeverity | None = None,
    status: AlertStatus | None = None,
    limit: int = 50,
    cursor: str | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all alerts for a project with filtering."""
    ...
```

## Migration Strategy

### Phase 1: Database Migration
1. Add `alert_type` column with default=`AlertType.RISK`
2. Add index on `alert_type` for efficient filtering
3. Backfill existing alerts:
   - If `rule_id` is not null → `alert_type="coherence"`
   - Otherwise → `alert_type="risk"`

### Phase 2: Code Changes
1. Update Alert model with alert_type field
2. Extend AlertGenerator with `generate_risk_alerts()` method
3. Update save_to_db_node to use AlertGenerator
4. Update coherence nodes to set alert_type="coherence"

### Phase 3: API
1. Create unified alerts endpoint
2. Update OpenAPI spec
3. Deprecate old endpoints (if any)

## TDD Test Plan

### Test Suite 1: AlertGenerator Risk Alerts
**File**: `apps/api/tests/unit/coherence/test_alert_generator_risk.py`

1. `test_generate_risk_alerts_sets_alert_type_risk()`
2. `test_generate_risk_alerts_maps_severity_correctly()`
3. `test_generate_risk_alerts_uses_risk_category_as_default()`
4. `test_generate_risk_alerts_includes_confidence_in_metadata()`
5. `test_generate_risk_alerts_handles_empty_list()`
6. `test_generate_risk_alerts_maps_impact_level()`
7. `test_generate_risk_alerts_uses_custom_category_when_provided()`

### Test Suite 2: Alert Model with alert_type
**File**: `apps/api/tests/unit/analysis/test_alert_model_types.py`

1. `test_alert_type_defaults_to_risk()`
2. `test_alert_type_can_be_set_to_coherence()`
3. `test_alert_type_validates_enum_values()`
4. `test_alert_can_have_risk_type_and_schedule_category()`
5. `test_alert_can_have_coherence_type_and_financial_category()`

### Test Suite 3: Unified Alerts Endpoint
**File**: `apps/api/tests/integration/analysis/test_unified_alerts_api.py`

1. `test_list_alerts_without_filters_returns_all_types()`
2. `test_list_alerts_filtered_by_alert_type_risk()`
3. `test_list_alerts_filtered_by_alert_type_coherence()`
4. `test_list_alerts_filtered_by_category_schedule()`
5. `test_list_alerts_filtered_by_severity_critical()`
6. `test_list_alerts_filtered_by_status_open()`
7. `test_list_alerts_pagination_works()`
8. `test_list_alerts_requires_authentication()`
9. `test_list_alerts_enforces_tenant_isolation()`
10. `test_list_alerts_combined_filters()`

## Deliverables

1. ✅ Design document (this file)
2. ⏳ Database migration (add alert_type, backfill, index)
3. ⏳ Updated Alert model with AlertType enum
4. ⏳ Enhanced AlertGenerator with risk alert generation
5. ⏳ Updated save_to_db_node to use AlertGenerator
6. ⏳ Updated coherence_scorer_node to set alert_type
7. ⏳ Unified GET /api/v1/projects/{id}/alerts endpoint
8. ⏳ TDD test suites (22 tests minimum)
9. ⏳ 80%+ test coverage verification
10. ⏳ BCK_BACKEND.md completion summary

## Implementation Order

1. **RED Phase**: Write TDD tests (all 22 tests)
2. **GREEN Phase**:
   - Create AlertType enum
   - Create database migration
   - Update Alert model
   - Extend AlertGenerator with `generate_risk_alerts()`
   - Update save_to_db_node
   - Update coherence_scorer_node
   - Create unified alerts endpoint
3. **REFACTOR Phase**: Code review, optimization
4. **VERIFY Phase**: Run tests, check coverage
5. **DOCUMENT Phase**: Update BCK_BACKEND.md

## Dependencies

- ✅ Alert model exists (`apps/api/src/analysis/adapters/persistence/models.py`)
- ✅ AlertGenerator exists (`apps/api/src/coherence/alert_generator.py`)
- ✅ AlertGeneratorService exists (`apps/api/src/coherence/services/alerts/generator.py`)
- ✅ save_to_db_node exists (`apps/api/src/analysis/adapters/graph/nodes.py`)
- ⏳ TASK-BCK-027 (Add budget alert generation) - Not blocking, future enhancement

## Risk Mitigation

1. **Backward Compatibility**: Default alert_type="risk" ensures existing code continues working
2. **Data Migration**: Backfill script uses rule_id presence to determine type
3. **Incremental Rollout**: Can deploy DB changes before code changes
4. **Testing**: 22 TDD tests ensure comprehensive coverage

---

**Status**: Design Complete, Ready for TDD Implementation
**Estimated Effort**: 8 hours (as per TASK-BCK-026)
**Priority**: P0 (Critical)
