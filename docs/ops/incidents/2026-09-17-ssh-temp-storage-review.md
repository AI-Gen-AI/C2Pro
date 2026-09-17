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

A size audit on 2026-09-17 found two temporary C2Pro revision artifacts under `/tmp/c2pro-uploads` with apparent sizes of approximately 26 GiB and 25 GiB. They belonged to different tenant/project/document paths but shared the same SHA-256-like revision filename:

`43fb0c19d2f86d42b22d794d03062a6cfbd3a6592ada26bbb05aae52d12a7106.pdf`

The two artifacts were timestamped only minutes apart on 2026-09-13.

If the filename is intended to identify immutable final content, the same digest-like name combined with different apparent sizes is anomalous. This observation is evidence, not a proven root cause. Possible explanations such as repeated writes/appends, sparse-file behaviour, mutation after revision naming, or a test harness defect must be verified from the write path rather than assumed.

Because the artifacts are under `/tmp`, cleanup should target the exact files after confirming that no process still has them open. A broad purge of `/tmp/c2pro-uploads` is not justified by this finding.

## Engineering follow-up

The development investigation should proceed from the write path rather than from the symptom:

- Reproduce the oversized-revision behaviour with the smallest failing test or controlled script possible.
- Trace revision creation/writing and the durability verification path, including `apps/api/scripts/verify_p0b_durability_revisions.py` where relevant.
- Verify whether the revision filename is defined as a content digest and whether revision objects are expected to be immutable after finalisation.
- Assert bounded final size and, if applicable, digest/content consistency at the point a revision becomes durable.
- Apply one root-cause fix at a time and add regression coverage before introducing cleanup/monitoring mechanisms.
- Treat retention or temporary-storage limits as defence-in-depth, not as a substitute for fixing an unbounded write path if one is confirmed.

## Operational principle

For incident/debugging work: **evidence first, bounded search second, exact cleanup third, root-cause regression test before code repair**.
