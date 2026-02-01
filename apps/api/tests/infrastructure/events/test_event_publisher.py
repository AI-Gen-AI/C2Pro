"""
Event Bus Publisher Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-EVT-BUS-001.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from src.core.events.event_publisher import EventPublisher


@pytest.mark.asyncio
async def test_document_uploaded_event_published_with_payload_under_50ms():
    redis_client = AsyncMock()
    publisher = EventPublisher(redis_client=redis_client)

    tenant_id = uuid4()
    file_id = uuid4()
    payload = {"tenant_id": str(tenant_id), "file_id": str(file_id)}

    await asyncio.wait_for(
        publisher.publish("document.uploaded", payload),
        timeout=0.05,
    )

    redis_client.publish.assert_awaited_once_with("document.uploaded", payload)
