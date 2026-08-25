"""Celery broker / result-backend URL and TLS resolution.

P0-OPS: separate the Celery Redis (broker + result backend) from the application
Redis (cache / rate-limit / event bus / prompt cache). Celery prefers the explicit
``CELERY_BROKER_URL`` / ``CELERY_RESULT_BACKEND_URL`` and falls back to ``REDIS_URL``
so dev, test and CI keep working with a single Redis.

Deliberately free of any ``celery`` import so it stays importable — and directly
unit-testable — even where the ``celery`` package is stubbed in tests.
"""

from __future__ import annotations

import ssl
from typing import Protocol

import certifi


class RedisSettings(Protocol):
    """Structural view of the settings fields this module reads."""

    redis_url: str | None
    celery_broker_url: str | None
    celery_result_backend_url: str | None


def resolve_broker_url(settings: RedisSettings) -> str | None:
    """Celery broker URL: explicit ``CELERY_BROKER_URL`` else ``REDIS_URL`` fallback."""
    return settings.celery_broker_url or settings.redis_url


def resolve_result_backend_url(settings: RedisSettings) -> str | None:
    """Celery result backend URL: explicit ``CELERY_RESULT_BACKEND_URL`` else ``REDIS_URL``.

    Kept configured (not disabled): ``CeleryJobQueue.get_status`` reads
    ``AsyncResult(job_id).state`` from the result backend.
    """
    return settings.celery_result_backend_url or settings.redis_url


def redis_ssl_options(url: str | None) -> dict[str, object] | None:
    """SSL options for a ``rediss://`` URL (verified against the certifi CA bundle);
    ``None`` for plaintext ``redis://`` or an unset URL.

    Derived independently per URL so the broker and result backend may use different
    schemes — e.g. a plaintext ``redis://`` Railway broker on private networking
    alongside a ``rediss://`` Upstash fallback.
    """
    if url and url.startswith("rediss://"):
        return {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_ca_certs": certifi.where()}
    return None
