"""
TS-INT-DB-CLS-001: Alert workspace settings validation tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.alerts.router import AlertWorkspaceSettingsPayload


def test_alert_workspace_settings_reject_invalid_email_subscription_target() -> None:
    with pytest.raises(ValidationError, match="emailAddress"):
        AlertWorkspaceSettingsPayload.model_validate(
            {
                "rules": [],
                "subscriptions": {
                    "emailEnabled": True,
                    "emailAddress": "not-an-email",
                    "slackEnabled": False,
                    "slackChannel": "",
                },
            }
        )


def test_alert_workspace_settings_reject_invalid_slack_subscription_target() -> None:
    with pytest.raises(ValidationError, match="slackChannel"):
        AlertWorkspaceSettingsPayload.model_validate(
            {
                "rules": [],
                "subscriptions": {
                    "emailEnabled": False,
                    "emailAddress": "",
                    "slackEnabled": True,
                    "slackChannel": "project-alerts",
                },
            }
        )
