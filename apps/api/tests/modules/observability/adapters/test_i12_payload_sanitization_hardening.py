"""
I12 - Payload Sanitization Hardening (RED)
Test Suite ID: TS-I12-OBS-ADP-002
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.modules.observability.application.ports import LangSmithAdapter


class _MockRun:
    def __init__(self, run_id: UUID, parent_run_id: UUID | None, name: str, run_type: str, inputs: dict) -> None:
        self.id = run_id
        self.parent_run_id = parent_run_id
        self.name = name
        self.run_type = run_type
        self.inputs = inputs
        self.outputs = None
        self.error = None
        self.end_time = None
        self.extra_attrs: dict = {}

    def end(self, outputs=None, error=None, **kwargs) -> None:
        self.outputs = outputs
        self.error = error
        self.end_time = datetime.now()
        self.extra_attrs.update(kwargs)


class _RecordingLangSmithClient:
    def __init__(self) -> None:
        self.last_create_kwargs: dict | None = None

    def create_run(self, name: str, run_type: str, inputs: dict, parent_run_id: UUID | None = None, **kwargs) -> _MockRun:
        self.last_create_kwargs = {
            "name": name,
            "run_type": run_type,
            "inputs": inputs,
            "parent_run_id": parent_run_id,
            **kwargs,
        }
        return _MockRun(run_id=uuid4(), parent_run_id=parent_run_id, name=name, run_type=run_type, inputs=inputs)

    def update_run(self, run, **kwargs) -> None:  # noqa: ANN001
        return None


@pytest.mark.asyncio
async def test_i12_payload_sanitization_recursively_redacts_nested_dict_keys_red() -> None:
    """
    TS-I12-OBS-ADP-002:
    sanitizer must recursively redact sensitive keys in nested dict payloads.
    """
    client = _RecordingLangSmithClient()
    adapter = LangSmithAdapter(langsmith_client=client)

    await adapter.start_run(
        name="sanitize_nested_dict",
        run_type="chain",
        inputs={"level1": {"authorization": "Bearer abc", "payload": {"secret": "s3cr3t"}}},
        metadata={"api_key": "top-secret"},
    )

    assert client.last_create_kwargs is not None
    assert client.last_create_kwargs["inputs"]["level1"]["authorization"] == "[REDACTED]"
    assert client.last_create_kwargs["inputs"]["level1"]["payload"]["secret"] == "[REDACTED]"
    assert client.last_create_kwargs["metadata"]["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_i12_payload_sanitization_redacts_sensitive_keys_inside_lists_red() -> None:
    """
    TS-I12-OBS-ADP-002:
    sanitizer must redact sensitive keys inside dict items nested in lists.
    """
    client = _RecordingLangSmithClient()
    adapter = LangSmithAdapter(langsmith_client=client)

    await adapter.start_run(
        name="sanitize_list_items",
        run_type="chain",
        inputs={
            "events": [
                {"token": "abc"},
                {"nested": {"refresh_token": "def"}},
            ]
        },
        metadata={},
    )

    assert client.last_create_kwargs is not None
    assert client.last_create_kwargs["inputs"]["events"][0]["token"] == "[REDACTED]"
    assert client.last_create_kwargs["inputs"]["events"][1]["nested"]["refresh_token"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_i12_payload_sanitization_applies_to_inputs_and_metadata_lists_red() -> None:
    """
    TS-I12-OBS-ADP-002:
    both inputs and metadata must be sanitized, including list-nested secrets.
    """
    client = _RecordingLangSmithClient()
    adapter = LangSmithAdapter(langsmith_client=client)

    await adapter.start_run(
        name="sanitize_inputs_and_metadata",
        run_type="chain",
        inputs={"steps": [{"api_key": "k1"}]},
        metadata={"audit": [{"password": "p1"}], "safe": "ok"},
    )

    assert client.last_create_kwargs is not None
    assert client.last_create_kwargs["inputs"]["steps"][0]["api_key"] == "[REDACTED]"
    assert client.last_create_kwargs["metadata"]["audit"][0]["password"] == "[REDACTED]"
    assert client.last_create_kwargs["metadata"]["safe"] == "ok"
