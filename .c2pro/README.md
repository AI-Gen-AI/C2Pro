# C2Pro governed development control

This directory is the compact, vendor-neutral development-control surface introduced by `C2PRO-DEV-01`.

Default hot context is intentionally small:
- `control/current.yaml`
- `control/work-queue.yaml`
- the referenced active work envelope, when one exists
- a handoff/evidence reference only when the current work requires it

Historical execution detail remains in Git, pull requests, CI and legacy cold references. Completed work must not accumulate in the hot queue.

The legacy supervisor, blackboard and Markdown backlogs remain untouched during the transition and are governed by `control/legacy-compatibility.yaml`. This directory does not activate AF-DEV/MR-DEV runtime execution by itself.
