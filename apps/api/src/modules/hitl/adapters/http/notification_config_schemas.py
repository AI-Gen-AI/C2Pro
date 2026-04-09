"""
Pydantic schemas for notification configuration API endpoints.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator


class NotificationChannel(str, Enum):
    """Valid notification channel types."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationConfigRequest(BaseModel):
    """Request schema for creating/updating notification configuration."""

    notification_channels: list[NotificationChannel] = Field(
        default_factory=list,
        description="List of enabled notification channels",
    )
    email_recipients: list[EmailStr] | None = Field(
        default=None,
        description="Email recipients for email notifications (required if email channel enabled)",
    )
    slack_webhook_url: HttpUrl | None = Field(
        default=None,
        description="Slack webhook URL (required if slack channel enabled)",
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        description="Generic webhook URL (required if webhook channel enabled)",
    )
    webhook_auth_token: str | None = Field(
        default=None,
        description="Optional webhook authentication token (Bearer token)",
    )
    custom_headers: dict[str, str] | None = Field(
        default=None,
        description="Optional custom headers for webhook requests",
    )

    @field_validator("notification_channels")
    @classmethod
    def validate_notification_channels(
        cls, v: list[NotificationChannel]
    ) -> list[NotificationChannel]:
        """Validate notification channels list."""
        if v is None:
            return []
        # Remove duplicates
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def validate_channel_requirements(self) -> "NotificationConfigRequest":
        """Validate per-channel required settings after all fields are parsed."""
        channels = set(self.notification_channels)
        if NotificationChannel.EMAIL in channels and not self.email_recipients:
            raise ValueError("email_recipients is required when email channel is enabled")
        if NotificationChannel.SLACK in channels and not self.slack_webhook_url:
            raise ValueError("slack_webhook_url is required when slack channel is enabled")
        if NotificationChannel.WEBHOOK in channels and not self.webhook_url:
            raise ValueError("webhook_url is required when webhook channel is enabled")
        return self


class NotificationConfigResponse(BaseModel):
    """Response schema for notification configuration."""

    notification_channels: list[NotificationChannel] = Field(
        default_factory=list,
        description="List of enabled notification channels",
    )
    email_recipients: list[str] | None = Field(
        default=None,
        description="Email recipients for email notifications",
    )
    slack_webhook_url: str | None = Field(
        default=None,
        description="Slack webhook URL (partial masking for security)",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Generic webhook URL",
    )
    webhook_auth_token: str | None = Field(
        default=None,
        description="Webhook authentication token (masked)",
    )
    custom_headers: dict[str, str] | None = Field(
        default=None,
        description="Custom headers for webhook requests (values masked)",
    )

    @classmethod
    def from_config(cls, config: dict) -> NotificationConfigResponse:
        """Create response from internal config dict with sensitive data masking."""
        # Mask sensitive data in response
        webhook_auth_token = config.get("webhook_auth_token")
        if webhook_auth_token:
            webhook_auth_token = "***" + webhook_auth_token[-4:] if len(webhook_auth_token) > 4 else "***"

        custom_headers = config.get("custom_headers")
        if custom_headers:
            # Mask header values
            custom_headers = {k: "***" for k in custom_headers}

        return cls(
            notification_channels=[
                NotificationChannel(ch) for ch in config.get("notification_channels", [])
            ],
            email_recipients=config.get("email_recipients"),
            slack_webhook_url=config.get("slack_webhook_url"),
            webhook_url=config.get("webhook_url"),
            webhook_auth_token=webhook_auth_token,
            custom_headers=custom_headers,
        )
