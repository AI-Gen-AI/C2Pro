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

The September 13 `overnight-20260912-gemini` worktree was then inspected. Its document use cases implement the exact scoped namespace observed on disk:

`tenants/<tenant_id>/projects/<project_id>/documents/<document_id>/revisions/<sha256>.<ext>`

In that worktree, initial upload computes `file_hash = sha256(content_bytes)`, builds the scoped `blob_key`, resets the upload stream to position zero, and passes the stream plus that key to `storage_service.upload_file(...)`. The re-upload path builds the same scoped form and persists through `upload_bytes(...)` when the blob does not already exist.

This materially narrows the investigation:

1. The path shape of the oversized artifacts is no longer unexplained: it is directly implemented in the September 13 development worktree.
2. The current `main` storage path is therefore not representative of the code family active when the files were created.
3. The two different files sharing the same digest-like filename while having different byte sizes remains inconsistent with a normal immutable content-addressed write.
4. This still does not prove which process or exact execution-time code produced the growth; the producer must be tied to the 2026-09-13 19:06–19:15 UTC execution window before repair.

## Critical narrowing: Revision A hash and local writer

Further inspection of `apps/api/scripts/verify_p0b_durability_revisions.py` and the September 13 local storage adapter produced a stronger constraint.

The durability script defines:

`content_a = b"Revision A content - Durable document plane verification"`

This payload is exactly 56 bytes. Its SHA-256 is:

`43fb0c19d2f86d42b22d794d03062a6cfbd3a6592ada26bbb05aae52d12a7106`

That digest is exactly the filename shared by both oversized artifacts. Therefore the revision key was derived from the small synthetic Revision A payload, not from the final 25–26 GiB file contents.

The same worktree's `LocalFileStorageService` implements initial upload as:

- `with open(dest, "wb") as f:`
- `shutil.copyfileobj(file_content, f)`

and re-upload as `dest.write_bytes(data)`.

Both mechanisms replace/truncate the destination rather than append. In the currently inspected durability script, the initial upload passes `fake_file.file = io.BytesIO(content_a)`, so the source stream for Revision A is also only 56 bytes.

Consequences:

1. A normal execution of the currently inspected durability script together with the currently inspected local storage adapter cannot by itself produce a 25–26 GiB Revision A object.
2. Simple repeated append in `LocalFileStorageService` is ruled out for this code state.
3. The hash-to-bytes invariant definitely diverged: a key naming the SHA-256 of a 56-byte payload ended up associated with tens of gigabytes of bytes.
4. Because two different tenant/project/document paths contain the same Revision A digest, the evidence is consistent with at least two separate synthetic durability runs or equivalent producers, but the exact process is not yet proven.
5. Remaining plausible classes of explanation are now narrower: execution-time code differed from the currently inspected files, another writer mutated the destination after creation, or a different storage/service wrapper intercepted the operation.
6. `path_a.read_bytes()` in the durability verifier is read-only and may explain severe memory pressure if invoked after a file had already become huge, but it cannot explain creation of the oversized file.

A bounded search of the previously suspected Codex session returned `MATCHES=0` for the exact digest, tenant IDs, payload text and durability script name. That specific Codex session is therefore not supported as the producer by the retained session evidence checked so far. The `overnight-20260912-gemini` worktree name and local Gemini state remain relevant provenance leads.

## Strong repeated-payload signature

The two anomalous file sizes are not merely large; both are exact integer multiples of the 56-byte Revision A payload size:

- `27,334,097,224 / 56 = 488,108,879`
- `26,389,299,104 / 56 = 471,237,484`

The remainders are zero in both cases.

This is highly unlikely to be an incidental size relationship. Together with the filename being the SHA-256 of that same 56-byte payload, it strongly supports a runaway repeated-read/repeated-write mechanism involving Revision A rather than arbitrary later corruption.

One concrete mechanism capable of producing this signature is a stream-like test double whose `read()` returns the same 56-byte payload on every call and never returns `b""` at EOF, when consumed by a loop such as `shutil.copyfileobj(...)`. The current script avoids that failure because `storage_service.upload_file(...)` receives `fake_file.file`, an `io.BytesIO(content_a)` that reaches EOF normally. However, because the script is untracked, an earlier version could have wired the fake object or another non-terminating reader directly into the storage copy path.

This remains a strong hypothesis rather than final proof because the oversized files were deleted before their complete byte pattern could be inspected. The next forensic step should therefore look specifically for historical script/test-double variants in which the storage source's `read()` did not terminate at EOF.

## Gemini execution evidence and script provenance

The worktree was confirmed at:

- HEAD `09a2e58bd744c06f41ee49a53ad9af31190fdd17`
- branch `feat/product-durable-document-plane`
- `apps/api/scripts/verify_p0b_durability_revisions.py` is **untracked** in the worktree.

This is an important evidence limitation: Git cannot establish which version of that script existed at the 19:06–19:15 UTC oversized-file creation window. The current untracked file must not be treated as historical execution truth.

A retained Gemini session does prove a later execution of the durability verifier. Gemini invoked:

`STORAGE_PROVIDER=local apps/api/.venv/bin/python3 apps/api/scripts/verify_p0b_durability_revisions.py`

The later run logged the local-storage fallback to `/tmp/c2pro-uploads`, created a normal Revision A object named with the same digest `43fb0c...7106.pdf`, then created Revision B and C objects under their respective content hashes. All three hash/content durability assertions passed.

The command output timestamps place this successful run around `2026-09-13 22:30 UTC`, more than three hours after the two anomalous files' mtimes (`19:06` and `19:14 UTC`). Its tenant/project/document identifiers also differ from the anomalous artifact paths.

Therefore:

1. The later Gemini run is a **working control example**, not the producer of the two oversized artifacts.
2. It demonstrates that the then-current visible script + local-storage path could complete normally and preserve the hash-to-bytes invariant.
3. It does not prove that the same untracked script contents were present during the earlier anomalous executions.
4. The forensic target is now specifically the earlier Gemini/agent activity around `18:55–19:20 UTC`, not the later 22:30 successful verification.
5. A subsequent broad pytest run in the same Gemini session produced database/test-environment failures (missing `nonsuperuser` role and tests targeting PostgreSQL on 5432 while the disposable test database was on 5433). Those failures are separate from the oversized-file creation unless new evidence links them.

This is a useful debugging pattern: when an untracked harness later passes, preserve it as a control but do not retroactively assume it matches the failing historical harness.

## Engineering follow-up

Proceed with root-cause investigation before making a code change:

- Recover bounded Gemini/agent records specifically around 2026-09-13 18:55–19:20 UTC and extract only commands/file edits involving the durability verifier, local storage, upload/reupload paths, `FakeFile`, `_async_read`, `copyfileobj`, or `/tmp/c2pro-uploads`.
- Capture the untracked script's filesystem birth/mtime/ctime. If its birth or modification time is later than the anomalous mtimes, the current script is definitively not the producer version.
- Look specifically for an earlier fake stream/test double whose `read()` can return Revision A indefinitely instead of reaching EOF.
- Inspect `get_storage_service()` and any wrapper/dependency-injection path active in that worktree to prove which concrete storage implementation the earlier execution received.
- Check Git/worktree state and file history for `local_file_storage_service.py` at the artifact creation window rather than assuming today's worktree contents are historical truth.
- Reconstruct the data flow from test payload -> `UploadFile`/bytes -> hash -> scoped key -> concrete storage writer -> later mutations.
- Once the producer is known, reproduce the behaviour with the smallest failing test or controlled script possible.
- Apply one root-cause fix at a time and add regression coverage before introducing cleanup/monitoring mechanisms.
- Treat retention or temporary-storage limits as defence-in-depth, not as a substitute for fixing an unbounded write path if one is confirmed.

## Operational principle

For incident/debugging work: **evidence first, bounded search second, exact cleanup third, root-cause regression test before code repair**.
