"""Exact-scope, offline owner-signature gate for pilot first-admin elevation."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts import pilot_owner_approval as approval

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
SCOPE = {
    "action": approval.ACTION,
    "railway_project_id": "44d57536-aca6-4ea0-bc0c-58ce1a5f8eba",
    "railway_environment_id": "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e",
    "project_id": "5992eb43-90ef-4d2a-983a-97695e13abfc",
    "tenant_id": "00000000-0000-0000-0000-0000000000aa",
    "user_id": "00000000-0000-0000-0000-0000000000bb",
    "clerk_user_id": "user_test_bound_to_approval",
    "operator_role": "c2pro_owner",
    "self_review_reason_sha256": None,
}


def _signed(
    path: Path,
    *,
    payload_overrides: dict | None = None,
    signer: Ed25519PrivateKey | None = None,
) -> bytes:
    private = signer or Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload = {
        **SCOPE,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(minutes=20)).isoformat(),
        "nonce": "0123456789abcdef0123456789abcdef",
        **(payload_overrides or {}),
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    signature = private.sign(body)
    path.write_text(
        json.dumps({"payload": payload, "signature": base64.b64encode(signature).decode()})
    )
    return public


def test_valid_signature_is_bound_to_scope_and_reports_only_digest(tmp_path: Path) -> None:
    file = tmp_path / "owner.json"
    public = _signed(file)
    receipt = approval.verify_signed_owner_approval(
        str(file), expected=SCOPE, now=NOW, public_key_for_test=public
    )
    assert receipt.startswith("approval_sha256:")
    assert "user_test_bound_to_approval" not in receipt


@pytest.mark.parametrize(
    "field,changed",
    [
        ("tenant_id", "00000000-0000-0000-0000-0000000000cc"),
        ("user_id", "00000000-0000-0000-0000-0000000000cc"),
        ("clerk_user_id", "user_wrong"),
        ("operator_role", "postgres"),
        ("project_id", "00000000-0000-0000-0000-0000000000dd"),
        ("self_review_reason_sha256", "forged_exception"),
    ],
)
def test_owner_signature_for_other_identity_or_project_refuses(
    tmp_path: Path, field: str, changed: str
) -> None:
    file = tmp_path / "owner.json"
    public = _signed(file, payload_overrides={field: changed})
    with pytest.raises(approval.ApprovalRefused, match="SCOPE_MISMATCH"):
        approval.verify_signed_owner_approval(
            str(file), expected=SCOPE, now=NOW, public_key_for_test=public
        )


def test_tampering_a_valid_payload_refuses(tmp_path: Path) -> None:
    file = tmp_path / "owner.json"
    public = _signed(file)
    contents = json.loads(file.read_text())
    contents["payload"]["tenant_id"] = "00000000-0000-0000-0000-0000000000cc"
    file.write_text(json.dumps(contents))
    with pytest.raises(approval.ApprovalRefused, match="SIGNATURE_INVALID"):
        approval.verify_signed_owner_approval(
            str(file), expected=SCOPE, now=NOW, public_key_for_test=public
        )


def test_other_signer_cannot_approve(tmp_path: Path) -> None:
    file = tmp_path / "owner.json"
    expected_public_key = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    )
    _signed(file)
    with pytest.raises(approval.ApprovalRefused, match="SIGNATURE_INVALID"):
        approval.verify_signed_owner_approval(
            str(file), expected=SCOPE, now=NOW, public_key_for_test=expected_public_key
        )


@pytest.mark.parametrize(
    "overrides,expected_error",
    [
        ({"expires_at": (NOW - timedelta(seconds=1)).isoformat()}, "EXPIRED"),
        ({"issued_at": (NOW + timedelta(hours=1)).isoformat()}, "EXPIRED"),
        ({"expires_at": (NOW + timedelta(days=2)).isoformat()}, "EXPIRED"),
        ({"nonce": "short"}, "NONCE"),
        ({"extra": "surplus"}, "FIELDS_INVALID"),
    ],
)
def test_stale_or_malformed_signed_owner_approval_fails_closed(
    tmp_path: Path, overrides: dict, expected_error: str
) -> None:
    file = tmp_path / "owner.json"
    public = _signed(file, payload_overrides=overrides)
    with pytest.raises(approval.ApprovalRefused, match=expected_error):
        approval.verify_signed_owner_approval(
            str(file), expected=SCOPE, now=NOW, public_key_for_test=public
        )


def test_missing_trusted_key_refuses_even_with_well_signed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "owner.json"
    _signed(file)
    monkeypatch.setattr(approval, "KEY_PATH", tmp_path / "unprovisioned-root-key")
    with pytest.raises(approval.ApprovalRefused, match="NOT_PROVISIONED"):
        approval.verify_signed_owner_approval(str(file), expected=SCOPE, now=NOW)
