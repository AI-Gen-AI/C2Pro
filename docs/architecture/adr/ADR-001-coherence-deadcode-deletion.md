# ADR-001: Delete Dead Coherence v0 Code

## Status

Accepted

## Context

TASK-COH-V1-01 starts Coherence Score v1 consolidation by removing duplicate code paths that are not part of the production coherence pipeline. The PRD identifies these files as dead code and requires deletion before Phase 2 changes the canonical scoring path.

Deleted files:

- `apps/api/src/coherence/engine_v2.py`: legacy enhanced engine facade for deterministic and LLM rule execution.
- `apps/api/src/coherence/rules.py`: YAML-backed rule schema/loader used by the deleted v2 engine.
- `apps/api/src/coherence/service.py`: thin repository facade superseded by application use cases and repository adapters.
- `apps/api/src/coherence/services/scoring/calculator.py`: alternate alert-penalty score calculator outside the canonical scoring contract.

## Decision

Delete the four files and remove their package export/test import surfaces. They had no active production import path in the canonical Coherence Score v1 pipeline and keeping them made the architecture ambiguous for Phase 2 consolidation.

## Canonical Paths

- Score aggregation lives in `apps/api/src/coherence/scoring.py::ScoringService`.
- Pipeline execution lives in `apps/api/src/coherence/graph/graph.py` as the 7-node coherence subgraph.
- Rule registration and evaluator lookup live in `apps/api/src/coherence/rules_engine/registry.py`.

## Consequences

Future Coherence Score v1 work must extend the canonical paths above rather than resurrecting deleted v0 code. This supports the forward plan in `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`, especially Phase 2 pipeline consolidation and the later evaluator registry work.
