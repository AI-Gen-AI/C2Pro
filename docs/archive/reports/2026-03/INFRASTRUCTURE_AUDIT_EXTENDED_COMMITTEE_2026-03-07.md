# INFRASTRUCTURE AUDIT - EXTENDED COMMITTEE REPORT
## C2Pro - Kubernetes, Performance & CI/CD Analysis

**Date:** 2026-03-07
**Extended Committee:** Kubernetes Architect, Performance Engineer, CI/CD Pipeline Auditor
**Related:** `docs/INFRASTRUCTURE_AUDIT_2026-03-07.md`

---

## KUBERNETES ARCHITECT AGENT REPORT

### K.1 Current State Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Kubernetes manifests | **NOT FOUND** | No k8s/ directory |
| Helm charts | **NOT FOUND** | No charts/ directory |
| Kustomize overlays | **NOT FOUND** | No kustomization.yaml |
| Container registry | **NOT CONFIGURED** | No registry references |

### K.2 Production Readiness Gaps

```
CURRENT STATE                    REQUIRED FOR K8S
+-----------------+             +-----------------------+
| docker-compose  |  ------>    | Deployment            |
| .yml            |             | Service               |
|                 |             | ConfigMap             |
|                 |             | Secret                |
|                 |             | Ingress               |
|                 |             | HPA                   |
|                 |             | PodDisruptionBudget   |
+-----------------+             +-----------------------+
```

### K.3 Recommended Kubernetes Architecture

```yaml
# Proposed structure: k8s/
k8s/
  base/
    namespace.yaml
    deployment-api.yaml
    deployment-worker.yaml
    service-api.yaml
    configmap.yaml
    secret.yaml
    pdb.yaml
    hpa.yaml
  overlays/
    staging/
      kustomization.yaml
      ingress.yaml
    production/
      kustomization.yaml
      ingress.yaml
      resources-patch.yaml
```

### K.4 Kubernetes Migration Plan

| Phase | Task | Priority | Effort |
|-------|------|----------|--------|
| K.1 | Create base Deployment for API | HIGH | 2h |
| K.2 | Create Service and Ingress | HIGH | 1h |
| K.3 | Convert env vars to ConfigMap/Secret | HIGH | 2h |
| K.4 | Add HorizontalPodAutoscaler | MEDIUM | 1h |
| K.5 | Add PodDisruptionBudget | MEDIUM | 30m |
| K.6 | Create Helm chart (optional) | LOW | 4h |
| K.7 | Set up GitOps with ArgoCD/Flux | LOW | 8h |

### K.5 Proposed Deployment Manifest

```yaml
# k8s/base/deployment-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: c2pro-api
  labels:
    app: c2pro
    component: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: c2pro
      component: api
  template:
    metadata:
      labels:
        app: c2pro
        component: api
    spec:
      containers:
      - name: api
        image: c2pro-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: c2pro-config
        - secretRef:
            name: c2pro-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
```

---

## PERFORMANCE ENGINEER AGENT REPORT

### PE.1 Current Observability Stack

| Component | Library | Version | Status |
|-----------|---------|---------|--------|
| Error Tracking | Sentry SDK | >=2.0.0 | CONFIGURED |
| Structured Logging | structlog | 24.1.0 | ACTIVE |
| Metrics | prometheus-client | 0.19.0 | INSTALLED (not exposed) |
| AI Tracing | LangSmith | >=0.1.0 | CONFIGURED |

### PE.2 Prometheus Metrics Gap Analysis

**Current State:** `prometheus-client` is installed but NOT exposed.

**Missing:**
- No `/metrics` endpoint in FastAPI
- No custom application metrics
- No Grafana dashboards
- No alerting rules

### PE.3 Recommended Metrics Implementation

```python
# src/core/metrics.py (TO CREATE)
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import make_asgi_app

# Request metrics
REQUEST_COUNT = Counter(
    'c2pro_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'c2pro_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
)

# AI metrics
AI_REQUESTS = Counter(
    'c2pro_ai_requests_total',
    'Total AI API requests',
    ['model', 'task', 'status']
)

AI_TOKENS = Counter(
    'c2pro_ai_tokens_total',
    'Total AI tokens used',
    ['model', 'direction']  # input/output
)

AI_COST = Counter(
    'c2pro_ai_cost_usd_total',
    'Total AI cost in USD',
    ['model', 'tenant']
)

AI_LATENCY = Histogram(
    'c2pro_ai_latency_seconds',
    'AI request latency',
    ['model', 'task'],
    buckets=[.5, 1, 2, 5, 10, 30, 60, 120]
)

# Database metrics
DB_CONNECTIONS = Gauge(
    'c2pro_db_connections',
    'Active database connections',
    ['state']  # active, idle
)

SLOW_QUERIES = Counter(
    'c2pro_slow_queries_total',
    'Slow queries (>100ms)',
    ['table']
)

# Cache metrics
CACHE_HITS = Counter(
    'c2pro_cache_hits_total',
    'Cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'c2pro_cache_misses_total',
    'Cache misses',
    ['cache_type']
)

# Expose metrics endpoint
metrics_app = make_asgi_app()
```

### PE.4 Database Performance Audit

| Check | Status | Recommendation |
|-------|--------|----------------|
| Connection pooling | CONFIGURED | Pool size 5, overflow 10 |
| Slow query logging | ACTIVE | Threshold 100ms |
| pg_stat_statements | NOT ENABLED | Enable for query analysis |
| Indexes | PARTIAL | Review 008_indexes.sql |
| Query explain plans | NOT AUTOMATED | Add to monitoring |

**PostgreSQL Tuning Recommendations:**
```sql
-- For local development (8GB RAM system)
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';

-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### PE.5 Load Testing Requirements

| Test Type | Tool | Target | Status |
|-----------|------|--------|--------|
| API Load Test | k6 / Locust | 100 RPS | NOT CONFIGURED |
| AI Latency Baseline | Custom | P95 < 5s | NOT MEASURED |
| Database Load | pgbench | 50 TPS | NOT CONFIGURED |
| Cache Performance | redis-benchmark | 10K ops/s | NOT MEASURED |

### PE.6 Performance Monitoring Tasks

| # | Task | Description | Priority |
|---|------|-------------|----------|
| PE.1 | Add /metrics endpoint | Expose Prometheus metrics | HIGH |
| PE.2 | Create Grafana dashboards | API, AI, DB dashboards | HIGH |
| PE.3 | Enable pg_stat_statements | Query performance analysis | MEDIUM |
| PE.4 | Create k6 load tests | API load testing scripts | MEDIUM |
| PE.5 | Add AI cost tracking metrics | Token and cost counters | HIGH |
| PE.6 | Configure alerting rules | Prometheus alertmanager | LOW |

---

## CI/CD PIPELINE AUDITOR AGENT REPORT

### CI.1 Current GitHub Actions Inventory

| Workflow | File | Triggers | Status |
|----------|------|----------|--------|
| Tests | tests.yml | push/PR to main,develop | ACTIVE |
| E2E Security | e2e-security-tests.yml | push/PR | ACTIVE |
| Frontend CI | frontend-ci.yml | push/PR | ACTIVE |
| Frontend E2E | frontend-e2e.yml | push/PR | ACTIVE |
| I13 Real E2E | i13-real-e2e-scheduled.yml | scheduled | ACTIVE |
| Drift Checks | scheduled-drift-checks.yml | scheduled | ACTIVE |

### CI.2 Tests Workflow Analysis (tests.yml)

**Jobs Structure:**
```
+------------------+     +------------------+     +---------------------+
| s5-core-ai-gates |     | unit-tests       |     | integration-tests   |
| (continue-on-err)|     | (Py 3.11, 3.12)  |     | (with Redis)        |
+------------------+     +------------------+     +---------------------+
         |                       |                        |
         v                       v                        v
+------------------+     +------------------+     +---------------------+
| e2e-security-    |     | i13-real-e2e     |     | test-summary        |
| tests            |     | (25min timeout)  |     | (aggregates all)    |
+------------------+     +------------------+     +---------------------+
```

**Strengths:**
- Multi-Python version matrix (3.11, 3.12)
- Proper service containers (Redis)
- Artifact upload for test results
- Test summary aggregation
- Infrastructure diagnostics on failure

**Weaknesses:**
- `continue-on-error: true` on unit tests (hides failures)
- No Docker build caching
- No container image push
- No deployment stages
- No security scanning (Trivy, Snyk)

### CI.3 Pipeline Security Assessment

| Check | Status | Risk |
|-------|--------|------|
| Secrets in workflows | PARTIAL | Mock keys used, acceptable |
| Permissions scoping | GOOD | `contents: read` only |
| Dependency caching | GOOD | pip cache enabled |
| Action versions pinned | GOOD | Using @v4, @v5 |
| OIDC for cloud auth | NOT USED | N/A for now |

### CI.4 Missing CI/CD Components

| Component | Status | Priority |
|-----------|--------|----------|
| Docker build job | MISSING | HIGH |
| Container registry push | MISSING | HIGH |
| Staging deployment | MISSING | MEDIUM |
| Production deployment | MISSING | MEDIUM |
| Security scanning | MISSING | HIGH |
| Dependency updates (Dependabot) | PARTIAL | LOW |
| Release automation | MISSING | LOW |

### CI.5 Recommended Pipeline Architecture

```yaml
# Proposed workflow structure
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # Stage 1: Quality Gates
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .
      - run: mypy src/

  test:
    needs: lint
    strategy:
      matrix:
        python: ['3.11', '3.12']
    # ... existing test logic

  security-scan:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          security-checks: 'vuln,secret,config'

  # Stage 2: Build
  build:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: ./apps/api
          push: true
          tags: ghcr.io/${{ github.repository }}/api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Stage 3: Deploy (develop -> staging)
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          # kubectl apply or helm upgrade

  # Stage 4: Deploy (main -> production)
  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [build, deploy-staging]
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to production
        run: |
          # kubectl apply or helm upgrade
```

### CI.6 CI/CD Improvement Tasks

| # | Task | Description | Priority |
|---|------|-------------|----------|
| CI.1 | Add Docker build job | Build and cache images | HIGH |
| CI.2 | Add GHCR push | Push to container registry | HIGH |
| CI.3 | Add Trivy scanning | Container vulnerability scan | HIGH |
| CI.4 | Remove continue-on-error | Fail pipeline on test failures | MEDIUM |
| CI.5 | Add staging deployment | Deploy develop to staging | MEDIUM |
| CI.6 | Add production deployment | Deploy main to production | MEDIUM |
| CI.7 | Add Dependabot config | Automated dependency updates | LOW |
| CI.8 | Add release workflow | Automated versioning/changelog | LOW |

---

## EXTENDED COMMITTEE SUMMARY

### Overall Production Readiness Score

| Area | Score | Status |
|------|-------|--------|
| Docker/Compose | 75% | Functional, needs fixes |
| Kubernetes | 0% | Not implemented |
| Performance Monitoring | 25% | Partial (Sentry, structlog) |
| CI/CD Pipeline | 60% | Good testing, no deployment |
| Security Scanning | 20% | Manual only |

### Critical Path to Production

```
CURRENT STATE                    PRODUCTION READY
+----------------+              +------------------+
| Docker Compose | ---> K8s --> | Kubernetes       |
| Local Dev      |     Deploy   | Managed Cluster  |
+----------------+              +------------------+
       |                               |
       v                               v
+----------------+              +------------------+
| GitHub Actions | ---> Add --> | Full CI/CD       |
| Tests Only     |     Deploy   | Build + Deploy   |
+----------------+              +------------------+
       |                               |
       v                               v
+----------------+              +------------------+
| Structlog      | ---> Add --> | Full Observability|
| Sentry         |     Metrics  | Prometheus/Grafana|
+----------------+              +------------------+
```

### Priority Recommendations

**Immediate (Week 1):**
1. Fix blocking infrastructure issues (P1 tasks)
2. Add /metrics endpoint for Prometheus
3. Add Docker build job to CI

**Short-term (Week 2-3):**
4. Create basic Kubernetes manifests
5. Add security scanning (Trivy)
6. Set up staging deployment

**Medium-term (Month 1):**
7. Create Grafana dashboards
8. Add production deployment workflow
9. Implement load testing

---

## TRACKING

All extended committee tasks are tracked in:
`docs/INFRASTRUCTURE_RECOVERY_TRACKER.md`

| Agent | Tasks Added | Status |
|-------|-------------|--------|
| Kubernetes (K) | 5 tasks | All PENDING |
| Performance (PE) | 5 tasks | All PENDING |
| CI/CD (CI) | 5 tasks | All PENDING |
