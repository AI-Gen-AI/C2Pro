import os
import re
import sys
import codecs

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc, cat, file_path):
    desc = desc.lower()
    cat = cat.lower()
    path = file_path.lower()
    if any(k in desc for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmarks', 'env setup', 'python 3.11', 'postgresql']):
        return "🔴 P0"
    if "clerk" in desc and "production" in desc:
        return "🔴 P0"
    if "setup test infrastructure" in desc or "setup vitest" in desc:
        return "🔴 P0"
    if any(k in desc for k in ['api endpoints', 'crud', 'dashboard', 'projects', 'p1', 'use case', 'service']):
        return "🟠 P1"
    if "connect all ui views" in desc or "extract clauses" in desc:
        return "🟠 P1"
    if any(k in desc for k in ['export', 'visualization', 'templates', 'p2', 'ui component', 'wireframe', 'd3.js', 'dnd-kit']):
        return "🟡 P2"
    return "🟢 P3"

def get_dependency(desc, cat):
    desc = desc.lower()
    if "ui" in desc or "frontend" in desc or "view" in desc or "page" in desc:
        return "Backend API"
    if "test" in desc or "run" in desc or "pytest" in desc:
        return "Env Setup"
    if "deployment" in desc or "production" in desc or "sign-off" in desc:
        return "Security Sign-off"
    return "None"

def refine_backlog():
    file_path = "C2PRO_MASTER_BACKLOG.md"
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except:
        return "Backlog file not found."

    new_lines = []
    current_section = ""
    in_table = False
    table_tasks = []

    def flush_table():
        nonlocal in_table, table_tasks
        if table_tasks:
            new_lines.append("| Done | Priority | ID | Dependency | Description | Source File |\n")
            new_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            table_tasks.sort(key=lambda x: x['prio'])
            for t in table_tasks:
                new_lines.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |\n")
            table_tasks = []
        in_table = False

    for line in lines:
        if line.startswith("### 2.") or line.startswith("## 3."):
            flush_table()
            current_section = line.strip()
            new_lines.append(line)
            continue
        
        if line.startswith("## 4.") or line.startswith("## 1."):
            flush_table()
            current_section = line.strip()
            new_lines.append(line)
            continue

        if line.startswith("| ID | File | Description |"):
            in_table = True
            continue
        
        if in_table and line.startswith("| TASK-"):
            match = re.search(r'\| (TASK-\d+) \| `(.*?)` \| (.*?) \|', line)
            if match:
                tid, f_path, desc = match.groups()
                prio = get_priority(desc, current_section, f_path)
                dep = get_dependency(desc, current_section)
                table_tasks.append({"tid": tid, "file": f_path, "desc": desc, "prio": prio, "dep": dep})
            continue
        
        if in_table and not line.strip():
            flush_table()
            new_lines.append(line)
            continue
            
        if not in_table:
            new_lines.append(line)

    flush_table()

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return "Backlog refined successfully."

if __name__ == "__main__":
    print(refine_backlog())
