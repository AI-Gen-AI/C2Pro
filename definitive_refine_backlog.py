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
    if any(k in desc for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmark', 'env setup', 'python 3.11', 'postgresql', 'production-like']):
        return "🔴 P0"
    if "clerk" in desc and "production" in desc:
        return "🔴 P0"
    if "setup test infrastructure" in desc or "setup vitest" in desc:
        return "🔴 P0"
    if "final_summary_ts-e2e-sec-tnt-001" in path:
        return "🔴 P0"
    if any(k in desc for k in ['api endpoint', 'crud', 'dashboard', 'projects', 'p1', 'use case', 'service', 'extract clauses', 'connect all ui views']):
        return "🟠 P1"
    if any(k in desc for k in ['export', 'visualization', 'template', 'p2', 'ui component', 'wireframe', 'd3.js', 'dnd-kit']):
        return "🟡 P2"
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
        content = f.read()

    # 1. Aggressive cleaning of blanks and artifacts
    content = content.replace("\r\n", "\n")
    content = re.sub(r'\n[ \t]+\n', '\n\n', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Fix encoding mangles
    content = content.replace("producci%n", "producción")
    content = content.replace("producci%%n", "producción")
    content = content.replace("versi%n", "versión")
    content = content.replace("m%tricas", "métricas")
    content = content.replace("categor%a", "categoría")
    content = content.replace("espa%ol", "español")
    content = content.replace("espa%%ol", "español")
    content = content.replace("%%Cu%l", "¿Cuál")
    content = content.replace(",%%", "¿")

    lines = content.split('\n')
    output_lines = []
    current_section = "General"
    captured_tasks = []

    def flush_tasks():
        if captured_tasks:
            # Sort by Priority
            captured_tasks.sort(key=lambda x: x['prio'])
            output_lines.append("| Done | Priority | ID | Dependency | Description | Source File |")
            output_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for t in captured_tasks:
                output_lines.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |")
            output_lines.append("") # Blank line after table
            captured_tasks.clear()

    for line in lines:
        stripped = line.strip()
        
        # Detect Section Headers
        if stripped.startswith("## ") or stripped.startswith("### "):
            flush_tasks()
            current_section = stripped
            output_lines.append(line)
            continue

        # Detect Tasks
        if stripped.startswith("| TASK-"):
            # Use regex to find TASK-ID, file, and description even if columns are missing or weird
            # Format usually: | TASK-XXX | `file` | desc |
            match = re.search(r'TASK-(\d+).*?`(.*?)`.*?\|(.*)\|', stripped)
            if not match:
                # Fallback match if backticks are missing
                match = re.search(r'TASK-(\d+).*?\|(.*?)\|', stripped)
            
            if match:
                groups = match.groups()
                tid = f"TASK-{groups[0]}"
                if len(groups) == 3:
                    f_path = groups[1].strip()
                    desc = groups[2].strip()
                else:
                    f_path = "Unknown"
                    desc = groups[1].strip()
                
                # Clean description of trailing pipes
                desc = desc.rstrip('|').strip()
                
                prio = get_priority(desc, current_section, f_path)
                dep = get_dependency(desc)
                captured_tasks.append({
                    "tid": tid,
                    "file": f_path,
                    "desc": desc,
                    "prio": prio,
                    "dep": dep
                })
            continue

        # Skip old table headers and separators
        if stripped.startswith("| ID |") or stripped.startswith("| :--- |"):
            continue
        if stripped.startswith("| Done |") and "Priority" in stripped:
            continue

        # Regular line
        if not stripped and captured_tasks:
            flush_tasks()
        
        if not stripped.startswith("| TASK-"):
            output_lines.append(line)

    flush_tasks()

    # Join and final pass on blanks
    final_output = '\n'.join(output_lines)
    final_output = re.sub(r'\n{3,}', '\n\n', final_output)

    with open(input_path, 'w', encoding='utf-8') as f:
        f.write(final_output)
    
    return "Backlog definitive restructuring complete."

if __name__ == "__main__":
    print(process_backlog())
