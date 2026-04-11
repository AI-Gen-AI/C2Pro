"""
TS-CT-API-001: CORS headers must survive early auth failures.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_upload_unauthorized_response_keeps_cors_headers(client) -> None:
    origin = "http://localhost:3000"
    response = await client.post(
        f"/api/v1/projects/{uuid4()}/documents",
        headers={"Origin": origin},
        files={
            "file": ("contract.pdf", b"fake-pdf", "application/pdf"),
            "document_type": (None, "contract"),
        },
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == origin
