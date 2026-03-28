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
    if any(d_key in d for d_key in ['deploy', 'production', 'sign-off']):
        return "Security Sign-off"
    return "None"

def process():
    path = "C2PRO_MASTER_BACKLOG.md"
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lines = content.split('\n')
    output = []
    current_tasks = []
    
    # Heuristic to detect table format
    # 3-col: | ID | File | Description |
    # 6-col: | Done | Priority | ID | Dependency | Description | Source File |

    def flush():
        nonlocal current_tasks
        if current_tasks:
            current_tasks.sort(key=lambda x: x['prio'])
            output.append("| Done | Priority | ID | Dependency | Description | Source File |")
            output.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for t in current_tasks:
                # Ensure no empty descriptions
                d = t['desc'] if t['desc'] and t['desc'] != "None" else "Task details in source"
                output.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {d} | `{t['file']}` |")
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
            # Positional parsing
            # Remove leading/trailing pipes and split
            parts = [p.strip() for p in s.split('|') if p.strip()]
            
            tid = "TASK-000"
            f_path = "Unknown"
            desc = ""
            
            if len(parts) == 3: # Old format
                tid = parts[0]
                f_path = parts[1].replace('`', '')
                desc = parts[2]
            elif len(parts) >= 6: # New (possibly shifted) format
                # Find the TASK-ID
                for p in parts:
                    if "TASK-" in p: tid = p; break
                # Find the File (has backticks or is long path)
                for p in parts:
                    if "`" in p or "\\" in p or "/" in p:
                        if "TASK-" not in p: f_path = p.replace('`', ''); break
                # Description is the one that isn't ID, File, [ ], icon, or Dependency placeholder
                # We'll take the longest one that isn't those.
                candidates = []
                for p in parts:
                    if "TASK-" in p or p == tid: continue
                    if p.replace('`', '') == f_path: continue
                    if p in ["[ ]", "None", "Backend API", "Env Setup", "Security Sign-off"]: continue
                    if any(icon in p for icon in ["🔴", "🟠", "🟡", "🟢"]): continue
                    candidates.append(p)
                if candidates:
                    desc = max(candidates, key=len)
            
            if not desc: # Try to recover from the parts if everything was excluded
                if len(parts) >= 3: desc = parts[2]
            
            current_tasks.append({
                "tid": tid, "file": f_path, "desc": desc,
                "prio": get_priority(desc),
                "dep": get_dependency(desc)
            })
            continue
            
        if s.startswith("|") and any(h in s for h in ["ID", "Done", ":---"]):
            continue
            
        output.append(line)

    flush()

    final = "\n".join(output)
    final = re.sub(r'\n{3,}', '\n\n', final)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final)
    
    return "Master Backlog definitively fixed v3."

if __name__ == "__main__":
    print(process())
