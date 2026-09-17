# 2026-09-17 — SSH access review and temporary-storage investigation

## Scope and outcome

A review was performed after SSH access activity and an apparently stalled recursive search raised concern on the C2Pro/AI-Gen VPS.

Based on the retained authentication logs available during the review:

- No successful SSH login using a password was found for the administrative account.
- Observed successful administrative access was public-key based and originated from known Tailscale devices.
- The previously unidentified ECDSA key was identified by its historical comment as an iPhone administration key and was already present in the `authorized_keys` backup created before the newer FaceID key was added. It is intentionally retained.
- A separate Windows key was also corroborated by successful logins from the known Windows Tailscale device.
- No evidence of SSH compromise was found in the retained logs reviewed. This conclusion is bounded by the available log-retention window and is not proof about periods for which logs are unavailable.

## Diagnostic-process lesson

A broad recursive filesystem search appeared to be blocked. The search was read-only and was safely interrupted with `Ctrl-C`; the problem was the unbounded search scope, not an SSH or VPS lockup.

For future investigations:

1. Start read-only and scope searches to the smallest known directory or file set.
2. Prefer `rg` with path exclusions and `--max-filesize`, or `find` with explicit size/path filters, over unbounded recursive `grep` across development or storage trees.
3. Add `timeout` to exploratory recursive searches when completion time is not predictably bounded.
4. Avoid hashing or recursively scanning very large artifacts unless the hash itself is required evidence.
5. Record enough evidence before cleanup: path, apparent size, allocated size where relevant, timestamp, ownership and whether the file is open.
6. If a read-only investigation produces no bounded progress, interrupt it rather than treating the delay as evidence of system failure.

## SSH-key review rule

Before removing an authorized key, map as much of the following as possible:

`fingerprint -> key comment/device -> Tailscale source -> retained authentication history -> historical authorized_keys backups`

A key must not be deleted solely because it has no recent hit in retained authentication logs.

## Temporary-storage anomaly discovered during the review

A size audit on 2026-09-17 found two temporary C2Pro revision artifacts under `/tmp/c2pro-uploads`:

- 27,334,097,224 bytes (reported as ~26 GiB), mtime `2026-09-13 19:06:06 UTC`
- 26,389,299,104 bytes (reported as ~25 GiB), mtime `2026-09-13 19:14:53 UTC`

They belonged to different tenant/project/document paths but shared the same SHA-256-like revision filename:

`43fb0c19d2f86d42b22d794d03062a6cfbd3a6592ada26bbb05aae52d12a7106.pdf`

`du` and `du --apparent-size` both reported approximately the same sizes for each file, while `stat` showed allocated block counts consistent with the files consuming real disk blocks. This rules out the simple explanation that they were merely large sparse files.

No open handle was reported by the bounded `lsof` check. The two exact files were then removed successfully. Post-cleanup verification showed:

- both target paths absent;
- `/tmp/c2pro-uploads` reduced to approximately 748 KiB;
- root filesystem usage reduced to approximately 90 GiB used / 297 GiB available (24%).

This cleanup removed the immediate storage pressure but does not establish root cause.

## Code-path evidence after cleanup

Inspection of current `main` identified the local storage fallback and revision write path:

- `LocalFileStorageService` falls back from `/app/uploads` to `${TMPDIR}/c2pro-uploads` when the preferred directory cannot be used.
- `upload_bytes()` creates parent directories and uses `Path.write_bytes(data)`, which replaces/truncates the destination rather than appending to it.
- Current upload/re-upload use cases generate revision blob names from a SHA-256 of `file_content`, using keys of the form `revisions/<sha256>.<ext>`.

This narrows the investigation:

1. The oversized artifacts cannot be explained by the current `upload_bytes()` implementation simply appending the same payload repeatedly.
2. The observed artifact paths were tenant/project/document-scoped (`tenants/.../projects/.../documents/.../revisions/...`), while the current `main` use cases pass a relative `revisions/<sha256>.<ext>` key to the local storage adapter.
3. Therefore the artifacts may have been produced by a different code revision, a test/verification harness, or a scoped-storage wrapper active in the September 13 development worktree rather than by the exact current `main` path.

These are evidence-backed constraints, not yet a root-cause conclusion.

## Engineering follow-up

Proceed with root-cause investigation before making a code change:

- Identify the exact commit/worktree/process that created the two files on 2026-09-13 around 19:06–19:15 UTC.
- Inspect the P0b durability verification path and any scoped-storage implementation that builds tenant/project/document revision paths.
- Reconstruct the write loop and establish whether the size growth came from generated test payload size, repeated concatenation before `upload_bytes()`, mutation of an already named content-addressed artifact, or another producer.
- Compare the producer's storage implementation with current `main`.
- Once the producer is known, reproduce the behaviour with the smallest failing test or controlled script possible.
- Apply one root-cause fix at a time and add regression coverage before introducing cleanup/monitoring mechanisms.
- Treat retention or temporary-storage limits as defence-in-depth, not as a substitute for fixing an unbounded write path if one is confirmed.

## Operational principle

For incident/debugging work: **evidence first, bounded search second, exact cleanup third, root-cause regression test before code repair**.
