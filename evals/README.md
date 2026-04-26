# Golden Corpus Expectations

The corpus runner validates each bundle in `evals/golden_corpus/bundles/`
against both structural expectations and v1 coherence expectations.

## Authoring New Bundle Expectations

Every bundle must include:

- `expected_score_range`: `{ "min": number|null, "max": number|null, "reasoning": string }`
- `expected_alerts`: a list of `{ "rule_id": string, "min_count": int, "severity": "low"|"medium"|"high"|"critical" }`
- `score_check`: `"required"` or `"skip"`

Use numeric `min` and `max` when the score must be asserted. Use `null` for
both values only when the bundle should withhold a score, such as a contract-only
upload with insufficient evidence. Contract-only bundles must include:

```json
{
  "rule_id": "AUDIT_INCOMPLETE",
  "min_count": 1,
  "severity": "medium"
}
```

`score_check: "skip"` is allowed only with a concrete `reasoning` comment. It
should be temporary and reserved for corpus cases where the expected score cannot
be stabilized until another phase lands.

Run:

```bash
python -m evals.run_evals --corpus --ci --output evals/results
```

The command exits non-zero if any bundle score falls outside its range or any
expected alert is missing.
