# HITL Resume Monitoring Runbook

Operational reference for the Human-in-the-Loop (HITL) workflow resume endpoint
(`POST /api/v1/hitl/resume/{review_id}`). Covers the metrics emitted,
dashboard queries, and paging thresholds.

Implementation: `src/core/observability/monitoring.py`,
`src/modules/hitl/application/resume_workflow_use_case.py`,
`src/modules/hitl/adapters/http/router.py`.

## Metrics emitted

All metrics are exposed via the Prometheus `/metrics` endpoint and mirrored
to DataDog when `DD_AGENT_HOST` (or `DATADOG_STATSD_HOST`) is set.

| Metric                                            | Type      | Labels                     | Purpose                                              |
| ------------------------------------------------- | --------- | -------------------------- | ---------------------------------------------------- |
| `c2pro_hitl_resume_total`                         | counter   | `decision`, `status`       | Every resume attempt; status is final outcome.       |
| `c2pro_hitl_resume_latency_seconds`               | histogram | `decision`                 | End-to-end latency of the use case.                  |
| `c2pro_hitl_resume_errors_total`                  | counter   | `error_type`               | Generic failure bucket (legacy).                     |
| `c2pro_hitl_checkpoint_load_errors_total`         | counter   | `reason`                   | Failed checkpoint loads by reason (`not_found`, …). |
| `c2pro_hitl_workflow_resume_errors_total`         | counter   | `decision`                 | Failed `graph_app.aupdate_state` calls.              |
| `c2pro_hitl_decision_total`                       | counter   | `tenant_id`, `decision`    | Tenant-scoped decision count.                        |
| `c2pro_hitl_approval_rate`                        | gauge     | `tenant_id`                | Running approve-ratio per tenant (process-local).    |
| `c2pro_hitl_review_items_pending`                 | gauge     | `tenant_id`                | Pending review items (updated by gauge refresher).   |
| `c2pro_hitl_review_items_total`                   | gauge     | `tenant_id`                | Total review items.                                  |

> The `c2pro_hitl_approval_rate` gauge is process-local and intended for
> quick operator feedback. For cluster-wide accuracy, use the PromQL
> recipe below derived from `c2pro_hitl_decision_total`.

## Structured log events

| Event                          | Emitted when                                             | Key fields                                                        |
| ------------------------------ | -------------------------------------------------------- | ----------------------------------------------------------------- |
| `loading_checkpoint`           | Before hitting PostgreSQL for the checkpoint.            | `review_id`, `thread_id`, `checkpoint_id`                         |
| `state_updated`                | After `state["human_feedback"]` injection.               | `review_id`, `decision`, `feedback_length`                        |
| `resuming_workflow`            | On APPROVE before `aupdate_state`.                       | `review_id`, `thread_id`                                          |
| `workflow_resumed`             | On APPROVE after `aupdate_state` succeeds.               | `review_id`, `thread_id`, `status`                                |
| `workflow_terminated`          | On REJECT, state marked `workflow_terminated = True`.    | `review_id`, `thread_id`, `reason`                                |
| `workflow_resumption_failed`   | `aupdate_state` raised (swallowed).                      | `review_id`, `thread_id`, `error`                                 |
| `hitl_decision_recorded`       | End of the use case (audit line).                        | `review_id`, `thread_id`, `decision`, `status`, `latency_seconds` |

`hitl_decision_recorded` is the canonical audit entry — point your
SIEM/log-pipeline filters at this event.

## Dashboard queries (PromQL)

### Throughput and latency

```promql
# Resumes per minute, broken down by decision
sum by (decision) (rate(c2pro_hitl_resume_total[1m])) * 60

# p50 / p95 / p99 latency
histogram_quantile(0.50, sum by (le, decision) (rate(c2pro_hitl_resume_latency_seconds_bucket[5m])))
histogram_quantile(0.95, sum by (le, decision) (rate(c2pro_hitl_resume_latency_seconds_bucket[5m])))
histogram_quantile(0.99, sum by (le, decision) (rate(c2pro_hitl_resume_latency_seconds_bucket[5m])))
```

### Cluster-wide approval rate (preferred over the gauge)

```promql
sum by (tenant_id) (rate(c2pro_hitl_decision_total{decision="approve"}[1h]))
/
sum by (tenant_id) (rate(c2pro_hitl_decision_total[1h]))
```

### Error breakdown

```promql
# Any resume error in the last 15 minutes
sum(increase(c2pro_hitl_resume_errors_total[15m]))

# Checkpoint load failures by reason
sum by (reason) (increase(c2pro_hitl_checkpoint_load_errors_total[15m]))

# Workflow resume failures by decision
sum by (decision) (increase(c2pro_hitl_workflow_resume_errors_total[15m]))
```

### Top rejection reasons (log-derived)

Filter logs where `event="hitl_decision_recorded" AND decision="reject"` and
aggregate by the `feedback_length`-truncated feedback (stored in the
`metadata.review_decision` field of the review item). PromQL cannot
enumerate free-text reasons; this is intentionally a log-layer query.

## Alert rules

Target SLO: **99% of resume operations complete under 2s; p99 < 10s;
resume-error rate < 1%; approval rate within ±15% of a 7-day baseline.**

```yaml
# prometheus alert rules
groups:
  - name: hitl_resume
    interval: 30s
    rules:
      # P0 - sustained resume failures
      - alert: HITLResumeErrorsSpike
        expr: sum(increase(c2pro_hitl_resume_errors_total[15m])) > 5
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "HITL resume errors > 5 in 15m"
          runbook: docs/runbooks/HITL_RESUME_MONITORING.md

      # P1 - latency regression
      - alert: HITLResumeLatencyHigh
        expr: |
          histogram_quantile(
            0.95,
            sum by (le) (rate(c2pro_hitl_resume_latency_seconds_bucket[10m]))
          ) > 10
        for: 10m
        labels:
          severity: high
          team: platform
        annotations:
          summary: "HITL resume p95 latency > 10s for 10m"

      # P2 - rejection rate anomaly
      - alert: HITLRejectionRateHigh
        expr: |
          (
            sum(rate(c2pro_hitl_decision_total{decision="reject"}[1h]))
            /
            sum(rate(c2pro_hitl_decision_total[1h]))
          ) > 0.5
        for: 1h
        labels:
          severity: medium
          team: product
        annotations:
          summary: "HITL rejection rate > 50% for the last hour"

      # P2 - checkpoint infrastructure degraded
      - alert: HITLCheckpointLoadFailures
        expr: |
          sum(increase(c2pro_hitl_checkpoint_load_errors_total[5m])) > 3
        for: 5m
        labels:
          severity: high
          team: platform
        annotations:
          summary: "LangGraph checkpoint loads are failing"
```

## DataDog parity

When DataDog is configured, the same telemetry appears under the
`c2pro.hitl.*` namespace:

- `c2pro.hitl.resume_attempt` (increment, tags: `decision`, `status`)
- `c2pro.hitl.resume_latency_seconds` (histogram, tags: `decision`)
- `c2pro.hitl.resume_errors` (increment, tags: `error_type`)
- `c2pro.hitl.checkpoint_load_errors` (increment, tags: `reason`)
- `c2pro.hitl.workflow_resume_errors` (increment, tags: `decision`)
- `c2pro.hitl.decision` (increment, tags: `tenant_id`, `decision`)
- `c2pro.hitl.approval_rate` (gauge, tags: `tenant_id`)

Env vars: `DD_AGENT_HOST` (required to activate), `DD_DOGSTATSD_PORT`
(default `8125`), `DD_NAMESPACE` (default `c2pro`).

## Verification checklist

- [ ] `curl -s $API/metrics | grep c2pro_hitl_` returns all 9 HITL metric names.
- [ ] A sample resume request emits one increment of `c2pro_hitl_resume_total`
      and one `c2pro_hitl_decision_total` for the caller tenant.
- [ ] `hitl_decision_recorded` log lines include `decision`, `status`, and
      `latency_seconds` fields.
- [ ] DataDog dashboards populate within 1m of a test resume (if configured).
