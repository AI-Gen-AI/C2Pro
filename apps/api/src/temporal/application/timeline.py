"""TS-UT-P0C-TEMPORAL-002 - deterministic, scope-bound timeline cursors."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.temporal.domain.project_event import ProjectEvent

_CURSOR_VERSION = 2
_CURSOR_PURPOSE = b"p0c-timeline-cursor-v2\0"


class InvalidTimelineCursor(ValueError):
    """A cursor cannot safely identify a continuation point."""


@dataclass(frozen=True, order=True)
class TimelineKey:
    occurred_at: datetime
    event_id: UUID


@dataclass(frozen=True)
class TimelineScope:
    """Every property a continuation token is permitted to represent."""

    tenant_id: UUID
    project_id: UUID
    order: str = "occurred_at:event_id:asc"
    query: str = "timeline-v1"

    def model(self) -> dict[str, str]:
        return {
            "tenant_id": str(self.tenant_id),
            "project_id": str(self.project_id),
            "order": self.order,
            "query": self.query,
        }


@dataclass(frozen=True)
class TimelinePage:
    items: list[ProjectEvent]
    next_cursor: str | None


def _event_key(event: ProjectEvent) -> TimelineKey:
    return TimelineKey(event.occurred_at, event.event_id)


def _canonical(data: dict[str, object]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _mac(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), _CURSOR_PURPOSE + body, hashlib.sha256).hexdigest()


def encode_cursor(
    occurred_at: datetime,
    event_id: UUID,
    *,
    scope: TimelineScope,
    secret: str,
) -> str:
    """Encode a signed continuation key bound to one tenant/project query."""
    body = {
        "v": _CURSOR_VERSION,
        "scope": scope.model(),
        "after": {"occurred_at": occurred_at.isoformat(), "event_id": str(event_id)},
    }
    body_bytes = _canonical(body)
    raw = _canonical({**body, "mac": _mac(body_bytes, secret)})
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, *, scope: TimelineScope, secret: str) -> TimelineKey:
    """Verify syntax, integrity and scope before accepting a keyset position."""
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        data = json.loads(decoded)
        if not isinstance(data, dict) or data.get("v") != _CURSOR_VERSION:
            raise ValueError("unsupported cursor version")
        token_scope = data.get("scope")
        after = data.get("after")
        mac = data.get("mac")
        if not isinstance(token_scope, dict) or not isinstance(after, dict) or not isinstance(mac, str):
            raise ValueError("invalid cursor shape")
        body = {"v": data["v"], "scope": token_scope, "after": after}
        if not hmac.compare_digest(mac, _mac(_canonical(body), secret)):
            raise ValueError("invalid cursor integrity")
        if token_scope != scope.model():
            raise ValueError("cursor scope mismatch")
        return TimelineKey(
            occurred_at=datetime.fromisoformat(str(after["occurred_at"])),
            event_id=UUID(str(after["event_id"])),
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise InvalidTimelineCursor("Invalid or stale timeline cursor") from exc


def paginate_events(
    events: list[ProjectEvent],
    *,
    limit: int,
    scope: TimelineScope,
    secret: str,
    cursor: str | None = None,
) -> TimelinePage:
    """Pure fallback for tests; HTTP uses database keyset paging directly."""
    after = decode_cursor(cursor, scope=scope, secret=secret) if cursor else None
    ordered = sorted(events, key=lambda event: (event.occurred_at, event.event_id))
    if after is not None:
        ordered = [event for event in ordered if _event_key(event) > after]
    page_items = ordered[:limit]
    has_more = len(ordered) > limit
    next_cursor = (
        encode_cursor(
            page_items[-1].occurred_at, page_items[-1].event_id, scope=scope, secret=secret
        )
        if has_more and page_items
        else None
    )
    return TimelinePage(items=page_items, next_cursor=next_cursor)


__all__ = [
    "InvalidTimelineCursor",
    "TimelineKey",
    "TimelinePage",
    "TimelineScope",
    "decode_cursor",
    "encode_cursor",
    "paginate_events",
]
