import os
import re
import sys

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def audit_markdown_files(root_dir):
    audit_results = []
    
    # Exclude directories that are typically noise or reference-only
    exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache'}
    
    for root, dirs, files in os.walk(root_dir):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.relpath(os.path.join(root, file), root_dir)
                
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Basic Metadata Extraction
                        status_match = re.search(r'(?i)Status:\s*(.*)', content)
                        version_match = re.search(r'(?i)Version:\s*(.*)', content)
                        
                        # Task Detection
                        pending_tasks = re.findall(r'-\s*\[ \]\s*(.*)', content)
                        todos = re.findall(r'(?i)TODO:\s*(.*)', content)
                        
                        # Classification logic (Heuristic)
                        category = "Updated"
                        if "legacy" in file_path.lower() or "archive" in file_path.lower():
                            category = "Legacy"
                        elif "outdated" in content.lower() or "deprecated" in content.lower():
                            category = "Outdated"
                        elif "v1." in content and "v4." not in content and "architecture" in file_path.lower():
                            category = "Outdated (Old Version)"
                        
                        health = "✅"
                        if category != "Updated":
                            health = "⚠️"
                        if len(pending_tasks) > 0 or len(todos) > 0:
                            health = "🔄"
                            
                        audit_results.append({
                            "File": file_path,
                            "Status": status_match.group(1).strip() if status_match else "Unknown",
                            "Version": version_match.group(1).strip() if version_match else "N/A",
                            "Health": health,
                            "Pending_Tasks": len(pending_tasks) + len(todos),
                            "Category": category,
                            "Task_Preview": (pending_tasks + todos)[0][:50] if (pending_tasks + todos) else "None"
                        })
                except Exception as e:
                    audit_results.append({
                        "File": file_path,
                        "Status": "Error",
                        "Version": "N/A",
                        "Health": "❌",
                        "Pending_Tasks": 0,
                        "Category": "Unreadable",
                        "Task_Preview": str(e)[:50]
                    })
    
    return audit_results

if __name__ == "__main__":
    results = audit_markdown_files(".")
    
    # Sort results by Category (Updated first) then File path
    results.sort(key=lambda x: (x['Category'], x['File']))
    
    print("| File | Category | Health | Status/Version | Pending Tasks | Notes |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        # Filter for "Doc and Context" relevant files (excluding individual test summaries to keep output manageable)
        # But for the user, I'll include them in the file I write.
        notes = f"Tasks: {r['Task_Preview']}..." if r['Pending_Tasks'] > 0 else "No pending tasks."
        print(f"| `{r['File']}` | **{r['Category']}** | {r['Health']} | {r['Status']} (v{r['Version']}) | {r['Pending_Tasks']} | {notes} |")
