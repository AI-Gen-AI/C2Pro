"""Pure, sanitized S3 worker-log counters for ephemeral acceptance runs.

Never return log lines, UUIDs, source payloads, tokens, or model outputs.
"""

from __future__ import annotations

import re

_SNAPSHOT = re.compile(
    r"\bTask project_snapshots\.write\[[a-fA-F0-9-]{36}\]\s+"
    r"(received|succeeded|failed|retry|retried)\b"
)


def summarize_s3_worker_diagnostics(raw_log: str) -> dict[str, int | str]:
    counts = {"received": 0, "succeeded": 0, "failed": 0, "retried": 0}
    enqueue_failed = 0
    write_failed = 0
    coherence_failed = 0
    for line in raw_log.splitlines():
        match = _SNAPSHOT.search(line)
        if match is not None:
            kind = match.group(1)
            if kind in ("retry", "retried"):
                kind = "retried"
            counts[kind] += 1
        enqueue_failed += "project_snapshot_enqueue_failed" in line
        write_failed += "project_snapshot_write_failed" in line
        coherence_failed += "node_coherence_scorer_failed" in line
    return {
        "schema": "c2pro-s3-worker-counters/v1",
        "snapshot_task_received": counts["received"],
        "snapshot_task_succeeded": counts["succeeded"],
        "snapshot_task_failed": counts["failed"],
        "snapshot_task_retried": counts["retried"],
        "snapshot_enqueue_failed": int(enqueue_failed),
        "snapshot_write_failed": int(write_failed),
        "n8_node_failed": int(coherence_failed),
    }
