"""JV1-A3 prompt identity and retry budgets fail closed before any DB access."""
import hashlib
import json

import pytest

from src.analysis.application.n4_incremental_runner import N4IncrementalRunner


class Provider:
    model_name = "synthetic-only"
    prompt_version = "n4-compact-window-v1"


def runner(provider=None, **overrides):
    return N4IncrementalRunner(
        session_factory=None, provider=provider or Provider(),
        run_cap_usd="1", per_window_reservation_usd="0.04",
        period_key="2026-11", max_context_chars=600, overlap_chars=50,
        **overrides,
    )


def test_v1_preserves_historical_sha256_digest():
    value = runner()
    payload = {
        "prompt": "n4-compact-window-v1", "model": "synthetic-only",
        "window_chars": 600, "overlap": 50,
    }
    expected = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    assert value.config_sha256 == expected == runner().config_sha256


def test_v1_to_v2_changes_digest_and_same_version_remains_stable():
    provider = Provider()
    v1 = runner(provider)
    provider.prompt_version = "n4-compact-window-v2"
    v2 = runner(provider)
    assert v1.config_sha256 != v2.config_sha256
    assert v2.config_sha256 == runner(provider).config_sha256


@pytest.mark.parametrize("version", [None, "", " ", "\t", " v2", "v2 ", 123])
def test_missing_or_unpinned_prompt_version_fails_closed(version):
    provider = Provider()
    provider.prompt_version = version
    with pytest.raises(ValueError, match="prompt_version"):
        runner(provider)


def test_missing_prompt_version_attribute_fails_closed():
    class OldProvider:
        model_name = "synthetic-only"
    with pytest.raises(ValueError, match="prompt_version"):
        runner(OldProvider())


@pytest.mark.parametrize("attempts", [0, -1, 11, True, "3", None])
def test_retry_budget_must_be_bounded_integer(attempts):
    with pytest.raises(ValueError, match="max_attempts"):
        runner(max_attempts=attempts)


def test_version_and_model_cannot_mutate_on_reused_runner():
    provider = Provider()
    value = runner(provider)
    provider.prompt_version = "n4-compact-window-v2"
    assert value.prompt_version == "n4-compact-window-v1"
    assert value.config_sha256 != runner(provider).config_sha256
