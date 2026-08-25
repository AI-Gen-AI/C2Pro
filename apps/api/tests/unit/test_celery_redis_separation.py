"""P0-OPS: Celery broker / result-backend Redis separation.

Proves CELERY_BROKER_URL / CELERY_RESULT_BACKEND_URL are used when set, fall back
to REDIS_URL otherwise (dev/test compatibility), that TLS is derived independently
per URL (redis:// -> no SSL, rediss:// -> verified SSL), and that result-state
polling stays functional (so the result backend must not be globally disabled).
"""

from __future__ import annotations

import ssl
from types import SimpleNamespace
from unittest.mock import Mock

import certifi

from src.config import Settings
from src.core.tasks.celery_job_queue import CeleryJobQueue, JobStatus
from src.core.tasks.redis_urls import (
    redis_ssl_options,
    resolve_broker_url,
    resolve_result_backend_url,
)

_APP_REDIS = "rediss://app:tok@meet-glider.upstash.io:6379"
_CELERY_BROKER = "redis://default:pw@celery.railway.internal:6379/0"
_CELERY_BACKEND = "redis://default:pw@celery.railway.internal:6379/1"


def _settings(monkeypatch, **env: str) -> Settings:
    for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND_URL", "REDIS_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_explicit_celery_urls_are_preferred(monkeypatch) -> None:
    settings = _settings(
        monkeypatch,
        CELERY_BROKER_URL=_CELERY_BROKER,
        CELERY_RESULT_BACKEND_URL=_CELERY_BACKEND,
        REDIS_URL=_APP_REDIS,
    )
    assert resolve_broker_url(settings) == _CELERY_BROKER
    assert resolve_result_backend_url(settings) == _CELERY_BACKEND
    # The application Redis (cache/rate-limit/events/prompt-cache) is untouched.
    assert settings.redis_url == _APP_REDIS


def test_falls_back_to_redis_url_when_celery_urls_unset(monkeypatch) -> None:
    settings = _settings(monkeypatch, REDIS_URL=_APP_REDIS)
    assert resolve_broker_url(settings) == _APP_REDIS
    assert resolve_result_backend_url(settings) == _APP_REDIS


def test_partial_config_backend_falls_back_broker_explicit(monkeypatch) -> None:
    settings = _settings(monkeypatch, CELERY_BROKER_URL=_CELERY_BROKER, REDIS_URL=_APP_REDIS)
    assert resolve_broker_url(settings) == _CELERY_BROKER
    assert resolve_result_backend_url(settings) == _APP_REDIS


def test_plaintext_redis_uses_no_ssl() -> None:
    assert redis_ssl_options(_CELERY_BROKER) is None


def test_unset_url_uses_no_ssl() -> None:
    assert redis_ssl_options(None) is None


def test_rediss_configures_verified_tls() -> None:
    assert redis_ssl_options(_APP_REDIS) == {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_ca_certs": certifi.where(),
    }


def test_result_state_polling_remains_functional() -> None:
    """CeleryJobQueue.get_status reads AsyncResult(job_id).state from the result
    backend, so the backend must stay configured (no global task_ignore_result)."""
    client = Mock()
    client.AsyncResult.return_value = SimpleNamespace(id="job-1", state="SUCCESS")

    queue = CeleryJobQueue(client, "document_parsing")

    assert queue.get_status("job-1") == JobStatus.SUCCESS
    client.AsyncResult.assert_called_once_with("job-1")
