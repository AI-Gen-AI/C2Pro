# Model Router - Usage Guide

## Overview

The C2Pro Model Router intelligently selects the appropriate Claude model based on task type, budget constraints, and performance requirements. It implements the routing strategy defined in ROADMAP §3.2.

## Core Concepts

### Model Tiers

- **FLASH (Haiku)**: Fast, economical - For high-volume simple tasks
- **STANDARD (Sonnet)**: Balanced - For normal complexity tasks
- **POWERFUL (Opus)**: Powerful, expensive - For complex tasks (Phase 2+)

### Task Types (ROADMAP §3.2)

The router supports the following core task types:

1. **contract_extraction** → Sonnet (High precision, long context)
2. **stakeholder_classification** → Haiku (High volume, simple task)
3. **coherence_check** → Haiku (Deterministic rules, speed)
4. **raci_generation** → Sonnet (Complex reasoning)
5. **multimodal_expediting** → Sonnet Vision (Images)

## Basic Usage

### Initialize Router

```python
from src.modules.ai.model_router import get_model_router, AITaskType

router = get_model_router()
```

### Select Model for Task

```python
# Simple selection
model = router.select_model(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    input_token_estimate=50000
)

print(f"Selected: {model.name}")
print(f"Tier: {model.tier}")
print(f"Max tokens: {model.max_tokens}")
```

## Low Budget Mode (ROADMAP §3.2)

The router supports intelligent cost optimization through `low_budget_mode`:

```python
# Normal mode - uses recommended tier
model_normal = router.select_model_with_budget_mode(
    task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
    low_budget_mode=False
)
# Result: Haiku (already cheapest)

# Low budget mode - downgrades when viable
model_budget = router.select_model_with_budget_mode(
    task_type=AITaskType.COHERENCE_ANALYSIS,  # Normally Sonnet
    low_budget_mode=True
)
# Result: Haiku (downgraded for cost savings)
```

### Budget Mode Strategy

**Tasks that ARE downgraded** (non-critical):
- `stakeholder_classification`: Sonnet → Haiku
- `coherence_check`: Already Haiku
- `coherence_analysis`: Sonnet → Haiku
- `classification`: Already Haiku

**Tasks that are NOT downgraded** (critical - require precision):
- `contract_extraction`: Always Sonnet
- `raci_generation`: Always Sonnet
- `legal_interpretation`: Always Opus
- `wbs_generation`: Always Opus
- `bom_generation`: Always Opus

### Example: Budget Mode Comparison

```python
from src.modules.ai.model_router import get_model_router, AITaskType

router = get_model_router()

# Test with non-critical task
print("=== STAKEHOLDER CLASSIFICATION ===")
model_normal = router.select_model_with_budget_mode(
    task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
    low_budget_mode=False
)
print(f"Normal mode: {model_normal.tier.value} - {model_normal.name}")

model_budget = router.select_model_with_budget_mode(
    task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
    low_budget_mode=True
)
print(f"Budget mode: {model_budget.tier.value} - {model_budget.name}")

# Test with critical task
print("\n=== CONTRACT EXTRACTION (CRITICAL) ===")
model_normal = router.select_model_with_budget_mode(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    low_budget_mode=False
)
print(f"Normal mode: {model_normal.tier.value} - {model_normal.name}")

model_budget = router.select_model_with_budget_mode(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    low_budget_mode=True
)
print(f"Budget mode: {model_budget.tier.value} - {model_budget.name}")
# Note: Still Sonnet (critical task not downgraded)
```

## ROADMAP Task Examples

### 1. Contract Extraction (Sonnet)

```python
model = router.select_model_with_budget_mode(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    low_budget_mode=False,
    input_token_estimate=100000  # Large contract
)

# Estimate cost
cost = router.estimate_cost(
    model=model,
    input_tokens=100000,
    output_tokens=10000
)
print(f"Estimated cost: ${cost:.4f}")
```

### 2. Stakeholder Classification (Haiku)

```python
# High volume - many stakeholders
for stakeholder in stakeholders:
    model = router.select_model_with_budget_mode(
        task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
        low_budget_mode=True  # Save costs
    )
    # Process with Haiku...
```

### 3. Coherence Check (Haiku)

```python
model = router.select_model_with_budget_mode(
    task_type=AITaskType.COHERENCE_CHECK,
    low_budget_mode=False  # Already Haiku
)

# Fast, deterministic rule checking
```

### 4. RACI Generation (Sonnet)

```python
model = router.select_model_with_budget_mode(
    task_type=AITaskType.RACI_GENERATION,
    low_budget_mode=True  # Still uses Sonnet (critical)
)

# Complex reasoning required - not downgraded
```

### 5. Multimodal Expediting (Sonnet Vision)

```python
model = router.select_model(
    task_type=AITaskType.MULTIMODAL_EXPEDITING
)

# For vision tasks, use model name: claude-sonnet-4-vision
```

## Cost Estimation

### Estimate Single Task

```python
model = router.get_model_by_tier(ModelTier.STANDARD)

cost = router.estimate_cost(
    model=model,
    input_tokens=50000,
    output_tokens=5000
)

print(f"Cost: ${cost:.4f}")
```

### Compare Costs Across Models

```python
costs = router.compare_costs(
    input_tokens=50000,
    output_tokens=5000
)

for tier, cost in costs.items():
    print(f"{tier}: ${cost:.4f}")

# Output:
# flash: $0.0188
# standard: $0.2250
# powerful: $1.1250
```

## Force Tier Override

For testing or special requirements, you can force a specific tier:

```python
# Force Haiku for testing
model = router.select_model(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    force_tier=ModelTier.FLASH
)

# Force Opus for critical analysis
model = router.select_model_with_budget_mode(
    task_type=AITaskType.COHERENCE_ANALYSIS,
    force_tier=ModelTier.POWERFUL,
    low_budget_mode=True  # Ignored due to force_tier
)
```

## Configuration

### YAML Configuration

The router loads configuration from `model_routing.yaml`:

```yaml
task_routing:
  contract_extraction: standard
  stakeholder_classification: flash
  coherence_check: flash
  raci_generation: standard
  multimodal_expediting: standard

fallback_rules:
  budget:
    enabled: true
    threshold_usd: 1.0
```

### Environment Variables

You can override model names via environment:

```bash
AI_MODEL_DEFAULT=claude-sonnet-4-20250514
AI_MODEL_FAST=claude-haiku-4-20250514
AI_MODEL_POWERFUL=claude-opus-4-20250514
```

## Advanced Usage

### Get Tasks for Tier

```python
# Get all tasks recommended for Haiku
flash_tasks = router.get_tasks_for_tier(ModelTier.FLASH)
print(f"Flash tasks: {flash_tasks}")
```

### Get Model by Name

```python
model = router.get_model_by_name("claude-sonnet-4-20250514")
if model:
    print(f"Found: {model.tier}")
```

### List Available Tasks

```python
all_tasks = router.get_available_tasks()
print(f"Available tasks: {len(all_tasks)}")
```

## Budget-Based Selection (Legacy Method)

The legacy `select_model()` method also supports budget constraints:

```python
model = router.select_model(
    task_type=AITaskType.COHERENCE_ANALYSIS,
    budget_remaining_usd=0.50  # Low budget
)

# Automatically downgrades to Haiku if budget < $1.00
```

## Best Practices

### 1. Use Budget Mode for Non-Critical Tasks

```python
# ✅ Good: Save costs on classification
model = router.select_model_with_budget_mode(
    task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
    low_budget_mode=True
)

# ❌ Bad: Don't use budget mode for critical extraction
model = router.select_model_with_budget_mode(
    task_type=AITaskType.CONTRACT_EXTRACTION,
    low_budget_mode=False  # Keep high precision
)
```

### 2. Estimate Costs Before Batch Operations

```python
# Estimate cost for processing 100 contracts
model = router.select_model(AITaskType.CONTRACT_EXTRACTION)

total_cost = 0
for _ in range(100):
    cost = router.estimate_cost(model, 50000, 5000)
    total_cost += cost

print(f"Total estimated: ${total_cost:.2f}")
```

### 3. Log Model Selections

The router automatically logs all selections:

```python
# This will log:
# - task_type
# - selected model
# - tier
# - budget mode status
# - downgrade reasons (if any)

model = router.select_model_with_budget_mode(
    task_type=AITaskType.RACI_GENERATION,
    low_budget_mode=True
)
```

## Monitoring and Observability

The router integrates with structured logging:

```python
# All selections are logged with context
logger.info(
    "model_selected_with_budget_mode",
    task_type="contract_extraction",
    model="claude-sonnet-4-20250514",
    tier="standard",
    low_budget_mode=False
)
```

## Testing

### Unit Test Example

```python
def test_budget_mode_downgrade():
    router = ModelRouter()

    # Non-critical task should downgrade
    model = router.select_model_with_budget_mode(
        task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
        low_budget_mode=True
    )
    assert model.tier == ModelTier.FLASH

    # Critical task should NOT downgrade
    model = router.select_model_with_budget_mode(
        task_type=AITaskType.CONTRACT_EXTRACTION,
        low_budget_mode=True
    )
    assert model.tier == ModelTier.STANDARD
```

## Performance Considerations

- **Flash (Haiku)**: 3x faster than Sonnet
- **Standard (Sonnet)**: Baseline performance
- **Powerful (Opus)**: 2x slower than Sonnet

Use `model.speed_factor` to estimate response times:

```python
model = router.get_model_by_tier(ModelTier.FLASH)
print(f"Speed factor: {model.speed_factor}x")
# Output: 3.0x (3x faster than baseline)
```

## Migration from Old Code

If you're using the old API, update to:

```python
# Old (deprecated)
from src.modules.ai.model_router import TaskType
model = router.select_model(task_type=TaskType.COHERENCE_ANALYSIS)

# New (recommended)
from src.modules.ai.model_router import AITaskType
model = router.select_model_with_budget_mode(
    task_type=AITaskType.COHERENCE_CHECK,
    low_budget_mode=True
)
```

Note: `TaskType` is still supported as an alias for backward compatibility.
