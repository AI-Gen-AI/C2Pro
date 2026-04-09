"""Automated sync script between C2PRO_MASTER_BACKLOG.md and blackboard.json.

Syncs tasks from the permanent backlog to the ephemeral session state,
and marks completed tasks in the backlog when session tasks complete.

Usage:
    python -m core.sync_backlog_to_blackboard pull      # Pull pending tasks from backlog to blackboard
    python -m core.sync_backlog_to_blackboard push      # Push completed tasks from blackboard to backlog
    python -m core.sync_backlog_to_blackboard sync      # Full bidirectional sync (pull + push)
    python -m core.sync_backlog_to_blackboard status    # Show sync status

UNIFY-007: Automated sync script for task tracking
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
BLACKBOARD_PATH = BASE_DIR / "blackboard.json"
MASTER_BACKLOG_PATH = BASE_DIR / "C2PRO_MASTER_BACKLOG.md"
BACKLOGS_DIR = BASE_DIR / "backlogs"

# Regex patterns
BACKLOG_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9-]+$")
TASK_ROW_PATTERN = re.compile(
    r'\|\s*\[\s*([x\s])\s*\]\s*\|\s*([^|]+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]*)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|'
)


def cargar_json(ruta: Path) -> dict:
    """Load JSON file, return empty dict if not exists."""
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta: Path, data: dict) -> None:
    """Save dict to JSON file with pretty formatting."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cargar_blackboard() -> dict:
    """Load blackboard.json with defaults."""
    default = {
        "session_id": None,
        "objetivo_global": None,
        "estado_actual": "idle",
        "created_at": None,
        "updated_at": None,
        "role_assignment": {
            "planner": None,
            "backend": None,
            "frontend": None,
            "ai": None,
            "infra": None,
            "qa": None,
            "reviewer": None,
            "security": None,
            "devops": None,
        },
        "tareas": [],
        "contexto_paso_anterior": "",
        "trazas_de_error": [],
        "reintentos": 0,
        "max_reintentos": 3,
        "backlog_sync": {
            "last_sync": None,
            "backlog_file": "C2PRO_MASTER_BACKLOG.md",
            "task_ids_en_sesion": [],
        },
    }
    if not BLACKBOARD_PATH.exists():
        return default

    data = cargar_json(BLACKBOARD_PATH)
    # Merge with defaults
    for key, val in default.items():
        if key not in data:
            data[key] = val
    if "backlog_sync" not in data:
        data["backlog_sync"] = default["backlog_sync"]

    return data


def guardar_blackboard(data: dict) -> None:
    """Save blackboard.json with updated timestamp."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    guardar_json(BLACKBOARD_PATH, data)


def extraer_tareas_de_backlog(backlog_path: Path) -> List[Dict]:
    """Extract pending tasks from a backlog markdown file.

    Returns list of task dicts with fields: backlog_id, priority, status,
    depends_on, description, source.
    """
    if not backlog_path.exists():
        return []

    content = backlog_path.read_text(encoding="utf-8")
    tasks = []

    for line in content.splitlines():
        match = TASK_ROW_PATTERN.match(line)
        if not match:
            continue

        status_mark, priority, task_id, depends_on, description, source = match.groups()
        status = "completado" if status_mark.strip().lower() == "x" else "pendiente"

        # Only include pending tasks
        if status == "pendiente":
            tasks.append({
                "backlog_id": task_id.strip(),
                "priority": priority.strip(),
                "depends_on": depends_on.strip() if depends_on.strip() else None,
                "description": description.strip(),
                "source": source.strip(),
                "status": status,
            })

    return tasks


def extraer_todas_las_tareas_pendientes() -> List[Dict]:
    """Extract all pending tasks from master backlog and category backlogs."""
    all_tasks = []

    # Extract from master backlog
    all_tasks.extend(extraer_tareas_de_backlog(MASTER_BACKLOG_PATH))

    # Extract from category backlogs
    if BACKLOGS_DIR.exists():
        for backlog_file in BACKLOGS_DIR.glob("*.md"):
            all_tasks.extend(extraer_tareas_de_backlog(backlog_file))

    return all_tasks


def inferir_tipo_y_rol(task_id: str, description: str) -> Tuple[str, str]:
    """Infer task type and assigned role from task ID and description.

    Returns (tipo, asignado_a) tuple.
    """
    # Map category prefixes to types and roles
    category_map = {
        "BCK": ("backend", "backend"),
        "FRT": ("frontend", "frontend"),
        "AI": ("ai", "ai"),
        "INF": ("infra", "infra"),
        "QA": ("qa", "qa"),
        "DEV": ("devops", "devops"),
        "SEC": ("security", "security"),
        "REV": ("revision", "reviewer"),
        "PLN": ("planificacion", "planner"),
        "DDD": ("backend", "backend"),  # DDD tasks typically backend
        "UNIFY": ("infra", "infra"),  # Unification tasks are infrastructure
    }

    # Extract category from task ID (e.g., TASK-BCK-001 → BCK)
    parts = task_id.split("-")
    if len(parts) >= 2:
        category = parts[1]
        if category in category_map:
            return category_map[category]

    # Fallback: infer from description keywords
    desc_lower = description.lower()

    if any(kw in desc_lower for kw in ["api", "endpoint", "database", "backend", "modelo", "repositorio"]):
        return ("backend", "backend")
    elif any(kw in desc_lower for kw in ["ui", "frontend", "component", "page", "interfaz"]):
        return ("frontend", "frontend")
    elif any(kw in desc_lower for kw in ["ai", "ml", "llm", "prompt", "embedding", "coherence"]):
        return ("ai", "ai")
    elif any(kw in desc_lower for kw in ["test", "qa", "coverage", "testing"]):
        return ("qa", "qa")
    elif any(kw in desc_lower for kw in ["deploy", "ci", "cd", "docker", "pipeline"]):
        return ("devops", "devops")
    elif any(kw in desc_lower for kw in ["security", "auth", "permission", "seguridad"]):
        return ("security", "security")
    elif any(kw in desc_lower for kw in ["review", "revision", "audit"]):
        return ("revision", "reviewer")
    elif any(kw in desc_lower for kw in ["plan", "architecture", "design", "arquitectura"]):
        return ("planificacion", "planner")
    else:
        # Default to infrastructure for unknown tasks
        return ("infra", "infra")


def pull_tasks_from_backlog(limit: Optional[int] = None) -> int:
    """Pull pending tasks from backlog to blackboard.

    Args:
        limit: Maximum number of tasks to pull (None = all pending tasks)

    Returns:
        Number of tasks pulled
    """
    blackboard = cargar_blackboard()

    # Get all pending tasks from backlogs
    pending_tasks = extraer_todas_las_tareas_pendientes()

    # Filter out tasks already in session
    existing_backlog_ids = {t.get("backlog_id") for t in blackboard["tareas"] if t.get("backlog_id")}
    new_tasks = [t for t in pending_tasks if t["backlog_id"] not in existing_backlog_ids]

    # Apply limit if specified
    if limit is not None:
        new_tasks = new_tasks[:limit]

    # Convert backlog tasks to blackboard task format
    task_count = len(blackboard["tareas"])
    for backlog_task in new_tasks:
        task_count += 1
        tipo, asignado_a = inferir_tipo_y_rol(backlog_task["backlog_id"], backlog_task["description"])

        blackboard_task = {
            "tarea_id": f"T{task_count:03d}",
            "backlog_id": backlog_task["backlog_id"],
            "tipo": tipo,
            "descripcion": backlog_task["description"],
            "asignado_a": asignado_a,
            "estado": "pendiente",
            "criterio_done": f"Complete task {backlog_task['backlog_id']}",
            "archivos_afectados": [],
            "priority": backlog_task["priority"],
            "depends_on": backlog_task["depends_on"],
            "source": backlog_task["source"],
            "timestamps": {
                "creado": datetime.now(timezone.utc).isoformat()
            }
        }

        blackboard["tareas"].append(blackboard_task)
        blackboard["backlog_sync"]["task_ids_en_sesion"].append(backlog_task["backlog_id"])

    # Update sync metadata
    if new_tasks:
        blackboard["backlog_sync"]["last_sync"] = datetime.now(timezone.utc).isoformat()
        guardar_blackboard(blackboard)

    return len(new_tasks)


def push_completed_tasks_to_backlog() -> int:
    """Push completed tasks from blackboard to backlog.

    Marks tasks as [x] in backlog files when they're completed in blackboard.

    Returns:
        Number of tasks marked complete in backlog
    """
    blackboard = cargar_blackboard()

    # Find completed tasks that haven't been synced yet
    completed_tasks = [
        t for t in blackboard["tareas"]
        if t.get("estado") == "completado" and t.get("backlog_id")
    ]

    if not completed_tasks:
        return 0

    updated_count = 0

    # Update master backlog
    updated_count += _mark_tasks_complete_in_file(MASTER_BACKLOG_PATH, completed_tasks)

    # Update category backlogs
    if BACKLOGS_DIR.exists():
        for backlog_file in BACKLOGS_DIR.glob("*.md"):
            updated_count += _mark_tasks_complete_in_file(backlog_file, completed_tasks)

    if updated_count > 0:
        blackboard["backlog_sync"]["last_sync"] = datetime.now(timezone.utc).isoformat()
        guardar_blackboard(blackboard)

    return updated_count


def _mark_tasks_complete_in_file(backlog_path: Path, completed_tasks: List[Dict]) -> int:
    """Mark completed tasks as [x] in a specific backlog file with timestamp.

    Adds completion timestamp in format: @YYYY-MM-DD to the Source column.
    If Source already has implementation note, timestamp is added before opening parenthesis.
    Otherwise, creates new note in Source: `[x] Implemented @YYYY-MM-DD`

    Returns:
        Number of tasks updated in this file
    """
    if not backlog_path.exists():
        return 0

    content = backlog_path.read_text(encoding="utf-8")
    original_content = content
    updated_count = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for task in completed_tasks:
        backlog_id = task["backlog_id"]

        # Get completion timestamp from task if available
        completion_time = None
        if "timestamps" in task and "completado" in task["timestamps"]:
            completion_time = task["timestamps"]["completado"]
            # Extract date from ISO timestamp
            if "T" in completion_time:
                completion_time = completion_time.split("T")[0]

        # Use task completion date or today's date
        completion_date = completion_time or today

        # Pattern to match full task row with all 6 columns
        # | [ ] | Priority | `TASK-ID` | Depends | Description | Source |
        full_row_pattern = rf'\|\s*\[\s*\]\s*\|([^|]*)\|\s*(`{re.escape(backlog_id)}`)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|'

        def add_completion_note(match):
            """Add or update completion note with timestamp in Source column."""
            priority = match.group(1).strip()
            task_id_col = match.group(2).strip()
            depends = match.group(3).strip()
            description = match.group(4).strip()
            source = match.group(5).strip()

            # Check if timestamp already present in source
            if f"@{completion_date}" in source or re.search(r'@\d{4}-\d{2}-\d{2}', source):
                # Already has timestamp, just mark checkbox
                return f"| [x] | {priority} | {task_id_col} | {depends} | {description} | {source} |"

            # Add timestamp to source column (where implementation notes are)
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

            # Return row with checkbox marked and timestamp added
            return f"| [x] | {priority} | {task_id_col} | {depends} | {description} | {new_source} |"

        new_content = re.sub(full_row_pattern, add_completion_note, content)

        if new_content != content:
            content = new_content
            updated_count += 1

    # Only write if changes were made
    if content != original_content:
        backlog_path.write_text(content, encoding="utf-8")

    return updated_count


def show_sync_status() -> None:
    """Display current sync status between blackboard and backlog."""
    blackboard = cargar_blackboard()

    print("\n" + "="*70)
    print("SYNC STATUS: Backlog <-> Blackboard")
    print("="*70)

    print(f"\nSession ID: {blackboard.get('session_id', 'N/A')}")
    print(f"Session State: {blackboard.get('estado_actual', 'N/A')}")
    print(f"Last Sync: {blackboard['backlog_sync'].get('last_sync', 'Never')}")

    # Count tasks by status
    total_tasks = len(blackboard["tareas"])
    pending = sum(1 for t in blackboard["tareas"] if t.get("estado") == "pendiente")
    in_progress = sum(1 for t in blackboard["tareas"] if t.get("estado") == "en_progreso")
    completed = sum(1 for t in blackboard["tareas"] if t.get("estado") == "completado")
    failed = sum(1 for t in blackboard["tareas"] if t.get("estado") == "fallido")

    print(f"\nBlackboard Tasks:")
    print(f"  Total: {total_tasks}")
    print(f"  Pending: {pending}")
    print(f"  In Progress: {in_progress}")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")

    # Count pending tasks in backlog
    backlog_pending = extraer_todas_las_tareas_pendientes()
    print(f"\nBacklog Pending Tasks: {len(backlog_pending)}")

    # Count tasks in session from backlog
    in_session = len(blackboard["backlog_sync"].get("task_ids_en_sesion", []))
    print(f"Backlog Tasks in Session: {in_session}")

    # Show tasks by role
    print(f"\nTasks by Role:")
    roles = {}
    for task in blackboard["tareas"]:
        role = task.get("asignado_a", "unknown")
        roles[role] = roles.get(role, 0) + 1

    for role, count in sorted(roles.items()):
        print(f"  {role}: {count}")

    print("\n" + "="*70 + "\n")


def main():
    """Main entry point for sync script."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    try:
        if command == "pull":
            # Pull pending tasks from backlog
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
            count = pull_tasks_from_backlog(limit=limit)
            print(f"[OK] Pulled {count} pending task(s) from backlog to blackboard")

        elif command == "push":
            # Push completed tasks to backlog
            count = push_completed_tasks_to_backlog()
            print(f"[OK] Marked {count} task(s) as complete in backlog")

        elif command == "sync":
            # Full bidirectional sync
            print("Running full bidirectional sync...")
            pulled = pull_tasks_from_backlog()
            pushed = push_completed_tasks_to_backlog()
            print(f"[OK] Sync complete:")
            print(f"   - Pulled {pulled} pending task(s) from backlog")
            print(f"   - Marked {pushed} completed task(s) in backlog")

        elif command == "status":
            # Show sync status
            show_sync_status()

        else:
            print(f"[ERROR] Unknown command: {command}")
            print(__doc__)
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
