"""
Per-rule rollout configuration for the LLM semantic gate (P3).

Defaults all 6 R-*-CLARITY rules to 100%. Per-rule overrides via env vars:
    COHERENCE_LLM_ROLLOUT_<RULE_ID_UPPER_SNAKE>=<int 0..100>
e.g.  COHERENCE_LLM_ROLLOUT_R_TECHNICAL_SPEC_CLARITY_01=0   # kill switch

Kept env-driven (not YAML) so ops can change percentages without redeploy.
"""

from __future__ import annotations

import os

_DEFAULTS: dict[str, int] = {
    "R-SCOPE-CLARITY-01": 100,
    "R-PAYMENT-CLARITY-01": 100,
    "R-SCHEDULE-CLARITY-01": 100,
    "R-TECHNICAL-SPEC-CLARITY-01": 100,
    "R-RESPONSIBILITY-01": 100,
    "R-QUALITY-STANDARDS-01": 100,
}


def _env_key(rule_id: str) -> str:
    # R-TECHNICAL-SPEC-CLARITY-01 -> COHERENCE_LLM_ROLLOUT_R_TECHNICAL_SPEC_CLARITY_01
    return "COHERENCE_LLM_ROLLOUT_" + rule_id.replace("-", "_").upper()


def get_rollout_pct(rule_id: str) -> int:
    """Return the rollout percentage for `rule_id` (0..100). Unknown rules → 0."""
    raw = os.environ.get(_env_key(rule_id))
    if raw is not None:
        try:
            pct = int(raw)
        except ValueError:
            pct = 0
        return max(0, min(100, pct))
    return _DEFAULTS.get(rule_id, 0)
