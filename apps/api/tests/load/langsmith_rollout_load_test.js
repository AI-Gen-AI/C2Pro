import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const BASE_URL = __ENV.STAGING_BASE_URL || 'http://localhost:8000';
const API_PATH = __ENV.LOAD_TEST_PATH || '/api/v1/analysis/health';
const BEARER_TOKEN = __ENV.LOAD_TEST_BEARER_TOKEN || '';

const REQUESTS_PER_DAY = Number(__ENV.REQUESTS_PER_DAY || 10000);
const TEST_DURATION_MINUTES = Number(__ENV.TEST_DURATION_MINUTES || 30);
const SLA_P95_MS = Number(__ENV.SLA_P95_MS || 2000);

const tracesFailureRate = new Rate('langsmith_trace_failures');
const endToEndLatency = new Trend('langsmith_e2e_latency_ms');

export const options = {
  scenarios: {
    ai_trace_rollout: {
      executor: 'constant-arrival-rate',
      rate: Math.ceil(REQUESTS_PER_DAY / (24 * 60)),
      timeUnit: '1m',
      duration: `${TEST_DURATION_MINUTES}m`,
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: [`p(95)<${SLA_P95_MS}`],
    langsmith_trace_failures: ['rate<0.01'],
    langsmith_e2e_latency_ms: [`p(95)<${SLA_P95_MS}`],
  },
};

function makePayload(iteration) {
  return JSON.stringify({
    request_id: `k6-${__VU}-${iteration}`,
    tenant_id: __ENV.LOAD_TEST_TENANT_ID || '00000000-0000-0000-0000-000000000001',
    prompt: 'Synthetic canary rollout validation request.',
    metadata: {
      synthetic: true,
      traffic_class: 'langsmith_rollout_validation',
    },
  });
}

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-Synthetic-Test': 'langsmith-rollout',
  };

  if (BEARER_TOKEN) {
    headers.Authorization = `Bearer ${BEARER_TOKEN}`;
  }

  const response = http.post(`${BASE_URL}${API_PATH}`, makePayload(__ITER), { headers });

  const ok = check(response, {
    'status is 2xx or 4xx validation': (r) => r.status >= 200 && r.status < 500,
    'response under hard timeout budget': (r) => r.timings.duration < 10000,
  });

  endToEndLatency.add(response.timings.duration);

  const traceFailureHeader = response.headers['X-LangSmith-Trace-Error'] || '';
  const traceFailed = traceFailureHeader.length > 0 || response.status >= 500;
  tracesFailureRate.add(traceFailed);

  if (!ok) {
    tracesFailureRate.add(true);
  }

  sleep(1);
}
