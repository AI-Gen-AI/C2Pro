#!/usr/bin/env python3
"""C2Pro Task-first PR audit. Read-only; never grants WORK or acceptance authority."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_MASTER = Path("validation/product/c2pro-master-product-control-v1.yaml")
DEV_QUEUE = Path(".c2pro/control/work-queue.yaml")
DELIVERY_SPEC = Path("docs/product/pq-hitl-2026-01-delivery-spec-v1.md")
DEV_ISSUES = {"C2PRO-DEV-14": 991}
DEV_SDD = {"C2PRO-DEV-14": "docs/architecture/development/c2pro-dev14-task-first-traceability-sdd-v1.md"}
DEV14_CHANGED_PATHS = (
    "scripts/development/", "tests/development/", ".c2pro/schemas/",
    ".c2pro/product-work/", "docs/architecture/development/", ".github/workflows/",
)
ALLOWED_EFFECTS = {"SPEC_ONLY", "IMPLEMENTATION_ONLY", "PRODUCT_ACCEPTANCE_PROPOSED"}
SPEC_DOC_PATHS = ("docs/architecture/development/", "docs/product/")
TRACE_KEYS = {"schema", "primary_task", "task_claims", "effect_claim", "defects", "execution_mode"}
CLAIM_KEYS = {"task_id", "parent_issue", "sdd_path", "acceptance_ids",
              "execution_work_id", "work_envelope_path", "workspace_evidence_ref"}


class TraceError(ValueError):
    """PR cannot be proven consistent with approved C2Pro task authority."""


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently accepting last writer."""


def _unique_mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, val_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise TraceError("non-string YAML key")
        if key in result:
            raise TraceError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(val_node, deep=True)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def safe_yaml(text: str) -> dict[str, Any]:
    try:
        value = yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise TraceError("invalid YAML metadata") from exc
    if not isinstance(value, dict):
        raise TraceError("metadata must be mapping")
    return value


def safe_path(root: Path, raw: Any, *, must_exist: bool = True) -> Path:
    if not isinstance(raw, str) or not raw or len(raw) > 255:
        raise TraceError("unsafe/empty path")
    target = Path(raw)
    if target.is_absolute() or any(part in (".", "..") for part in target.parts):
        raise TraceError("unsafe path traversal")
    path = root / target
    if path.is_symlink() or path.resolve(strict=False) != (root.resolve() / target):
        raise TraceError("unsafe symlink path")
    if must_exist and not path.is_file():
        raise TraceError(f"missing approved path: {raw}")
    return path


def read_approved_source(root: Path, rel: str, base_sha: str | None) -> str:
    """Load authority only from effective pre-PR Git base when available."""
    if base_sha is None:
        return safe_path(root, rel).read_text()
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise TraceError("invalid approved base SHA")
    safe_path(root, rel, must_exist=False)
    result = subprocess.run(
        ["git", "show", f"{base_sha}:{rel}"], cwd=root,
        capture_output=True, check=False,
    )
    if result.returncode:
        raise TraceError(f"source absent from approved base: {rel}")
    return result.stdout.decode("utf-8")


def load_registry(root: Path = ROOT, base_sha: str | None = None) -> dict[str, dict[str, Any]]:
    """Use canonical Product MASTER parent IDs and existing signed-off delivery spec.

    Atomic Product IDs come from numbered packages *under the correct parent section*,
    not arbitrary implementation fixture names or the text of a PR.
    """
    master = safe_yaml(read_approved_source(root, PRODUCT_MASTER.as_posix(), base_sha))
    data = master.get("product_quality_hitl_2026_10_08", {})
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise TraceError("Product MASTER tasks missing")
    registry: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("issue"), int):
            raise TraceError("malformed Product MASTER task")
        name = task.get("id")
        if not isinstance(name, str) or not re.fullmatch(r"PQ-HITL-\d{2}", name):
            raise TraceError("malformed Product Task")
        if name in registry:
            raise TraceError("duplicate Product Task")
        registry[name] = {"issue": task["issue"], "source": PRODUCT_MASTER.as_posix(), "sdd_path": DELIVERY_SPEC.as_posix(),
                          "acceptance_ids": set()}
    spec_path = data.get("delivery_specification", {}).get("spec_ref")
    if spec_path != DELIVERY_SPEC.as_posix():
        raise TraceError("Product delivery spec source drift")
    contents = read_approved_source(root, spec_path, base_sha)
    active_parent = None
    for line in contents.splitlines():
        match = re.match(r"^### (\d{2}) · (PQ-HITL-\d{2}) / #(\d+)", line)
        if match:
            n, active_parent, issue = match.groups()
            if active_parent not in registry or active_parent != "PQ-HITL-" + n:
                raise TraceError("delivery parent not in Product MASTER")
            if registry[active_parent]["issue"] != int(issue):
                raise TraceError("delivery parent issue disagrees with MASTER")
            continue
        if line.startswith("### "):
            active_parent = None
        item = re.match(r"^- \*\*(\d{2}\.\d+)\*\*\s+", line)
        if item and active_parent:
            atomic_id = "PQ-HITL-" + item.group(1)
            if not atomic_id.startswith(active_parent + ".") or atomic_id in registry:
                raise TraceError("duplicate/mismatched atomic Task")
            registry[atomic_id] = {
                "issue": registry[active_parent]["issue"],
                "source": spec_path, "sdd_path": spec_path,
                "acceptance_ids": {atomic_id},
            }
    queue = safe_yaml(read_approved_source(root, DEV_QUEUE.as_posix(), base_sha))
    for item in queue.get("items", []):
        dev_id = item.get("work_id")
        if dev_id in DEV_ISSUES:
            sdd_text = read_approved_source(root, DEV_SDD[dev_id], base_sha)
            ids = set(re.findall(r"^\| (TRACE-\d{2}) \|", sdd_text, re.M))
            if not ids:
                raise TraceError("DEV SDD missing stable TRACE acceptance IDs")
            registry[dev_id] = {"issue": DEV_ISSUES[dev_id],
                                "source": DEV_QUEUE.as_posix(), "sdd_path": DEV_SDD[dev_id],
                                "acceptance_ids": ids}
    return registry


def parse_trace(body: str) -> dict[str, Any] | None:
    if not isinstance(body, str) or len(body.encode("utf-8")) > 16000:
        raise TraceError("PR body missing or oversized")
    fence = re.escape(chr(96) * 3)
    pattern = fence + r"(?:yaml|yml)\s*\n(.*?)\n" + fence
    blocks = re.findall(pattern, body, flags=re.I | re.S)
    matches = []
    for block in blocks:
        if "c2pro_trace:" not in block:
            continue
        doc = safe_yaml(block)
        if "c2pro_trace" not in doc or len(doc) != 1:
            raise TraceError("trace block must contain only c2pro_trace")
        matches.append(doc["c2pro_trace"])
    if len(matches) > 1:
        raise TraceError("multiple trace blocks")
    if not matches:
        return None
    if not isinstance(matches[0], dict):
        raise TraceError("c2pro_trace is not mapping")
    return matches[0]


def validate_effect(effect: str, changed_paths: list[str]) -> None:
    if effect not in ALLOWED_EFFECTS:
        raise TraceError("invalid effect_claim")
    for path in changed_paths:
        if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts:
            raise TraceError("invalid changed path")
        if effect == "SPEC_ONLY":
            if (not path.startswith(SPEC_DOC_PATHS)
                    or path == "docs/product/00-c2pro-master-product-control-v1.md"
                    or not path.endswith(".md")):
                raise TraceError(f"SPEC_ONLY rejects changed path: {path}")


def validate_claims(meta: dict[str, Any], registry: dict[str, dict[str, Any]],
                    root: Path = ROOT, base_sha: str | None = None) -> None:
    if set(meta) - TRACE_KEYS or meta.get("schema") != "c2pro-pr-task-trace-v1":
        raise TraceError("unsupported/unknown trace schema keys")
    effect = meta.get("effect_claim")
    execution_mode = meta.get("execution_mode", "AGENT_WORK")
    if execution_mode not in {"AGENT_WORK", "OWNER_SUPERVISED"}:
        raise TraceError("invalid execution_mode")
    if effect not in ALLOWED_EFFECTS:
        raise TraceError("invalid effect_claim")
    claims = meta.get("task_claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
        raise TraceError("task_claims must have 1..8 claims")
    primary = meta.get("primary_task")
    seen: set[str] = set()
    for c in claims:
        if not isinstance(c, dict) or set(c) - CLAIM_KEYS:
            raise TraceError("malformed/unknown Task claim keys")
        task = c.get("task_id")
        if not isinstance(task, str) or task not in registry:
            raise TraceError(f"unknown canonical Task: {task}")
        if task in seen:
            raise TraceError("duplicate task claim")
        seen.add(task)
        canonical = registry[task]
        if isinstance(c.get("parent_issue"), bool) or c.get("parent_issue") != canonical["issue"]:
            raise TraceError(f"parent_issue mismatch for {task}")
        sdd = c.get("sdd_path")
        if not isinstance(sdd, str) or not (sdd.startswith("docs/") and sdd.endswith(".md")):
            raise TraceError("invalid sdd_path")
        if sdd != canonical.get("sdd_path"):
            raise TraceError("sdd_path is not canonical for Task")
        read_approved_source(root, sdd, base_sha)
        acceptance = c.get("acceptance_ids")
        if not isinstance(acceptance, list) or any(not isinstance(x, str) for x in acceptance):
            raise TraceError("invalid acceptance_ids")
        if len(set(acceptance)) != len(acceptance):
            raise TraceError("duplicate acceptance_ids")
        if effect != "SPEC_ONLY":
            if not acceptance or not set(acceptance).issubset(canonical["acceptance_ids"]):
                raise TraceError("acceptance_ids not in approved Product task spec")
            if execution_mode == "OWNER_SUPERVISED":
                # This is a Task-to-PR mapping, NOT a provider call or WORK receipt.
                # Human review and existing CI remain the execution/merge gates.
                continue
            wid = c.get("execution_work_id")
            work_ref = c.get("work_envelope_path")
            if not isinstance(wid, str) or not isinstance(work_ref, str):
                raise TraceError("WORK envelope missing for implementation")
            work = safe_yaml(read_approved_source(root, work_ref, base_sha))
            if not work_ref.startswith(".c2pro/product-work/"):
                raise TraceError("WORK must be canonical product-work envelope")
            if work.get("schema") != "c2pro-product-work-envelope-v1":
                raise TraceError("invalid PRODUCT WORK schema")
            if work.get("work_id") != wid or wid != task:
                raise TraceError("WORK ID mismatch/invalid authorization")
            if work.get("parent_issue") != canonical["issue"] or work.get("task_id") != task:
                raise TraceError("WORK/Task parent mismatch")
            if not re.fullmatch(r"[0-9a-f]{40}", str(work.get("base_sha", ""))) or not isinstance(work.get("branch"), str):
                raise TraceError("WORK branch/base SHA missing")
            if work.get("acceptance_ids") != acceptance:
                raise TraceError("WORK acceptance mismatch")
            if work.get("status") != "assigned":
                raise TraceError("WORK must be assigned, not prepared")
            if not c.get("workspace_evidence_ref"):
                raise TraceError("WORK workspace evidence missing")
    if primary not in seen or sum(c["task_id"] == primary for c in claims) != 1:
        raise TraceError("primary_task not present exactly once")
    if "defects" in meta:
        defects = meta["defects"]
        if not isinstance(defects, list) or any(
            not isinstance(x, str) or not re.fullmatch(r"DEF-[A-Za-z0-9-]+", x)
            for x in defects
        ):
            raise TraceError("malformed defects")


def audit_pr(body: str, changed_paths: list[str], root: Path = ROOT,
             base_sha: str | None = None) -> dict[str, Any]:
    try:
        meta = parse_trace(body)
        if meta is None:
            return {"status": "MISSING_TRACE", "reason": "PR not yet migrated"}
        validate_claims(meta, load_registry(root, base_sha), root, base_sha)
        validate_effect(meta["effect_claim"], changed_paths)
        if meta.get("execution_mode") == "OWNER_SUPERVISED":
            if meta["primary_task"] == "C2PRO-DEV-14":
                for path in changed_paths:
                    if not (path.startswith(DEV14_CHANGED_PATHS) or path == ".github/ci-pip-install-baseline.json"):
                        raise TraceError(f"owner-supervised DEV-14 scope violation: {path}")
    except (TraceError, OSError, ValueError) as exc:
        return {"status": "REJECT", "reason": str(exc)}
    if meta["effect_claim"] == "SPEC_ONLY":
        return {"status": "PASS_SPEC", "reason": "Document trace; not execution authority"}
    if meta.get("execution_mode") == "OWNER_SUPERVISED":
        return {"status": "TASK_MAPPED_PENDING_HUMAN_REVIEW",
                "reason": "Task, parent and acceptance mapped; CI does not grant merge or Product acceptance"}
    return {"status": "TRACE_MATCHED_NOT_AUTHORIZED",
            "reason": "Task consistency only; CI never grants authority"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--mode", choices=["audit", "enforce"], default="audit")
    args = parser.parse_args(argv)
    event = json.loads(args.event.read_text())
    pr = event.get("pull_request", {})
    body = pr.get("body") or ""
    def exact_sha(s: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{40}", s):
            raise TraceError("invalid Git SHA")
        return s
    try:
        base = exact_sha(args.base or pr.get("base", {}).get("sha", ""))
        head = exact_sha(args.head or pr.get("head", {}).get("sha", ""))
        result = subprocess.run(
            ["git", "diff", "--name-only", "-z", base, head],
            cwd=ROOT, check=True, capture_output=True,
        )
        paths = [p.decode("utf-8") for p in result.stdout.split(b"\0") if p]
        verdict = audit_pr(body, paths, ROOT, base)
    except (TraceError, OSError, subprocess.CalledProcessError) as exc:
        verdict = {"status": "REJECT", "reason": f"diff unavailable: {type(exc).__name__}"}
    print("C2PRO_PR_TRACE=" + json.dumps(verdict, sort_keys=True))
    # Future enforcement needs a base-pinned executable and independent
    # workspace receipt proof, not merely user-supplied PR metadata.
    if args.mode == "enforce":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
