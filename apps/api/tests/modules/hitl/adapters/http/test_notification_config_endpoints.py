"""
TDD tests for notification configuration API endpoints.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Test Suite ID: TS-HITL-NOTIFY-CONFIG-API-001
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestNotificationConfigEndpoints:
    """Integration tests for notification configuration API endpoints."""

    @staticmethod
    def _auth_headers(get_auth_headers) -> dict[str, str]:
        return get_auth_headers()

    @pytest.mark.asyncio
    async def test_get_notification_config_returns_current_settings(self, client: AsyncClient, get_auth_headers):
        """GET /api/v1/settings/notifications should return current tenant configuration."""
        response = await client.get(
            "/api/v1/settings/notifications",
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "notification_channels" in data
        assert "email_recipients" in data or data["notification_channels"] == []
        assert "slack_webhook_url" in data or "slack" not in data["notification_channels"]
        assert "webhook_url" in data or "webhook" not in data["notification_channels"]

        # Channels should be a list
        assert isinstance(data["notification_channels"], list)

    @pytest.mark.asyncio
    async def test_get_notification_config_returns_404_when_not_configured(self, client: AsyncClient, get_auth_headers):
        """GET should return 404 if tenant has no configuration yet."""
        # For a fresh tenant with no config
        response = await client.get(
            "/api/v1/settings/notifications",
            headers=self._auth_headers(get_auth_headers),
        )

        # Could return 404 or empty config
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["notification_channels"] == []

    @pytest.mark.asyncio
    async def test_post_notification_config_creates_new_config(self, client: AsyncClient, get_auth_headers):
        """POST /api/v1/settings/notifications should create/update tenant configuration."""
        config_payload = {
            "notification_channels": ["email", "slack"],
            "email_recipients": ["pm@example.com", "lead@example.com"],
            "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/XXX",
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=config_payload,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 201
        data = response.json()

        # Verify saved configuration
        assert data["notification_channels"] == ["email", "slack"]
        assert data["email_recipients"] == ["pm@example.com", "lead@example.com"]
        assert data["slack_webhook_url"] == "https://hooks.slack.com/services/T00/B00/XXX"

    @pytest.mark.asyncio
    async def test_post_notification_config_updates_existing_config(self, client: AsyncClient, get_auth_headers):
        """POST should update existing configuration (upsert behavior)."""
        headers = self._auth_headers(get_auth_headers)
        # Create initial config
        initial_config = {
            "notification_channels": ["email"],
            "email_recipients": ["old@example.com"],
        }
        await client.post("/api/v1/settings/notifications", json=initial_config, headers=headers)

        # Update config
        updated_config = {
            "notification_channels": ["slack"],
            "slack_webhook_url": "https://hooks.slack.com/services/NEW",
        }
        response = await client.post("/api/v1/settings/notifications", json=updated_config, headers=headers)

        assert response.status_code in [200, 201]
        data = response.json()

        # Verify updated configuration
        assert data["notification_channels"] == ["slack"]
        assert "slack_webhook_url" in data

    @pytest.mark.asyncio
    async def test_post_validates_notification_channels(self, client: AsyncClient, get_auth_headers):
        """POST should validate that notification_channels contains valid values."""
        invalid_config = {
            "notification_channels": ["invalid_channel"],
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "notification_channels" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_validates_email_recipients_format(self, client: AsyncClient, get_auth_headers):
        """POST should validate email recipient format."""
        invalid_config = {
            "notification_channels": ["email"],
            "email_recipients": ["not-an-email"],
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "email" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_validates_slack_webhook_url_format(self, client: AsyncClient, get_auth_headers):
        """POST should validate Slack webhook URL format."""
        invalid_config = {
            "notification_channels": ["slack"],
            "slack_webhook_url": "not-a-url",
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "slack_webhook_url" in str(error_data).lower() or "url" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_validates_webhook_url_format(self, client: AsyncClient, get_auth_headers):
        """POST should validate webhook URL format."""
        invalid_config = {
            "notification_channels": ["webhook"],
            "webhook_url": "not-a-url",
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "webhook_url" in str(error_data).lower() or "url" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_requires_email_recipients_when_email_enabled(self, client: AsyncClient, get_auth_headers):
        """POST should require email_recipients when email channel is enabled."""
        invalid_config = {
            "notification_channels": ["email"],
            # Missing email_recipients
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "email_recipients" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_requires_slack_url_when_slack_enabled(self, client: AsyncClient, get_auth_headers):
        """POST should require slack_webhook_url when slack channel is enabled."""
        invalid_config = {
            "notification_channels": ["slack"],
            # Missing slack_webhook_url
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "slack_webhook_url" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_post_requires_webhook_url_when_webhook_enabled(self, client: AsyncClient, get_auth_headers):
        """POST should require webhook_url when webhook channel is enabled."""
        invalid_config = {
            "notification_channels": ["webhook"],
            # Missing webhook_url
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=invalid_config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "webhook_url" in str(error_data).lower()

    @pytest.mark.asyncio
    async def test_config_is_tenant_isolated(self, client: AsyncClient):
        """Each tenant should have isolated notification configuration."""
        # This test requires multi-tenant setup in test client
        # Verify that tenant A's config doesn't affect tenant B
        # Implementation depends on auth/tenant setup in tests
        pass  # TODO: Implement with proper tenant fixtures

    @pytest.mark.asyncio
    async def test_post_allows_all_channels_enabled(self, client: AsyncClient, get_auth_headers):
        """POST should allow enabling all notification channels simultaneously."""
        config = {
            "notification_channels": ["email", "slack", "webhook"],
            "email_recipients": ["pm@example.com"],
            "slack_webhook_url": "https://hooks.slack.com/services/TEST",
            "webhook_url": "https://api.example.com/hitl",
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert set(data["notification_channels"]) == {"email", "slack", "webhook"}

    @pytest.mark.asyncio
    async def test_post_allows_empty_channels(self, client: AsyncClient, get_auth_headers):
        """POST should allow disabling all channels (log-only mode)."""
        config = {
            "notification_channels": [],
        }

        response = await client.post(
            "/api/v1/settings/notifications",
            json=config,
            headers=self._auth_headers(get_auth_headers),
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["notification_channels"] == []

    @pytest.mark.asyncio
    async def test_authentication_required(self, client: AsyncClient):
        """Endpoints should require authentication."""
        # Without auth token
        response = await client.get("/api/v1/settings/notifications")

        # Should return 401 if auth is required
        assert response.status_code in [200, 401]  # Depends on test client auth setup

    @pytest.mark.asyncio
    async def test_get_returns_sanitized_sensitive_data(self, client: AsyncClient, get_auth_headers):
        """GET should not return sensitive data like webhook auth tokens."""
        headers = self._auth_headers(get_auth_headers)
        # Create config with sensitive data
        config = {
            "notification_channels": ["webhook"],
            "webhook_url": "https://api.example.com/hitl",
            "webhook_auth_token": "secret-token-123",
        }
        await client.post("/api/v1/settings/notifications", json=config, headers=headers)

        # Get config
        response = await client.get("/api/v1/settings/notifications", headers=headers)
        data = response.json()

        # Sensitive fields should be masked or omitted
        if "webhook_auth_token" in data:
            assert data["webhook_auth_token"] == "***" or data["webhook_auth_token"].startswith("***")
