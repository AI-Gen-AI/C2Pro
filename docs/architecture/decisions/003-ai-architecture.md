# ADR 003: AI Architecture

## Status
Accepted

## Context
C2Pro requires deterministic orchestration around extraction, analysis, and coherence scoring while preserving legal traceability and tenant isolation.

## Decision
Use a modular AI architecture with clear boundaries:
- Domain rules and scoring logic remain deterministic and testable.
- Application services orchestrate workflows and ports.
- External model providers are isolated in adapters.

## Consequences
- Positive: Improved auditability, easier testing, and safer model-provider changes.
- Tradeoff: Additional adapter/port design overhead.
- Mitigation: Reuse shared contracts and enforce strict documentation of model interfaces.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added initial ADR scaffold and documented AI architecture boundaries.
