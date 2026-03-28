import os
import re
import sys
import codecs

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_tech_category(path, content):
    path = path.lower()
    content = content.lower()
    if any(k in path for k in ['agent', 'ai', 'mcp', 'coherence', 'analysis', 'prompt', 'langgraph', 'rag']):
        return "AI & Intelligence"
    if any(k in path for k in ['apps/web', 'frontend', 'ui', 'wireframe', 'component', 'hook', 'css', 'react', 'nextjs']):
        return "Frontend"
    if any(k in path for k in ['apps/api', 'backend', 'module', 'persistence', 'repository', 'adapter', 'sqlalchemy', 'database', 'alembic', 'fastapi']):
        return "Backend"
    if any(k in path for k in ['docker', 'github/workflow', 'deploy', 'infrastructure', 'cicd', 'makefile', 'ops', 'setup']):
        return "DevOps & Infrastructure"
    if 'test' in path or 'tdd' in path or 'coverage' in path:
        return "Testing & Quality"
    return "General & Management"

def generate_master_backlog(root_dir):
    registry = []
    active_backlog = {
        "Backend": [], "Frontend": [], "AI & Intelligence": [],
        "DevOps & Infrastructure": [], "Testing & Quality": [], "General & Management": []
    }
    legacy_with_tasks = []
    clean_archive = []
    
    task_id_counter = 1
    exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'everything-claude-code'}

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.relpath(os.path.join(root, file), root_dir)
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        pending_tasks = re.findall(r'-\s*\[ \]\s*(.*)', content)
                        todos = re.findall(r'(?i)TODO:\s*(.*)', content)
                        task_list = pending_tasks + todos
                        task_count = len(task_list)
                        
                        is_legacy = any(k in file_path.lower() for k in ['legacy', 'archive', 'deprecated', 'old'])
                        cat = get_tech_category(file_path, content)
                        
                        # Registry Info
                        status_match = re.search(r'(?i)Status:\s*(.*)', content)
                        registry.append({
                            "File": file_path,
                            "Category": "Legacy" if is_legacy else "Current",
                            "Health": "✅" if task_count == 0 else "🔄",
                            "Tasks": task_count,
                            "Status": status_match.group(1).strip() if status_match else "N/A"
                        })

                        # Task Processing
                        for task_desc in task_list:
                            task_data = {
                                "ID": f"TASK-{task_id_counter:03d}",
                                "File": file_path,
                                "Description": task_desc.strip().replace("|", "\\|")
                            }
                            task_id_counter += 1
                            
                            if is_legacy:
                                legacy_with_tasks.append(task_data)
                            else:
                                active_backlog[cat].append(task_data)
                        
                        if is_legacy and task_count == 0:
                            clean_archive.append(file_path)
                            
                except Exception:
                    pass

    # Start writing output
    print("# C2Pro MASTER BACKLOG & DOCUMENTATION AUDIT")
    print("> **Consolidated Report** | Generated on 2026-03-28\n")
    
    print("## 1. Documentation Registry & Health Check")
    print("| File | Scope | Health | Status | Tasks |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    for r in sorted(registry, key=lambda x: (x['Category'], x['File'])):
        print(f"| `{r['File']}` | {r['Category']} | {r['Health']} | {r['Status']} | {r['Tasks']} |")
    print("\n")

    print("## 2. Active Development Backlog (Categorized)")
    for cat, tasks in active_backlog.items():
        print(f"### 2.{list(active_backlog.keys()).index(cat)+1} {cat} ({len(tasks)} tasks)")
        if not tasks:
            print("*No active tasks identified.*\n")
            continue
        print("| ID | File | Description |")
        print("| :--- | :--- | :--- |")
        for t in tasks:
            print(f"| {t['ID']} | `{t['File']}` | {t['Description']} |")
        print("\n")

    print("## 3. Legacy Task Resurrections")
    print("> Tasks extracted from archived or deprecated files that may still require attention.")
    if not legacy_with_tasks:
        print("*No legacy tasks identified.*\n")
    else:
        print("| ID | File | Description |")
        print("| :--- | :--- | :--- |")
        for t in legacy_with_tasks:
            print(f"| {t['ID']} | `{t['File']}` | {t['Description']} |")
    print("\n")

    print("## 4. Archive Registry (Clean - No Tasks)")
    print("> Historical files with no pending actions.")
    for f in sorted(clean_archive):
        print(f"- `{f}`")

if __name__ == "__main__":
    generate_master_backlog(".")
