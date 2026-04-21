# LangSmith Rollout Emergency Runbook

## Preconditions
- `EPIC-LANGSMITH-VALIDATION` is marked done in `C2PRO_MASTER_BACKLOG.md` before rollout activation.
- Rollout control is managed with `LANGSMITH_ROLLOUT_PERCENTAGE` and `LANGSMITH_ROLLOUT_FAIL_OPEN`.

## Rollout Plan
1. Set `LANGSMITH_ROLLOUT_PERCENTAGE=10` and monitor 30 minutes.
2. If alerts remain clean, set `LANGSMITH_ROLLOUT_PERCENTAGE=50` and monitor 60 minutes.
3. If stable, set `LANGSMITH_ROLLOUT_PERCENTAGE=100`.

## Synthetic Load Validation (10,000 requests/day equivalent)
```bash
k6 run apps/api/tests/load/langsmith_rollout_load_test.js \
  -e STAGING_BASE_URL=https://staging.c2pro.app \
  -e LOAD_TEST_PATH=/api/v1/ai/generate \
  -e REQUESTS_PER_DAY=10000 \
  -e TEST_DURATION_MINUTES=30 \
  -e SLA_P95_MS=2000
```

## Failure Scenario: LangSmith API Offline During 50% Phase
Expected behavior:
- Requests routed to traced path may throw SDK/API exceptions.
- Router fail-open fallback shifts affected traced requests to legacy path.
- User-facing request success remains available unless legacy dependency fails.

Immediate mitigation steps:
1. **Rollback command (required):**
```bash
export LANGSMITH_ROLLOUT_PERCENTAGE=0
```
2. Trigger config reload/redeploy for API pods.
3. Confirm fallback path health via synthetic check endpoint.
4. Keep `LANGSMITH_ROLLOUT_FAIL_OPEN=true` until LangSmith incident is resolved.

## Alert References
- `LangSmithTraceFailureRateHigh` (>1% over 5m)
- `AIP99LatencyRegression300ms` (>300ms above baseline P99 over 5m)

## Exit Criteria
- Trace failure rate < 0.5% for 30m.
- P99 latency regression < 100ms for 30m.
- No active critical rollout alerts.
