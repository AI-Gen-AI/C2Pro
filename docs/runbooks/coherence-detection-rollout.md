# Runbook: Coherence detection + canary rollout

Staged rollout (**shadow → canary → GA**) for the coherence capabilities shipped in
`#546` (canary scorer), `#549/#550` (cross-clause LEGAL/SCOPE detection) and `#551`
(project-identity comparator). The two **cost-bearing** capabilities are gated per tenant
and default **off**; the deterministic detection floor + identity comparator are always on.

## What the flags gate

| Flag | Capability | Cost |
|---|---|---|
| `coherence_canonical_canary` | Expert-calibrated canonical scorer on `/evaluate` (flips the headline; findings unchanged) | none extra |
| `coherence_llm_crosscheck` | LLM cross-clause contradiction depth pass (semantic LEGAL/SCOPE) | +LLM calls/eval (bounded by `max_cross_pairs=20`, skipped in `low_budget_mode`) |

Always-on (no flag): `CROSS-LEGAL-CONFLICT`, `CROSS-SCOPE-CONFLICT` (deterministic floor),
`DET-CRS-IDMISMATCH` (identity).

## 1. Enroll one pilot tenant

From `apps/api` (venv active, `.env` → target DB):

```bash
python scripts/enroll_coherence_pilot.py <TENANT_UUID>            # enable
python scripts/enroll_coherence_pilot.py <TENANT_UUID> --dry-run  # preview only
python scripts/enroll_coherence_pilot.py <TENANT_UUID> --off      # roll back
```

Idempotent + reversible; writes `tenants.settings.feature_flags`. Emits a
`coherence.flag_changed` structlog event per flag.

## 2. Observe (a few real evaluations for the pilot tenant)

**Structlog events**
- `coherence_canary_rescore` — the v1↔canonical headline delta (`v1_score`, `canonical_score`, `delta`) on every eval.
- `coherence_llm_crosscheck` failures log `cross_clause_llm_failed` (fail-open — no findings, never blocks `/evaluate`).

**New findings** (in `coherence_results.alerts` / the alerts table):

```sql
SELECT c.rule_id, c.severity, count(*)
FROM coherence_results r, jsonb_to_recordset(r.alerts) AS c(rule_id text, severity text)
WHERE r.tenant_id = '<TENANT_UUID>'
  AND c.rule_id IN ('CROSS-LLM-CONTRADICTION','DET-CRS-IDMISMATCH',
                    'CROSS-LEGAL-CONFLICT','CROSS-SCOPE-CONFLICT')
GROUP BY 1, 2 ORDER BY 3 DESC;
```

**LLM cost** — per-tenant token/cost in `usage_analytics` (compare the pilot's cost/eval before vs after enabling `coherence_llm_crosscheck`).

**Sanity checks**
- Findings are plausible (real contradictions, not noise) — spot-check a handful.
- No `cross_clause_llm_failed` storm (would indicate an LLM/parse problem).
- Canary deltas match calibration (a single critical → canonical ≈ 85 vs v1 ≈ 65).

## 3. Widen / roll back

- **Looks right** → enroll a small cohort, then flip the settings defaults for GA.
- **Cost too high or noisy findings** → `--off` the pilot immediately (reversible), tune
  (e.g. lower `max_cross_pairs`, tighten the contradiction prompt) and re-pilot.

## Guardrails
- Live `/evaluate` is byte-identical for any tenant not enrolled (both flags default off).
- The LLM pass is fail-open; the canary substitutes only the headline (same alerts).
- Roll back with `--off` at any time — no deploy needed.
