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
    if any(k in d for k in ['ui', 'frontend', 'view', 'page', 'matrix', 'viewer', 'dashboard']):
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
            
        if "| TASK-" in s:
            # 1. Extract Task ID
            tid_m = re.search(r'TASK-\d+', s)
            tid = tid_m.group(0) if tid_m else "TASK-000"
            
            # 2. Extract File Path (anything between ` ` or containing \ or /)
            file_m = re.search(r'`(.*?)`', s)
            if file_m:
                f_path = file_m.group(1).strip()
            else:
                # Try to find a part that looks like a path
                parts = [p.strip() for p in s.split('|') if p.strip()]
                f_path = "Unknown"
                for p in parts:
                    if "\\" in p or "/" in p or ".md" in p:
                        f_path = p.replace('`','').strip()
                        break
            
            # 3. Extract Description: The hardest part
            # Description is the part that is NOT ID, NOT File, NOT [ ], NOT emoji, NOT dependency
            parts = [p.strip() for p in s.split('|') if p.strip()]
            desc = ""
            for p in parts:
                p_clean = p.replace('[ ]', '').strip()
                if not p_clean: continue
                if tid in p: continue
                if p.replace('`','') == f_path: continue
                if any(icon in p for icon in ["🔴", "🟠", "🟡", "🟢"]): continue
                if p in ["Done", "Priority", "ID", "Dependency", "Description", "Source File", ":---"]: continue
                # We also want to skip the placeholder dependencies if they matched previously
                if p in ["Backend API", "Env Setup", "Security Sign-off", "None"]: continue
                
                if len(p) > len(desc):
                    desc = p
            
            # If still empty, it might be that the description WAS "Backend API" or similar
            if not desc:
                # Take the last part that isn't the file path or ID
                for p in reversed(parts):
                    if tid not in p and p.replace('`','') != f_path and p not in [":---", "|"]:
                        desc = p
                        break

            if not desc: desc = "Task details in source"
            
            current_tasks.append({
                "tid": tid, "file": f_path, "desc": desc,
                "prio": get_priority(desc),
                "dep": get_dependency(desc)
            })
            continue
            
        if s.startswith("|") and any(h in s for h in ["ID", "Done", "Priority", ":---"]):
            continue
            
        output.append(line)

    flush()

    final = "\n".join(output)
    final = re.sub(r'\n{3,}', '\n\n', final)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final)
    
    return "Master Backlog fixed v4."

if __name__ == "__main__":
    print(process())
