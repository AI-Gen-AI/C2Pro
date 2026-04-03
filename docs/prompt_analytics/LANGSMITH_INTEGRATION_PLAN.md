# LangSmith Integration Plan for TASK-216
## Prompt Analytics Dashboard Implementation

**Status**: Planning
**Priority**: P1
**Owner**: Backend Team
**Target**: 2026-Q2
**Dependencies**: Backend API, LangSmith Account Setup

---

## Overview

Integrate LangSmith to provide comprehensive prompt analytics, versioning, A/B testing, and cost tracking for all AI-powered features in C2Pro.

**Why LangSmith?**
- Purpose-built for LLM observability and prompt management
- Native support for prompt versioning and A/B testing
- Built-in analytics dashboards and cost tracking
- Seamless integration with LangChain/LangGraph (already used in Coherence Engine)
- Automatic trace capture and debugging tools

---

## Architecture

### Current State
```
apps/api/src/core/ai/
├── templates/           # Jinja2 prompt templates
│   ├── coherence_llm_v1.0.jinja2
│   ├── evidence_extraction_v1.0.jinja2
│   └── risk_analysis_v2.1.jinja2
├── prompt_loader.py     # Template loading and rendering
└── usage_logger.py      # Logs to ai_usage_logs table
```

**Database**: `ai_usage_logs` table tracks:
- `prompt_template_name`, `prompt_version`
- `tokens_input`, `tokens_output`, `cost_usd`
- `model_name`, `latency_ms`
- `tenant_id`, `user_id`, `created_at`

### Target State (with LangSmith)

```
┌─────────────────────────────────────────────────────────────┐
│                      LangSmith Cloud                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Prompt Hub │  │  Trace Store │  │  Analytics APIs  │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ LangSmith SDK
                            │
┌─────────────────────────────────────────────────────────────┐
│                    C2Pro Backend API                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  LangSmith Wrapper (apps/api/src/core/ai/)         │    │
│  │  ├── langsmith_client.py   # SDK initialization    │    │
│  │  ├── prompt_registry.py    # Sync templates → Hub  │    │
│  │  └── traced_llm_call.py    # Auto-trace decorator  │    │
│  └────────────────────────────────────────────────────┘    │
│                            ▲                                 │
│                            │                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Existing AI Modules                                │    │
│  │  ├── coherence/llm_integration.py                   │    │
│  │  ├── evidence/extraction_service.py                 │    │
│  │  └── risk/analysis_service.py                       │    │
│  └────────────────────────────────────────────────────┘    │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │  PostgreSQL                                         │    │
│  │  └── ai_usage_logs (enhanced with trace_id)        │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────┐
│                     C2Pro Frontend                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Prompt Analytics Dashboard                         │    │
│  │  ├── VersionComparisonView                          │    │
│  │  ├── CostAnalysisView                               │    │
│  │  ├── QualityDriftChart                              │    │
│  │  └── UsageMetricsTable                              │    │
│  └────────────────────────────────────────────────────┘    │
│                            │                                 │
│  GET /api/v1/ai/analytics/{metric}?version=...&range=...   │
└─────────────────────────────────────────────────────────────┘
```

**Data Flow**:
1. **Prompt Registration**: Push all Jinja2 templates to LangSmith Prompt Hub on deployment
2. **Runtime Tracing**: Every LLM call auto-traced via `@traced_llm_call` decorator
3. **Dual Logging**: Write trace_id to `ai_usage_logs` for local retention + query
4. **Analytics APIs**: Backend fetches metrics from LangSmith + local DB
5. **Dashboard Rendering**: Frontend visualizes version comparisons, cost trends, quality drift

---

## Implementation Phases

### Phase 1: LangSmith Setup & Integration (Week 1-2)

**Tasks**:
- [ ] **TASK-1119** (P1): Create LangSmith organization account, generate API keys
- [ ] **TASK-1120** (P1): Add `langsmith` SDK to `apps/api/pyproject.toml`
- [ ] **TASK-1121** (P1): Implement `langsmith_client.py` wrapper with:
  - Environment-based config (`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`)
  - Client initialization with error handling
  - Helper methods: `create_run()`, `end_run()`, `log_feedback()`
- [ ] **TASK-1122** (P1): Create `@traced_llm_call` decorator for automatic tracing
- [ ] **TASK-1123** (P2): Add `trace_id` column to `ai_usage_logs` table (nullable, indexed)

**Acceptance Criteria**:
- LangSmith client initializes successfully in dev/staging/prod
- Simple test call creates a trace visible in LangSmith UI
- `trace_id` persisted to local DB for cross-reference

**Migration SQL**:
```sql
ALTER TABLE ai_usage_logs
ADD COLUMN trace_id UUID NULL;

CREATE INDEX idx_ai_usage_logs_trace_id ON ai_usage_logs(trace_id);

COMMENT ON COLUMN ai_usage_logs.trace_id IS 'LangSmith trace ID for cross-referencing';
```

---

### Phase 2: Prompt Registry & Versioning (Week 3-4)

**Tasks**:
- [ ] **TASK-1124** (P1): Implement `prompt_registry.py`:
  - `sync_template_to_hub(template_name, version, jinja_content)` — push to LangSmith
  - `pull_template_from_hub(template_name, version)` — fetch from LangSmith
  - `list_template_versions(template_name)` — get version history
- [ ] **TASK-1125** (P1): Create CLI command `python -m core.ai.sync_prompts` to push all templates on deployment
- [ ] **TASK-1126** (P2): Add prompt metadata to LangSmith (owner, description, tags)
- [ ] **TASK-1127** (P2): Implement A/B test config in LangSmith Hub (gradual rollout)

**Acceptance Criteria**:
- All existing templates (`coherence_llm_v1.0`, `evidence_extraction_v1.0`, etc.) synced to LangSmith Hub
- Version history visible in LangSmith UI
- Ability to roll back to previous version via Hub UI or API

**Example Usage**:
```python
from core.ai.prompt_registry import sync_template_to_hub

sync_template_to_hub(
    template_name="coherence_llm",
    version="1.0",
    jinja_content=Path("templates/coherence_llm_v1.0.jinja2").read_text(),
    metadata={
        "owner": "backend-team",
        "description": "LLM evaluator for coherence scoring",
        "tags": ["coherence", "production"]
    }
)
```

---

### Phase 3: Enhanced Tracing & Feedback (Week 5-6)

**Tasks**:
- [ ] **TASK-1128** (P1): Enhance `@traced_llm_call` decorator to capture:
  - Input prompt (rendered Jinja2)
  - Model parameters (temperature, max_tokens, etc.)
  - Output completion
  - Token counts and cost (derived from model pricing)
  - Latency (end-to-end ms)
- [ ] **TASK-1129** (P1): Integrate with existing `usage_logger.py` to write both:
  - LangSmith trace (via SDK)
  - Local `ai_usage_logs` row (with `trace_id` FK)
- [ ] **TASK-1130** (P2): Implement feedback collection API:
  - `POST /api/v1/ai/feedback` — user thumbs up/down on AI output
  - Writes to LangSmith + local DB for quality analysis
- [ ] **TASK-1131** (P2): Add trace URL to `ai_usage_logs` for debugging

**Acceptance Criteria**:
- Every LLM call creates a trace in LangSmith with full input/output
- `ai_usage_logs` row includes `trace_id` and `trace_url`
- User feedback (thumbs up/down) recorded in LangSmith for quality metrics

**Database Schema Update**:
```sql
ALTER TABLE ai_usage_logs
ADD COLUMN trace_url TEXT NULL;

COMMENT ON COLUMN ai_usage_logs.trace_url IS 'LangSmith trace URL for debugging (e.g., https://smith.langchain.com/o/.../runs/...)';
```

---

### Phase 4: Analytics Backend APIs (Week 7-8)

**Tasks**:
- [ ] **TASK-1132** (P1): Implement `GET /api/v1/ai/analytics/versions` — list all prompt versions with stats
- [ ] **TASK-1133** (P1): Implement `GET /api/v1/ai/analytics/comparison` — compare two versions:
  - Avg tokens (input/output)
  - Avg cost per call
  - Call volume over time
  - Quality score (from feedback)
- [ ] **TASK-1134** (P1): Implement `GET /api/v1/ai/analytics/cost-breakdown` — cost by prompt version & model
- [ ] **TASK-1135** (P1): Implement `GET /api/v1/ai/analytics/quality-drift` — quality trend over time
- [ ] **TASK-1136** (P2): Add caching layer (Redis) for expensive analytics queries

**API Examples**:

```http
GET /api/v1/ai/analytics/versions?template=coherence_llm
Response:
{
  "versions": [
    {
      "version": "1.0",
      "total_calls": 1523,
      "avg_tokens_input": 412,
      "avg_tokens_output": 87,
      "avg_cost_usd": 0.0032,
      "avg_latency_ms": 1240,
      "quality_score": 0.87,  // from user feedback
      "last_used_at": "2026-04-02T14:23:00Z"
    },
    {
      "version": "2.0",
      "total_calls": 89,
      "avg_tokens_input": 385,
      "avg_tokens_output": 92,
      "avg_cost_usd": 0.0028,
      "avg_latency_ms": 1180,
      "quality_score": 0.91,
      "last_used_at": "2026-04-03T09:12:00Z"
    }
  ]
}
```

```http
GET /api/v1/ai/analytics/comparison?template=coherence_llm&version_a=1.0&version_b=2.0&date_range=30d
Response:
{
  "version_a": {...},
  "version_b": {...},
  "delta": {
    "tokens_input_pct": -6.5,     // v2.0 uses 6.5% fewer input tokens
    "tokens_output_pct": +5.7,
    "cost_pct": -12.5,             // v2.0 is 12.5% cheaper
    "latency_pct": -4.8,
    "quality_pct": +4.6            // v2.0 has 4.6% better quality score
  },
  "time_series": [
    {"date": "2026-03-04", "version_a_calls": 52, "version_b_calls": 3, "version_a_cost": 0.17, "version_b_cost": 0.01},
    {"date": "2026-03-05", "version_a_calls": 48, "version_b_calls": 5, "version_a_cost": 0.15, "version_b_cost": 0.014},
    // ... daily breakdown
  ]
}
```

---

### Phase 5: Frontend Dashboard (Week 9-10)

**Tasks**:
- [ ] **TASK-1137** (P1): Create `PromptAnalyticsDashboard` page route `/analytics/prompts`
- [ ] **TASK-1138** (P1): Implement `VersionComparisonView` component:
  - Dropdown to select template
  - Dropdown to select two versions (A vs B)
  - Date range picker (7d, 30d, 90d, custom)
  - Comparison table (tokens, cost, latency, quality)
  - Delta indicators (↑ ↓ with % change)
- [ ] **TASK-1139** (P1): Implement `CostAnalysisView` component:
  - Stacked bar chart: cost breakdown by prompt version
  - Pie chart: cost by model (gpt-4, claude-3, etc.)
  - Total spend trend line over time
- [ ] **TASK-1140** (P1): Implement `QualityDriftChart` component:
  - Line chart: quality score (from feedback) over time per version
  - Anomaly detection: highlight quality drops >10%
- [ ] **TASK-1141** (P2): Implement `UsageMetricsTable` component:
  - Table: all versions with call volume, avg cost, quality
  - Sortable columns
  - Export to CSV button
- [ ] **TASK-1142** (P2): Add LangSmith trace deep-link from AI usage logs page

**UI Mockup** (simplified ASCII wireframe):

```
┌─────────────────────────────────────────────────────────────────┐
│  Prompt Analytics Dashboard                          [Date Range]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Template: [coherence_llm ▼]   Version A: [1.0 ▼]  vs  [2.0 ▼] │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Metric Comparison                                        │  │
│  │  ┌────────────────┬─────────┬─────────┬─────────────┐    │  │
│  │  │ Metric         │ v1.0    │ v2.0    │ Delta       │    │  │
│  │  ├────────────────┼─────────┼─────────┼─────────────┤    │  │
│  │  │ Avg Tokens In  │ 412     │ 385     │ ↓ -6.5%     │    │  │
│  │  │ Avg Tokens Out │ 87      │ 92      │ ↑ +5.7%     │    │  │
│  │  │ Avg Cost       │ $0.0032 │ $0.0028 │ ↓ -12.5% ✓  │    │  │
│  │  │ Avg Latency    │ 1240ms  │ 1180ms  │ ↓ -4.8%  ✓  │    │  │
│  │  │ Quality Score  │ 0.87    │ 0.91    │ ↑ +4.6%  ✓  │    │  │
│  │  └────────────────┴─────────┴─────────┴─────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Cost Trend (Last 30 Days)                                │  │
│  │  ┌──────────────────────────────────────────────────┐    │  │
│  │  │         ___                                       │    │  │
│  │  │  $0.20 |   \___                                   │    │  │
│  │  │  $0.15 |       \____                              │    │  │
│  │  │  $0.10 |            \____                         │    │  │
│  │  │  $0.05 |                 \____                    │    │  │
│  │  │  $0.00 └─────────────────────────────────────────│    │  │
│  │  │        Mar 4    Mar 14    Mar 24    Apr 3        │    │  │
│  │  │        ■ v1.0   ■ v2.0   (stacked)               │    │  │
│  │  └──────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Quality Drift Detection                                  │  │
│  │  ┌──────────────────────────────────────────────────┐    │  │
│  │  │ 1.0 ────────────────────────────────────────     │    │  │
│  │  │ 0.9                                          ●───│    │  │
│  │  │ 0.8 ─●──●──●──●──●──●──●──                       │    │  │
│  │  │ 0.7                                               │    │  │
│  │  │ 0.6 └─────────────────────────────────────────   │    │  │
│  │  │     Mar 4    Mar 14    Mar 24    Apr 3           │    │  │
│  │  │     ● v1.0   ● v2.0                              │    │  │
│  │  └──────────────────────────────────────────────────┘    │  │
│  │  ⚠️  Quality drop detected: v1.0 dropped 8% on Mar 20   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [Export CSV]  [View in LangSmith →]                           │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 6: Testing & Rollout (Week 11-12)

**Tasks**:
- [ ] **TASK-1143** (P1): Write unit tests for LangSmith client wrapper (mock SDK)
- [ ] **TASK-1144** (P1): Write integration tests for analytics APIs (use test DB + mock LangSmith)
- [ ] **TASK-1145** (P1): Write E2E tests for dashboard (Playwright)
- [ ] **TASK-1146** (P2): Load testing: 10k LLM calls/day with tracing enabled
- [ ] **TASK-1147** (P1): Deploy to staging, verify traces appear in LangSmith
- [ ] **TASK-1148** (P1): Gradual rollout to production (10% → 50% → 100%)
- [ ] **TASK-1149** (P2): Documentation: usage guide for data scientists and PM
- [ ] **TASK-1150** (P2): Set up monitoring alerts for trace failures or high latency

**Acceptance Criteria**:
- 80%+ test coverage on new modules
- E2E test validates full flow: LLM call → trace → analytics API → dashboard render
- No performance degradation (<5% latency increase)
- Dashboard accessible to internal users with correct RBAC

---

## Technical Specifications

### LangSmith SDK Integration

**Installation**:
```toml
# apps/api/pyproject.toml
[project]
dependencies = [
    "langsmith>=0.1.0",
    # ... existing deps
]
```

**Configuration** (`apps/api/src/core/ai/langsmith_client.py`):
```python
import os
from langsmith import Client
from langsmith.run_trees import RunTree

class LangSmithClient:
    """Wrapper for LangSmith SDK with C2Pro-specific config."""

    def __init__(self):
        api_key = os.getenv("LANGSMITH_API_KEY")
        if not api_key:
            raise ValueError("LANGSMITH_API_KEY not set")

        self.client = Client(
            api_key=api_key,
            api_url=os.getenv("LANGSMITH_API_URL", "https://api.smith.langchain.com")
        )
        self.project_name = os.getenv("LANGSMITH_PROJECT", "c2pro-production")

    def create_run(
        self,
        name: str,
        run_type: str = "llm",
        inputs: dict | None = None,
        **kwargs
    ) -> RunTree:
        """Create a new traced run."""
        return RunTree(
            name=name,
            run_type=run_type,
            inputs=inputs or {},
            project_name=self.project_name,
            client=self.client,
            **kwargs
        )

    def log_feedback(
        self,
        run_id: str,
        key: str,
        score: float,
        comment: str | None = None
    ):
        """Log user feedback for a traced run."""
        self.client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment
        )
```

**Traced Decorator** (`apps/api/src/core/ai/traced_llm_call.py`):
```python
import functools
import time
from typing import Callable
from .langsmith_client import LangSmithClient
from .usage_logger import log_ai_usage

langsmith_client = LangSmithClient()

def traced_llm_call(
    template_name: str,
    version: str,
    model_name: str
):
    """Decorator to auto-trace LLM calls to LangSmith + local DB."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            # Extract inputs for tracing
            inputs = {
                "template_name": template_name,
                "version": version,
                "model": model_name,
                "args": str(args),
                "kwargs": str(kwargs)
            }

            # Create LangSmith run
            run = langsmith_client.create_run(
                name=f"{template_name}_v{version}",
                run_type="llm",
                inputs=inputs
            )

            try:
                # Execute the LLM call
                result = await func(*args, **kwargs)

                # Record output and finalize
                run.end(outputs={"result": result})
                run.post()

                # Log to local DB
                elapsed_ms = (time.time() - start_time) * 1000
                await log_ai_usage(
                    prompt_template_name=template_name,
                    prompt_version=version,
                    model_name=model_name,
                    tokens_input=result.get("usage", {}).get("prompt_tokens", 0),
                    tokens_output=result.get("usage", {}).get("completion_tokens", 0),
                    cost_usd=calculate_cost(model_name, result.get("usage", {})),
                    latency_ms=elapsed_ms,
                    trace_id=run.id,
                    trace_url=run.url
                )

                return result

            except Exception as e:
                run.end(error=str(e))
                run.post()
                raise

        return wrapper
    return decorator
```

**Usage Example**:
```python
from core.ai.traced_llm_call import traced_llm_call
from core.ai.prompt_loader import render_template

@traced_llm_call(
    template_name="coherence_llm",
    version="1.0",
    model_name="gpt-4"
)
async def evaluate_coherence_with_llm(clauses: list[Clause]) -> dict:
    prompt = render_template("coherence_llm_v1.0.jinja2", {"clauses": clauses})

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return {
        "result": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens
        }
    }
```

---

## Migration Strategy

### Phase 0: Preparation (Pre-implementation)
1. Create LangSmith organization account (https://smith.langchain.com)
2. Generate API keys for dev/staging/prod environments
3. Add API keys to secret manager (AWS Secrets Manager / Vault)
4. Set up project structure in LangSmith UI:
   - Project: `c2pro-development`
   - Project: `c2pro-staging`
   - Project: `c2pro-production`

### Gradual Rollout
1. **Week 1-2**: Dev environment only, manual testing
2. **Week 3-6**: Staging environment, automated tests
3. **Week 7**: Production rollout at 10% traffic (feature flag)
4. **Week 8**: Production rollout at 50% traffic
5. **Week 9**: Production rollout at 100% traffic
6. **Week 10+**: Monitor, optimize, iterate

### Backward Compatibility
- Keep existing `ai_usage_logs` table structure intact
- `trace_id` and `trace_url` columns are nullable — existing rows unaffected
- Existing analytics queries continue to work without modification
- New analytics APIs are additive, not replacements

---

## Cost Estimation

**LangSmith Pricing** (as of 2026-04):
- Free tier: 5,000 traces/month
- Developer: $39/month (50,000 traces/month)
- Team: $199/month (500,000 traces/month)
- Enterprise: Custom pricing (1M+ traces/month)

**C2Pro Current Usage** (estimated):
- Coherence LLM calls: ~2,000/day = 60,000/month
- Evidence extraction: ~1,500/day = 45,000/month
- Risk analysis: ~800/day = 24,000/month
- **Total**: ~129,000 traces/month

**Recommended Plan**: Team ($199/month) with headroom for growth.

**ROI**:
- **Cost savings from prompt optimization**: 10-15% reduction in token usage = $500-800/month saved
- **Reduced debugging time**: 5-10 hours/month saved = $500-1,000/month (engineer time)
- **Quality improvements**: Fewer hallucinations/errors = reduced support tickets
- **Net benefit**: $800-1,600/month savings, ROI within 2-3 months

---

## Success Metrics

### Technical Metrics
- [ ] 100% of LLM calls traced to LangSmith (target: 99.5%+ after rollout)
- [ ] <50ms tracing overhead per LLM call (p95 latency)
- [ ] Analytics API response time <500ms (p95)
- [ ] Dashboard load time <2s

### Business Metrics
- [ ] 10% reduction in average token usage within 3 months (via prompt optimization)
- [ ] 15% improvement in user satisfaction with AI features (measured via feedback)
- [ ] 50% reduction in time-to-resolution for AI debugging incidents
- [ ] 3+ A/B tests run per quarter on critical prompts

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LangSmith service outage affects production | High | Low | Graceful degradation: log to local DB only, queue traces for retry |
| Tracing overhead degrades API latency | Medium | Medium | Async trace posting, batch uploads, circuit breaker |
| PII/sensitive data leaked to LangSmith | Critical | Low | Sanitize prompts before tracing, enable LangSmith PII redaction |
| Cost overruns from excessive tracing | Medium | Low | Set quota alerts, implement sampling for high-volume endpoints |
| Team learning curve delays adoption | Low | Medium | Training sessions, documentation, pair programming |

**PII Handling**:
- **Sanitization**: Strip user emails, names, financial data before tracing
- **LangSmith PII Redaction**: Enable built-in redaction for common PII patterns
- **Audit Trail**: Log all trace creations for compliance review

---

## Dependencies

### External Services
- LangSmith Cloud (https://smith.langchain.com)
- LangSmith Python SDK (https://github.com/langchain-ai/langsmith-sdk)

### Internal Components
- `apps/api/src/core/ai/prompt_loader.py` — template rendering
- `apps/api/src/core/ai/usage_logger.py` — local DB logging
- `apps/api/src/coherence/llm_integration.py` — existing LLM caller
- `apps/web/app/(app)/analytics/` — frontend dashboard container

### Database Schema Changes
```sql
-- Migration: Add LangSmith trace tracking
ALTER TABLE ai_usage_logs
ADD COLUMN trace_id UUID NULL,
ADD COLUMN trace_url TEXT NULL;

CREATE INDEX idx_ai_usage_logs_trace_id ON ai_usage_logs(trace_id);

COMMENT ON COLUMN ai_usage_logs.trace_id IS 'LangSmith trace ID for cross-referencing';
COMMENT ON COLUMN ai_usage_logs.trace_url IS 'LangSmith trace URL for debugging';
```

---

## Team Responsibilities

| Role | Responsibilities |
|------|------------------|
| Backend Team | Phases 1-4: LangSmith integration, analytics APIs, tracing infrastructure |
| Frontend Team | Phase 5: Dashboard UI/UX, charting components, API integration |
| DevOps | LangSmith account setup, secret management, deployment automation |
| QA | Phase 6: Test plan execution, regression testing, load testing |
| Product Manager | Requirements validation, A/B test design, success metrics tracking |
| Data Science | Prompt optimization experiments, quality drift analysis |

---

## Next Steps (Immediate Actions)

1. **[ ] Create LangSmith organization** — DevOps to set up accounts and API keys (ETA: 1 day)
2. **[ ] Spike: LangSmith SDK integration** — Backend to build POC with single traced call (ETA: 2 days)
3. **[ ] Design review: Analytics API contracts** — Backend + Frontend alignment (ETA: 1 day)
4. **[ ] Prioritize Phase 1 tasks in backlog** — PM to create JIRA/Linear tickets (ETA: 1 day)
5. **[ ] Kickoff meeting** — All stakeholders align on timeline and roles (ETA: 1 week)

---

## References

- **LangSmith Documentation**: https://docs.smith.langchain.com/
- **LangSmith Python SDK**: https://github.com/langchain-ai/langsmith-sdk
- **PROMPT_TEMPLATES_GUIDE.md**: `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md`
- **TASK-216**: C2PRO_MASTER_BACKLOG.md, line 98
- **Coherence Engine Integration**: `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md`

---

*Document Version*: 1.0
*Last Updated*: 2026-04-03
*Author*: Backend Team + AI Assistant
*Status*: Draft → Ready for Review
