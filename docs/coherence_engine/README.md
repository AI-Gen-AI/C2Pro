# Coherence Engine

**Lifecycle:** Supporting domain reference  
**Reconciled:** 2026-10-01

This section contains Coherence-specific implementation/scoring reference material.

The durable architecture authority is [ADR-009](../architecture/decisions/ADR-009-evidence-oriented-coherence-orchestration.md) together with the current [technical baseline](../architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md). Product realization/deployment/validation state is owned by Product Control.

## Semantic boundary

Coherence answers whether reconcilable project facts agree. It is **not** the same as Health/coverage and it is **not** alert severity.

Unsupported evidence remains Unknown/null.

## Contents

- [Engine v2 integration](./CE-26_ENGINE_V2_INTEGRATION.md)
- [Scoring methodology v1](./scoring_methodology_v1.md)
- phase reports/specifications in this directory are implementation history/supporting detail unless explicitly promoted by an ADR

## Related

- [Documentation authority](../DOCUMENTATION_AUTHORITY.md)
- [Architecture](../architecture/README.md)
- [Product control](../product/00-c2pro-master-product-control-v1.md)
- [Specifications](../specifications/README.md)
