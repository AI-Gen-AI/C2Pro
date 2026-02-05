"""
Dead letter queue integration tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.events.dead_letter_queue import DeadLetterQueue, DLQMessage


class TestDeadLetterQueue:
    """Refers to Suite ID: TS-INT-EVT-DLQ-001"""

    def test_001_push_failed_message(self) -> None:
        dlq = DeadLetterQueue()
        msg = dlq.push(topic="document.uploaded", payload={"id": "d1"}, reason="handler_error")
        assert isinstance(msg, DLQMessage)
        assert msg.topic == "document.uploaded"

    def test_002_message_has_timestamp(self) -> None:
        dlq = DeadLetterQueue()
        msg = dlq.push(topic="document.uploaded", payload={"id": "d1"}, reason="handler_error")
        assert isinstance(msg.created_at, datetime)
        assert msg.created_at.tzinfo is not None

    def test_003_list_returns_messages_in_insert_order(self) -> None:
        dlq = DeadLetterQueue()
        dlq.push("t", {"id": "1"}, "e1")
        dlq.push("t", {"id": "2"}, "e2")
        assert [m.payload["id"] for m in dlq.list()] == ["1", "2"]

    def test_004_pop_oldest_returns_first_message(self) -> None:
        dlq = DeadLetterQueue()
        dlq.push("t", {"id": "1"}, "e1")
        dlq.push("t", {"id": "2"}, "e2")
        popped = dlq.pop_oldest()
        assert popped is not None
        assert popped.payload["id"] == "1"

    def test_005_list_by_topic_filters(self) -> None:
        dlq = DeadLetterQueue()
        dlq.push("document.uploaded", {"id": "1"}, "e1")
        dlq.push("alert.created", {"id": "2"}, "e2")
        filtered = dlq.list_by_topic("alert.created")
        assert len(filtered) == 1
        assert filtered[0].topic == "alert.created"

    def test_006_retryable_flag_defaults_true(self) -> None:
        dlq = DeadLetterQueue()
        msg = dlq.push("t", {"id": "1"}, "e1")
        assert msg.retryable is True

    def test_007_max_size_discards_oldest(self) -> None:
        dlq = DeadLetterQueue(max_size=2)
        dlq.push("t", {"id": "1"}, "e1")
        dlq.push("t", {"id": "2"}, "e2")
        dlq.push("t", {"id": "3"}, "e3")
        assert [m.payload["id"] for m in dlq.list()] == ["2", "3"]

    def test_008_purge_clears_queue(self) -> None:
        dlq = DeadLetterQueue()
        dlq.push("t", {"id": "1"}, "e1")
        dlq.push("t", {"id": "2"}, "e2")
        dlq.purge()
        assert dlq.list() == []
