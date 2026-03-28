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
    
    # P0: Critical Infrastructure, Security, Core Auth, DB Migrations
    if any(k in desc for k in ['critical', 'security', 'auth', 'database migration', 'p0', 'benchmarks']):
        return "🔴 P0"
    if "clerk" in desc and "production" in desc:
        return "🔴 P0"
    if "setup test infrastructure" in desc:
        return "🔴 P0"
    
    # P1: Core Features, Main API, Main UI Views
    if any(k in desc for k in ['api endpoints', 'crud', 'dashboard', 'projects', 'p1']):
        return "🟠 P1"
    if "connect all ui views" in desc:
        return "🟠 P1"
    
    # P2: Enhancements, Quality, Secondary Features
    if any(k in desc for k in ['export', 'visualization', 'templates', 'p2', 'ui component']):
        return "🟡 P2"
    
    # P3: Documentation, Cleanup, Low Priority
    return "🟢 P3"

def get_dependency(desc, cat):
    desc = desc.lower()
    if "ui" in desc or "frontend" in desc or "view" in desc:
        return "Backend API"
    if "test" in desc or "run" in desc:
        return "Env Setup"
    if "deployment" in desc or "production" in desc:
        return "Security Sign-off"
    return "None"

def refine_backlog():
    try:
        with open("C2PRO_MASTER_BACKLOG.md", 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return "Backlog file not found."

    # Parse Sections
    sections = re.split(r'## (2\.\d+ .*?) \((\d+) tasks\)', content)
    
    header = "# C2Pro PRIORITIZED MASTER BACKLOG\n> **Task Registry & Dependency Matrix** | Updated on 2026-03-28\n\n"
    new_content = header
    
    # Re-extract Registry (Section 1)
    registry_match = re.search(r'## 1\. Documentation Registry & Health Check\n(.*?)\n\n##', content, re.S)
    if registry_match:
        new_content += "## 1. Documentation Registry & Health Check\n" + registry_match.group(1) + "\n\n"

    # Process Active Backlog Sections
    for i in range(1, len(sections), 3):
        title = sections[i]
        tasks_raw = sections[i+2].strip()
        
        new_content += f"## {title}\n"
        new_content += "| Done | Priority | ID | Dependency | Description | Source File |\n"
        new_content += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        
        # Parse table rows
        task_lines = re.findall(r'\| (TASK-\d+) \| `(.*?)` \| (.*?) \|', tasks_raw)
        
        prioritized_tasks = []
        for tid, file, desc in task_lines:
            prio = get_priority(desc, title, file)
            dep = get_dependency(desc, title)
            prioritized_tasks.append({
                "tid": tid, "file": file, "desc": desc, "prio": prio, "dep": dep
            })
            
        # Sort by Priority
        prioritized_tasks.sort(key=lambda x: x['prio'])
        
        for t in prioritized_tasks:
            new_content += f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |\n"
        new_content += "\n"

    # Process Section 3: Legacy
    legacy_match = re.search(r'## 3\. Legacy Task Resurrections\n.*?\n(\| :--- \| :--- \| :--- \|\n)(.*?)\n\n##', content, re.S)
    if legacy_match:
        new_content += "## 3. Legacy Task Resurrections\n"
        new_content += "| Done | Priority | ID | Dependency | Description | Source File |\n"
        new_content += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        legacy_tasks = re.findall(r'\| (TASK-\d+) \| `(.*?)` \| (.*?) \|', legacy_match.group(2))
        for tid, file, desc in legacy_tasks:
            prio = get_priority(desc, "Legacy", file)
            dep = get_dependency(desc, "Legacy")
            new_content += f"| [ ] | {prio} | {tid} | {dep} | {desc} | `{file}` |\n"
        new_content += "\n"

    # Archive Registry
    archive_match = re.search(r'## 4\. Archive Registry (.*?)$', content, re.S)
    if archive_match:
        new_content += "## 4. Archive Registry " + archive_match.group(1)

    return new_content

if __name__ == "__main__":
    refined = refine_backlog()
    print(refined)
