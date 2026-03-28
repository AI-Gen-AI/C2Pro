import os
import re
import sys
import codecs

# Force UTF-8
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc):
    d = desc.lower()
    if any(k in d for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmark', 'env setup', 'python 3.11', 'postgresql', 'production-like']):
        return "🔴 P0"
    if "clerk" in d and "production" in d:
        return "🔴 P0"
    if "setup test infrastructure" in d or "setup vitest" in d:
        return "🔴 P0"
    if any(k in d for k in ['api endpoint', 'crud', 'dashboard', 'projects', 'p1', 'use case', 'service', 'extract clauses', 'connect all ui views']):
        return "🟠 P1"
    if any(k in d for k in ['export', 'visualization', 'template', 'p2', 'ui component', 'wireframe', 'd3.js', 'dnd-kit']):
        return "🟡 P2"
    return "🟢 P3"

def get_dependency(desc):
    d = desc.lower()
    if any(k in d for k in ['ui', 'frontend', 'view', 'page', 'matrix', 'viewer']):
        return "Backend API"
    if any(k in d for k in ['test', 'run', 'pytest', 'check']):
        return "Env Setup"
    if any(k in d for k in ['deploy', 'production', 'sign-off']):
        return "Security Sign-off"
    return "None"

def process():
    path = "C2PRO_MASTER_BACKLOG.md"
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lines = content.split('\n')
    output = []
    current_tasks = []

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
        if not s:
            if current_tasks: flush()
            output.append(line)
            continue
            
        if s.startswith("#"):
            flush()
            output.append(line)
            continue
            
        if "TASK-" in s and "|" in s:
            # Match ID
            tid_m = re.search(r'TASK-\d+', s)
            tid = tid_m.group(0) if tid_m else "TASK-000"
            
            # Match File (in backticks)
            file_m = re.search(r'`(.*?)`', s)
            f_path = file_m.group(1) if file_m else "Unknown"
            
            # Match Description: It's usually the part that doesn't have TASK-, backticks, or emojis
            parts = [p.strip() for p in s.split('|') if p.strip()]
            desc = ""
            # Logic: Description is the one that isn't ID, File, [ ], or Priority icon
            for p in parts:
                p_clean = p.replace('[ ]', '').strip()
                if not p_clean: continue
                if tid in p: continue
                if f_path in p: continue
                if any(icon in p for icon in ["🔴", "🟠", "🟡", "🟢"]): continue
                if p in ["Done", "Priority", "ID", "Dependency", "Description", "Source File", ":---"]: continue
                # If we found a candidate, and it's longer than what we have, take it
                if len(p) > len(desc):
                    desc = p
            
            if not desc: desc = "Task description not found"
            
            # Cleanup Spanish mangling in description
            desc = re.sub(r'producci[%]+n', 'producción', desc)
            desc = re.sub(r'versi[%]+n', 'versión', desc)
            desc = re.sub(r'espa[%]+ol', 'español', desc)
            
            current_tasks.append({
                "tid": tid, "file": f_path, "desc": desc,
                "prio": get_priority(desc),
                "dep": get_dependency(desc)
            })
            continue
            
        # Skip junk table lines
        if any(icon in s for icon in ["| Done", "| :---", "| ID |"]):
            continue
            
        output.append(line)

    flush()

    final = "\n".join(output)
    # Aggressive blank line cleanup
    final = re.sub(r'\n{3,}', '\n\n', final)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final)
    
    return "Master Backlog definitively fixed."

if __name__ == "__main__":
    print(process())
