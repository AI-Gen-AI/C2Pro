import os
import re
import sys
import codecs

# Force UTF-8
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

def get_priority(desc, section, file_path):
    desc = desc.lower()
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

def process():
    path = "C2PRO_MASTER_BACKLOG.md"
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # 1. Pre-process artifacts
    content = content.replace("\r\n", "\n")
    content = re.sub(r' +', ' ', content) # Multi-spaces to single
    
    # Recover Spanish
    content = content.replace("producci%n", "producción").replace("producci%%n", "producción")
    content = content.replace("versi%n", "versión").replace("versi%%n", "versión")
    content = content.replace("espa%ol", "español").replace("espa%%ol", "español")

    lines = content.split('\n')
    sections = []
    current_section_name = "Header"
    current_section_lines = []
    
    # Registry and Header preservation
    # We'll just split by headers
    for line in lines:
        if line.startswith("#") or line.startswith("## ") or line.startswith("### "):
            sections.append((current_section_name, current_section_lines))
            current_section_name = line.strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)
    sections.append((current_section_name, current_section_lines))

    final_output = []
    
    for sec_title, sec_lines in sections:
        if sec_title == "Header":
            final_output.extend(sec_lines)
            continue
            
        final_output.append(sec_title)
        
        # Extract tasks from this section
        tasks = []
        other_lines = []
        
        for line in sec_lines:
            if "| TASK-" in line:
                # Robust extraction
                parts = [p.strip() for p in line.split('|') if p.strip()]
                # parts[0] should be TASK-XXX
                # parts[1] should be `file`
                # parts[2] should be description
                if len(parts) >= 3:
                    tid = parts[0]
                    f_path = parts[1].replace('`', '')
                    desc = " ".join(parts[2:])
                    tasks.append({
                        "tid": tid, "file": f_path, "desc": desc,
                        "prio": get_priority(desc, sec_title, f_path),
                        "dep": get_dependency(desc)
                    })
            elif "| Done | Priority |" in line or "| :--- | :--- |" in line or "| ID | File | Description |" in line:
                continue # Skip old headers
            else:
                if line.strip():
                    other_lines.append(line)

        # Write other lines first (intro text)
        final_output.extend(other_lines)
        
        # Write prioritized table
        if tasks:
            tasks.sort(key=lambda x: x['prio'])
            final_output.append("")
            final_output.append("| Done | Priority | ID | Dependency | Description | Source File |")
            final_output.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for t in tasks:
                final_output.append(f"| [ ] | {t['prio']} | {t['tid']} | {t['dep']} | {t['desc']} | `{t['file']}` |")
            final_output.append("")

    # Clean up blank lines
    raw_res = "\n".join(final_output)
    raw_res = re.sub(r'\n{3,}', '\n\n', raw_res)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(raw_res)
    
    return "Backlog absolutely restructured."

if __name__ == "__main__":
    print(process())
