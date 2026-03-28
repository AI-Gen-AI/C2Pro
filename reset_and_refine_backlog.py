import os
import re
import sys
import codecs

# Force UTF-8
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc):
    desc = desc.lower()
    if any(k in desc for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmark', 'env setup', 'python 3.11', 'postgresql', 'production-like']):
        return "🔴 P0"
    if "clerk" in desc and "production" in desc:
        return "🔴 P0"
    if "setup test infrastructure" in desc or "setup vitest" in desc:
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

def process():
    path = "C2PRO_MASTER_BACKLOG.md"
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Normalize newlines
    content = content.replace("\r\n", "\n")
    
    # Fix encoding artifacts
    content = re.sub(r'producci[%]+n', 'producción', content)
    content = re.sub(r'versi[%]+n', 'versión', content)
    content = re.sub(r'm[%]+tricas', 'métricas', content)
    content = re.sub(r'categor[%]+a', 'categoría', content)
    content = re.sub(r'espa[%]+ol', 'español', content)
    content = content.replace(",%%", "¿").replace("%%Cu%l", "¿Cuál")

    lines = content.split('\n')
    output = []
    current_tasks = []
    
    header_written = False

    def flush():
        nonlocal current_tasks
        if current_tasks:
            current_tasks.sort(key=lambda x: x['prio'])
            output.append("| Done | Priority | ID | Dependency | Description | Source File |")
            output.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for t in current_tasks:
                output.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |")
            output.append("")
            current_tasks = []

    for line in lines:
        s = line.strip()
        
        # Handle Headers
        if s.startswith("#"):
            flush()
            output.append(line)
            continue
            
        # Handle Task Lines (Clean them first)
        if "TASK-" in s and "|" in s:
            # Extract TASK-ID
            tid_match = re.search(r'TASK-(\d+)', s)
            if tid_match:
                tid = f"TASK-{tid_match.group(1)}"
                
                # Extract File (look for backticks)
                file_match = re.search(r'`(.*?)`', s)
                f_path = file_match.group(1) if file_match else "Unknown"
                
                # Extract Description (everything else that isn't ID, File, or priority icons)
                # We'll just take the longest part of the split
                parts = [p.strip() for p in s.split('|') if p.strip()]
                desc = ""
                for p in parts:
                    if "TASK-" not in p and "`" not in p and "🔴" not in p and "🟠" not in p and "🟡" not in p and "🟢" not in p and p != "[ ]" and p != "Done":
                        if len(p) > len(desc):
                            desc = p
                
                # If description is still empty, fallback
                if not desc: desc = "Task description not found"
                
                current_tasks.append({
                    "tid": tid, "file": f_path, "desc": desc,
                    "prio": get_priority(desc),
                    "dep": get_dependency(desc)
                })
            continue
            
        # Skip existing table headers or empty lines within a task block
        if in_table_struct := (s.startswith("| Done |") or s.startswith("| :--- |") or s.startswith("| ID |")):
            continue
            
        if not s and current_tasks:
            flush()
            continue
            
        if not s.startswith("|"):
            output.append(line)

    flush()

    # Final cleanup of blanks
    final = "\n".join(output)
    final = re.sub(r'\n{3,}', '\n\n', final)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final)
    
    return "Backlog reset and refined successfully."

if __name__ == "__main__":
    print(process())
