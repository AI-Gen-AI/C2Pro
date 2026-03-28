# Golden Dataset Case Creation Guidelines

This document provides comprehensive guidelines for creating golden test cases
for the LangGraph multi-agent coherence evaluation system.

---

## Overview

Golden cases are reference test scenarios that define expected behavior for the
coherence analysis workflow. Each case specifies:
- Input documents to analyze
- Expected graph traversal trajectory
- Expected tool calls
- Expected state values
- Expected coherence issues to detect

---

## Directory Structure

Cases are organized by difficulty level:

```
apps/api/src/golden/cases/
├── easy/         # Single-dimension, obvious violations
├── medium/       # Multi-step reasoning required
├── hard/         # Cross-dimensional, subtle issues
└── expert/       # Complex multi-dimensional analysis
```

---

## Case ID Conventions

### Format
```
{DIMENSION_PREFIX}-{NUMBER}
```

### Dimension Prefixes

| Prefix | Dimension | Examples |
|--------|-----------|----------|
| `SCHED` | Schedule | `SCHED-001`, `SCHED-101` |
| `COST` | Cost | `COST-001`, `COST-201` |
| `LEG`, `LEGAL` | Legal | `LEG-001`, `LEGAL-101` |
| `QUAL`, `QUALITY` | Quality | `QUAL-001`, `QUALITY-201` |
| `SCOPE`, `SCP` | Scope | `SCOPE-001`, `SCP-101` |
| `TECH`, `TECHNICAL` | Technical | `TECH-001`, `TECHNICAL-201` |
| `MULTI`, `MIX` | Multi-dimensional | `MULTI-301`, `MIX-401` |

### Numbering Ranges by Difficulty

| Difficulty | Number Range | Examples |
|------------|--------------|----------|
| Easy | 001-099 | `SCHED-001`, `COST-050` |
| Medium | 100-199 | `SCHED-101`, `COST-150` |
| Hard | 200-299 | `SCHED-201`, `COST-250` |
| Expert | 300-999 | `MULTI-301`, `MULTI-500` |

---

## Schema Reference

### GoldenCase Fields

```python
{
    "case_id": str,           # Required: Unique ID (e.g., "SCHED-001")
    "name": str,              # Required: Descriptive name (5-200 chars)
    "dimensions": list[str],  # Required: 1-6 dimensions covered
    "difficulty": str,        # Required: "Easy", "Medium", "Hard", "Expert"
    "input_documents": {...}, # Required: Document paths
    "trajectory": {...},      # Required: Expected workflow path
    "tool_calls": [...],      # Optional: Expected tool calls
    "state_assertions": [...],# Optional: Expected state values
    "expected_issues": [...], # Optional: Expected coherence issues
    "metadata": {...}         # Optional: Additional metadata
}
```

### Input Documents

```python
{
    "contract_path": str,        # Required: Path to contract document
    "schedule_path": str,        # Required: Path to project schedule
    "budget_path": str | None,   # Optional: Path to budget document
    "specifications_path": str | None,  # Optional: Technical specs
    "drawings_path": str | None  # Optional: Engineering drawings
}
```

### Trajectory Constraints

```python
{
    "required_nodes": list[str],  # Required: Nodes that MUST be visited
    "optional_nodes": list[str],  # Optional: Nodes that MAY be visited
    "forbidden_nodes": list[str], # Optional: Nodes that MUST NOT be visited
    "max_loops": int | None       # Optional: Max allowed loop iterations
}
```

### Tool Call Assertions

```python
{
    "tool_name": str,           # Required: Name of the tool
    "required_args": list[str], # Optional: Args that MUST be present
    "forbidden_args": list[str],# Optional: Args that MUST NOT be present
    "min_calls": int,           # Default 1: Minimum call count
    "max_calls": int | None     # Optional: Maximum call count
}
```

### State Assertions

```python
{
    "path": str,           # Required: JSON path (e.g., "issues.0.severity")
    "operator": str,       # Required: "equals", "contains", "greater_than",
                          #           "less_than", "exists"
    "expected_value": Any, # Required: Value to compare against
    "at_node": str | None  # Optional: Node where assertion applies
}
```

### Coherence Issue Assertions

```python
{
    "rule_id": str,        # Required: Rule ID (e.g., "SCHED-001")
    "dimension": str,      # Required: Coherence dimension
    "severity": str,       # Required: "high", "medium", "low"
    "description_contains": str | None  # Optional: Text that must appear
}
```

---

## Difficulty Level Guidelines

### Easy (001-099)

- **Complexity**: Single dimension, obvious violation
- **Reasoning**: Straightforward pattern matching
- **Expected nodes**: 3-5 nodes
- **Tool calls**: 1-2 tools
- **Issues**: 1-2 clear issues

**Example scenarios**:
- Missing signature date in contract
- Milestone date mismatch between schedule and contract
- Budget line item clearly missing

### Medium (100-199)

- **Complexity**: Single or dual dimension, requires inference
- **Reasoning**: Multi-step analysis, cross-reference
- **Expected nodes**: 5-8 nodes
- **Tool calls**: 2-4 tools
- **Issues**: 2-4 issues with varying severity

**Example scenarios**:
- Resource allocation conflicts across multiple milestones
- Currency exchange risk exposure in multi-vendor contracts
- Quality standard deviation across specifications

### Hard (200-299)

- **Complexity**: 2-4 dimensions, subtle or cascading issues
- **Reasoning**: Complex cross-referencing, chain analysis
- **Expected nodes**: 7-12 nodes
- **Tool calls**: 4-6 tools
- **Issues**: 3-6 issues with interdependencies

**Example scenarios**:
- Dependency chain violations affecting multiple schedules
- Multi-party liability chains in subcontractor agreements
- Technical risk cascades from specification conflicts

### Expert (300-999)

- **Complexity**: 4-6 dimensions, full coherence analysis
- **Reasoning**: System-level analysis, risk assessment
- **Expected nodes**: 10-15 nodes
- **Tool calls**: 6+ tools
- **Issues**: 5+ issues across multiple dimensions

**Example scenarios**:
- Full project coherence audit (all 6 dimensions)
- Supplier distress impact on schedule, cost, quality, technical
- New supplier risk assessment with legal and technical validation

---

## Example Cases

### Easy Case: SCHED-001

```json
{
    "case_id": "SCHED-001",
    "name": "Simple milestone date mismatch detection",
    "dimensions": ["Schedule"],
    "difficulty": "Easy",
    "input_documents": {
        "contract_path": "samples/España/LAV_La_Robla/contrato.pdf",
        "schedule_path": "samples/España/LAV_La_Robla/cronograma.pdf"
    },
    "trajectory": {
        "required_nodes": ["extract_dates", "compare_schedules", "report_issues"],
        "optional_nodes": ["validate_format"],
        "forbidden_nodes": ["deep_analysis"]
    },
    "tool_calls": [
        {
            "tool_name": "extract_schedule_dates",
            "required_args": ["document_path"],
            "min_calls": 2
        }
    ],
    "state_assertions": [
        {
            "path": "issues_found",
            "operator": "greater_than",
            "expected_value": 0
        }
    ],
    "expected_issues": [
        {
            "rule_id": "SCHED-001",
            "dimension": "Schedule",
            "severity": "high",
            "description_contains": "milestone date"
        }
    ],
    "metadata": {
        "source_project": "LAV La Robla-Pobla de Lena",
        "sector": "Rail Infrastructure",
        "author": "evaluation_team",
        "created_date": "2026-03-24"
    }
}
```

### Medium Case: MULTI-101

```json
{
    "case_id": "MULTI-101",
    "name": "Schedule-cost cross-reference variance",
    "dimensions": ["Schedule", "Cost"],
    "difficulty": "Medium",
    "input_documents": {
        "contract_path": "samples/España/Metro_Madrid/contrato.pdf",
        "schedule_path": "samples/España/Metro_Madrid/cronograma.pdf",
        "budget_path": "samples/España/Metro_Madrid/presupuesto.xlsx"
    },
    "trajectory": {
        "required_nodes": [
            "extract_schedule",
            "extract_budget",
            "correlate_milestones_costs",
            "identify_variances",
            "report_findings"
        ],
        "optional_nodes": ["risk_assessment"],
        "max_loops": 3
    },
    "tool_calls": [
        {
            "tool_name": "extract_schedule_dates",
            "required_args": ["document_path"],
            "min_calls": 1
        },
        {
            "tool_name": "extract_budget_items",
            "required_args": ["document_path"],
            "min_calls": 1
        },
        {
            "tool_name": "correlate_schedule_cost",
            "required_args": ["schedule_data", "budget_data"],
            "min_calls": 1
        }
    ],
    "expected_issues": [
        {
            "rule_id": "SCHED-101",
            "dimension": "Schedule",
            "severity": "medium",
            "description_contains": "milestone"
        },
        {
            "rule_id": "COST-101",
            "dimension": "Cost",
            "severity": "medium",
            "description_contains": "budget allocation"
        }
    ],
    "metadata": {
        "source_project": "Metro Madrid Line Extension",
        "sector": "Urban Transit",
        "tags": ["cross-dimensional", "variance-analysis"]
    }
}
```

### Expert Case: MULTI-301

```json
{
    "case_id": "MULTI-301",
    "name": "Full 6-dimensional coherence analysis",
    "dimensions": ["Schedule", "Cost", "Legal", "Quality", "Scope", "Technical"],
    "difficulty": "Expert",
    "input_documents": {
        "contract_path": "samples/España/LAV_Madrid_Murcia/contrato_marco.pdf",
        "schedule_path": "samples/España/LAV_Madrid_Murcia/cronograma_maestro.pdf",
        "budget_path": "samples/España/LAV_Madrid_Murcia/presupuesto_global.xlsx",
        "specifications_path": "samples/España/LAV_Madrid_Murcia/especificaciones_tecnicas.pdf"
    },
    "trajectory": {
        "required_nodes": [
            "extract_all_documents",
            "analyze_legal_compliance",
            "analyze_schedule_coherence",
            "analyze_cost_consistency",
            "analyze_scope_alignment",
            "analyze_quality_standards",
            "analyze_technical_requirements",
            "cross_reference_all_dimensions",
            "risk_assessment",
            "generate_comprehensive_report"
        ],
        "optional_nodes": ["deep_legal_analysis", "variance_projection"],
        "max_loops": 5
    },
    "tool_calls": [
        {"tool_name": "extract_contract_terms", "min_calls": 1},
        {"tool_name": "extract_schedule_dates", "min_calls": 1},
        {"tool_name": "extract_budget_items", "min_calls": 1},
        {"tool_name": "extract_scope_items", "min_calls": 1},
        {"tool_name": "extract_quality_standards", "min_calls": 1},
        {"tool_name": "extract_technical_specs", "min_calls": 1},
        {"tool_name": "cross_reference_analysis", "min_calls": 1}
    ],
    "expected_issues": [
        {
            "rule_id": "SCHED-301",
            "dimension": "Schedule",
            "severity": "high"
        },
        {
            "rule_id": "COST-301",
            "dimension": "Cost",
            "severity": "medium"
        },
        {
            "rule_id": "LEG-301",
            "dimension": "Legal",
            "severity": "high"
        },
        {
            "rule_id": "QUAL-301",
            "dimension": "Quality",
            "severity": "medium"
        },
        {
            "rule_id": "SCOPE-301",
            "dimension": "Scope",
            "severity": "low"
        },
        {
            "rule_id": "TECH-301",
            "dimension": "Technical",
            "severity": "high"
        }
    ],
    "metadata": {
        "source_project": "LAV Madrid-Murcia HSR",
        "sector": "High-Speed Rail",
        "complexity": "maximum",
        "estimated_analysis_time_minutes": 15,
        "tags": ["full-coherence", "hsm", "multi-dimensional"]
    }
}
```

---

## Validation Checklist

Before submitting a new case, verify:

### Required Fields
- [ ] `case_id` follows naming convention
- [ ] `case_id` prefix matches primary dimension
- [ ] `name` is descriptive (5-200 characters)
- [ ] `dimensions` list is non-empty (1-6 items)
- [ ] `difficulty` matches number range
- [ ] `input_documents` has `contract_path` and `schedule_path`
- [ ] `trajectory.required_nodes` has at least 1 node

### Consistency Checks
- [ ] Difficulty number range matches directory (easy/001-099, etc.)
- [ ] Dimensions in `expected_issues` match case `dimensions`
- [ ] `rule_id` patterns match the rule format (`{PREFIX}-{NUMBER}`)
- [ ] No overlap between required/optional/forbidden nodes

### Quality Checks
- [ ] Case tests a real, meaningful scenario
- [ ] Expected issues are realistic and verifiable
- [ ] Tool call assertions match actual workflow capabilities
- [ ] Metadata includes `source_project` for traceability

---

## Security Constraints

The golden dataset system enforces security limits:

| Constraint | Limit | Reason |
|------------|-------|--------|
| Max file size | 50 MB | Prevent resource exhaustion |
| Max string length (short) | 200 chars | IDs, tool names, rule IDs |
| Max string length (medium) | 1000 chars | Descriptions, paths |
| Max metadata depth | 5 levels | Prevent stack overflow |
| Path traversal | Blocked | Security |

---

## Running Validation

### Validate All Cases
```bash
cd apps/api
python -m pytest tests/golden/test_golden_schema_validation.py -v
```

### Run Core-100 Nightly Validation
```bash
python -m pytest tests/golden/test_core25_validation.py -v
```

### Run Regression Tests
```bash
python -m golden.runner --mock
```

### Run Benchmark
```bash
python -m golden.benchmark --threshold 80
```

---

## Adding New Cases

1. **Choose difficulty** based on complexity guidelines
2. **Create JSON file** in appropriate `cases/{difficulty}/` directory
3. **Name file** as `{CASE_ID}.json` (e.g., `SCHED-002.json`)
4. **Run validation** to ensure schema compliance
5. **Add specific tests** for edge cases if needed
6. **Update metrics** by running benchmark with `--baseline`

---

## Troubleshooting

### Case fails schema validation

**Error**: `ValidationError: Case ID prefix 'XXX' does not match any known dimension`

**Solution**: Use a valid dimension prefix (SCHED, COST, LEG, QUAL, SCOPE, TECH, MULTI, MIX)

---

**Error**: `ValidationError: Nodes cannot be both required and forbidden`

**Solution**: Ensure no node appears in both `required_nodes` and `forbidden_nodes`

---

**Error**: `ValidationError: min_calls (X) must be <= max_calls (Y)`

**Solution**: Ensure `min_calls` is less than or equal to `max_calls`

---

**Error**: `PathTraversalError: Path traversal detected`

**Solution**: Ensure all file paths are within the allowed directory structure

---

## References

| Document | Location |
|----------|----------|
| Schema Definition | `apps/api/src/golden/schemas.py` |
| Loader Implementation | `apps/api/src/golden/loader.py` |
| Runner Implementation | `apps/api/src/golden/runner.py` |
| Benchmark Runner | `apps/api/src/golden/benchmark.py` |
| Core-100 Nightly Cases | `apps/api/src/golden/cases/` |
| Validation Tests | `apps/api/tests/golden/` |
| Security Audit | `SECURITY_AUDIT_GOLDEN_DATASET.md` |
| Orchestration Report | `docs/ORCHESTRATION_REPORT_G6-02_CORE25.md` |
| Core-100 Expansion Report | `docs/ORCHESTRATION_REPORT_G6-02_CORE100.md` |

---

**End of Case Creation Guidelines**
