# apps/api/tests/unit/core/observability/test_sentry_alerts.py
import uuid
from unittest.mock import MagicMock, patch

from src.core.observability.sentry_alerts import record_auth_failure

def test_record_auth_failure_sends_event_when_dsn_is_set(monkeypatch):
    """
    Verify that record_auth_failure sends a correctly structured event to Sentry
    when the SENTRY_DSN is configured.
    """
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.sentry_dsn = "https://dummy_dsn@sentry.io/12345"
    monkeypatch.setattr("src.core.observability.sentry_alerts.settings", mock_settings)

    # Mock sentry_sdk
    mock_push_scope = MagicMock()
    mock_capture_event = MagicMock()

    with patch("src.core.observability.sentry_alerts.sentry_sdk.push_scope", mock_push_scope) as p1, \
         patch("src.core.observability.sentry_alerts.sentry_sdk.capture_event", mock_capture_event) as p2:
        
        scope_manager = mock_push_scope.return_value.__enter__.return_value
        
        tenant_id = uuid.uuid4()
        reason_code = "test_reason"
        path = "/test/path"
        ip = "127.0.0.1"

        record_auth_failure(
            reason_code=reason_code,
            tenant_id=tenant_id,
            path=path,
            ip=ip
        )

        # Assertions
        mock_push_scope.assert_called_once()
        
        scope_manager.set_tag.assert_any_call("auth.reason", reason_code)
        scope_manager.set_tag.assert_any_call("tenant.id", str(tenant_id))
        scope_manager.set_tag.assert_any_call("http.path", path)
        scope_manager.set_user.assert_called_once_with({"ip_address": ip})

        mock_capture_event.assert_called_once()
        call_args, call_kwargs = mock_capture_event.call_args
        
        event_payload = call_args[0]
        assert event_payload["message"] == f"Authentication failure: {reason_code}"
        assert event_payload["level"] == "warning"
        
        hint = call_kwargs.get("hint")
        assert hint is not None
        assert hint["fingerprint"] == [reason_code, path]


def test_record_auth_failure_is_noop_when_dsn_is_not_set(monkeypatch):
    """
    Verify that record_auth_failure does nothing when the SENTRY_DSN is not set.
    """
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.sentry_dsn = None
    monkeypatch.setattr("src.core.observability.sentry_alerts.settings", mock_settings)

    # Mock sentry_sdk
    mock_capture_event = MagicMock()
    with patch("src.core.observability.sentry_alerts.sentry_sdk.capture_event", mock_capture_event):
        
        record_auth_failure(
            reason_code="test_reason",
            tenant_id=uuid.uuid4(),
            path="/test/path",
            ip="127.0.0.1"
        )

        mock_capture_event.assert_not_called()
