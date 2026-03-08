# ADR-004: Circuit Breakers for External Services

**Status**: Implemented
**Date**: 2026-03-08
**Priority**: P4.1 Production Hardening

## Context

The C2Pro application depends on multiple external services:
- Anthropic Claude API (AI/LLM)
- OpenAI Embeddings API (RAG)
- Redis/Upstash (Cache)
- Cloudflare R2 (Storage)
- Clerk (Authentication JWKS)

When any of these services become unavailable or slow, cascading failures can occur, causing the entire application to become unresponsive. We needed a resilience pattern to:
1. Fail fast when services are down
2. Prevent hammering failing services
3. Allow automatic recovery when services come back online
4. Provide visibility into service health

## Decision

Implement a **centralized circuit breaker infrastructure** in `src/core/resilience/` with:

1. **CircuitBreaker class**: Async-native 3-state (CLOSED/OPEN/HALF_OPEN) pattern
2. **CircuitBreakerRegistry**: Singleton for managing all circuit breakers
3. **CircuitBreakerSettings**: Pydantic settings for per-service configuration
4. **Decorators**: `@with_circuit_breaker()` for easy integration

### State Diagram

```
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    ▼                                                     │
┌──────────┐  N failures   ┌──────────┐  timeout elapsed  │
│  CLOSED  │──────────────▶│   OPEN   │──────────────────▶│
└──────────┘               └──────────┘                   │
    ▲                                                     │
    │ 2 successes         ┌───────────┐                   │
    └─────────────────────│ HALF_OPEN │◀──────────────────┘
                          └───────────┘
                               │
                               │ any failure
                               ▼
                          ┌──────────┐
                          │   OPEN   │
                          └──────────┘
```

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `src/core/resilience/__init__.py` | Package exports |
| `src/core/resilience/circuit_breaker.py` | Core CB class |
| `src/core/resilience/registry.py` | Singleton registry |
| `src/core/resilience/config.py` | Pydantic settings |
| `src/core/resilience/decorators.py` | Decorator API |

### Services Protected

| Service | Config | Fallback Strategy |
|---------|--------|-------------------|
| Anthropic LLM | threshold=5, timeout=60s | Raise error |
| OpenAI Embeddings | threshold=5, timeout=60s | Raise error |
| Redis Cache | threshold=3, timeout=15s | In-memory cache |
| R2 Storage | threshold=5, timeout=60s | Raise error |
| Clerk JWKS | threshold=3, timeout=30s | Use cached keys |

### Configuration

Environment variables (CB_ prefix):
```bash
CB_ENABLE_CIRCUIT_BREAKERS=true
CB_ANTHROPIC_FAILURE_THRESHOLD=5
CB_ANTHROPIC_RECOVERY_TIMEOUT=60
CB_OPENAI_FAILURE_THRESHOLD=5
CB_REDIS_FAILURE_THRESHOLD=3
CB_REDIS_RECOVERY_TIMEOUT=15
# ... etc
```

### Health Endpoint

```
GET /health/circuit-breakers

{
  "total_breakers": 5,
  "open_circuits": [],
  "breakers": {
    "anthropic_llm": {"state": "closed", "failure_count": 0, ...},
    "openai_embeddings": {"state": "closed", ...},
    ...
  }
}
```

### Prometheus Metrics

- `c2pro_circuit_breaker_state` (Gauge): Current state per service
- `c2pro_circuit_breaker_failures_total` (Counter): Total failures
- `c2pro_circuit_breaker_rejections_total` (Counter): Rejected requests
- `c2pro_circuit_breaker_state_changes_total` (Counter): State transitions

## Usage

### Decorator (Recommended)

```python
from src.core.resilience import with_circuit_breaker

@with_circuit_breaker("my_service", failure_threshold=5, recovery_timeout=60)
async def call_external_service():
    # External API call
    ...
```

### Direct Usage

```python
from src.core.resilience import CircuitBreakerRegistry, CircuitBreakerConfig

cb = CircuitBreakerRegistry.register(
    CircuitBreakerConfig(service_name="my_service", failure_threshold=5)
)

if await cb.can_execute():
    try:
        result = await external_call()
        await cb.record_success()
    except Exception as e:
        await cb.record_failure(e)
        raise
```

## Consequences

### Positive
- Fast failure when services are down (no waiting for timeouts)
- Automatic recovery without manual intervention
- Per-service configuration for fine-tuning
- Full observability via health endpoints and Prometheus
- Thread-safe async implementation

### Negative
- Added complexity in service layer
- Need to handle `CircuitBreakerOpenError` in callers
- Small overhead for circuit breaker state checks

### Neutral
- Excluded exceptions (400-level errors) don't trip circuit
- Global circuit breakers (not per-tenant)

## Test Coverage

- 39 unit tests covering all state transitions, configuration, registry
- Located in `tests/unit/core/resilience/`

## References

- Martin Fowler: https://martinfowler.com/bliki/CircuitBreaker.html
- Microsoft Cloud Design Patterns
