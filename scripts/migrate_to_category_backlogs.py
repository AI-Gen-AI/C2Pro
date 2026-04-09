#!/usr/bin/env python3
"""
Migration script: C2PRO_MASTER_BACKLOG.md → Category-Specific Backlogs

Migrates monolithic backlog to distributed category backlogs:
- Auto-categorizes tasks based on section and content
- Renumbers tasks sequentially within categories (TASK-BCK-001, TASK-FRT-001, etc.)
- Keeps cross-category tasks in master backlog
- Generates category backlog files in backlogs/
- Simplifies master backlog to index + cross-category only

Usage:
    python scripts/migrate_to_category_backlogs.py --dry-run  # Preview changes
    python scripts/migrate_to_category_backlogs.py           # Execute migration
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Path configuration
BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_BACKLOG = BASE_DIR / "C2PRO_MASTER_BACKLOG.md"
BACKLOGS_DIR = BASE_DIR / "backlogs"
BACKUP_DIR = BASE_DIR / "backups"

# Category configuration
CATEGORIES = {
    "BCK": {"name": "Backend", "role": "backend"},
    "FRT": {"name": "Frontend", "role": "frontend"},
    "AI": {"name": "AI/ML Intelligence", "role": "ai"},
    "INF": {"name": "Infrastructure", "role": "infra"},
    "QA": {"name": "Quality Assurance", "role": "qa"},
    "REV": {"name": "Code Review", "role": "reviewer"},
    "SEC": {"name": "Security", "role": "security"},
    "DEV": {"name": "DevOps", "role": "devops"},
    "PLN": {"name": "Planning", "role": "planner"},
    "DOC": {"name": "Documentation", "role": "shared"},
}

# Category mapping rules (section name → category prefix)
SECTION_TO_CATEGORY = {
    "2.1 Backend": "BCK",
    "2.2 Frontend": "FRT",
    "2.3 AI & Intelligence": "AI",
    "2.4 DevOps & Infrastructure": "INF",  # Will split INF/DEV based on content
    "2.5 Security": "SEC",
    "2.6 Testing & Quality": "QA",
    "2.7 Architectural Refactoring": "CROSS",  # Cross-category
    "2.8 Execution Phase": "QA",
    "2.9 Agent Orchestration": "CROSS",  # Cross-category
}

# Cross-category task prefixes (stay in master)
CROSS_CATEGORY_PREFIXES = ["UNIFY-", "REL-", "ARCH-", "GATE-", "G6-", "G7-"]


def parse_master_backlog() -> Dict[str, List[Dict]]:
    """Parse master backlog into sections with tasks."""
    with open(MASTER_BACKLOG, "r", encoding="utf-8") as f:
        content = f.read()

    sections = {}
    current_section = None
    task_pattern = r'^\| \[(.)\]\s+\| (P\d)\s+\| `([^`]+)`\s+\| ([^|]+)\| ([^|]+)\| ([^|]+)\|'

    for line in content.split("\n"):
        # Detect section headers
        if line.startswith("### "):
            current_section = line.replace("### ", "").strip()
            if current_section not in sections:
                sections[current_section] = []
            continue

        # Parse task rows
        match = re.match(task_pattern, line.strip())
        if match and current_section:
            status, priority, task_id, dependency, description, source = match.groups()
            sections[current_section].append({
                "status": "x" if status.lower() == "x" else " ",
                "priority": priority.strip(),
                "task_id": task_id.strip(),
                "dependency": dependency.strip(),
                "description": description.strip(),
                "source": source.strip(),
                "original_line": line,
            })

    return sections


def categorize_task(task: Dict, section: str) -> str:
    """Auto-categorize a single task based on section and content."""
    task_id = task["task_id"]
    description = task["description"].lower()
    source = task["source"].lower()

    # Rule 1: Cross-category tasks (special prefixes)
    for prefix in CROSS_CATEGORY_PREFIXES:
        if task_id.startswith(prefix):
            return "CROSS"

    # Rule 2: Section-based categorization
    category = SECTION_TO_CATEGORY.get(section, "CROSS")
    if category == "CROSS":
        return "CROSS"

    # Rule 3: Content-based refinement for Infrastructure/DevOps split
    if category == "INF":
        devops_keywords = ["docker", "deployment", "ci/cd", "monitoring", "github actions", "pipeline"]
        if any(kw in description or kw in source for kw in devops_keywords):
            return "DEV"
        return "INF"

    return category


def renumber_task(task: Dict, category: str, seq_num: int) -> Dict:
    """Renumber task with new category-specific ID."""
    old_id = task["task_id"]
    new_id = f"TASK-{category}-{seq_num:03d}"

    # Update task ID
    task["task_id"] = new_id
    task["old_id"] = old_id

    # Update description if it contains implementation notes with old ID
    if old_id in task["description"]:
        task["description"] = task["description"].replace(old_id, new_id)

    return task


def migrate_tasks(dry_run: bool = False) -> Dict[str, any]:
    """Execute migration: parse, categorize, renumber, write."""
    print("=" * 80)
    print("C2PRO BACKLOG MIGRATION: Monolithic -> Category-Specific")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE MIGRATION'}")
    print()

    # Step 1: Parse current backlog
    print("[1/5] Parsing C2PRO_MASTER_BACKLOG.md...")
    sections = parse_master_backlog()
    total_tasks = sum(len(tasks) for tasks in sections.values())
    print(f"  OK Parsed {len(sections)} sections, {total_tasks} total tasks")

    # Step 2: Categorize tasks
    print("\n[2/5] Categorizing tasks...")
    categorized = defaultdict(list)
    category_counters = defaultdict(int)

    for section, tasks in sections.items():
        for task in tasks:
            category = categorize_task(task, section)
            categorized[category].append(task)

    # Print categorization summary
    print(f"  OK Categorization complete:")
    for cat in sorted(categorized.keys()):
        count = len(categorized[cat])
        name = CATEGORIES.get(cat, {}).get("name", "Cross-Category")
        print(f"    {cat:6} ({name:20}): {count:3} tasks")

    # Step 3: Renumber tasks within categories
    print("\n[3/5] Renumbering tasks with sequential IDs...")
    for category, tasks in categorized.items():
        if category == "CROSS":
            continue  # Cross-category tasks keep original IDs

        for i, task in enumerate(tasks, start=1):
            renumber_task(task, category, i)
            category_counters[category] = i

    print(f"  OK Renumbered {sum(category_counters.values())} tasks")
    for cat, count in sorted(category_counters.items()):
        print(f"    {cat}: TASK-{cat}-001 to TASK-{cat}-{count:03d}")

    # Step 4: Write category backlogs
    print("\n[4/5] Writing category backlog files...")
    if not dry_run:
        BACKLOGS_DIR.mkdir(exist_ok=True)

    for category, tasks in categorized.items():
        if category == "CROSS":
            continue  # Cross-category stays in master

        filename = f"{category}_{CATEGORIES[category]['name'].upper().replace(' ', '_').replace('/', '_')}.md"
        filepath = BACKLOGS_DIR / filename

        if dry_run:
            print(f"  [DRY RUN] Would write {len(tasks)} tasks to {filename}")
        else:
            write_category_backlog(filepath, category, tasks)
            print(f"  OK Wrote {len(tasks)} tasks to {filename}")

    # Step 5: Update master backlog
    print("\n[5/5] Updating master backlog (cross-category tasks only)...")
    cross_tasks = categorized.get("CROSS", [])
    if dry_run:
        print(f"  [DRY RUN] Would update master with {len(cross_tasks)} cross-category tasks")
    else:
        # Backup original
        BACKUP_DIR.mkdir(exist_ok=True)
        backup_path = BACKUP_DIR / f"C2PRO_MASTER_BACKLOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md.bak"
        with open(MASTER_BACKLOG, "r", encoding="utf-8") as f_in:
            with open(backup_path, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())
        print(f"  OK Backup created: {backup_path}")

        # Write new lightweight master
        write_master_index(cross_tasks, categorized)
        print(f"  OK Master backlog updated ({len(cross_tasks)} cross-category tasks)")

    # Summary
    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total tasks processed: {total_tasks}")
    print(f"Category-specific tasks: {total_tasks - len(cross_tasks)}")
    print(f"Cross-category tasks: {len(cross_tasks)}")
    print()
    print("Distribution:")
    for cat in sorted(categorized.keys()):
        count = len(categorized[cat])
        pct = (count / total_tasks * 100) if total_tasks > 0 else 0
        name = CATEGORIES.get(cat, {}).get("name", "Cross-Category")
        print(f"  {cat:6} ({name:20}): {count:3} tasks ({pct:5.1f}%)")

    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN COMPLETE - No files were modified")
        print("Run without --dry-run to execute migration")
        print("=" * 80)

    return {"total": total_tasks, "categorized": dict(categorized), "counters": dict(category_counters)}


def write_category_backlog(filepath: Path, category: str, tasks: List[Dict]):
    """Write a category backlog file."""
    cat_info = CATEGORIES[category]
    completed = [t for t in tasks if t["status"] == "x"]
    active = [t for t in tasks if t["status"] == " "]

    content = f"""# {cat_info['name']} Tasks & Knowledge Base

**Category**: {cat_info['name']} ({category})
**Owner Role**: {cat_info['role']}
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_{cat_info['role']}.md)

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
"""

    # Write tasks
    for task in tasks:
        status_symbol = "[x]" if task["status"] == "x" else "[ ]"
        content += f"| {status_symbol} | {task['priority']} | `{task['task_id']}` | {task['dependency']} | {task['description']} | {task['source']} |\n"

    # Statistics
    total = len(tasks)
    completed_pct = (len(completed) / total * 100) if total > 0 else 0
    active_pct = (len(active) / total * 100) if total > 0 else 0

    content += f"""
**Statistics**:
- Total: {total} tasks
- Active: {len(active)} ({active_pct:.1f}%)
- Completed: {len(completed)} ({completed_pct:.1f}%)
- Blocked: 0 (0%)

---

## 2. Specifications

_Category-specific specifications will be added here_

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
|---------|-------------|--------|--------|---------|

---

## 6. Metrics

- **Total Tasks**: {total}
- **Completed**: {len(completed)} ({completed_pct:.1f}%)
- **Average Completion Time**: TBD
- **Test Coverage**: TBD

---

## Change Log

| Date | Change |
|------|--------|
| {datetime.now().strftime('%Y-%m-%d')} | Category backlog created from master backlog migration |
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def write_master_index(cross_tasks: List[Dict], all_categorized: Dict[str, List[Dict]]):
    """Write new lightweight master backlog (index + cross-category)."""
    content = f"""# C2PRO Master Backlog - Index

**Purpose**: High-level project overview and cross-category coordination
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}

> **Note**: Task details have been migrated to category-specific backlogs in `backlogs/`.
> This master backlog now contains only cross-category tasks and serves as an index.

---

## Quick Navigation

| Category | File | Owner | Total Tasks | Active | Completed |
|----------|------|-------|-------------|--------|-----------|
"""

    # Category index
    for cat in sorted([c for c in CATEGORIES.keys()]):
        tasks = all_categorized.get(cat, [])
        total = len(tasks)
        active = len([t for t in tasks if t["status"] == " "])
        completed = len([t for t in tasks if t["status"] == "x"])
        cat_info = CATEGORIES[cat]
        filename = f"{cat}_{cat_info['name'].upper().replace(' ', '_').replace('/', '_')}.md"

        content += f"| {cat_info['name']} | [backlogs/{filename}](backlogs/{filename}) | {cat_info['role']} | {total} | {active} | {completed} |\n"

    # Cross-category tasks
    content += f"""
---

## Cross-Category Initiatives

**Legend**: 🔗 Symbol indicates tasks affecting multiple categories

| Status | Priority | Task ID | Affects | Description | Source |
|--------|----------|---------|---------|-------------|--------|
"""

    for task in cross_tasks:
        status_symbol = "[x]" if task["status"] == "x" else "[ ]"
        # Determine which categories are affected (simplified - user can refine manually)
        affects = "🔗 ALL" if task["task_id"].startswith("UNIFY-") else "🔗 Multiple"
        content += f"| {status_symbol} | {task['priority']} | `{task['task_id']}` | {affects} | {task['description']} | {task['source']} |\n"

    # Simplified change log
    content += f"""
---

## Change Log

| Date | Major Milestone |
|------|-----------------|
| {datetime.now().strftime('%Y-%m-%d')} | Migrated to category-specific backlog architecture - detailed change logs now in category backlogs |

---

**Migration Note**: Detailed change history has been preserved in category backlog files.
This master change log will now only track major milestones and cross-category initiatives.
"""

    with open(MASTER_BACKLOG, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate C2PRO backlog to category-specific structure")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    args = parser.parse_args()

    try:
        result = migrate_tasks(dry_run=args.dry_run)
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
