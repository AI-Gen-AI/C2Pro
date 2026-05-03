<!-- TS-INF-PERF-056-002: Performance benchmark runbook. -->

# Performance Benchmarks

TASK-INF-056 adds pytest-benchmark coverage for deterministic hot paths:

- Coherence scoring over 250 synthetic findings.
- Analysis coherence derivation over large extracted risk/WBS/BOM payloads.
- Disabled-tracing LLM wrapper overhead under `C2PRO_AI_MOCK=1`.

Run from `apps/api`:

```powershell
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/perf/ --benchmark-only --benchmark-save=baseline_2026_05_03
```

Baselines are written by pytest-benchmark under `apps/api/.benchmarks/`.
The checked-in `tests/perf/baselines/` directory is reserved for curated
baseline exports when release evidence needs to be promoted into Git.

The perf suite disables LangSmith/LangChain tracing in `tests/perf/conftest.py`
before benchmark modules import production code. This avoids LangChain tracer
parent-run context leaking across repeated pytest-benchmark rounds.
