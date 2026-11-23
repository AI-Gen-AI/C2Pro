"""Verify offline owner approval for the ONE pilot first-admin action.

There is intentionally no CLI-selected or environment-selected verifier key.
The owner's Ed25519 public key must be provisioned independently in a root-owned
file on the operator host. No private signing key is held by C2Pro.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

KEY_PATH = Path("/etc/c2pro/pilot-first-admin-approver.ed25519.pub")
ACTION = "C2PRO_PILOT_FIRST_ADMIN_V1"
MAX_LIFETIME = timedelta(hours=24)


class ApprovalRefused(ValueError):
    """The owner approval is unavailable, forged, stale or for another target."""


def _read_trusted_public_key() -> bytes:
    """Fail closed: no relative/env/CLI key path, symlinks or writable owner key."""
    try:
        parent = KEY_PATH.parent
        pstat = parent.lstat()
        fstat = KEY_PATH.lstat()
        if (
            stat.S_ISLNK(fstat.st_mode)
            or not stat.S_ISREG(fstat.st_mode)
            or pstat.st_uid != 0
            or fstat.st_uid != 0
            or bool(pstat.st_mode & 0o022)
            or bool(fstat.st_mode & 0o022)
        ):
            raise ApprovalRefused("TRUSTED_OWNER_PUBLIC_KEY_NOT_PROTECTED")
        key = KEY_PATH.read_bytes()
        if len(key) != 32:
            raise ApprovalRefused("TRUSTED_OWNER_PUBLIC_KEY_MALFORMED")
        return key
    except OSError as exc:
        raise ApprovalRefused("TRUSTED_OWNER_PUBLIC_KEY_NOT_PROVISIONED") from exc


def verify_signed_owner_approval(
    path: str,
    *,
    expected: dict[str, Any],
    now: datetime | None = None,
    public_key_for_test: bytes | None = None,
) -> str:
    """Return only a digest of a valid signed, exact-scope approval; never its contents."""
    if not path:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_FILE_MISSING")
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 8192:
            raise ApprovalRefused("SIGNED_OWNER_APPROVAL_TOO_LARGE")
        approval = json.loads(raw)
        payload = approval["payload"]
        encoded_signature = approval["signature"]
        if not isinstance(payload, dict) or not isinstance(encoded_signature, str):
            raise ApprovalRefused("SIGNED_OWNER_APPROVAL_INVALID")
        signature = base64.b64decode(encoded_signature, validate=True)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        binascii.Error,
    ) as exc:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_MISSING_OR_INVALID") from exc
    key = public_key_for_test if public_key_for_test is not None else _read_trusted_public_key()
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, body)
    except (ValueError, InvalidSignature) as exc:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_SIGNATURE_INVALID") from exc
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ApprovalRefused("SIGNED_OWNER_APPROVAL_SCOPE_MISMATCH")
    if set(payload) != set(expected) | {"issued_at", "expires_at", "nonce"}:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_FIELDS_INVALID")
    try:
        issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_DATES_INVALID") from exc
    current = now or datetime.now(UTC)
    if (
        issued.tzinfo is None
        or expiry.tzinfo is None
        or not (issued <= current < expiry <= issued + MAX_LIFETIME)
    ):
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_EXPIRED_OR_INVALID_PERIOD")
    nonce = payload["nonce"]
    if not isinstance(nonce, str) or len(nonce) < 24:
        raise ApprovalRefused("SIGNED_OWNER_APPROVAL_NONCE_INVALID")
    return "approval_sha256:" + hashlib.sha256(body + signature).hexdigest()
