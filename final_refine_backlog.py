import os
import re
import sys
import codecs

# Force UTF-8 for output
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc, section, file_path):
    desc = desc.lower()
    section = section.lower()
    path = file_path.lower()
    
    # P0: Critical Infrastructure, Security, Auth, Env
    if any(k in desc for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmark', 'env setup', 'python 3.11', 'postgresql', 'production-like']):
        return "🔴 P0"
    if "clerk" in desc and "production" in desc:
        return "🔴 P0"
    if "setup test infrastructure" in desc or "setup vitest" in desc:
        return "🔴 P0"
    if "final_summary_ts-e2e-sec-tnt-001" in path: # This file is security E2E
        return "🔴 P0"
    
    # P1: Core Functionality, Main API
    if any(k in desc for k in ['api endpoint', 'crud', 'dashboard', 'projects', 'p1', 'use case', 'service', 'extract clauses', 'connect all ui views']):
        return "🟠 P1"
    
    # P2: UI Components, Enhancements
    if any(k in desc for k in ['export', 'visualization', 'template', 'p2', 'ui component', 'wireframe', 'd3.js', 'dnd-kit']):
        return "🟡 P2"
    
    # P3: All else
    return "🟢 P3"

def get_dependency(desc):
    desc = desc.lower()
    if any(k in desc for k in ['ui', 'frontend', 'view', 'page', 'matrix', 'viewer']):
        return "Backend API"
    if any(k in desc for k in ['test', 'run', 'pytest', 'check']):
        return "Env Setup"
    if any(k in desc for k in ['deploy', 'production', 'sign-off']):
        return "Security Sign-off"
    return "None"

def process_backlog():
    input_path = "C2PRO_MASTER_BACKLOG.md"
    if not os.path.exists(input_path):
        return "File not found."

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    output_lines = []
    current_section = ""
    in_task_table = False
    captured_tasks = []

    def flush_tasks():
        nonlocal captured_tasks, in_task_table
        if captured_tasks:
            # Sort by Priority
            captured_tasks.sort(key=lambda x: x['prio'])
            
            output_lines.append("| Done | Priority | ID | Dependency | Description | Source File |\n")
            output_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for t in captured_tasks:
                output_lines.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |\n")
            
            captured_tasks = []
        in_task_table = False

    for line in lines:
        stripped = line.strip()
        
        # Detect Sections
        if stripped.startswith("### 2.") or stripped.startswith("## 3."):
            flush_tasks()
            current_section = stripped
            output_lines.append(line)
            continue
            
        if stripped.startswith("## 1.") or stripped.startswith("## 4."):
            flush_tasks()
            output_lines.append(line)
            continue

        # Detect start of a task table
        if stripped.startswith("| ID | File | Description |"):
            in_task_table = True
            continue
            
        # Skip the separator line
        if in_task_table and stripped.startswith("| :--- |"):
            continue

        # Capture task rows
        if in_task_table and stripped.startswith("| TASK-"):
            # Format: | TASK-008 | `FRONTEND_TESTING_PLAN.md` | Description |
            match = re.search(r'\| (TASK-\d+) \| `(.*?)` \| (.*?) \|', stripped)
            if match:
                tid, f_path, desc = match.groups()
                prio = get_priority(desc, current_section, f_path)
                dep = get_dependency(desc)
                captured_tasks.append({
                    "tid": tid,
                    "file": f_path,
                    "desc": desc.strip(),
                    "prio": prio,
                    "dep": dep
                })
            continue

        # If we were in a table and see something else, flush
        if in_task_table and not stripped.startswith("|"):
            flush_tasks()
            output_lines.append(line)
            continue
            
        if not in_task_table:
            output_lines.append(line)

    flush_tasks()

    # Final write
    with open(input_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    
    return "Backlog prioritized and restructured successfully."

if __name__ == "__main__":
    print(process_backlog())
