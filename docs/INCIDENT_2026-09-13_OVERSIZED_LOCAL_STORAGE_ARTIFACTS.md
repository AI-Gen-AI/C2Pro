# Incident — Oversized local-storage artifacts (2026-09-13)

## Status

Forensic closeout: **producer not proven from retained telemetry**.

The two oversized artifacts were removed only after exact-path verification, size/block inspection, and confirmation that no process held them open. Disk usage returned to a normal level afterwards.

This document records verified evidence, rejected interpretations, and operational guardrails. It deliberately does **not** claim a root cause that the evidence cannot prove.

## Verified evidence

Two files under `/tmp/c2pro-uploads/.../revisions/` occupied approximately 26 GiB and 25 GiB respectively. Both used the same content-addressed filename:

`43fb0c19d2f86d42b22d794d03062a6cfbd3a6592ada26bbb05aae52d12a7106.pdf`

That SHA-256 is the hash used by the durability verification fixture for:

`Revision A content - Durable document plane verification`

The oversized files had mtimes around 2026-09-13 19:06 UTC and 19:14 UTC.

A later successful run of `apps/api/scripts/verify_p0b_durability_revisions.py` occurred at about 2026-09-13 22:30 UTC and created normal three-revision durability artifacts. Therefore that observed successful invocation cannot itself be the producer of the earlier oversized files.

The retained script version uses a small `io.BytesIO(content_a)` and the local storage implementation copies the underlying binary stream with `shutil.copyfileobj()`. That captured version, by itself, does not demonstrate an unbounded-write mechanism.

The two large files were deleted after `lsof`/open-handle checks showed no active holder. After deletion, `/tmp/c2pro-uploads` fell to less than 1 MiB and filesystem usage fell to about 24%.

## What the investigation did not prove

The evidence does **not** identify the exact process, PID, command, code revision, or call path that produced the oversized artifacts.

A repeated-56-byte-write mechanism remains technically plausible because of the content hash and size pattern, but it is not established as root cause.

Large retrospective `rg`/string searches over Gemini/Codex session JSONL files produced many later matches because historic context and copied transcripts contain the same strings. String presence in an accumulated session log is therefore **not provenance evidence** unless it is tied to a concrete timestamped tool invocation or process event.

Records with `timestamp=None`, repeated imported context, and later conversation snapshots further reduce the value of those logs as a strict event ledger.

## Lessons learned

1. **Do not equate textual occurrence with execution provenance.** Attribution requires at least timestamp + action/tool call + target path/process evidence.
2. **Preserve temporal ordering first.** File `mtime`/`ctime`, process logs, shell history, and agent tool-call timestamps should be reconciled before searching by content.
3. **Bound forensic searches.** Never recursively scan large binary/temp trees without `--max-filesize` and explicit exclusions such as `node_modules`, `.next`, `.git`, upload roots, and generated artifacts.
4. **Capture evidence before cleanup.** Record `stat`, `du`, `df`, inode, owner, timestamps, and open-handle state before deleting anomalous files.
5. **Test storage must be disposable and observable.** Long-running agent/test campaigns should use a dedicated temporary storage root with explicit start/end accounting and cleanup.
6. **A successful later reproduction does not explain an earlier anomaly.** Keep observed runs separate from inferred historical behavior.
7. **When telemetry is exhausted, stop.** Record the incident as unresolved rather than continuing low-signal searches or inventing a causal narrative.

## Preventive guardrails for future campaigns

These are operational safeguards, not claims about root cause:

- Allocate a unique temp storage root per verification/test campaign.
- Record campaign metadata: UTC start/end, PID/PGID, worktree, branch, HEAD SHA, storage root, and invoked command.
- Record storage size before and after the campaign.
- Fail/abort a campaign when its temp-storage delta exceeds a defined safety budget.
- Ensure cleanup runs in `finally`/teardown paths and report cleanup success explicitly.
- For forensic commands, default to bounded searches (`--max-filesize`) and exclude upload/storage trees unless the storage tree is the explicit target.
- Keep generated test artifacts out of shared long-lived `/tmp` namespaces where practical.

## Closure decision

The 2026-09-13 oversized-file event is closed as **forensically indeterminate with retained evidence**. No production-code causal fix should be justified solely from this incident without a reproducible failure or new evidence. The actionable outcome is improved campaign isolation, telemetry, storage-budget guarding, and bounded forensic procedure.
