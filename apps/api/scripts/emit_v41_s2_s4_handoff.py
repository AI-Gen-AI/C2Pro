#!/usr/bin/env python3
"""Emit the A-side, non-promotable S2/S4 provenance handoff offline.

Run inside the private recovered-evidence directory. Exact packet SHA
supplied by the operator; fixed input/output filenames (no traversal).
No network, provider, database, grants, approval, or Coherence invocation.

Example:
    python /repo/apps/api/scripts/emit_v41_s2_s4_handoff.py <64-hex-packet-sha>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from src.analysis.application.v41_s2_s4_handoff import (
    S2S4HandoffError,
    create_pending_s2_s4_manifest,
)

INPUT = "n4_offline_review_packet_sec_verified.json"
OUTPUT = "s2_s4_handoff_manifest.json"


def emit(*, root: Path, expected_packet_sha256: str) -> dict:
    if not isinstance(expected_packet_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_packet_sha256,
    ):
        raise S2S4HandoffError("SHA256_INPUT_REQUIRED")
    source = root / INPUT
    target = root / OUTPUT
    if source.is_symlink() or target.is_symlink():
        raise S2S4HandoffError("SYMLINK_FILE_REFUSED")
    if not source.is_file() or source.stat().st_size > 3_000_000:
        raise S2S4HandoffError("REVIEW_PACKET_NOT_PRESENT_OR_TOO_LARGE")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_packet_sha256:
        raise S2S4HandoffError("REVIEW_PACKET_SHA256_MISMATCH")
    try:
        packet = json.loads(raw)
        handoff = create_pending_s2_s4_manifest(packet)
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise S2S4HandoffError("INVALID_RECOVERED_REVIEW_PACKET") from exc
    payload = (json.dumps(
        handoff, sort_keys=True, indent=2, ensure_ascii=False,
    ) + "\n").encode("utf8")
    # Never overwrite an existing source of decision provenance.
    try:
        fd = os.open(
            target,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise S2S4HandoffError("HANDOFF_ALREADY_EXISTS") from exc
    return {
        "status": "S2_TO_S4_PROPOSAL_HANDOFF_ONLY",
        "source_packet_sha256": expected_packet_sha256,
        "s2_s4_handoff_sha256": handoff["handoff_sha256"],
        "proposal_count": handoff["proposed_count"],
        "pending_human_review": handoff["pending_human_review_count"],
        "trusted": False,
        "s4_provider_call_authorized": False,
        "projectgraph_promotion_authorized": False,
    }


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise S2S4HandoffError("EXPECTED_EXACT_PACKET_SHA256")
        result = emit(
            root=Path.cwd().resolve(),
            expected_packet_sha256=sys.argv[1],
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (S2S4HandoffError, OSError) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc)[:100],
            "trusted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
