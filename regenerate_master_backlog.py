import os
import re
import sys
import codecs

# Force UTF-8
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc, path):
    d = desc.lower()
    p = path.lower()
    if any(k in d for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmark', 'env setup', 'python 3.11', 'postgresql', 'production-like']):
        return "🔴 P0"
    if "clerk" in d and "production" in d:
        return "🔴 P0"
    if "setup test infrastructure" in d or "setup vitest" in d:
        return "🔴 P0"
    if "final_summary_ts-e2e-sec-tnt-001" in p:
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

def get_tech_category(path, content):
    path = path.lower()
    content = content.lower()
    if any(k in path for k in ['agent', 'ai', 'mcp', 'coherence', 'analysis', 'prompt', 'langgraph', 'rag']): return "AI & Intelligence"
    if any(k in path for k in ['apps/web', 'frontend', 'ui', 'wireframe', 'component', 'hook', 'css', 'react', 'nextjs']): return "Frontend"
    if any(k in path for k in ['apps/api', 'backend', 'module', 'persistence', 'repository', 'adapter', 'sqlalchemy', 'database', 'alembic', 'fastapi']): return "Backend"
    if any(k in path for k in ['docker', 'github/workflow', 'deploy', 'infrastructure', 'cicd', 'makefile', 'ops', 'setup']): return "DevOps & Infrastructure"
    if 'test' in path or 'tdd' in path or 'coverage' in path: return "Testing & Quality"
    return "General & Management"

def generate():
    root_dir = "."
    exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'everything-claude-code'}
    
    registry = []
    active_backlog = {
        "Backend": [], "Frontend": [], "AI & Intelligence": [],
        "DevOps & Infrastructure": [], "Testing & Quality": [], "General & Management": []
    }
    legacy_tasks = []
    archive_clean = []
    
    task_id_counter = 1

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith('.md') and file != "C2PRO_MASTER_BACKLOG.md":
                file_path = os.path.relpath(os.path.join(root, file), root_dir)
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Extract tasks
                        raw_tasks = re.findall(r'-\s*\[ \]\s*(.*)', content)
                        todos = re.findall(r'(?i)TODO:\s*(.*)', content)
                        all_task_descs = raw_tasks + todos
                        
                        is_legacy = any(k in file_path.lower() for k in ['legacy', 'archive', 'deprecated', 'old'])
                        cat = get_tech_category(file_path, content)
                        
                        # Registry metadata
                        status_match = re.search(r'(?i)Status:\s*(.*)', content)
                        registry.append({
                            "File": file_path, "Scope": "Legacy" if is_legacy else "Current",
                            "Health": "✅" if not all_task_descs else "🔄",
                            "Status": status_match.group(1).strip() if status_match else "N/A",
                            "Tasks": len(all_task_descs)
                        })

                        for desc in all_task_descs:
                            desc = desc.strip().replace("|", "\\|")
                            if not desc: continue
                            
                            t_data = {
                                "tid": f"TASK-{task_id_counter:03d}",
                                "file": file_path,
                                "desc": desc,
                                "prio": get_priority(desc, file_path),
                                "dep": get_dependency(desc)
                            }
                            task_id_counter += 1
                            
                            if is_legacy: legacy_tasks.append(t_data)
                            else: active_backlog[cat].append(t_data)
                            
                        if is_legacy and not all_task_descs:
                            archive_clean.append(file_path)
                            
                except: pass

    # Sort Registry
    registry.sort(key=lambda x: (x['Scope'], x['File']))

    # Write Output
    with open("C2PRO_MASTER_BACKLOG.md", 'w', encoding='utf-8') as f:
        f.write("# C2Pro MASTER BACKLOG & DOCUMENTATION AUDIT\n")
        f.write("> **Unified Roadmap** | Generated on 2026-03-28\n\n")
        
        f.write("## 1. Documentation Registry & Health Check\n")
        f.write("| File | Scope | Health | Status | Tasks |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for r in registry:
            f.write(f"| `{r['File']}` | {r['Scope']} | {r['Health']} | {r['Status']} | {r['Tasks']} |\n")
        f.write("\n")
        
        f.write("## 2. Active Development Backlog (Categorized)\n")
        for cat, tasks in active_backlog.items():
            f.write(f"### 2.{list(active_backlog.keys()).index(cat)+1} {cat} ({len(tasks)} tasks)\n")
            if not tasks:
                f.write("*No active tasks identified.*\n\n")
                continue
            
            f.write("| Done | Priority | ID | Dependency | Description | Source File |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            tasks.sort(key=lambda x: x['prio'])
            for t in tasks:
                f.write(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |\n")
            f.write("\n")
            
        f.write("## 3. Legacy Task Resurrections\n")
        f.write("> Tasks extracted from archived or deprecated folders.\n\n")
        if not legacy_tasks:
            f.write("*No legacy tasks identified.*\n\n")
        else:
            f.write("| Done | Priority | ID | Dependency | Description | Source File |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            legacy_tasks.sort(key=lambda x: x['prio'])
            for t in legacy_tasks:
                f.write(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |\n")
            f.write("\n")
            
        f.write("## 4. Archive Registry (Clean)\n")
        for file in sorted(archive_clean):
            f.write(f"- `{file}`\n")

if __name__ == "__main__":
    generate()
    print("Backlog regenerated from scratch successfully.")
