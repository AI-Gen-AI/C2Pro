"""Migration utility to add completion timestamps to existing completed tasks.

Adds @YYYY-MM-DD timestamps to tasks marked [x] that don't have timestamps.
For tasks with existing completion dates in their descriptions (like "on 2026-04-02"),
extracts and formats them as @2026-04-02.

Usage:
    python scripts/add_completion_timestamps.py                # Dry run (preview changes)
    python scripts/add_completion_timestamps.py --apply        # Apply changes
    python scripts/add_completion_timestamps.py --file path    # Process specific file

UNIFY-008: Add completion timestamps to backlog task format
"""
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_BACKLOG_PATH = BASE_DIR / "C2PRO_MASTER_BACKLOG.md"
BACKLOGS_DIR = BASE_DIR / "backlogs"

# Regex patterns
# Match full task row: | [x] | Priority | `TASK-ID` | Depends | Description | Source |
# Captures: status_col, priority_col, task_id_col, depends_col, description_col, source_col
COMPLETED_ROW_PATTERN = re.compile(
    r'\|\s*(\[x\])\s*\|([^|]*)\|\s*(`[^`]+`)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|',
    re.IGNORECASE
)

# Pattern to extract existing dates from descriptions
DATE_PATTERNS = [
    re.compile(r'on (\d{4}-\d{2}-\d{2})'),  # "on 2026-04-02"
    re.compile(r'@(\d{4}-\d{2}-\d{2})'),     # "@2026-04-02"
    re.compile(r'(\d{4}-\d{2}-\d{2})'),      # "2026-04-02" anywhere
]


def extract_date_from_description(description: str) -> str:
    """Extract completion date from description, or return default."""
    # Try each pattern in order of specificity
    for pattern in DATE_PATTERNS:
        match = pattern.search(description)
        if match:
            extracted_date = match.group(1)
            # Validate it's a real date format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', extracted_date):
                return extracted_date

    # Default to today if no date found
    return datetime.now().strftime("%Y-%m-%d")


def add_timestamps_to_file(filepath: Path, dry_run: bool = True) -> Tuple[int, List[str]]:
    """Add timestamps to completed tasks in a backlog file.

    Args:
        filepath: Path to backlog markdown file
        dry_run: If True, preview changes without writing

    Returns:
        Tuple of (updated_count, changes_preview)
    """
    if not filepath.exists():
        return 0, []

    content = filepath.read_text(encoding="utf-8")
    original_content = content
    updated_count = 0
    changes = []

    def add_timestamp(match):
        """Add timestamp to completed task if not present."""
        nonlocal updated_count, changes

        status = match.group(1)  # [x]
        priority = match.group(2).strip()  # P0, P1, etc.
        task_id_col = match.group(3).strip()  # `TASK-ID`
        depends = match.group(4).strip()  # Depends On
        description = match.group(5).strip()  # Description
        source = match.group(6).strip()  # Source

        # Extract task ID from backticks
        task_id = task_id_col.strip('`')

        # Check if timestamp already present in source column
        if "@" in source and re.search(r'@\d{4}-\d{2}-\d{2}', source):
            # Already has timestamp, skip
            return match.group(0)

        # Extract date from source column (where completion notes are)
        completion_date = extract_date_from_description(source)

        # Add timestamp to source column where implementation notes are
        new_source = source
        if "[x] Implemented" in source or "[x] Verified" in source:
            # Add timestamp before opening parenthesis if present
            if "(" in source:
                new_source = source.replace("(", f"@{completion_date} (", 1)
            else:
                new_source = f"{source} @{completion_date}"
        elif source:
            # Source has content but no completion note - add timestamp
            new_source = f"{source} `[x] @{completion_date}`"
        else:
            # Empty source - add completion note
            new_source = f"`[x] Implemented @{completion_date}`"

        updated_count += 1
        changes.append(f"  {task_id}: Added @{completion_date}")

        # Reconstruct the row with proper spacing
        return f"| {status} | {priority} | {task_id_col} | {depends} | {description} | {new_source} |"

    # Apply transformation
    new_content = COMPLETED_ROW_PATTERN.sub(add_timestamp, content)

    # Write changes if not dry run
    if not dry_run and new_content != original_content:
        filepath.write_text(new_content, encoding="utf-8")

    return updated_count, changes


def process_all_backlogs(dry_run: bool = True, specific_file: Path = None) -> None:
    """Process all backlog files or a specific file.

    Args:
        dry_run: If True, preview changes without writing
        specific_file: If provided, only process this file
    """
    if specific_file:
        files = [specific_file]
    else:
        # Process master backlog + all category backlogs
        files = [MASTER_BACKLOG_PATH]
        if BACKLOGS_DIR.exists():
            files.extend(sorted(BACKLOGS_DIR.glob("*.md")))

    total_updated = 0

    print("\n" + "="*70)
    if dry_run:
        print("DRY RUN: Preview of timestamp additions")
    else:
        print("APPLYING: Adding timestamps to completed tasks")
    print("="*70 + "\n")

    for filepath in files:
        if not filepath.exists():
            continue

        count, changes = add_timestamps_to_file(filepath, dry_run=dry_run)

        if count > 0:
            print(f"\n{filepath.name}:")
            print(f"  Updated: {count} task(s)")
            for change in changes[:10]:  # Show first 10 changes
                print(change)
            if len(changes) > 10:
                print(f"  ... and {len(changes) - 10} more")

            total_updated += count

    print("\n" + "="*70)
    print(f"Total: {total_updated} task(s) updated")
    if dry_run:
        print("\nRun with --apply to write changes")
    else:
        print("\nChanges written to backlog files")
    print("="*70 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Add completion timestamps to backlog tasks (UNIFY-008)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Process specific file only"
    )

    args = parser.parse_args()

    try:
        process_all_backlogs(
            dry_run=not args.apply,
            specific_file=args.file
        )
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
