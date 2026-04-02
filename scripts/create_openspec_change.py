"""TS-OPS-OPENSPEC-CREATE-001

Deterministic scaffold creator for follow-up OpenSpec changes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


EXIT_OK = 0
EXIT_ERROR = 1


@dataclass(frozen=True)
class ChangeScaffoldInput:
    repo_root: Path
    change_name: str
    domain_name: str


@dataclass(frozen=True)
class ChangeScaffoldPaths:
    change_root: Path
    proposal: Path
    design: Path
    tasks: Path
    spec: Path


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "unnamed"


def normalize_change_name(value: str) -> str:
    stripped = value.strip()
    if "/" in stripped or "\\" in stripped:
        raise ValueError("change name must not include path separators")
    if "." in {part for part in stripped.split() if part} or stripped in {".", ".."}:
        raise ValueError("change name must not include traversal")
    slug = _slugify(stripped)
    if ".." in stripped:
        raise ValueError("change name must not include traversal")
    return slug


def normalize_domain_name(value: str) -> str:
    stripped = value.strip()
    if "/" in stripped or "\\" in stripped:
        raise ValueError("domain name must not include path separators")
    if stripped in {".", ".."} or ".." in stripped:
        raise ValueError("domain name must not include traversal")
    return _slugify(stripped)


def build_paths(scaffold_input: ChangeScaffoldInput) -> ChangeScaffoldPaths:
    change_root = (
        scaffold_input.repo_root
        / "openspec"
        / "changes"
        / scaffold_input.change_name
    )
    return ChangeScaffoldPaths(
        change_root=change_root,
        proposal=change_root / "proposal.md",
        design=change_root / "design.md",
        tasks=change_root / "tasks.md",
        spec=change_root / "specs" / scaffold_input.domain_name / "spec.md",
    )


def _proposal_template(change_name: str) -> str:
    title = change_name.replace("-", " ").title()
    return (
        f"# Proposal: {title}\n\n"
        "## Intent\n\n"
        "Describe the follow-up change intent.\n\n"
        "## Scope\n\n"
        "### In Scope\n\n"
        "- Define the concrete work for this change.\n\n"
        "### Out of Scope\n\n"
        "- Document adjacent work that stays outside this change.\n\n"
        "## Rollback Plan\n\n"
        "- Revert this change folder if the follow-up approach needs to be withdrawn.\n\n"
        "## Affected Areas\n\n"
        "| Area | Impact | Description |\n"
        "| ---- | ------ | ----------- |\n"
        "| `(fill-me)` | New/Modify | Describe the affected module or artifact |\n"
    )


def _design_template(change_name: str, domain_name: str) -> str:
    title = change_name.replace("-", " ").title()
    return (
        f"# Design: {title}\n\n"
        "## Technical Approach\n\n"
        "Describe the implementation approach for this follow-up change.\n\n"
        "## Architecture Decisions\n\n"
        "| Decision | Options | Tradeoffs | Chosen |\n"
        "| -------- | ------- | --------- | ------ |\n"
        "| `(fill-me)` | A / B | Document tradeoffs | `(fill-me)` |\n\n"
        "## File Changes\n\n"
        "| File | Action | Description |\n"
        "| ---- | ------ | ----------- |\n"
        f"| `openspec/changes/{change_name}/specs/{domain_name}/spec.md` | Create | Requirement deltas for this change |\n"
    )


def _tasks_template() -> str:
    return (
        "# Tasks\n\n"
        "## Phase 1: Infrastructure\n\n"
        "- [ ] 1.1 Define the minimum scaffolding or setup required.\n\n"
        "## Phase 2: Implementation\n\n"
        "- [ ] 2.1 Implement the core change.\n\n"
        "## Phase 3: Testing\n\n"
        "- [ ] 3.1 Verify the change against its scenarios.\n"
    )


def _spec_template(change_name: str, domain_name: str) -> str:
    title = change_name.replace("-", " ").title()
    domain_title = domain_name.replace("-", " ").title()
    return (
        f"# {domain_title} Specification\n\n"
        f"### Requirement: {title}\n"
        "The implementation MUST define the expected behavior for this follow-up change.\n\n"
        "#### Scenario: Follow-up change applies canonical scaffold\n"
        "- GIVEN a contributor creates a new OpenSpec follow-up change\n"
        "- WHEN the scaffold is generated\n"
        "- THEN the canonical proposal, design, tasks, and spec files SHALL exist in the expected paths\n"
    )


def create_change(scaffold_input: ChangeScaffoldInput) -> ChangeScaffoldPaths:
    paths = build_paths(scaffold_input)
    if paths.change_root.exists():
        raise FileExistsError(f"change '{scaffold_input.change_name}' already exists")

    paths.spec.parent.mkdir(parents=True, exist_ok=False)
    paths.proposal.write_text(
        _proposal_template(scaffold_input.change_name),
        encoding="utf-8",
    )
    paths.design.write_text(
        _design_template(scaffold_input.change_name, scaffold_input.domain_name),
        encoding="utf-8",
    )
    paths.tasks.write_text(_tasks_template(), encoding="utf-8")
    paths.spec.write_text(
        _spec_template(scaffold_input.change_name, scaffold_input.domain_name),
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a canonical OpenSpec follow-up change scaffold")
    parser.add_argument("--change", required=True, help="Human title or slug for the new change")
    parser.add_argument("--domain", default="openspec", help="Single spec domain folder name")
    parser.add_argument("--repo-root", help="Optional repository root override")
    args = parser.parse_args(argv)

    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
        scaffold_input = ChangeScaffoldInput(
            repo_root=repo_root,
            change_name=normalize_change_name(args.change),
            domain_name=normalize_domain_name(args.domain),
        )
        paths = create_change(scaffold_input)
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR

    print(f"Created OpenSpec change scaffold: {paths.change_root.relative_to(repo_root)}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
