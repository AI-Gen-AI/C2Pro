"""
Test Suite: TS-INT-EVT-BUS-001 — Event Bus Publish/Subscribe
Component: Infrastructure — Event Bus (Redis Pub/Sub)
Priority: P0 (Critical)
Coverage Target: 95%
Tests: 14

Validates the EventPublisher contract against a mocked async Redis client:

  1. Channel routing and JSON serialisation          (INT-EVT-001 – 003)
  2. document.uploaded payload completeness           (INT-EVT-004 – 007)
  3. Serialisation round-trip integrity               (INT-EVT-008 – 010)
  4. Async non-blocking behaviour (50 ms budget)      (INT-EVT-011 – 012)
  5. Error propagation                                (INT-EVT-013 – 014)

Green Bar Pattern applied: tests are written alongside a minimal
EventPublisher implementation so that the green bar is established
in a single pass.  The implementation is intentionally thin — retry /
DLQ logic is out of scope (tested in TS-INT-EVT-DLQ-001).

Methodology: TDD Strict (Red → Green → Refactor)
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from src.core.events.event_publisher import EventPublisher


# ===========================================
# HELPERS
# ===========================================

_TIMEOUT_SECS = 0.050  # 50 ms — the non-blocking budget


def _build_publisher() -> tuple[EventPublisher, AsyncMock]:
    """Return a (publisher, mock_redis) pair wired together."""
    redis = AsyncMock()
    return EventPublisher(redis_client=redis), redis


def _extract_published(mock_redis: AsyncMock) -> tuple[str, dict]:
    """
    Pull (channel, deserialized_payload) from a single redis.publish call.
    Raises AssertionError if publish was not awaited exactly once.
    """
    mock_redis.publish.assert_awaited_once()
    channel, raw = mock_redis.publish.call_args[0]
    return channel, json.loads(raw)


# ===========================================
# INT-EVT-001 – 003: Core Publish Contract
# ===========================================


class TestPublishContract:
    """
    Validates the fundamental publish → Redis delegation contract.
    INT-EVT-001, INT-EVT-002, INT-EVT-003
    """

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_001_publish_delegates_to_redis(self):
        """
        INT-EVT-001 — publish calls redis_client.publish exactly once

        Given: A publisher backed by a mock Redis client
        When:  publish("document.uploaded", {...}) is awaited
        Then:  redis_client.publish is awaited exactly once.
        """
        pub, redis = _build_publisher()
        await pub.publish("document.uploaded", {"tenant_id": str(uuid4())})

        redis.publish.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_002_channel_matches_event_name(self):
        """
        INT-EVT-002 — The Redis channel equals the event name argument

        Given: A publisher backed by a mock Redis client
        When:  publish("document.uploaded", {...}) is awaited
        Then:  The first positional arg to redis.publish is "document.uploaded".
        """
        pub, redis = _build_publisher()
        await pub.publish("document.uploaded", {"key": "val"})

        channel, _ = _extract_published(redis)
        assert channel == "document.uploaded"

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_003_message_is_json_serialised_payload(self):
        """
        INT-EVT-003 — Message sent to Redis is a JSON string that
                      round-trips back to the original payload.

        Given: A publisher and a simple string-value payload
        When:  publish is awaited
        Then:  json.loads of the Redis message equals the original payload dict.
        """
        pub, redis = _build_publisher()
        payload = {"tenant_id": str(uuid4()), "file_id": str(uuid4())}

        await pub.publish("document.uploaded", payload)

        _, deserialized = _extract_published(redis)
        assert deserialized == payload


# ===========================================
# INT-EVT-004 – 007: document.uploaded Payload
# ===========================================


class TestDocumentUploadedPayload:
    """
    Validates payload content for the document.uploaded event — the
    primary event fired after a document is persisted and stored.
    INT-EVT-004, INT-EVT-005, INT-EVT-006, INT-EVT-007
    """

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_004_payload_contains_tenant_id(self):
        """
        INT-EVT-004 — tenant_id survives the publish round-trip

        Given: payload = {"tenant_id": <uuid-str>, "file_id": <uuid-str>}
        When:  publish("document.uploaded", payload) is awaited
        Then:  Deserialized Redis message contains the same tenant_id string.
        """
        pub, redis = _build_publisher()
        tenant_id = str(uuid4())
        payload = {"tenant_id": tenant_id, "file_id": str(uuid4())}

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["tenant_id"] == tenant_id

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_005_payload_contains_file_id(self):
        """
        INT-EVT-005 — file_id survives the publish round-trip

        Given: payload with a specific file_id
        When:  publish("document.uploaded", payload) is awaited
        Then:  Deserialized message contains the same file_id string.
        """
        pub, redis = _build_publisher()
        file_id = str(uuid4())
        payload = {"tenant_id": str(uuid4()), "file_id": file_id}

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["file_id"] == file_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_006_payload_carries_project_id(self):
        """
        INT-EVT-006 — project_id is preserved when included

        Given: payload includes project_id alongside tenant_id / file_id
        When:  publish("document.uploaded", payload) is awaited
        Then:  project_id appears unchanged in the deserialized message.
        """
        pub, redis = _build_publisher()
        project_id = str(uuid4())
        payload = {
            "tenant_id": str(uuid4()),
            "file_id": str(uuid4()),
            "project_id": project_id,
        }

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["project_id"] == project_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_007_payload_carries_document_type(self):
        """
        INT-EVT-007 — document_type enum value is preserved

        Given: payload includes document_type = "contract"
        When:  publish("document.uploaded", payload) is awaited
        Then:  document_type appears unchanged in the deserialized message.
        """
        pub, redis = _build_publisher()
        payload = {
            "tenant_id": str(uuid4()),
            "file_id": str(uuid4()),
            "document_type": "contract",
        }

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["document_type"] == "contract"


# ===========================================
# INT-EVT-008 – 010: Serialisation Integrity
# ===========================================


class TestSerialisation:
    """
    Validates that the JSON round-trip does not corrupt or lose data.
    Covers UUID coercion, nested structures, and the empty-payload edge case.
    INT-EVT-008, INT-EVT-009, INT-EVT-010
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_008_uuid_objects_serialise_as_strings(self):
        """
        INT-EVT-008 — Raw uuid.UUID values in the payload are coerced to strings

        Given: payload values are uuid.UUID instances (not str)
        When:  publish is awaited
        Then:  Deserialized message contains those UUIDs as plain strings.
               The publisher does not raise TypeError on raw UUID objects.
        """
        pub, redis = _build_publisher()
        tid = uuid4()
        fid = uuid4()
        # Pass raw UUID objects — publisher must coerce before json.dumps
        payload = {"tenant_id": tid, "file_id": fid}

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["tenant_id"] == str(tid)
        assert body["file_id"] == str(fid)
        assert isinstance(body["tenant_id"], str)
        assert isinstance(body["file_id"], str)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_009_nested_metadata_survives_round_trip(self):
        """
        INT-EVT-009 — Nested dicts (metadata) are preserved exactly

        Given: payload contains a nested dict with lists and booleans
        When:  publish is awaited
        Then:  Deserialized message's metadata field equals the original.
        """
        pub, redis = _build_publisher()
        metadata = {
            "source": "web",
            "tags": ["contract", "urgent"],
            "dimensions": {"pages": 12, "has_tables": True},
        }
        payload = {
            "tenant_id": str(uuid4()),
            "file_id": str(uuid4()),
            "metadata": metadata,
        }

        await pub.publish("document.uploaded", payload)

        _, body = _extract_published(redis)
        assert body["metadata"] == metadata

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_010_empty_payload_publishes_valid_json(self):
        """
        INT-EVT-010 — An empty payload still produces a valid JSON object

        Given: payload = {}
        When:  publish("some.event", {}) is awaited
        Then:  Redis receives "{}" (valid JSON); no error is raised.
        """
        pub, redis = _build_publisher()
        await pub.publish("some.event", {})

        _, body = _extract_published(redis)
        assert body == {}


# ===========================================
# INT-EVT-011 – 012: Async / Concurrency
# ===========================================


class TestAsyncBehaviour:
    """
    Validates non-blocking semantics and concurrent publish isolation.
    INT-EVT-011, INT-EVT-012
    """

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_011_single_publish_under_50ms(self):
        """
        INT-EVT-011 — A single publish completes within the 50 ms budget

        Given: A publisher with a mock Redis client (zero real I/O)
        When:  publish is wrapped in asyncio.wait_for(timeout=0.050)
        Then:  No TimeoutError is raised.

        This is the primary guard against accidental synchronous blocking —
        the exact refactor trigger documented in the suite spec.
        """
        pub, _ = _build_publisher()
        payload = {"tenant_id": str(uuid4()), "file_id": str(uuid4())}

        # Raises asyncio.TimeoutError if publish blocks > 50 ms
        await asyncio.wait_for(
            pub.publish("document.uploaded", payload),
            timeout=_TIMEOUT_SECS,
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_012_concurrent_publishes_all_succeed(self):
        """
        INT-EVT-012 — 10 concurrent publishes complete independently

        Given: 10 distinct payloads launched via asyncio.gather
        When:  All coroutines are awaited concurrently under a 50 ms fence
        Then:  redis.publish was awaited exactly 10 times; every file_id
               appears exactly once in the published messages.
        """
        pub, redis = _build_publisher()
        file_ids = [str(uuid4()) for _ in range(10)]
        payloads = [{"tenant_id": str(uuid4()), "file_id": fid} for fid in file_ids]

        await asyncio.wait_for(
            asyncio.gather(
                *(pub.publish("document.uploaded", p) for p in payloads)
            ),
            timeout=_TIMEOUT_SECS,
        )

        assert redis.publish.await_count == 10
        # Every file_id must appear exactly once — order is non-deterministic
        published_file_ids = {
            json.loads(call[0][1])["file_id"]
            for call in redis.publish.call_args_list
        }
        assert published_file_ids == set(file_ids)


# ===========================================
# INT-EVT-013 – 014: Error Propagation
# ===========================================


class TestErrorPropagation:
    """
    Validates that failures in the Redis transport or in serialisation
    surface to the caller without being swallowed.
    INT-EVT-013, INT-EVT-014
    """

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_int_evt_013_redis_connection_error_propagates(self):
        """
        INT-EVT-013 — ConnectionError from Redis reaches the caller

        Given: redis.publish is configured to raise ConnectionError
        When:  publish is awaited
        Then:  ConnectionError propagates; EventPublisher does not swallow it.
        """
        pub, redis = _build_publisher()
        redis.publish.side_effect = ConnectionError("Redis is down")

        with pytest.raises(ConnectionError, match="Redis is down"):
            await pub.publish("document.uploaded", {"tenant_id": str(uuid4())})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_int_evt_014_non_serialisable_payload_raises(self):
        """
        INT-EVT-014 — A payload containing a non-serialisable value raises
                      TypeError before redis.publish is contacted.

        Given: payload contains a set (not JSON-serialisable by any
               reasonable encoder — the UUID encoder's default() calls
               super().default() which raises for unknown types)
        When:  publish is awaited
        Then:  TypeError is raised; redis.publish is never called.
        """
        pub, redis = _build_publisher()
        bad_payload: dict = {"data": {1, 2, 3}}  # set is not JSON-serialisable

        with pytest.raises(TypeError):
            await pub.publish("document.uploaded", bad_payload)

        redis.publish.assert_not_awaited()
