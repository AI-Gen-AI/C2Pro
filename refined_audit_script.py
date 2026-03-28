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
    
    # AI / LLM / Coherence / Agents
    if any(k in path for k in ['agent', 'ai', 'mcp', 'coherence', 'analysis', 'prompt', 'langgraph', 'rag']):
        return "AI & Intelligence"
    if any(k in content for k in ['llm', 'anthropic', 'openai', 'vector store', 'embedding']):
        return "AI & Intelligence"
        
    # Frontend
    if any(k in path for k in ['apps/web', 'frontend', 'ui', 'wireframe', 'component', 'hook', 'css', 'react', 'nextjs']):
        return "Frontend"
    
    # Backend
    if any(k in path for k in ['apps/api', 'backend', 'module', 'persistence', 'repository', 'adapter', 'sqlalchemy', 'database', 'alembic', 'fastapi']):
        return "Backend"
        
    # DevOps & Infra
    if any(k in path for k in ['docker', 'github/workflow', 'deploy', 'infrastructure', 'cicd', 'makefile', 'ops', 'setup']):
        return "DevOps & Infrastructure"
    if "docker-compose" in content or "kubernetes" in content:
        return "DevOps & Infrastructure"
        
    # Testing (Specialized Category)
    if 'test' in path or 'tdd' in path or 'coverage' in path:
        return "Testing & Quality"
        
    return "General & Management"

def audit_markdown_files(root_dir):
    groups = {
        "Legacy (No Tasks)": [],
        "Legacy (With Pending Tasks)": [],
        "Backend": [],
        "Frontend": [],
        "AI & Intelligence": [],
        "DevOps & Infrastructure": [],
        "Testing & Quality": [],
        "General & Management": []
    }
    
    exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'everything-claude-code'}
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.relpath(os.path.join(root, file), root_dir)
                
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Task Detection
                        pending_tasks = re.findall(r'-\s*\[ \]\s*(.*)', content)
                        todos = re.findall(r'(?i)TODO:\s*(.*)', content)
                        task_count = len(pending_tasks) + len(todos)
                        
                        # Classification
                        is_legacy = any(k in file_path.lower() for k in ['legacy', 'archive', 'deprecated', 'old'])
                        
                        data = {
                            "File": file_path,
                            "Health": "✅" if task_count == 0 else "🔄",
                            "Tasks": task_count,
                            "Preview": (pending_tasks + todos)[0][:50] if task_count > 0 else "N/A"
                        }
                        
                        if is_legacy:
                            if task_count == 0:
                                groups["Legacy (No Tasks)"].append(data)
                            else:
                                groups["Legacy (With Pending Tasks)"].append(data)
                        else:
                            cat = get_tech_category(file_path, content)
                            groups[cat].append(data)
                            
                except Exception as e:
                    pass
    
    return groups

if __name__ == "__main__":
    audit_data = audit_markdown_files(".")
    
    print("# Refined C2Pro Documentation Audit Report")
    print(f"**Date:** 2026-03-28\n")
    
    for group_name, files in audit_data.items():
        if not files:
            continue
            
        print(f"## {group_name} ({len(files)} files)")
        print("| File | Health | Tasks | Task Preview |")
        print("| :--- | :--- | :--- | :--- |")
        
        # Sort by most tasks first in relevant groups
        if "With Pending Tasks" in group_name:
            files.sort(key=lambda x: x['Tasks'], reverse=True)
        else:
            files.sort(key=lambda x: x['File'])
            
        # Limit very large groups (like Legacy No Tasks) to top 100 to keep report readable
        display_files = files[:100]
        for f in display_files:
            print(f"| `{f['File']}` | {f['Health']} | {f['Tasks']} | {f['Preview']}... |")
            
        if len(files) > 100:
            print(f"| ... | ... | ... | *({len(files)-100} more files hidden for brevity)* |")
        print("\n")
