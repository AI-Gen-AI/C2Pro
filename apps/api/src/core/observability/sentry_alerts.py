"""
Sentry Alerting Utilities
"""
from uuid import UUID
import sentry_sdk
from src.config import settings

def record_auth_failure(
    reason_code: str,
    *,
    tenant_id: UUID | None,
    path: str,
    ip: str | None,
) -> None:
    """
    Records a structured authentication failure event to Sentry.

    These events are used to power Sentry alerts for auth failure spikes.

    Args:
        reason_code: A stable, machine-readable code for why auth failed.
        tenant_id: The tenant ID, if available.
        path: The request path that failed.
        ip: The client IP address, if available.
    """
    if not settings.sentry_dsn:
        return

    with sentry_sdk.push_scope() as scope:
        scope.set_tag("auth.reason", reason_code)
        scope.set_tag("tenant.id", str(tenant_id) if tenant_id else "anonymous")
        scope.set_tag("http.path", path)
        if ip:
            scope.set_user({"ip_address": ip})

        sentry_sdk.capture_event(
            {
                "message": f"Authentication failure: {reason_code}",
                "level": "warning",
            },
            hint={"fingerprint": [reason_code, path]},
        )
