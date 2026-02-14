# ADR 001: Monolith-First

## Status
Accepted

## Context
The current delivery phase prioritizes speed of iteration, strict tenant isolation, and traceable feature delivery over early distributed-system complexity.

## Decision
Use a modular monolith as the default architecture for C2Pro until operational metrics justify service extraction.

## Consequences
- Positive: Faster delivery, simpler deployment, easier debugging and observability.
- Tradeoff: Independent scaling by capability is limited in early phases.
- Mitigation: Keep clear module boundaries and ports to preserve extraction readiness.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added initial ADR scaffold and formalized decision state.
